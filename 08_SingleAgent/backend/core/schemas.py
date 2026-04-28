"""
schemas.py — 전체 파이프라인 공유 Pydantic 스키마 + API 모델
"""

from typing import Optional, Any
from pydantic import BaseModel

CATEGORIES = [
    "업무/비즈니스",
    "뉴스레터/마케팅",
    "금융/결제",
    "소셜/알림",
    "개인",
    "스팸/광고",
    "기타",
]


# ── 이메일 도메인 모델 ───────────────────────────────────────────────────────
class Email(BaseModel):
    id: str
    subject: str
    sender: str
    date: str
    body: str
    html_body: str


class Classification(BaseModel):
    index: int
    category: str
    summary: str


class BusinessSummary(BaseModel):
    index: int
    subject: str
    sender: str
    date: str
    key_points: list[str]
    action_required: Optional[str] = None
    detail_summary: str


class JobPosting(BaseModel):
    job_title: str
    company: str
    location: Optional[str] = None
    source_email: str
    url: Optional[str] = None
    deadline: Optional[str] = None


class JobPostingResult(JobPosting):
    sections: list[dict] = []


class Section(BaseModel):
    heading: str
    content: str


class ResumeAnalysis(BaseModel):
    name: str
    suitable_jobs: list[str]
    skills: list[str]
    characteristics: list[str]
    career_summary: str
    strengths: list[str]
    job_keywords: list[str]


# ── API 모델 ─────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    context: dict = {}


class ChatResponse(BaseModel):
    reply: str
    complete: bool
    tool_calls_log: list[dict] = []
    data: dict = {}


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
