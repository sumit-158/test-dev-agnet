"""v1/F-07 — normalisation, verification, conflict, merge and patch rules (pure logic)."""

from typing import Any

import pytest

from backend.agents.line_item_extraction.agent import (
    DraftLine,
    ExtractionDraft,
    LineItemExtractionAgent,
)
from backend.config import Settings
from backend.constants import PIR_FIELDS, SL_FIELDS
from backend.models import (
    Attachment,
    Candidate,
    ChangedField,
    FieldValue,
    LineItem,
    Message,
    RequestTypeResult,
    Result,
    Source,
)
from backend.repositories.gateway_repository import CallMeta
from backend.services.extraction_service import (
    Patch,
    add_line,
    apply_patches,
    build_result,
    merge_result,
    remove_line,
    set_request_type,
)
from backend.services.normalization import (
    CURRENCY_SYMBOLS,
    SIGNATURE_LINES,
    UOM_SYNONYMS,
    NormalizationContext,
    n01_supplier,
    n02_material,
    n03_vendor_material_no,
    n04_plant,
    n05_purchasing_org,
    n06_country_of_origin,
    n07_lead_time_days,
    n08_standard_qty,
    n09_amount,
    n10_currency,
    n11_pricing_unit,
    n12_unit_of_measure,
    n13_date,
    n14_fixed_vendor,
    n15_personal_data,
    normalize,
    signature_lines,
)

PERSONAL = "Personal data is not extracted"
S33_ISSUE = '"S33" is not a purchasing organisation (3000, 3300, 8000)'
EMPTY_CTX = NormalizationContext({})


def _msg_source(text: str = "x", message_id: str = "M1", start: int = 0) -> Source:
    return Source(
        kind="message", message_id=message_id, start=start, end=start + len(text), text=text
    )


def _att_source(text: str = "x", page_no: int = 1) -> Source:
    return Source(
        kind="attachment", attachment_id="A1", page_no=page_no, bbox=(0, 0, 1, 1), text=text
    )


def _cand(raw: str, source: Source | None = None, **extra: Any) -> Candidate:
    return Candidate(value_raw=raw, source=source or _msg_source(raw), **extra)


def _norm(field: str, raw: str, ctx: NormalizationContext = EMPTY_CTX) -> Candidate:
    return normalize(field, _cand(raw), ctx)


def _rt(value: str = "update_pir") -> RequestTypeResult:
    return RequestTypeResult(value=value, reason="The message asks to update PIR data")


def _meta() -> CallMeta:
    return CallMeta(
        prompt_name="line_item_extraction_chat",
        prompt_version=1,
        endpoint="e",
        model=None,
        latency_ms=0,
        input_tokens=None,
        output_tokens=None,
        retries=0,
    )


def _draft(lines: list[DraftLine], notes: list[str] | None = None) -> ExtractionDraft:
    return ExtractionDraft(lines=lines, notes=notes or [], dropped=[], meta=_meta())


USER_EDIT = Source(kind="user_edit", text="Edited by the steward")
M2_SOURCE = Source(kind="message", message_id="M2", start=0, end=21, text="line 2 amount is 8000")


@pytest.fixture
def golden_draft(
    fake_gateway: Any,
    settings: Settings,
    golden_messages: list[Message],
    golden_attachment: Attachment,
    golden_extraction_output: dict[str, Any],
) -> ExtractionDraft:
    fake_gateway.responses = {"line_item_extraction_chat": [golden_extraction_output]}
    agent = LineItemExtractionAgent(fake_gateway, settings)
    return agent.run(golden_messages, [golden_attachment], "update_pir")


@pytest.fixture
def golden_result(golden_draft: ExtractionDraft, golden_messages: list[Message]) -> Result:
    return build_result(golden_draft, _rt(), golden_messages, None)


# --------------------------------------------------------------------------- AC tests


