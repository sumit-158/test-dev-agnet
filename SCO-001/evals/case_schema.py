"""EvalCase mirroring the T-01 columns (TSD §5.2) and ``load_case`` for one SRC-01 case folder."""

import json
import posixpath
import re
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

from backend.constants import PIR_FIELDS, REQUEST_TYPES, SL_FIELDS

CASE_ID_PATTERN = re.compile(r"^(GE|DEMO|SYN|INJ|NOT|COR)-\d{3}$")
CASE_FILE = "case.json"
MESSAGE_FILE_PATTERN = re.compile(r"^message_.*\.txt$")
FIELDS_BY_DOC_TYPE = {"PIR": set(PIR_FIELDS), "SL": set(SL_FIELDS)}
ACTIONS = {"create", "update"}
# T-01 tags column comment (TSD §5.2 + DDL).
ALLOWED_TAGS = {
    "golden",
    "demo",
    "synthetic",
    "injection",
    "not_pir_sl",
    "multilingual",
    "conflict",
    "computed",
    "both_pir_and_sl",
    "scanned",
    "correction",
}


class VolumeFiles(Protocol):
    """Read access to SRC-01; satisfied by ``FakeVolumeRepository`` and the SDK adapter."""

    def list(self, prefix: str) -> list[str]:
        """Every file path (recursive) under ``prefix``."""
        ...

    def get(self, path: str) -> bytes: ...


class EvalCase(BaseModel):
    case_id: str
    version: int | None = None
    title: str
    messages: list[str]
    attachment_paths: list[str]
    expected_request_type: str
    expected_line_items: list[dict[str, Any]]
    expected_source_segments: dict[str, list[str]] = {}
    tags: list[str]
    is_synthetic: bool
    notes: str | None = None

    @property
    def messages_json(self) -> str:
        return json.dumps([{"text": text} for text in self.messages], ensure_ascii=False)

    @property
    def expected_line_items_json(self) -> str:
        return json.dumps(self.expected_line_items, ensure_ascii=False)

    @property
    def expected_source_segments_json(self) -> str:
        return json.dumps(self.expected_source_segments, ensure_ascii=False)


def _validate(case: EvalCase) -> None:
    cid = case.case_id
    if not CASE_ID_PATTERN.fullmatch(cid):
        raise ValueError(f"{cid!r}: case_id must match {CASE_ID_PATTERN.pattern}")
    if case.expected_request_type not in REQUEST_TYPES:
        raise ValueError(f"{cid}: expected_request_type must be one of {', '.join(REQUEST_TYPES)}")
    unknown_tags = sorted(set(case.tags) - ALLOWED_TAGS)
    if unknown_tags:
        raise ValueError(f"{cid}: unknown tags {', '.join(unknown_tags)}")
    for line_no, item in enumerate(case.expected_line_items, start=1):
        doc_type = item.get("doc_type")
        if doc_type not in FIELDS_BY_DOC_TYPE:
            raise ValueError(f"{cid}: line {line_no} doc_type must be PIR or SL")
        if item.get("action") not in ACTIONS:
            raise ValueError(f"{cid}: line {line_no} action must be create or update")
        fields = item.get("fields") or {}
        unknown = sorted(set(fields) - FIELDS_BY_DOC_TYPE[doc_type])
        if unknown:
            raise ValueError(
                f"{cid}: line {line_no} fields not allowed for {doc_type}: {', '.join(unknown)}"
            )
        for value in fields.values():
            if value is not None and "@" in str(value):
                raise ValueError(f"{cid}: expected values must not contain personal data")


def load_case(case_dir: str, files: VolumeFiles) -> EvalCase:
    """Read case.json and message_nn.txt files in send order.

    attachment_paths = every file in case_dir that is not case.json or message_*.txt.
    Raises ValueError when case.json is missing, when case_id is invalid or differs from the
    folder name, or when expected_request_type is invalid.
    """
    case_dir = case_dir.rstrip("/")
    paths = sorted(files.list(case_dir + "/"))
    message_paths = [p for p in paths if MESSAGE_FILE_PATTERN.fullmatch(posixpath.basename(p))]
    case_path = f"{case_dir}/{CASE_FILE}"
    attachment_paths = [p for p in paths if p != case_path and p not in message_paths]
    if case_path not in paths:
        raise ValueError(f"{case_dir}: {CASE_FILE} not found")

    raw = json.loads(files.get(case_path).decode("utf-8"))
    raw["messages"] = [files.get(p).decode("utf-8").rstrip("\n") for p in message_paths]
    raw["attachment_paths"] = attachment_paths
    try:
        case = EvalCase.model_validate(raw)
    except ValidationError as error:
        raise ValueError(f"{raw.get('case_id', case_dir)}: invalid case.json: {error}") from error
    _validate(case)
    folder = posixpath.basename(case_dir)
    if case.case_id != folder:
        raise ValueError(f"{case.case_id}: case_id must equal the folder name {folder!r}")
    return case
