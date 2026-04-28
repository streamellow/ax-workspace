"""
Indexing — 이메일 수집 · 분류 · 채용공고 구조화
"""

import re
import base64
import json
import email
import imaplib
import datetime
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime
from openai import OpenAI
from bs4 import BeautifulSoup

from core.schemas import CATEGORIES, Email, Classification, JobPosting


def _strip_html(html: str) -> str:
    text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&[a-z]+;", "", text)
    text = re.sub(r"\s{2,}", "\n", text)
    return text.strip()


def _get_email_parts(payload: dict, max_chars: int = 5000) -> tuple[str, str]:
    plain, html = "", ""
    stack = list(payload.get("parts", []) or [payload])
    while stack:
        part = stack.pop()
        mime = part.get("mimeType", "")
        if mime.startswith("multipart/"):
            stack.extend(part.get("parts", []))
            continue
        data = part.get("body", {}).get("data", "")
        if not data:
            continue
        decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        if mime == "text/plain" and not plain:
            plain = decoded
        elif mime == "text/html" and not html:
            html = decoded
    return (plain if plain else _strip_html(html))[:max_chars], html


def _parse_email_date(date_str: str) -> datetime.datetime | None:
    try:
        return parsedate_to_datetime(date_str).replace(tzinfo=None)
    except Exception:
        return None


def fetch_emails(
    service,
    max_results: int = 50,
    since_dt: datetime.datetime | None = None,
) -> list[Email]:
    params: dict = {"userId": "me", "labelIds": ["INBOX"], "maxResults": max_results}
    if since_dt:
        params["q"] = f"after:{int(since_dt.timestamp())}"

    result = service.users().messages().list(**params).execute()

    emails = []
    for msg in result.get("messages", []):
        detail = service.users().messages().get(
            userId="me", id=msg["id"], format="full"
        ).execute()
        headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
        body, html_body = _get_email_parts(detail["payload"])
        emails.append(Email(
            id=msg["id"],
            subject=headers.get("Subject", "(제목 없음)"),
            sender=headers.get("From", ""),
            date=headers.get("Date", ""),
            body=body,
            html_body=html_body,
        ))

    if since_dt:
        emails = [
            e for e in emails
            if (dt := _parse_email_date(e.date)) and dt >= since_dt
        ]

    return emails


def fetch_emails_imap(
    conn: imaplib.IMAP4_SSL,
    max_results: int = 50,
    since_dt: datetime.datetime | None = None,
) -> list[Email]:
    conn.select("INBOX")
    if since_dt:
        date_str = since_dt.strftime("%d-%b-%Y")
        _, data = conn.search(None, f'SINCE "{date_str}"')
    else:
        _, data = conn.search(None, "ALL")
    all_ids = data[0].split()
    target_ids = all_ids[-max_results:][::-1]

    emails = []
    for uid in target_ids:
        _, msg_data = conn.fetch(uid, "(RFC822)")
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)

        subject = str(make_header(decode_header(msg.get("Subject", "(제목 없음)"))))
        sender  = str(make_header(decode_header(msg.get("From", ""))))
        date    = msg.get("Date", "")

        plain, html_body = "", ""
        if msg.is_multipart():
            for part in msg.walk():
                mime = part.get_content_type()
                charset = part.get_content_charset() or "utf-8"
                if mime == "text/plain" and not plain:
                    plain = part.get_payload(decode=True).decode(charset, errors="ignore")
                elif mime == "text/html" and not html_body:
                    html_body = part.get_payload(decode=True).decode(charset, errors="ignore")
        else:
            charset = msg.get_content_charset() or "utf-8"
            payload = msg.get_payload(decode=True).decode(charset, errors="ignore")
            if msg.get_content_type() == "text/html":
                html_body = payload
            else:
                plain = payload

        body = (plain if plain else _strip_html(html_body))[:5000]
        emails.append(Email(
            id=uid.decode(),
            subject=subject,
            sender=sender,
            date=date,
            body=body,
            html_body=html_body,
        ))
    conn.logout()

    if since_dt:
        emails = [
            e for e in emails
            if (dt := _parse_email_date(e.date)) and dt >= since_dt
        ]

    return emails


