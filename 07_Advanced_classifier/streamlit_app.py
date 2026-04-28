"""
streamlit_app.py — 앱 진입점 & 네비게이션
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

st.set_page_config(
    page_title="Scheduly",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded",
)

from login import require_login, logout_button

require_login()

pg = st.navigation([
    st.Page("pages/home.py",             title="Scheduly Home",  icon="🏠"),
    st.Page("pages/email_category.py",   title="Email Category", icon="📧"),
    st.Page("pages/resume_summary.py",   title="Resume Summary", icon="📄"),
])

logout_button()
pg.run()
