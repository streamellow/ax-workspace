"""
Auth — Gmail OAuth2 인증 및 서비스 빌드 / Daum IMAP 연결
token.json 자동 갱신, credentials.json 없을 시 명확한 오류 메시지
"""

import os
import imaplib
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

TOKEN_PATH          = os.environ.get("TOKEN_PATH",          "token.json")
CREDS_PATH          = os.environ.get("CREDS_PATH",          "credentials.json")
CALENDAR_TOKEN_PATH = os.environ.get("CALENDAR_TOKEN_PATH", "calendar_token.json")


def get_gmail_service():
    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDS_PATH):
                raise FileNotFoundError(
                    f"credentials.json 파일이 없습니다 (경로: {CREDS_PATH})\n"
                    "Google Cloud Console > OAuth 2.0 클라이언트 ID > JSON 다운로드 후 저장하세요."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


DAUM_IMAP_HOST = "imap.daum.net"
DAUM_IMAP_PORT = 993


def get_calendar_service():
    creds = None

    if os.path.exists(CALENDAR_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(CALENDAR_TOKEN_PATH, CALENDAR_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDS_PATH):
                raise FileNotFoundError(
                    f"credentials.json 파일이 없습니다 (경로: {CREDS_PATH})\n"
                    "Google Cloud Console > OAuth 2.0 클라이언트 ID > JSON 다운로드 후 저장하세요."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, CALENDAR_SCOPES)
            creds = flow.run_local_server(port=0)

        with open(CALENDAR_TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def get_daum_imap() -> imaplib.IMAP4_SSL:
    email_addr = os.environ.get("DAUM_EMAIL", "")
    password   = os.environ.get("DAUM_PASSWORD", "")
    if not email_addr or not password:
        raise ValueError(
            ".env 파일에 DAUM_EMAIL과 DAUM_PASSWORD를 설정해주세요."
        )
    conn = imaplib.IMAP4_SSL(DAUM_IMAP_HOST, DAUM_IMAP_PORT)
    conn.login(email_addr, password)
    return conn