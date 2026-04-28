"""
database.py — SQLite 연결 및 테이블 초기화
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

DATABASE_URL = "sqlite:///./schedule.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class Schedule(Base):
    __tablename__ = "schedules"

    id           = Column(Integer, primary_key=True, index=True)
    title        = Column(String(200), nullable=False)
    start_time   = Column(DateTime, nullable=False)
    end_time     = Column(DateTime, nullable=True)
    description  = Column(Text, nullable=True)
    is_completed = Column(Boolean, default=False, nullable=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
