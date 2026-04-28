"""
resume_summary.py — 이력서 / 포트폴리오 분석
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import io
import logging
import pdfplumber
import fitz
import pytesseract
from PIL import Image
import streamlit as st
from dotenv import load_dotenv

logging.getLogger("pdfminer").setLevel(logging.ERROR)

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
load_dotenv(os.path.join(_ROOT, ".env"))

import json as _json
import datetime as _dt
from retrieval import analyze_resume, scrape_job_page, playwright_login, PLAYWRIGHT_AUTH
from auth import get_calendar_service, CALENDAR_TOKEN_PATH
from vector_store import store_resume as _vs_store_resume
from keyword_store import store_resume as _ks_store_resume, get_all_resumes, get_resume_full, get_job_posting
from search import hybrid_search_jobs, reverse_search_resumes
from schemas import ResumeAnalysis


def _render_match_expander(i: int, m: dict, btn_prefix: str, show_sections: bool = False) -> None:
    final_pct = int(m["final_score"] * 100)
    vec_pct   = int(m.get("vector_score", 0) * 100)
    kw_pct    = int(m.get("keyword_score", 0) * 100)
    btn_key   = f"{btn_prefix}_{i}"

    with st.expander(
        f"{i+1}. **{m['job_title']}** — {m['company']}  ·  매칭 {final_pct}%",
        expanded=(i < 3),
    ):
        c1, c2, c3 = st.columns([3, 3, 2])
        c1.markdown(f"**회사:** {m['company']}")
        c2.markdown(f"**지역:** {m.get('location') or '미상'}")
        c3.metric("매칭도", f"{final_pct}%")
        st.caption(f"벡터 유사도 {vec_pct}%  ·  키워드 매칭 {kw_pct}%")
        if m.get("url"):
            st.markdown(f"[🔗 공고 보러가기]({m['url']})")

        # ── ✏️ 마감일 캘린더 등록 / 🔄 수정 버튼 ─────────────────────
        stored        = get_job_posting(m["company"], m["job_title"])
        deadline      = (stored or {}).get("deadline") or ""
        cal_key       = f"cal_status_{btn_key}"
        cal_event_key = f"cal_event_{btn_key}"   # 등록된 Google Calendar 이벤트 ID
        date_key      = f"cal_date_{btn_key}"

        if deadline:
            is_registered = cal_event_key in st.session_state
            btn_label     = "🔄 일정 수정" if is_registered else "✏️ 마감일 캘린더 등록"

            btn_col, date_col, msg_col = st.columns([2, 2, 3])
            with date_col:
                new_date = st.text_input(
                    "날짜",
                    value=deadline,
                    key=date_key,
                    placeholder="YYYY-MM-DD",
                    label_visibility="collapsed",
                )
            with btn_col:
                if st.button(btn_label, key=f"cal_{btn_key}"):
                    if not os.path.exists(CALENDAR_TOKEN_PATH):
                        st.session_state[cal_key] = "⚠️ Home 화면에서 Google Calendar를 먼저 연동해주세요."
                    else:
                        try:
                            svc      = get_calendar_service()
                            use_date = (new_date or "").strip() or deadline
                            next_day = (
                                _dt.date.fromisoformat(use_date) + _dt.timedelta(days=1)
                            ).isoformat()

                            # 기존 이벤트 삭제
                            old_event_id = st.session_state.get(cal_event_key)
                            if old_event_id:
                                try:
                                    svc.events().delete(
                                        calendarId="primary", eventId=old_event_id
                                    ).execute()
                                except Exception:
                                    pass

                            # 새 이벤트 등록
                            event = svc.events().insert(
                                calendarId="primary",
                                body={
                                    "summary":     f"{m['company']} 채용 마감",
                                    "description": m["job_title"],
                                    "start":       {"date": use_date},
                                    "end":         {"date": next_day},
                                },
                            ).execute()
                            st.session_state[cal_event_key] = event["id"]
                            action = "수정" if is_registered else "등록"
                            st.session_state[cal_key] = f"✅ {use_date} {action} 완료"
                        except Exception as e:
                            st.session_state[cal_key] = f"❌ 실패: {e}"
                    st.rerun()
            with msg_col:
                status = st.session_state.get(cal_key)
                st.caption(status if status else f"마감일: **{deadline}**")

        if not show_sections:
            return

        # ── 공고 상세 섹션 ─────────────────────────────────────────────
        st.divider()
        sections = (stored.get("sections", []) if stored else [])

        if not sections and m.get("url"):
            with st.spinner("공고 내용 불러오는 중..."):
                sections = [s.model_dump() for s in scrape_job_page(m["url"])]

        failed = (
            len(sections) == 1 and sections[0].get("heading") == "스크래핑 실패"
        ) if sections else False

        LOGIN_KEYWORDS = {"로그인", "sign in", "log in", "signin", "login", "인증"}
        is_login_wall = sections and not failed and all(
            any(kw in (sec.get("heading", "") + sec.get("content", "")).lower()
                for kw in LOGIN_KEYWORDS)
            for sec in sections[:3]
        )

        if not sections:
            st.info("공고 상세 내용이 없습니다.")
        elif failed:
            st.warning(f"페이지 접근 실패: {sections[0].get('content', '')}")
        elif is_login_wall:
            st.warning(
                "이 공고는 로그인이 필요한 사이트(LinkedIn 등)입니다.  \n"
                "상세 내용을 보려면 위 **공고 보러가기** 링크를 직접 클릭해주세요."
            )
        else:
            for sec in sections:
                heading = sec.get("heading", "")
                content = sec.get("content", "").strip()
                if not heading and not content:
                    continue
                st.markdown(
                    f"""<div style="border-left:4px solid #4a90d9;background:#f4f7fb;
                    padding:10px 16px;margin-bottom:8px;border-radius:0 6px 6px 0">
                      <div style="font-weight:700;font-size:0.92rem;color:#1a1a2e;
                      margin-bottom:4px">{heading}</div>
                      <div style="font-size:0.85rem;color:#444;white-space:pre-wrap;
                      line-height:1.7">{content}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )


# ── 헤더 ─────────────────────────────────────────────────────────────────────
st.title("📄 Resume Summary")
st.caption("PDF 이력서를 업로드하면 AI가 적합 직무, 기술 스택, 특징을 분석합니다.")
st.divider()

# ── PDF 업로드 ────────────────────────────────────────────────────────────────
st.markdown("#### PDF 파일을 업로드하세요")
uploaded = st.file_uploader("이력서 또는 포트폴리오 PDF", type=["pdf"], label_visibility="collapsed")

if not uploaded:
    st.info("PDF 파일을 드래그하거나 위 버튼으로 업로드하세요.")


def extract_text_with_ocr(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    texts = []
    for page_num, page in enumerate(doc):
        if page_num >= 10:
            break
        pix = page.get_pixmap(dpi=200)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        text = pytesseract.image_to_string(img, lang="kor+eng")
        if text.strip():
            texts.append(text)
    return "\n".join(texts)


def extract_text(uploaded_file) -> tuple[str, bool]:
    pdf_bytes = uploaded_file.read()
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages).strip()
    if text:
        return text, False
    return extract_text_with_ocr(pdf_bytes), True


if uploaded:
    if st.button("분석 시작", type="primary"):
        with st.spinner("PDF 텍스트 추출 중..."):
            try:
                pdf_text, used_ocr = extract_text(uploaded)
            except Exception as e:
                st.error(f"PDF 읽기 실패: {e}")
                st.stop()

        if not pdf_text.strip():
            st.error("텍스트를 추출할 수 없습니다.")
            st.stop()

        if used_ocr:
            st.info("이미지 기반 PDF — Tesseract OCR로 텍스트를 추출했습니다.")

        with st.spinner("AI 분석 중..."):
            try:
                result = analyze_resume(pdf_text)
            except Exception as e:
                st.error(f"분석 실패: {e}")
                st.stop()

        st.success(f"분석 완료 — {result.name}")
        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("🎯 적합 직무")
            for job in result.suitable_jobs:
                st.markdown(f"- {job}")

            st.subheader("💪 강점")
            for s in result.strengths:
                st.markdown(f"- {s}")

            st.subheader("🔑 직무 키워드")
            st.markdown(" · ".join(f"`{k}`" for k in result.job_keywords))

        with col2:
            st.subheader("🛠 기술 스택")
            for skill in result.skills:
                st.markdown(f"- {skill}")

            st.subheader("✨ 특징")
            for c in result.characteristics:
                st.markdown(f"- {c}")

        st.divider()
        st.subheader("📋 경력 요약")
        st.write(result.career_summary)

        # ── DB 저장 ──────────────────────────────────────────────────────────
        st.divider()
        resume_id = uploaded.name.replace(".pdf", "").replace(" ", "_")
        try:
            resume_dict = result.model_dump()
            _vs_store_resume(resume_id, resume_dict)
            _ks_store_resume(resume_id, resume_dict, uploaded.name, pdf_text)
            st.caption("✅ 이력서가 DB에 저장되었습니다.")
        except Exception as e:
            st.caption(f"⚠️ 이력서 저장 실패: {e}")

        # ── 매칭 채용공고 ─────────────────────────────────────────────────────
        st.divider()
        st.subheader("🎯 이력서 기반 매칭 채용공고")
        try:
            matches = hybrid_search_jobs(result)
            if not matches:
                st.info("저장된 채용공고가 없습니다. Email Category에서 이메일 분석을 먼저 실행해주세요.")
            else:
                for i, m in enumerate(matches):
                    _render_match_expander(i, m, "pdf", show_sections=True)
        except Exception as e:
            st.warning(f"매칭 검색 실패: {e}")

