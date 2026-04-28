"""
tools/__init__.py — OpenAI tool 정의 + 실행 라우터
"""

from typing import Any

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_and_classify_emails",
            "description": "Gmail 또는 IMAP에서 이메일을 가져와 카테고리별(업무/비즈니스, 뉴스레터/마케팅 등)로 분류합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {"type": "integer", "description": "가져올 이메일 최대 수 (기본값 30)"},
                    "mail_source": {"type": "string", "enum": ["gmail", "daum"], "description": "메일 소스 (기본값 gmail)"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_business_emails",
            "description": "최근 fetch_and_classify_emails로 가져온 업무/비즈니스 이메일을 AI로 상세 요약합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_indices": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "요약할 업무 이메일 인덱스 목록 (0-based). 생략하면 전체 업무 메일을 요약합니다."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extract_and_store_job_postings",
            "description": "업무/비즈니스 및 뉴스레터 이메일에서 채용공고를 추출하여 벡터 DB와 SQLite에 저장합니다.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_jobs",
            "description": "저장된 채용공고를 쿼리로 하이브리드(벡터+키워드) 검색합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "검색 쿼리 (직무명, 기술 스택, 회사명 등)"},
                    "top_k": {"type": "integer", "description": "반환할 결과 수 (기본값 10)"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_resume",
            "description": "이력서 텍스트를 AI로 분석하여 적합 직무, 기술 스택, 강점, 경력 요약 등을 추출하고 DB에 저장합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "resume_text": {"type": "string", "description": "이력서 전문 텍스트"},
                    "resume_id": {"type": "string", "description": "이력서 식별자 (파일명 등)"}
                },
                "required": ["resume_text", "resume_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_calendar_events",
            "description": "Google Calendar에서 특정 날짜의 일정 목록을 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "조회할 날짜 (YYYY-MM-DD)"}
                },
                "required": ["date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": "Google Calendar에 새 일정을 등록합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "일정 제목"},
                    "date": {"type": "string", "description": "날짜 (YYYY-MM-DD)"},
                    "start_time": {"type": "string", "description": "시작 시간 HH:MM (종일 일정이면 생략)"},
                    "end_time": {"type": "string", "description": "종료 시간 HH:MM (생략 시 시작+1h)"},
                    "description": {"type": "string", "description": "일정 설명 (선택)"}
                },
                "required": ["title", "date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_calendar_event",
            "description": "Google Calendar에서 이벤트 ID로 일정을 삭제합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "삭제할 이벤트 ID"}
                },
                "required": ["event_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_calendar_event",
            "description": "Google Calendar 일정을 다른 날짜로 이동합니다 (시간은 유지).",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "이동할 이벤트 ID"},
                    "new_date": {"type": "string", "description": "이동할 날짜 (YYYY-MM-DD)"}
                },
                "required": ["event_id", "new_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_slack_message",
            "description": "Slack 웹훅으로 메시지를 전송합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "전송할 메시지 내용 (마크다운 지원)"}
                },
                "required": ["message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": "내부 벡터 DB(ChromaDB)에서 채용공고 또는 이력서를 의미 기반으로 검색합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "검색 쿼리"},
                    "collection": {"type": "string", "enum": ["job_postings", "resumes"], "description": "검색할 컬렉션"}
                },
                "required": ["query", "collection"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Tavily API를 사용해 인터넷에서 최신 정보를 검색합니다. 회사 정보, 채용 트렌드, 기술 정보 조사에 활용합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "검색할 내용"}
                },
                "required": ["query"]
            }
        }
    },
]


def execute_tool(tool_name: str, args: dict, context: dict) -> Any:
    """tool_name → 실제 함수 실행 라우터"""
    if tool_name == "fetch_and_classify_emails":
        from tools.email_tools import fetch_and_classify_emails
        return fetch_and_classify_emails(
            max_results=args.get("max_results", 30),
            mail_source=args.get("mail_source", context.get("mail_source", "gmail")),
            context=context,
        )
    elif tool_name == "summarize_business_emails":
        from tools.email_tools import summarize_business_emails
        return summarize_business_emails(
            email_indices=args.get("email_indices"),
            context=context,
        )
    elif tool_name == "extract_and_store_job_postings":
        from tools.email_tools import extract_and_store_job_postings
        return extract_and_store_job_postings(context=context)
    elif tool_name == "search_jobs":
        from tools.resume_tools import search_jobs
        return search_jobs(query=args["query"], top_k=args.get("top_k", 10))
    elif tool_name == "analyze_resume":
        from tools.resume_tools import analyze_resume
        return analyze_resume(
            resume_text=args["resume_text"],
            resume_id=args["resume_id"],
        )
    elif tool_name == "list_calendar_events":
        from tools.calendar_tools import list_calendar_events
        return list_calendar_events(date=args["date"])
    elif tool_name == "create_calendar_event":
        from tools.calendar_tools import create_calendar_event
        return create_calendar_event(
            title=args["title"],
            date=args["date"],
            start_time=args.get("start_time"),
            end_time=args.get("end_time"),
            description=args.get("description"),
        )
    elif tool_name == "delete_calendar_event":
        from tools.calendar_tools import delete_calendar_event
        return delete_calendar_event(event_id=args["event_id"])
    elif tool_name == "move_calendar_event":
        from tools.calendar_tools import move_calendar_event
        return move_calendar_event(event_id=args["event_id"], new_date=args["new_date"])
    elif tool_name == "send_slack_message":
        from tools.slack_tools import send_slack_message
        return send_slack_message(
            message=args["message"],
            webhook_url=context.get("slack_webhook_url", ""),
        )
    elif tool_name == "rag_search":
        from tools.search_tools import rag_search
        return rag_search(query=args["query"], collection=args["collection"])
    elif tool_name == "web_search":
        from tools.search_tools import web_search
        return web_search(query=args["query"])
    else:
        return {"error": f"Unknown tool: {tool_name}"}
