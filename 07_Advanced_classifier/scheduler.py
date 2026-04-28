"""
scheduler.py — 6시간마다 이메일 자동 수집·분류·저장
실행: python scheduler.py
      python scheduler.py --once   (단 1회 실행 후 종료)
"""

import os
import sys
import time
import datetime
import schedule
import requests
from email.utils import parsedate_to_datetime
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from auth import get_gmail_service, get_daum_imap, get_calendar_service, CALENDAR_TOKEN_PATH
from indexing import fetch_emails, fetch_emails_imap, classify_emails
from email_store import store_session

# .env 에서 SCHEDULER_MAIL_SOURCE=gmail 또는 daum 으로 설정
MAIL_SOURCE              = os.environ.get("SCHEDULER_MAIL_SOURCE", "gmail").lower()
INTERVAL_HOURS           = int(os.environ.get("SCHEDULER_INTERVAL_HOURS", "6"))
SLACK_WEBHOOK_URL        = os.environ.get("SLACK_WEBHOOK_URL", "")
CALENDAR_REMINDER_TIME   = os.environ.get("CALENDAR_REMINDER_TIME", "09:00")


def _fetch_today_calendar_events() -> list[dict]:
    """오늘 날짜 Google Calendar 이벤트 목록 반환."""
    today    = datetime.date.today()
    next_day = (today + datetime.timedelta(days=1)).isoformat()
    result   = get_calendar_service().events().list(
        calendarId  = "primary",
        timeMin     = f"{today.isoformat()}T00:00:00+09:00",
        timeMax     = f"{next_day}T00:00:00+09:00",
        singleEvents= True,
        orderBy     = "startTime",
    ).execute()
    events = []
    for ev in result.get("items", []):
        start     = ev.get("start", {})
        is_allday = "dateTime" not in start
        time_str  = "종일"
        if not is_allday:
            dt       = start.get("dateTime", "")
            time_str = dt[11:16] if len(dt) >= 16 else "종일"
        events.append({"title": ev.get("summary", "(제목 없음)"), "time": time_str})
    return events


def send_calendar_reminders() -> None:
    """오늘 일정을 조회해 Slack 으로 알림 전송."""
    now = datetime.datetime.now()
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 캘린더 알림 확인 중...")

    if not SLACK_WEBHOOK_URL:
        print("  [SKIP] SLACK_WEBHOOK_URL 미설정")
        return
    if not os.path.exists(CALENDAR_TOKEN_PATH):
        print("  [SKIP] Google Calendar 미연동 (Home 화면에서 연동 필요)")
        return

    try:
        events = _fetch_today_calendar_events()
    except Exception as e:
        print(f"  [ERROR] 캘린더 조회 실패: {e}")
        return

    today_label = datetime.date.today().strftime("%Y년 %m월 %d일")

    if not events:
        print(f"  오늘({today_label}) 일정 없음 — 알림 건너뜀")
        return

    print(f"  오늘 일정 {len(events)}개 → Slack 전송")

    event_lines = "\n".join(f"• *{ev['title']}*  —  {ev['time']}" for ev in events)
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📅 오늘의 일정  |  {today_label}", "emoji": True},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": event_lines},
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"총 {len(events)}개 일정"}],
        },
    ]
    try:
        requests.post(SLACK_WEBHOOK_URL, json={"blocks": blocks}, timeout=10).raise_for_status()
        print(f"  Slack 캘린더 알림 전송 완료 ({len(events)}개)")
    except Exception as e:
        print(f"  [ERROR] Slack 전송 실패: {e}")


def _parse_email_dt(date_str: str) -> datetime.datetime | None:
    try:
        return parsedate_to_datetime(date_str).replace(tzinfo=None)
    except Exception:
        return None


