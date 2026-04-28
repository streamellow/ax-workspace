"""
VectorStore — ChromaDB 기반 벡터 저장/검색
"""

import os
import chromadb
from chromadb.utils import embedding_functions

CHROMA_PATH = os.environ.get(
    "CHROMA_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "chroma_db"),
)


def _client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=CHROMA_PATH)


def _ef():
    return embedding_functions.OpenAIEmbeddingFunction(
        api_key=os.environ.get("OPENAI_API_KEY"),
        model_name="text-embedding-3-small",
    )


def _col(name: str):
    return _client().get_or_create_collection(
        name,
        embedding_function=_ef(),
        metadata={"hnsw:space": "cosine"},
    )


def store_job_postings(postings: list[dict]) -> int:
    try:
        col = _col("job_postings")
        docs, metas, ids = [], [], []
        for p in postings:
            sections_text = " ".join(
                f"{s['heading']} {s['content']}" for s in p.get("sections", [])
            )
            text = f"{p['job_title']} {p['company']} {p.get('location', '')} {sections_text}".strip()
            doc_id = f"{p['company']}_{p['job_title']}".replace(" ", "_")[:64]
            docs.append(text)
            metas.append({
                "job_title":    p["job_title"],
                "company":      p["company"],
                "location":     p.get("location") or "",
                "url":          p.get("url") or "",
                "source_email": p.get("source_email") or "",
            })
            ids.append(doc_id)
        if docs:
            col.upsert(documents=docs, metadatas=metas, ids=ids)
        return len(docs)
    except Exception:
        return 0


def search_jobs_by_text(query: str, n_results: int = 10) -> list[dict]:
    try:
        col = _col("job_postings")
        count = col.count()
        if count == 0:
            return []
        results = col.query(query_texts=[query], n_results=min(n_results, count))
        return [
            {**meta, "score": max(0.0, 1 - dist / 2), "source": "vector"}
            for meta, dist in zip(results["metadatas"][0], results["distances"][0])
        ]
    except Exception:
        return []


def store_resume(resume_id: str, resume: dict) -> None:
    col = _col("resumes")
    text = " ".join([
        resume.get("career_summary", ""),
        " ".join(resume.get("skills", [])),
        " ".join(resume.get("suitable_jobs", [])),
        " ".join(resume.get("job_keywords", [])),
    ]).strip()
    col.upsert(
        documents=[text],
        metadatas=[{
            "name":          resume.get("name", ""),
            "skills":        ", ".join(resume.get("skills", [])),
            "suitable_jobs": ", ".join(resume.get("suitable_jobs", [])),
        }],
        ids=[resume_id],
    )


def search_resumes_by_text(query: str, n_results: int = 5) -> list[dict]:
    try:
        col = _col("resumes")
        count = col.count()
        if count == 0:
            return []
        results = col.query(query_texts=[query], n_results=min(n_results, count))
        return [
            {**meta, "id": rid, "score": max(0.0, 1 - dist / 2)}
            for meta, dist, rid in zip(
                results["metadatas"][0],
                results["distances"][0],
                results["ids"][0],
            )
        ]
    except Exception:
        return []
