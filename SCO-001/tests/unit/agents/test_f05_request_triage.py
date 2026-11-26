"""v1/F-05 — AG-02 request triage (fake gateway only; no model calls)."""

import inspect
import json
import logging
import typing
from typing import Any

import pytest

from backend.agents.request_triage.agent import RequestTriageAgent, TriageDecision
from backend.agents.request_triage.schema import Evidence, RequestTriageOutput
from backend.config import Settings
from backend.constants import MESSAGE_KINDS, REQUEST_TYPE_LABELS, REQUEST_TYPES
from backend.errors import UpstreamUnavailable
from backend.models import Message, Source, Word
from backend.repositories.gateway_repository import (
    CallMeta,
    GatewayRepository,
    has_free_form_map,
    strict_json_schema,
)

PROMPT = "request_triage_chat"
CORRECTION_TEXT = "line 2 amount is 8000"
SUMMARY = "Current result: Update PIR, 2 line items: 1 PIR 1038-967-34; 2 PIR 1038-967-04"


def _answer(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "request_type": "update_pir",
        "message_kind": "request_content",
        "reason": "r",
        "evidence": [],
    }
    payload.update(overrides)
    return payload


# --- acceptance criteria ---------------------------------------------------------------------


def test_f05_ac1_golden_triage(
    settings, fake_gateway, golden_messages, golden_attachment, golden_triage_output
):
    fake_gateway.responses = {PROMPT: [golden_triage_output]}
    decision = RequestTriageAgent(fake_gateway, settings).run(
        golden_messages, [golden_attachment], ""
    )

    assert isinstance(decision, TriageDecision)
    rt = decision.request_type
    assert rt.value == "update_pir"
    assert rt.reason == "The message asks to update PIR data for two parts"
    assert rt.corrected is False
    assert rt.sources[0].kind == "message"
    assert golden_messages[0].text[rt.sources[0].start : rt.sources[0].end] == "update PIR data"
    assert rt.sources == [
        Source(kind="message", message_id="M1", start=10, end=25, text="update PIR data")
    ]
    assert decision.message_kind == "request_content"
    assert decision.meta.prompt_name == PROMPT

    assert len(fake_gateway.calls) == 1
    call = fake_gateway.calls[0]
    assert call.prompt_name == PROMPT
    assert call.endpoint == "sco_001_intent"
    assert call.variables["result_summary"] == ""


def test_f05_ac2_correction_kind(settings, fake_gateway, golden_messages):
    messages = [*golden_messages, Message(message_id="M2", role="user", text=CORRECTION_TEXT)]
    fake_gateway.responses = {
        PROMPT: [
            _answer(
                message_kind="correction", evidence=[{"segment_id": "M2", "text": "amount is 8000"}]
            )
        ]
    }
    decision = RequestTriageAgent(fake_gateway, settings).run(messages, [], SUMMARY)

    assert decision.message_kind == "correction"
    assert decision.request_type.value == "update_pir"
    variables = fake_gateway.calls[0].variables
    assert f"M2: {CORRECTION_TEXT}" in variables["segments"].splitlines()
    assert variables["result_summary"] == SUMMARY
    src = decision.request_type.sources[0]
    assert (src.message_id, CORRECTION_TEXT[src.start : src.end]) == ("M2", "amount is 8000")


def test_f05_ac3_nothing_to_classify(settings, fake_gateway):
    with pytest.raises(ValueError, match=r"^Nothing to classify$"):
        RequestTriageAgent(fake_gateway, settings).run([], [], "")
    assert fake_gateway.calls == []


def test_f05_ac4_unknown_evidence_dropped(
    settings, fake_gateway, golden_messages, golden_attachment
):
    fake_gateway.responses = {PROMPT: [_answer(evidence=[{"segment_id": "A9.p1.e1", "text": "x"}])]}
    decision = RequestTriageAgent(fake_gateway, settings).run(
        golden_messages, [golden_attachment], ""
    )
    assert decision.request_type.sources == []


# --- variables -------------------------------------------------------------------------------


