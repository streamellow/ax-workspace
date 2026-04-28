"""
home.py — Scheduly 홈 페이지 (Google Calendar 연동 + 자연어 일정 등록)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import json
import calendar
import datetime
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
load_dotenv(os.path.join(_ROOT, ".env"))

from auth import get_calendar_service, CALENDAR_TOKEN_PATH


# ── 자연어 파싱 ───────────────────────────────────────────────────────────────

def _parse_schedule_prompt(text: str, today: datetime.date) -> dict | None:
    prompt = f"""오늘 날짜는 {today.isoformat()}입니다.
다음 문장에서 일정 관련 의도와 정보를 추출해주세요.

문장: {text}

반드시 아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "intent": "create, move, delete 중 하나",
  "title": "일정 제목 (create일 때)",
  "date": "YYYY-MM-DD (create일 때 등록할 날짜)",
  "from_date": "YYYY-MM-DD (move일 때 기존 날짜)",
  "to_date": "YYYY-MM-DD (move일 때 이동할 날짜)",
  "target_date": "YYYY-MM-DD (delete일 때 삭제할 날짜)",
  "start_time": "HH:MM 또는 null",
  "end_time": "HH:MM 또는 null"
}}

규칙:
- intent: 새 일정 등록이면 "create", 기존 일정 이동이면 "move", 일정 삭제이면 "delete"
- create: title(간결하게), date(YYYY-MM-DD) 필수. 시간 없으면 start_time/end_time은 null
- move: from_date(기존 날짜), to_date(이동할 날짜) 필수. 나머지는 null 가능
- delete: target_date(삭제 대상 날짜) 필수. 나머지는 null 가능
- 날짜는 반드시 YYYY-MM-DD 형식"""

    response = OpenAI().chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=256,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        return json.loads(response.choices[0].message.content)
    except Exception:
        return None


# ── Google Calendar 이벤트 생성 ───────────────────────────────────────────────

def _create_calendar_event(service, title: str, date_str: str,
                            start_time: str | None, end_time: str | None) -> dict:
    if start_time:
        start = {"dateTime": f"{date_str}T{start_time}:00", "timeZone": "Asia/Seoul"}
        if end_time:
            end = {"dateTime": f"{date_str}T{end_time}:00", "timeZone": "Asia/Seoul"}
        else:
            h, m = map(int, start_time.split(":"))
            end_h = (h + 1) % 24
            end = {"dateTime": f"{date_str}T{end_h:02d}:{m:02d}:00", "timeZone": "Asia/Seoul"}
    else:
        next_day = (datetime.date.fromisoformat(date_str) + datetime.timedelta(days=1)).isoformat()
        start = {"date": date_str}
        end   = {"date": next_day}

    event = {"summary": title, "start": start, "end": end}
    return service.events().insert(calendarId="primary", body=event).execute()


# ── Google Calendar 단일 날짜 이벤트 조회 / 이동 ─────────────────────────────

def _fetch_day_events(service, date_str: str) -> list[dict]:
    """특정 날짜의 이벤트 목록 반환 (id·title·time·원본 start/end 포함)."""
    next_day = (datetime.date.fromisoformat(date_str) + datetime.timedelta(days=1)).isoformat()
    result = service.events().list(
        calendarId="primary",
        timeMin=f"{date_str}T00:00:00+09:00",
        timeMax=f"{next_day}T00:00:00+09:00",
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    events = []
    for ev in result.get("items", []):
        start     = ev.get("start", {})
        end       = ev.get("end", {})
        is_allday = "dateTime" not in start
        time_str  = "종일"
        if not is_allday:
            dt       = start.get("dateTime", "")
            time_str = dt[11:16] if len(dt) >= 16 else "종일"
        events.append({
            "id":       ev["id"],
            "title":    ev.get("summary", "(제목 없음)"),
            "time":     time_str,
            "is_allday": is_allday,
            "start":    start,
            "end":      end,
        })
    return events


def _do_move_event(service, event: dict, to_date: str) -> None:
    """기존 이벤트를 삭제하고 to_date 로 동일 일정을 새로 등록."""
    service.events().delete(calendarId="primary", eventId=event["id"]).execute()
    if event["is_allday"]:
        next_day = (datetime.date.fromisoformat(to_date) + datetime.timedelta(days=1)).isoformat()
        start = {"date": to_date}
        end   = {"date": next_day}
    else:
        tz          = event["start"].get("timeZone", "Asia/Seoul")
        time_part_s = event["start"]["dateTime"][10:]
        time_part_e = event["end"]["dateTime"][10:]
        start = {"dateTime": to_date + time_part_s, "timeZone": tz}
        end   = {"dateTime": to_date + time_part_e, "timeZone": tz}
    service.events().insert(
        calendarId="primary",
        body={"summary": event["title"], "start": start, "end": end},
    ).execute()


# ── Google Calendar 데이터 fetch ──────────────────────────────────────────────

def _fetch_month_events(service, year: int, month: int) -> dict[int, list[str]]:
    first = datetime.datetime(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    last = datetime.datetime(year, month, last_day, 23, 59, 59)

    result = service.events().list(
        calendarId="primary",
        timeMin=first.isoformat() + "Z",
        timeMax=last.isoformat() + "Z",
        singleEvents=True,
        orderBy="startTime",
        maxResults=200,
    ).execute()

    events_by_day: dict[int, list[str]] = {}
    for ev in result.get("items", []):
        start = ev.get("start", {})
        dt_str = start.get("dateTime") or start.get("date", "")
        if not dt_str:
            continue
        try:
            day = int(dt_str[8:10])
        except ValueError:
            continue
        title = ev.get("summary", "(제목 없음)")
        events_by_day.setdefault(day, []).append(title)

    return events_by_day


# ── HTML 캘린더 렌더링 ────────────────────────────────────────────────────────

_WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

_CSS = """
<style>
.sc-wrap{font-family:'Segoe UI',Arial,sans-serif;border-radius:16px;overflow:hidden;
  box-shadow:0 8px 32px rgba(79,70,229,.18);background:#fff;max-width:480px}
.sc-head{background:linear-gradient(135deg,#4f46e5,#7c3aed);padding:18px 20px}
.sc-head-title{color:#fff;font-size:1.15rem;font-weight:700}
.sc-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:0}
.sc-dow{text-align:center;padding:8px 2px;font-size:.7rem;font-weight:700;
  color:#94a3b8;background:#f8faff;border-bottom:1px solid #e2e8f0}
.sc-cell{min-height:68px;padding:4px 5px;border-right:1px solid #f1f5f9;
  border-bottom:1px solid #f1f5f9;vertical-align:top;background:#fff}
.sc-cell:nth-child(7n){border-right:none}
.sc-num{font-size:.8rem;font-weight:600;color:#475569;margin-bottom:3px}
.sc-today .sc-num{background:#4f46e5;color:#fff;border-radius:50%;
  width:22px;height:22px;display:flex;align-items:center;justify-content:center}
.sc-today{background:#f5f3ff}
.sc-ev{font-size:.65rem;background:#e0e7ff;color:#3730a3;border-radius:4px;
  padding:1px 4px;margin-bottom:2px;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;max-width:100%}
.sc-empty{background:#fafafa}
</style>
"""

def _render_calendar(year: int, month: int, today: datetime.date,
                     events_by_day: dict[int, list[str]]) -> str:
    month_name = datetime.date(year, month, 1).strftime("%B %Y")
    first_weekday, last_day = calendar.monthrange(year, month)
    first_col = (first_weekday + 1) % 7

    cells = []
    for _ in range(first_col):
        cells.append('<div class="sc-cell sc-empty"></div>')

    for day in range(1, last_day + 1):
        is_today = (year == today.year and month == today.month and day == today.day)
        cls = "sc-cell sc-today" if is_today else "sc-cell"
        num_html = f'<div class="sc-num">{day}</div>'
        evs = events_by_day.get(day, [])
        ev_html = "".join(
            f'<div class="sc-ev" title="{e}">{e}</div>' for e in evs[:3]
        )
        if len(evs) > 3:
            ev_html += f'<div class="sc-ev">+{len(evs)-3}개 더</div>'
        cells.append(f'<div class="{cls}">{num_html}{ev_html}</div>')

    dow_row = "".join(f'<div class="sc-dow">{d}</div>' for d in _WEEKDAYS)
    grid = dow_row + "".join(cells)

    return (
        f'{_CSS}'
        f'<div class="sc-wrap">'
        f'  <div class="sc-head"><span class="sc-head-title">📅 {month_name}</span></div>'
        f'  <div class="sc-grid">{grid}</div>'
        f'</div>'
    )


# ── 세션 상태 초기화 ──────────────────────────────────────────────────────────

today = datetime.date.today()
if "cal_year" not in st.session_state:
    st.session_state["cal_year"] = today.year
if "cal_month" not in st.session_state:
    st.session_state["cal_month"] = today.month


# ── 레이아웃 ──────────────────────────────────────────────────────────────────
col1, col2 = st.columns([1.1, 1], gap="large")

with col1:
    st.markdown(
        "<h1 style='font-size:2.6rem;font-weight:900;color:#1a1a2e;"
        "letter-spacing:-1px;margin-bottom:28px'>📅 Scheduly</h1>",
        unsafe_allow_html=True,
    )

    # ── 자연어 일정 입력 폼 ────────────────────────────────────────────────────
    with st.form("schedule_form", clear_on_submit=True):
        inp_col, btn_col = st.columns([6, 1])
        with inp_col:
            user_input = st.text_input(
                "일정 입력",
                placeholder="예) 0월 0일에 일정 등록 / 0월 0일 일정을 0월 0일로 옮겨줘",
                label_visibility="collapsed",
            )
        with btn_col:
            submitted = st.form_submit_button(
                "✔",
                use_container_width=True,
                type="primary",
            )

    # ── 이전 액션 결과 메시지 ────────────────────────────────────────────────
    if "home_msg" in st.session_state:
        _msg_type, _msg_text = st.session_state.pop("home_msg")
        if _msg_type == "success":
            st.success(_msg_text)
        else:
            st.error(_msg_text)

    if submitted and user_input.strip():
        connected = os.path.exists(CALENDAR_TOKEN_PATH)
        if not connected:
            st.warning("먼저 Google Calendar를 연동해주세요. (우측 캘린더 하단 연동 버튼)")
        else:
            with st.spinner("일정 분석 중..."):
                parsed = _parse_schedule_prompt(user_input, today)

            intent = (parsed or {}).get("intent", "create")

            # ── 일정 이동 ─────────────────────────────────────────────────────
            if intent == "move":
                from_date = (parsed or {}).get("from_date")
                to_date   = (parsed or {}).get("to_date")
                if not from_date or not to_date:
                    st.error("날짜를 인식하지 못했습니다. '○월 ○일 일정을 ○월 ○일로 옮겨줘' 형태로 입력해주세요.")
                else:
                    try:
                        svc        = get_calendar_service()
                        day_events = _fetch_day_events(svc, from_date)
                        if not day_events:
                            st.warning(f"**{from_date}** 에 등록된 일정이 없습니다.")
                        elif len(day_events) == 1:
                            _do_move_event(svc, day_events[0], to_date)
                            to_obj = datetime.date.fromisoformat(to_date)
                            st.session_state["cal_year"]  = to_obj.year
                            st.session_state["cal_month"] = to_obj.month
                            st.session_state["home_msg"]  = (
                                "success",
                                f"✅ **{day_events[0]['title']}** — {from_date} → {to_date} 이동 완료!",
                            )
                            st.rerun()
                        else:
                            st.session_state["pending_move"] = {
                                "from_date": from_date,
                                "to_date":   to_date,
                                "events":    day_events,
                            }
                            st.rerun()
                    except Exception as e:
                        st.error(f"일정 이동 실패: {e}")

            # ── 일정 삭제 ─────────────────────────────────────────────────────
            elif intent == "delete":
                target_date = (parsed or {}).get("target_date")
                if not target_date:
                    st.error("날짜를 인식하지 못했습니다. '○월 ○일 일정을 지워줘' 형태로 입력해주세요.")
                else:
                    try:
                        svc        = get_calendar_service()
                        day_events = _fetch_day_events(svc, target_date)
                        if not day_events:
                            st.warning(f"**{target_date}** 에 등록된 일정이 없습니다.")
                        elif len(day_events) == 1:
                            svc.events().delete(
                                calendarId="primary", eventId=day_events[0]["id"]
                            ).execute()
                            tgt_obj = datetime.date.fromisoformat(target_date)
                            st.session_state["cal_year"]  = tgt_obj.year
                            st.session_state["cal_month"] = tgt_obj.month
                            st.session_state["home_msg"]  = (
                                "success",
                                f"🗑 **{day_events[0]['title']}** ({target_date}) 삭제 완료!",
                            )
                            st.rerun()
                        else:
                            st.session_state["pending_delete"] = {
                                "target_date": target_date,
                                "events":      day_events,
                            }
                            st.rerun()
                    except Exception as e:
                        st.error(f"일정 삭제 실패: {e}")

            # ── 일정 등록 ─────────────────────────────────────────────────────
            else:
                if not parsed or not parsed.get("date") or not parsed.get("title"):
                    st.error("일정 정보를 인식하지 못했습니다. 날짜와 일정 내용을 포함해 다시 입력해주세요.")
                else:
                    title      = parsed["title"]
                    date_str   = parsed["date"]
                    start_time = parsed.get("start_time")
                    end_time   = parsed.get("end_time")

                    try:
                        svc = get_calendar_service()
                        _create_calendar_event(svc, title, date_str, start_time, end_time)

                        event_date = datetime.date.fromisoformat(date_str)
                        st.session_state["cal_year"]  = event_date.year
                        st.session_state["cal_month"] = event_date.month

                        time_label = f" {start_time}" if start_time else ""
                        st.success(f"✅ **{date_str}{time_label}** — **{title}** 등록 완료!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"일정 등록 실패: {e}")

    # ── 일정 이동 선택 UI (여러 일정이 있을 때) ───────────────────────────────
    if "pending_move" in st.session_state:
        pm = st.session_state["pending_move"]
        st.divider()
        st.markdown(
            f"**{pm['from_date']}** 에 일정이 **{len(pm['events'])}개** 있습니다.  \n"
            f"**{pm['to_date']}** 로 옮길 일정을 선택해주세요."
        )
        for idx, ev in enumerate(pm["events"]):
            ev_col, btn_col = st.columns([4, 1])
            ev_col.markdown(f"**{ev['title']}** · {ev['time']}")
            if btn_col.button("옮기기", key=f"move_ev_{idx}"):
                try:
                    svc    = get_calendar_service()
                    _do_move_event(svc, ev, pm["to_date"])
                    to_obj = datetime.date.fromisoformat(pm["to_date"])
                    st.session_state["cal_year"]  = to_obj.year
                    st.session_state["cal_month"] = to_obj.month
                    st.session_state["home_msg"]  = (
                        "success",
                        f"✅ **{ev['title']}** — {pm['from_date']} → {pm['to_date']} 이동 완료!",
                    )
                    st.session_state.pop("pending_move")
                    st.rerun()
                except Exception as exc:
                    st.error(f"이동 실패: {exc}")
        if st.button("취소", key="cancel_pending_move"):
            st.session_state.pop("pending_move")
            st.rerun()

    # ── 일정 삭제 선택 UI (여러 일정이 있을 때) ───────────────────────────────
    if "pending_delete" in st.session_state:
        pd_ = st.session_state["pending_delete"]
        st.divider()
        st.markdown(
            f"**{pd_['target_date']}** 에 일정이 **{len(pd_['events'])}개** 있습니다.  \n"
            "삭제할 일정을 선택해주세요."
        )
        for idx, ev in enumerate(pd_["events"]):
            ev_col, btn_col = st.columns([4, 1])
            ev_col.markdown(f"**{ev['title']}** · {ev['time']}")
            if btn_col.button("삭제", key=f"del_ev_{idx}"):
                try:
                    svc = get_calendar_service()
                    svc.events().delete(calendarId="primary", eventId=ev["id"]).execute()
                    tgt_obj = datetime.date.fromisoformat(pd_["target_date"])
                    st.session_state["cal_year"]  = tgt_obj.year
                    st.session_state["cal_month"] = tgt_obj.month
                    st.session_state["home_msg"]  = (
                        "success",
                        f"🗑 **{ev['title']}** ({pd_['target_date']}) 삭제 완료!",
                    )
                    st.session_state.pop("pending_delete")
                    st.rerun()
                except Exception as exc:
                    st.error(f"삭제 실패: {exc}")
        if st.button("취소", key="cancel_pending_delete"):
            st.session_state.pop("pending_delete")
            st.rerun()


# ── 오른쪽: Google Calendar ───────────────────────────────────────────────────
with col2:
    connected = os.path.exists(CALENDAR_TOKEN_PATH)

    if not connected:
        st.markdown(
            "<div style='border:2px dashed #c7d2fe;border-radius:16px;padding:36px 28px;"
            "text-align:center;background:#f5f3ff;margin-top:10px'>"
            "<div style='font-size:2.4rem;margin-bottom:12px'>📅</div>"
            "<div style='font-size:1.05rem;font-weight:700;color:#3730a3;margin-bottom:8px'>"
            "Google Calendar 연동</div>"
            "<div style='color:#64748b;font-size:0.88rem;line-height:1.6;margin-bottom:20px'>"
            "연동하면 오늘 일정이 캘린더에<br>바로 표시됩니다."
            "</div></div>",
            unsafe_allow_html=True,
        )
        if st.button("🔗 Google Calendar 연동하기", type="primary", use_container_width=True):
            with st.spinner("브라우저에서 Google 계정 인증을 완료해주세요..."):
                try:
                    get_calendar_service()
                    st.success("연동 완료!")
                    st.rerun()
                except FileNotFoundError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"연동 실패: {e}")

    else:
        year  = st.session_state["cal_year"]
        month = st.session_state["cal_month"]

        nav_l, nav_title, nav_r, nav_dis = st.columns([1, 3, 1, 2])
        with nav_l:
            if st.button("◀", key="cal_prev"):
                if month == 1:
                    st.session_state["cal_year"]  = year - 1
                    st.session_state["cal_month"] = 12
                else:
                    st.session_state["cal_month"] = month - 1
                st.rerun()
        with nav_title:
            st.markdown(
                f"<div style='text-align:center;font-weight:700;font-size:0.95rem;"
                f"color:#1a1a2e;padding-top:6px'>"
                f"{datetime.date(year, month, 1).strftime('%Y년 %m월')}</div>",
                unsafe_allow_html=True,
            )
        with nav_r:
            if st.button("▶", key="cal_next"):
                if month == 12:
                    st.session_state["cal_year"]  = year + 1
                    st.session_state["cal_month"] = 1
                else:
                    st.session_state["cal_month"] = month + 1
                st.rerun()
        with nav_dis:
            if st.button("연동 해제", key="cal_disconnect"):
                os.remove(CALENDAR_TOKEN_PATH)
                st.rerun()

        try:
            service = get_calendar_service()
            events_by_day = _fetch_month_events(service, year, month)
        except Exception as e:
            st.error(f"캘린더 불러오기 실패: {e}")
            events_by_day = {}

        cal_html = _render_calendar(year, month, today, events_by_day)
        st.markdown(cal_html, unsafe_allow_html=True)
