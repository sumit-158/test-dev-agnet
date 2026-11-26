# Feature Set v3 — PIR / Source List Request Chat (SCO-001) — PoC operations: run it for 10 stewards

| Field | Value |
|---|---|
| Feature set | v3 — PoC operations: run it for 10 stewards |
| TSD version | TSD-SCO-001 v1.0 |
| Source PRD(s) | PRD-SCO-001 v0.1 §2, §7 (cost < USD 200 per month), §9 (confidentiality) |
| Status | Draft |
| Approved by / date | |
| Depends on sets | v2 merged |
| Context library version | 2026.11.24-1 |

## 1. What this feature set delivers

**Goal:** The PoC app runs for the 10 stewards at 40 requests per day with measured cost, enforced budgets and rate
limits that fail with plain texts, verified access grants (BR-09 / BR-10) and a runbook.

**Builds on (already exists before this set):** v1 and v2 — the deployed app `sco-001-pir-sl-chat`, endpoints
`sco_001_intent` / `sco_001_extract` (EXT-01, EXT-02) with inference tables T-02, experiment `/Shared/SCO-001/pir_sl_chat`
(EXT-05), `GatewayRepository` error texts (v1/F-03), API error mapping (v2/F-03), README (v1/F-01).

**Adds:** cost and usage report script, budget and rate-limit configuration with the app's handling of them, permission
integration tests and the "Operate" runbook.

| In scope | Out of scope (later set or never) |
|---|---|
| Monthly cost and usage query over `system.billing.usage`, `system.ai_gateway.usage` and MLflow traces | AI/BI dashboard (no dashboard in a PoC unless it is the primary deliverable, `business/stages_and_approvals.md`) |
| Gateway budgets USD 30 / USD 150 with 80 % alerts; rate limits 60 / 30 requests per minute; app texts for 429 / budget | Autoscaling, SLAs, on-call (Prod) |
| Permission tests for the app, inference tables, volumes, experiment | RBAC inside the app (PRD §8 excludes user management) |
| Runbook in README "Operate" | Prod deployment (PRD §10) |

## 2. Set exit criteria

| ID | The set is done when… | Checked by |
|---|---|---|
| EX-v3-1 | `python -m evals.usage_report --month 2026-12` prints model cost in USD for the month below 200 and the request count, token totals, fallback count and p95 latency per endpoint | query |
| EX-v3-2 | The budgets and rate limits of TSD §7 are configured on both endpoints and a forced 429 in dev shows the text `The AI service is busy or the monthly budget is reached; try again later` in the app | test + manual |
| EX-v3-3 | `pytest -m integration tests/integration/test_v3_permissions.py` passes: a non-member service principal gets no access to the app, T-02, SRC-01, SRC-02 and the experiment; the stewards group has `CAN USE` on the app | test |
| EX-v3-4 | README "Operate" is reviewed by the tech lead (pull request approval) | review |

## 3. Build order

| # | Feature | Title | Module | Depends on / related to | Size | Status | PR |
|---|---|---|---|---|---|---|---|
| 1 | v3/F-01 | Build the usage and cost report | `evals` | v1/F-08, v2/F-03 | S | To do | |
| 2 | v3/F-02 | Configure budgets and rate limits and handle them in the app | `gateway_repository`, `routers/messages` | v1/F-03, v2/F-03, v2/F-06 | S | To do | |
| 3 | v3/F-03 | Verify access grants and write the runbook | `tests/integration`, `README` | v2/F-01, v3/F-01, v3/F-02 | M | To do | |

Feature references are written `v{set}/F-{nn}` so a link to a feature in another feature set is unambiguous.
Status: To do → In progress → In review → Human testing → Done (Blocked, Dropped). Only a human sets Done.

---

## 4. Features

### v3/F-01 — Build the usage and cost report

