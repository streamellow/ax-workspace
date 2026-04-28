"""
Search — 하이브리드 검색 (벡터 60% + 키워드 40%) 및 역방향 검색
"""

from schemas import ResumeAnalysis
from vector_store import search_jobs_by_text, search_resumes_by_text
from keyword_store import search_jobs_by_keywords


def hybrid_search_jobs(resume: ResumeAnalysis, n_results: int = 10) -> list[dict]:
    """이력서 기반 매칭 채용공고 검색 (벡터 + 키워드 하이브리드)"""
    query = " ".join([
        resume.career_summary,
        " ".join(resume.skills),
        " ".join(resume.suitable_jobs),
        " ".join(resume.job_keywords),
    ])
    keywords = resume.skills + resume.job_keywords + resume.suitable_jobs

    vector_hits  = search_jobs_by_text(query, n_results=n_results)
    keyword_hits = search_jobs_by_keywords(keywords, limit=n_results)

    merged: dict[str, dict] = {}

    for r in vector_hits:
        key = f"{r['company']}_{r['job_title']}"
        merged[key] = {**r, "vector_score": r["score"], "keyword_score": 0.0}

    max_kw = max((r["score"] for r in keyword_hits), default=1) or 1
    for r in keyword_hits:
        key = f"{r['company']}_{r['job_title']}"
        norm = r["score"] / max_kw
        if key in merged:
            merged[key]["keyword_score"] = norm
        else:
            merged[key] = {**r, "vector_score": 0.0, "keyword_score": norm}

    for item in merged.values():
        item["final_score"] = item["vector_score"] * 0.6 + item["keyword_score"] * 0.4

    return sorted(merged.values(), key=lambda x: x["final_score"], reverse=True)[:n_results]


def reverse_search_resumes(job_title: str, company: str, n_results: int = 5) -> list[dict]:
    """채용공고 기반 매칭 이력서 역방향 검색"""
    return search_resumes_by_text(f"{job_title} {company}", n_results=n_results)
