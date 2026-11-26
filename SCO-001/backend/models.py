"""In-memory domain models (TSD §5.2) — the names every feature uses."""

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from backend.constants import PIR_FIELDS, SL_FIELDS

BBox = tuple[float, float, float, float]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _uuid4() -> str:
    return str(uuid.uuid4())


class ChangedField(BaseModel):
    line_no: int | None = None
    field: str
    old_value: str | None = None
    new_value: str | None = None


class Message(BaseModel):
    message_id: str
    role: Literal["user", "assistant"]
    text: str
    attachment_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utc_now)
    changed_fields: list[ChangedField] = Field(default_factory=list)
    clarification: bool = False


class Element(BaseModel):
    element_id: str
    type: str
    content: str
    bbox: BBox


class Word(BaseModel):
    text: str
    bbox: BBox


class Page(BaseModel):
    page_no: int
    image_path: str = ""
    width_px: int
    height_px: int
    elements: list[Element] = Field(default_factory=list)
    words: list[Word] = Field(default_factory=list)


class Attachment(BaseModel):
    attachment_id: str
    file_name: str
    media_type: str
    size_bytes: int = 0
    pages: list[Page] = Field(default_factory=list)
    parse_status: Literal["pending", "parsed", "failed"] = "pending"
    error: str | None = None


class Source(BaseModel):
    kind: Literal["message", "attachment", "user_edit"]
    message_id: str | None = None
    start: int | None = None
    end: int | None = None
    attachment_id: str | None = None
    page_no: int | None = None
    bbox: BBox | None = None
    text: str


class Candidate(BaseModel):
    value_raw: str
    value_normalised: str | None = None
    derivation: Literal["literal", "computed"] = "literal"
    computation: str | None = None
    source: Source
    issue: str | None = None


class FieldValue(BaseModel):
    value: str | None = None
    status: Literal["found", "missing", "conflict", "corrected", "rejected"]
    derivation: Literal["literal", "computed"] = "literal"
    computation: str | None = None
    sources: list[Source] = Field(default_factory=list)
    candidates: list[Candidate] = Field(default_factory=list)
    issue: str | None = None


class LineItem(BaseModel):
    line_no: int
    line_id: str = Field(default_factory=_uuid4)
    doc_type: Literal["PIR", "SL"]
    action: Literal["create", "update"]
    fields: dict[str, FieldValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_field_names(self) -> "LineItem":
        allowed = PIR_FIELDS if self.doc_type == "PIR" else SL_FIELDS
        for name in self.fields:
            if name not in allowed:
                raise ValueError(f"Unknown field {name} for {self.doc_type}")
        return self


class RequestTypeResult(BaseModel):
    value: Literal[
        "create_pir", "update_pir", "create_sl", "update_sl", "create_pir_and_sl", "not_pir_sl"
    ]
    reason: str
    sources: list[Source] = Field(default_factory=list)
    corrected: bool = False


class Result(BaseModel):
    request_type: RequestTypeResult
    line_items: list[LineItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=_utc_now)


class Session(BaseModel):
    session_id: str = Field(default_factory=_uuid4)
    created_at: datetime = Field(default_factory=_utc_now)
    last_seen_at: datetime = Field(default_factory=_utc_now)
    messages: list[Message] = Field(default_factory=list)
    attachments: list[Attachment] = Field(default_factory=list)
    result: Result | None = None
    extraction_status: Literal["idle", "extracting", "ready", "failed"] = "idle"
    error: str | None = None