def test_f07_ac1_golden_result(golden_result: Result) -> None:
    result = golden_result
    assert len(result.line_items) == 2
    assert [li.line_no for li in result.line_items] == [1, 2]
    for line in result.line_items:
        assert line.doc_type == "PIR"
        assert line.action == "update"
        assert list(line.fields) == PIR_FIELDS
    f = result.line_items[0].fields
    assert f["supplier"].value == "18570"
    assert f["material"].value == "1038-967-34"
    assert f["vendor_material_no"].value == "RAIL-DIN 35MM X 7.5MM X 450MM LG"

    assert f["purchasing_org"].value == "3300"
    assert f["purchasing_org"].status == "found"
    s33 = [c for c in f["purchasing_org"].candidates if c.value_raw == "S33"]
    assert len(s33) == 1
    assert s33[0].value_normalised is None
    assert s33[0].issue == S33_ISSUE

    coo = f["country_of_origin"]
    assert coo.status == "conflict"
    assert coo.value == "KR"
    assert [c.value_normalised for c in coo.candidates] == ["KR", "DE"]
    # AC-F07-1 says "2 sources"; rule C-04 wins (human-approved deviation, recorded for the
    # Planner): field sources = the selected group only (KR, M1); KR and DE each keep their own
    # source on their candidate.
    assert len(coo.sources) == 1
    assert coo.sources[0].kind == "message"
    assert coo.sources[0].message_id == "M1"
    by_value = {c.value_normalised: c.source for c in coo.candidates}
    assert by_value["KR"].kind == "message"
    assert by_value["DE"].kind == "attachment"
    assert by_value["DE"].page_no == 1

    lead = f["lead_time_days"]
    assert lead.value == "7"
    assert lead.status == "found"
    assert len(lead.sources) == 2
    assert lead.derivation == "literal"  # C-02 selects the message candidate
    assert lead.computation is None
    # N-07: a bare number is always literal days, whatever the model said
    assert all(c.derivation == "literal" and c.computation is None for c in lead.candidates)

    assert f["standard_qty"].value == "1"
    amount = f["amount"]
    assert amount.value == "7000"
    assert amount.status == "found"
    assert len(amount.sources) == 2
    assert amount.sources[0].kind == "message"
    assert amount.sources[0].text == "7,000"
    assert amount.sources[1].kind == "attachment"
    assert amount.sources[1].page_no == 1
    assert f["currency"].value == "KRW"
    assert f["pricing_unit"].value == "1"
    assert f["unit_of_measure"].value == "EA"
    assert f["valid_from"].value == "2025-11-26"
    for name in ("plant", "valid_to"):
        assert f[name].status == "missing"
        assert f[name].value is None
        assert f[name].sources == []

    f2 = result.line_items[1].fields
    assert f2["material"].value == "1038-967-04"
    assert f2["vendor_material_no"].value == "RAIL-DIN 35MM X 7.5MM X 75MM LG"
    assert result.notes == [
        "No plant is given in the request.",
        "No valid-to date is given in the request.",
    ]
    assert result.request_type.value == "update_pir"


def test_f07_ac2_normalization_table() -> None:
    assert _norm("amount", "7,000").value_normalised == "7000"
    assert _norm("amount", "7.000,50").value_normalised == "7000.50"
    s33 = _norm("purchasing_org", "S33")
    assert s33.value_normalised is None
    assert s33.issue == S33_ISSUE
    lead = _norm("lead_time_days", "8 weeks")
    assert lead.value_normalised == "56"
    assert lead.derivation == "computed"
    assert lead.computation == "8 weeks × 7"
    assert _norm("valid_to", "31.12.9999").value_normalised == "9999-12-31"
    assert _norm("unit_of_measure", "pcs").value_normalised == "PC"
    kim = _norm("supplier", "kim@vendor.com")
    assert kim.value_normalised is None
    assert kim.issue == PERSONAL
    assert _norm("fixed_vendor", "sole source").value_normalised == "X"
    ambiguous = _norm("valid_from", "03/04/2025")
    assert ambiguous.value_normalised is None
    assert ambiguous.issue == "Ambiguous date order"
    too_long = _norm("lead_time_days", "400")
    assert too_long.value_normalised is None
    assert too_long.issue == "Lead time must be between 1 and 365 days"


def test_f07_ac3_merge_keeps_corrected(
    golden_result: Result, golden_draft: ExtractionDraft, golden_messages: list[Message]
) -> None:
    existing, changes, skipped = apply_patches(
        golden_result, [Patch(1, "amount", "8000")], USER_EDIT
    )
    assert skipped == []
    assert len(changes) == 1
    new_line = DraftLine(
        doc_type="PIR",
        action="update",
        candidates={"material": [_cand("2000-04275")], "amount": [_cand("1,200")]},
    )
    fresh_draft = _draft([*golden_draft.lines, new_line], golden_draft.notes)

    merged = build_result(fresh_draft, _rt(), golden_messages, existing)
    assert merged.line_items[0].fields["amount"].value == "8000"
    assert merged.line_items[0].fields["amount"].status == "corrected"
    assert merged.line_items[1].fields["amount"].value == "7000"
    assert len(merged.line_items) == 3
    assert merged.line_items[2].line_no == 3
    assert merged.line_items[2].fields["material"].value == "2000-04275"

    # merge_result directly gives the same outcome
    fresh = build_result(fresh_draft, _rt(), golden_messages, None)
    direct = merge_result(existing, fresh)
    assert direct.line_items[0].fields["amount"].value == "8000"
    assert direct.line_items[0].fields["amount"].status == "corrected"
    assert [li.line_no for li in direct.line_items] == [1, 2, 3]


