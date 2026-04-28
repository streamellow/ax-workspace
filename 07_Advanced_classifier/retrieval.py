"""
Retrieval — 요약 생성 · Slack 전송 · 채용공고 페이지 스크래핑
분류된 이메일에서 의미 있는 정보를 꺼내 외부로 전달하는 레이어
"""

import os
import json
import time
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from openai import OpenAI

from schemas import Email, BusinessSummary, JobPostingResult, Section, ResumeAnalysis
from indexing import _parse_json_text

PLAYWRIGHT_AUTH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "playwright_auth.json")


def _get_browser_cookies(url: str):
    """Chrome → Firefox 순으로 브라우저 쿠키를 읽어 반환. 실패 시 None."""
    try:
        import browser_cookie3
        domain = urlparse(url).netloc
        for loader in (browser_cookie3.chrome, browser_cookie3.firefox):
            try:
                jar = loader(domain_name=domain)
                if jar:
                    return jar
            except Exception:
                continue
    except ImportError:
        pass
    return None


def playwright_login(login_url: str = "https://www.linkedin.com/login") -> tuple[bool, str]:
    """Playwright로 브라우저를 열고 사용자가 로그인 완료 후 세션을 저장한다.
    (성공 여부, 오류 메시지) 튜플 반환. 별도 스레드에서 실행해 asyncio 충돌 방지."""
    import threading

    result = {"ok": False, "error": ""}

    def _run():
        import asyncio

        async def _async_login():
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False, slow_mo=200, channel="chrome")
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto(login_url)
                # 로그인 완료 감지: /login·/checkpoint 를 벗어날 때까지 대기 (최대 3분)
                await page.wait_for_function(
                    "() => !window.location.href.includes('/login') "
                    "     && !window.location.href.includes('/checkpoint')",
                    timeout=180_000,
                )
                await context.storage_state(path=PLAYWRIGHT_AUTH)
                await browser.close()

        try:
            loop = asyncio.ProactorEventLoop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_async_login())
            finally:
                loop.close()
            result["ok"] = True
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {e}"

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=200)
    return result["ok"], result["error"]


def _is_saramin_url(url: str) -> bool:
    return "saramin.co.kr" in urlparse(url).netloc


def _parse_saramin_sections(html: str) -> list[Section]:
    """사람인 채용공고 페이지 전용 파서.
    상세 공고 내용 / 채용 일정 / 회사 소개 세 섹션을 우선 추출."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "iframe"]):
        tag.decompose()

    sections: list[Section] = []

    # ── 1. 채용 기본 정보 (직무, 경력, 학력, 근무지 등) ─────────────────────
    summary_selectors = [".jv_summary", ".summary_info", ".wrap_jv_summary"]
    for sel in summary_selectors:
        el = soup.select_one(sel)
        if el:
            rows = []
            for dt, dd in zip(el.find_all(["dt", "th"]), el.find_all(["dd", "td"])):
                label = dt.get_text(strip=True)
                value = dd.get_text(separator=" ", strip=True)
                if label and value:
                    rows.append(f"{label}: {value}")
            if rows:
                sections.append(Section(heading="채용 기본 정보", content="\n".join(rows)[:600]))
                break

    # ── 2. 상세 공고 내용 ──────────────────────────────────────────────────
    detail_selectors = [
        ".wrap_jv_cont", "#job_content", ".jv_cont",
        ".content_box", ".recruit_detail",
    ]
    for sel in detail_selectors:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(separator="\n", strip=True)
            if len(text) > 50:
                sections.append(Section(heading="상세 공고 내용", content=text[:1500]))
                break

    # ── 3. 채용 일정 / 마감일 ──────────────────────────────────────────────
    deadline_selectors = [
        ".deadline_box", ".info_period", ".jv_date",
        ".recruit_period", ".apply_period",
    ]
    for sel in deadline_selectors:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(separator=" ", strip=True)
            if text:
                sections.append(Section(heading="채용 일정", content=text[:400]))
                break

    # 마감일 정보가 없으면 텍스트에서 날짜 패턴으로 추출
    if not any(s.heading == "채용 일정" for s in sections):
        import re
        date_pattern = re.compile(r"\d{4}[.\-/]\d{2}[.\-/]\d{2}")
        for tag in soup.find_all(string=date_pattern):
            parent_text = tag.parent.get_text(separator=" ", strip=True)
            if any(kw in parent_text for kw in ["마감", "접수", "일정", "기간"]):
                sections.append(Section(heading="채용 일정", content=parent_text[:300]))
                break

    # ── 4. 회사 소개 ───────────────────────────────────────────────────────
    company_selectors = [
        ".wrap_company_info", ".company_intro", "#company",
        ".jv_company", ".company_profile",
    ]
    for sel in company_selectors:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(separator="\n", strip=True)
            if len(text) > 30:
                sections.append(Section(heading="회사 소개", content=text[:800]))
                break

    # 위 셀렉터로 아무것도 못 찾으면 generic fallback
    return sections if sections else _parse_html_to_sections(html)


def _parse_html_to_sections(html: str) -> list[Section]:
    """BeautifulSoup으로 HTML을 파싱해 Section 목록으로 변환."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "iframe"]):
        tag.decompose()

    sections, seen = [], set()
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "strong", "b"]):
        text = tag.get_text(strip=True)
        if not text or len(text) < 2 or len(text) > 150 or text in seen:
            continue
        seen.add(text)
        content = ""
        for sib in tag.find_next_siblings():
            if sib.name in ["h1", "h2", "h3", "h4", "strong", "b"]:
                break
            t = sib.get_text(separator=" ", strip=True)
            if t:
                content = t[:300]
                break
        sections.append(Section(heading=text, content=content))

    return sections[:25]


