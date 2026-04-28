"""
email_category.py — 이메일 분류 페이지
"""

import json
import uuid

import streamlit as st

from utils import chat

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "mail_source" not in st.session_state:
    st.session_state.mail_source = "gmail"
if "email_result" not in st.session_state:
    st.session_state.email_result = None
if "email_tool_log" not in st.session_state:
    st.session_state.email_tool_log = []

st.title("📧 Email Category")

# 설정
with st.expander("⚙️ 설정", expanded=False):
    st.session_state.mail_source = st.selectbox(
        "메일 소스", ["gmail", "daum"],
        index=0 if st.session_state.mail_source == "gmail" else 1,
    )

# 실행 버튼
col1, col2 = st.columns(2)
with col1:
    if st.button("📥 이메일 가져오기 & 분류", type="primary", use_container_width=True):
        with st.spinner("이메일 가져오는 중..."):
            try:
                result = chat(
                    "이메일을 가져와서 카테고리별로 분류해주세요.",
                    context={
                        "session_id": st.session_state.session_id,
                        "mail_source": st.session_state.mail_source,
                    },
                )
                st.session_state.email_result = result["reply"]
                st.session_state.email_tool_log = result.get("tool_calls_log", [])
                st.rerun()
            except Exception as e:
                st.error(str(e))

with col2:
    if st.button("💼 채용공고 추출", use_container_width=True):
        with st.spinner("채용공고 추출 중..."):
            try:
                result = chat(
                    "이메일에서 채용공고를 추출하고 저장해주세요.",
                    context={
                        "session_id": st.session_state.session_id,
                        "mail_source": st.session_state.mail_source,
                    },
                )
                st.session_state.email_result = result["reply"]
                st.session_state.email_tool_log = result.get("tool_calls_log", [])
                st.rerun()
            except Exception as e:
                st.error(str(e))

# 결과 표시
if st.session_state.email_result:
    st.divider()
    st.markdown(st.session_state.email_result)

    if st.session_state.email_tool_log:
        with st.expander(f"🔧 도구 호출 ({len(st.session_state.email_tool_log)}건)"):
            for tc in st.session_state.email_tool_log:
                st.code(
                    f"🔨 {tc['tool']}\n"
                    f"인자: {json.dumps(tc.get('args', {}), ensure_ascii=False, indent=2)}\n"
                    f"결과 미리보기: {tc.get('result_preview', '')}",
                    language="text",
                )
