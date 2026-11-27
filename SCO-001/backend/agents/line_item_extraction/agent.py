"""AG-03 line-item extraction (v1/F-06, TSD §4, §7).

Builds the segments, calls prompt ``line_item_extraction_chat`` on ``ENDPOINT_EXTRACT`` and turns
the raw answer into ``Candidate`` objects with resolved ``Source``s. A candidate whose quoted text
is not in its segment is dropped (rule C-01). Normalisation and selection follow in v1/F-07.

Never logs message text, element content or any model-supplied string (field names, segment ids,
values, quotes, computations, notes) (TSD §11.2); counts and durations only. ``dropped`` holds
the dropped texts for the caller only; its contents are never logged.
"""

import json
import logging
from dataclasses import dataclass
from typing import Literal, cast

from backend.agents.line_item_extraction.schema import (
    LineItemExtractionOutput,
    RawCandidate,
    RawLineItem,
)
from backend.config import Settings
from backend.constants import PIR_FIELDS, REQUEST_TYPE_LABELS, REQUEST_TYPES, SL_FIELDS
from backend.models import Attachment, Candidate, Message, Source
from backend.repositories.gateway_repository import CallMeta, GatewayRepository
from backend.services.source_locator import (
    Segment,
    build_segments,
    locate_element,
    locate_message,
    render_segments,
)

logger = logging.getLogger(__name__)

PROMPT_NAME = "line_item_extraction_chat"
NOT_PIR_SL = "not_pir_sl"
NO_EXTRACTION = "No extraction for not_pir_sl"
NOTHING_TO_EXTRACT = "Nothing to extract"
UNKNOWN_FIELD = "unknown field"


@dataclass
class DraftLine:
    doc_type: Literal["PIR", "SL"]
    action: Literal["create", "update"]
    candidates: dict[str, list[Candidate]]  # keys: subset of the field list of doc_type


@dataclass
class ExtractionDraft:
    lines: list[DraftLine]
    notes: list[str]
    dropped: list[str]  # "<segment_id>: <text>" (C-01) and "<field>: unknown field"; counts only
    meta: CallMeta  # the gateway's call metadata, passed through unchanged


def _normalise(text: str) -> str:
    return " ".join(text.split()).casefold()


@dataclass
class _Counts:
    kept: int = 0
    dropped: int = 0  # C-01: unknown segment or quote not found
    unknown_fields: int = 0
    lines_dropped: int = 0


class LineItemExtractionAgent:
    def __init__(self, gateway: GatewayRepository, settings: Settings) -> None:
        self._gateway = gateway
        self._settings = settings

    def run(
        self, messages: list[Message], attachments: list[Attachment], request_type: str
    ) -> ExtractionDraft:
        """Call prompt line_item_extraction_chat on ENDPOINT_EXTRACT; return raw lines with
        resolved candidates.

        Raises ValueError without a model call when request_type == 'not_pir_sl', when
        request_type is not one of REQUEST_TYPES, or when both messages and attachments are
        empty. ``UpstreamUnavailable`` from the gateway is propagated unchanged.
        """
        if request_type == NOT_PIR_SL:
            raise ValueError(NO_EXTRACTION)
        if request_type not in REQUEST_TYPES:
            raise ValueError("Unknown request type")
        if not messages and not attachments:
            raise ValueError(NOTHING_TO_EXTRACT)
        segments = build_segments(messages, attachments)
        variables = {
            "segments": render_segments(segments),
            "pir_fields": json.dumps(PIR_FIELDS),
            "sl_fields": json.dumps(SL_FIELDS),
            "request_type": REQUEST_TYPE_LABELS[request_type],
        }
        answer, meta = self._gateway.complete_json(
            PROMPT_NAME, self._settings.ENDPOINT_EXTRACT, variables, LineItemExtractionOutput
        )
        out = cast(LineItemExtractionOutput, answer)  # the gateway validated it against the schema

        resolver = _Resolver(segments, messages, attachments)
        dropped: list[str] = []
        counts = _Counts()
        lines: list[DraftLine] = []
        for raw_line in out.line_items:
            line = self._resolve_line(raw_line, resolver, dropped, counts)
            if line is None:
                counts.lines_dropped += 1
            else:
                lines.append(line)

        logger.info(
            "line item extraction done: segments=%d lines=%d lines_dropped=%d "
            "candidates_kept=%d candidates_dropped=%d unknown_fields=%d notes=%d "
            "latency_ms=%d retries=%d",
            len(segments),
            len(lines),
            counts.lines_dropped,
            counts.kept,
            counts.dropped,
            counts.unknown_fields,
            len(out.notes),
            meta.latency_ms,
            meta.retries,
        )
        return ExtractionDraft(lines=lines, notes=list(out.notes), dropped=dropped, meta=meta)

    @staticmethod
    def _resolve_line(
        raw_line: RawLineItem, resolver: "_Resolver", dropped: list[str], counts: _Counts
    ) -> DraftLine | None:
        allowed = PIR_FIELDS if raw_line.doc_type == "PIR" else SL_FIELDS
        candidates: dict[str, list[Candidate]] = {}
        for field_name, raw_candidates in raw_line.fields.items():
            if field_name not in allowed:
                dropped.append(f"{field_name}: {UNKNOWN_FIELD}")
                counts.unknown_fields += 1
                continue
            kept: list[Candidate] = []
            for raw in raw_candidates:
                source = resolver.source(raw)
                if source is None:  # rule C-01
                    dropped.append(f"{raw.segment_id}: {raw.text}")
                    counts.dropped += 1
                    continue
                kept.append(
                    Candidate(
                        value_raw=raw.value,
                        value_normalised=None,
                        derivation=raw.derivation,
                        computation=raw.computation,
                        source=source,
                        issue=None,
                    )
                )
            counts.kept += len(kept)
            if kept:
                candidates[field_name] = kept
        if not candidates:
            return None
        return DraftLine(doc_type=raw_line.doc_type, action=raw_line.action, candidates=candidates)


class _Resolver:
    """Resolves a raw candidate's segment and quote into a Source, or None (rule C-01)."""

    def __init__(
        self, segments: list[Segment], messages: list[Message], attachments: list[Attachment]
    ) -> None:
        self._by_id = {segment.segment_id: segment for segment in segments}
        self._texts = {message.message_id: message.text for message in messages}
        self._by_attachment = {attachment.attachment_id: attachment for attachment in attachments}

    def source(self, raw: RawCandidate) -> Source | None:
        segment = self._by_id.get(raw.segment_id)
        if segment is None:
            return None
        if segment.kind == "message":
            text = self._texts.get(segment.message_id or "")
            if text is None:
                return None
            span = locate_message(text, raw.text)
            if span is None:
                return None
            return Source(
                kind="message",
                message_id=segment.message_id,
                start=span[0],
                end=span[1],
                text=raw.text,
            )
        return self._element_source(raw, segment)

    def _element_source(self, raw: RawCandidate, segment: Segment) -> Source | None:
        needle = _normalise(raw.text)
        if not needle or needle not in _normalise(segment.content):
            return None
        attachment = self._by_attachment.get(segment.attachment_id or "")
        if attachment is None:
            return None
        for page in attachment.pages:
            if page.page_no != segment.page_no:
                continue
            for element in page.elements:
                if element.element_id == segment.segment_id:
                    return Source(
                        kind="attachment",
                        attachment_id=attachment.attachment_id,
                        page_no=page.page_no,
                        bbox=locate_element(page, element, raw.text),
                        text=raw.text,
                    )
        return None
