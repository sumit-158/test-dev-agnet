"""Structured output of prompt ``request_triage_chat`` (v1/F-05).

Labels are built from ``backend.constants``; no label list is written here. The schema has no
free-form maps, so the gateway can send it as strict structured output (v1/F-03).
"""

from typing import Literal

from pydantic import BaseModel, Field

from backend.constants import MESSAGE_KINDS, REQUEST_TYPES

RequestTypeLabel = Literal[tuple(REQUEST_TYPES)]  # type: ignore[valid-type]
MessageKindLabel = Literal[tuple(MESSAGE_KINDS)]  # type: ignore[valid-type]

REASON_MAX_CHARS = 300


class Evidence(BaseModel):
    segment_id: str
    text: str


class RequestTriageOutput(BaseModel):
    request_type: RequestTypeLabel
    message_kind: MessageKindLabel
    reason: str = Field(max_length=REASON_MAX_CHARS)
    evidence: list[Evidence]