def test_f07_ac4_apply_patches(golden_result: Result) -> None:
    patched, changes, skipped = apply_patches(
        golden_result, [Patch(2, "amount", "8000"), Patch(9, "amount", "1")], M2_SOURCE
    )
    assert changes == [ChangedField(line_no=2, field="amount", old_value="7000", new_value="8000")]
    assert skipped == ["Line 9 does not exist"]
    amount = patched.line_items[1].fields["amount"]
    assert amount.value == "8000"
    assert amount.status == "corrected"
    assert amount.derivation == "literal"
    assert amount.computation is None
    assert amount.issue is None
    assert amount.sources[0].message_id == "M2"
    assert len(amount.sources) == 1
    assert amount.candidates == golden_result.line_items[1].fields["amount"].candidates
    assert patched.line_items[0] == golden_result.line_items[0]


def test_human_check_won_symbol_amount() -> None:
    assert _norm("amount", "₩7,000").value_normalised == "7000"


# --------------------------------------------------------------------------- §7 edge cases


def test_edge_empty_draft() -> None:
    result = build_result(_draft([], ["Nothing found"]), _rt(), [], None)
    assert result.line_items == []
    assert result.notes == ["Nothing found"]


def test_edge_all_candidates_rejected() -> None:
    line = DraftLine("PIR", "update", {"purchasing_org": [_cand("S33")]})
    fv = build_result(_draft([line]), _rt(), [], None).line_items[0].fields["purchasing_org"]
    assert fv.status == "missing"
    assert fv.value is None
    assert fv.issue == S33_ISSUE
    assert [c.value_raw for c in fv.candidates] == ["S33"]
    assert fv.sources == []


def test_edge_conflict_equal_rank_lower_page_wins() -> None:
    line = DraftLine(
        "PIR",
        "update",
        {
            "amount": [
                _cand("8,000", _att_source("8,000", 2)),
                _cand("7,000", _att_source("7,000", 1)),
            ]
        },
    )
    fv = build_result(_draft([line]), _rt(), [], None).line_items[0].fields["amount"]
    assert fv.status == "conflict"
    assert fv.value == "7000"
    assert [s.page_no for s in fv.sources] == [1]
    assert len(fv.candidates) == 2


def test_edge_same_value_different_raw() -> None:
    line = DraftLine(
        "PIR", "update", {"amount": [_cand("7,000"), _cand("7000", _att_source("7000"))]}
    )
    fv = build_result(_draft([line]), _rt(), [], None).line_items[0].fields["amount"]
    assert fv.status == "found"
    assert fv.value == "7000"
    assert len(fv.sources) == 2


def test_edge_merge_with_corrected_field(golden_result: Result) -> None:
    existing, _, _ = apply_patches(golden_result, [Patch(1, "amount", "8000")], USER_EDIT)
    merged = merge_result(existing, golden_result)
    assert merged.line_items[0].fields["amount"].value == "8000"
    assert merged.line_items[0].fields["amount"].status == "corrected"
    assert merged.line_items[0].line_id == existing.line_items[0].line_id


def test_edge_merge_new_part(golden_result: Result) -> None:
    line = DraftLine("PIR", "update", {"material": [_cand("2000-04275")]})
    fresh = build_result(_draft([line]), _rt(), [], None)
    merged = merge_result(golden_result, fresh)
    assert len(merged.line_items) == 3
    assert merged.line_items[2].line_no == 3
    assert merged.line_items[2].fields["material"].value == "2000-04275"


def test_edge_patch_unknown_line(golden_result: Result) -> None:
    patched, changes, skipped = apply_patches(golden_result, [Patch(9, "amount", "1")], USER_EDIT)
    assert changes == []
    assert skipped == ["Line 9 does not exist"]
    assert patched.line_items == golden_result.line_items


def test_edge_patch_unknown_field(golden_result: Result) -> None:
    patched, changes, skipped = apply_patches(golden_result, [Patch(1, "moq", "1")], USER_EDIT)
    assert changes == []
    assert skipped == ["Field moq does not exist on line 1"]
    assert patched.line_items == golden_result.line_items


def test_edge_patch_to_empty(golden_result: Result) -> None:
    patched, changes, _ = apply_patches(golden_result, [Patch(1, "plant", None)], USER_EDIT)
    fv = patched.line_items[0].fields["plant"]
    assert fv.value is None
    assert fv.status == "corrected"
    assert fv.sources == [USER_EDIT]
    assert changes == [ChangedField(line_no=1, field="plant", old_value=None, new_value=None)]


def test_edge_remove_missing_line(golden_result: Result) -> None:
    with pytest.raises(ValueError, match="^Line 7 does not exist$"):
        remove_line(golden_result, 7)


