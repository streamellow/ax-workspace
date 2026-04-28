"""
home.py — Scheduly 홈: 일정 입력 + 월별 캘린더
"""

import uuid
from datetime import date

import streamlit as st
from streamlit_calendar import calendar as st_calendar

from utils import chat, get_month_events

# 세션 초기화
for _key, _default in [
    ("session_id", str(uuid.uuid4())),
    ("home_messages", []),
    ("cal_year", date.today().year),
    ("cal_month", date.today().month),
]:
    if _key not in st.session_state:
        st.session_state[_key] = _default

left_col, right_col = st.columns([2, 3], gap="large")

# ── 왼쪽: 로고 + 명령 입력 ──────────────────────────────────────────────────
with left_col:
    st.markdown(
        "<div style='display:flex;align-items:center;gap:14px;margin-bottom:36px;'>"
        "<span style='font-size:52px;'>🗓️</span>"
        "<span style='font-size:40px;font-weight:700;letter-spacing:-1px;'>Scheduly</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    with st.form("cmd_form", clear_on_submit=True):
        inp_col, btn_col = st.columns([6, 1])
        with inp_col:
            user_cmd = st.text_input(
                "cmd",
                placeholder="예) 0월 0일에 일정 등록 / 0월 0일 일정을 0월 0일로 옮겨줘",
                label_visibility="collapsed",
            )
        with btn_col:
            submit = st.form_submit_button("✓", type="primary", use_container_width=True)

    if submit and user_cmd:
        with st.spinner("처리 중..."):
            try:
                result = chat(user_cmd, context={"session_id": st.session_state.session_id})
                st.session_state.home_messages.append({"role": "user", "content": user_cmd})
                st.session_state.home_messages.append(
                    {"role": "assistant", "content": result["reply"]}
                )
                st.rerun()
            except Exception as e:
                st.error(str(e))

    # 전체 대화 기록 (스크롤 가능)
    with st.container(height=450):
        for msg in st.session_state.home_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

# ── 오른쪽: 캘린더 ─────────────────────────────────────────────────────────
with right_col:
    year = st.session_state.cal_year
    month = st.session_state.cal_month

    # 월 네비게이션 헤더
    c_prev, c_title, c_next, c_disc = st.columns([1, 4, 1, 2])
    with c_prev:
        if st.button("◄", key="cal_prev"):
            if month == 1:
                st.session_state.cal_year, st.session_state.cal_month = year - 1, 12
            else:
                st.session_state.cal_month = month - 1
            st.rerun()
    with c_title:
        st.markdown(
            f"<p style='text-align:center;font-size:16px;font-weight:600;margin:6px 0;'>"
            f"{year}년 {month:02d}월</p>",
            unsafe_allow_html=True,
        )
    with c_next:
        if st.button("►", key="cal_next"):
            if month == 12:
                st.session_state.cal_year, st.session_state.cal_month = year + 1, 1
            else:
                st.session_state.cal_month = month + 1
            st.rerun()
    with c_disc:
        if st.button("연동 해제", key="disconnect"):
            st.info("캘린더 연동 해제: token.json 및 calendar_token.json을 삭제하세요.")

    # 이벤트 조회
    raw_events = get_month_events(year, month)

    cal_events = [
        {
            "title": ev.get("title", ""),
            "start": ev["start"][:10] if "T" in ev.get("start", "") else ev.get("start", ""),
            "color": "#6c5ce7",
        }
        for ev in raw_events
        if ev.get("start")
    ]

    cal_options = {
        "headerToolbar": {"left": "", "center": "", "right": ""},
        "initialView": "dayGridMonth",
        "initialDate": f"{year}-{month:02d}-01",
        "height": "auto",
        "editable": False,
        "selectable": False,
        "dayMaxEvents": 3,
        "locale": "en",
    }

    custom_css = """
    .fc-theme-standard td, .fc-theme-standard th { border-color: #2d2d4e; }
    .fc-daygrid-day { background: #0f0f1a; }
    .fc-col-header { background: #312e81; }
    .fc-col-header-cell-cushion { color: #ccc; font-size: 12px; text-decoration: none; }
    .fc-daygrid-day-number { color: #ddd; font-size: 13px; text-decoration: none; }
    .fc .fc-daygrid-day.fc-day-today { background-color: rgba(108,92,231,0.15); }
    .fc-event { border-radius: 4px; font-size: 11px; }
    .fc-event-title { font-weight: 400; }
    .fc-daygrid-day.fc-day-sun .fc-daygrid-day-number { color: #ff7675; }
    .fc-daygrid-day.fc-day-sat .fc-daygrid-day-number { color: #74b9ff; }
    """

    st_calendar(
        events=cal_events,
        options=cal_options,
        custom_css=custom_css,
        key=f"cal_{year}_{month}",
    )
