"""
google_auth.py — Gmail / Calendar OAuth2 인증 (Streamlit 의존성 없는 순수 백엔드 버전)
"""

import os
import imaplib
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

TOKEN_PATH = os.environ.get("TOKEN_PATH", "token.json")
CREDS_PATH = os.environ.get("CREDS_PATH", "credentials.json")
CALENDAR_TOKEN_PATH = os.environ.get("CALENDAR_TOKEN_PATH", "calendar_token.json")


def _load_creds(path: str, scopes: list) -> Credentials | None:
    if os.path.exists(path):
        return Credentials.from_authorized_user_file(path, scopes)
    return None


def get_gmail_service():
    creds = _load_creds(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDS_PATH):
                raise FileNotFoundError(
                    f"credentials.json 없음 (경로: {CREDS_PATH}). "
                    "Google Cloud Console에서 OAuth 2.0 클라이언트 ID JSON을 다운로드하세요."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def get_calendar_service():
    creds = _load_creds(CALENDAR_TOKEN_PATH, CALENDAR_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDS_PATH):
                raise FileNotFoundError(
                    f"credentials.json 없음 (경로: {CREDS_PATH}). "
                    "Google Cloud Console에서 OAuth 2.0 클라이언트 ID JSON을 다운로드하세요."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, CALENDAR_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(CALENDAR_TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


def get_daum_imap() -> imaplib.IMAP4_SSL:
    email_addr = os.environ.get("DAUM_EMAIL", "")
    password = os.environ.get("DAUM_PASSWORD", "")
    if not email_addr or not password:
        raise ValueError(".env에 DAUM_EMAIL과 DAUM_PASSWORD를 설정해주세요.")
    conn = imaplib.IMAP4_SSL("imap.daum.net", 993)
    conn.login(email_addr, password)
    return conn


def is_calendar_connected() -> bool:
    return os.path.exists(CALENDAR_TOKEN_PATH)
