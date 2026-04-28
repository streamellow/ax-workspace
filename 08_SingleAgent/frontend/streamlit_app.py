"""
streamlit_app.py — 인증 + 멀티페이지 네비게이션 진입점
"""

import streamlit as st
from utils import login, secret

st.set_page_config(page_title="Scheduly", page_icon="🗓️", layout="wide")

# 세션 초기화
if "token" not in st.session_state:
    st.session_state.token = None
if "username" not in st.session_state:
    st.session_state.username = ""

# 로그인 화면
if not st.session_state.token:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown(
            "<div style='text-align:center;font-size:52px;margin-bottom:8px;'>🗓️</div>"
            "<h1 style='text-align:center;margin-bottom:32px;'>Scheduly</h1>",
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            username = st.text_input("아이디", value=secret("ADMIN_USERNAME", ""))
            password = st.text_input("비밀번호", type="password", value=secret("ADMIN_PASSWORD", ""))
            submitted = st.form_submit_button("로그인", use_container_width=True, type="primary")
        if submitted:
            token = login(username, password)
            if token:
                st.session_state.token = token
                st.session_state.username = username
                st.rerun()
            else:
                st.error("로그인 실패. 아이디 또는 비밀번호를 확인하세요.")
    st.stop()

# 페이지 네비게이션
pages = [
    st.Page("home.py", title="Scheduly Home", icon=":material/calendar_month:"),
    st.Page("email_category.py", title="Email Category", icon=":material/mail:"),
    st.Page("resume_summary.py", title="Resume Summary", icon=":material/description:"),
]
pg = st.navigation(pages)

with st.sidebar:
    st.divider()
    st.caption(f"👤 **{st.session_state.username}** 로그인 중")
    if st.button("로그아웃", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

pg.run()