| Field | Value |
|---|---|
| Module / layer | `evals` — `evals/usage_report.py`, `evals/sql/usage_report.sql` (TSD §4) |
| Type | test-only / report script |
| Size | S |
| Depends on / related to | v1/F-08 (uses the SQL runner pattern), v2/F-03 (traces of the deployed app) |
| PRD refs | PRD-SCO-001 §7 (cost < USD 200 per month, 40 requests per day) |
| TSD refs | §7 volume and cost column, §9 Cost, §13, §16 D-11, R-03; system tables verified in §18 |
| Standards applied | skill:ai_agents §3 (`system.ai_gateway.usage`), references/eval-and-ops.md §5, §6; skill:data_engineering references/spark-and-python.md §2 (small result on the driver) |

#### 1. Context

D-11 is an estimate. This feature replaces it with measured numbers: DBU cost of the project endpoints and the AI
function from `system.billing.usage`, requests, tokens, fallbacks and latency from `system.ai_gateway.usage`, printed
per month so the owner can compare with the USD 200 ceiling.

#### 2. Related features — context from earlier work

| Feature | Set | Relationship | What it built that this feature uses (exact names) | Status |
|---|---|---|---|---|
| v1/F-08 | v1 | uses | `SqlRunner` protocol (`execute(sql, params) -> rows`) and the `databricks-sql-connector` runner in `evals/run_eval.py` (moved to `evals/sql_runner.py` by this feature — allowed modification) | Done |
| v1/F-01 | v1 | uses | `Settings.ENDPOINT_INTENT`, `ENDPOINT_EXTRACT`, `WAREHOUSE_ID` | Done |
| v2/F-03 | v2 | uses | deployed app generating traffic on both endpoints | Done |

**Rules carried over from those features:** no hard-coded endpoint names (from `Settings`).

#### 3. Files

| Action | Path | Purpose |
|---|---|---|
| create | `SCO-001/evals/usage_report.py` | CLI `python -m evals.usage_report --month YYYY-MM` |
| create | `SCO-001/evals/sql/usage_report.sql` | the two queries below |
| create | `SCO-001/evals/sql_runner.py` | `SqlRunner` protocol and `DatabricksSqlRunner(settings)` extracted from `evals/run_eval.py` |
| modify | `SCO-001/evals/run_eval.py` | import the runner from `evals/sql_runner.py` only |
| create | `SCO-001/tests/unit/evals/test_f01_usage_report.py` | tests for this feature |

No other files may be created or changed.

#### 4. Data

| Table (TSD §5.2 ID) | Columns read | Columns written | Write mode |
|---|---|---|---|
| `system.billing.usage` | `usage_date`, `usage_quantity`, `sku_name`, `billing_origin_product`, `usage_metadata.endpoint_name` | — | — |
| `system.billing.list_prices` | `sku_name`, `pricing.default`, `price_start_time`, `price_end_time` | — | — |
| `system.ai_gateway.usage` | `event_time`, `endpoint_name`, `destination_model`, `input_tokens`, `output_tokens`, `latency_ms`, `status_code`, `routing_information.attempts` | — | — |

**Joins (this feature):**

| Left | Right | Type | Condition | Filters | Expected result |
|---|---|---|---|---|---|
| `system.billing.usage` u | `system.billing.list_prices` p | LEFT | `u.sku_name = p.sku_name AND u.usage_date >= p.price_start_time::date AND (p.price_end_time IS NULL OR u.usage_date < p.price_end_time::date)` | `u.usage_date` in the month; `u.usage_metadata.endpoint_name IN (:intent, :extract, 'databricks-ai-parse-document')` | one row per endpoint and SKU per month |

#### 5. Interfaces

**API (TSD §6.1):** none.

**Functions added by this feature:**

```python
def usage_report(settings: Settings, month: str, sql: SqlRunner) -> UsageReport:
    """UsageReport(month, cost_usd_by_endpoint: dict[str, float], total_cost_usd: float, requests_by_endpoint: dict[str, int], input_tokens: int, output_tokens: int, fallback_requests: int, p95_latency_ms_by_endpoint: dict[str, float], under_ceiling: bool). Raises ValueError for a month not matching YYYY-MM."""
```

