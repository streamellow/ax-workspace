"""
email_category.py — 이메일 분류 및 요약
탭1: 자동 수집 이력 (DB, 월별 통계 + 목록)
탭2: 수동 분류 (즉시 실행)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import streamlit as st
import pandas as pd
from collections import defaultdict
from dotenv import load_dotenv

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
load_dotenv(os.path.join(_ROOT, ".env"))

from schemas import CATEGORIES
from auth import get_gmail_service, get_daum_imap
from indexing import fetch_emails, fetch_emails_imap, classify_emails, extract_job_postings, resolve_job_urls
from retrieval import summarize_business_emails
from vector_store import store_job_postings as _vs_store_jobs
from keyword_store import store_job_postings as _ks_store_jobs, get_job_postings_by_month
import datetime
from email_store import (get_available_months, get_monthly_stats, get_monthly_emails,
                         get_session_history, store_session, get_last_period_end)

# ── 헤더 ─────────────────────────────────────────────────────────────────────
st.title("📧 Email Category")
st.caption("Gmail 또는 다음 메일을 AI로 자동 분류하고 업무 메일을 요약합니다.")
st.divider()

tab_history, tab_manual = st.tabs(["📊 자동 수집 이력", "🔄 수동 분류"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — 자동 수집 이력
# ══════════════════════════════════════════════════════════════════════════════
with tab_history:
    months = get_available_months()

    if not months:
        st.info(
            "아직 저장된 이메일 이력이 없습니다.\n\n"
            "**scheduler.py** 를 실행하면 6시간마다 메일을 자동 수집합니다.\n\n"
            "```\npython scheduler.py\n```"
        )
    else:
        # ── 월 선택 ──────────────────────────────────────────────────────────
        month_labels = [f"{y}년 {m:02d}월" for y, m in months]
        sel_idx = st.selectbox(
            "조회 월", options=range(len(months)), format_func=lambda i: month_labels[i]
        )
        sel_year, sel_month = months[sel_idx]

        # ── 카테고리 통계 ─────────────────────────────────────────────────────
        stats = get_monthly_stats(sel_year, sel_month)
        total = sum(stats.values())

        st.subheader(f"📊 {month_labels[sel_idx]} — 총 {total}개 이메일")

        if stats:
            metric_cols = st.columns(min(len(stats), 4))
            for col, (cat, cnt) in zip(metric_cols, stats.items()):
                col.metric(cat, f"{cnt}개")

            st.bar_chart(
                pd.DataFrame({"개수": list(stats.values())}, index=list(stats.keys()))
            )

        st.divider()

        # ── 카테고리 필터 + 이메일 목록 ──────────────────────────────────────
        cat_options = ["전체"] + [c for c in CATEGORIES if c in stats]
        sel_cat = st.radio("카테고리 필터", cat_options, horizontal=True)

        emails = get_monthly_emails(
            sel_year, sel_month,
            category=(None if sel_cat == "전체" else sel_cat),
        )

        if not emails:
            st.info("해당 카테고리의 이메일이 없습니다.")
        else:
            st.caption(f"{len(emails)}개 이메일")
            for em in emails:
                with st.expander(
                    f"**{(em.get('subject') or '(제목 없음)')[:60]}**  ·  {em.get('category', '')}",
                    expanded=False,
                ):
                    st.caption(
                        f"📨 {(em.get('sender') or '')[:55]}  ·  "
                        f"{(em.get('received_at') or '')[:25]}  ·  "
                        f"소스: {em.get('source', '').upper()}"
                    )
                    st.markdown(em.get("ai_summary") or "")

        st.divider()

        # ── 채용공고 테이블 ───────────────────────────────────────────────────
        job_postings = get_job_postings_by_month(sel_year, sel_month)
        with st.expander(f"📋 채용공고 — {len(job_postings)}개", expanded=bool(job_postings)):
            if not job_postings:
                st.info("이 월에 수집된 채용공고가 없습니다.")
            else:
                rows = []
                for jp in job_postings:
                    rows.append({
                        "회사명":    jp.get("company", ""),
                        "마감일":    jp.get("deadline") or "",
                        "공고 내용": jp.get("job_title", ""),
                        "링크":      jp.get("url") or "",
                    })
                df = pd.DataFrame(rows)
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "링크": st.column_config.LinkColumn(
                            "링크", display_text="🔗 보기"
                        ),
                    },
                )

        st.divider()

        # ── 수집 실행 이력 ────────────────────────────────────────────────────
        with st.expander("🕒 수집 실행 이력", expanded=False):
            history = get_session_history(20)
            if not history:
                st.info("이력 없음")
            else:
                rows = [
                    {
                        "실행시각":   h["fetched_at"][:19],
                        "소스":      h["source"].upper(),
                        "수집구간":  f"{h['period_start'][11:16]} ~ {h['period_end'][11:16]}",
                        "날짜":      h["period_start"][:10],
                        "수집건수":  h["total_count"],
                    }
                    for h in history
                ]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — 수동 분류
# ══════════════════════════════════════════════════════════════════════════════
with tab_manual:
    ctrl1, ctrl2 = st.columns([2, 1])
    with ctrl1:
        mail_source = st.radio(
            "메일 계정 선택",
            options=["Gmail", "다음(Daum) 메일"],
            horizontal=True,
        )
    with ctrl2:
        st.write("")
        run_btn = st.button("🔄 이메일 분류 시작", type="primary", use_container_width=True)

    # ── 조회 구간 안내 ─────────────────────────────────────────────────────────
    _src_key = "gmail" if mail_source == "Gmail" else "daum"
    _last_end = get_last_period_end(_src_key)
    _now = datetime.datetime.now()
    _period_start = _last_end if _last_end else (_now - datetime.timedelta(hours=24))

    if _last_end:
        st.info(
            f"마지막 저장: **{_last_end.strftime('%Y-%m-%d %H:%M')}**  →  "
            f"현재: **{_now.strftime('%Y-%m-%d %H:%M')}** 사이의 이메일을 가져옵니다. (최대 50개)"
        )
    else:
        st.info("저장된 이력이 없습니다. 최근 24시간 이내 이메일을 가져옵니다. (최대 50개)")

    st.divider()

    # ── 분석 실행 ─────────────────────────────────────────────────────────────
    if run_btn:
        for key in ("category_groups", "business_summaries", "postings_with_urls",
                    "scraped_results", "total_count"):
            st.session_state.pop(key, None)

        period_start = _period_start
        period_end   = datetime.datetime.now()

        try:
            progress = st.progress(0, text="이메일 가져오는 중...")
            if mail_source == "Gmail":
                with st.spinner("Gmail 연결 중..."):
                    service = get_gmail_service()
                emails = fetch_emails(service, max_results=50, since_dt=period_start)
            else:
                with st.spinner("다음 메일 연결 중..."):
                    conn = get_daum_imap()
                emails = fetch_emails_imap(conn, max_results=50, since_dt=period_start)
            progress.empty()

            if not emails:
                st.info("해당 기간에 새로운 이메일이 없습니다.")
            else:
                progress = st.progress(25, text="이메일 분류 중...")
                classifications = classify_emails(emails)
                progress.progress(55, text="업무 메일 요약 중...")

                category_groups = defaultdict(list)
                business_emails = []
                newsletter_emails = []

                for c in classifications:
                    idx = c.index - 1
                    if 0 <= idx < len(emails):
                        email_obj = emails[idx]
                        category_groups[c.category].append({
                            "subject": email_obj.subject,
                            "sender":  email_obj.sender,
                            "summary": c.summary,
                            "date":    email_obj.date,
                        })
                        if c.category == "업무/비즈니스":
                            business_emails.append(email_obj)
                        elif c.category == "뉴스레터/마케팅":
                            newsletter_emails.append(email_obj)

                business_summaries = []
                if business_emails:
                    business_summaries = [
                        s.model_dump() for s in summarize_business_emails(business_emails)
                    ]

                progress.progress(80, text="채용공고 추출 중...")

                # 업무/비즈니스 + 뉴스레터/마케팅 모두에서 채용공고 추출
                job_source_emails = business_emails + newsletter_emails
                postings_with_urls = []
                if job_source_emails:
                    postings = extract_job_postings(job_source_emails)
                    postings_with_urls = [
                        p.model_dump() for p in resolve_job_urls(job_source_emails, postings)
                    ]

                if postings_with_urls:
                    progress.progress(90, text="채용공고 DB 저장 중...")
                    try:
                        _vs_store_jobs(postings_with_urls)
                        _ks_store_jobs(postings_with_urls)
                    except Exception:
                        pass

                # ── 이메일 이력 DB 저장 ───────────────────────────────────────
                progress.progress(95, text="이메일 이력 저장 중...")
                try:
                    to_store = [
                        {
                            "subject":     item["subject"],
                            "sender":      item["sender"],
                            "received_at": item["date"],
                            "category":    cat,
                            "ai_summary":  item["summary"],
                        }
                        for cat, items in category_groups.items()
                        for item in items
                    ]
                    store_session(_src_key, period_start, period_end, to_store)
                except Exception:
                    pass

                progress.progress(100, text="완료!")

                st.session_state["category_groups"]    = dict(category_groups)
                st.session_state["business_summaries"] = business_summaries
                st.session_state["postings_with_urls"] = postings_with_urls
                st.session_state["total_count"]        = len(classifications)

                progress.empty()
                st.rerun()

        except FileNotFoundError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"오류 발생: {e}")

    # ── 결과 없으면 안내 ──────────────────────────────────────────────────────
    if "category_groups" not in st.session_state:
        st.info("위에서 메일 계정과 이메일 수를 설정하고 **이메일 분류 시작** 버튼을 누르세요.")
        st.stop()

    category_groups    = st.session_state["category_groups"]
    total_count        = st.session_state["total_count"]
    business_summaries = st.session_state.get("business_summaries", [])

    # ── 통계 카드 + 바 차트 ───────────────────────────────────────────────────
    st.subheader(f"📊 분류 결과 — 총 {total_count}개 이메일 분석 완료")

    stats       = {cat: len(category_groups.get(cat, [])) for cat in CATEGORIES}
    active_cats = {k: v for k, v in stats.items() if v > 0}

    if active_cats:
        for col, (cat, cnt) in zip(st.columns(len(active_cats)), active_cats.items()):
            col.metric(cat, f"{cnt}개")
        st.divider()
        st.bar_chart(pd.DataFrame({"개수": list(active_cats.values())}, index=list(active_cats.keys())))

    st.divider()

    # ── 카테고리별 이메일 목록 ────────────────────────────────────────────────
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

    # ── 업무/비즈니스 상세 요약 ───────────────────────────────────────────────
    if business_summaries:
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

    # ── 추출된 채용공고 ───────────────────────────────────────────────────────
    postings = st.session_state.get("postings_with_urls", [])
    if postings:
        st.divider()
        st.subheader(f"📋 추출된 채용공고 — {len(postings)}개")
        for i, p in enumerate(postings):
            title   = p.get("job_title", "(직무 미상)")
            company = p.get("company", "")
            loc     = p.get("location") or ""
            url     = p.get("url")
            with st.expander(
                f"{i+1}. **{title}** — {company}" + (f"  ·  {loc}" if loc else ""),
                expanded=False,
            ):
                if url:
                    st.markdown(f"[🔗 공고 보러가기]({url})")
                else:
                    st.caption("링크 없음")
