"""
agent.py — OpenAI tool-calling ReAct 루프 (Single Agent)
"""

import json
import os
from datetime import datetime, timezone, timedelta
from openai import OpenAI
from tools import TOOL_DEFINITIONS, execute_tool
from core.schemas import ChatResponse

_KST = timezone(timedelta(hours=9))

MAX_ITERATIONS = 10

_SYSTEM_PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "prompts", "system_prompt.txt"
)

def _load_system_prompt() -> str:
    try:
        with open(_SYSTEM_PROMPT_PATH, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "당신은 이메일, 채용공고, 이력서, 캘린더 관리를 돕는 AI 어시스턴트입니다."


# in-memory session cache: session_id → context dict
_SESSION_CACHE: dict[str, dict] = {}


def _get_context(session_id: str, initial_context: dict) -> dict:
    if session_id not in _SESSION_CACHE:
        _SESSION_CACHE[session_id] = {}
    ctx = _SESSION_CACHE[session_id]
    for k, v in initial_context.items():
        if k not in ctx:
            ctx[k] = v
    return ctx


def run_agent(message: str, history: list[dict], context: dict) -> ChatResponse:
    client = OpenAI()
    today_str = datetime.now(_KST).strftime("%Y년 %m월 %d일 (%A)")
    system_prompt = f"오늘 날짜: {today_str}\n연도가 명시되지 않은 날짜는 오늘 기준 가장 가까운 미래 또는 현재 연도({datetime.now(_KST).year})로 해석하세요.\n\n" + _load_system_prompt()

    session_id = context.get("session_id", "default")
    ctx = _get_context(session_id, context)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    tool_calls_log: list[dict] = []
    reply = ""

    for iteration in range(MAX_ITERATIONS):
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
        )

        choice = response.choices[0]
        msg = choice.message

        if choice.finish_reason == "tool_calls" and msg.tool_calls:
            messages.append(msg)

            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                tool_calls_log.append({"tool": tool_name, "args": args})

                result = execute_tool(tool_name, args, ctx)
                result_str = json.dumps(result, ensure_ascii=False, default=str)

                tool_calls_log[-1]["result_preview"] = result_str[:200]

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str,
                })

        elif choice.finish_reason == "stop":
            reply = msg.content or ""
            break

        else:
            reply = msg.content or "처리 중 오류가 발생했습니다."
            break
    else:
        reply = f"최대 반복 횟수({MAX_ITERATIONS})에 도달했습니다. 지금까지의 정보를 바탕으로 답변합니다."
        final = client.chat.completions.create(
            model="gpt-4o",
            messages=messages + [{"role": "user", "content": "지금까지 수집한 정보를 바탕으로 최종 답변을 제공해주세요."}],
        )
        reply = final.choices[0].message.content or reply

    data = _build_data(ctx)

    return ChatResponse(
        reply=reply,
        complete=True,
        tool_calls_log=tool_calls_log,
        data=data,
    )


def _build_data(ctx: dict) -> dict:
    data: dict = {}

    emails = ctx.get("_emails", [])
    classifications = ctx.get("_classifications", [])
    if emails and classifications:
        data["emails"] = [
            {
                "index": i,
                "subject": e.subject,
                "sender": e.sender,
                "date": e.date,
                "category": next(
                    (c.category for c in classifications if c.index == i + 1), "기타"
                ),
                "summary": next(
                    (c.summary for c in classifications if c.index == i + 1), ""
                ),
            }
            for i, e in enumerate(emails)
        ]

    return data