| Input | Output |
|---|---|
| `usage_report(settings, "2026-12", fake_sql)` with cost rows `[("sco_001_extract", 1200.0 DBU, 0.07), ("sco_001_intent", 40.0, 0.07), ("databricks-ai-parse-document", 300.0, 0.088)]` and usage rows | `total_cost_usd == 113.2` (84.0 + 2.8 + 26.4), `under_ceiling == True`, `requests_by_endpoint["sco_001_extract"] == <count>` |

#### 6. Implementation steps

1. `evals/sql/usage_report.sql`, query 1 (cost):

```sql
SELECT u.usage_metadata.endpoint_name AS endpoint_name,
       u.sku_name,
       SUM(u.usage_quantity) AS dbu,
       MAX(p.pricing.default) AS usd_per_dbu,
       SUM(u.usage_quantity) * MAX(p.pricing.default) AS cost_usd
FROM system.billing.usage u
LEFT JOIN system.billing.list_prices p
  ON u.sku_name = p.sku_name
 AND u.usage_date >= CAST(p.price_start_time AS DATE)
 AND (p.price_end_time IS NULL OR u.usage_date < CAST(p.price_end_time AS DATE))
WHERE u.usage_date >= to_date(:month_start) AND u.usage_date < add_months(to_date(:month_start), 1)
  AND u.billing_origin_product IN ('MODEL_SERVING', 'AI_FUNCTIONS')
  AND u.usage_metadata.endpoint_name IN (:endpoint_intent, :endpoint_extract, 'databricks-ai-parse-document')
GROUP BY 1, 2
```

   Query 2 (usage):

```sql
SELECT endpoint_name,
       COUNT(*) AS requests,
       SUM(input_tokens) AS input_tokens,
       SUM(output_tokens) AS output_tokens,
       SUM(CASE WHEN size(routing_information.attempts) > 1 THEN 1 ELSE 0 END) AS fallback_requests,
       percentile_approx(latency_ms, 0.95) AS p95_latency_ms,
       SUM(CASE WHEN status_code = 429 THEN 1 ELSE 0 END) AS rate_limited
FROM system.ai_gateway.usage
WHERE event_time >= to_timestamp(:month_start) AND event_time < add_months(to_timestamp(:month_start), 1)
  AND endpoint_name IN (:endpoint_intent, :endpoint_extract)
GROUP BY 1
```

2. `usage_report` runs both with `month_start = f"{month}-01"`; `under_ceiling = total_cost_usd < COST_CEILING_USD`; `ai_parse_document` cost is attributed to AG-01 and counted in the total (PRD §7 "model cost").
3. Print a table and a line `TOTAL <cost> USD — under 200: True/False`; exit 0 when under, 3 when not; `--json` prints the report as JSON.
4. Record the measured cost in TSD D-11 through a change request after the first full month (the Planner updates the TSD; this feature only reports).

Constants: `COST_CEILING_USD = 200.0` (defined in `evals/usage_report.py`).

#### 7. Edge cases and errors

| Case | Input | Expected behaviour |
|---|---|---|
| Bad month | `2026-13` | `ValueError("month must be YYYY-MM")` |
| No usage | empty month | all zeros, `total_cost_usd == 0.0`, `under_ceiling == True` |
| Price missing | `usd_per_dbu NULL` | cost row `None`, warning `No list price for <sku>`; total excludes it and prints `(incomplete)` |
| System tables denied | permission error | `UpstreamUnavailable("system tables not readable; ask the workspace admin for SELECT on system.billing and system.ai_gateway")` |

#### 8. Acceptance criteria and tests

Test file: `SCO-001/tests/unit/evals/test_f01_usage_report.py` · fixtures: `settings`, `FakeSqlRunner` (scripted rows per query)

