"""
Gmail 이메일 분류기
- Gmail API로 이메일 가져오기
- Claude API로 자동 분류
- 분류별 개수 및 요약 출력
"""

import os
import re
import base64
import json
from collections import defaultdict
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

CATEGORIES = [
    "업무/비즈니스",
    "뉴스레터/마케팅",
    "금융/결제",
    "소셜/알림",
    "개인",
    "스팸/광고",
    "기타",
]


def get_gmail_service():
    creds = None
    token_path = "token.json"
    creds_path = "credentials.json"

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(creds_path):
                raise FileNotFoundError(
                    "credentials.json 파일이 없습니다.\n"
                    "Google Cloud Console에서 OAuth 2.0 클라이언트 ID를 생성하고\n"
                    "credentials.json을 이 폴더에 저장하세요."
                )
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def strip_html(html):
    """HTML 태그 제거 후 공백 정리"""
    text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&[a-z]+;", "", text)
    text = re.sub(r"\s{2,}", "\n", text)
    return text.strip()


def get_email_parts(payload, max_chars=5000):
    """이메일에서 텍스트 본문과 raw HTML 모두 추출"""
    plain = ""
    html = ""

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

    body_text = (plain if plain else strip_html(html))[:max_chars]
    return body_text, html


def fetch_emails(service, max_results=50):
    """받은편지함에서 이메일 가져오기"""
    print(f"최근 {max_results}개 이메일을 가져오는 중...")
    result = service.users().messages().list(
        userId="me",
        labelIds=["INBOX"],
        maxResults=max_results
    ).execute()

    messages = result.get("messages", [])
    emails = []

    for i, msg in enumerate(messages):
        print(f"  이메일 읽기 중... ({i+1}/{len(messages)})", end="\r")
        msg_detail = service.users().messages().get(
            userId="me", id=msg["id"], format="full"
        ).execute()

        headers = {h["name"]: h["value"] for h in msg_detail["payload"]["headers"]}
        body, html_body = get_email_parts(msg_detail["payload"])

        emails.append({
            "id": msg["id"],
            "subject": headers.get("Subject", "(제목 없음)"),
            "sender": headers.get("From", ""),
            "date": headers.get("Date", ""),
            "body": body,
            "html_body": html_body,
        })

    print(f"\n총 {len(emails)}개 이메일 로드 완료.")
    return emails


def classify_emails_with_claude(emails):
    """OpenAI API로 이메일 일괄 분류"""
    client = OpenAI()

    email_list_text = ""
    for i, email in enumerate(emails):
        email_list_text += f"""
[{i+1}]
발신자: {email['sender']}
제목: {email['subject']}
본문 미리보기: {email['body'][:200]}
---"""

    prompt = f"""다음 이메일 목록을 분류해주세요.

분류 카테고리:
{chr(10).join(f"- {c}" for c in CATEGORIES)}

분류 기준:
- 채용공고 알림, 면접 안내, 입사 지원 관련 메일 → 업무/비즈니스
- 정기 구독 뉴스레터, 마케팅 홍보 메일 → 뉴스레터/마케팅

이메일 목록:
{email_list_text}

각 이메일에 대해 다음 JSON 배열 형식으로만 응답하세요 (다른 텍스트 없이):
[
  {{"index": 1, "category": "카테고리명", "summary": "한 줄 요약 (30자 이내)"}},
  ...
]"""

    print("OpenAI로 이메일 분류 중...")
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=4096,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.choices[0].message.content.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    return json.loads(text)


