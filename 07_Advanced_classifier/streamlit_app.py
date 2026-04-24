"""
Gmail 이메일 분류기 — Streamlit UI
메인 페이지: 분류 통계 + 업무/비즈니스 상세 요약
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from schemas import CATEGORIES
from auth import get_gmail_service
from indexing import fetch_emails, classify_emails, extract_job_postings, resolve_job_urls
from retrieval import summarize_business_emails

st.set_page_config(
    page_title="Gmail 분류기",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 사이드바 ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 설정")
    max_results = st.slider("가져올 이메일 수", min_value=10, max_value=100, value=30, step=5)
    run_btn = st.button("🔄 이메일 분석 시작", type="primary", use_container_width=True)

    if st.session_state.get("postings_with_urls"):
        count = len(st.session_state["postings_with_urls"])
        st.divider()
        st.success(f"📋 채용공고 {count}개 추출 완료")
        st.page_link("pages/1_채용공고.py", label="채용공고 보러 가기 →", icon="📋")

    st.divider()
    st.page_link("pages/2_이력서분석.py", label="이력서 / 포트폴리오 분석 →", icon="📄")

# ── 분석 실행 ────────────────────────────────────────────────────────────────
if run_btn:
    for key in ("category_groups", "business_summaries", "postings_with_urls",
                "scraped_results", "total_count"):
        st.session_state.pop(key, None)

    try:
        with st.spinner("Gmail 연결 중..."):
            service = get_gmail_service()

        progress = st.progress(0, text="이메일 가져오는 중...")
        emails = fetch_emails(service, max_results=max_results)
        progress.progress(25, text="이메일 분류 중...")

        classifications = classify_emails(emails)
        progress.progress(55, text="업무 메일 요약 중...")

        category_groups = defaultdict(list)
        business_emails = []

        for c in classifications:
            idx = c.index - 1
            if 0 <= idx < len(emails):
                email = emails[idx]
                category_groups[c.category].append({
                    "subject": email.subject,
                    "sender": email.sender,
                    "summary": c.summary,
                    "date": email.date,
                })
                if c.category == "업무/비즈니스":
                    business_emails.append(email)

        business_summaries = []
        if business_emails:
            business_summaries = [
                s.model_dump() for s in summarize_business_emails(business_emails)
            ]

        progress.progress(80, text="채용공고 추출 중...")

        postings_with_urls = []
        if business_emails:
            postings = extract_job_postings(business_emails)
            postings_with_urls = [
                p.model_dump() for p in resolve_job_urls(business_emails, postings)
            ]

        progress.progress(100, text="완료!")

        st.session_state["category_groups"] = dict(category_groups)
        st.session_state["business_summaries"] = business_summaries
        st.session_state["postings_with_urls"] = postings_with_urls
        st.session_state["total_count"] = len(classifications)

        progress.empty()
        st.rerun()

    except FileNotFoundError as e:
        st.error(str(e))
    except Exception as e:
        st.error(f"오류 발생: {e}")

# ── 결과 없으면 안내 화면 ────────────────────────────────────────────────────
if "category_groups" not in st.session_state:
    st.title("📧 Gmail 이메일 분류기")
    st.info("사이드바에서 이메일 수를 설정하고 **이메일 분석 시작** 버튼을 누르세요.")
    st.stop()

category_groups    = st.session_state["category_groups"]
total_count        = st.session_state["total_count"]
business_summaries = st.session_state.get("business_summaries", [])

st.title("📧 Gmail 이메일 분류 결과")
st.caption(f"총 {total_count}개 이메일 분석 완료")

# ── 통계 카드 + 바 차트 ───────────────────────────────────────────────────────
st.subheader("📊 카테고리별 통계")
stats       = {cat: len(category_groups.get(cat, [])) for cat in CATEGORIES}
active_cats = {k: v for k, v in stats.items() if v > 0}

if active_cats:
    for col, (cat, cnt) in zip(st.columns(len(active_cats)), active_cats.items()):
        col.metric(cat, f"{cnt}개")
    st.divider()
    st.bar_chart(pd.DataFrame({"개수": list(active_cats.values())}, index=list(active_cats.keys())))

st.divider()

# ── 카테고리별 이메일 목록 ────────────────────────────────────────────────────
st.subheader("📂 카테고리별 이메일")
left_col, right_col = st.columns(2)
col_map = {i: (left_col if i % 2 == 0 else right_col) for i in range(len(CATEGORIES))}
col_idx = 0
for cat in CATEGORIES:
    items = category_groups.get(cat, [])
    if not items:
        continue
    with col_map[col_idx]:
        with st.expander(f"**{cat}** — {len(items)}개", expanded=(cat == "업무/비즈니스")):
            for item in items:
                st.markdown(f"**{item['subject'][:60]}**")
                st.caption(f"📨 {item['sender'][:55]}  ·  {item['date'][:25]}")
                st.text(item["summary"])
                st.divider()
    col_idx += 1

# ── 업무/비즈니스 상세 요약 ───────────────────────────────────────────────────
if not business_summaries:
    st.stop()

st.divider()
st.subheader("💼 업무/비즈니스 메일 상세 요약")

for s in business_summaries:
    with st.expander(f"📩  {s.get('subject', '(제목 없음)')}", expanded=True):
        meta_col, detail_col = st.columns([3, 2])

        with meta_col:
            st.markdown(f"**발신:** {s.get('sender', '')}")
            st.markdown(f"**날짜:** {s.get('date', '')}")
            st.markdown("---")
            st.markdown(s.get("detail_summary", ""))

        with detail_col:
            key_points = s.get("key_points", [])
            if key_points:
                st.markdown("**핵심 내용**")
                for pt in key_points:
                    st.markdown(f"- {pt}")
            action = s.get("action_required")
            if action:
                st.warning(f"**조치 필요:** {action}")