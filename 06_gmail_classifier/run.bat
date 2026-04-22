@echo off
cd /d "%~dp0"
echo [스케줄러] 매일 12:00, 00:00 자동 이메일 분석 시작
python scheduler.py