def summarize_business_emails(business_emails):
    """업무/비즈니스 이메일 상세 요약"""
    client = OpenAI()

    email_list_text = ""
    for i, email in enumerate(business_emails):
        email_list_text += f"""
[{i+1}]
발신자: {email['sender']}
제목: {email['subject']}
날짜: {email['date']}
본문: {email['body']}
---"""

    prompt = f"""다음 업무/비즈니스 이메일들을 각각 상세 요약해주세요.

이메일 목록:
{email_list_text}

각 이메일에 대해 다음 JSON 배열 형식으로만 응답하세요 (다른 텍스트 없이):
[
  {{
    "index": 1,
    "subject": "제목",
    "sender": "발신자",
    "date": "날짜",
    "key_points": ["핵심 내용 1", "핵심 내용 2"],
    "action_required": "필요한 조치 (없으면 null)",
    "detail_summary": "3~5문장의 상세 요약"
  }},
  ...
]"""

    print("업무 메일 상세 요약 중...")
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.choices[0].message.content.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    return json.loads(text)


def extract_job_postings(business_emails):
    """업무 메일 중 채용공고를 개별 공고 단위로 추출"""
    client = OpenAI()

    email_list_text = ""
    for i, email in enumerate(business_emails):
        email_list_text += f"""
[이메일 {i+1}]
제목: {email['subject']}
발신자: {email['sender']}
날짜: {email['date']}
본문: {email['body']}
---"""

    prompt = f"""다음 이메일 본문에서 채용공고 항목을 하나씩 모두 추출해주세요.

규칙:
- 이메일 한 통에 여러 채용공고가 나열된 경우 각 공고를 개별 항목으로 추출하세요.
- 직무명, 회사명, 지역이 본문에 명시된 그대로 추출하세요.
- 재택근무·혼합근무 등 근무형태가 지역에 표기된 경우 그대로 포함하세요.
- 채용공고가 아닌 일반 업무 메일은 건너뜁니다.

이메일 목록:
{email_list_text}

모든 채용공고를 추출하여 다음 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "job_postings": [
    {{
      "job_title": "직무명",
      "company": "회사명",
      "location": "지역 (재택근무 등 포함, 모르면 null)",
      "source_email": "출처 이메일 제목",
      "url": "본문에 포함된 공고 URL (없으면 null)"
    }}
  ]
}}"""

    print("채용공고 분류 및 정리 중...")
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=8192,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.choices[0].message.content.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    # 잘린 JSON 복구: 마지막 완성된 항목까지만 파싱
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        last = text.rfind("},")
        if last != -1:
            text = text[:last+1] + "\n  ]\n}"
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        print("  경고: 채용공고 JSON 파싱 실패 — 결과를 건너뜁니다.")
        return {"job_postings": []}


def extract_job_links(business_emails, job_postings):
    """채용공고 URL 결정 (우선순위: OpenAI추출 → HTML링크 → plain text regex)"""

    # 1순위: extract_job_postings 에서 OpenAI가 뽑은 url 필드 사용
    # 2순위: 이메일 HTML에서 <a> 태그 텍스트 매칭
    # 3순위: 이메일 plain text에서 URL 정규식 추출 후 직무명 주변 URL 사용

    # HTML 링크 맵 구성
    html_link_map = {}
    for email in business_emails:
        html = email.get("html_body", "")
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            text = " ".join(a.stripped_strings)
            href = a["href"]
            if href.startswith("http") and text:
                html_link_map[text.lower()] = href

    # plain text URL 목록
    plain_urls = []
    for email in business_emails:
        body = email.get("body", "")
        found = re.findall(r'https?://[^\s\)\]\>\"\']+', body)
        plain_urls.extend(found)

    result = []
    for posting in job_postings:
        title = posting.get("job_title", "").lower()

        # 1순위: OpenAI가 추출한 url
        url = posting.get("url") or None

        # 2순위: HTML 링크 텍스트 매칭
        if not url:
            for link_text, href in html_link_map.items():
                if title in link_text or link_text in title:
                    url = href
                    break

        # 3순위: plain text에서 직무명 단어와 가장 가까운 URL
        if not url and plain_urls:
            title_words = set(title.split())
            for pu in plain_urls:
                if any(w in pu.lower() for w in title_words if len(w) > 3):
                    url = pu
                    break
            if not url:
                # 직무 관련 키워드가 포함된 URL 선택
                job_keywords = ["job", "jobs", "career", "careers", "position", "recruit"]
                for pu in plain_urls:
                    if any(kw in pu.lower() for kw in job_keywords):
                        url = pu
                        break

        result.append({**posting, "url": url})
    return result