# --------------------------------------------------------------------------- rules N-01..N-15


def test_n01_supplier() -> None:
    assert n01_supplier(" 18570 ") == "18570"
    assert n01_supplier("  Woojin Co. ") == "Woojin Co."
    assert _norm("supplier", "18570").value_normalised == "18570"
    rejected = _norm("supplier", "   ")
    assert rejected.value_normalised is None
    assert rejected.issue == "Empty value"


def test_n02_material() -> None:
    for raw in ("1038-967-34", "2000-04275", "1234567", "1234567890"):
        assert n02_material(f" {raw} ") == raw
        assert _norm("material", raw).value_normalised == raw
    for raw in ("1038-96-34", "123456", "ABC-123", "12345678901"):
        c = _norm("material", raw)
        assert c.value_normalised is None
        assert c.issue == "Not a part number pattern"


def test_n03_vendor_material_no() -> None:
    assert n03_vendor_material_no(" RAIL-DIN  35MM   X 7.5MM ") == "RAIL-DIN 35MM X 7.5MM"
    c = _norm("vendor_material_no", "1038-967-34")
    assert c.value_normalised is None
    assert c.issue == "Description equals the part number"


def test_n04_plant() -> None:
    assert _norm("plant", " 1100 ").value_normalised == "1100"
    for raw in ("110", "P100", "11000"):
        c = _norm("plant", raw)
        assert c.value_normalised is None
        assert c.issue == "Not a plant code"
    assert n04_plant("1100") == "1100"


def test_n05_purchasing_org() -> None:
    for raw in ("3000", "3300", " 8000 "):
        assert _norm("purchasing_org", raw).value_normalised == raw.strip()
    assert n05_purchasing_org("3300") == "3300"
    for raw in ("3301", "S33", "33 00"):
        c = _norm("purchasing_org", raw)
        assert c.value_normalised is None
        assert c.issue == f'"{raw.strip()}" is not a purchasing organisation (3000, 3300, 8000)'


def test_n06_country_of_origin_format() -> None:
    assert _norm("country_of_origin", " kr ").value_normalised == "KR"
    assert n06_country_of_origin("de") == "DE"
    for raw in ("KOR", "Korea", "K1"):
        c = _norm("country_of_origin", raw)
        assert c.value_normalised is None
        assert c.issue == "Not a country code"


def test_n06_country_from_signature_dropped() -> None:
    text = "Please update the PIR, origin KR\n\nBest regards\nKim\nSeoul, KR\nTel 010-1234-5678"
    messages = [Message(message_id="M1", role="user", text=text)]
    body = text.index("KR")
    sig = text.index("KR", body + 1)
    line = DraftLine(
        "PIR",
        "update",
        {
            "country_of_origin": [
                _cand("KR", _msg_source("KR", start=body)),
                _cand("KR", _msg_source("KR", start=sig)),
            ]
        },
    )
    # The whole message is within the last 8 lines, so both are in the signature block.
    fv = (
        build_result(_draft([line]), _rt(), messages, None)
        .line_items[0]
        .fields["country_of_origin"]
    )
    assert fv.status == "missing"
    assert fv.issue == "Taken from a signature"
    assert all(c.issue == "Taken from a signature" for c in fv.candidates)

    long_text = "Origin KR\n" + "\n".join(f"row {i}" for i in range(8)) + "\nkim@vendor.com"
    messages = [Message(message_id="M1", role="user", text=long_text)]
    line = DraftLine(
        "PIR", "update", {"country_of_origin": [_cand("KR", _msg_source("KR", start=7))]}
    )
    fv = (
        build_result(_draft([line]), _rt(), messages, None)
        .line_items[0]
        .fields["country_of_origin"]
    )
    assert fv.status == "found"
    assert fv.value == "KR"


def test_n07_lead_time_days() -> None:
    for raw, days in (("7", "7"), ("10 days", "10"), ("3d", "3"), ("1 day", "1"), ("365", "365")):
        c = _norm("lead_time_days", raw)
        assert c.value_normalised == days
        assert c.derivation == "literal"
    for raw, days, n in (("2 wks", "14", "2"), ("1 week", "7", "1"), ("3w", "21", "3")):
        c = _norm("lead_time_days", raw)
        assert c.value_normalised == days
        assert c.derivation == "computed"
        assert c.computation == f"{n} weeks × 7"
    assert n07_lead_time_days("8 weeks") == "56"
    for raw in ("0", "53 weeks"):
        assert _norm("lead_time_days", raw).issue == "Lead time must be between 1 and 365 days"
    c = _norm("lead_time_days", "soon")
    assert c.value_normalised is None
    assert c.issue == "Not a lead time"


