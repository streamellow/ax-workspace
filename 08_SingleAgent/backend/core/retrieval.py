"""
Retrieval — 요약 생성 · 채용공고 페이지 스크래핑 · 이력서 분석
"""

import os
import json
import time
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from openai import OpenAI

from core.schemas import Email, BusinessSummary, JobPostingResult, Section, ResumeAnalysis
from core.indexing import _parse_json_text

PLAYWRIGHT_AUTH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "playwright_auth.json")


def _is_saramin_url(url: str) -> bool:
    return "saramin.co.kr" in urlparse(url).netloc


def _parse_saramin_sections(html: str) -> list[Section]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "iframe"]):
        tag.decompose()

    sections: list[Section] = []

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

    if not any(s.heading == "채용 일정" for s in sections):
        import re
        date_pattern = re.compile(r"\d{4}[.\-/]\d{2}[.\-/]\d{2}")
        for tag in soup.find_all(string=date_pattern):
            parent_text = tag.parent.get_text(separator=" ", strip=True)
            if any(kw in parent_text for kw in ["마감", "접수", "일정", "기간"]):
                sections.append(Section(heading="채용 일정", content=parent_text[:300]))
                break

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

    return sections if sections else _parse_html_to_sections(html)


def _parse_html_to_sections(html: str) -> list[Section]:
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
    import asyncio
    import concurrent.futures

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
                wait_ms = 5_000 if _is_saramin_url(url) else 3_000
                await page.wait_for_timeout(wait_ms)
                return await page.content()
            finally:
                await browser.close()

    def _run_in_thread() -> str:
        return asyncio.run(_async_scrape())

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        html = executor.submit(_run_in_thread).result(timeout=30)

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
    if os.path.exists(PLAYWRIGHT_AUTH):
        try:
            return _scrape_with_playwright(url)
        except Exception:
            pass

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