def send_to_slack(webhook_url: str, summaries: list) -> list[str]:
    """업무/비즈니스 메일 요약을 Slack Incoming Webhook으로 전송.
    성공한 subject 목록을 반환, 실패 시 예외 발생."""
    errors = []

    # 전체 헤더 메시지
    header = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"💼 업무/비즈니스 메일 요약  ({len(summaries)}건)",
                    "emoji": True,
                },
            }
        ]
    }
    resp = requests.post(webhook_url, json=header, timeout=10)
    resp.raise_for_status()

    # 이메일별 개별 메시지
    for s in summaries:
        subject = s.get("subject", "(제목 없음)")
        sender  = s.get("sender", "")
        date    = s.get("date", "")
        detail  = s.get("detail_summary", "")
        points  = s.get("key_points", [])
        action  = s.get("action_required")

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{subject}*\n📨 {sender}\n🗓 {date}",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": detail or "(요약 없음)"},
            },
        ]

        if points:
            bullet = "\n".join(f"• {p}" for p in points)
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*핵심 내용*\n{bullet}"},
            })

        if action:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"⚠️ *조치 필요:* {action}"},
            })

        try:
            r = requests.post(webhook_url, json={"blocks": blocks}, timeout=10)
            r.raise_for_status()
        except Exception as e:
            errors.append(f"{subject}: {e}")

    return errors


def scrape_job_page(url):
    """채용공고 페이지에서 굵은 글씨(항목명) 및 본문 섹션 추출"""
    import time
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "iframe"]):
            tag.decompose()

        sections = []
        seen = set()
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "strong", "b"]):
            text = tag.get_text(strip=True)
            if not text or len(text) < 2 or len(text) > 150:
                continue
            if text in seen:
                continue
            seen.add(text)

            sibling_text = ""
            for sib in tag.find_next_siblings():
                if sib.name in ["h1", "h2", "h3", "h4", "strong", "b"]:
                    break
                t = sib.get_text(separator=" ", strip=True)
                if t:
                    sibling_text = t[:300]
                    break

            sections.append({"heading": text, "content": sibling_text})

        return sections[:25]

    except Exception as e:
        return [{"heading": "스크래핑 실패", "content": str(e)}]


def display_job_page_details(postings_with_urls, batch_size=10, delay=30):
    """채용공고 페이지 스크래핑 — 10개마다 30초 대기"""
    import time

    print("\n" + "=" * 60)
    print("🔍 채용공고 상세 정보 (공고 페이지)")
    print("=" * 60)

    total = len(postings_with_urls)
    for i, posting in enumerate(postings_with_urls, 1):
        title    = posting.get("job_title", "")
        company  = posting.get("company", "")
        location = posting.get("location", "")
        url      = posting.get("url")

        print(f"\n[{i}/{total}] {title} — {company} / {location}")

        if not url:
            print("  링크: 찾을 수 없음")
            print("  " + "-" * 56)
        else:
            print(f"  링크: {url}")
            print("  페이지 로딩 중...")
            sections = scrape_job_page(url)

            if not sections:
                print("  내용을 가져올 수 없습니다.")
            else:
                for sec in sections:
                    print(f"\n  ■ {sec['heading']}")
                    if sec["content"]:
                        for line in sec["content"].split("\n"):
                            line = line.strip()
                            if line:
                                print(f"    {line[:100]}")
            print("\n  " + "-" * 56)

        # 배치 단위로 대기 (마지막 항목 제외)
        if i % batch_size == 0 and i < total:
            print(f"\n  ⏳ {batch_size}개 완료 — {delay}초 대기 후 계속합니다...")
            time.sleep(delay)

    print("=" * 60)


