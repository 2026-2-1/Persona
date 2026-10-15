from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CandidateReviewInput(StrictModel):
    """Client review payload; execution identity and audit fields are server-owned."""

    card_id: str = Field(strict=True, min_length=1, max_length=200)
    card_version: str = Field(strict=True, pattern=r"^[a-f0-9]{64}$")
    reviewer_id: str = Field(strict=True, min_length=1, max_length=200)
    verdict: Literal["valid", "invalid", "deferred", "tool_error", "environment_error"]
    note: str = Field(default="", strict=True, max_length=4000)

    @field_validator("card_id")
    @classmethod
    def nonblank_card_identity(cls, value: str):
        # Existing EvaluationCheck IDs allow Unicode and whitespace. IDs are
        # opaque equality keys, never filesystem paths, and must not be trimmed.
        if not value.strip():
            raise ValueError("card_id must not be blank")
        return value

    @field_validator("reviewer_id", "note")
    @classmethod
    def normalize_review_text(cls, value: str, info):
        value = value.strip()
        if info.field_name == "reviewer_id" and not value:
            raise ValueError("reviewer_id must not be blank")
        return value


class CandidateReviewRecord(CandidateReviewInput):
    schema_version: Literal["1.0"] = "1.0"
    review_id: str = Field(strict=True)
    run_id: str = Field(strict=True, min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    created_at: str = Field(strict=True)

    @field_validator("review_id")
    @classmethod
    def valid_review_uuid(cls, value: str):
        from uuid import UUID
        if str(UUID(value)) != value:
            raise ValueError("review_id must be a canonical UUID")
        return value

    @field_validator("created_at")
    @classmethod
    def utc_review_time(cls, value: str):
        from datetime import datetime, timedelta
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
            raise ValueError("created_at must be an ISO UTC timestamp")
        return value


class Viewport(StrictModel):
    width: int = Field(default=1440, gt=0)
    height: int = Field(default=900, gt=0)


class EvaluationCheck(StrictModel):
    id: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=200)
    kind: Literal['visible', 'text_contains', 'url_contains']
    selector: str | None = Field(default=None, min_length=1, max_length=1000)
    expected: str | None = Field(default=None, min_length=1, max_length=2000)

    @model_validator(mode='after')
    def check_fields(self):
        if self.kind == 'url_contains':
            if self.selector is not None or self.expected is None:
                raise ValueError('url_contains requires expected and forbids selector')
        elif self.selector is None:
            raise ValueError('DOM checks require selector')
        if self.kind == 'visible' and self.expected is not None:
            raise ValueError('visible forbids expected')
        if self.kind == 'text_contains' and self.expected is None:
            raise ValueError('text_contains requires expected')
        return self


class StudyConfig(StrictModel):
    schema_version: str = "1.0"
    study_id: str
    start_url: str
    task: str
    allowed_origins: list[str]
    persona_file: str = "configs/persona.json"
    evaluator_id: str = "local-bag-detail-v1"
    evaluation_checks: list[EvaluationCheck] = Field(default_factory=list, max_length=50)
    viewport: Viewport = Field(default_factory=Viewport)
    observation_policy: Literal["viewport"] = "viewport"
    source_kind: Literal["unknown", "synthetic_fixture", "live_configured"] = "unknown"
    explicit_scroll: bool = False
    max_steps: int = Field(default=30, gt=0)
    run_timeout_seconds: float = Field(default=300, gt=0)
    action_timeout_ms: int = Field(default=5000, gt=0)
    settle_timeout_ms: int = Field(default=3000, gt=0)
    max_llm_requests: int | None = Field(default=None, gt=0)
    max_total_tokens: int | None = Field(default=None, gt=0)
    recent_step_count: int = Field(default=6, ge=0)
    repeated_state_action_limit: int = Field(default=3, gt=0)
    max_observation_text: int = Field(default=12000, gt=0)
    max_observation_elements: int = Field(default=100, gt=0)
    screenshot_input: Literal[False] = False
    enable_slow_loop: bool = False
    enable_wonder: bool = False
    reflection_every_actions: int = Field(default=5, gt=0)
    memory_limit: int = Field(default=8, gt=0)
    max_active_memories: int = Field(default=64, ge=10, le=64)
    embedding_model: str | None = None
    model: str = "gpt-4o-mini"
    provider_model: str | None = None
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_output_tokens: int = Field(default=1200, gt=0)
    headed: bool = True

    @field_validator('evaluation_checks')
    @classmethod
    def unique_evaluation_ids(cls, checks):
        if len({check.id for check in checks}) != len(checks):
            raise ValueError('evaluation check IDs must be unique')
        return checks

    @field_validator("start_url")
    @classmethod
    def absolute_http_url(cls, value: str) -> str:
        from urllib.parse import urlsplit
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("start_url must be an absolute http(s) URL")
        return value

    @field_validator("allowed_origins")
    @classmethod
    def valid_origins(cls, values: list[str]) -> list[str]:
        from .security import normalize_origin
        normalized = [normalize_origin(value) for value in values]
        if not normalized:
            raise ValueError("allowed_origins must contain at least one origin")
        return list(dict.fromkeys(normalized))


