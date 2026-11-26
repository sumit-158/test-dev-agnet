"""AG-02 request triage (v1/F-05, TSD §4, §11.1).

Builds the segments, calls prompt ``request_triage_chat`` on ``ENDPOINT_INTENT`` and resolves
the model's evidence into ``Source`` objects. Labels come from ``backend.constants``, the prompt
text from the prompt registry (via the gateway); the agent holds neither.

Never logs message text, element content or any model-supplied string (segment ids, evidence
text, reason, labels) (TSD §11.2); counts and durations only.
"""

import json
import logging
from dataclasses import dataclass
from typing import cast

from backend.agents.request_triage.schema import (
    Evidence,
    MessageKindLabel,
    RequestTriageOutput,
)
from backend.config import Settings
from backend.constants import REQUEST_TYPE_LABELS
from backend.models import Attachment, Message, RequestTypeResult, Source
from backend.repositories.gateway_repository import CallMeta, GatewayRepository
from backend.services.source_locator import (
    Segment,
    build_segments,
    locate_element,
    locate_message,
    render_segments,
)

logger = logging.getLogger(__name__)

PROMPT_NAME = "request_triage_chat"
NOTHING_TO_CLASSIFY = "Nothing to classify"


@dataclass
class TriageDecision:
    request_type: RequestTypeResult
    message_kind: MessageKindLabel
    meta: CallMeta  # the gateway's call metadata, passed through unchanged


def _normalise(text: str) -> str:
    return " ".join(text.split()).casefold()


class RequestTriageAgent:
    def __init__(self, gateway: GatewayRepository, settings: Settings) -> None:
        self._gateway = gateway
        self._settings = settings

    def run(
        self, messages: list[Message], attachments: list[Attachment], result_summary: str
    ) -> TriageDecision:
        """Build segments, call prompt request_triage_chat on ENDPOINT_INTENT, resolve evidence
        into Sources.

        result_summary is '' when no result exists, else 'Current result: <request_type label>,
        <n> line items: <line_no> <doc_type> <material>; ...'. It is built by the caller and
        passed to the prompt unchanged.

        Raises ValueError("Nothing to classify") without a model call when both messages and
        attachments are empty. A message with empty text (rendered ``M1: ``) or an attachment
        without elements still counts as input. ``UpstreamUnavailable`` from the gateway is
        propagated unchanged.
        """
        if not messages and not attachments:
            raise ValueError(NOTHING_TO_CLASSIFY)
        segments = build_segments(messages, attachments)
        variables = {
            "segments": render_segments(segments),
            "result_summary": result_summary,
            "request_type_labels": json.dumps(REQUEST_TYPE_LABELS),
        }
        answer, meta = self._gateway.complete_json(
            PROMPT_NAME, self._settings.ENDPOINT_INTENT, variables, RequestTriageOutput
        )
        out = cast(RequestTriageOutput, answer)  # the gateway validated it against the schema
        sources, unknown_segment, quote_not_found = self._resolve(
            out.evidence, segments, messages, attachments
        )
        logger.info(
            "request triage done: segments=%d evidence=%d sources=%d latency_ms=%d retries=%d",
            len(segments),
            len(out.evidence),
            len(sources),
            meta.latency_ms,
            meta.retries,
        )
        if unknown_segment or quote_not_found:
            logger.info(
                "triage evidence dropped=%d unknown_segment=%d quote_not_found=%d",
                unknown_segment + quote_not_found,
                unknown_segment,
                quote_not_found,
            )
        return TriageDecision(
            request_type=RequestTypeResult(
                value=out.request_type, reason=out.reason, sources=sources, corrected=False
            ),
            message_kind=out.message_kind,
            meta=meta,
        )

    @staticmethod
    def _resolve(
        evidence: list[Evidence],
        segments: list[Segment],
        messages: list[Message],
        attachments: list[Attachment],
    ) -> tuple[list[Source], int, int]:
        """Sources plus drop counts (unknown_segment, quote_not_found)."""
        by_id = {segment.segment_id: segment for segment in segments}
        texts = {message.message_id: message.text for message in messages}
        by_attachment = {attachment.attachment_id: attachment for attachment in attachments}
        sources: list[Source] = []
        unknown_segment = 0
        quote_not_found = 0
        for item in evidence:
            segment = by_id.get(item.segment_id)
            source: Source | None = None
            if segment is None:
                unknown_segment += 1
                continue
            if segment.kind == "message" and segment.message_id in texts:
                span = locate_message(texts[segment.message_id], item.text)
                if span is not None:
                    source = Source(
                        kind="message",
                        message_id=segment.message_id,
                        start=span[0],
                        end=span[1],
                        text=item.text,
                    )
            elif segment.kind == "element":
                source = RequestTriageAgent._element_source(item, segment, by_attachment)
            if source is None:
                quote_not_found += 1
                continue
            sources.append(source)
        return sources, unknown_segment, quote_not_found

    @staticmethod
    def _element_source(
        item: Evidence, segment: Segment, by_attachment: dict[str, Attachment]
    ) -> Source | None:
        needle = _normalise(item.text)
        if not needle or needle not in _normalise(segment.content):
            return None
        attachment = by_attachment.get(segment.attachment_id or "")
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
                        bbox=locate_element(page, element, item.text),
                        text=item.text,
                    )
        return None