def run_once() -> None:
    now = datetime.datetime.now()
    period_start = now - datetime.timedelta(hours=INTERVAL_HOURS)
    period_end   = now

    print(
        f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 수집 시작 ({MAIL_SOURCE.upper()})  "
        f"{period_start.strftime('%m/%d %H:%M')} ~ {period_end.strftime('%H:%M')}"
    )

    # ── 메일 가져오기 ─────────────────────────────────────────────────────────
    try:
        if MAIL_SOURCE == "gmail":
            service = get_gmail_service()
            emails  = fetch_emails(service, max_results=100)
        else:
            conn   = get_daum_imap()
            emails = fetch_emails_imap(conn, max_results=100)
    except Exception as e:
        print(f"  [ERROR] 메일 가져오기 실패: {e}")
        return

    # ── 6시간 이내 수신 메일만 필터 ──────────────────────────────────────────
    filtered = [
        em for em in emails
        if (dt := _parse_email_dt(em.date)) and period_start <= dt <= period_end
    ]

    print(f"  전체 {len(emails)}개 → 해당 구간 {len(filtered)}개")

    if not filtered:
        print("  저장할 메일 없음.")
        return

    # ── AI 분류 ───────────────────────────────────────────────────────────────
    try:
        classifications = classify_emails(filtered)
    except Exception as e:
        print(f"  [ERROR] 분류 실패: {e}")
        return

    cat_map = {c.index - 1: (c.category, c.summary) for c in classifications}

    to_store = []
    business_emails   = []
    newsletter_emails = []
    for i, em in enumerate(filtered):
        cat, summary = cat_map.get(i, ("기타", ""))
        to_store.append({
            "subject":     em.subject,
            "sender":      em.sender,
            "received_at": em.date,
            "category":    cat,
            "ai_summary":  summary,
        })
        if cat == "업무/비즈니스":
            business_emails.append(em)
        elif cat == "뉴스레터/마케팅":
            newsletter_emails.append(em)

    # ── 채용공고 추출 및 저장 (업무/비즈니스 + 뉴스레터/마케팅) ─────────────────
    job_source_emails = business_emails + newsletter_emails
    if job_source_emails:
        try:
            from indexing import extract_job_postings, resolve_job_urls
            from vector_store import store_job_postings as _vs_store_jobs
            from keyword_store import store_job_postings as _ks_store_jobs

            postings = extract_job_postings(job_source_emails)
            postings_with_urls = [
                p.model_dump() for p in resolve_job_urls(job_source_emails, postings)
            ]
            if postings_with_urls:
                _vs_store_jobs(postings_with_urls)
                _ks_store_jobs(postings_with_urls)
                print(f"  채용공고 저장 — {len(postings_with_urls)}개")
        except Exception as e:
            print(f"  [WARN] 채용공고 추출 실패: {e}")

    # ── 이메일 이력 DB 저장 ───────────────────────────────────────────────────
    try:
        session_id = store_session(MAIL_SOURCE, period_start, period_end, to_store)
        print(f"  저장 완료 — session #{session_id}, {len(to_store)}개")
    except Exception as e:
        print(f"  [ERROR] 저장 실패: {e}")


def main() -> None:
    once         = "--once" in sys.argv
    remind_now   = "--remind-now" in sys.argv

    print("=" * 55)
    print(f"  Scheduly 메일 스케줄러  (소스: {MAIL_SOURCE.upper()})")
    if once:
        print("  모드: 1회 실행")
    else:
        print(f"  모드: {INTERVAL_HOURS}시간 간격 반복")
        print(f"  캘린더 알림: 매일 {CALENDAR_REMINDER_TIME}")
    print("=" * 55)

    run_once()

    if remind_now:
        send_calendar_reminders()

    if once:
        return

    schedule.every(INTERVAL_HOURS).hours.do(run_once)
    schedule.every().day.at(CALENDAR_REMINDER_TIME).do(send_calendar_reminders)

    print(f"\n다음 실행: {INTERVAL_HOURS}시간 후. 캘린더 알림: 매일 {CALENDAR_REMINDER_TIME}. 종료하려면 Ctrl+C\n")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