def test_f05_variables_segments_and_labels(
    settings, fake_gateway, golden_messages, golden_attachment, golden_triage_output
):
    fake_gateway.responses = {PROMPT: [golden_triage_output]}
    RequestTriageAgent(fake_gateway, settings).run(golden_messages, [golden_attachment], "")
    variables = fake_gateway.calls[0].variables
    assert set(variables) == {"segments", "result_summary", "request_type_labels"}
    lines = variables["segments"].splitlines()
    assert lines[0].startswith("M1: Could you update PIR data")
    assert "A1 = BE25112601_RAIL-DIN 35MM X 7.5MM.pdf, 1 pages" in lines
    assert "A1.p1.e4: Country of origin: DE" in lines
    assert json.loads(variables["request_type_labels"]) == REQUEST_TYPE_LABELS


# --- §7 edge cases ---------------------------------------------------------------------------


def test_f05_attachments_only_empty_message(settings, fake_gateway, golden_attachment):
    fake_gateway.responses = {PROMPT: [_answer()]}
    messages = [Message(message_id="M1", role="user", text="", attachment_ids=["A1"])]
    decision = RequestTriageAgent(fake_gateway, settings).run(messages, [golden_attachment], "")
    assert decision.request_type.value == "update_pir"
    lines = fake_gateway.calls[0].variables["segments"].splitlines()
    assert lines[0] == "M1: "
    assert "A1.p1.e1: QUOTATION" in lines


def test_f05_attachments_without_messages_is_classified(settings, fake_gateway, golden_attachment):
    fake_gateway.responses = {PROMPT: [_answer()]}
    RequestTriageAgent(fake_gateway, settings).run([], [golden_attachment], "")
    assert len(fake_gateway.calls) == 1


def test_f05_gateway_failure_propagated(settings, fake_gateway, golden_messages):
    error = UpstreamUnavailable("The AI service is busy")
    fake_gateway.raise_for = {PROMPT: error}
    with pytest.raises(UpstreamUnavailable) as caught:
        RequestTriageAgent(fake_gateway, settings).run(golden_messages, [], "")
    assert caught.value is error


def test_f05_not_pir_sl_returned_as_is(settings, fake_gateway):
    text = "Thanks for your help last week!"
    fake_gateway.responses = {
        PROMPT: [
            _answer(
                request_type="not_pir_sl",
                message_kind="other",
                evidence=[{"segment_id": "M1", "text": "thanks for your help"}],
            )
        ]
    }
    messages = [Message(message_id="M1", role="user", text=text)]
    decision = RequestTriageAgent(fake_gateway, settings).run(messages, [], "")
    assert decision.request_type.value == "not_pir_sl"
    assert decision.message_kind == "other"
    assert decision.request_type.sources == [
        Source(kind="message", message_id="M1", start=0, end=20, text="thanks for your help")
    ]
    assert len(fake_gateway.calls) == 1


# --- evidence resolution ---------------------------------------------------------------------


def test_f05_element_evidence_resolves_to_attachment_source(
    settings, fake_gateway, golden_messages, golden_attachment
):
    fake_gateway.responses = {
        PROMPT: [_answer(evidence=[{"segment_id": "A1.p1.e4", "text": "Country of origin: DE"}])]
    }
    decision = RequestTriageAgent(fake_gateway, settings).run(
        golden_messages, [golden_attachment], ""
    )
    assert decision.request_type.sources == [
        Source(
            kind="attachment",
            attachment_id="A1",
            page_no=1,
            bbox=(0.08, 0.5, 0.4, 0.52),
            text="Country of origin: DE",
        )
    ]


def test_f05_element_evidence_bbox_refined_by_words(settings, fake_gateway, golden_attachment):
    page = golden_attachment.pages[0]
    page.words = [
        Word(text="Country", bbox=(0.08, 0.5, 0.15, 0.52)),
        Word(text="of", bbox=(0.16, 0.5, 0.18, 0.52)),
        Word(text="origin:", bbox=(0.19, 0.5, 0.26, 0.52)),
        Word(text="DE", bbox=(0.27, 0.5, 0.3, 0.52)),
    ]
    fake_gateway.responses = {
        PROMPT: [_answer(evidence=[{"segment_id": "A1.p1.e4", "text": "origin: DE"}])]
    }
    decision = RequestTriageAgent(fake_gateway, settings).run([], [golden_attachment], "")
    [source] = decision.request_type.sources
    assert source.bbox == (0.19, 0.5, 0.3, 0.52)
    assert source.text == "origin: DE"


