"""
Indexing — 이메일 수집 · 분류 · 채용공고 구조화
Gmail API → raw Email 리스트 → Classification + JobPosting 추출
"""

import re
import base64
import json
from openai import OpenAI
from bs4 import BeautifulSoup

from schemas import CATEGORIES, Email, Classification, JobPosting


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


def fetch_emails(service, max_results: int = 30) -> list[Email]:
    result = service.users().messages().list(
        userId="me", labelIds=["INBOX"], maxResults=max_results
    ).execute()

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


def extract_job_postings(business_emails: list[Email]) -> list[JobPosting]:
    client = OpenAI()
    items = ""
    for i, e in enumerate(business_emails):
        items += f"\n[이메일 {i+1}]\n제목: {e.subject}\n발신자: {e.sender}\n날짜: {e.date}\n본문: {e.body}\n---"

    prompt = f"""다음 이메일 본문에서 채용공고 항목을 하나씩 모두 추출해주세요.

규칙:
- 이메일 한 통에 여러 채용공고가 나열된 경우 각 공고를 개별 항목으로 추출하세요.
- 직무명, 회사명, 지역이 본문에 명시된 그대로 추출하세요.
- 재택근무·혼합근무 등 근무형태가 지역에 표기된 경우 그대로 포함하세요.
- 채용공고가 아닌 일반 업무 메일은 건너뜁니다.

이메일 목록:
{items}

모든 채용공고를 추출하여 다음 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "job_postings": [
    {{
      "job_title": "직무명",
      "company": "회사명",
      "location": "지역 (모르면 null)",
      "source_email": "출처 이메일 제목",
      "url": "본문에 포함된 공고 URL (없으면 null)"
    }}
  ]
}}"""

    response = client.chat.completions.create(
        model="gpt-4o", max_tokens=8192, temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    text = _parse_json_text(response.choices[0].message.content)
    data = _safe_parse_json(text)
    return [JobPosting(**p) for p in data.get("job_postings", [])]


def resolve_job_urls(business_emails: list[Email], postings: list[JobPosting]) -> list[JobPosting]:
    """HTML <a> 태그 및 plain text 정규식으로 URL 보완 (3단계 우선순위)"""
    html_link_map: dict[str, str] = {}
    for e in business_emails:
        if not e.html_body:
            continue
        soup = BeautifulSoup(e.html_body, "html.parser")
        for a in soup.find_all("a", href=True):
            label = " ".join(a.stripped_strings).lower()
            href = a["href"]
            if href.startswith("http") and label:
                html_link_map[label] = href

    plain_urls: list[str] = []
    for e in business_emails:
        plain_urls.extend(re.findall(r'https?://[^\s\)\]\>\"\']+', e.body))

    result = []
    for p in postings:
        url = p.url
        title = p.job_title.lower()

        if not url:
            for label, href in html_link_map.items():
                if title in label or label in title:
                    url = href
                    break

        if not url:
            title_words = {w for w in title.split() if len(w) > 3}
            for pu in plain_urls:
                if any(w in pu.lower() for w in title_words):
                    url = pu
                    break

        if not url:
            job_kws = ["job", "jobs", "career", "careers", "position", "recruit"]
            for pu in plain_urls:
                if any(kw in pu.lower() for kw in job_kws):
                    url = pu
                    break

        result.append(p.model_copy(update={"url": url}))
    return result


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────

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