| AC ID | Given / When / Then | Test name | Fixture data | Expected |
|---|---|---|---|---|
| AC-F01-1 | Given the §5 rows, when the report runs, then totals and flag are right | `test_f01_ac1_totals` | §5 rows; usage rows `sco_001_extract 880 req, 15.8M in, 3.1M out, 12 fallbacks, p95 41000`; `sco_001_intent 1760 req` | `total_cost_usd == 113.2`, `under_ceiling`, `fallback_requests == 12`, `p95_latency_ms_by_endpoint["sco_001_extract"] == 41000` |
| AC-F01-2 | Given cost rows above the ceiling, when run, then flag false and exit code 3 | `test_f01_ac2_over_ceiling` | `sco_001_extract 4000 DBU` | `under_ceiling == False`; `main()` returns 3 |
| AC-F01-3 | Given an invalid month, when run, then `ValueError` | `test_f01_ac3_bad_month` | `"2026-13"` | message `month must be YYYY-MM` |
| AC-F01-4 | Given the SQL text, when parameters are bound, then both queries filter on the project endpoints | `test_f01_ac4_queries_use_settings` | — | executed SQL params include `endpoint_intent == "sco_001_intent"`, `endpoint_extract == "sco_001_extract"`, `month_start == "2026-12-01"` |

Integration / evaluation checks (run by a human in dev): `python -m evals.usage_report --month <current month>` prints a cost below 200 after the evaluation runs and one week of steward use.

#### 9. Build-ready checklist (Planner self-check)

- [x] Every related feature (this set or earlier sets) is listed in §2 with the exact names this feature uses
- [x] Every path, table, column, API, agent and config key exists in the TSD, in §2, or earlier in this feature
- [x] Every join is written out in §4 (tables, type, condition, filters, expected result)
- [x] Every step is exact; SQL given for non-trivial logic; all constants have values
- [x] Every acceptance criterion has a test with literal fixture data and expected output
- [x] Edge cases cover empty, invalid, not-found and permission cases where relevant
- [x] No open words (e.g., such as, appropriate, as needed, TBD, etc., choose, decide)

**Out of scope for this feature:** a dashboard; alerts (v3/F-02); per-user cost; Databricks Apps compute cost (not model cost, PRD §7).

**How a human tests it:** 1) Run the report for the current month. 2) Compare the `sco_001_extract` request count with the number of requests sent that month. 3) Run with `--json` and read `under_ceiling`.

---

### v3/F-02 — Configure budgets and rate limits and handle them in the app

| Field | Value |
|---|---|
| Module / layer | `gateway_repository`, `routers/messages` — `backend/repositories/gateway_repository.py`, `backend/services/extraction_service.py`, `frontend/src/components/ChatPane.tsx`, `infra/gateway_endpoints.md` (TSD §4; `infra/` is a documentation folder added by this feature) |
| Type | API |
| Size | S |
| Depends on / related to | v1/F-03, v2/F-03, v2/F-06 (depends on) |
| PRD refs | PRD-SCO-001 §7 (cost), §2 (10 stewards) |
| TSD refs | §7 gateway endpoint column (rate limits, budgets), §9 Cost, §13 alerts, §16 R-03, R-05; §2.4 RF-01 error rows |
| Standards applied | skill:ai_agents §3 (rate limits, budget with alert thresholds, inference table), references/eval-and-ops.md §5, §6; skill:ui_ux_design §6, §8 (error copy) |

#### 1. Context

The endpoints get the TSD §7 limits: `sco_001_intent` 60 requests per minute, budget USD 30; `sco_001_extract` 30
requests per minute, budget USD 150; alerts at 80 % to the project owner. The app already maps 429 to a text (v1/F-03);
this feature confirms the text end to end, adds the budget-exceeded code path, and documents the endpoint configuration
so it can be re-created.

#### 2. Related features — context from earlier work

| Feature | Set | Relationship | What it built that this feature uses (exact names) | Status |
|---|---|---|---|---|
| v1/F-03 | v1 | extends | `GatewayRepository.complete_json` retry on 429 once after `LLM_RATE_LIMIT_WAIT_SECONDS = 2`, then `UpstreamUnavailable("The AI service is busy or the monthly budget is reached; try again later")` | Done |
| v2/F-03 | v2 | extends | API-04 maps `UpstreamUnavailable` from AG-02 to `503` with `The AI service did not answer; send the message again`; `run_extraction` sets `extraction_status failed` with the reason | Done |
| v2/F-06 | v2 | extends | error texts shown under the composer and in the right-pane error card with `Send again` | Done |

**Rules carried over from those features:** error texts are returned by the API and shown as is.

#### 3. Files

