"""
schemas.py — Pydantic 요청/응답 모델
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


class ScheduleCreate(BaseModel):
    title: str
    start_time: datetime
    end_time: Optional[datetime] = None
    description: Optional[str] = None
    is_completed: bool = False

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, end, info):
        start = info.data.get("start_time")
        if end and start and end <= start:
            raise ValueError("end_time은 start_time 이후여야 합니다.")
        return end


class ScheduleUpdate(BaseModel):
    title: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    description: Optional[str] = None
    is_completed: Optional[bool] = None


class ScheduleResponse(BaseModel):
    id: int
    title: str
    start_time: datetime
    end_time: Optional[datetime]
    description: Optional[str]
    is_completed: bool

    model_config = {"from_attributes": True}