class Persona(StrictModel):
    persona_id: str
    background: str
    digital_familiarity: str
    preferences: list[str]
    constraints: dict[str, Any] = Field(default_factory=dict)
    intent: str

    @field_validator("preferences")
    @classmethod
    def preferences_not_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("preferences must contain at least one item")
        return value


class ElementInfo(StrictModel):
    id: str
    role: str
    name: str
    enabled: bool = True
    value: str | None = None
    checked: bool | None = None
    focused: bool = False
    href: str | None = None
    options: list[dict[str, str]] = Field(default_factory=list)


class TabInfo(StrictModel):
    id: str
    title: str
    url: str
    active: bool


class CaptureInfo(StrictModel):
    policy: str = "viewport"
    truncated: bool = False
    omitted_element_count: int = 0
    screenshot_path: str | None = None
    unsupported: list[str] = Field(default_factory=list)


class Observation(StrictModel):
    schema_version: str = "1.0"
    observation_id: str
    tab_id: str
    url: str
    title: str
    html: str
    clickable_elements: list[ElementInfo] = Field(default_factory=list)
    input_elements: list[ElementInfo] = Field(default_factory=list)
    hoverable_elements: list[ElementInfo] = Field(default_factory=list)
    select_elements: list[ElementInfo] = Field(default_factory=list)
    tabs: list[TabInfo] = Field(default_factory=list)
    error: dict[str, Any] | None = None
    capture: CaptureInfo = Field(default_factory=CaptureInfo)


class Action(StrictModel):
    type: Literal["click", "type", "hover", "select", "keypress", "scroll", "navigate", "back", "switch_tab", "close_tab"]
    observation_id: str
    tab_id: str
    target_id: str | None = None
    text: str | None = None
    option_value: str | None = None
    url: str | None = None
    target_tab_id: str | None = None
    key: Literal["Enter", "Escape", "Tab", "ArrowUp", "ArrowDown", "Space"] | None = None
    scroll_y: int | None = Field(default=None, strict=True, ge=-900, le=900)
    input_mode: Literal["fill", "sequential"] | None = None

    @model_validator(mode="after")
    def validate_fields(self):
        required = {"click": ["target_id"], "type": ["target_id", "text"], "hover": ["target_id"],
                    "select": ["target_id", "option_value"], "keypress": ["target_id", "key"],
                    "scroll": ["scroll_y"], "navigate": ["url"],
                    "switch_tab": ["target_tab_id"], "close_tab": ["target_tab_id"]}
        for key in required.get(self.type, []):
            if getattr(self, key) is None:
                raise ValueError(f"{key} is required for {self.type}")
        allowed={"click":{"target_id"},"type":{"target_id","text","input_mode"},"hover":{"target_id"},
                 "select":{"target_id","option_value"},"keypress":{"target_id","key"},
                 "scroll":{"scroll_y"},"navigate":{"url"},"back":set(),
                 "switch_tab":{"target_tab_id"},"close_tab":{"target_tab_id"}}
        fields={"target_id","text","option_value","url","target_tab_id","key","scroll_y","input_mode"}
        supplied={key for key in fields if getattr(self,key) is not None}
        if supplied-allowed[self.type]:
            raise ValueError(f"fields {sorted(supplied-allowed[self.type])} are not allowed for {self.type}")
        if self.type == "scroll" and self.scroll_y == 0:
            raise ValueError("scroll_y must be nonzero")
        return self


class ActionResult(StrictModel):
    action_id: str
    observation_id: str
    ok: bool
    error: dict[str, str] | None = None
    url_before: str
    url_after: str
    elapsed_ms: int
    settled: bool = True
    tab_events: list[dict[str, str]] = Field(default_factory=list)


class Finish(StrictModel):
    claim: Literal["completed", "give_up"]
    summary: str


class AgentDecision(StrictModel):
    decision_id: str
    perception: str
    plan: str
    rationale_summary: str
    action: Action | None = None
    finish: Finish | None = None

    @model_validator(mode="after")
    def exactly_one_outcome(self):
        if (self.action is None) == (self.finish is None):
            raise ValueError("exactly one of action or finish is required")
        return self