def test_n07_bare_number_is_always_literal() -> None:
    c = normalize(
        "lead_time_days",
        _cand("7", _att_source("1 week"), derivation="computed", computation="1 week x 7 days = 7"),
        EMPTY_CTX,
    )
    assert c.value_normalised == "7"
    assert c.derivation == "literal"
    assert c.computation is None
    c = normalize(
        "lead_time_days",
        _cand("10 days", derivation="computed", computation="model computation"),
        EMPTY_CTX,
    )
    assert (c.value_normalised, c.derivation, c.computation) == ("10", "literal", None)


def test_n08_standard_qty() -> None:
    assert _norm("standard_qty", "1.0").value_normalised == "1"
    assert _norm("standard_qty", " 10 ").value_normalised == "10"
    assert n08_standard_qty("5") == "5"
    for raw in ("0", "1.5", "-1", "many"):
        c = _norm("standard_qty", raw)
        assert c.value_normalised is None
        assert c.issue == "Standard quantity must be a whole number of at least 1"


def test_n09_amount() -> None:
    cases = {
        "7,000": "7000",
        "7.000,50": "7000.50",
        "7,000.00": "7000.00",
        "KRW 7,000": "7000",
        "$ 1,234,567.5": "1234567.5",
        "7.000": "7000",
        "7.5": "7.5",
        "1,5": "1.5",
        "1.234.567": "1234567",
    }
    for raw, expected in cases.items():
        assert _norm("amount", raw).value_normalised == expected, raw
    assert n09_amount("₩7,000") == "7000"
    neg = _norm("amount", "-7,000")
    assert neg.value_normalised is None
    assert neg.issue == "Amount must be positive"
    for raw in ("abc", "1.2.3,4,5"):
        c = _norm("amount", raw)
        assert c.value_normalised is None
        assert c.issue == "Not an amount"


def test_n10_currency() -> None:
    assert _norm("currency", "krw").value_normalised == "KRW"
    for symbol, code in CURRENCY_SYMBOLS.items():
        c = _norm("currency", symbol)
        assert c.value_normalised == code
        assert c.derivation == "computed"
        assert c.computation == f"symbol {symbol}"
    assert CURRENCY_SYMBOLS == {"$": "USD", "€": "EUR", "¥": "JPY", "₩": "KRW"}
    assert n10_currency("eur") == "EUR"
    for raw in ("KRWX", "₩₩", "won1"):
        c = _norm("currency", raw)
        assert c.value_normalised is None
        assert c.issue == "Not a currency code"


def test_n11_pricing_unit() -> None:
    for raw in ("1", "10", "100", "1000"):
        assert _norm("pricing_unit", raw).value_normalised == raw
    assert n11_pricing_unit(" 100 ") == "100"
    for raw in ("5", "1.0", "per 100"):
        c = _norm("pricing_unit", raw)
        assert c.value_normalised is None
        assert c.issue == "Not an allowed pricing unit"


def test_n12_unit_of_measure() -> None:
    assert UOM_SYNONYMS == {
        "PCS": "PC",
        "EACH": "EA",
        "PIECE": "PC",
        "PIECES": "PC",
        "METER": "M",
        "METRE": "M",
        "KGS": "KG",
    }
    for raw, expected in (
        ("ea", "EA"),
        ("Each", "EA"),
        ("metre", "M"),
        ("kgs", "KG"),
        ("box", "BOX"),
    ):
        assert _norm("unit_of_measure", raw).value_normalised == expected
    assert n12_unit_of_measure("pieces") == "PC"
    c = _norm("unit_of_measure", "drum")
    assert c.value_normalised is None
    assert c.issue == "Not an allowed unit of measure"


def test_n13_dates() -> None:
    cases = {
        "2025-11-26": "2025-11-26",
        "26.11.2025": "2025-11-26",
        "2025.11.26": "2025-11-26",
        "26/11/2025": "2025-11-26",
        "11/26/2025": "2025-11-26",
        "26 November 2025": "2025-11-26",
        "November 26, 2025": "2025-11-26",
        "31.12.9999": "9999-12-31",
    }
    for raw, expected in cases.items():
        assert _norm("valid_from", raw).value_normalised == expected, raw
        assert _norm("valid_to", raw).value_normalised == expected, raw
    assert n13_date("2025-11-26") == "2025-11-26"
    for raw in ("03/04/2025", "12/12/2025"):
        assert _norm("valid_from", raw).issue == "Ambiguous date order"
    for raw in ("next month", "2025-13-01", "13/13/2025"):
        c = _norm("valid_to", raw)
        assert c.value_normalised is None
        assert c.issue == "Not a date"


