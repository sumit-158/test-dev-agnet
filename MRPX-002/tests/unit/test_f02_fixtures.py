"""Unit test of the shared fake Databricks connection (v1/F-02, AC-F02-3)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.conftest import FakeConnection


def test_f02_ac3_fake_connection_records_calls(
    fake_connection: FakeConnection, golden_row: dict[str, object]
) -> None:
    """AC-F02-3: queued rows come back as one FakeRow and every execute call is recorded."""
    fake_connection.queued_results = [[golden_row]]

    cur = fake_connection.cursor()
    cur.execute("SELECT 1", {"a": 1})
    rows = cur.fetchall()

    assert len(rows) == 1
    assert type(rows[0]).__name__ == "FakeRow"
    assert rows[0].asDict() == golden_row
    assert cur.calls == [("SELECT 1", {"a": 1})]
