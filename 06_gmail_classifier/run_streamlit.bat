@echo off
cd /d "%~dp0"
echo [Streamlit] 웹앱 시작
streamlit run streamlit_app.py
pause