def test_n14_fixed_vendor() -> None:
    for raw in ("sole source", "Fixed vendor", "FIXED SOURCE"):
        assert n14_fixed_vendor(raw) == "X"
        assert _norm("fixed_vendor", raw).value_normalised == "X"
    assert n14_fixed_vendor("preferred vendor") is None
    assert n14_fixed_vendor("console") is None
    c = _norm("fixed_vendor", "preferred vendor")
    assert c.value_normalised is None
    assert c.issue == "No fixed or sole source wording"
    # the model's value "X" is accepted when its quoted text says fixed / sole
    c = normalize("fixed_vendor", _cand("X", _msg_source("sole source")), EMPTY_CTX)
    assert c.value_normalised == "X"


def test_n14_fixed_vendor_missing_without_candidate() -> None:
    line = DraftLine("SL", "create", {"material": [_cand("1038-967-34")]})
    result = build_result(_draft([line]), _rt("create_sl"), [], None)
    fv = result.line_items[0].fields["fixed_vendor"]
    assert list(result.line_items[0].fields) == SL_FIELDS
    assert fv.status == "missing"
    assert fv.value is None


def test_n15_personal_data() -> None:
    ctx = NormalizationContext({"M1": {"Kim Min-jun", "Sales Manager"}})
    assert n15_personal_data("kim@vendor.com", "vendor_material_no", ctx, "M1")
    assert n15_personal_data("010-1234-5678", "supplier", ctx, "M1")
    assert n15_personal_data("+82 10 1234 5678", "vendor_material_no", ctx, "M1")
    assert n15_personal_data("Kim Min-jun", "supplier", ctx, "M1")
    assert not n15_personal_data("Kim Min-jun", "supplier", ctx, "M2")
    assert not n15_personal_data("Woojin Co.", "supplier", ctx, "M1")
    assert not n15_personal_data("1,234,567", "amount", ctx, "M1")
    assert not n15_personal_data("1038-967-34", "material", ctx, "M1")
    assert not n15_personal_data("2025-11-26", "valid_from", ctx, "M1")
    assert not n15_personal_data("31.12.9999", "valid_to", ctx, "M1")
    for field, raw in (("supplier", "Kim Min-jun"), ("supplier", "010-1234-5678")):
        c = normalize(field, _cand(raw), ctx)
        assert c.value_normalised is None
        assert c.issue == PERSONAL
    c = normalize("supplier", _cand("Kim Min-jun", _att_source("Kim Min-jun")), ctx)
    assert c.value_normalised == "Kim Min-jun"  # attachment source: no message signature


def test_signature_lines() -> None:
    assert SIGNATURE_LINES == 8
    body = "\n".join(f"body {i}" for i in range(5))
    sig = "Best regards\nKim Min-jun\nSales Manager\nTel 010-1234-5678"
    messages = [
        Message(message_id="M1", role="user", text=f"{body}\n{sig}\n"),
        Message(message_id="M2", role="user", text="Please update PIR 1038-967-34 on 2025-11-26"),
        Message(message_id="M3", role="user", text="Thanks\nkim@vendor.com"),
    ]
    lines = signature_lines(messages)
    assert lines["M1"] == {
        "body 1",
        "body 2",
        "body 3",
        "body 4",
        "Best regards",
        "Kim Min-jun",
        "Sales Manager",
        "Tel 010-1234-5678",
    }
    assert lines["M2"] == set()
    assert lines["M3"] == {"Thanks", "kim@vendor.com"}


def test_golden_message_has_no_signature(golden_messages: list[Message]) -> None:
    assert signature_lines(golden_messages) == {"M1": set()}


def test_normalize_unknown_field() -> None:
    with pytest.raises(ValueError, match="^Unknown field moq$"):
        _norm("moq", "1")


# --------------------------------------------------------------------------- other functions


def test_add_line(golden_result: Result) -> None:
    result, line = add_line(
        golden_result, "SL", "create", {"material": "2000-04275", "fixed_vendor": "X"}, USER_EDIT
    )
    assert line.line_no == 3
    assert result.line_items[-1] == line
    assert list(line.fields) == SL_FIELDS
    assert line.fields["material"].value == "2000-04275"
    assert line.fields["material"].status == "corrected"
    assert line.fields["material"].sources == [USER_EDIT]
    assert line.fields["plant"].status == "missing"
    assert line.fields["plant"].value is None
    assert len(golden_result.line_items) == 2
    with pytest.raises(ValueError):
        add_line(golden_result, "SL", "create", {"amount": "1"}, USER_EDIT)


def test_add_line_to_empty_result() -> None:
    _, line = add_line(Result(request_type=_rt()), "PIR", "create", {}, USER_EDIT)
    assert line.line_no == 1
    assert all(fv.status == "missing" for fv in line.fields.values())


