"""All model calls of the app (v1/F-03): prompt by alias, gateway endpoint, JSON schema, retries.

Never logs prompt text or model output (TSD §11.2); logs prompt_name, endpoint, latency_ms,
retries and status only.
"""

import copy
import logging
import re
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import mlflow
import openai
from pydantic import BaseModel, ValidationError

from backend.config import Settings
from backend.constants import (
    LLM_RATE_LIMIT_RETRIES,
    LLM_RATE_LIMIT_WAIT_SECONDS,
    LLM_SCHEMA_RETRIES,
    LLM_TIMEOUT_SECONDS,
)
from backend.errors import UpstreamUnavailable

if TYPE_CHECKING:
    from openai import OpenAI

logger = logging.getLogger(__name__)

PROMPT_CACHE_SECONDS = 3600
SYSTEM_MESSAGE = "You answer only with JSON that matches the given schema."
UNKNOWN_PROMPT_VERSION = 0  # reported when an injected prompt_loader gives no version

BUSY_MESSAGE = "The AI service is busy or the monthly budget is reached; try again later"
TIMEOUT_MESSAGE = f"The AI service did not answer within {LLM_TIMEOUT_SECONDS} seconds"

_VARIABLE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
FIRST_VARIABLE = "segments"  # every prompt uses it; reported first when missing
# The OpenAI SDK logs full request options (the rendered prompt) at DEBUG on "openai._base_client";
# httpx / httpcore log request details at DEBUG. While a model call runs, every existing logger in
# these namespaces (the roots and any child, even one set to DEBUG explicitly) is raised to at
# least INFO; the exact previous levels are restored when the last concurrent call ends.
QUIET_LOGGERS = ("openai", "httpx", "httpcore")
_quiet_lock = threading.Lock()
_quiet_depth = 0
_quiet_saved: dict[str, int] = {}


def _sdk_loggers() -> list[logging.Logger]:
    names = set(QUIET_LOGGERS)
    for name, item in list(logging.Logger.manager.loggerDict.items()):
        if isinstance(item, logging.Logger) and name.startswith(
            tuple(f"{root}." for root in QUIET_LOGGERS)
        ):
            names.add(name)
    return [logging.getLogger(name) for name in sorted(names)]


@contextmanager
def _quiet_sdk_logs() -> Iterator[None]:
    """Keep the openai / httpx / httpcore loggers at INFO or above for the duration of a call."""
    global _quiet_depth
    with _quiet_lock:
        if _quiet_depth == 0:
            _quiet_saved.clear()
            for quiet in _sdk_loggers():
                _quiet_saved[quiet.name] = quiet.level
                if quiet.level < logging.INFO:
                    quiet.setLevel(logging.INFO)
        _quiet_depth += 1
    try:
        yield
    finally:
        with _quiet_lock:
            _quiet_depth -= 1
            if _quiet_depth == 0:
                for name, level in _quiet_saved.items():
                    logging.getLogger(name).setLevel(level)
                _quiet_saved.clear()


_monotonic = time.monotonic


@dataclass
class CallMeta:
    prompt_name: str
    prompt_version: int
    endpoint: str
    model: str | None
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    retries: int


def render_prompt(template: str, variables: dict[str, str]) -> str:
    """Replace every ``{{name}}`` in one pass; a missing name raises ValueError.

    ``segments`` is checked first, then the other names in template order.
    """
    missing = [name for name in _VARIABLE.findall(template) if name not in variables]
    if missing:
        name = FIRST_VARIABLE if FIRST_VARIABLE in missing else missing[0]
        raise ValueError(f"Prompt variable {name} missing")
    return _VARIABLE.sub(lambda match: variables[match.group(1)], template)


# Human-approved deviation from FEATURES_V1 v1/F-03 step 4: Databricks strict structured
# output rejects open objects.
def strict_json_schema(schema: type[BaseModel]) -> dict[str, Any]:
    """Copy of ``schema.model_json_schema()`` accepted by strict structured output.

    Every object node with ``properties`` (top level, ``$defs``, ``items``, ``anyOf``, nested)
    gets ``additionalProperties: false`` and ``required`` = all its property keys; ``default``
    keys are dropped. Object nodes without ``properties`` (free-form maps) keep their
    ``additionalProperties`` schema. Local ``model_validate_json`` stays the source of truth.
    """
    return _make_strict(copy.deepcopy(schema.model_json_schema()))