def test_f05_element_evidence_quote_not_in_element_dropped(
    settings, fake_gateway, golden_messages, golden_attachment
):
    fake_gateway.responses = {
        PROMPT: [
            _answer(
                evidence=[
                    {"segment_id": "A1.p1.e4", "text": "Country of origin: KR"},
                    {"segment_id": "A1.p1.e5", "text": "lead   TIME: 1 week"},
                ]
            )
        ]
    }
    decision = RequestTriageAgent(fake_gateway, settings).run(
        golden_messages, [golden_attachment], ""
    )
    assert [s.bbox for s in decision.request_type.sources] == [(0.08, 0.53, 0.4, 0.55)]


def test_f05_message_quote_not_found_dropped(settings, fake_gateway, golden_messages):
    fake_gateway.responses = {
        PROMPT: [
            _answer(
                evidence=[
                    {"segment_id": "M1", "text": "create a source list"},
                    {"segment_id": "M1", "text": "update PIR data"},
                    {"segment_id": "M1", "text": "   "},
                ]
            )
        ]
    }
    decision = RequestTriageAgent(fake_gateway, settings).run(golden_messages, [], "")
    assert [s.text for s in decision.request_type.sources] == ["update PIR data"]


# --- schema ----------------------------------------------------------------------------------


def test_f05_schema_labels_from_constants_and_strict_compatible():
    schema = RequestTriageOutput.model_json_schema()
    props = schema["properties"]
    assert props["request_type"]["enum"] == REQUEST_TYPES
    assert props["message_kind"]["enum"] == MESSAGE_KINDS
    assert props["reason"]["maxLength"] == 300
    assert "Evidence" in schema["$defs"]
    assert not has_free_form_map(schema)
    strict = strict_json_schema(RequestTriageOutput)
    assert strict["additionalProperties"] is False
    assert strict["$defs"]["Evidence"]["required"] == ["segment_id", "text"]


def test_f05_schema_rejects_unknown_label_and_long_reason():
    with pytest.raises(ValueError):
        RequestTriageOutput.model_validate(_answer(request_type="delete_pir"))
    with pytest.raises(ValueError):
        RequestTriageOutput.model_validate(_answer(message_kind="question"))
    with pytest.raises(ValueError):
        RequestTriageOutput.model_validate(_answer(reason="x" * 301))
    out = RequestTriageOutput.model_validate(_answer(evidence=[{"segment_id": "M1", "text": "a"}]))
    assert out.evidence == [Evidence(segment_id="M1", text="a")]


# --- logging (TSD §11.2) and interface -------------------------------------------------------


def test_f05_logs_no_model_strings_or_labels(
    settings, fake_gateway, golden_messages, golden_attachment, caplog
):
    fake_gateway.responses = {
        PROMPT: [
            _answer(
                reason="SECRET-REASON marker",
                evidence=[
                    {"segment_id": "SECRET-SEG Could you update", "text": "SECRET-TEXT-1"},
                    {"segment_id": "M1", "text": "SECRET-TEXT-2 not in message"},
                    {"segment_id": "A1.p1.e4", "text": "SECRET-TEXT-3 not in element"},
                    {"segment_id": "M1", "text": "update PIR data"},
                ],
            )
        ]
    }
    with caplog.at_level(logging.DEBUG, logger="backend"):
        decision = RequestTriageAgent(fake_gateway, settings).run(
            golden_messages, [golden_attachment], ""
        )
    assert len(decision.request_type.sources) == 1

    records = [r for r in caplog.records if r.name.startswith("backend")]
    assert records
    forbidden = [
        "SECRET",
        "Could you update",
        "update PIR data",
        "Country of origin",
        "update_pir",
        "request_content",
    ]
    for record in records:
        rendered = record.getMessage()
        pieces = [rendered, str(record.msg), *(str(a) for a in (record.args or ()))]
        for marker in forbidden:
            assert all(marker not in piece for piece in pieces), (marker, rendered)

    messages = " ".join(r.getMessage() for r in records)
    assert "dropped=3" in messages
    assert "unknown_segment=1" in messages
    assert "quote_not_found=2" in messages


def test_f05_constructor_annotations_match_contract():
    hints = typing.get_type_hints(RequestTriageAgent.__init__)
    assert hints["gateway"] is GatewayRepository
    assert hints["settings"] is Settings
    param = inspect.signature(RequestTriageAgent.__init__).parameters["gateway"].annotation
    assert param in (GatewayRepository, "GatewayRepository")
    assert typing.get_type_hints(TriageDecision)["meta"] is CallMeta