def print_job_postings_table(job_data):
    """채용공고 표 출력"""
    postings = job_data.get("job_postings", [])
    if not postings:
        print("\n  채용공고 메일이 없습니다.")
        return

    def cell_width(values, header, max_w):
        return min(max_w, max(len(header), max(len(str(v) if v else "미상") for v in values)))

    w_title    = cell_width([p.get("job_title", "") for p in postings],   "직무",   35)
    w_company  = cell_width([p.get("company", "") for p in postings],     "회사",   25)
    w_location = cell_width([p.get("location", "") for p in postings],    "지역",   25)

    def sep(char="-"):
        return f"+{char*(w_title+2)}+{char*(w_company+2)}+{char*(w_location+2)}+"

    def row(title, company, location):
        def fit(s, w):
            s = str(s) if s else "미상"
            return s[:w].ljust(w)
        return f"| {fit(title, w_title)} | {fit(company, w_company)} | {fit(location, w_location)} |"

    print(sep("="))
    print(row("직무", "회사", "지역"))
    print(sep("="))
    for p in postings:
        print(row(p.get("job_title", ""), p.get("company", ""), p.get("location", "")))
        print(sep())

    print(f"\n총 {len(postings)}개 채용공고")


def print_report(emails, classifications):
    """분류 결과 리포트 출력"""
    category_groups = defaultdict(list)

    for clf in classifications:
        idx = clf["index"] - 1
        if 0 <= idx < len(emails):
            email = emails[idx]
            category_groups[clf["category"]].append({
                "subject": email["subject"],
                "sender": email["sender"],
                "summary": clf["summary"],
                "date": email["date"],
                "body": email["body"],
            })

    print("\n" + "=" * 60)
    print("📧 Gmail 이메일 분류 결과")
    print("=" * 60)
    print(f"총 분류된 이메일 수: {len(classifications)}개\n")

    for category in CATEGORIES:
        items = category_groups.get(category, [])
        if not items:
            continue

        print(f"┌─ {category} ({len(items)}개)")
        for item in items:
            print(f"│  • {item['summary']}")
            print(f"│    발신: {item['sender'][:50]}")
        print("│")

    print("=" * 60)

    # 카테고리별 통계 요약
    print("\n📊 카테고리별 통계")
    print("-" * 30)
    for category in CATEGORIES:
        count = len(category_groups.get(category, []))
        if count > 0:
            bar = "█" * count
            print(f"{category:<15} {count:>3}개  {bar}")
    print("-" * 30)

    # 업무/비즈니스 메일 상세 요약
    business_items = category_groups.get("업무/비즈니스", [])
    if business_items:
        summaries = summarize_business_emails(business_items)

        print("\n" + "=" * 60)
        print("💼 업무/비즈니스 메일 상세 요약")
        print("=" * 60)

        for s in summaries:
            print(f"\n  제목: {s.get('subject', '')}")
            print(f"  발신: {s.get('sender', '')[:60]}")
            print(f"  날짜: {s.get('date', '')}")
            print(f"  요약: {s.get('detail_summary', '')}")
            key_points = s.get("key_points", [])
            if key_points:
                print("  핵심:")
                for point in key_points:
                    print(f"    - {point}")
            action = s.get("action_required")
            if action:
                print(f"  조치 필요: {action}")
            print("  " + "-" * 56)

        print("=" * 60)

    # 채용공고 표 + 상세 정보
    if business_items:
        job_data = extract_job_postings(business_items)
        postings = job_data.get("job_postings", [])
        if postings:
            print("\n" + "=" * 60)
            print("📋 채용공고 정리")
            print("=" * 60)
            print_job_postings_table(job_data)
            print("=" * 60)

            # 채용공고별 링크 추출
            postings_with_urls = extract_job_links(business_items, postings)

            # 공고 페이지 접속 후 항목별 내용 출력
            display_job_page_details(postings_with_urls)


def main():
    max_results = 30  # 가져올 이메일 수 (조정 가능)

    service = get_gmail_service()
    emails = fetch_emails(service, max_results=max_results)

    if not emails:
        print("이메일이 없습니다.")
        return

    classifications = classify_emails_with_claude(emails)
    print_report(emails, classifications)


if __name__ == "__main__":
    main()
