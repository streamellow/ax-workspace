"""
resume_summary.py — 이력서 분석 페이지
"""

import io
import json
import uuid

import streamlit as st

from utils import chat

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "resume_result" not in st.session_state:
    st.session_state.resume_result = None
if "resume_tool_log" not in st.session_state:
    st.session_state.resume_tool_log = []


def _extract_pdf_text(file) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file.read())) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception:
        pass
    try:
        import fitz
        doc = fitz.open(stream=file.read(), filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    except Exception:
        return ""


st.title("📄 Resume Summary")

uploaded = st.file_uploader("PDF 이력서를 업로드하세요", type=["pdf"])

if uploaded:
    st.success(f"업로드 완료: {uploaded.name}")
    if st.button("🔍 이력서 분석", type="primary"):
        resume_text = _extract_pdf_text(uploaded)
        if not resume_text.strip():
            st.error("PDF에서 텍스트를 추출하지 못했습니다.")
        else:
            with st.spinner("이력서 분석 중..."):
                try:
                    result = chat(
                        f"다음 이력서를 분석해주세요.\n\n이력서 내용:\n{resume_text[:4000]}",
                        context={
                            "session_id": st.session_state.session_id,
                            "resume_id": uploaded.name,
                        },
                    )
                    st.session_state.resume_result = result["reply"]
                    st.session_state.resume_tool_log = result.get("tool_calls_log", [])
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

if st.session_state.resume_result:
    st.divider()
    st.markdown(st.session_state.resume_result)

    if st.session_state.resume_tool_log:
        with st.expander(f"🔧 도구 호출 ({len(st.session_state.resume_tool_log)}건)"):
            for tc in st.session_state.resume_tool_log:
                st.code(
                    f"🔨 {tc['tool']}\n"
                    f"인자: {json.dumps(tc.get('args', {}), ensure_ascii=False, indent=2)}\n"
                    f"결과 미리보기: {tc.get('result_preview', '')}",
                    language="text",
                )

# 채용공고 매칭 버튼 (이력서 분석 후)
if st.session_state.resume_result:
    st.divider()
    if st.button("💼 저장된 채용공고와 매칭"):
        with st.spinner("매칭 중..."):
            try:
                result = chat(
                    "분석된 이력서와 저장된 채용공고를 매칭해주세요.",
                    context={"session_id": st.session_state.session_id},
                )
                st.markdown(result["reply"])
            except Exception as e:
                st.error(str(e))
