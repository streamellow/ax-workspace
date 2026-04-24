"""
Retrieval — 요약 생성 · Slack 전송 · 채용공고 페이지 스크래핑
분류된 이메일에서 의미 있는 정보를 꺼내 외부로 전달하는 레이어
"""

import json
import time
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

from schemas import Email, BusinessSummary, JobPostingResult, Section, ResumeAnalysis
from indexing import _parse_json_text


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
    """채용공고 페이지에서 섹션(제목+내용) 최대 25개 추출."""
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