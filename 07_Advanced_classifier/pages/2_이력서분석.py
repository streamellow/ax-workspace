import os
import sys
import io
import pdfplumber
import fitz  # pymupdf
import pytesseract
from PIL import Image
import streamlit as st
from dotenv import load_dotenv

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from retrieval import analyze_resume

st.set_page_config(page_title="이력서 분석", page_icon="📄", layout="wide")
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