def classify_emails(emails: list[Email]) -> list[Classification]:
    client = OpenAI()
    items = ""
    for i, e in enumerate(emails):
        items += f"\n[{i+1}]\n발신자: {e.sender}\n제목: {e.subject}\n본문 미리보기: {e.body[:200]}\n---"

    prompt = f"""다음 이메일 목록을 분류해주세요.

분류 카테고리:
{chr(10).join(f"- {c}" for c in CATEGORIES)}

분류 기준:
- 채용공고 알림, 면접 안내, 입사 지원 관련 메일 → 업무/비즈니스
- 정기 구독 뉴스레터, 마케팅 홍보 메일 → 뉴스레터/마케팅

이메일 목록:
{items}

각 이메일에 대해 다음 JSON 배열 형식으로만 응답하세요 (다른 텍스트 없이):
[
  {{"index": 1, "category": "카테고리명", "summary": "한 줄 요약 (30자 이내)"}},
  ...
]"""

    response = client.chat.completions.create(
        model="gpt-4o-mini", max_tokens=4096, temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    text = _parse_json_text(response.choices[0].message.content)
    return [Classification(**c) for c in json.loads(text)]


def _extract_html_links(html: str, limit: int = 60) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    lines = []
    seen: set[str] = set()
    trivial = ("unsubscribe", "수신거부", "mailto:", "tel:", "facebook.com",
                "twitter.com", "instagram.com", "youtube.com")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http"):
            continue
        if any(t in href.lower() for t in trivial):
            continue
        if href in seen:
            continue
        seen.add(href)
        label = " ".join(a.stripped_strings).strip()
        lines.append(f"  - {label or '(링크)'}: {href}")
        if len(lines) >= limit:
            break
    return "\nHTML 링크 목록:\n" + "\n".join(lines) if lines else ""


def extract_job_postings(business_emails: list[Email]) -> list[JobPosting]:
    client = OpenAI()
    items = ""
    for i, e in enumerate(business_emails):
        html_links = _extract_html_links(e.html_body)
        items += (
            f"\n[이메일 {i+1}]\n제목: {e.subject}\n발신자: {e.sender}\n날짜: {e.date}"
            f"\n본문: {e.body}{html_links}\n---"
        )

    prompt = (
        "다음 이메일 본문에서 채용공고 항목을 하나씩 모두 추출해주세요.\n\n"
        "규칙:\n"
        "- 이메일 한 통에 여러 채용공고가 나열된 경우 각 공고를 개별 항목으로 추출하세요.\n"
        "- 직무명, 회사명, 지역이 본문에 명시된 그대로 추출하세요.\n"
        "- 재택근무·혼합근무 등 근무형태가 지역에 표기된 경우 그대로 포함하세요.\n"
        "- 채용공고가 아닌 일반 업무 메일은 건너뜁니다.\n"
        "- HTML 링크 목록이 제공된 경우, 각 공고의 제목·회사명과 가장 잘 맞는 링크를 url로 지정하세요.\n"
        "- 링크가 명확히 매칭되지 않더라도, 채용 관련 포털(사람인·잡코리아·원티드 등) URL이 있으면 url에 넣으세요.\n\n"
        f"이메일 목록:\n{items}\n\n"
        "모든 채용공고를 추출하여 다음 JSON 형식으로만 응답하세요 (다른 텍스트 없이):\n"
        "{\n"
        '  "job_postings": [\n'
        "    {\n"
        '      "job_title": "직무명",\n'
        '      "company": "회사명",\n'
        '      "location": "지역 (모르면 null)",\n'
        '      "source_email": "출처 이메일 제목 (정확히 복사)",\n'
        '      "url": "공고 URL (본문 또는 HTML 링크 목록에서, 없으면 null)",\n'
        '      "deadline": "마감일 YYYY-MM-DD 형식 (본문에서 추출, 없으면 null)"\n'
        "    }\n"
        "  ]\n"
        "}"
    )

    response = client.chat.completions.create(
        model="gpt-4o", max_tokens=8192, temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    text = _parse_json_text(response.choices[0].message.content)
    data = _safe_parse_json(text)
    return [JobPosting(**p) for p in data.get("job_postings", [])]


PORTAL_DOMAINS = ("saramin.co.kr", "jobkorea.co.kr", "wanted.co.kr",
                  "linkareer.com", "incruit.com", "rallit.com", "jumpit.co.kr")
PORTAL_KWS = ("saramin", "jobkorea", "wanted", "linkareer", "incruit",
               "rallit", "jumpit", "job", "jobs", "career", "careers",
               "position", "recruit")
_TRIVIAL_HREF = ("unsubscribe", "수신거부", "mailto:", "tel:",
                 "facebook.com", "twitter.com", "instagram.com", "youtube.com")


def resolve_job_urls(business_emails: list[Email], postings: list[JobPosting]) -> list[JobPosting]:
    links_by_subject: dict[str, list[tuple[str, str]]] = {}
    plain_by_subject: dict[str, list[str]] = {}

    for e in business_emails:
        pairs: list[tuple[str, str]] = []
        if e.html_body:
            soup = BeautifulSoup(e.html_body, "html.parser")
            seen: set[str] = set()
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if not href.startswith("http") or href in seen:
                    continue
                if any(t in href.lower() for t in _TRIVIAL_HREF):
                    continue
                seen.add(href)
                label = " ".join(a.stripped_strings).lower().strip()
                pairs.append((label, href))
        links_by_subject[e.subject] = pairs
        plain_by_subject[e.subject] = re.findall(r'https?://[^\s\)\]\>\"\']+', e.body)

    def _best_subject(src: str) -> str:
        if src in links_by_subject:
            return src
        best, best_score = src, 0
        for subj in links_by_subject:
            score = sum(1 for w in src.split() if w in subj)
            if score > best_score:
                best, best_score = subj, score
        return best

    used_idx: dict[str, set[int]] = {s: set() for s in links_by_subject}
    all_portal_hrefs: list[str] = []
    seen_global: set[str] = set()
    for pairs in links_by_subject.values():
        for _, href in pairs:
            if any(d in href for d in PORTAL_DOMAINS) and href not in seen_global:
                all_portal_hrefs.append(href)
                seen_global.add(href)
    used_global: set[str] = set()

    result = []
    for p in postings:
        url = p.url
        title = p.job_title.lower()
        title_words = {w for w in re.split(r"[\s/·,]+", title) if len(w) >= 2}
        src = _best_subject(p.source_email)
        pairs = links_by_subject.get(src, [])
        plain_urls = plain_by_subject.get(src, [])
        idx_used = used_idx.setdefault(src, set())

        if not url:
            for idx, (label, href) in enumerate(pairs):
                if idx in idx_used:
                    continue
                if title in label or label in title:
                    url = href
                    idx_used.add(idx)
                    break

        if not url and title_words:
            for idx, (label, href) in enumerate(pairs):
                if idx in idx_used:
                    continue
                label_words = set(re.split(r"[\s/·,\[\]()\-]+", label))
                if title_words & label_words:
                    url = href
                    idx_used.add(idx)
                    break

        if not url and title_words:
            for pu in plain_urls:
                if any(w in pu.lower() for w in title_words):
                    url = pu
                    break

        if not url:
            for idx, (_, href) in enumerate(pairs):
                if idx in idx_used:
                    continue
                if any(kw in href.lower() for kw in PORTAL_KWS):
                    url = href
                    idx_used.add(idx)
                    break

        if not url:
            for idx, (_, href) in enumerate(pairs):
                if idx in idx_used:
                    url = href
                    idx_used.add(idx)
                    break

        if not url:
            for href in all_portal_hrefs:
                if href not in used_global:
                    url = href
                    used_global.add(href)
                    break

        result.append(p.model_copy(update={"url": url}))
    return result


def _parse_json_text(text: str) -> str:
    text = text.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


def _safe_parse_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        last = text.rfind("},")
        if last != -1:
            trimmed = text[:last + 1] + "\n  ]\n}"
            try:
                return json.loads(trimmed)
            except json.JSONDecodeError:
                pass
        return {"job_postings": []}