# Every subschema-valued JSON-Schema keyword (draft 2020-12, 2019-09 and draft-07). Only these
# positions are walked by has_free_form_map and _make_strict. Every other key holds data
# (_NON_SUBSCHEMA_KEYS) or is an unknown keyword / extension (e.g. from json_schema_extra); those
# are never descended into, so data is never treated as schema and never rewritten.
_SUBSCHEMA_KEYS = (  # a single subschema; walked only when the value is an object
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
)
_SUBSCHEMA_LIST_KEYS = ("prefixItems", "allOf", "anyOf", "oneOf")  # plus the list form of items
_SUBSCHEMA_MAP_KEYS = (  # a map whose values are subschemas
    "properties",
    "patternProperties",
    "$defs",
    "definitions",
    "dependentSchemas",
)
_DEPENDENCIES_KEY = "dependencies"  # draft-07: dict values are subschemas, list values are data
_NON_SUBSCHEMA_KEYS = (  # known keywords that hold data (documentation; never walked)
    "type", "title", "description", "default", "examples", "example", "const", "enum",
    "format", "pattern", "minLength", "maxLength", "minimum", "maximum", "exclusiveMinimum",
    "exclusiveMaximum", "multipleOf", "minItems", "maxItems", "uniqueItems", "minProperties",
    "maxProperties", "required", "$ref", "$id", "$schema", "$comment", "$anchor", "readOnly",
    "writeOnly", "deprecated", "nullable", "discriminator", "contentMediaType",
    "contentEncoding", "dependentRequired", "minContains", "maxContains",
)  # fmt: skip


