"""
resume_tools.py — 이력서 분석 및 채용공고 검색 툴
"""


def analyze_resume(resume_text: str, resume_id: str) -> dict:
    from core.retrieval import analyze_resume as _analyze
    from core.vector_store import store_resume as vstore
    from core.keyword_store import store_resume as kstore

    analysis = _analyze(resume_text)
    resume_dict = analysis.model_dump()

    vstore(resume_id, resume_dict)
    kstore(resume_id, resume_dict, filename=resume_id, full_text=resume_text)

    return {
        "resume_id": resume_id,
        "analysis": resume_dict,
    }


def search_jobs(query: str, top_k: int = 10) -> dict:
    from core.vector_store import search_jobs_by_text
    from core.keyword_store import search_jobs_by_keywords

    vector_hits = search_jobs_by_text(query, n_results=top_k)
    keywords = query.split()
    keyword_hits = search_jobs_by_keywords(keywords, limit=top_k)

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

    results = sorted(merged.values(), key=lambda x: x["final_score"], reverse=True)[:top_k]

    return {
        "query": query,
        "count": len(results),
        "results": results,
    }