| Action | Path | Purpose |
|---|---|---|
| create | `SCO-001/infra/gateway_endpoints.md` | the exact configuration of `sco_001_intent`, `sco_001_extract`, `sco_001_intent_fb`, `sco_001_extract_fb`: served models, fallbacks, rate limits, budgets, alert e-mail, inference tables `sandbox_others.sco_001_poc.gateway_<endpoint>_payload`, service policies none |
| modify | `SCO-001/backend/repositories/gateway_repository.py` | distinguish HTTP 429 with body containing `budget` → `UpstreamUnavailable(MSG_BUDGET)`; keep rate-limit text otherwise |
| modify | `SCO-001/backend/services/extraction_service.py` | API-04: when AG-02 raises `UpstreamUnavailable` whose message is `MSG_BUDGET` or the rate-limit text, return `503` with that message instead of the generic one |
| modify | `SCO-001/frontend/src/components/ChatPane.tsx` | show a `Retry` ghost button next to the 503 text |
| create | `SCO-001/tests/unit/repositories/test_f02_limits.py` | tests for this feature |
| create | `SCO-001/tests/integration/test_v3_f02_rate_limit.py` | forces 429 in dev by sending 31 extraction calls within one minute (marker `integration`) |

No other files may be created or changed.

#### 4. Data

| Table (TSD §5.2 ID) | Columns read | Columns written | Write mode |
|---|---|---|---|
| T-02 inference tables | — (configuration only) | written by the gateway | — |

**Joins (this feature):** none.

#### 5. Interfaces

**API (TSD §6.1):** API-04 `503 {"detail": "The AI service is busy or the monthly budget is reached; try again later"}` for 429 or budget; otherwise unchanged.

**Functions added by this feature:**

```python
MSG_BUDGET = "The monthly AI budget for this app is reached; ask the SCO team lead to raise it"
MSG_RATE_LIMIT = "The AI service is busy or the monthly budget is reached; try again later"
def classify_gateway_error(exc: Exception) -> str | None:
    """MSG_BUDGET when HTTP 429 and the error body contains 'budget' (case-insensitive); MSG_RATE_LIMIT for other 429; None otherwise."""
```

| Input | Output |
|---|---|
| `RateLimitError` with body `{"error_code": "RESOURCE_EXHAUSTED", "message": "Budget exceeded for endpoint sco_001_extract"}` | `MSG_BUDGET` |
| `RateLimitError` with body `rate limit exceeded` | `MSG_RATE_LIMIT` |

#### 6. Implementation steps

1. Write `infra/gateway_endpoints.md` with a table per endpoint (name, served entity, fallback, traffic 100 % / 0 %, rate limit `<n> requests per minute per service principal`, budget `USD <n> per month, alert at 80 % to <owner e-mail config key OWNER_EMAIL>`, inference table) and the Databricks UI path to set them (Serving → endpoint → AI Gateway). The platform team applies it (D-14).
2. `gateway_repository.py`: wrap the 429 branch with `classify_gateway_error`; no retry for `MSG_BUDGET`.
3. `extraction_service.py`: propagate the two messages to the 503 detail.
4. `ChatPane.tsx`: `Retry` re-sends the last message text (no attachments).
5. Integration test: with `ENDPOINT_EXTRACT` limited to 30 per minute, fire 31 `complete_json` calls in a loop; assert at least one `UpstreamUnavailable` with `MSG_RATE_LIMIT`; the test is skipped unless `RUN_RATE_LIMIT_TEST=1`.
6. Add `OWNER_EMAIL` to the config table of `README.md` (documentation only; not a `Settings` key).

Constants: `MSG_BUDGET`, `MSG_RATE_LIMIT` (defined in `backend/repositories/gateway_repository.py`; `MSG_RATE_LIMIT` replaces the inline literal of v1/F-03 with the same text).

#### 7. Edge cases and errors

| Case | Input | Expected behaviour |
|---|---|---|
| Budget hit mid-extraction | 429 budget during AG-03 | `extraction_status failed`, `error == MSG_BUDGET`, right pane error card with that text |
| Rate limit on triage | 429 then 200 | retry after 2 s succeeds; `retries == 1` |
| Fallback taken | primary 5xx | handled by the gateway; the app sees 200; `fallback_requests` counted in v3/F-01 |
| Alert e-mail missing | no `OWNER_EMAIL` documented | README instruction marks it as required; no code impact |

