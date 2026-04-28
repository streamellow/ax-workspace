"""
Main — 스케줄러 진입점
매일 12:00, 00:00 에 이메일 분석 → Slack 전송
로그는 logs/YYYY-MM-DD.log 파일에 일별 저장
"""

import os
import time
import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

import schedule
from dotenv import load_dotenv

load_dotenv()

from auth import get_gmail_service
from indexing import fetch_emails, classify_emails
from retrieval import summarize_business_emails, send_to_slack

MAX_RESULTS = int(os.environ.get("MAX_RESULTS", 30))

# ── 로거 설정 ────────────────────────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("scheduler")
logger.setLevel(logging.INFO)

# 콘솔 출력
_console = logging.StreamHandler()
_console.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
logger.addHandler(_console)

# 파일 출력 — 자정마다 새 파일, 최대 90일 보관
_log_file = os.path.join(LOG_DIR, f"{datetime.now().strftime('%Y-%m-%d')}.log")
_file = TimedRotatingFileHandler(
    _log_file, when="midnight", interval=1, backupCount=90, encoding="utf-8"
)
_file.suffix = "%Y-%m-%d.log"
_file.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
logger.addHandler(_file)


def log(msg: str) -> None:
    logger.info(msg)


# ── 파이프라인 ───────────────────────────────────────────────────────────────
def run_pipeline() -> None:
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook_url:
        log("SLACK_WEBHOOK_URL 환경 변수가 설정되지 않았습니다. .env 파일을 확인하세요.")
        return

    try:
        log("이메일 분석 시작...")
        service = get_gmail_service()
        emails = fetch_emails(service, max_results=MAX_RESULTS)

        if not emails:
            log("가져온 이메일이 없습니다.")
            return

        log(f"{len(emails)}개 이메일 분류 중...")
        classifications = classify_emails(emails)

        business_emails = [
            emails[c.index - 1]
            for c in classifications
            if c.category == "업무/비즈니스" and 0 < c.index <= len(emails)
        ]

        if not business_emails:
            log("업무/비즈니스 이메일이 없어 Slack 전송을 건너뜁니다.")
            return

        log(f"업무 메일 {len(business_emails)}건 요약 중...")
        summaries = summarize_business_emails(business_emails)

        errors = send_to_slack(webhook_url, summaries)
        if errors:
            log(f"일부 전송 실패: {errors}")
        else:
            log(f"Slack 전송 완료 ({len(summaries)}건)")

    except Exception as e:
        log(f"오류 발생: {e}")


# ── 스케줄 등록 ──────────────────────────────────────────────────────────────
schedule.every().hour.do(run_pipeline)

log("스케줄러 시작 — 매 1시간마다 이메일 분석 및 Slack 알림 전송")

while True:
    schedule.run_pending()
    time.sleep(30)