def test_remove_line_keeps_numbers_and_never_reuses(golden_result: Result) -> None:
    result = remove_line(golden_result, 1)
    assert [li.line_no for li in result.line_items] == [2]
    assert len(golden_result.line_items) == 2
    _, line = add_line(result, "PIR", "create", {}, USER_EDIT)
    assert line.line_no == 3


def test_set_request_type(golden_result: Result) -> None:
    result = set_request_type(golden_result, "create_pir", M2_SOURCE)
    assert result.request_type.value == "create_pir"
    assert result.request_type.corrected is True
    assert result.request_type.sources == [M2_SOURCE]
    assert golden_result.request_type.corrected is False


def test_merge_keeps_corrected_request_type(golden_result: Result) -> None:
    existing = set_request_type(golden_result, "create_pir", M2_SOURCE)
    assert merge_result(existing, golden_result).request_type.value == "create_pir"
    fresh = golden_result.model_copy(update={"request_type": _rt("update_sl")})
    assert merge_result(golden_result, fresh).request_type.value == "update_sl"


def test_merge_unmatched_existing_lines_stay(golden_result: Result) -> None:
    line = DraftLine("PIR", "update", {"material": [_cand("1038-967-04")], "amount": [_cand("9")]})
    fresh = build_result(_draft([line]), _rt(), [], None)
    merged = merge_result(golden_result, fresh)
    assert [li.line_no for li in merged.line_items] == [1, 2]
    assert merged.line_items[0] == golden_result.line_items[0]
    assert merged.line_items[1].fields["amount"].value == "9"
    assert merged.line_items[1].fields["supplier"].status == "missing"


def test_c02_later_message_ranks_above_earlier() -> None:
    messages = [
        Message(message_id="M1", role="user", text="amount 7,000"),
        Message(message_id="M2", role="user", text="amount 8,000"),
    ]
    line = DraftLine(
        "PIR",
        "update",
        {
            "amount": [
                _cand("7,000", _att_source("7,000")),
                _cand("7,000", _msg_source("7,000", "M1", 7)),
                _cand("8,000", _msg_source("8,000", "M2", 7)),
            ]
        },
    )
    fv = build_result(_draft([line]), _rt(), messages, None).line_items[0].fields["amount"]
    assert fv.status == "conflict"
    assert fv.value == "8000"
    assert [s.message_id for s in fv.sources] == ["M2"]


def test_c03_missing_without_candidates_has_no_issue() -> None:
    line = DraftLine("PIR", "update", {"material": [_cand("1038-967-34")]})
    fv = build_result(_draft([line]), _rt(), [], None).line_items[0].fields["amount"]
    assert fv == FieldValue(status="missing")


def test_c04_computed_value_sources() -> None:
    line = DraftLine(
        "PIR", "update", {"lead_time_days": [_cand("2 weeks", _att_source("2 weeks"))]}
    )
    fv = build_result(_draft([line]), _rt(), [], None).line_items[0].fields["lead_time_days"]
    assert fv.value == "14"
    assert fv.derivation == "computed"
    assert fv.computation == "2 weeks × 7"
    assert [s.text for s in fv.sources] == ["2 weeks"]


def test_no_defaults_filled(golden_result: Result) -> None:
    line = DraftLine("PIR", "create", {"material": [_cand("1038-967-34")]})
    fields = build_result(_draft([line]), _rt(), [], None).line_items[0].fields
    for name in ("plant", "valid_to", "pricing_unit", "unit_of_measure"):
        assert fields[name].value is None
        assert fields[name].status == "missing"


# --------------------------------------------------------------------------- immutability


def test_normalize_does_not_mutate_input() -> None:
    candidate = _cand("7,000")
    before = candidate.model_copy(deep=True)
    out = normalize("amount", candidate, EMPTY_CTX)
    assert candidate == before
    assert out is not candidate
    assert out.source is not candidate.source


def test_build_result_does_not_mutate_draft(
    golden_draft: ExtractionDraft, golden_messages: list[Message]
) -> None:
    before = [
        {k: [c.model_copy(deep=True) for c in v] for k, v in line.candidates.items()}
        for line in golden_draft.lines
    ]
    build_result(golden_draft, _rt(), golden_messages, None)
    assert [line.candidates for line in golden_draft.lines] == before


def test_result_functions_do_not_mutate_input(golden_result: Result) -> None:
    snapshot = golden_result.model_copy(deep=True)
    apply_patches(golden_result, [Patch(1, "amount", "8000")], USER_EDIT)
    add_line(golden_result, "PIR", "create", {"amount": "1"}, USER_EDIT)
    remove_line(golden_result, 1)
    set_request_type(golden_result, "create_pir", USER_EDIT)
    existing, _, _ = apply_patches(golden_result, [Patch(1, "amount", "8000")], USER_EDIT)
    existing_snapshot = existing.model_copy(deep=True)
    merged = merge_result(existing, golden_result)
    assert golden_result == snapshot
    assert existing == existing_snapshot
    merged.line_items[0].fields["amount"].value = "1"
    assert existing.line_items[0].fields["amount"].value == "8000"
    assert golden_result.line_items[1].fields["amount"].value == "7000"


