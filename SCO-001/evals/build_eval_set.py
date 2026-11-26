"""Build evaluation set T-01 from the demo requests in SRC-01 (v1/F-02).

CLI: ``python -m evals.build_eval_set --set-version 1`` (run from ``SCO-001/``).
"""

import argparse
import json
import posixpath
from collections import Counter
from pathlib import Path
from typing import Any, Protocol

from backend.config import Settings, load_settings
from evals.case_schema import EvalCase, VolumeFiles, load_case

MIN_CASES = 30
MIN_TAG_COUNTS = {
    "golden": 1,
    "injection": 3,
    "not_pir_sl": 3,
    "multilingual": 3,
    "conflict": 1,
    "computed": 1,
    "both_pir_and_sl": 1,
    "scanned": 1,
}

DDL_PATH = Path(__file__).parent / "sql" / "create_eval_table.sql"
COLUMNS = [
    "case_id",
    "version",
    "title",
    "messages_json",
    "attachment_paths",
    "expected_request_type",
    "expected_line_items_json",
    "expected_source_segments_json",
    "tags",
    "is_synthetic",
    "notes",
    "ETL_LOADDATE",
]


class SqlRunner(Protocol):
    def execute(self, sql: str, params: dict[str, Any] | None = None) -> list[tuple[Any, ...]]:
        """Run one statement with named parameters; return the result rows (empty for DML)."""
        ...


def list_case_dirs(root: str, files: VolumeFiles) -> list[str]:
    """Every immediate sub-directory of ``root``; each one must be a case folder.

    When ``files`` exposes ``list_dirs`` (the real volume), empty directories are included so
    that ``load_case`` rejects them; otherwise folders are derived from the file paths.
    """
    root = root.rstrip("/")
    names: set[str] = set()
    list_dirs = getattr(files, "list_dirs", None)
    if callable(list_dirs):
        for directory in list_dirs(root):
            names.add(posixpath.basename(directory.rstrip("/")))
    for path in files.list(root + "/"):
        rest = path[len(root) + 1 :]
        if "/" in rest:
            names.add(rest.split("/", 1)[0])
    return [f"{root}/{name}" for name in sorted(names)]


def _validate_set(cases: list[EvalCase]) -> None:
    if len(cases) < MIN_CASES:
        raise ValueError(f"Evaluation set needs at least {MIN_CASES} cases, found {len(cases)}")
    duplicates = sorted(cid for cid, n in Counter(c.case_id for c in cases).items() if n > 1)
    if duplicates:
        raise ValueError(f"Duplicate case_id: {', '.join(duplicates)}")
    tag_counts = Counter(tag for case in cases for tag in set(case.tags))
    for tag, minimum in MIN_TAG_COUNTS.items():
        if tag_counts[tag] < minimum:
            raise ValueError(f"Tag {tag} needs at least {minimum} cases, found {tag_counts[tag]}")


def render_ddl(settings: Settings) -> str:
    return (
        DDL_PATH.read_text(encoding="utf-8")
        .replace("${catalog}", settings.CATALOG)
        .replace("${schema}", settings.SCHEMA)
    )


def build_insert(table: str, cases: list[EvalCase], set_version: int) -> tuple[str, dict[str, Any]]:
    """One multi-row INSERT; every value is a named parameter (arrays passed as JSON strings)."""
    params: dict[str, Any] = {}
    tuples = []
    for i, case in enumerate(cases):
        row = {
            "case_id": case.case_id,
            "version": set_version,
            "title": case.title,
            "messages_json": case.messages_json,
            "attachment_paths": json.dumps(case.attachment_paths, ensure_ascii=False),
            "expected_request_type": case.expected_request_type,
            "expected_line_items_json": case.expected_line_items_json,
            "expected_source_segments_json": case.expected_source_segments_json,
            "tags": json.dumps(case.tags, ensure_ascii=False),
            "is_synthetic": case.is_synthetic,
            "notes": case.notes,
        }
        placeholders = []
        for column, value in row.items():
            name = f"{column}_{i}"
            params[name] = value
            if column in ("attachment_paths", "tags"):
                placeholders.append(f"from_json(:{name}, 'ARRAY<STRING>')")
            else:
                placeholders.append(f":{name}")
        placeholders.append("current_date()")
        tuples.append("(" + ", ".join(placeholders) + ")")
    sql = f"INSERT INTO {table} ({', '.join(COLUMNS)}) VALUES\n" + ",\n".join(tuples)
    return sql, params


