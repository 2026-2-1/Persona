from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


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
    explicit_scroll: Literal[False] = False
    max_steps: int = Field(default=30, gt=0)
    run_timeout_seconds: float = Field(default=300, gt=0)
    action_timeout_ms: int = Field(default=5000, gt=0)
    settle_timeout_ms: int = Field(default=3000, gt=0)
    max_llm_requests: int = Field(default=40, gt=0)
    max_total_tokens: int = Field(default=50000, gt=0)
    recent_step_count: int = Field(default=6, ge=0)
    repeated_state_action_limit: int = Field(default=3, gt=0)
    max_observation_text: int = Field(default=12000, gt=0)
    max_observation_elements: int = Field(default=100, gt=0)
    screenshot_input: Literal[False] = False
    enable_slow_loop: bool = False
    enable_wonder: bool = False
    reflection_every_actions: int = Field(default=5, gt=0)
    memory_limit: int = Field(default=8, gt=0)
    embedding_model: str | None = None
    model: str = "gpt-4o-mini"
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
    type: Literal["click", "type", "hover", "select", "navigate", "back", "switch_tab", "close_tab"]
    observation_id: str
    tab_id: str
    target_id: str | None = None
    text: str | None = None
    option_value: str | None = None
    url: str | None = None
    target_tab_id: str | None = None

    @model_validator(mode="after")
    def validate_fields(self):
        required = {"click": ["target_id"], "type": ["target_id", "text"], "hover": ["target_id"],
                    "select": ["target_id", "option_value"], "navigate": ["url"],
                    "switch_tab": ["target_tab_id"], "close_tab": ["target_tab_id"]}
        for key in required.get(self.type, []):
            if getattr(self, key) is None:
                raise ValueError(f"{key} is required for {self.type}")
        allowed={"click":{"target_id"},"type":{"target_id","text"},"hover":{"target_id"},
                 "select":{"target_id","option_value"},"navigate":{"url"},"back":set(),
                 "switch_tab":{"target_tab_id"},"close_tab":{"target_tab_id"}}
        fields={"target_id","text","option_value","url","target_tab_id"}
        supplied={key for key in fields if getattr(self,key) is not None}
        if supplied-allowed[self.type]:
            raise ValueError(f"fields {sorted(supplied-allowed[self.type])} are not allowed for {self.type}")
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


class MemoryEntry(StrictModel):
    memory_id: str
    seq: int
    run_id: str
    kind: Literal["observation", "plan", "action", "reflection", "wonder"]
    text: str
    source_step_ids: list[int] = Field(default_factory=list)
    source_observation_ids: list[str] = Field(default_factory=list)
    created_at: str
    created_monotonic_ms: int
    based_on_seq: int = 0
    importance: int | None = Field(default=None, ge=0, le=5)
    embedding_ref: str | None = None
    content_status: Literal["observed", "generated"] = "observed"
