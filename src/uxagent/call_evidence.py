"""Safe, local-only evidence fields for model API call records."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from .security import check_sensitive_input


_METHODS = {
    "perception": "perceive",
    "feedback": "feedback",
    "plan": "planning",
    "decision": "action",
    "reflection": "reflection",
    "wonder": "wonder",
    "importance": "importance",
    "questionnaire": "questionnaire",
}


def call_evidence(stage: str, messages, payload=None, response=None) -> dict:
    """Return reconstructible request evidence, suppressing credential-like content."""
    evidence = {
        "schema_version": "2.0",
        "call_id": f"call-{uuid.uuid4().hex}",
        "method_name": _METHODS.get(stage, stage),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "request": messages,
        "response": response,
    }
    source = payload if isinstance(payload, dict) else {}
    evidence["retrieve_result"] = source.get(
        "recent_memories", source.get("memories", []))
    try:
        check_sensitive_input({"request": evidence["request"], "response": response})
    except ValueError:
        evidence["request"] = "[redacted: sensitive input]"
        evidence["response"] = "[redacted: sensitive output]" if response is not None else None
        evidence["retrieve_result"] = "[redacted: sensitive input]"
        evidence["evidence_redacted"] = True
    return evidence