def run_dq_checks(settings: Settings, set_version: int, sql: SqlRunner) -> dict[str, Any]:
    table = settings.EVAL_TABLE
    params = {"v": set_version}
    rows = sql.execute(f"SELECT COUNT(*) FROM {table} WHERE version = :v", params)[0][0]
    grain_unique = sql.execute(
        f"SELECT COUNT(*) = COUNT(DISTINCT case_id) FROM {table} WHERE version = :v", params
    )[0][0]
    null_keys = sql.execute(
        f"SELECT COUNT(*) FROM {table} WHERE version = :v "
        "AND (case_id IS NULL OR expected_request_type IS NULL)",
        params,
    )[0][0]
    return {
        "rows": int(rows),
        "count>0": int(rows) > 0,
        "grain_unique": bool(grain_unique),
        "null_keys": int(null_keys),
    }


def build_eval_set(settings: Settings, set_version: int, sql: SqlRunner, files: VolumeFiles) -> int:
    """Create T-01 if missing, replace rows of set_version, return the number of rows written.

    Raises ValueError when fewer than 30 cases or a required tag is missing.
    """
    root = settings.VOLUME_DEMO_REQUESTS
    case_dirs = list_case_dirs(root, files)
    if not case_dirs:
        raise ValueError(f"No case folders found under {root}")
    cases = [load_case(case_dir, files) for case_dir in case_dirs]
    _validate_set(cases)

    table = settings.EVAL_TABLE
    sql.execute(render_ddl(settings), {})
    sql.execute(f"DELETE FROM {table} WHERE version = :v", {"v": set_version})
    insert_sql, insert_params = build_insert(table, cases, set_version)
    sql.execute(insert_sql, insert_params)

    dq = run_dq_checks(settings, set_version, sql)
    print(" ".join(f"{key}={value}" for key, value in dq.items()))
    if not (dq["count>0"] and dq["grain_unique"] and dq["null_keys"] == 0):
        raise RuntimeError(f"Data-quality checks failed for version {set_version}: {dq}")
    return len(cases)


# --- Databricks adapters (CLI only; imported lazily so unit tests need no workspace) -----------


class WorkspaceVolumeFiles:
    """VolumeFiles over ``WorkspaceClient().files``."""

    def __init__(self, client: Any) -> None:
        self._files = client.files

    def list_dirs(self, prefix: str) -> list[str]:
        """Immediate sub-directories of ``prefix``, including empty ones."""
        entries = self._files.list_directory_contents(prefix.rstrip("/"))
        return sorted(entry.path.rstrip("/") for entry in entries if entry.is_directory)

    def list(self, prefix: str) -> list[str]:
        result: list[str] = []
        pending = [prefix.rstrip("/")]
        while pending:
            directory = pending.pop()
            for entry in self._files.list_directory_contents(directory):
                if entry.is_directory:
                    pending.append(entry.path.rstrip("/"))
                else:
                    result.append(entry.path)
        return sorted(result)

    def get(self, path: str) -> bytes:
        return self._files.download(path).contents.read()


class WarehouseSqlRunner:
    """SqlRunner over databricks-sql-connector; host and credentials from the SDK ``Config()``."""

    def __init__(self, warehouse_id: str) -> None:
        from databricks import sql as dbsql
        from databricks.sdk.core import Config

        config = Config()
        host = config.host.removeprefix("https://").removeprefix("http://").rstrip("/")
        self._connection = dbsql.connect(
            server_hostname=host,
            http_path=f"/sql/1.0/warehouses/{warehouse_id}",
            credentials_provider=lambda: config.authenticate,
        )

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> list[tuple[Any, ...]]:
        with self._connection.cursor() as cursor:
            cursor.execute(sql, params or None)
            if cursor.description is None:
                return []
            return [tuple(row) for row in cursor.fetchall()]

    def close(self) -> None:
        self._connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build evaluation set T-01 from SRC-01.")
    parser.add_argument("--set-version", type=int, required=True)
    args = parser.parse_args(argv)

    from databricks.sdk import WorkspaceClient

    settings = load_settings()
    files = WorkspaceVolumeFiles(WorkspaceClient())
    runner = WarehouseSqlRunner(settings.WAREHOUSE_ID)
    try:
        build_eval_set(settings, args.set_version, runner, files)
    finally:
        runner.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
