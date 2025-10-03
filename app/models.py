from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, Text, Enum
from typing import Optional
import enum
import uuid

class Base(DeclarativeBase): pass

class Urgency(str, enum.Enum):
    none = "none"; low = "low"; normal = "normal"; high = "high"; critical = "critical"

class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text())
    urgency: Mapped[Urgency] = mapped_column(Enum(Urgency), default=Urgency.normal)
    due_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # ISO date YYYY-MM-DD
    status: Mapped[str] = mapped_column(String(16), default="printed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    printed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    print_job_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    archive_pdf_path: Mapped[str] = mapped_column(Text())
    archive_json_path: Mapped[str] = mapped_column(Text())
    hash: Mapped[str] = mapped_column(String(64))
    author: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
