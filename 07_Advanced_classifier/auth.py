"""
Auth — Gmail OAuth2 인증 및 서비스 빌드
token.json 자동 갱신, credentials.json 없을 시 명확한 오류 메시지
"""

import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

TOKEN_PATH = os.environ.get("TOKEN_PATH", "token.json")
CREDS_PATH = os.environ.get("CREDS_PATH", "credentials.json")


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