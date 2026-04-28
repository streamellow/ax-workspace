import os
import sys
import io
import json
import logging
import pdfplumber
import fitz  # pymupdf
import pytesseract
from PIL import Image
import streamlit as st
from dotenv import load_dotenv

logging.getLogger("pdfminer").setLevel(logging.ERROR)

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

from retrieval import analyze_resume, scrape_job_page, playwright_login, PLAYWRIGHT_AUTH
from vector_store import store_resume as _vs_store_resume
from keyword_store import store_resume as _ks_store_resume, get_all_resumes, get_job_posting
from search import hybrid_search_jobs, reverse_search_resumes
from login import require_login, logout_button

st.set_page_config(page_title="이력서 분석", page_icon="📄", layout="wide")

require_login()

logout_button()

# ── 사이드바: Playwright 로그인 관리 ───────────────────────────────────────────
with st.sidebar:
    st.header("🔐 사이트 로그인")
    auth_exists = os.path.exists(PLAYWRIGHT_AUTH)
    if auth_exists:
        st.success("로그인 세션 저장됨")
        st.caption("LinkedIn 등 로그인 필요 사이트 스크래핑 가능")
        if st.button("🔄 세션 초기화 후 재로그인"):
            os.remove(PLAYWRIGHT_AUTH)
            st.rerun()
    else:
        st.warning("로그인 세션 없음")
        st.caption("LinkedIn 공고 내용을 보려면 로그인이 필요합니다.")
        if st.button("🔑 LinkedIn 로그인", type="primary"):
            with st.spinner("브라우저가 열립니다. LinkedIn에 로그인해주세요..."):
                success, error_msg = playwright_login()
            if success:
                st.success("로그인 완료! 세션이 저장되었습니다.")
                st.rerun()
            else:
                st.error(f"로그인에 실패했습니다: {error_msg}")

st.title("📄 이력서 / 포트폴리오 분석")
st.caption("PDF 이력서를 업로드하면 AI가 적합 직무, 기술 스택, 특징을 분석합니다.")


def extract_text_with_ocr(pdf_bytes: bytes) -> str:
    """이미지 기반 PDF를 Tesseract OCR로 텍스트 추출."""
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
    """텍스트 추출. (추출된 텍스트, OCR 사용 여부) 반환."""
    pdf_bytes = uploaded_file.read()

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages).strip()

    if text:
        return text, False

    return extract_text_with_ocr(pdf_bytes), True


uploaded = st.file_uploader("PDF 파일을 업로드하세요", type=["pdf"])

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

        # ── 이력서 DB 저장 ────────────────────────────────────────────────────
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
                st.info("저장된 채용공고가 없습니다. 메인 페이지에서 이메일 분석을 먼저 실행해주세요.")
            else:
                for i, m in enumerate(matches):
                    final_pct  = int(m["final_score"] * 100)
                    vec_pct    = int(m.get("vector_score", 0) * 100)
                    kw_pct     = int(m.get("keyword_score", 0) * 100)
                    with st.expander(
                        f"{i+1}. **{m['job_title']}** — {m['company']}  ·  매칭 {final_pct}%",
                        expanded=(i < 3),
                    ):
                        # ── 기본 정보 헤더 ────────────────────────────────────
                        c1, c2, c3 = st.columns([3, 3, 2])
                        c1.markdown(f"**회사:** {m['company']}")
                        c2.markdown(f"**지역:** {m.get('location') or '미상'}")
                        c3.metric("매칭도", f"{final_pct}%")
                        st.caption(f"벡터 유사도 {vec_pct}%  ·  키워드 매칭 {kw_pct}%")
                        if m.get("url"):
                            st.markdown(f"[🔗 공고 보러가기]({m['url']})")

                        # ── 공고 상세 내용 ────────────────────────────────────
                        st.divider()
                        stored = get_job_posting(m["company"], m["job_title"])
                        sections = stored.get("sections", []) if stored else []

                        # sections가 없거나 비어있으면 URL 스크래핑 fallback
                        if not sections and m.get("url"):
                            with st.spinner("공고 내용 불러오는 중..."):
                                scraped = scrape_job_page(m["url"])
                                sections = [s.model_dump() for s in scraped]

                        failed = (
                            len(sections) == 1
                            and sections[0].get("heading") == "스크래핑 실패"
                        ) if sections else False

                        # 로그인 장벽 감지 (LinkedIn 등)
                        LOGIN_KEYWORDS = {"로그인", "sign in", "log in", "signin", "login", "인증"}
                        is_login_wall = sections and not failed and all(
                            any(kw in (sec.get("heading", "") + sec.get("content", "")).lower()
                                for kw in LOGIN_KEYWORDS)
                            for sec in sections[:3]
                        )

                        if not sections:
                            st.info("공고 상세 내용이 없습니다. 채용공고 페이지를 먼저 방문해주세요.")
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
                                    f"""
                                    <div style="
                                        border-left: 4px solid #4a90d9;
                                        background: #f4f7fb;
                                        padding: 10px 16px;
                                        margin-bottom: 8px;
                                        border-radius: 0 6px 6px 0;
                                    ">
                                      <div style="font-weight:700;font-size:0.92rem;color:#1a1a2e;margin-bottom:4px">{heading}</div>
                                      <div style="font-size:0.85rem;color:#444;white-space:pre-wrap;line-height:1.7">{content}</div>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
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
            import json as _json
            skills = _json.loads(r.get("skills") or "[]")
            suitable = _json.loads(r.get("suitable_jobs") or "[]")
            with st.expander(
                f"**{r.get('name') or r['id']}**  ·  {r.get('filename', '')}  "
                f"·  {r.get('created_at', '')[:10]}",
                expanded=False,
            ):
                st.markdown(f"**적합 직무:** {' · '.join(suitable)}")
                st.markdown(f"**기술 스택:** {' · '.join(skills)}")
except Exception as e:
    st.warning(f"이력서 목록 불러오기 실패: {e}")