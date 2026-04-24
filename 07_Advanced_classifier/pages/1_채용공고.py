"""
채용공고 페이지 — 게시판 형태, 제목 클릭 시 스크래핑 내용 펼침
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
import streamlit as st

from retrieval import scrape_job_page

st.set_page_config(
    page_title="채용공고",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 사이드바 ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.page_link("streamlit_app.py", label="← 메인으로 돌아가기", icon="📧")
    if st.session_state.get("scraped_results"):
        st.divider()
        if st.button("🔄 다시 스크래핑", use_container_width=True):
            st.session_state.pop("scraped_results", None)
            st.rerun()

# ── 데이터 확인 ──────────────────────────────────────────────────────────────
if "postings_with_urls" not in st.session_state:
    st.title("📋 채용공고")
    st.warning("메인 페이지에서 먼저 이메일 분석을 실행해주세요.")
    st.page_link("streamlit_app.py", label="메인 페이지로 이동", icon="📧")
    st.stop()

postings = st.session_state["postings_with_urls"]

# ── 자동 스크래핑 ────────────────────────────────────────────────────────────
if "scraped_results" not in st.session_state:
    st.title("📋 채용공고")
    with_link = sum(1 for p in postings if p.get("url"))
    st.info(f"공고 페이지 내용을 수집하는 중입니다. (링크 있는 공고: {with_link} / {len(postings)}개)")

    progress_bar = st.progress(0, text="수집 시작...")
    status_box = st.empty()
    results = []

    for i, posting in enumerate(postings):
        p_title   = posting.get("job_title", "")
        p_company = posting.get("company", "")
        url       = posting.get("url")

        status_box.markdown(
            f"**[{i+1}/{len(postings)}]** {p_title} — {p_company}  "
            f"{'🔗 페이지 로딩 중...' if url else '⚠️ 링크 없음'}"
        )

        sections = [s.model_dump() for s in scrape_job_page(url)] if url else []
        results.append({**posting, "sections": sections})
        progress_bar.progress((i + 1) / len(postings), text=f"{i+1} / {len(postings)} 완료")

        if (i + 1) % 10 == 0 and (i + 1) < len(postings):
            for remaining in range(30, 0, -1):
                status_box.markdown(f"⏳ **10개 완료 — {remaining}초 후 재개합니다...**")
                time.sleep(1)

    st.session_state["scraped_results"] = results
    progress_bar.empty()
    status_box.empty()
    st.rerun()

# ── 결과 표시 ────────────────────────────────────────────────────────────────
results = st.session_state["scraped_results"]
total = len(results)
with_content = sum(
    1 for r in results
    if r.get("sections") and not (
        len(r["sections"]) == 1 and r["sections"][0].get("heading") == "스크래핑 실패"
    )
)

st.title("📋 채용공고")
st.caption(f"총 {total}개 공고 · 수집 완료 {with_content}개 · 실패/링크없음 {total - with_content}개")
st.divider()

# ── 게시판 헤더 행 ────────────────────────────────────────────────────────────
col_no, col_title, col_company, col_loc, col_status = st.columns([1, 4, 3, 2, 1])
col_no.markdown("**번호**")
col_title.markdown("**직무**")
col_company.markdown("**회사**")
col_loc.markdown("**지역**")
col_status.markdown("**상태**")
st.markdown("<hr style='margin:4px 0 12px 0;border-color:#ddd'>", unsafe_allow_html=True)

# ── 게시판 목록 + 펼침 ────────────────────────────────────────────────────────
for i, r in enumerate(results):
    title    = r.get("job_title", "(직무 미상)")
    company  = r.get("company", "")
    location = r.get("location") or "미상"
    url      = r.get("url")
    sections = r.get("sections", [])

    is_failed = (
        not sections
        or (len(sections) == 1 and sections[0].get("heading") == "스크래핑 실패")
    )

    if not url:
        status_label = "🔗 없음"
    elif is_failed:
        status_label = "⚠️ 실패"
    else:
        status_label = "✅"

    with st.expander(f"{i+1}.  {title}  |  {company}  |  {location}  {status_label}", expanded=False):
        if not url:
            st.warning("공고 링크를 찾을 수 없어 내용을 가져오지 못했습니다.")
        elif is_failed:
            err = sections[0].get("content", "") if sections else ""
            st.error(f"페이지 접근 실패: {err or '알 수 없는 오류'}")
        else:
            for sec in sections:
                heading = sec.get("heading", "")
                content = sec.get("content", "").strip()
                st.markdown(
                    f"""
                    <div style="
                        border-left: 4px solid #4a90d9;
                        background: #f4f7fb;
                        padding: 10px 16px;
                        margin-bottom: 10px;
                        border-radius: 0 6px 6px 0;
                    ">
                      <div style="font-weight:700;font-size:0.95rem;color:#1a1a2e;margin-bottom:5px">{heading}</div>
                      <div style="font-size:0.88rem;color:#444;white-space:pre-wrap;line-height:1.7">{content}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )