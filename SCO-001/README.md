# SCO-001 — PIR / Source List chat extraction (PoC)

FastAPI + React app on Databricks Apps that reads a PIR / Source List request (chat messages and
attached quotations) and proposes line items with per-field sources. Design: `plan/TSD.md`.

## Run locally

Requires Python 3.11.

```bash
pip install -e ".[dev]"
pytest tests/unit
ruff check .
```

Set the environment variables of `plan/TSD.md` §10 (see `app.yaml`), then:

```bash
uvicorn backend.main:app
# open http://localhost:8000/api/health -> {"status": "ok"}
```

The app fails at start-up with `Missing required setting <KEY>` when a required variable is absent.

## Deploy to dev

The workspace host is read from `DATABRICKS_HOST`; authenticate with the Databricks CLI first.

```bash
databricks bundle validate -t dev
databricks bundle deploy -t dev
```

Dev uses the Serverless Starter Warehouse (app resource `sql-warehouse`, CAN USE) and the MLflow
experiment `/Shared/SCO-001/pir_sl_chat` (app resource `experiment`, CAN EDIT); their ids are set
in `databricks.yml` under `targets.dev.variables` (`warehouse_id`, `experiment_id`). The app also
gets WRITE VOLUME on `sandbox_others.sco_001_poc.uploads` (app resource `uc-volume`).

To override the ids, pass `--var` or set `BUNDLE_VAR_*`:

```bash
databricks bundle validate -t dev --var warehouse_id=$WAREHOUSE_ID --var experiment_id=$EXPERIMENT_ID
# or
export BUNDLE_VAR_warehouse_id=$WAREHOUSE_ID BUNDLE_VAR_experiment_id=$EXPERIMENT_ID
databricks bundle validate -t dev
```

The `prod` target is declared but not deployed in the PoC.

### Model endpoints

The app calls the Databricks-hosted model endpoints directly (app resources
`serving-endpoint-intent` and `serving-endpoint-extract`, CAN QUERY):

- `ENDPOINT_INTENT` = `databricks-gpt-5-4-mini` (AG-02 triage)
- `ENDPOINT_EXTRACT` = `databricks-claude-sonnet-4-5` (AG-03 / AG-04)

There is no project AI Gateway endpoint in front of them, so there is no automatic fallback, no
project rate limit and no budget alert. To use the plan's fallback model (`databricks-gpt-5-2`),
change the env value in `app.yaml` (and the matching resource in `databricks.yml`).

## Evaluate

Evaluation scripts are added in later features (`evals/`).

## Operate
