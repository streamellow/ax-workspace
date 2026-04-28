"""
Auth — Gmail OAuth2 인증 및 서비스 빌드 / Daum IMAP 연결
token.json 자동 갱신, credentials.json 없을 시 Streamlit Secrets에서 로드
"""

import os
import json
import imaplib
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES          = ["https://www.googleapis.com/auth/gmail.readonly"]
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

TOKEN_PATH          = os.environ.get("TOKEN_PATH",          "token.json")
CREDS_PATH          = os.environ.get("CREDS_PATH",          "credentials.json")
CALENDAR_TOKEN_PATH = os.environ.get("CALENDAR_TOKEN_PATH", "calendar_token.json")


def _secret(key: str) -> dict | None:
    """Streamlit secrets에서 JSON 내용을 로드 (클라우드 배포용)"""
    try:
        import streamlit as st
        if key in st.secrets:
            return json.loads(st.secrets[key]["content"])
    except Exception:
        pass
    return None


def _load_token(path: str, scopes: list, secret_key: str) -> Credentials | None:
    if os.path.exists(path):
        return Credentials.from_authorized_user_file(path, scopes)
    data = _secret(secret_key)
    if data:
        return Credentials.from_authorized_user_info(data, scopes)
    return None


def get_gmail_service():
    creds = _load_token(TOKEN_PATH, SCOPES, "gmail_token")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_config = _secret("google_credentials")
            if client_config:
                flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            elif os.path.exists(CREDS_PATH):
                flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
            else:
                raise FileNotFoundError(
                    f"credentials.json 파일이 없습니다 (경로: {CREDS_PATH})\n"
                    "Google Cloud Console > OAuth 2.0 클라이언트 ID > JSON 다운로드 후 저장하세요."
                )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def get_calendar_service():
    creds = _load_token(CALENDAR_TOKEN_PATH, CALENDAR_SCOPES, "calendar_token")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_config = _secret("google_credentials")
            if client_config:
                flow = InstalledAppFlow.from_client_config(client_config, CALENDAR_SCOPES)
            elif os.path.exists(CREDS_PATH):
                flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, CALENDAR_SCOPES)
            else:
                raise FileNotFoundError(
                    f"credentials.json 파일이 없습니다 (경로: {CREDS_PATH})\n"
                    "Google Cloud Console > OAuth 2.0 클라이언트 ID > JSON 다운로드 후 저장하세요."
                )
            creds = flow.run_local_server(port=0)

        with open(CALENDAR_TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


DAUM_IMAP_HOST = "imap.daum.net"
DAUM_IMAP_PORT = 993


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
