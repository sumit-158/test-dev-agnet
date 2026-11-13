# MRPT-001 — agent guide

All work for this project happens only under `MRPT-001/`. Never touch other top-level folders.

## Commands
- Tests (from repo root): `pytest MRPT-001/tests -q`
- Python 3 + pytest only; standard library otherwise (no extra dependencies).

## Folder layout
- `notebooks/` — Databricks source notebooks `nb_<NN>_<verb>_<object>.py`
- `src/mrpt/` — pure Python helpers (importable, unit-testable)
- `tests/mrpt/` — pytest tests
- `plan/` — PRD/TSD/feature list; **read-only**, never create or edit

## Notebooks run their SQL through dbsql
Each notebook's business logic is plain SQL. The Builder runs the same SQL via dbsql on the dev
warehouse to create objects in `sandbox_others.mrpt_001_poc`. Acceptance criteria are SQL review
queries run with dbsql on the created objects.

## Notebook conventions
- Format: first line `# Databricks notebook source`, cells split by `# COMMAND ----------`,
  markdown as `# MAGIC %md`.
- Cell order: header (purpose, source, target, grain, columns, how to run), parameters, functions,
  input checks, business logic, main.
- Parameter cell defines `CATALOG = "sandbox_others"`, `SCHEMA = "mrpt_001_poc"`,
  `SRC_SAP_SCHEMA = "sap_test"`; build every table name from these (f-strings), never hard-code.
- `run_id` from widget `run_id` (default `"manual"`), coerced to str and validated `[A-Za-z0-9_.-]+`
  before it goes into SQL.
- No `SELECT *`; list columns. Explicit casts; use `TRY_CAST` where bad values must become NULL
  (the warehouse runs in ANSI mode, where `CAST` fails on malformed input).
- Audit columns last: `_etl_loaded_at` TIMESTAMP, `_etl_run_id` STRING.
- Rerunnable: `CREATE OR REPLACE TABLE`, never append. `CREATE SCHEMA IF NOT EXISTS` first.
- Input check (`fx_check_not_empty`) runs before any write; keep it cheap on big sources (`limit(1)`).
- After the write: row count > 0, grain unique (`fx_check_unique_grain`), no null keys.
- Never: DROP/DELETE/TRUNCATE/GRANT/REVOKE, secrets/tokens/workspace URLs, reading `bw_mrp_testpull_api`.

## Git
- Branch `feature/mrpt-001-<feature-id>-<slug>` from `main`.
- Commit message `<FEATURE-ID>: <title>`. No force-push; never push to `main`.
