"""
calendar_tools.py — Google Calendar CRUD 툴
"""

from datetime import datetime, timedelta, timezone


def list_calendar_events(date: str) -> dict:
    from core.google_auth import get_calendar_service

    try:
        service = get_calendar_service()
    except Exception as e:
        return {"error": str(e), "events": []}

    try:
        day_start = datetime.fromisoformat(date).replace(
            hour=0, minute=0, second=0, tzinfo=timezone.utc
        )
        day_end = day_start + timedelta(days=1)
        result = service.events().list(
            calendarId="primary",
            timeMin=day_start.isoformat(),
            timeMax=day_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = result.get("items", [])
        return {
            "date": date,
            "count": len(events),
            "events": [
                {
                    "id": e["id"],
                    "title": e.get("summary", "(제목 없음)"),
                    "start": e["start"].get("dateTime", e["start"].get("date")),
                    "end": e["end"].get("dateTime", e["end"].get("date")),
                    "description": e.get("description", ""),
                }
                for e in events
            ],
        }
    except Exception as e:
        return {"error": str(e), "events": []}


def create_calendar_event(
    title: str,
    date: str,
    start_time: str | None = None,
    end_time: str | None = None,
    description: str | None = None,
) -> dict:
    from core.google_auth import get_calendar_service

    try:
        service = get_calendar_service()
    except Exception as e:
        return {"error": str(e)}

    try:
        if start_time:
            start_dt = datetime.fromisoformat(f"{date}T{start_time}:00")
            if end_time:
                end_dt = datetime.fromisoformat(f"{date}T{end_time}:00")
            else:
                end_dt = start_dt + timedelta(hours=1)
            event_body = {
                "summary": title,
                "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Seoul"},
                "end":   {"dateTime": end_dt.isoformat(),   "timeZone": "Asia/Seoul"},
            }
        else:
            event_body = {
                "summary": title,
                "start": {"date": date},
                "end":   {"date": date},
            }
        if description:
            event_body["description"] = description

        created = service.events().insert(calendarId="primary", body=event_body).execute()
        return {
            "success": True,
            "event_id": created["id"],
            "title": title,
            "date": date,
            "start_time": start_time,
            "end_time": end_time,
        }
    except Exception as e:
        return {"error": str(e)}


def delete_calendar_event(event_id: str) -> dict:
    from core.google_auth import get_calendar_service

    try:
        service = get_calendar_service()
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return {"success": True, "event_id": event_id}
    except Exception as e:
        return {"error": str(e)}


def get_month_calendar_events(year: int, month: int) -> dict:
    import calendar as cal_module
    from core.google_auth import get_calendar_service

    try:
        service = get_calendar_service()
    except Exception as e:
        return {"error": str(e), "events": []}

    try:
        start_dt = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
        last_day = cal_module.monthrange(year, month)[1]
        end_dt = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)

        result = service.events().list(
            calendarId="primary",
            timeMin=start_dt.isoformat(),
            timeMax=end_dt.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=200,
        ).execute()
        events = result.get("items", [])
        return {
            "year": year,
            "month": month,
            "count": len(events),
            "events": [
                {
                    "id": e["id"],
                    "title": e.get("summary", "(제목 없음)"),
                    "start": e["start"].get("dateTime", e["start"].get("date")),
                    "end": e["end"].get("dateTime", e["end"].get("date")),
                    "description": e.get("description", ""),
                }
                for e in events
            ],
        }
    except Exception as e:
        return {"error": str(e), "events": []}


def move_calendar_event(event_id: str, new_date: str) -> dict:
    from core.google_auth import get_calendar_service

    try:
        service = get_calendar_service()
        event = service.events().get(calendarId="primary", eventId=event_id).execute()

        start = event.get("start", {})
        end   = event.get("end", {})

        if "dateTime" in start:
            old_start = datetime.fromisoformat(start["dateTime"])
            old_end   = datetime.fromisoformat(end["dateTime"])
            duration  = old_end - old_start
            new_start = old_start.replace(
                year=int(new_date[:4]),
                month=int(new_date[5:7]),
                day=int(new_date[8:10]),
            )
            new_end = new_start + duration
            event["start"] = {"dateTime": new_start.isoformat(), "timeZone": start.get("timeZone", "Asia/Seoul")}
            event["end"]   = {"dateTime": new_end.isoformat(),   "timeZone": end.get("timeZone",   "Asia/Seoul")}
        else:
            event["start"] = {"date": new_date}
            event["end"]   = {"date": new_date}

        updated = service.events().update(
            calendarId="primary", eventId=event_id, body=event
        ).execute()
        return {
            "success": True,
            "event_id": event_id,
            "new_date": new_date,
            "title": updated.get("summary", ""),
        }
    except Exception as e:
        return {"error": str(e)}