class BrainStageRecord(StrictModel):
    """A generated stage result with links to the state used to produce it."""

    schema_version: Literal["1.0"] = "1.0"
    record_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    stage: Literal["perception", "plan", "decision", "importance", "reflection", "plan_review", "wonder"]
    observation_id: str | None = Field(default=None, min_length=1)
    plan_id: str | None = Field(default=None, min_length=1)
    plan_version: int | None = Field(default=None, ge=1)
    source_memory_ids: list[str] = Field(default_factory=list)
    snapshot_seq: int | None = Field(default=None, ge=0)
    text: str = Field(min_length=1)
    action: Action | None = None
    finish: Finish | None = None
    content_status: Literal["generated"] = "generated"
    recorded_at: datetime

    @model_validator(mode="after")
    def validate_provenance(self):
        if (self.plan_id is None) != (self.plan_version is None):
            raise ValueError("plan_id and plan_version must be provided together")
        if self.stage in ("perception", "plan", "decision", "plan_review") and self.observation_id is None:
            raise ValueError(f"observation_id is required for {self.stage}")
        if self.stage in ("plan", "decision", "plan_review") and self.plan_id is None:
            raise ValueError(f"plan_id and plan_version are required for {self.stage}")
        if self.stage == "decision":
            if (self.action is None) == (self.finish is None):
                raise ValueError("decision requires exactly one action or finish proposal")
            if self.action is not None and self.action.observation_id != self.observation_id:
                raise ValueError("proposed action must reference the decision observation")
        elif self.action is not None or self.finish is not None:
            raise ValueError("only decision stages may propose an action or finish")
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("recorded_at must include a time zone")
        return self


class BrainTaskEvent(StrictModel):
    """One append-only state change for a scheduled Slow Loop task."""

    schema_version: Literal["1.0"] = "1.0"
    event_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    kind: Literal["importance", "reflection", "plan_review", "wonder"]
    status: Literal["scheduled", "started", "skipped", "completed", "failed", "cancelled"]
    snapshot_seq: int = Field(ge=0)
    observation_id: str | None = Field(default=None, min_length=1)
    plan_id: str | None = Field(default=None, min_length=1)
    plan_version: int | None = Field(default=None, ge=1)
    source_memory_ids: list[str] = Field(default_factory=list)
    output_record_ids: list[str] = Field(default_factory=list)
    reason_code: str | None = Field(default=None, min_length=1)
    recorded_at: datetime

    @model_validator(mode="after")
    def validate_event(self):
        if (self.plan_id is None) != (self.plan_version is None):
            raise ValueError("plan_id and plan_version must be provided together")
        if self.kind == "plan_review" and (self.plan_id is None or self.observation_id is None):
            raise ValueError("plan_review requires plan and observation references")
        if self.status in ("failed", "cancelled", "skipped"):
            if self.reason_code is None:
                raise ValueError(f"{self.status} requires reason_code")
        elif self.reason_code is not None:
            raise ValueError(f"{self.status} must not have reason_code")
        if self.status != "completed" and self.output_record_ids:
            raise ValueError("only completed tasks may reference output records")
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("recorded_at must include a time zone")
        return self


class MemoryEntry(StrictModel):
    schema_version: Literal["1.0", "2.0"] = "1.0"
    memory_id: str
    seq: int = Field(ge=1)
    run_id: str
    kind: Literal["observation", "plan", "action", "reflection", "wonder"]
    text: str
    source_step_ids: list[int] = Field(default_factory=list)
    source_observation_ids: list[str] = Field(default_factory=list)
    source_memory_ids: list[str] = Field(default_factory=list)
    source_stage_record_id: str | None = Field(default=None, min_length=1)
    created_at: str
    created_monotonic_ms: int
    based_on_seq: int = 0
    importance: int | None = None
    embedding_ref: str | None = None
    content_status: Literal["observed", "generated"] = "observed"

    @model_validator(mode="after")
    def validate_importance_scale(self):
        if self.importance is not None:
            minimum, maximum = (0, 5) if self.schema_version == "1.0" else (1, 10)
            if not minimum <= self.importance <= maximum:
                raise ValueError(f"importance for memory schema {self.schema_version} must be {minimum}..{maximum}")
        return self


class MemoryChangeEvent(StrictModel):
    """An append-only importance update or active-memory eviction record."""

    schema_version: Literal["1.0"] = "1.0"
    event_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    memory_id: str = Field(min_length=1)
    memory_seq: int = Field(ge=1)
    change: Literal["importance_scored", "evicted"]
    importance_before: int | None = Field(default=None, ge=1, le=10)
    importance_after: int | None = Field(default=None, ge=1, le=10)
    retention_score: float | None = Field(default=None, ge=0, le=1)
    source_stage_record_id: str | None = Field(default=None, min_length=1)
    reason_code: str | None = Field(default=None, min_length=1)
    recorded_at: datetime

    @model_validator(mode="after")
    def validate_change(self):
        if self.change == "importance_scored":
            if self.importance_after is None or self.source_stage_record_id is None:
                raise ValueError("importance scoring requires a score and source stage")
            if self.retention_score is not None or self.reason_code is not None:
                raise ValueError("importance scoring cannot carry eviction fields")
        else:
            if self.retention_score is None or self.reason_code is None:
                raise ValueError("eviction requires a retention score and reason")
            if self.importance_after is not None:
                raise ValueError("eviction cannot set importance_after")
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("recorded_at must include a time zone")
        return self
