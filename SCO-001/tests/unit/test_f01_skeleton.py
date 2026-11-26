"""Tests for v1/F-01: project skeleton, config, constants, domain models and test fakes."""

import pytest
from fastapi import FastAPI

import backend.main
from backend.config import load_settings
from backend.constants import (
    ALLOWED_PURCHASING_ORG,
    FIELD_LABELS,
    PIR_FIELDS,
    SL_FIELDS,
)

COMPLETE_ENV = {
    "CATALOG": "sandbox_others",
    "SCHEMA": "sco_001_poc",
    "VOLUME_UPLOADS": "/Volumes/sandbox_others/sco_001_poc/uploads",
    "VOLUME_DEMO_REQUESTS": "/Volumes/sandbox_others/sco_001_poc/demo_requests",
    "WAREHOUSE_ID": "abc",
    "ENDPOINT_INTENT": "sco_001_intent",
    "ENDPOINT_EXTRACT": "sco_001_extract",
    "PROMPT_ALIAS": "production",
    "MLFLOW_EXPERIMENT": "/Shared/SCO-001/pir_sl_chat",
    "EVAL_TABLE": "sandbox_others.sco_001_poc.eval_pir_sl_extraction_chat",
}


def test_f01_ac1_settings_load() -> None:
    settings = load_settings(COMPLETE_ENV)

    for key, value in COMPLETE_ENV.items():
        assert getattr(settings, key) == value
    assert settings.TIME_ZONE == "Asia/Singapore"
    assert settings.LOG_LEVEL == "INFO"
    assert settings.ENDPOINT_EXTRACT == "sco_001_extract"


def test_f01_ac2_missing_setting() -> None:
    with pytest.raises(ValueError) as exc_info:
        load_settings({"CATALOG": "sandbox_others"})

    assert str(exc_info.value) == "Missing required setting SCHEMA"


def test_f01_ac3_constants() -> None:
    assert len(PIR_FIELDS) == 14
    assert len(SL_FIELDS) == 8
    assert ALLOWED_PURCHASING_ORG == {"3000", "3300", "8000"}
    assert FIELD_LABELS["material"] == "Vendor Material No."


def test_f01_ac4_health_and_fixtures(client, golden_messages, golden_attachment) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "7,000" in golden_messages[0].text
    assert len(golden_attachment.pages[0].elements) == 6


def test_f01_lazy_app_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    # ``uvicorn backend.main:app`` builds the app on first access; never leave a cached instance.
    module_dict = backend.main.__dict__
    module_dict.pop("app", None)
    for key, value in COMPLETE_ENV.items():
        monkeypatch.setenv(key, value)
    try:
        assert isinstance(backend.main.app, FastAPI)

        module_dict.pop("app", None)
        monkeypatch.delenv("WAREHOUSE_ID")
        with pytest.raises(ValueError) as exc_info:
            _ = backend.main.app

        assert str(exc_info.value) == "Missing required setting WAREHOUSE_ID"
        assert "app" not in module_dict
    finally:
        module_dict.pop("app", None)
