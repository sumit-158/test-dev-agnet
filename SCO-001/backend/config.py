"""Settings from the environment / app resources (TSD §10); fails fast on a missing key."""

import os
from collections.abc import Mapping

from pydantic import BaseModel

# TSD §10 table order; keys with a default are optional.
SETTING_KEYS = [
    "CATALOG",
    "SCHEMA",
    "VOLUME_UPLOADS",
    "VOLUME_DEMO_REQUESTS",
    "WAREHOUSE_ID",
    "ENDPOINT_INTENT",
    "ENDPOINT_EXTRACT",
    "PROMPT_ALIAS",
    "MLFLOW_EXPERIMENT",
    "EVAL_TABLE",
    "TIME_ZONE",
    "LOG_LEVEL",
]

DEFAULTS = {"TIME_ZONE": "Asia/Singapore", "LOG_LEVEL": "INFO"}


class Settings(BaseModel):
    CATALOG: str
    SCHEMA: str
    VOLUME_UPLOADS: str
    VOLUME_DEMO_REQUESTS: str
    WAREHOUSE_ID: str
    ENDPOINT_INTENT: str
    ENDPOINT_EXTRACT: str
    PROMPT_ALIAS: str
    MLFLOW_EXPERIMENT: str
    EVAL_TABLE: str
    TIME_ZONE: str = DEFAULTS["TIME_ZONE"]
    LOG_LEVEL: str = DEFAULTS["LOG_LEVEL"]


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Build Settings from env (default os.environ).

    Raises ValueError("Missing required setting <KEY>") when a key without default is absent.
    """
    source = os.environ if env is None else env
    values: dict[str, str] = {}
    for key in SETTING_KEYS:
        value = source.get(key)
        if value is None or value == "":
            if key in DEFAULTS:
                values[key] = DEFAULTS[key]
                continue
            raise ValueError(f"Missing required setting {key}")
        values[key] = value
    return Settings(**values)
