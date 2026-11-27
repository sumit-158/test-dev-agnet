"""Selection, merge and patch rules C-02..C-04, M-01..M-04 (v1/F-07, TSD §7).

Pure logic: no I/O, no model calls, no logging. Every function returns new objects and leaves
its inputs unchanged. Orchestration methods are added in v2/F-03.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from backend.agents.line_item_extraction.agent import DraftLine, ExtractionDraft
from backend.constants import PIR_FIELDS, SL_FIELDS
from backend.models import (
    Candidate,
    ChangedField,
    FieldValue,
    LineItem,
    Message,
    RequestTypeResult,
    Result,
    Source,
)
from backend.services.normalization import (
    ISSUE_SIGNATURE,
    NormalizationContext,
    normalize,
    signature_block,
    signature_lines,
)

STEWARD_REASON = "Set by the steward"


@dataclass(frozen=True)
class Patch:
    line_no: int
    field: str
    value: str | None


def _fields_of(doc_type: str) -> list[str]:
    return PIR_FIELDS if doc_type == "PIR" else SL_FIELDS


def _now() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- build (C-02..C-04)


def _in_signature(candidate: Candidate, signature_starts: dict[str, int]) -> bool:
    """N-06: the candidate's message span lies inside the message's signature block."""
    source = candidate.source
    if source.kind != "message" or source.message_id is None or source.start is None:
        return False
    start = signature_starts.get(source.message_id)
    return start is not None and source.start >= start


def _rank(candidate: Candidate, message_index: dict[str, int]) -> tuple[int, int, int]:
    """C-02: message above attachment, later message above earlier, lower page_no first."""
    source = candidate.source
    if source.kind == "message":
        return (0, -message_index.get(source.message_id or "", 0), 0)
    return (1, 0, source.page_no or 0)


def _field_value(candidates: list[Candidate], message_index: dict[str, int]) -> FieldValue:
    survivors = [c for c in candidates if c.value_normalised is not None]
    if not survivors:  # C-03
        issues = [c.issue for c in candidates if c.issue]
        return FieldValue(
            value=None,
            status="missing",
            candidates=candidates,
            issue=issues[-1] if issues else None,
        )
    best = min(survivors, key=lambda c: _rank(c, message_index))  # stable: first on ties
    group = [c for c in survivors if c.value_normalised == best.value_normalised]
    group_count = len({c.value_normalised for c in survivors})
    return FieldValue(
        value=best.value_normalised,
        status="found" if group_count == 1 else "conflict",
        derivation=best.derivation,
        computation=best.computation,
        sources=[c.source.model_copy(deep=True) for c in group],  # C-04
        candidates=candidates,
        issue=None,
    )


def _build_line(
    line: DraftLine,
    line_no: int,
    ctx: NormalizationContext,
    signature_starts: dict[str, int],
    message_index: dict[str, int],
) -> LineItem:
    fields: dict[str, FieldValue] = {}
    for name in _fields_of(line.doc_type):
        normalised: list[Candidate] = []
        for candidate in line.candidates.get(name, []):
            out = normalize(name, candidate, ctx)
            if (
                name == "country_of_origin"
                and out.value_normalised is not None
                and _in_signature(out, signature_starts)
            ):
                out = out.model_copy(update={"value_normalised": None, "issue": ISSUE_SIGNATURE})
            normalised.append(out)
        fields[name] = _field_value(normalised, message_index)
    return LineItem(line_no=line_no, doc_type=line.doc_type, action=line.action, fields=fields)


def build_result(
    draft: ExtractionDraft,
    request_type: RequestTypeResult,
    messages: list[Message],
    existing: Result | None,
) -> Result:
    """Normalise, select (C-02..C-04), create FieldValues for every field of each line, merge
    with existing (M-01, M-03)."""
    ctx = NormalizationContext(signature_lines(messages))
    signature_starts: dict[str, int] = {}
    for message in messages:
        block = signature_block(message.text)
        if block is not None:
            signature_starts[message.message_id] = block[0]
    message_index = {m.message_id: i for i, m in enumerate(messages)}
    fresh = Result(
        request_type=request_type.model_copy(deep=True),
        line_items=[
            _build_line(line, line_no, ctx, signature_starts, message_index)
            for line_no, line in enumerate(draft.lines, start=1)
        ],
        notes=list(draft.notes),
    )
    if existing is None:
        return _with_last_line_no(fresh, len(fresh.line_items))
    return merge_result(existing, fresh)


# --------------------------------------------------------------------------- merge (M-01, M-03)


def _key(line: LineItem) -> tuple[str, str | None]:
    material = line.fields.get("material")
    return (line.doc_type, material.value if material else None)


# M-04: line_no is never reused in a session. Result (models.py) has no counter field, and a
# removed line leaves no trace in its fields, so the highest line_no ever used is kept as a
# pydantic private value on the Result instance ("high-water mark"). It is carried by every
# model_copy / deepcopy and by Session.result (sessions live in process memory, TSD §2), and it is
# never part of model_dump / the API JSON. Limits (Planner gap, needs a Result field such as
# last_line_no): a Result rebuilt from JSON or constructed by hand starts again from its highest
# current line_no, and two Results that differ only in this mark compare unequal.
_LAST_LINE_NO = "_last_line_no"


def _last_line_no(result: Result) -> int:
    private = result.__pydantic_private__ or {}
    current = max((line.line_no for line in result.line_items), default=0)
    return max(int(private.get(_LAST_LINE_NO, 0)), current)


def _with_last_line_no(result: Result, last: int) -> Result:
    private = dict(result.__pydantic_private__ or {})
    private[_LAST_LINE_NO] = max(last, _last_line_no(result))
    object.__setattr__(result, "__pydantic_private__", private)
    return result


def merge_result(existing: Result, fresh: Result) -> Result:
    """M-01: match on (doc_type, material value); keep corrected fields; append new lines with
    next line_no."""
    lines = [line.model_copy(deep=True) for line in existing.line_items]
    matched: set[int] = set()
    next_no = _last_line_no(existing) + 1
    for fresh_line in fresh.line_items:
        index = next(
            (
                i
                for i, line in enumerate(lines)
                if i not in matched
                and i < len(existing.line_items)
                and _key(line) == _key(fresh_line)
            ),
            None,
        )
        if index is None:
            lines.append(fresh_line.model_copy(deep=True, update={"line_no": next_no}))
            next_no += 1
            continue
        matched.add(index)
        target = lines[index]
        for name, value in fresh_line.fields.items():
            current = target.fields.get(name)
            if current is not None and current.status == "corrected":  # M-03
                continue
            target.fields[name] = value.model_copy(deep=True)
    request_type = existing.request_type if existing.request_type.corrected else fresh.request_type
    merged = Result(
        request_type=request_type.model_copy(deep=True),
        line_items=lines,
        notes=list(fresh.notes),
        updated_at=_now(),
    )
    return _with_last_line_no(merged, next_no - 1)


# --------------------------------------------------------------------------- patches (M-02, M-04)


def apply_patches(
    result: Result, patches: list[Patch], source: Source
) -> tuple[Result, list[ChangedField], list[str]]:
    """M-02, M-04. Patch(line_no, field, value | None). Returns new result, changes, and
    skipped-patch messages ('Line 9 does not exist', 'Field moq does not exist on line 1')."""
    new = result.model_copy(deep=True)
    changes: list[ChangedField] = []
    skipped: list[str] = []
    for patch in patches:
        line = next((li for li in new.line_items if li.line_no == patch.line_no), None)
        if line is None:
            skipped.append(f"Line {patch.line_no} does not exist")
            continue
        current = line.fields.get(patch.field)
        if current is None:  # not on this line (unknown field, or absent from a sparse line)
            skipped.append(f"Field {patch.field} does not exist on line {patch.line_no}")
            continue
        old = current.value
        line.fields[patch.field] = FieldValue(
            value=patch.value,
            status="corrected",
            derivation="literal",
            computation=None,
            sources=[source.model_copy(deep=True)],
            candidates=list(current.candidates),
            issue=None,
        )
        changes.append(
            ChangedField(
                line_no=patch.line_no, field=patch.field, old_value=old, new_value=patch.value
            )
        )
    new.updated_at = _now()  # §6 step 5: on every call, also when nothing changed
    return new, changes, skipped


def add_line(
    result: Result,
    doc_type: str,
    action: str,
    values: dict[str, str | None],
    source: Source,
) -> tuple[Result, LineItem]:
    names = _fields_of(doc_type)
    for name in values:
        if name not in names:
            raise ValueError(f"Unknown field {name} for {doc_type}")
    fields = {
        name: (
            FieldValue(
                value=values[name], status="corrected", sources=[source.model_copy(deep=True)]
            )
            if name in values
            else FieldValue(value=None, status="missing")
        )
        for name in names
    }
    new = result.model_copy(deep=True)
    line_no = _last_line_no(result) + 1
    line = LineItem(line_no=line_no, doc_type=doc_type, action=action, fields=fields)
    new.line_items.append(line)
    new.updated_at = _now()
    return _with_last_line_no(new, line_no), line.model_copy(deep=True)


def remove_line(result: Result, line_no: int) -> Result:
    """Raises ValueError('Line <n> does not exist')."""
    if not any(line.line_no == line_no for line in result.line_items):
        raise ValueError(f"Line {line_no} does not exist")
    new = result.model_copy(deep=True)
    new.line_items = [line for line in new.line_items if line.line_no != line_no]
    new.updated_at = _now()
    return _with_last_line_no(new, _last_line_no(result))


def set_request_type(result: Result, value: str, source: Source) -> Result:
    """Marks corrected = True."""
    new = result.model_copy(deep=True)
    new.request_type = RequestTypeResult(
        value=value, reason=STEWARD_REASON, sources=[source.model_copy(deep=True)], corrected=True
    )
    new.updated_at = _now()
    return new
