"""
main.py — FastAPI 앱 진입점 및 라우터
"""

from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import init_db, get_db
from schemas import ScheduleCreate, ScheduleUpdate, ScheduleResponse
import crud

app = FastAPI(title="개인 일정 관리 API", version="1.0.0")


@app.on_event("startup")
def startup():
    init_db()


# ── 일정 생성 ────────────────────────────────────────────────────────────────
@app.post("/schedules", response_model=ScheduleResponse, status_code=201)
def create_schedule(data: ScheduleCreate, db: Session = Depends(get_db)):
    return crud.create_schedule(db, data)


# ── 일정 목록 조회 ────────────────────────────────────────────────────────────
@app.get("/schedules", response_model=list[ScheduleResponse])
def list_schedules(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    is_completed: Optional[bool] = Query(None),
    start_from: Optional[datetime] = Query(None),
    start_until: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
):
    return crud.get_schedules(db, skip, limit, is_completed, start_from, start_until)


# ── 단건 조회 ────────────────────────────────────────────────────────────────
@app.get("/schedules/{schedule_id}", response_model=ScheduleResponse)
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    schedule = crud.get_schedule(db, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다.")
    return schedule


# ── 일정 수정 ────────────────────────────────────────────────────────────────
@app.patch("/schedules/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(
    schedule_id: int, data: ScheduleUpdate, db: Session = Depends(get_db)
):
    schedule = crud.update_schedule(db, schedule_id, data)
    if not schedule:
        raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다.")
    return schedule


# ── 완료 처리 ────────────────────────────────────────────────────────────────
@app.patch("/schedules/{schedule_id}/complete", response_model=ScheduleResponse)
def complete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    schedule = crud.complete_schedule(db, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다.")
    return schedule


# ── 일정 삭제 ────────────────────────────────────────────────────────────────
@app.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    deleted = crud.delete_schedule(db, schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다.")
