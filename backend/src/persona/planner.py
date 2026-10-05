from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class BrowserAction:
    kind: Literal["click"]
    selector: str
    description: str


class ActionProvider(Protocol):
    def actions(self, persona_name: str, task_id: str) -> list[BrowserAction]: ...


class MockActionProvider:
    """Deterministic setup fixture; persona names are labels, not a behavioral model."""

    def actions(self, persona_name: str, task_id: str) -> list[BrowserAction]:
        if task_id != "T02":
            raise ValueError("Only the local T02 fixture is implemented")
        return [BrowserAction("click", "#show-info", "상품 상세 정보 펼치기")]
