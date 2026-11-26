"""v1/F-03 — Register prompts v1 and build the gateway repository."""

import copy
import json
import logging
import re
import subprocess
import sys
import types
from pathlib import Path
from typing import Any, Literal

import httpx
import mlflow
import openai
import pytest
from pydantic import BaseModel, ConfigDict, Field

from backend.config import Settings
from backend.constants import MESSAGE_KINDS, REQUEST_TYPES
from backend.errors import UpstreamUnavailable
from backend.repositories import gateway_repository
from backend.repositories.gateway_repository import (
    PROMPT_CACHE_SECONDS,
    CallMeta,
    GatewayRepository,
)
from evals import register_prompts
from tests.conftest import FakeCallMeta

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"

VALID_ANSWER = (
    '{"request_type":"update_pir","message_kind":"request_content","reason":"r","evidence":[]}'
)
SYSTEM_MESSAGE = "You answer only with JSON that matches the given schema."


class Evidence(BaseModel):
    segment_id: str
    text: str


class RequestTriageOutput(BaseModel):
    """Local stand-in with the TSD §7 shape; the real schema belongs to v1/F-05."""

    request_type: Literal[tuple(REQUEST_TYPES)]  # type: ignore[valid-type]
    message_kind: Literal[tuple(MESSAGE_KINDS)]  # type: ignore[valid-type]
    reason: str = Field(max_length=300)
    evidence: list[Evidence]


# --- fakes -------------------------------------------------------------------------------------

_REQUEST = httpx.Request("POST", "https://example.invalid/serving-endpoints/chat/completions")


def rate_limit_error() -> openai.RateLimitError:
    return openai.RateLimitError(
        "Rate limit exceeded", response=httpx.Response(429, request=_REQUEST), body=None
    )


def timeout_error() -> openai.APITimeoutError:
    return openai.APITimeoutError(request=_REQUEST)


def server_error() -> openai.InternalServerError:
    return openai.InternalServerError(
        "boom", response=httpx.Response(500, request=_REQUEST), body=None
    )


class _Completions:
    def __init__(self, script: list[Any]) -> None:
        self.script = list(script)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if not self.script:
            raise AssertionError("FakeOpenAI has no scripted answer left")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return types.SimpleNamespace(
            model="fake-model-1",
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=item))],
            usage=types.SimpleNamespace(prompt_tokens=12, completion_tokens=7),
        )


class FakeOpenAI:
    """Scripted ``chat.completions.create``: each item is answer text or an exception to raise."""

    def __init__(self, script: list[Any]) -> None:
        self.chat = types.SimpleNamespace(completions=_Completions(script))
        self.options: list[dict[str, Any]] = []

    def with_options(self, **options: Any) -> "FakeOpenAI":
        self.options.append(options)
        return self

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self.chat.completions.calls


class Recorder:
    def __init__(self, result: Any = None) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.result = result

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        return self.result


