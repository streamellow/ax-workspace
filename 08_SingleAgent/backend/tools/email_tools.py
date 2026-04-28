"""
email_tools.py — 이메일 fetch/분류/요약/채용공고 추출 툴
"""

from datetime import datetime
from core.schemas import CATEGORIES


def fetch_and_classify_emails(
    max_results: int = 30,
    mail_source: str = "gmail",
    context: dict = {},
) -> dict:
    from core.google_auth import get_gmail_service, get_daum_imap
    from core.indexing import fetch_emails, fetch_emails_imap, classify_emails

    try:
        if mail_source == "daum":
            conn = get_daum_imap()
            emails = fetch_emails_imap(conn, max_results=max_results)
        else:
            service = get_gmail_service()
            emails = fetch_emails(service, max_results=max_results)
    except Exception as e:
        return {"error": str(e), "emails": [], "categories": {}}

    if not emails:
        return {"message": "이메일이 없습니다.", "emails": [], "categories": {}}

    classifications = classify_emails(emails)

    cat_map: dict[str, list[dict]] = {c: [] for c in CATEGORIES}
    for clf in classifications:
        idx = clf.index - 1
        if 0 <= idx < len(emails):
            e = emails[idx]
            cat_map.setdefault(clf.category, []).append({
                "index": idx,
                "subject": e.subject,
                "sender": e.sender,
                "date": e.date,
                "summary": clf.summary,
            })

    business_emails = [emails[c.index - 1] for c in classifications
                       if c.category == "업무/비즈니스" and 0 <= c.index - 1 < len(emails)]
    newsletter_emails = [emails[c.index - 1] for c in classifications
                         if c.category == "뉴스레터/마케팅" and 0 <= c.index - 1 < len(emails)]

    # store in context for subsequent tool calls
    context["_emails"] = emails
    context["_business_emails"] = business_emails
    context["_newsletter_emails"] = newsletter_emails
    context["_classifications"] = classifications

    return {
        "total": len(emails),
        "categories": {cat: len(items) for cat, items in cat_map.items() if items},
        "emails": [
            {
                "index": i,
                "subject": e.subject,
                "sender": e.sender,
                "date": e.date,
                "category": next(
                    (c.category for c in classifications if c.index == i + 1), "기타"
                ),
                "summary": next(
                    (c.summary for c in classifications if c.index == i + 1), ""
                ),
            }
            for i, e in enumerate(emails)
        ],
    }


def summarize_business_emails(
    email_indices: list[int] | None = None,
    context: dict = {},
) -> dict:
    from core.retrieval import summarize_business_emails as _summarize

    business_emails = context.get("_business_emails", [])
    if not business_emails:
        return {"error": "먼저 fetch_and_classify_emails를 실행해주세요.", "summaries": []}

    if email_indices is not None:
        target = [e for i, e in enumerate(business_emails) if i in email_indices]
    else:
        target = business_emails

    if not target:
        return {"message": "요약할 업무 이메일이 없습니다.", "summaries": []}

    summaries = _summarize(target)
    return {
        "count": len(summaries),
        "summaries": [s.model_dump() for s in summaries],
    }


def extract_and_store_job_postings(context: dict = {}) -> dict:
    business_emails = context.get("_business_emails", [])
    newsletter_emails = context.get("_newsletter_emails", [])
    target_emails = business_emails + newsletter_emails

    if not target_emails:
        return {"error": "먼저 fetch_and_classify_emails를 실행해주세요.", "stored": 0}

    try:
        from core.indexing import extract_job_postings, resolve_job_urls
        from core.retrieval import scrape_all_postings
        from core.vector_store import store_job_postings as vstore
        from core.keyword_store import store_job_postings as kstore

        postings = extract_job_postings(target_emails)
        if not postings:
            return {"message": "채용공고를 찾을 수 없습니다.", "stored": 0}

        postings = resolve_job_urls(target_emails, postings)
        results = scrape_all_postings(postings, batch_size=10, delay=5)

        posting_dicts = [r.model_dump() for r in results]
        try:
            v_count = vstore(posting_dicts)
        except Exception:
            v_count = 0
        try:
            k_count = kstore(posting_dicts)
        except Exception:
            k_count = len(posting_dicts)

        return {
            "extracted": len(postings),
            "stored": k_count,
            "job_postings": [
                {
                    "job_title": p.job_title,
                    "company": p.company,
                    "location": p.location,
                    "url": p.url,
                    "deadline": p.deadline,
                }
                for p in postings
            ],
        }
    except Exception as e:
        return {"error": f"채용공고 추출 중 오류가 발생했습니다: {str(e)}", "stored": 0}
