"""
login.py — 로그인 게이트
각 페이지 상단에서 require_login()을 호출하면 미로그인 시 로그인 폼을 표시하고 st.stop().
"""

import streamlit as st

_CREDENTIALS: dict[str, str] = {
    "admin": "admin",
}

_LOGIN_CSS = """
<style>
/* 사이드바 + 토글 버튼 완전 숨김 */
[data-testid="stSidebar"],
[data-testid="collapsedControl"] {
    display: none !important;
}

/* 본문 왼쪽 여백 제거 (사이드바 없으니 불필요) */
.block-container {
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}

/* 로그인 폼 카드 스타일 */
[data-testid="stForm"] {
    background: #ffffff;
    border: 1px solid #e2e8f0 !important;
    border-radius: 16px !important;
    padding: 40px 36px 32px !important;
    box-shadow: 0 4px 24px rgba(0,0,0,0.07);
}
</style>
"""


def require_login() -> None:
    """로그인 상태가 아니면 전체 화면 로그인 화면을 표시하고 페이지 진입을 차단한다."""
    if st.session_state.get("logged_in"):
        return

    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    # 수직 중앙 여백
    st.markdown("<div style='margin-top:12vh'></div>", unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        # 타이틀
        st.markdown(
            "<h1 style='text-align:center;font-size:2.2rem;font-weight:800;"
            "color:#1a1a2e;letter-spacing:-0.5px;margin-bottom:4px'>Scheduly</h1>"
            "<p style='text-align:center;color:#94a3b8;font-size:0.93rem;"
            "margin-bottom:28px'>계속하려면 로그인하세요</p>",
            unsafe_allow_html=True,
        )

        with st.form("login_form", clear_on_submit=False):
            user_id  = st.text_input("아이디", placeholder="아이디를 입력하세요")
            password = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요")
            submitted = st.form_submit_button("로그인", use_container_width=True, type="primary")

        if submitted:
            if _CREDENTIALS.get(user_id) == password:
                st.session_state["logged_in"] = True
                st.session_state["user_id"] = user_id
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 올바르지 않습니다.")

    st.stop()


def logout_button() -> None:
    """사이드바 하단에 로그아웃 버튼을 렌더링한다."""
    st.sidebar.divider()
    user = st.session_state.get("user_id", "")
    st.sidebar.caption(f"👤 {user} 로그인 중")
    if st.sidebar.button("로그아웃", use_container_width=True):
        st.session_state.clear()
        st.rerun()