def test_apply_patches_updates_timestamp(golden_result: Result) -> None:
    patched, _, _ = apply_patches(golden_result, [Patch(1, "amount", "8000")], USER_EDIT)
    assert patched.updated_at >= golden_result.updated_at
    assert isinstance(patched.line_items[0], LineItem)


# --------------------------------------------------------------------------- review round 1


def test_m04_remove_highest_line_never_reuses_its_number(golden_result: Result) -> None:
    removed = remove_line(golden_result, 2)
    assert [li.line_no for li in removed.line_items] == [1]
    _, added = add_line(removed, "PIR", "create", {}, USER_EDIT)
    assert added.line_no == 3

    line = DraftLine("PIR", "update", {"material": [_cand("2000-04275")]})
    fresh = build_result(_draft([line]), _rt(), [], None)
    merged = merge_result(removed, fresh)
    assert [li.line_no for li in merged.line_items] == [1, 3]

    # the mark survives the other operations and the copies they make
    kept = set_request_type(removed, "create_pir", USER_EDIT)
    kept, _, _ = apply_patches(kept, [Patch(1, "amount", "1")], USER_EDIT)
    kept = remove_line(kept, 1)
    assert kept.line_items == []
    kept = build_result(_draft([line]), _rt(), [], kept)
    assert [li.line_no for li in kept.line_items] == [3]
    kept, again = add_line(kept, "PIR", "create", {}, USER_EDIT)
    assert again.line_no == 4
    kept = remove_line(kept, 4)
    _, last = add_line(kept.model_copy(deep=True), "PIR", "create", {}, USER_EDIT)
    assert last.line_no == 5


def test_patch_field_absent_from_line_is_skipped() -> None:
    sparse = Result(
        request_type=_rt(),
        line_items=[
            LineItem(
                line_no=1,
                doc_type="PIR",
                action="update",
                fields={"material": FieldValue(value="1038-967-34", status="found")},
            )
        ],
    )
    patched, changes, skipped = apply_patches(sparse, [Patch(1, "amount", "1")], USER_EDIT)
    assert changes == []
    assert skipped == ["Field amount does not exist on line 1"]
    assert list(patched.line_items[0].fields) == ["material"]


def test_apply_patches_always_sets_updated_at(golden_result: Result) -> None:
    from datetime import UTC, datetime

    old = golden_result.model_copy(update={"updated_at": datetime(2020, 1, 1, tzinfo=UTC)})
    for patches in ([], [Patch(9, "amount", "1")], [Patch(1, "moq", "1")]):
        patched, changes, _ = apply_patches(old, patches, USER_EDIT)
        assert changes == []
        assert patched.updated_at > old.updated_at
    assert old.updated_at == datetime(2020, 1, 1, tzinfo=UTC)


@pytest.mark.parametrize("raw", ["", "   "])
def test_blank_values_get_the_rule_message(raw: str) -> None:
    expected = {
        "material": "Not a part number pattern",
        "purchasing_org": f'"{raw.strip()}" is not a purchasing organisation (3000, 3300, 8000)',
        "plant": "Not a plant code",
        "country_of_origin": "Not a country code",
        "lead_time_days": "Not a lead time",
        "standard_qty": "Standard quantity must be a whole number of at least 1",
        "amount": "Not an amount",
        "currency": "Not a currency code",
        "pricing_unit": "Not an allowed pricing unit",
        "unit_of_measure": "Not an allowed unit of measure",
        "valid_from": "Not a date",
        "valid_to": "Not a date",
        "fixed_vendor": "No fixed or sole source wording",
        "supplier": "Empty value",
        "vendor_material_no": "Empty value",
    }
    assert set(expected) == set(PIR_FIELDS) | set(SL_FIELDS)
    for field, issue in expected.items():
        c = normalize(field, _cand(raw, _att_source("x")), EMPTY_CTX)
        assert c.value_normalised is None, field
        assert c.issue == issue, field


def test_n09_leading_decimal_point() -> None:
    assert _norm("amount", ".50").value_normalised == "0.50"
    assert _norm("amount", "$.5").value_normalised == "0.5"
    assert n09_amount(",50") == "0.50"


def test_n13_output_is_zero_padded_iso() -> None:
    for raw in ("0001-01-01", "01.01.0001", "0001.01.01"):
        assert n13_date(raw) == "0001-01-01"
        assert _norm("valid_from", raw).value_normalised == "0001-01-01"
    assert n13_date("26 November 0999") == "0999-11-26"