#### 8. Acceptance criteria and tests

Test file: `SCO-001/tests/unit/repositories/test_f02_limits.py` · fixtures: `settings`, `FakeOpenAI` (from v1/F-03 tests)

| AC ID | Given / When / Then | Test name | Fixture data | Expected |
|---|---|---|---|---|
| AC-F02-1 | Given a 429 body containing `Budget exceeded`, when `complete_json` runs, then `UpstreamUnavailable(MSG_BUDGET)` without retry | `test_f02_ac1_budget` | one `RateLimitError` with that body | message equals `MSG_BUDGET`; 1 call made |
| AC-F02-2 | Given two 429 `rate limit exceeded`, when run, then `MSG_RATE_LIMIT` after one retry | `test_f02_ac2_rate_limit` | two `RateLimitError` | message `MSG_RATE_LIMIT`; 2 calls |
| AC-F02-3 | Given the API-04 route and a triage raising `UpstreamUnavailable(MSG_BUDGET)`, when posted, then `503` with `MSG_BUDGET` | `test_f02_ac3_route_budget_text` | `fake_gateway.raise_for = {"request_triage_chat": UpstreamUnavailable(MSG_BUDGET)}` | `503 {"detail": MSG_BUDGET}` |

Integration / evaluation checks (run by a human in dev): open both endpoints in the Serving UI and compare with `infra/gateway_endpoints.md`; run `RUN_RATE_LIMIT_TEST=1 pytest -m integration tests/integration/test_v3_f02_rate_limit.py`; in the app send a message while the limit is active and read the text under the composer; check the alert e-mail arrives when the budget threshold is lowered to the current spend for the test and restored afterwards.

#### 9. Build-ready checklist (Planner self-check)

- [x] Every related feature (this set or earlier sets) is listed in §2 with the exact names this feature uses
- [x] Every path, table, column, API, agent and config key exists in the TSD, in §2, or earlier in this feature
- [x] Every join is written out in §4 (tables, type, condition, filters, expected result)
- [x] Every step is exact; SQL given for non-trivial logic; all constants have values
- [x] Every acceptance criterion has a test with literal fixture data and expected output
- [x] Edge cases cover empty, invalid, not-found and permission cases where relevant
- [x] No open words (e.g., such as, appropriate, as needed, TBD, etc., choose, decide)

**Out of scope for this feature:** client-side throttling or queues; per-user quotas; automatic budget increase; gateway
service policies for PII (D-09: inputs contain signatures and quotations by design; policies would block them).

**How a human tests it:** 1) Compare the endpoint settings with `infra/gateway_endpoints.md`. 2) Run the rate-limit integration test. 3) Lower the budget threshold temporarily and confirm the alert e-mail.

---

### v3/F-03 — Verify access grants and write the runbook

| Field | Value |
|---|---|
| Module / layer | `tests/integration`, `README` — `tests/integration/test_v3_permissions.py`, `infra/grants.sql`, `README.md` "Operate" (TSD §4) |
| Type | test-only |
| Size | M |
| Depends on / related to | v2/F-01 (deployed app), v3/F-01, v3/F-02 (depends on) |
| PRD refs | PRD-SCO-001 §2 (users), §9 (confidentiality) |
| TSD refs | §8 grants table, §13 runbook, §16 D-09, D-12, R-08 |
| Standards applied | BR-09, BR-10, skill:ai_agents §7, §10 (checklist), skill:data_engineering §3 (volumes), §9 (tags) |

#### 1. Context

Prices and quotations are Confidential - Commercial. This feature turns TSD §8 into a grants script applied by the
owner, proves with tests that a non-member cannot reach the app, the inference tables, the volumes or the traces, and
writes the runbook the SCO team lead and the tech lead need to run the PoC.

#### 2. Related features — context from earlier work