# ── 저장된 이력서 목록 ─────────────────────────────────────────────────────────
st.divider()
st.subheader("🗂 저장된 이력서 목록")
try:
    all_resumes = get_all_resumes()
    if not all_resumes:
        st.info("아직 저장된 이력서가 없습니다.")
    else:
        for r in all_resumes:
            skills   = _json.loads(r.get("skills") or "[]")
            suitable = _json.loads(r.get("suitable_jobs") or "[]")
            with st.expander(
                f"**{r.get('name') or r['id']}**  ·  {r.get('filename', '')}  "
                f"·  {r.get('created_at', '')[:10]}",
                expanded=False,
            ):
                st.markdown(f"**적합 직무:** {' · '.join(suitable)}")
                st.markdown(f"**기술 스택:** {' · '.join(skills)}")
                if st.button("🔍 매칭 공고 찾기", key=f"match_{r['id']}"):
                    st.session_state["match_resume_id"] = r["id"]
                    st.session_state["match_resume_name"] = r.get("name") or r["id"]
                    st.rerun()
except Exception as e:
    st.warning(f"이력서 목록 불러오기 실패: {e}")

# ── 저장된 이력서 매칭 결과 ───────────────────────────────────────────────────
if "match_resume_id" in st.session_state:
    match_id   = st.session_state["match_resume_id"]
    match_name = st.session_state.get("match_resume_name", match_id)

    st.divider()
    hdr_col, close_col = st.columns([5, 1])
    hdr_col.subheader(f"🎯 **{match_name}** — 매칭 채용공고")
    if close_col.button("✕ 닫기", key="close_match"):
        st.session_state.pop("match_resume_id", None)
        st.session_state.pop("match_resume_name", None)
        st.rerun()

    try:
        full = get_resume_full(match_id)
        if not full:
            st.warning("이력서 데이터를 불러올 수 없습니다.")
        else:
            resume_obj = ResumeAnalysis(
                name=full.get("name") or "",
                suitable_jobs=_json.loads(full.get("suitable_jobs") or "[]"),
                skills=_json.loads(full.get("skills") or "[]"),
                characteristics=[],
                career_summary=full.get("career_summary") or "",
                strengths=[],
                job_keywords=_json.loads(full.get("job_keywords") or "[]"),
            )

            with st.spinner("채용공고 매칭 중..."):
                matches = hybrid_search_jobs(resume_obj)

            if not matches:
                st.info("매칭되는 채용공고가 없습니다. Email Category에서 이메일 분석을 먼저 실행해주세요.")
            else:
                # 요약 태그 표시
                tag_col1, tag_col2 = st.columns(2)
                with tag_col1:
                    st.caption(f"**적합 직무:** {' · '.join(resume_obj.suitable_jobs)}")
                with tag_col2:
                    st.caption(f"**기술 스택:** {' · '.join(resume_obj.skills[:6])}"
                               + (" ..." if len(resume_obj.skills) > 6 else ""))

                st.markdown(f"총 **{len(matches)}개** 공고 매칭됨")
                st.divider()

                for i, m in enumerate(matches):
                    _render_match_expander(i, m, f"saved_{match_id}", show_sections=False)
    except Exception as e:
        st.warning(f"매칭 검색 실패: {e}")
