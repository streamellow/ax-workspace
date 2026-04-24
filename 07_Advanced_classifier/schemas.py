"""
Data models — 전체 파이프라인에서 공유하는 Pydantic 스키마
"""

from typing import Optional
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