| Feature | Set | Relationship | What it built that this feature uses (exact names) | Status |
|---|---|---|---|---|
| v2/F-01 | v2 | uses | the deployed app `sco-001-pir-sl-chat` and its service principal; `DELETE /api/sessions/{id}`; TTL sweep | Done |
| v3/F-01 | v3 | uses | `python -m evals.usage_report --month` | To do |
| v3/F-02 | v3 | uses | `infra/gateway_endpoints.md`; `MSG_BUDGET` | To do |
| v1/F-03 | v1 | uses | `python -m evals.register_prompts`; alias move for rollback (`mlflow.genai.set_prompt_alias`) | Done |
| v1/F-08 | v1 | uses | `python -m evals.run_eval` as the regression check after a prompt change | Done |

**Rules carried over from those features:** never log or print message text or values (TSD §11.2).

#### 3. Files

| Action | Path | Purpose |
|---|---|---|
| create | `SCO-001/infra/grants.sql` | GRANT statements of TSD §8, parameterised `${app_sp}`, `${stewards_group}` |
| create | `SCO-001/tests/integration/test_v3_permissions.py` | permission tests (marker `integration`) |
| modify | `SCO-001/README.md` | fill "Operate" |

No other files may be created or changed.

#### 4. Data

| Table (TSD §5.2 ID) | Columns read | Columns written | Write mode |
|---|---|---|---|
| T-02 `sandbox_others.sco_001_poc.gateway_sco_001_intent_payload`, `gateway_sco_001_extract_payload` | `SELECT 1 ... LIMIT 1` as the test principal | — | — |
| `sandbox_others.information_schema.table_privileges`, `volume_privileges`, `schema_privileges` | `grantee`, `privilege_type`, `table_name` / `volume_name` | — | — |

**Joins (this feature):** none.

#### 5. Interfaces

**API (TSD §6.1):** none.

**Functions added by this feature:** none (tests and documentation).

`infra/grants.sql` (exact):

```sql
GRANT USE CATALOG ON CATALOG sandbox_others TO `${app_sp}`;
GRANT USE SCHEMA, EXECUTE ON SCHEMA sandbox_others.sco_001_poc TO `${app_sp}`;
GRANT READ VOLUME, WRITE VOLUME ON VOLUME sandbox_others.sco_001_poc.uploads TO `${app_sp}`;
GRANT USE CATALOG ON CATALOG sandbox_others TO `${stewards_group}`;
GRANT USE SCHEMA ON SCHEMA sandbox_others.sco_001_poc TO `${stewards_group}`;
GRANT SELECT ON TABLE sandbox_others.sco_001_poc.gateway_sco_001_intent_payload TO `${stewards_group}`;
GRANT SELECT ON TABLE sandbox_others.sco_001_poc.gateway_sco_001_extract_payload TO `${stewards_group}`;
GRANT READ VOLUME ON VOLUME sandbox_others.sco_001_poc.uploads TO `${stewards_group}`;
GRANT READ VOLUME ON VOLUME sandbox_others.sco_001_poc.demo_requests TO `${stewards_group}`;
GRANT SELECT ON TABLE sandbox_others.sco_001_poc.eval_pir_sl_extraction_chat TO `${stewards_group}`;
```

App, warehouse, endpoint and experiment permissions are set in the UI / bundle (`CAN USE` app → `${stewards_group}`;
`CAN USE` warehouse, `CAN QUERY` endpoints, `CAN EDIT` experiment → `${app_sp}`), listed in README "Operate".

#### 6. Implementation steps