def _scrape_with_playwright(url: str) -> list[Section]:
    """저장된 인증 세션으로 Playwright headless 스크래핑."""
    import asyncio

    async def _async_scrape() -> str:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx_kwargs = {}
            if os.path.exists(PLAYWRIGHT_AUTH):
                ctx_kwargs["storage_state"] = PLAYWRIGHT_AUTH
            context = await browser.new_context(**ctx_kwargs)
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                # 사람인은 JS 렌더링이 느리므로 대기 시간 연장
                wait_ms = 5_000 if _is_saramin_url(url) else 3_000
                await page.wait_for_timeout(wait_ms)
                return await page.content()
            finally:
                await browser.close()

    loop = asyncio.ProactorEventLoop()
    asyncio.set_event_loop(loop)
    try:
        html = loop.run_until_complete(_async_scrape())
    finally:
        loop.close()

    parse_fn = _parse_saramin_sections if _is_saramin_url(url) else _parse_html_to_sections
    sections = parse_fn(html)
    return sections or [Section(heading="스크래핑 실패", content="내용을 가져올 수 없습니다.")]


def summarize_business_emails(emails: list[Email]) -> list[BusinessSummary]:
    items = ""
    for i, e in enumerate(emails):
        items += f"\n[{i+1}]\n발신자: {e.sender}\n제목: {e.subject}\n날짜: {e.date}\n본문: {e.body}\n---"

    prompt = f"""다음 업무/비즈니스 이메일들을 각각 상세 요약해주세요.

이메일 목록:
{items}

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

    response = OpenAI().chat.completions.create(
        model="gpt-4o-mini", max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    text = _parse_json_text(response.choices[0].message.content)
    return [BusinessSummary(**s) for s in json.loads(text)]


def send_to_slack(webhook_url: str, summaries: list[BusinessSummary]) -> list[str]:
    """Block Kit 메시지로 Slack 전송. 실패한 건의 오류 메시지 목록 반환."""
    errors: list[str] = []

    header = {"blocks": [{"type": "header", "text": {
        "type": "plain_text",
        "text": f"💼 업무/비즈니스 메일 요약  ({len(summaries)}건)",
        "emoji": True,
    }}]}
    requests.post(webhook_url, json=header, timeout=10).raise_for_status()

    for s in summaries:
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn",
                "text": f"*{s.subject}*\n📨 {s.sender}\n🗓 {s.date}"}},
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn",
                "text": s.detail_summary or "(요약 없음)"}},
        ]
        if s.key_points:
            bullet = "\n".join(f"• {p}" for p in s.key_points)
            blocks.append({"type": "section", "text": {"type": "mrkdwn",
                "text": f"*핵심 내용*\n{bullet}"}})
        if s.action_required:
            blocks.append({"type": "section", "text": {"type": "mrkdwn",
                "text": f"⚠️ *조치 필요:* {s.action_required}"}})
        try:
            requests.post(webhook_url, json={"blocks": blocks}, timeout=10).raise_for_status()
        except Exception as e:
            errors.append(f"{s.subject}: {e}")

    return errors


def analyze_resume(pdf_text: str) -> ResumeAnalysis:
    prompt = f"""다음은 구직자의 이력서 텍스트입니다. 분석하여 JSON 형식으로만 응답하세요 (다른 텍스트 없이):

이력서:
{pdf_text[:6000]}

{{
  "name": "이름 (없으면 '미상')",
  "suitable_jobs": ["적합 직무 1", "적합 직무 2", "적합 직무 3"],
  "skills": ["기술 스택/툴 1", "기술 2", ...],
  "characteristics": ["특징 1", "특징 2", ...],
  "career_summary": "경력 및 배경 요약 (3~5문장)",
  "strengths": ["강점 1", "강점 2", ...],
  "job_keywords": ["키워드 1", "키워드 2", ...]
}}"""

    response = OpenAI().chat.completions.create(
        model="gpt-4o-mini", max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    text = _parse_json_text(response.choices[0].message.content)
    return ResumeAnalysis(**json.loads(text))


def scrape_job_page(url: str) -> list[Section]:
    """채용공고 페이지에서 섹션(제목+내용) 최대 25개 추출.
    Playwright 인증 세션이 있으면 우선 사용, 없으면 requests fallback."""
    # Playwright 세션이 있으면 우선 사용 (JS 렌더링 + 로그인 상태)
    if os.path.exists(PLAYWRIGHT_AUTH):
        try:
            return _scrape_with_playwright(url)
        except Exception:
            pass  # requests fallback

    # 사람인은 Playwright 없어도 requests로 기본 내용 접근 가능
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
        parse_fn = _parse_saramin_sections if _is_saramin_url(url) else _parse_html_to_sections
        sections = parse_fn(resp.text)
        return sections or [Section(heading="스크래핑 실패", content="내용을 가져올 수 없습니다.")]
    except Exception as e:
        return [Section(heading="스크래핑 실패", content=str(e))]


def scrape_all_postings(
    postings,
    batch_size: int = 10,
    delay: int = 30,
) -> list[JobPostingResult]:
    """채용공고 목록을 순회하며 페이지 스크래핑. 10개마다 대기."""
    results = []
    for i, p in enumerate(postings):
        sections = scrape_job_page(p.url) if p.url else []
        results.append(JobPostingResult(
            **p.model_dump(),
            sections=[s.model_dump() for s in sections],
        ))
        if (i + 1) % batch_size == 0 and (i + 1) < len(postings):
            time.sleep(delay)
    return results