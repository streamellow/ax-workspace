"""
slack_tools.py — Slack 웹훅 메시지 전송 툴
"""

import requests


def send_slack_message(message: str, webhook_url: str) -> dict:
    if not webhook_url:
        return {"error": "SLACK_WEBHOOK_URL이 설정되지 않았습니다."}
    try:
        payload = {
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": message},
                }
            ]
        }
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        return {"success": True, "message": message[:100]}
    except Exception as e:
        return {"error": str(e)}
