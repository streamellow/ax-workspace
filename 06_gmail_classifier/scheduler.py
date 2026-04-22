"""
Gmail 이메일 분류기 — 자동 스케줄러
매일 12:00, 00:00 에 이메일 분석 후 Slack 알림 전송
"""

import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import schedule
from dotenv import load_dotenv

load_dotenv()

from gmail_classifier import (
    get_gmail_service,
    fetch_emails,
    classify_emails_with_claude,
    summarize_business_emails,
    send_to_slack,
)


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def run_analysis():
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook_url:
        log("SLACK_WEBHOOK_URL 환경 변수가 설정되지 않았습니다. .env 파일을 확인하세요.")
        return

    try:
        log("이메일 분석 시작...")
        service = get_gmail_service()
        emails = fetch_emails(service, max_results=30)

        if not emails:
            log("가져온 이메일이 없습니다.")
            return

        classifications = classify_emails_with_claude(emails)

        business_emails = []
        for clf in classifications:
            idx = clf["index"] - 1
            if 0 <= idx < len(emails) and clf["category"] == "업무/비즈니스":
                business_emails.append(emails[idx])

        if not business_emails:
            log("업무/비즈니스 이메일이 없어 Slack 전송을 건너뜁니다.")
            return

        summaries = summarize_business_emails(business_emails)
        errors = send_to_slack(webhook_url, summaries)

        if errors:
            log(f"일부 전송 실패: {errors}")
        else:
            log(f"Slack 전송 완료 ({len(summaries)}건)")

    except Exception as e:
        log(f"오류 발생: {e}")


schedule.every().day.at("12:00").do(run_analysis)
schedule.every().day.at("00:00").do(run_analysis)

log("스케줄러 시작 — 매일 12:00, 00:00 에 이메일 분석 및 Slack 알림 전송")

while True:
    schedule.run_pending()
    time.sleep(30)