1. Write `infra/grants.sql`; the owner runs it with `${app_sp}` = the app's service principal application id and `${stewards_group}` = `sco-procurement-data-stewards` (D-12).
2. `test_v3_permissions.py` (skipped unless `PERM_TEST_TOKEN` of a non-member test service principal is set): with that token, `GET <app-url>/api/health` → `403` or redirect to login (not `200`); `SELECT 1 FROM sandbox_others.sco_001_poc.gateway_sco_001_extract_payload LIMIT 1` → permission error; `LIST '/Volumes/sandbox_others/sco_001_poc/uploads/'` → permission error; MLflow `search_traces` on the experiment → permission error. With the owner token: `information_schema.table_privileges` shows `SELECT` for `${stewards_group}` on both T-02 tables and nothing for any other principal than the owner, the app SP and the group.
3. README "Operate": sections — `Daily`: nothing scheduled; `Cost`: run `evals.usage_report`, ceiling USD 200, budget alert e-mails; `Prompt change`: edit `prompts/*.md`, `register_prompts`, `run_eval` primary and fallback, move alias; `Roll back a prompt`: `set_prompt_alias` to the previous version, restart the app (`databricks apps restart sco-001-pir-sl-chat` is NOT a command — use `databricks bundle run -t dev sco_001_pir_sl_chat`); `Restart the app`: the same command; sessions are lost (R-08); `Delete a session folder`: `databricks fs rm -r dbfs:/Volumes/sandbox_others/sco_001_poc/uploads/<session_id>`; `Access`: `infra/grants.sql` and the UI permissions; `Confidentiality`: BR-09 / BR-10 statement, who may read T-02 and traces; `Known limits`: 20 pages, 10 attachments, 20 MB, 8 h session; `Contacts`: product owner, tech lead, platform team.
4. Tag the app and the endpoints with `project_id = SCO-001` (bundle `tags` for the app; endpoint tags in `infra/gateway_endpoints.md`).

Constants: none.

#### 7. Edge cases and errors

| Case | Input | Expected behaviour |
|---|---|---|
| Test token missing | `PERM_TEST_TOKEN` unset | tests skipped with reason `needs a non-member service principal token` |
| Grant drift | a new grantee on T-02 | test fails listing the grantee |
| Group renamed | `${stewards_group}` wrong | grants fail; README names the owner to ask |

#### 8. Acceptance criteria and tests

Test file: `SCO-001/tests/integration/test_v3_permissions.py` · fixtures: `PERM_TEST_TOKEN`, owner token from the CLI profile

| AC ID | Given / When / Then | Test name | Fixture data | Expected |
|---|---|---|---|---|
| AC-F03-1 | Given a non-member token, when the app health route is called, then access is refused | `test_v3_f03_ac1_app_denied` | token | status in `{401, 403, 302}` |
| AC-F03-2 | Given a non-member token, when T-02, the uploads volume and the experiment are read, then every read fails with a permission error | `test_v3_f03_ac2_data_denied` | token | three permission errors |
| AC-F03-3 | Given the owner token, when privileges are listed, then only the owner, `${app_sp}` and `${stewards_group}` appear on T-02 and the volumes | `test_v3_f03_ac3_grants_match_tsd` | — | set of grantees equals the expected set |
| AC-F03-4 | Given the README, when the tech lead follows "Roll back a prompt" in dev, then the previous prompt version answers (checked by the `prompt_version` param of a trace) | manual `runbook rollback` | — | trace shows the older version |

Integration / evaluation checks (run by a human in dev): run the test file with the token; follow the rollback section once and restore the alias.

#### 9. Build-ready checklist (Planner self-check)

- [x] Every related feature (this set or earlier sets) is listed in §2 with the exact names this feature uses
- [x] Every path, table, column, API, agent and config key exists in the TSD, in §2, or earlier in this feature
- [x] Every join is written out in §4 (tables, type, condition, filters, expected result)
- [x] Every step is exact; SQL given for non-trivial logic; all constants have values
- [x] Every acceptance criterion has a test with literal fixture data and expected output
- [x] Edge cases cover empty, invalid, not-found and permission cases where relevant
- [x] No open words (e.g., such as, appropriate, as needed, TBD, etc., choose, decide)

**Out of scope for this feature:** roles inside the app; row filters; a security scanner; production hardening; data
retention automation (sessions are deleted by TTL already).

**How a human tests it:** 1) Run `infra/grants.sql` and the permission tests. 2) Read README "Operate" end to end and run the cost report. 3) Perform the prompt rollback and restore.

---

## 5. Change log

| Date | Change | Features | Source (PRD / CR) | Approved by |
|---|---|---|---|---|
| 2026-11-26 | Initial set | all | PRD-SCO-001 v0.1 | |
