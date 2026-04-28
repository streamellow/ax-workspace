"""
utils.py — 공유 유틸리티 (API 호출, 인증 헬퍼)
"""

import os
import requests
import streamlit as st


def backend_url() -> str:
    try:
        return st.secrets.get("BACKEND_URL", "http://localhost:8000")
    except Exception:
        return os.environ.get("BACKEND_URL", "http://localhost:8000")


def api_headers() -> dict:
    return {"Authorization": f"Bearer {st.session_state.get('token', '')}"}


def login(username: str, password: str) -> str | None:
    try:
        resp = requests.post(
            f"{backend_url()}/auth/login",
            json={"username": username, "password": password},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()["access_token"]
    except Exception:
        pass
    return None


def chat(message: str, history: list | None = None, context: dict | None = None) -> dict:
    resp = requests.post(
        f"{backend_url()}/chat",
        json={"message": message, "history": history or [], "context": context or {}},
        headers=api_headers(),
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def get_month_events(year: int, month: int) -> list:
    try:
        resp = requests.get(
            f"{backend_url()}/calendar/month",
            params={"year": year, "month": month},
            headers=api_headers(),
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("events", [])
    except Exception:
        pass
    return []


def secret(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, default)
    except Exception:
        return os.environ.get(key, default)
