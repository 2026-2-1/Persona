from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SessionStatus = Literal["queued", "running", "succeeded", "technical_error", "cancelled"]


class CreateSession(BaseModel):
    model_config = ConfigDict(extra="forbid")
    persona_name: str = Field(default="첫 방문 사용자", min_length=1, max_length=80)
    task_id: Literal["T02"] = "T02"

    @field_validator("persona_name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("persona_name must not be blank")
        return value


class StepDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    step_no: int
    action: str
    url: str
    description: str
    status: Literal["succeeded", "technical_error"]
    created_at: datetime
    screenshot_before: str | None
    screenshot_after: str | None

    @field_validator("created_at")
    @classmethod
    def as_utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class SessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    persona_name: str
    task_id: Literal["T02"]
    status: SessionStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    steps_count: int = 0

    @field_validator("created_at", "started_at", "finished_at")
    @classmethod
    def as_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class SessionDetail(SessionSummary):
    steps: list[StepDetail] = Field(default_factory=list)
