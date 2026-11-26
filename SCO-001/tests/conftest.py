"""Shared fixtures and fakes (TSD §12). Databricks access is replaced by in-memory fakes."""

import copy
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from backend.config import Settings
from backend.main import create_app
from backend.models import Attachment, Element, Message, Page

FIXTURES_DIR = Path(__file__).parent / "fixtures"
GOLDEN_TEXT = (FIXTURES_DIR / "golden_message_M1.txt").read_text(encoding="utf-8").rstrip("\n")


def _load_json(name: str) -> Any:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


class FakeVolumeRepository:
    """In-memory volume: ``dict[path, bytes]``."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def put(self, path: str, data: bytes) -> None:
        self.files[path] = data

    def get(self, path: str) -> bytes:
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    def delete_prefix(self, prefix: str) -> None:
        for path in [p for p in self.files if p.startswith(prefix)]:
            del self.files[path]

    def list(self, prefix: str) -> list[str]:
        return sorted(p for p in self.files if p.startswith(prefix))


class FakeParseRepository:
    """Returns the elements of ``parsed_golden_A1.json`` for any pages folder.

    ``fail_for`` holds attachment ids whose parse raises.
    """

    def __init__(self, elements: list[dict[str, Any]], fail_for: set[str] | None = None) -> None:
        self.elements = elements
        self.fail_for: set[str] = set(fail_for or set())
        self.calls: list[str] = []

    def parse(self, pages_folder: str, attachment_id: str | None = None) -> list[dict[str, Any]]:
        self.calls.append(pages_folder)
        path_parts = set(pages_folder.strip("/").split("/"))
        if attachment_id in self.fail_for or path_parts & self.fail_for:
            raise RuntimeError(f"Parse failed for {attachment_id or pages_folder}")
        return copy.deepcopy(self.elements)


@dataclass
class GatewayCall:
    prompt_name: str
    endpoint: str
    messages: dict[str, str]  # the prompt variables passed to ``complete_json``

    @property
    def variables(self) -> dict[str, str]:
        return self.messages


@dataclass
class FakeCallMeta:
    """Mirrors ``CallMeta`` of the real GatewayRepository (v1/F-03)."""

    prompt_name: str
    prompt_version: int = 1
    endpoint: str = ""
    model: str | None = "fake-model"
    latency_ms: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    retries: int = 0


@dataclass
class FakeGateway:
    """Canned JSON answers per prompt name, returned in order; records every call."""

    responses: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    raise_for: dict[str, Exception] = field(default_factory=dict)
    calls: list[GatewayCall] = field(default_factory=list)

    def complete_json(
        self,
        prompt_name: str,
        endpoint: str,
        variables: dict[str, str],
        schema: type[BaseModel],
    ) -> tuple[BaseModel, FakeCallMeta]:
        self.calls.append(GatewayCall(prompt_name, endpoint, dict(variables)))
        if prompt_name in self.raise_for:
            raise self.raise_for[prompt_name]
        queue = self.responses.get(prompt_name) or []
        if not queue:
            raise AssertionError(f"FakeGateway has no canned response for {prompt_name}")
        payload = queue.pop(0)
        return schema.model_validate(payload), FakeCallMeta(
            prompt_name=prompt_name, endpoint=endpoint
        )


@pytest.fixture
def settings() -> Settings:
    # TSD §12 values; VOLUME_DEMO_REQUESTS, EVAL_TABLE and LOG_LEVEL are required Settings fields
    # not listed in TSD §12, so they take the TSD §10 dev values.
    return Settings(
        CATALOG="sandbox_others",
        SCHEMA="sco_001_poc",
        VOLUME_UPLOADS="/Volumes/sandbox_others/sco_001_poc/uploads",
        VOLUME_DEMO_REQUESTS="/Volumes/sandbox_others/sco_001_poc/demo_requests",
        WAREHOUSE_ID="test-wh",
        ENDPOINT_INTENT="sco_001_intent",
        ENDPOINT_EXTRACT="sco_001_extract",
        PROMPT_ALIAS="production",
        MLFLOW_EXPERIMENT="/Shared/SCO-001/pir_sl_chat",
        EVAL_TABLE="sandbox_others.sco_001_poc.eval_pir_sl_extraction_chat",
        TIME_ZONE="Asia/Singapore",
        LOG_LEVEL="INFO",
    )


@pytest.fixture
def fake_volume_repository() -> FakeVolumeRepository:
    return FakeVolumeRepository()


@pytest.fixture
def fake_parse_repository() -> FakeParseRepository:
    return FakeParseRepository(_load_json("parsed_golden_A1.json"))


@pytest.fixture
def fake_gateway() -> FakeGateway:
    return FakeGateway()


@pytest.fixture
def golden_messages() -> list[Message]:
    return [Message(message_id="M1", role="user", text=GOLDEN_TEXT, attachment_ids=["A1"])]


@pytest.fixture
def golden_attachment() -> Attachment:
    elements = [Element(**element) for element in _load_json("parsed_golden_A1.json")]
    return Attachment(
        attachment_id="A1",
        file_name="BE25112601_RAIL-DIN 35MM X 7.5MM.pdf",
        media_type="application/pdf",
        pages=[Page(page_no=1, width_px=1240, height_px=1754, elements=elements)],
        parse_status="parsed",
    )


@pytest.fixture
def golden_triage_output() -> dict[str, Any]:
    return {
        "request_type": "update_pir",
        "message_kind": "request_content",
        "reason": "The message asks to update PIR data for two parts",
        "evidence": [{"segment_id": "M1", "text": "update PIR data"}],
    }


@pytest.fixture
def golden_extraction_output() -> dict[str, Any]:
    return _load_json("golden_extraction_output.json")


@pytest.fixture
def client(
    settings: Settings,
    fake_volume_repository: FakeVolumeRepository,
    fake_parse_repository: FakeParseRepository,
    fake_gateway: FakeGateway,
) -> Iterator[TestClient]:
    app = create_app(
        settings,
        volume_repository=fake_volume_repository,
        parse_repository=fake_parse_repository,
        gateway=fake_gateway,
    )
    with TestClient(app) as test_client:
        yield test_client
