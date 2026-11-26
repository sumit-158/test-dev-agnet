"""Structured output of prompt ``line_item_extraction_chat`` (v1/F-06).

``RawLineItem.fields`` is a free-form map (field name -> candidates), so the gateway sends this
schema with ``strict: false`` (human-approved v1/F-03 behaviour). Field names are checked by the
agent against ``PIR_FIELDS`` / ``SL_FIELDS``, not here.
"""

from typing import Literal

from pydantic import BaseModel, Field


class RawCandidate(BaseModel):
    value: str
    segment_id: str
    text: str
    derivation: Literal["literal", "computed"] = "literal"
    computation: str | None = None


class RawLineItem(BaseModel):
    doc_type: Literal["PIR", "SL"]
    action: Literal["create", "update"]
    fields: dict[str, list[RawCandidate]]


class LineItemExtractionOutput(BaseModel):
    line_items: list[RawLineItem]
    notes: list[str] = Field(default_factory=list)
