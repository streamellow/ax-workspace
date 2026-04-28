"""
search_tools.py — RAG(ChromaDB) 검색 및 Tavily 웹 검색 툴
"""

import os


def rag_search(query: str, collection: str) -> dict:
    if collection == "job_postings":
        from core.vector_store import search_jobs_by_text
        results = search_jobs_by_text(query, n_results=10)
    elif collection == "resumes":
        from core.vector_store import search_resumes_by_text
        results = search_resumes_by_text(query, n_results=5)
    else:
        return {"error": f"Unknown collection: {collection}"}

    return {
        "query": query,
        "collection": collection,
        "count": len(results),
        "results": results,
    }


def web_search(query: str) -> dict:
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        return {"error": "TAVILY_API_KEY가 설정되지 않았습니다."}
    try:
        import requests
        resp = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": api_key, "query": query, "max_results": 5},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "query": query,
            "results": [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", "")[:500],
                    "score": r.get("score", 0),
                }
                for r in data.get("results", [])
            ],
        }
    except Exception as e:
        return {"error": str(e)}