@pytest.fixture(autouse=True)
def no_mlflow_server(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Keep every test away from a tracking server; record experiment and trace names."""
    recorded: dict[str, Any] = {"experiments": [], "traces": []}

    def fake_set_experiment(name: str | None = None, **_: Any) -> None:
        recorded["experiments"].append(name)

    def fake_trace(func: Any = None, name: str | None = None, **_: Any) -> Any:
        def decorate(f: Any) -> Any:
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                recorded["traces"].append(name)
                return f(*args, **kwargs)

            return wrapper

        return decorate(func) if func is not None else decorate

    monkeypatch.setattr(mlflow, "set_experiment", fake_set_experiment)
    monkeypatch.setattr(mlflow, "trace", fake_trace)
    return recorded


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    waits: list[float] = []
    monkeypatch.setattr(gateway_repository.time, "sleep", waits.append)
    return waits


def make_repo(
    settings: Settings, client: FakeOpenAI, template: str = "Classify: {{segments}}"
) -> GatewayRepository:
    return GatewayRepository(settings, client=client, prompt_loader=lambda name: template)


def triage(repo: GatewayRepository, variables: dict[str, str] | None = None) -> Any:
    if variables is None:
        variables = {"segments": "M1: hello", "result_summary": ""}
    return repo.complete_json(
        "request_triage_chat", "sco_001_intent", variables, RequestTriageOutput
    )


# --- acceptance criteria -----------------------------------------------------------------------


def test_f03_ac1_valid_answer(settings: Settings, no_mlflow_server: dict[str, Any]) -> None:
    client = FakeOpenAI([VALID_ANSWER])
    repo = make_repo(settings, client)

    result, meta = triage(repo)

    assert isinstance(result, RequestTriageOutput)
    assert result.request_type == "update_pir"
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["messages"] == [
        {"role": "system", "content": SYSTEM_MESSAGE},
        {"role": "user", "content": "Classify: M1: hello"},
    ]
    assert call["model"] == "sco_001_intent"
    assert call["response_format"]["type"] == "json_schema"
    json_schema = call["response_format"]["json_schema"]
    assert set(json_schema) == {"name", "schema", "strict"}
    assert json_schema["name"] == "RequestTriageOutput"
    assert json_schema["strict"] is True
    assert_strict_objects(json_schema["schema"])
    assert json_schema["schema"]["$defs"]["Evidence"]["additionalProperties"] is False
    assert call["temperature"] == 0
    assert call["timeout"] == 60
    assert "extra_body" not in call
    assert "extra_headers" not in call
    assert isinstance(meta, CallMeta)
    assert meta.prompt_name == "request_triage_chat"
    assert meta.endpoint == "sco_001_intent"
    assert meta.retries == 0
    assert meta.model == "fake-model-1"
    assert meta.input_tokens == 12
    assert meta.output_tokens == 7
    assert meta.latency_ms >= 0
    assert no_mlflow_server["experiments"] == ["/Shared/SCO-001/pir_sl_chat"]
    assert no_mlflow_server["traces"] == ["gateway.request_triage_chat"]


def test_f03_ac2_schema_retry(settings: Settings) -> None:
    client = FakeOpenAI(['{"request_type": "banana"}', VALID_ANSWER])

    result, meta = triage(make_repo(settings, client))

    assert result.request_type == "update_pir"
    assert meta.retries == 1
    assert len(client.calls) == 2


def test_f03_ac3_rate_limit(settings: Settings, sleeps: list[float]) -> None:
    client = FakeOpenAI([rate_limit_error(), rate_limit_error()])

    with pytest.raises(UpstreamUnavailable) as excinfo:
        triage(make_repo(settings, client))

    assert str(excinfo.value) == (
        "The AI service is busy or the monthly budget is reached; try again later"
    )
    assert len(client.calls) == 2
    assert sleeps == [2]


def test_f03_ac4_register_prompts(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    registered: list[dict[str, Any]] = []
    aliases: list[dict[str, Any]] = []

    def fake_register_prompt(name: str, template: str, commit_message: str | None = None) -> Any:
        registered.append({"name": name, "template": template, "commit_message": commit_message})
        return types.SimpleNamespace(name=name, version=1)

    def fake_set_prompt_alias(name: str, alias: str, version: int) -> None:
        aliases.append({"name": name, "alias": alias, "version": version})

    def fake_git(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, stdout="abc1234\n", stderr="")

    monkeypatch.setattr(mlflow.genai, "register_prompt", fake_register_prompt)
    monkeypatch.setattr(mlflow.genai, "set_prompt_alias", fake_set_prompt_alias)
    monkeypatch.setattr(register_prompts.subprocess, "run", fake_git)
    monkeypatch.setattr(register_prompts, "load_settings", lambda: settings)

    register_prompts.main(["--alias", "production"])

    expected = {
        "sandbox_others.sco_001_poc.request_triage_chat",
        "sandbox_others.sco_001_poc.line_item_extraction_chat",
    }
    assert {r["name"] for r in registered} == expected
    assert len(registered) == 2
    for record in registered:
        stem = record["name"].rsplit(".", 1)[1]
        assert record["template"] == (PROMPTS_DIR / f"{stem}.md").read_text(encoding="utf-8")
        assert record["commit_message"] == "abc1234"
    assert {a["name"] for a in aliases} == expected
    assert all(a["alias"] == "production" and a["version"] == 1 for a in aliases)
    out = capsys.readouterr().out
    for name in expected:
        assert f"{name} version=1" in out


# --- edge cases (contract §7) and supporting behaviour ------------------------------------------


def test_f03_schema_violation_twice(settings: Settings) -> None:
    client = FakeOpenAI(['{"request_type": "banana"}', "not json at all"])

    with pytest.raises(UpstreamUnavailable) as excinfo:
        triage(make_repo(settings, client))

    assert str(excinfo.value) == (
        "Model output did not match schema RequestTriageOutput after 1 retry"
    )
    assert len(client.calls) == 2


def test_f03_rate_limit_then_ok(settings: Settings, sleeps: list[float]) -> None:
    client = FakeOpenAI([rate_limit_error(), VALID_ANSWER])

    result, meta = triage(make_repo(settings, client))

    assert result.request_type == "update_pir"
    assert meta.retries == 1
    assert sleeps == [2]
    assert len(client.calls) == 2


def test_f03_timeout(settings: Settings, sleeps: list[float]) -> None:
    client = FakeOpenAI([timeout_error()])

    with pytest.raises(UpstreamUnavailable) as excinfo:
        triage(make_repo(settings, client))

    assert str(excinfo.value) == "The AI service did not answer within 60 seconds"
    assert len(client.calls) == 1
    assert sleeps == []


def test_f03_other_api_error_is_upstream_unavailable(settings: Settings) -> None:
    client = FakeOpenAI([server_error()])

    with pytest.raises(UpstreamUnavailable):
        triage(make_repo(settings, client))
    assert len(client.calls) == 1


def test_f03_empty_variables(settings: Settings) -> None:
    client = FakeOpenAI([VALID_ANSWER])

    with pytest.raises(ValueError) as excinfo:
        triage(make_repo(settings, client), variables={})

    assert str(excinfo.value) == "Prompt variable segments missing"
    assert client.calls == []


def test_f03_variable_values_are_not_rendered_again(settings: Settings) -> None:
    client = FakeOpenAI([VALID_ANSWER])
    repo = make_repo(settings, client, template="A {{segments}} B {{result_summary}}")

    triage(repo, variables={"segments": "{{result_summary}}", "result_summary": "x"})

    assert client.calls[0]["messages"][1]["content"] == "A {{result_summary}} B x"


def test_f03_prompt_missing(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_load_prompt(uri: str, **_: Any) -> None:
        return None

    monkeypatch.setattr(mlflow.genai, "load_prompt", fake_load_prompt)
    client = FakeOpenAI([VALID_ANSWER])
    repo = GatewayRepository(settings, client=client)

    with pytest.raises(ValueError) as excinfo:
        triage(repo)

    assert str(excinfo.value) == "Prompt request_triage_chat@production not found"
    assert client.calls == []


def test_f03_prompt_registry_error_is_not_found(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_load_prompt(uri: str, **_: Any) -> None:
        raise mlflow.exceptions.MlflowException("RESOURCE_DOES_NOT_EXIST")

    monkeypatch.setattr(mlflow.genai, "load_prompt", fake_load_prompt)
    repo = GatewayRepository(settings, client=FakeOpenAI([]))

    with pytest.raises(ValueError, match="^Prompt request_triage_chat@production not found$"):
        triage(repo)


def test_f03_default_loader_uri_version_and_cache(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    uris: list[str] = []

    def fake_load_prompt(uri: str, **_: Any) -> Any:
        uris.append(uri)
        return types.SimpleNamespace(template="Classify: {{segments}}", version=3)

    now = [1000.0]
    monkeypatch.setattr(mlflow.genai, "load_prompt", fake_load_prompt)
    monkeypatch.setattr(gateway_repository, "_monotonic", lambda: now[0])
    client = FakeOpenAI([VALID_ANSWER, VALID_ANSWER, VALID_ANSWER])
    repo = GatewayRepository(settings, client=client)

    _, meta = triage(repo)
    triage(repo)
    assert uris == ["prompts:/sandbox_others.sco_001_poc.request_triage_chat@production"]
    assert meta.prompt_version == 3

    now[0] += PROMPT_CACHE_SECONDS + 1
    triage(repo)
    assert len(uris) == 2
    assert PROMPT_CACHE_SECONDS == 3600


def test_f03_default_client_uses_workspace_client(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_client = FakeOpenAI([])

    class FakeWorkspaceClient:
        def __init__(self) -> None:
            self.serving_endpoints = types.SimpleNamespace(get_open_ai_client=lambda: fake_client)

    monkeypatch.setitem(
        sys.modules, "databricks.sdk", types.SimpleNamespace(WorkspaceClient=FakeWorkspaceClient)
    )

    repo = GatewayRepository(settings, prompt_loader=lambda name: "x")

    assert repo.client is fake_client


def test_f03_tracing_errors_are_ignored(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("tracking server down")

    monkeypatch.setattr(mlflow, "set_experiment", broken)
    monkeypatch.setattr(mlflow, "trace", broken)
    client = FakeOpenAI([VALID_ANSWER])

    with caplog.at_level(logging.WARNING, logger=gateway_repository.__name__):
        repo = make_repo(settings, client)
        result, _ = triage(repo)

    assert result.request_type == "update_pir"
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 2


def test_f03_logs_never_contain_prompt_or_output(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    client = FakeOpenAI(['{"request_type": "banana"}', VALID_ANSWER])
    repo = make_repo(settings, client, template="SECRET-PROMPT {{segments}}")

    with caplog.at_level(logging.DEBUG, logger=gateway_repository.__name__):
        triage(repo, variables={"segments": "PRICE-7000", "result_summary": ""})

    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "request_triage_chat" in text
    assert "sco_001_intent" in text
    assert "SECRET-PROMPT" not in text
    assert "PRICE-7000" not in text
    assert "banana" not in text
    assert "update_pir" not in text


def test_f03_call_meta_matches_fake(settings: Settings) -> None:
    real = set(CallMeta.__dataclass_fields__)
    fake = set(FakeCallMeta.__dataclass_fields__)
    assert real == fake


def test_f03_register_only_and_git_fallback(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    registered: list[tuple[str, str | None]] = []

    def fake_register_prompt(name: str, template: str, commit_message: str | None = None) -> Any:
        registered.append((name, commit_message))
        return types.SimpleNamespace(version=4)

    def no_git(*args: Any, **kwargs: Any) -> Any:
        raise FileNotFoundError("git")

    monkeypatch.setattr(mlflow.genai, "register_prompt", fake_register_prompt)
    monkeypatch.setattr(mlflow.genai, "set_prompt_alias", Recorder())
    monkeypatch.setattr(register_prompts.subprocess, "run", no_git)

    result = register_prompts.register_prompts(
        settings, alias="production", only="request_triage_chat"
    )

    assert registered == [("sandbox_others.sco_001_poc.request_triage_chat", "unknown")]
    assert result == [("sandbox_others.sco_001_poc.request_triage_chat", 4)]
    with pytest.raises(ValueError):
        register_prompts.register_prompts(settings, alias="production", only="nope")


@pytest.mark.parametrize(
    ("stem", "variables"),
    [
        ("request_triage_chat", {"segments", "result_summary", "request_type_labels"}),
        ("line_item_extraction_chat", {"segments", "pir_fields", "sl_fields", "request_type"}),
    ],
)
def test_f03_prompt_files_use_only_listed_variables(stem: str, variables: set[str]) -> None:
    text = (PROMPTS_DIR / f"{stem}.md").read_text(encoding="utf-8")
    assert set(re.findall(r"\{\{\s*(\w+)\s*\}\}", text)) == variables


def test_f03_response_format_schema_is_json_serialisable(settings: Settings) -> None:
    client = FakeOpenAI([VALID_ANSWER])
    triage(make_repo(settings, client))
    json.dumps(client.calls[0]["response_format"])


# --- strict-compatible response schema (fix round 1) --------------------------------------------


def assert_strict_objects(node: Any) -> None:
    """Every object node with ``properties`` is closed and requires all its keys; no defaults."""
    if isinstance(node, dict):
        assert "default" not in node
        if "properties" in node:
            assert node["additionalProperties"] is False
            assert sorted(node["required"]) == sorted(node["properties"])
        for value in node.values():
            assert_strict_objects(value)
    elif isinstance(node, list):
        for item in node:
            assert_strict_objects(item)


class Candidate(BaseModel):
    value: str
    derivation: Literal["literal", "computed"] = "literal"
    computation: str | None = None


class LineItem(BaseModel):
    doc_type: Literal["PIR", "SL"]
    fields: dict[str, list[Candidate]] = Field(default_factory=dict)


class MapOutput(BaseModel):
    line_items: list[LineItem]
    notes: list[str] = Field(default_factory=list)


MAP_ANSWER = (
    '{"line_items":[{"doc_type":"PIR","fields":{"plant":[{"value":"1000",'
    '"derivation":"literal","computation":null}]}}],"notes":[]}'
)


def sent_schema(settings: Settings, schema: type[BaseModel], answer: str) -> dict[str, Any]:
    client = FakeOpenAI([answer])
    repo = make_repo(settings, client)
    repo.complete_json("line_item_extraction_chat", "sco_001_extract", {"segments": "s"}, schema)
    return client.calls[0]["response_format"]["json_schema"]["schema"]


def test_f03_strict_schema_top_and_defs_objects(settings: Settings) -> None:
    schema = sent_schema(settings, RequestTriageOutput, VALID_ANSWER)

    assert schema["additionalProperties"] is False
    assert sorted(schema["required"]) == sorted(
        ["request_type", "message_kind", "reason", "evidence"]
    )
    evidence = schema["$defs"]["Evidence"]
    assert evidence["additionalProperties"] is False
    assert sorted(evidence["required"]) == ["segment_id", "text"]
    assert schema["properties"]["reason"]["maxLength"] == 300  # constraints are kept
    assert_strict_objects(schema)


def test_f03_strict_schema_defaults_dropped_and_maps_kept(settings: Settings) -> None:
    schema = sent_schema(settings, MapOutput, MAP_ANSWER)

    assert_strict_objects(schema)
    assert sorted(schema["required"]) == ["line_items", "notes"]
    candidate = schema["$defs"]["Candidate"]
    assert sorted(candidate["required"]) == ["computation", "derivation", "value"]
    assert "default" not in candidate["properties"]["derivation"]
    assert {"type": "null"} in candidate["properties"]["computation"]["anyOf"]
    fields = schema["$defs"]["LineItem"]["properties"]["fields"]
    assert fields["type"] == "object"
    assert "properties" not in fields
    assert "required" not in fields
    assert fields["additionalProperties"] == {
        "items": {"$ref": "#/$defs/Candidate"},
        "type": "array",
    }


def test_f03_strict_schema_does_not_mutate_model_schema(settings: Settings) -> None:
    before = json.dumps(MapOutput.model_json_schema(), sort_keys=True)
    original = MapOutput.model_json_schema()

    sent = sent_schema(settings, MapOutput, MAP_ANSWER)

    assert json.dumps(MapOutput.model_json_schema(), sort_keys=True) == before
    assert "additionalProperties" not in original
    assert sent is not original


def test_f03_strict_schema_answer_still_validated_locally(settings: Settings) -> None:
    client = FakeOpenAI([MAP_ANSWER])
    result, meta = make_repo(settings, client).complete_json(
        "line_item_extraction_chat", "sco_001_extract", {"segments": "s"}, MapOutput
    )
    assert isinstance(result, MapOutput)
    assert result.line_items[0].fields["plant"][0].value == "1000"
    assert meta.retries == 0


# --- fix round 2: SDK retries, DEBUG logging, runtime tracing failures, missing variables -------

QUIET_LOGGERS = ("openai", "httpx", "httpcore")


@pytest.fixture
def reset_http_loggers() -> Any:
    """Start from unset levels on the SDK loggers and restore them afterwards."""
    saved = {name: logging.getLogger(name).level for name in QUIET_LOGGERS}
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.NOTSET)
    yield
    for name, level in saved.items():
        logging.getLogger(name).setLevel(level)


def completion_body(content: str) -> dict[str, Any]:
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 0,
        "model": "real-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
    }


def real_client(handler: Any) -> tuple[openai.OpenAI, list[httpx.Request]]:
    """A real OpenAI client over httpx.MockTransport: no network, every request recorded."""
    requests: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    client = openai.OpenAI(
        api_key="x",
        base_url="http://test.invalid/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(record)),
    )
    return client, requests


def test_f03_default_client_disables_sdk_retries(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_client = FakeOpenAI([])

    class FakeWorkspaceClient:
        def __init__(self) -> None:
            self.serving_endpoints = types.SimpleNamespace(get_open_ai_client=lambda: fake_client)

    monkeypatch.setitem(
        sys.modules, "databricks.sdk", types.SimpleNamespace(WorkspaceClient=FakeWorkspaceClient)
    )

    GatewayRepository(settings, prompt_loader=lambda name: "x")

    assert fake_client.options == [{"max_retries": 0}]


def test_f03_injected_client_disables_sdk_retries(settings: Settings) -> None:
    client = FakeOpenAI([VALID_ANSWER])
    make_repo(settings, client)
    assert client.options == [{"max_retries": 0}]

    real, _ = real_client(lambda request: httpx.Response(200, json=completion_body(VALID_ANSWER)))
    repo = make_repo(settings, real)  # type: ignore[arg-type]
    assert repo.client.max_retries == 0


def test_f03_real_client_rate_limit_twice_makes_two_requests(
    settings: Settings, sleeps: list[float]
) -> None:
    client, requests = real_client(
        lambda request: httpx.Response(429, json={"error": {"message": "rate limited"}})
    )

    with pytest.raises(UpstreamUnavailable) as excinfo:
        triage(make_repo(settings, client))  # type: ignore[arg-type]

    assert str(excinfo.value) == (
        "The AI service is busy or the monthly budget is reached; try again later"
    )
    assert len(requests) == 2
    assert sleeps == [2]


def test_f03_real_client_timeout_is_not_retried(settings: Settings, sleeps: list[float]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client, requests = real_client(handler)

    with pytest.raises(UpstreamUnavailable) as excinfo:
        triage(make_repo(settings, client))  # type: ignore[arg-type]

    assert str(excinfo.value) == "The AI service did not answer within 60 seconds"
    assert len(requests) == 1
    assert sleeps == []


def test_f03_real_client_debug_logs_never_contain_prompt_or_output(
    settings: Settings, caplog: pytest.LogCaptureFixture, reset_http_loggers: None
) -> None:
    answer = (
        '{"request_type":"update_pir","message_kind":"request_content",'
        '"reason":"RESPONSE-MARKER","evidence":[]}'
    )
    client, requests = real_client(
        lambda request: httpx.Response(200, json=completion_body(answer))
    )

    with caplog.at_level(logging.DEBUG):
        repo = make_repo(settings, client, template="SECRET-PROMPT {{segments}}")  # type: ignore[arg-type]
        result, meta = triage(repo, variables={"segments": "PRICE-7000", "result_summary": ""})

    assert result.reason == "RESPONSE-MARKER"
    assert meta.model == "real-model"
    assert len(requests) == 1
    assert b"SECRET-PROMPT" in requests[0].content  # the prompt was really sent
    text = "\n".join(
        f"{r.name} {r.getMessage()} {r.args!r} {getattr(r, '__dict__', {})!r}"
        for r in caplog.records
    )
    assert "gateway call" in text
    for marker in ("SECRET-PROMPT", "PRICE-7000", "RESPONSE-MARKER"):
        assert marker not in text


def _trace_stub(mode: str) -> Any:
    def fake_trace(func: Any = None, name: str | None = None, **_: Any) -> Any:
        def decorate(f: Any) -> Any:
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                if mode == "before":
                    raise RuntimeError("trace start failed")
                f(*args, **kwargs)
                raise RuntimeError("trace output capture failed")

            return wrapper

        return decorate(func) if func is not None else decorate

    return fake_trace


def test_f03_tracing_failure_after_call_keeps_result(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(mlflow, "trace", _trace_stub("after"))
    client = FakeOpenAI([VALID_ANSWER])

    with caplog.at_level(logging.WARNING, logger=gateway_repository.__name__):
        result, meta = triage(make_repo(settings, client))

    assert result.request_type == "update_pir"
    assert meta.retries == 0
    assert len(client.calls) == 1
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == ["MLflow tracing failed: RuntimeError"]


def test_f03_tracing_failure_before_call_runs_untraced(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(mlflow, "trace", _trace_stub("before"))
    client = FakeOpenAI([VALID_ANSWER])

    with caplog.at_level(logging.WARNING, logger=gateway_repository.__name__):
        result, _ = triage(make_repo(settings, client))

    assert result.request_type == "update_pir"
    assert len(client.calls) == 1
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == ["MLflow tracing failed: RuntimeError"]


def test_f03_tracing_failure_reraises_inner_error(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def fake_trace(func: Any = None, name: str | None = None, **_: Any) -> Any:
        def decorate(f: Any) -> Any:
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    return f(*args, **kwargs)
                except UpstreamUnavailable:
                    raise RuntimeError("trace error handling failed") from None

            return wrapper

        return decorate

    monkeypatch.setattr(mlflow, "trace", fake_trace)
    client = FakeOpenAI([timeout_error()])

    with (
        caplog.at_level(logging.WARNING, logger=gateway_repository.__name__),
        pytest.raises(UpstreamUnavailable, match="^The AI service did not answer within 60"),
    ):
        triage(make_repo(settings, client))
    assert len(client.calls) == 1
    warnings = [
        r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING and r.name == gateway_repository.__name__
    ]
    assert "MLflow tracing failed: RuntimeError" in warnings


@pytest.mark.parametrize("stem", ["request_triage_chat", "line_item_extraction_chat"])
def test_f03_empty_variables_with_shipped_prompts(settings: Settings, stem: str) -> None:
    template = (PROMPTS_DIR / f"{stem}.md").read_text(encoding="utf-8")
    client = FakeOpenAI([VALID_ANSWER])
    repo = make_repo(settings, client, template=template)

    with pytest.raises(ValueError) as excinfo:
        triage(repo, variables={})

    assert str(excinfo.value) == "Prompt variable segments missing"
    assert client.calls == []


def test_f03_other_missing_variable_named_when_segments_given(settings: Settings) -> None:
    template = (PROMPTS_DIR / "request_triage_chat.md").read_text(encoding="utf-8")
    repo = make_repo(settings, FakeOpenAI([]), template=template)

    with pytest.raises(ValueError, match="^Prompt variable result_summary missing$"):
        triage(repo, variables={"segments": "M1: hello", "request_type_labels": "x"})


# --- fix round 3: explicit DEBUG on SDK child loggers; strict only when strict-compatible -------

DEBUG_CHILD_LOGGERS = ("openai._base_client", "httpx._client", "httpcore.http11")


@pytest.fixture
def debug_child_loggers() -> Any:
    """Explicitly set SDK child loggers to DEBUG; restore every touched level afterwards."""
    names = QUIET_LOGGERS + DEBUG_CHILD_LOGGERS
    saved = {name: logging.getLogger(name).level for name in names}
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.NOTSET)
    for name in DEBUG_CHILD_LOGGERS:
        logging.getLogger(name).setLevel(logging.DEBUG)
    yield
    for name, level in saved.items():
        logging.getLogger(name).setLevel(level)


def test_f03_explicit_debug_child_loggers_never_log_prompt_or_output(
    settings: Settings, caplog: pytest.LogCaptureFixture, debug_child_loggers: None
) -> None:
    answer = (
        '{"request_type":"update_pir","message_kind":"request_content",'
        '"reason":"RESPONSE-MARKER","evidence":[]}'
    )
    client, requests = real_client(
        lambda request: httpx.Response(200, json=completion_body(answer))
    )
    levels_before = {
        name: logging.getLogger(name).level for name in QUIET_LOGGERS + DEBUG_CHILD_LOGGERS
    }

    with caplog.at_level(logging.DEBUG):
        repo = make_repo(settings, client, template="SECRET-PROMPT {{segments}}")  # type: ignore[arg-type]
        result, _ = triage(repo, variables={"segments": "PRICE-7000", "result_summary": ""})

    assert result.reason == "RESPONSE-MARKER"
    assert b"SECRET-PROMPT" in requests[0].content  # the prompt was really sent
    text = "\n".join(
        f"{r.name} {r.getMessage()} {r.args!r} {getattr(r, '__dict__', {})!r}"
        for r in caplog.records
    )
    assert "gateway call" in text
    for marker in ("SECRET-PROMPT", "PRICE-7000", "RESPONSE-MARKER"):
        assert marker not in text
    levels_after = {
        name: logging.getLogger(name).level for name in QUIET_LOGGERS + DEBUG_CHILD_LOGGERS
    }
    assert levels_after == levels_before
    assert logging.getLogger("openai._base_client").level == logging.DEBUG


def test_f03_debug_child_loggers_restored_after_failed_call(
    settings: Settings, sleeps: list[float], debug_child_loggers: None
) -> None:
    client, _ = real_client(
        lambda request: httpx.Response(429, json={"error": {"message": "rate limited"}})
    )

    with pytest.raises(UpstreamUnavailable):
        triage(make_repo(settings, client))  # type: ignore[arg-type]

    for name in DEBUG_CHILD_LOGGERS:
        assert logging.getLogger(name).level == logging.DEBUG


def test_f03_strict_true_for_strict_compatible_schema(settings: Settings) -> None:
    client = FakeOpenAI([VALID_ANSWER])
    triage(make_repo(settings, client))
    assert client.calls[0]["response_format"]["json_schema"]["strict"] is True


def test_f03_strict_false_when_schema_has_free_form_map(settings: Settings) -> None:
    client = FakeOpenAI([MAP_ANSWER])
    result, _ = make_repo(settings, client).complete_json(
        "line_item_extraction_chat", "sco_001_extract", {"segments": "s"}, MapOutput
    )
    json_schema = client.calls[0]["response_format"]["json_schema"]
    assert json_schema["strict"] is False
    assert json_schema["name"] == "MapOutput"
    assert_strict_objects(json_schema["schema"])  # same strict-compatible copy is sent
    assert isinstance(result, MapOutput)


class ItemsMapOutput(BaseModel):
    rows: list[dict[str, str]]


class AnyOfMapOutput(BaseModel):
    extra: dict[str, int] | None = None


class ClosedOnly(BaseModel):
    evidence: list[Evidence]
    note: str | None = None


@pytest.mark.parametrize(
    ("schema", "expected"),
    [
        (RequestTriageOutput, False),
        (ClosedOnly, False),
        (MapOutput, True),  # map inside $defs.LineItem.properties.fields
        (ItemsMapOutput, True),  # map inside items
        (AnyOfMapOutput, True),  # map inside anyOf
    ],
)
def test_f03_free_form_map_detection(schema: type[BaseModel], expected: bool) -> None:
    sent = gateway_repository.strict_json_schema(schema)
    assert gateway_repository.has_free_form_map(sent) is expected


def test_f03_free_form_map_detection_on_raw_nodes() -> None:
    has_map = gateway_repository.has_free_form_map
    assert has_map({"$defs": {"M": {"type": "object", "additionalProperties": {"type": "string"}}}})
    assert has_map({"items": {"type": "object", "additionalProperties": True}})
    assert has_map({"anyOf": [{"type": "object"}, {"type": "null"}]})
    assert not has_map(
        {"type": "object", "properties": {"a": {"type": "string"}}, "additionalProperties": False}
    )
    # a property *named* like a keyword is not a schema node
    assert not has_map(
        {
            "type": "object",
            "properties": {"additionalProperties": {"type": "string"}},
            "additionalProperties": False,
            "required": ["additionalProperties"],
        }
    )


# --- fix round 4: only JSON-Schema subschema positions are walked, never data values ------------

MAP_LIKE_EXAMPLE = {"type": "object"}
MAP_LIKE_EXTRA_EXAMPLE = {"additionalProperties": {}}
CLOSED_LIKE_EXAMPLE = {"properties": {"x": {"default": 1}}, "default": "kept"}


class ExamplesOnlyOutput(BaseModel):
    """Closed model whose annotations hold map-like *data*, not map schemas."""

    label: str = Field(examples=[MAP_LIKE_EXAMPLE])
    note: str = Field(json_schema_extra={"examples": [MAP_LIKE_EXTRA_EXAMPLE]})


class DataDefaultsOutput(BaseModel):
    payload: str = Field(
        default="x",
        json_schema_extra={
            "example": {"type": "object", "additionalProperties": True},
            "const_like": {"type": "object"},
        },
    )
    shape: str = Field(json_schema_extra={"examples": [CLOSED_LIKE_EXAMPLE]})


def test_f03_examples_data_is_not_a_free_form_map(settings: Settings) -> None:
    sent = gateway_repository.strict_json_schema(ExamplesOnlyOutput)
    assert gateway_repository.has_free_form_map(sent) is False

    client = FakeOpenAI(['{"label":"a","note":"b"}'])
    make_repo(settings, client).complete_json(
        "line_item_extraction_chat", "sco_001_extract", {"segments": "s"}, ExamplesOnlyOutput
    )
    assert client.calls[0]["response_format"]["json_schema"]["strict"] is True


def test_f03_default_and_extra_data_is_not_a_free_form_map() -> None:
    sent = gateway_repository.strict_json_schema(DataDefaultsOutput)
    assert gateway_repository.has_free_form_map(sent) is False


def test_f03_free_form_map_detection_ignores_data_keywords() -> None:
    has_map = gateway_repository.has_free_form_map
    closed = {"type": "object", "properties": {}, "additionalProperties": False}
    for keyword in ("examples", "example", "default", "const", "enum"):
        node = dict(closed, **{keyword: [{"type": "object", "additionalProperties": True}]})
        assert has_map(node) is False, keyword
    assert has_map(dict(closed, title={"type": "object"}, description={"type": "object"})) is False
    assert has_map(dict(closed, x_custom={"type": "object"})) is False


@pytest.mark.parametrize(
    "position",
    [
        lambda m: {"properties": {"a": m}, "additionalProperties": False},
        lambda m: {"patternProperties": {"^a": m}},
        lambda m: {"type": "object", "properties": {}, "additionalProperties": {"items": m}},
        lambda m: {"items": m},
        lambda m: {"prefixItems": [{"type": "string"}, m]},
        lambda m: {"anyOf": [m]},
        lambda m: {"oneOf": [m]},
        lambda m: {"allOf": [m]},
        lambda m: {"not": m},
        lambda m: {"if": m},
        lambda m: {"then": m},
        lambda m: {"else": m},
        lambda m: {"$defs": {"M": m}},
        lambda m: {"definitions": {"M": m}},
        lambda m: {"contains": m},
    ],
)
def test_f03_free_form_map_detection_in_every_subschema_position(position: Any) -> None:
    free_form = {"type": "object", "additionalProperties": {"type": "string"}}
    assert gateway_repository.has_free_form_map(position(free_form)) is True


def test_f03_make_strict_leaves_examples_data_untouched() -> None:
    original = DataDefaultsOutput.model_json_schema()
    sent = gateway_repository.strict_json_schema(DataDefaultsOutput)

    for field in ("payload", "shape"):
        for keyword in ("examples", "example", "const_like"):
            if keyword in original["properties"][field]:
                assert json.dumps(sent["properties"][field][keyword], sort_keys=True) == (
                    json.dumps(original["properties"][field][keyword], sort_keys=True)
                )
    assert sent["properties"]["shape"]["examples"] == [CLOSED_LIKE_EXAMPLE]
    assert "default" not in sent["properties"]["payload"]  # the schema keyword is still dropped
    sent_examples = gateway_repository.strict_json_schema(ExamplesOnlyOutput)["properties"]
    assert sent_examples["label"]["examples"] == [MAP_LIKE_EXAMPLE]
    assert sent_examples["note"]["examples"] == [MAP_LIKE_EXTRA_EXAMPLE]


def test_f03_make_strict_closes_objects_in_every_subschema_position() -> None:
    open_object = {"type": "object", "properties": {"a": {"type": "string", "default": "x"}}}
    for wrap in (
        lambda o: {"items": o},
        lambda o: {"prefixItems": [o]},
        lambda o: {"oneOf": [o]},
        lambda o: {"allOf": [o]},
        lambda o: {"definitions": {"O": o}},
        lambda o: {"patternProperties": {"^a": o}},
        lambda o: {"type": "object", "additionalProperties": o},
        lambda o: {"not": o},
        lambda o: {"if": o, "then": o, "else": o},
        lambda o: {"contains": o},
    ):
        node = wrap(copy.deepcopy(open_object))
        gateway_repository._make_strict(node)
        assert_strict_objects(node)
        found = json.dumps(node)
        assert '"additionalProperties": false' in found
        assert '"default"' not in found


# --- fix round 5: the complete set of subschema keywords (draft 2020-12, 2019-09, draft-07) -----

FREE_FORM = {"type": "object", "additionalProperties": {"type": "string"}}
OPEN_OBJECT = {"type": "object", "properties": {"a": {"type": "string", "default": "x"}}}

NEW_POSITIONS = {
    "dependentSchemas": lambda m: {"dependentSchemas": {"a": m}},
    "dependencies": lambda m: {"dependencies": {"a": m}},
    "additionalItems": lambda m: {"additionalItems": m},
    "unevaluatedItems": lambda m: {"unevaluatedItems": m},
    "unevaluatedProperties": lambda m: {"unevaluatedProperties": m},
    "propertyNames": lambda m: {"propertyNames": m},
    "contentSchema": lambda m: {"contentSchema": m},
}


@pytest.mark.parametrize("keyword", sorted(NEW_POSITIONS))
def test_f03_free_form_map_detected_under_every_subschema_keyword(keyword: str) -> None:
    node = NEW_POSITIONS[keyword](copy.deepcopy(FREE_FORM))
    assert gateway_repository.has_free_form_map(node) is True


@pytest.mark.parametrize("keyword", sorted(NEW_POSITIONS))
def test_f03_make_strict_closes_objects_under_every_subschema_keyword(keyword: str) -> None:
    node = NEW_POSITIONS[keyword](copy.deepcopy(OPEN_OBJECT))
    gateway_repository._make_strict(node)
    found = json.dumps(node)
    assert '"additionalProperties": false' in found
    assert '"required": ["a"]' in found
    assert '"default"' not in found
    assert_strict_objects(node)


class DependentSchemasOutput(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "dependentSchemas": {"label": {"type": "object", "additionalProperties": {}}}
        }
    )

    label: str


def test_f03_dependent_schemas_map_sends_strict_false(settings: Settings) -> None:
    client = FakeOpenAI(['{"label":"a"}'])
    result, _ = make_repo(settings, client).complete_json(
        "line_item_extraction_chat", "sco_001_extract", {"segments": "s"}, DependentSchemasOutput
    )
    json_schema = client.calls[0]["response_format"]["json_schema"]
    assert "dependentSchemas" in json_schema["schema"]
    assert json_schema["strict"] is False
    assert result.label == "a"


def test_f03_dependencies_list_value_is_data() -> None:
    node = {
        "type": "object",
        "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
        "dependencies": {"a": ["b"], "b": {"type": "object"}},
    }
    original_list = copy.deepcopy(node["dependencies"]["a"])

    gateway_repository._make_strict(node)

    assert node["dependencies"]["a"] == original_list == ["b"]
    assert (
        gateway_repository.has_free_form_map(
            {"dependencies": {"a": ["b"]}, "type": "object", "properties": {}}
        )
        is False
    )
    # the dict value of dependencies is a subschema and is walked
    assert gateway_repository.has_free_form_map(node) is True


def test_f03_boolean_subschemas_are_not_walked() -> None:
    node = {
        "type": "object",
        "properties": {"a": {"type": "string"}},
        "additionalProperties": False,
        "unevaluatedProperties": False,
        "propertyNames": True,
        "contentSchema": False,
    }
    before = copy.deepcopy(node)
    assert gateway_repository.has_free_form_map(node) is False
    gateway_repository._make_strict(node)
    assert {k: v for k, v in node.items() if k != "required"} == before


def test_f03_unknown_keywords_are_never_walked() -> None:
    map_like = {"type": "object", "additionalProperties": {"type": "string"}}
    open_like = {"type": "object", "properties": {"x": {"default": 1}}}
    node = {
        "type": "object",
        "properties": {"a": {"type": "string"}},
        "additionalProperties": False,
        "x-vendor": copy.deepcopy(map_like),
        "discriminator": {"propertyName": "a", "mapping": copy.deepcopy(map_like)},
        "dependentRequired": {"a": ["b"]},
        "custom": copy.deepcopy(open_like),
    }

    assert gateway_repository.has_free_form_map(node) is False
    gateway_repository._make_strict(node)
    assert node["x-vendor"] == map_like
    assert node["discriminator"]["mapping"] == map_like
    assert node["custom"] == open_like
    assert node["dependentRequired"] == {"a": ["b"]}


def test_f03_subschema_keyword_sets_are_complete() -> None:
    single = {
        "additionalProperties",
        "items",
        "additionalItems",
        "unevaluatedItems",
        "unevaluatedProperties",
        "propertyNames",
        "contains",
        "not",
        "if",
        "then",
        "else",
        "contentSchema",
    }
    lists = {"prefixItems", "allOf", "anyOf", "oneOf"}
    maps = {"properties", "patternProperties", "$defs", "definitions", "dependentSchemas"}
    assert set(gateway_repository._SUBSCHEMA_KEYS) == single
    assert set(gateway_repository._SUBSCHEMA_LIST_KEYS) == lists
    assert set(gateway_repository._SUBSCHEMA_MAP_KEYS) == maps
    known = single | lists | maps | {"dependencies"}
    assert not known & set(gateway_repository._NON_SUBSCHEMA_KEYS)
