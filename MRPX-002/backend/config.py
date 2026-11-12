"""Settings from the Databricks Apps environment and the SQL warehouse connection factory."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from backend.constants import REQUIRED_ENV


@dataclass(frozen=True)
class Settings:
    """Runtime settings of the app; built once at start-up by load_settings."""

    catalog: str
    schema_gold: str
    view_transfer_candidates: str
    databricks_host: str
    databricks_warehouse_id: str

    @property
    def view_full_name(self) -> str:
        """Three-part name `{catalog}.{schema_gold}.{view_transfer_candidates}`."""
        return f"{self.catalog}.{self.schema_gold}.{self.view_transfer_candidates}"


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Read CATALOG, SCHEMA_GOLD, VIEW_TRANSFER_CANDIDATES, DATABRICKS_HOST and
    DATABRICKS_WAREHOUSE_ID.
    Raises RuntimeError("Missing required environment variable <NAME>") on the first missing or
    empty key."""
    source = os.environ if environ is None else environ
    values: dict[str, str] = {}
    for name in REQUIRED_ENV:
        value = (source.get(name) or "").strip()
        if not value:
            raise RuntimeError(f"Missing required environment variable {name}")
        values[name] = value
    return Settings(
        catalog=values["CATALOG"],
        schema_gold=values["SCHEMA_GOLD"],
        view_transfer_candidates=values["VIEW_TRANSFER_CANDIDATES"],
        databricks_host=values["DATABRICKS_HOST"],
        databricks_warehouse_id=values["DATABRICKS_WAREHOUSE_ID"],
    )


def make_connection_factory(settings: Settings) -> Callable[[], Any]:
    """Return a zero-argument callable opening a databricks.sql connection to the app's warehouse,
    authenticated with databricks.sdk.core.Config(host=settings.databricks_host).authenticate."""

    def connect() -> Any:
        from databricks import sql
        from databricks.sdk.core import Config

        cfg = Config(host=settings.databricks_host)
        return sql.connect(
            server_hostname=cfg.host.removeprefix("https://"),
            http_path=f"/sql/1.0/warehouses/{settings.databricks_warehouse_id}",
            credentials_provider=lambda: cfg.authenticate,
        )

    return connect