def _subschemas(node: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """The direct subschemas of a schema node (JSON-Schema subschema positions only).

    Boolean schemas (``true`` / ``false``) and any non-object value are not yielded.
    """

    def objects(values: Any) -> Iterator[dict[str, Any]]:
        for value in values:
            if isinstance(value, dict):
                yield value

    for key in _SUBSCHEMA_KEYS:
        value = node.get(key)
        if isinstance(value, dict):
            yield value
        elif key == "items" and isinstance(value, list):  # draft-07 tuple form
            yield from objects(value)
    for key in _SUBSCHEMA_LIST_KEYS:
        value = node.get(key)
        if isinstance(value, list):
            yield from objects(value)
    for key in _SUBSCHEMA_MAP_KEYS:
        value = node.get(key)
        if isinstance(value, dict):
            yield from objects(value.values())
    dependencies = node.get(_DEPENDENCIES_KEY)
    if isinstance(dependencies, dict):
        yield from objects(dependencies.values())  # list values are property-name arrays


def has_free_form_map(node: Any) -> bool:
    """True when a schema node in any subschema position is an open object: no ``properties``
    and either a schema / ``true`` as ``additionalProperties`` or ``type: object`` alone
    (e.g. ``dict[str, X]``). Data-valued keywords such as ``examples`` are never inspected."""
    if not isinstance(node, dict):
        return False
    if "properties" not in node:
        extra = node.get("additionalProperties")
        if (extra is not None and extra is not False) or (
            node.get("type") == "object" and extra is None
        ):
            return True
    return any(has_free_form_map(sub) for sub in _subschemas(node))


def _make_strict(node: Any) -> Any:
    """Close objects and drop ``default`` in subschema positions only; data values stay as is."""
    if isinstance(node, dict):
        node.pop("default", None)
        for sub in _subschemas(node):
            _make_strict(sub)
        properties = node.get("properties")
        if isinstance(properties, dict):
            node["additionalProperties"] = False
            node["required"] = list(properties)
    return node


class GatewayRepository:
    def __init__(
        self,
        settings: Settings,
        client: "OpenAI | None" = None,
        prompt_loader: Callable[[str], str] | None = None,
    ) -> None:
        """client defaults to WorkspaceClient().serving_endpoints.get_open_ai_client();
        prompt_loader defaults to the Prompt Registry by alias with a 1 h cache."""
        self.settings = settings
        if client is None:
            from databricks.sdk import WorkspaceClient  # lazy: no workspace needed to import

            client = WorkspaceClient().serving_endpoints.get_open_ai_client()
        # The repository is the only retry layer: switch off the SDK's own 429 / timeout retries.
        with_options = getattr(client, "with_options", None)
        if callable(with_options):
            client = with_options(max_retries=0)
        self.client = client
        self._custom_loader = prompt_loader
        self._prompt_cache: dict[str, tuple[str, int, float]] = {}
        try:
            mlflow.set_experiment(settings.MLFLOW_EXPERIMENT)
        except Exception as exc:  # noqa: BLE001 - tracing must never break a call
            logger.warning("MLflow experiment not set: %s", type(exc).__name__)

    # --- prompts -----------------------------------------------------------------------------

    def _load_prompt(self, prompt_name: str) -> tuple[str, int]:
        if self._custom_loader is not None:
            return self._custom_loader(prompt_name), UNKNOWN_PROMPT_VERSION
        cached = self._prompt_cache.get(prompt_name)
        now = _monotonic()
        if cached is not None and now - cached[2] < PROMPT_CACHE_SECONDS:
            return cached[0], cached[1]
        alias = self.settings.PROMPT_ALIAS
        uri = f"prompts:/{self.settings.CATALOG}.{self.settings.SCHEMA}.{prompt_name}@{alias}"
        not_found = ValueError(f"Prompt {prompt_name}@{alias} not found")
        try:
            prompt = mlflow.genai.load_prompt(uri, allow_missing=True, link_to_model=False)
        except mlflow.exceptions.MlflowException:
            raise not_found from None
        if prompt is None:
            raise not_found
        template, version = prompt.template, int(prompt.version)
        self._prompt_cache[prompt_name] = (template, version, now)
        return template, version

    # --- calls -------------------------------------------------------------------------------

    def complete_json(
        self,
        prompt_name: str,
        endpoint: str,
        variables: dict[str, str],
        schema: type[BaseModel],
    ) -> tuple[BaseModel, CallMeta]:
        """Render the prompt, call ``endpoint`` with the JSON schema of ``schema``, validate.

        Retries once on a schema violation and once (after 2 s) on HTTP 429; any other failure
        raises UpstreamUnavailable(reason).
        """
        template, version = self._load_prompt(prompt_name)
        user_message = render_prompt(template, variables)

        outcome: dict[str, Any] = {}

        def call() -> tuple[BaseModel, CallMeta]:
            try:
                result = self._call(prompt_name, version, endpoint, user_message, schema)
            except Exception as exc:
                outcome["error"] = exc
                raise
            outcome["result"] = result
            return result

        try:
            traced = mlflow.trace(name=f"gateway.{prompt_name}")(call)
        except Exception as exc:  # noqa: BLE001 - tracing must never break a call
            logger.warning("MLflow tracing unavailable: %s", type(exc).__name__)
            return call()
        try:
            return traced()
        except Exception as exc:
            if "error" in outcome:  # the call itself failed: raise its error, not a tracing one
                if exc is outcome["error"]:
                    raise
                logger.warning("MLflow tracing failed: %s", type(exc).__name__)
                raise outcome["error"] from None
            logger.warning("MLflow tracing failed: %s", type(exc).__name__)
            if "result" in outcome:  # tracing failed after a successful call
                return outcome["result"]
            return call()  # tracing failed before the call ran

    def _call(
        self,
        prompt_name: str,
        prompt_version: int,
        endpoint: str,
        user_message: str,
        schema: type[BaseModel],
    ) -> tuple[BaseModel, CallMeta]:
        json_schema = strict_json_schema(schema)
        request: dict[str, Any] = {
            "model": endpoint,
            "messages": [
                {"role": "system", "content": SYSTEM_MESSAGE},
                {"role": "user", "content": user_message},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "schema": json_schema,
                    # Human-approved deviation (as strict_json_schema): strict mode rejects
                    # free-form maps, so such schemas are sent with strict False.
                    "strict": not has_free_form_map(json_schema),
                },
            },
            "temperature": 0,
            "timeout": LLM_TIMEOUT_SECONDS,
        }
        started = _monotonic()
        schema_retries = 0
        rate_limit_retries = 0

        def fail(status: str, reason: str) -> UpstreamUnavailable:
            self._log(prompt_name, endpoint, started, schema_retries + rate_limit_retries, status)
            return UpstreamUnavailable(reason)

        while True:
            try:
                with _quiet_sdk_logs():
                    response = self.client.chat.completions.create(**request)
            except openai.RateLimitError:
                if rate_limit_retries >= LLM_RATE_LIMIT_RETRIES:
                    raise fail("rate_limited", BUSY_MESSAGE) from None
                rate_limit_retries += 1
                time.sleep(LLM_RATE_LIMIT_WAIT_SECONDS)
                continue
            except openai.APITimeoutError:
                raise fail("timeout", TIMEOUT_MESSAGE) from None
            except openai.APIStatusError as exc:
                reason = f"The AI service returned an error (HTTP {exc.status_code})"
                raise fail("error", reason) from None
            except openai.APIConnectionError:
                raise fail("error", "The AI service could not be reached") from None

            choices = getattr(response, "choices", None) or []
            content = choices[0].message.content if choices else None
            try:
                parsed = schema.model_validate_json(content or "")
            except ValidationError:
                if schema_retries >= LLM_SCHEMA_RETRIES:
                    reason = (
                        f"Model output did not match schema {schema.__name__} "
                        f"after {LLM_SCHEMA_RETRIES} retry"
                    )
                    raise fail("schema_error", reason) from None
                schema_retries += 1
                continue

            retries = schema_retries + rate_limit_retries
            latency_ms = self._log(prompt_name, endpoint, started, retries, "ok")
            usage = getattr(response, "usage", None)
            return parsed, CallMeta(
                prompt_name=prompt_name,
                prompt_version=prompt_version,
                endpoint=endpoint,
                model=getattr(response, "model", None),
                latency_ms=latency_ms,
                input_tokens=getattr(usage, "prompt_tokens", None),
                output_tokens=getattr(usage, "completion_tokens", None),
                retries=retries,
            )

    @staticmethod
    def _log(prompt_name: str, endpoint: str, started: float, retries: int, status: str) -> int:
        latency_ms = int((_monotonic() - started) * 1000)
        level = logging.INFO if status == "ok" else logging.WARNING
        logger.log(
            level,
            "gateway call prompt_name=%s endpoint=%s latency_ms=%d retries=%d status=%s",
            prompt_name,
            endpoint,
            latency_ms,
            retries,
            status,
        )
        return latency_ms
