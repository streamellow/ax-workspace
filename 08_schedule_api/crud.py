"""
crud.py — 일정 CRUD 비즈니스 로직
"""

from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from database import Schedule
from schemas import ScheduleCreate, ScheduleUpdate


def create_schedule(db: Session, data: ScheduleCreate) -> Schedule:
    schedule = Schedule(**data.model_dump())
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


def get_schedule(db: Session, schedule_id: int) -> Optional[Schedule]:
    return db.query(Schedule).filter(Schedule.id == schedule_id).first()


def get_schedules(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    is_completed: Optional[bool] = None,
    start_from: Optional[datetime] = None,
    start_until: Optional[datetime] = None,
) -> list[Schedule]:
    query = db.query(Schedule)

    filters = []
    if is_completed is not None:
        filters.append(Schedule.is_completed == is_completed)
    if start_from is not None:
        filters.append(Schedule.start_time >= start_from)
    if start_until is not None:
        filters.append(Schedule.start_time <= start_until)

    if filters:
        query = query.filter(and_(*filters))

    return query.order_by(Schedule.start_time).offset(skip).limit(limit).all()


def update_schedule(
    db: Session, schedule_id: int, data: ScheduleUpdate
) -> Optional[Schedule]:
    schedule = get_schedule(db, schedule_id)
    if not schedule:
        return None

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(schedule, field, value)

    db.commit()
    db.refresh(schedule)
    return schedule


def delete_schedule(db: Session, schedule_id: int) -> bool:
    schedule = get_schedule(db, schedule_id)
    if not schedule:
        return False
    db.delete(schedule)
    db.commit()
    return True


def complete_schedule(db: Session, schedule_id: int) -> Optional[Schedule]:
    schedule = get_schedule(db, schedule_id)
    if not schedule:
        return None
    schedule.is_completed = True
    db.commit()
    db.refresh(schedule)
    return schedule
