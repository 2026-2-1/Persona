import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

STATUSES = ("queued", "running", "succeeded", "technical_error", "cancelled")
TERMINAL_STATUSES = frozenset({"succeeded", "technical_error", "cancelled"})


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','succeeded','technical_error','cancelled')",
            name="ck_sessions_status",
        ),
        CheckConstraint("task_id = 'T02'", name="ck_sessions_task"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    persona_name: Mapped[str] = mapped_column(String(80))
    task_id: Mapped[str] = mapped_column(String(20), default="T02")
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    steps: Mapped[list["Step"]] = relationship(
        back_populates="session", order_by="Step.step_no", cascade="all, delete-orphan"
    )


class Step(Base):
    __tablename__ = "steps"
    __table_args__ = (
        UniqueConstraint("session_id", "step_no", name="uq_steps_session_number"),
        CheckConstraint("step_no > 0", name="ck_steps_number"),
        CheckConstraint("status IN ('succeeded','technical_error')", name="ck_steps_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    step_no: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(40))
    url: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    screenshot_before: Mapped[str | None] = mapped_column(Text)
    screenshot_after: Mapped[str | None] = mapped_column(Text)
    session: Mapped[Session] = relationship(back_populates="steps")
