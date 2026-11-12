# Feature Set v1 — Shortage Rebalancing: Short in One Plant, Stock Held in Another (MRPX-002) — PoC core data

| Field | Value |
|---|---|
| Feature set | v1 — PoC core data: the governed transfer-candidate view |
| TSD version | TSD-MRPX-002 v1.0 |
| Source PRD(s) | PRD-MRPX-002 §3, §4 (US-1, US-2, US-3, US-5, US-7), §4b, §5, §6, §7, §9 |
| Status | Draft |
| Approved by / date | |
| Depends on sets | — |
| Context library version | 2026.11.04-1 |

## 1. What this feature set delivers

**Goal:** After this set the materialized view `sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair` (T-01) exists, refreshes daily at 06:45 Asia/Singapore, reproduces the PRD golden example, passes its data-quality assertions, and the product owner's planners can receive the validation extract of their plant's candidates.

**Builds on (already exists before this set):** SRC-01 `sandbox_others.sap_test.f_mrp`, SRC-02 `sandbox_others.sap_test.f_monthly_inventory_stock`, SRC-03 `gops_dev.test.sap_extract_dim_material`, SRC-04 `sandbox_others.sap_test.dim_plant` (all read in place, TSD §5.2).

**Adds:** T-01 (TSD §5.2), VAL-01 validation extract (TSD §2.2), shared test fixtures (TSD §12).

| In scope | Out of scope (later set or never) |
|---|---|
| T-01 definition with expectations, schedule, comments, grant | Any app code, API or screen (v2) |
| Integration tests proving grain, nulls, golden example, column list | Alerts on refresh failure (never in PoC, D-12) |
| Parameterised validation extract per plant | Service-principal ownership of T-01 (MVP, D-07) |

## 2. Set exit criteria

| ID | The set is done when… | Checked by |
|---|---|---|
| EX-v1-1 | `SELECT COUNT(*) FROM sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair` returns more than 0 and `COUNT(*) = COUNT(DISTINCT CONCAT(material, '|', short_plant, '|', stock_plant))` | test `test_f01_ac2_grain_unique` (query) |
| EX-v1-2 | For `mrp_snapshot_date = '2026-08-30'` and `inventory_month = '202608'` the view returns exactly one row for `material = '1236-561-01'`, `short_plant = '3300'`, `stock_plant = '1000'` with `shortage_qty = 336233.000`, `stock_qty = 356500.000`, `movable_qty = 336233.000`, `weeks_late = 9`, `criticality = 'A'`, `product_family = 'PE'`, `material_description = 'EMI GASKET / SPIRAL / SSN-053W'`, and this row has the largest `movable_qty` of the view | test `test_f01_ac3_golden_example` (query) |
| EX-v1-3 | The materialized view shows a `SCHEDULE` of `0 45 6 * * ?` in `Asia/Singapore` in `DESCRIBE EXTENDED` and one successful refresh in its pipeline event log | manual check in the Pipelines UI (one step) |
| EX-v1-4 | `validation_extract_by_plant.sql` run with `:short_plant = '3300'` returns 6,256 rows for snapshot `2026-08-30`, first row material `1236-561-01` | query in the SQL editor |

## 3. Build order

| # | Feature | Title | Module | Depends on / related to | Size | Status | PR |
|---|---|---|---|---|---|---|---|
| 1 | v1/F-01 | Create the gold materialized view of transfer candidates (T-01) | `pipelines` | — | M | To do | |
| 2 | v1/F-02 | Integration tests and shared fixtures for T-01 | `tests` | v1/F-01 | S | To do | |
| 3 | v1/F-03 | Validation extract per short plant (VAL-01) | `pipelines` | v1/F-01 | S | To do | |

Feature references are written `v{set}/F-{nn}` so a link to a feature in another feature set is unambiguous.
Status: To do → In progress → In review → Human testing → Done (Blocked, Dropped). Only a human sets Done.

---

## 4. Features

### v1/F-01 — Create the gold materialized view of transfer candidates (T-01)

| Field | Value |
|---|---|
| Module / layer | `pipelines` — pipelines (TSD §4, §11.1) |
| Type | table (materialized view) |
| Size | M |
| Depends on / related to | — |
| PRD refs | PRD-MRPX-002 US-1, US-2, US-3, US-5, US-7, §4b, §5, §6, §7, §9 |
| TSD refs | §2.3 steps 1–4, §2.4 RF-03, §3 Data processing, §5.2 SRC-01 … SRC-04 and T-01, §8, §9, §16 D-01 … D-08, D-10, D-11, D-13 |
| Standards applied | BR-01, BR-02, BR-03, BR-04, BR-05, BR-06, BR-07, BR-09, skill:data_engineering §2, §3, §6, §7, §9, skill:data_engineering references/delivery-specs.md §2, references/spark-and-python.md §1, §3 |

#### 1. Context

The whole product rests on one governed view: every pair of a short plant and a plant holding normal stock of the same material, with the shortage, the stock, the movable quantity (the smaller of the two), the weeks late and the material and plant master attributes. This feature creates that view as a scheduled materialized view in `sandbox_others.gold`, the interface between the data and the app built in v2. It applies the library rules for MRP (one snapshot, shortage > 0, weeks late from the planner-owned column) and for plants (join on `PLANT_KEY`, geography by country).

#### 2. Related features — context from earlier work

| Feature | Set | Relationship | What it built that this feature uses (exact names) | Status |
|---|---|---|---|---|
| — | — | — | None: first feature of the product | — |

**Rules carried over from those features:** None.

#### 3. Files

| Action | Path | Purpose |
|---|---|---|
| create | `MRPX-002/pipelines/sql/agg_mrpx_transfer_candidate_plant_pair.sql` | `CREATE OR REPLACE MATERIALIZED VIEW` statement for T-01 followed by the `GRANT SELECT` statement |

No other files may be created or changed.

#### 4. Data

| Table (TSD §5.2 ID) | Columns read | Columns written | Write mode |
|---|---|---|---|
| SRC-01 `sandbox_others.sap_test.f_mrp` | `SNAPSHOT_DATE` STRING, `PLANT` STRING, `MATERIAL` STRING, `MRP_SHORTAGE_QUANTITY` DECIMAL, `ESTIMATED_WEEKS_LATE` STRING, `BASE_UNIT_OF_MEASURE` STRING | — | — |
| SRC-02 `sandbox_others.sap_test.f_monthly_inventory_stock` | `CALENDAR_YEAR_MONTH` STRING, `PLANT` STRING, `MATERIAL` STRING, `TOTAL_QUANTITY` DECIMAL, `SPECIAL_STOCK_INDICATOR` STRING | — | — |
| SRC-03 `gops_dev.test.sap_extract_dim_material` | `BATCHRUN_DATE` STRING, `MATERIAL_KEY` STRING, `MATERIAL` STRING, `MATERIAL_TYPE` STRING, `PRODUCT_HIER_LEVEL_1` STRING, `CRITICALITY` STRING, `CHANGED_ON` DATE | — | — |
| SRC-04 `sandbox_others.sap_test.dim_plant` | `PLANT_KEY` STRING, `PLANT` STRING, `COUNTRY_KEY` STRING | — | — |
| T-01 `sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair` | — | all 20 columns of TSD §5.2 T-01 | full refresh by the materialized view (CREATE OR REPLACE; scheduled REFRESH) |

**Joins (this feature):**

| Left | Right | Type | Condition | Filters | Expected result |
|---|---|---|---|---|---|
| CTE `short` (from SRC-01) | CTE `stock` (from SRC-02) | INNER | `short.material = stock.material AND short.plant <> stock.plant` | `short`: `SNAPSHOT_DATE = (SELECT MAX(SNAPSHOT_DATE) FROM f_mrp)`, `MRP_SHORTAGE_QUANTITY > 0`; `stock`: `CALENDAR_YEAR_MONTH = (SELECT MAX(CALENDAR_YEAR_MONTH) FROM f_monthly_inventory_stock)`, `SPECIAL_STOCK_INDICATOR IS NULL OR SPECIAL_STOCK_INDICATOR = ''`, `HAVING SUM(TOTAL_QUANTITY) > 0` | one row per (material, short plant, stock plant); 115,077 rows for 2026-08-30 / 202608 |
| result | CTE `mat` (from SRC-03) | LEFT | `short.material = mat.MATERIAL_KEY` | `mat`: `BATCHRUN_DATE = (SELECT MAX(BATCHRUN_DATE) FROM sap_extract_dim_material)`, `ROW_NUMBER() OVER (PARTITION BY MATERIAL_KEY ORDER BY CHANGED_ON DESC NULLS LAST, MATERIAL ASC) = 1` | row count unchanged (one master row per material); 0 unmatched materials in the current data |
| result | SRC-04 `dim_plant` ps | LEFT | `short.plant = ps.PLANT_KEY` | — | row count unchanged; unmatched → name `'UNKNOWN PLANT'`, country NULL |
| result | SRC-04 `dim_plant` ph | LEFT | `stock.plant = ph.PLANT_KEY` | — | row count unchanged; unmatched → name `'UNKNOWN PLANT'`, country NULL |

#### 5. Interfaces

**API (TSD §6.1):** none — this feature exposes the table interface T-01 with the exact column list, types and order below (TSD §5.2).

**Functions added by this feature:** none (one SQL statement).

| Input | Output |
|---|---|
| snapshot `2026-08-30`, month `202608`, material batch `202611040335140501` | 115,077 rows; row (`1236-561-01`, `3300`, `1000`) = `shortage_qty 336233.000`, `stock_qty 356500.000`, `movable_qty 336233.000`, `weeks_late 9`, `criticality 'A'`, `product_family 'PE'`, `material_type 'HALB'`, `material_description 'EMI GASKET / SPIRAL / SSN-053W'`, `short_plant_name 'ASM Korea Ltd.'`, `short_plant_country 'KR'`, `stock_plant_name 'UNKNOWN PLANT'`, `stock_plant_country NULL`, `unit_of_measure 'MM'`, `mrp_snapshot_date 2026-08-30`, `inventory_month '202608'` |

#### 6. Implementation steps

1. Create `MRPX-002/pipelines/sql/agg_mrpx_transfer_candidate_plant_pair.sql` with the two statements below, in this order. The file is run in the Databricks SQL editor (or `databricks sql` CLI) by the engineer who owns T-01 in PoC (D-07), on a serverless SQL warehouse.
2. Before running the `CREATE`, run `EXPLAIN` of the `SELECT` part (statement 1 without the `CREATE ... AS` prefix) and keep the plan output in the pull-request description; record that the scalar `MAX(...)` subqueries force a full refresh (skill §2), with the slice sizes from TSD §3.
3. Run statement 1 (`CREATE OR REPLACE MATERIALIZED VIEW`). Wait for the initial refresh to finish (the statement returns when the first refresh completes).
4. Run statement 2 (`GRANT SELECT`).
5. Run `DESCRIBE EXTENDED sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair` and confirm the 20 columns in the order below, the comments and the schedule.
6. Run the three data-quality queries in §8 (AC-F01-1 … AC-F01-3) by hand once and paste the results into the pull-request description.

```sql
-- Statement 1: T-01 (TSD §5.2). Rules: BR-01, BR-02, BR-05, BR-06 (shortage side); library stock notes
-- (stock side); BR-03, BR-04 (plants); D-11 (material master duplicates); BR-07 (schedule); skill §6 (audit columns).
CREATE OR REPLACE MATERIALIZED VIEW sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair (
  material               STRING  COMMENT 'Material (part) number; f_mrp.MATERIAL = dim_material.MATERIAL_KEY',
  material_description   STRING  COMMENT 'Material description from the latest material master batch (column MATERIAL); NULL when blank',
  material_type          STRING  COMMENT 'SAP material type (MATERIAL_TYPE), for example HALB',
  product_family         STRING  COMMENT 'Product family = PRODUCT_HIER_LEVEL_1 of the material master; NULL when blank',
  criticality            STRING  COMMENT 'Material criticality A, B or C from the material master; NULL when blank',
  short_plant            STRING  COMMENT 'Plant code with the MRP shortage (f_mrp.PLANT)',
  short_plant_name       STRING  COMMENT 'Plant name from dim_plant.PLANT; UNKNOWN PLANT when the code is not in dim_plant (BR-03)',
  short_plant_country    STRING  COMMENT 'ISO country of the short plant (dim_plant.COUNTRY_KEY, BR-04); NULL when unmatched',
  stock_plant            STRING  COMMENT 'Plant code holding normal stock of the material (f_monthly_inventory_stock.PLANT)',
  stock_plant_name       STRING  COMMENT 'Plant name from dim_plant.PLANT; UNKNOWN PLANT when the code is not in dim_plant (BR-03)',
  stock_plant_country    STRING  COMMENT 'ISO country of the stock plant (dim_plant.COUNTRY_KEY); NULL when unmatched',
  shortage_qty           DECIMAL(27,3) COMMENT 'SUM(MRP_SHORTAGE_QUANTITY) over shortage rows (> 0) of the material in the short plant, one snapshot (BR-02, BR-05)',
  stock_qty              DECIMAL(27,3) COMMENT 'SUM(TOTAL_QUANTITY) of normal stock (blank SPECIAL_STOCK_INDICATOR) of the material in the stock plant, latest inventory month',
  movable_qty            DECIMAL(27,3) COMMENT 'LEAST(shortage_qty, stock_qty): the part of the shortage this stock could cover',
  weeks_late             INT     COMMENT 'MAX(CAST(ESTIMATED_WEEKS_LATE AS INT)) over the shortage rows (BR-06)',
  unit_of_measure        STRING  COMMENT 'Base unit of measure of the MRP rows (BASE_UNIT_OF_MEASURE); MRP and stock units agree',
  mrp_snapshot_date      DATE    COMMENT 'MRP result date: the one SNAPSHOT_DATE used (latest)',
  inventory_month        STRING  COMMENT 'Inventory month used (CALENDAR_YEAR_MONTH, yyyyMM, latest)',
  ETL_LOADDATE           DATE    COMMENT 'Day this row was computed by the refresh',
  SOURCE_SNAPSHOT_DATE   DATE    COMMENT 'Snapshot date of the MRP source (same as mrp_snapshot_date)',
  CONSTRAINT material_not_null     EXPECT (material IS NOT NULL)            ON VIOLATION FAIL UPDATE,
  CONSTRAINT short_plant_not_null  EXPECT (short_plant IS NOT NULL)         ON VIOLATION FAIL UPDATE,
  CONSTRAINT stock_plant_not_null  EXPECT (stock_plant IS NOT NULL)         ON VIOLATION FAIL UPDATE,
  CONSTRAINT plants_differ         EXPECT (short_plant <> stock_plant)      ON VIOLATION FAIL UPDATE,
  CONSTRAINT movable_positive      EXPECT (movable_qty > 0)                 ON VIOLATION FAIL UPDATE,
  CONSTRAINT criticality_valid     EXPECT (criticality IS NULL OR criticality IN ('A', 'B', 'C'))
)
CLUSTER BY (short_plant, material)
COMMENT 'MRPX-002 transfer candidates: one row per material short in one plant and held as normal stock in another plant, latest MRP snapshot and latest inventory month. Read by the Shortage Rebalancing app.'
SCHEDULE CRON '0 45 6 * * ?' AT TIME ZONE 'Asia/Singapore'
AS
WITH snap AS (
  SELECT MAX(SNAPSHOT_DATE) AS snapshot_date
  FROM sandbox_others.sap_test.f_mrp
),
short AS (
  SELECT m.PLANT                                   AS plant,
         m.MATERIAL                                AS material,
         SUM(m.MRP_SHORTAGE_QUANTITY)              AS shortage_qty,
         MAX(CAST(m.ESTIMATED_WEEKS_LATE AS INT))  AS weeks_late,
         MIN(m.BASE_UNIT_OF_MEASURE)               AS unit_of_measure,
         MAX(m.SNAPSHOT_DATE)                      AS snapshot_date
  FROM sandbox_others.sap_test.f_mrp m
  JOIN snap s ON m.SNAPSHOT_DATE = s.snapshot_date
  WHERE m.MRP_SHORTAGE_QUANTITY > 0
  GROUP BY m.PLANT, m.MATERIAL
),
mon AS (
  SELECT MAX(CALENDAR_YEAR_MONTH) AS inventory_month
  FROM sandbox_others.sap_test.f_monthly_inventory_stock
),
stock AS (
  SELECT s.PLANT                     AS plant,
         s.MATERIAL                  AS material,
         SUM(s.TOTAL_QUANTITY)       AS stock_qty,
         MAX(s.CALENDAR_YEAR_MONTH)  AS inventory_month
  FROM sandbox_others.sap_test.f_monthly_inventory_stock s
  JOIN mon ON s.CALENDAR_YEAR_MONTH = mon.inventory_month
  WHERE s.SPECIAL_STOCK_INDICATOR IS NULL OR s.SPECIAL_STOCK_INDICATOR = ''
  GROUP BY s.PLANT, s.MATERIAL
  HAVING SUM(s.TOTAL_QUANTITY) > 0
),
mat AS (
  SELECT MATERIAL_KEY,
         NULLIF(TRIM(MATERIAL), '')             AS material_description,
         NULLIF(TRIM(MATERIAL_TYPE), '')        AS material_type,
         NULLIF(TRIM(PRODUCT_HIER_LEVEL_1), '') AS product_family,
         NULLIF(TRIM(CRITICALITY), '')          AS criticality
  FROM gops_dev.test.sap_extract_dim_material
  WHERE BATCHRUN_DATE = (SELECT MAX(BATCHRUN_DATE) FROM gops_dev.test.sap_extract_dim_material)
  QUALIFY ROW_NUMBER() OVER (PARTITION BY MATERIAL_KEY ORDER BY CHANGED_ON DESC NULLS LAST, MATERIAL ASC) = 1
)
SELECT sh.material                                        AS material,
       mat.material_description                           AS material_description,
       mat.material_type                                  AS material_type,
       mat.product_family                                 AS product_family,
       mat.criticality                                    AS criticality,
       sh.plant                                           AS short_plant,
       COALESCE(ps.PLANT, 'UNKNOWN PLANT')                AS short_plant_name,
       ps.COUNTRY_KEY                                     AS short_plant_country,
       st.plant                                           AS stock_plant,
       COALESCE(ph.PLANT, 'UNKNOWN PLANT')                AS stock_plant_name,
       ph.COUNTRY_KEY                                     AS stock_plant_country,
       CAST(sh.shortage_qty AS DECIMAL(27,3))             AS shortage_qty,
       CAST(st.stock_qty AS DECIMAL(27,3))                AS stock_qty,
       CAST(LEAST(sh.shortage_qty, st.stock_qty) AS DECIMAL(27,3)) AS movable_qty,
       sh.weeks_late                                      AS weeks_late,
       sh.unit_of_measure                                 AS unit_of_measure,
       CAST(sh.snapshot_date AS DATE)                     AS mrp_snapshot_date,
       st.inventory_month                                 AS inventory_month,
       current_date()                                     AS ETL_LOADDATE,
       CAST(sh.snapshot_date AS DATE)                     AS SOURCE_SNAPSHOT_DATE
FROM short sh
JOIN stock st
  ON sh.material = st.material
 AND sh.plant <> st.plant
LEFT JOIN mat
  ON sh.material = mat.MATERIAL_KEY
LEFT JOIN sandbox_others.sap_test.dim_plant ps
  ON sh.plant = ps.PLANT_KEY
LEFT JOIN sandbox_others.sap_test.dim_plant ph
  ON st.plant = ph.PLANT_KEY;

-- Statement 2: access (D-08)
GRANT SELECT ON TABLE sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair TO `account users`;
```

Constants: none beyond the literals in the SQL (`'UNKNOWN PLANT'` per BR-03; schedule `0 45 6 * * ?` / `Asia/Singapore` per D-06).

#### 7. Edge cases and errors

| Case | Input | Expected behaviour |
|---|---|---|
| Plant code absent from `dim_plant` | `short_plant` or `stock_plant` = `1000` | row kept; name `UNKNOWN PLANT`; country NULL (BR-03) |
| Material absent from the material master | material with no `MATERIAL_KEY` row in the latest batch | row kept; `material_description`, `material_type`, `product_family`, `criticality` NULL (0 rows today) |
| Blank criticality or description | `CRITICALITY = ''` | stored as NULL (`NULLIF`); passes `criticality_valid` |
| Criticality outside A, B, C | a new value in the master | warning count in the event log (`criticality_valid` has no `ON VIOLATION` clause); row kept |
| Stock total zero or negative for a plant and material | `SUM(TOTAL_QUANTITY) <= 0` | excluded by `HAVING` |
| Material short and in stock in the same plant | `short.plant = stock.plant` | excluded by the join condition; `plants_differ` fails the update if a row ever slips through |
| Null key or non-positive movable quantity | — | refresh fails (`FAIL UPDATE`); yesterday's rows stay (RF-03) |
| Several storage locations in one plant | 2 stock rows for one plant and material | summed into one `stock_qty` |

#### 8. Acceptance criteria and tests

Test file: `MRPX-002/tests/integration/test_f01_transfer_candidate_view.py` (written in v1/F-02) · fixtures: `integration_connection`, `golden_row`

| AC ID | Given / When / Then | Test name | Fixture data | Expected |
|---|---|---|---|---|
| AC-F01-1 | Given T-01 refreshed, when `SELECT COUNT(*) AS n, SUM(CASE WHEN material IS NULL OR short_plant IS NULL OR stock_plant IS NULL THEN 1 ELSE 0 END) AS null_keys FROM sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair` runs, then `n > 0` and `null_keys = 0` (proves skill §7 not-null keys) | `test_f01_ac1_rows_and_no_null_keys` | real view | `n` ≥ 1 (115,077 on 2026-08-30 / 202608); `null_keys = 0` |
| AC-F01-2 | Given T-01, when `SELECT COUNT(*) AS n, COUNT(DISTINCT CONCAT(material, '|', short_plant, '|', stock_plant)) AS d FROM ...` runs, then `n = d` (proves grain) and `SELECT COUNT(*) FROM ... WHERE short_plant = stock_plant OR movable_qty <= 0 OR movable_qty > shortage_qty OR movable_qty > stock_qty` returns 0 (proves `LEAST`) | `test_f01_ac2_grain_unique` | real view | `n = d`; second query 0 |
| AC-F01-3 | Given `mrp_snapshot_date = '2026-08-30'` and `inventory_month = '202608'`, when `SELECT * FROM ... WHERE material = '1236-561-01' AND short_plant = '3300' AND stock_plant = '1000'` runs, then exactly one row equals `golden_row` on every column except `ETL_LOADDATE`, and `SELECT MAX(movable_qty) FROM ...` = `336233.000` (proves PRD §6, BR-02, BR-05, BR-06, BR-03) | `test_f01_ac3_golden_example` | `golden_row` | one row; equality on 18 columns; max movable 336233.000; the test is skipped with reason "snapshot moved on" when `MAX(mrp_snapshot_date) <> DATE '2026-08-30'` |
| AC-F01-4 | Given T-01, when `DESCRIBE sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair` runs, then the column names in order are exactly the 20 names of TSD §5.2 and none of `TOTAL_VALUE`, `STANDARD_PRICE`, `MFG_COST_PRICE`, `CREATED_BY`, `CHANGED_BY`, `REGION` appears (proves BR-09, BR-04) | `test_f01_ac4_column_list` | real view | exact list match |

Integration / evaluation checks (run by a human in dev): run `SELECT COUNT(*) FROM sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair WHERE short_plant = '3300'` → `6256` for the 2026-08-30 snapshot; open the view's pipeline in the Pipelines UI → one completed refresh, expectation `criticality_valid` with 0 failed rows.

#### 9. Build-ready checklist (Planner self-check)

- [x] Every related feature (this set or earlier sets) is listed in §2 with the exact names this feature uses
- [x] Every path, table, column, API, agent and config key exists in the TSD, in §2, or earlier in this feature
- [x] Every join is written out in §4 (tables, type, condition, filters, expected result)
- [x] Every step is exact; SQL given for non-trivial logic; all constants have values
- [x] Every acceptance criterion has a test with literal fixture data and expected output
- [x] Edge cases cover empty, invalid, not-found and permission cases where relevant
- [x] No open words (e.g., such as, appropriate, as needed, TBD, etc., choose, decide)

**Out of scope for this feature:** a notebook or job for the refresh (the schedule is in the definition, skill §9); bronze or silver copies of the sources; amount, price or value columns; a per-material or per-plant aggregate view; a filter on `REGION`; filtering out plant `1000` or any other unmatched plant; recomputing weeks late from `REQUIRED_WEEK`; a Lakeview dashboard; the test file (v1/F-02).

**How a human tests it:** (1) In the SQL editor run `SELECT * FROM sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair WHERE material = '1236-561-01' AND short_plant = '3300'` → one row with `stock_plant 1000`, `movable_qty 336233.000`, `weeks_late 9`, `criticality A`, `product_family PE`. (2) Run `SELECT COUNT(*) FROM sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair` → `115077`. (3) Open the view in Catalog Explorer → 20 columns with comments, schedule visible.

---

### v1/F-02 — Integration tests and shared fixtures for T-01

| Field | Value |
|---|---|
| Module / layer | `tests` — tests (TSD §4, §11.1, §12) |
| Type | test-only |
| Size | S |
| Depends on / related to | v1/F-01 (depends on) — details in §2 below |
| PRD refs | PRD-MRPX-002 §6, §7, §9 |
| TSD refs | §5.2 T-01, §12 fixtures, §16 D-05, D-11 |
| Standards applied | BR-02, BR-03, BR-05, BR-06, BR-09, skill:data_engineering §7, §8, skill:data_engineering references/delivery-specs.md §4 |

#### 1. Context

A materialized view is tested with SQL assertions, not a unit-test notebook (`data_engineering` skill §8). This feature writes those assertions as pytest integration tests so they run again after every refresh and in every later pull request, and it creates the shared fixtures (`golden_row`, `sample_rows`, `fake_connection`, `settings`, `client`, `integration_connection`) that every v2 feature reuses.

#### 2. Related features — context from earlier work

| Feature | Set | Relationship | What it built that this feature uses (exact names) | Status |
|---|---|---|---|---|
| v1/F-01 | v1 | depends on | materialized view `sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair` with the 20 columns `material`, `material_description`, `material_type`, `product_family`, `criticality`, `short_plant`, `short_plant_name`, `short_plant_country`, `stock_plant`, `stock_plant_name`, `stock_plant_country`, `shortage_qty`, `stock_qty`, `movable_qty`, `weeks_late`, `unit_of_measure`, `mrp_snapshot_date`, `inventory_month`, `ETL_LOADDATE`, `SOURCE_SNAPSHOT_DATE` | To do |

**Rules carried over from those features:** unmatched plant name is exactly `UNKNOWN PLANT` with NULL country (v1/F-01); blank master values are NULL, never empty strings (v1/F-01); grain is (`material`, `short_plant`, `stock_plant`) (v1/F-01).

#### 3. Files

| Action | Path | Purpose |
|---|---|---|
| create | `MRPX-002/tests/__init__.py` | empty package marker |
| create | `MRPX-002/tests/conftest.py` | fixtures of TSD §12: `golden_row`, `sample_rows`, `FakeRow`, `FakeCursor`, `FakeConnection`, `fake_connection`, `settings`, `client`, `integration_connection`; the `client` and `settings` fixtures import lazily from `backend` and are skipped with reason "backend not built yet" when the import fails, so they are usable from v2/F-01 on |
| create | `MRPX-002/tests/integration/__init__.py` | empty package marker |
| create | `MRPX-002/tests/integration/test_f01_transfer_candidate_view.py` | the four tests of v1/F-01 §8, marker `integration` |
| create | `MRPX-002/pytest.ini` | `[pytest] markers = integration: needs a dev workspace and real tables` and `testpaths = tests` |
| create | `MRPX-002/tests/unit/__init__.py` | empty package marker |
| create | `MRPX-002/tests/unit/test_f02_fixtures.py` | the single unit test AC-F02-3 of the fake connection |

No other files may be created or changed.

#### 4. Data

| Table (TSD §5.2 ID) | Columns read | Columns written | Write mode |
|---|---|---|---|
| T-01 `sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair` | all 20 columns | — | — |

**Joins (this feature):**

| Left | Right | Type | Condition | Filters | Expected result |
|---|---|---|---|---|---|
| — | — | — | none: single-table assertions | — | — |

#### 5. Interfaces

**API (TSD §6.1):** none.

**Functions added by this feature:**

```python
@pytest.fixture
def golden_row() -> dict[str, object]:
    """The PRD §6 golden example as one T-01 row (values in TSD §12)."""

@pytest.fixture
def sample_rows(golden_row: dict[str, object]) -> list[dict[str, object]]:
    """Three T-01 rows: golden_row, row B (1226-807-01), row C (1232-405-01) exactly as TSD §12."""

class FakeRow:
    def __init__(self, data: dict[str, object]) -> None: ...
    def asDict(self) -> dict[str, object]:
        """Return the row as a dict (mirrors databricks.sql Row.asDict)."""

class FakeCursor:
    calls: list[tuple[str, dict[str, object] | None]]
    def execute(self, sql: str, parameters: dict[str, object] | None = None) -> None:
        """Record (sql, parameters) and load the next queued result."""
    def fetchall(self) -> list[FakeRow]: ...
    def fetchone(self) -> FakeRow | None: ...
    def close(self) -> None: ...

class FakeConnection:
    queued_results: list[list[dict[str, object]]]
    last_cursor: FakeCursor | None
    def cursor(self) -> FakeCursor: ...
    def close(self) -> None: ...

@pytest.fixture
def fake_connection() -> FakeConnection:
    """Connection whose cursors return queued_results in order and record every call."""

@pytest.fixture
def integration_connection():
    """Real databricks.sql connection from DATABRICKS_HOST, DATABRICKS_WAREHOUSE_ID, DATABRICKS_TOKEN; skips when missing."""
```

| Input | Output |
|---|---|
| `fake_connection.queued_results = [[golden_row]]`; `cur = fake_connection.cursor(); cur.execute("SELECT 1", {"a": 1}); cur.fetchall()` | `[FakeRow(golden_row)]`; `cur.calls == [("SELECT 1", {"a": 1})]` |

#### 6. Implementation steps

1. Create `MRPX-002/pytest.ini` with the marker and `testpaths` from §3.
2. In `MRPX-002/tests/conftest.py` define `golden_row` and `sample_rows` with the literal values of TSD §12 (use `decimal.Decimal` and `datetime.date`).
3. Define `FakeRow`, `FakeCursor`, `FakeConnection` and the `fake_connection` fixture as in §5. `FakeCursor` supports `with` (returns itself, `close()` on exit). `FakeConnection.cursor()` stores the cursor in `last_cursor`.
4. Define `settings` and `client` fixtures: `from backend.config import Settings` and `from backend.main import create_app` inside the fixture body wrapped in `try/except ImportError: pytest.skip("backend not built yet")`; `settings` values as TSD §12; `client = TestClient(create_app(settings, connection_factory=lambda: fake_connection))`.
5. Define `integration_connection`: read the three environment variables; `pytest.skip("integration environment not set")` when any is missing; `databricks.sql.connect(server_hostname=host_without_scheme, http_path=f"/sql/1.0/warehouses/{warehouse_id}", access_token=token)`; yield; close.
6. In `test_f01_transfer_candidate_view.py` mark the module `pytestmark = pytest.mark.integration`, define `VIEW = "sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair"` and `EXPECTED_COLUMNS` (the 20 names in order), and implement the four tests of v1/F-01 §8 with the SQL written there; `test_f01_ac3_golden_example` first runs `SELECT MAX(mrp_snapshot_date) FROM VIEW` and skips when the value is not `date(2026, 8, 30)`; compare `Decimal` columns with `==` and dates with `datetime.date`.

```sql
-- used by test_f01_ac4_column_list
DESCRIBE sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair
```

Constants: `VIEW = "sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair"`, `GOLDEN_SNAPSHOT = date(2026, 8, 30)`, `GOLDEN_MONTH = "202608"`, `FORBIDDEN_COLUMNS = ("TOTAL_VALUE", "STANDARD_PRICE", "MFG_COST_PRICE", "CREATED_BY", "CHANGED_BY", "REGION")` (defined at the top of `test_f01_transfer_candidate_view.py`).

#### 7. Edge cases and errors

| Case | Input | Expected behaviour |
|---|---|---|
| Environment variables missing | no `DATABRICKS_TOKEN` | all integration tests skipped with reason "integration environment not set" |
| Snapshot moved on | `MAX(mrp_snapshot_date) = 2026-09-15` | `test_f01_ac3_golden_example` skipped with reason "snapshot moved on"; the other three tests still run |
| Backend not built | `import backend` fails | `settings` and `client` fixtures skip; v1 tests unaffected |
| Empty queued results | `fake_connection.queued_results = []` and `execute` called | `IndexError("no queued result for query")` raised by `FakeCursor.execute` |

#### 8. Acceptance criteria and tests

Test file: `MRPX-002/tests/integration/test_f01_transfer_candidate_view.py` · fixtures: `integration_connection`, `golden_row`

| AC ID | Given / When / Then | Test name | Fixture data | Expected |
|---|---|---|---|---|
| AC-F02-1 | Given the dev environment variables, when `pytest -m integration tests/integration/test_f01_transfer_candidate_view.py` runs, then 4 tests pass (or AC-F01-3 is skipped when the snapshot moved on) | the four tests of v1/F-01 §8 | real view, `golden_row` | 4 passed, 0 failed |
| AC-F02-2 | Given no environment variables, when the same command runs, then 4 tests are skipped and the exit code is 0 | same four tests | — | 4 skipped |
| AC-F02-3 | Given `fake_connection` with `queued_results = [[golden_row]]`, when `cursor().execute("SELECT 1", {"a": 1})` then `fetchall()` runs, then one `FakeRow` whose `asDict()` equals `golden_row` is returned and `calls == [("SELECT 1", {"a": 1})]` | `test_f02_ac3_fake_connection_records_calls` in `MRPX-002/tests/unit/test_f02_fixtures.py` | `golden_row` | as stated |

Integration / evaluation checks (run by a human in dev): `cd MRPX-002 && DATABRICKS_HOST=<host> DATABRICKS_WAREHOUSE_ID=<id> DATABRICKS_TOKEN=<pat> pytest -m integration -q` → `4 passed` (or `3 passed, 1 skipped`).

#### 9. Build-ready checklist (Planner self-check)

- [x] Every related feature (this set or earlier sets) is listed in §2 with the exact names this feature uses
- [x] Every path, table, column, API, agent and config key exists in the TSD, in §2, or earlier in this feature
- [x] Every join is written out in §4 (tables, type, condition, filters, expected result)
- [x] Every step is exact; SQL given for non-trivial logic; all constants have values
- [x] Every acceptance criterion has a test with literal fixture data and expected output
- [x] Edge cases cover empty, invalid, not-found and permission cases where relevant
- [x] No open words (e.g., such as, appropriate, as needed, TBD, etc., choose, decide)

**Out of scope for this feature:** a unit-test notebook; tests of the app (v2); CI pipeline files; changing the view definition (v1/F-01); a `tests/unit/test_f02_fixtures.py` beyond the single test AC-F02-3.

**How a human tests it:** (1) run the command above in the dev workspace terminal → 4 passed. (2) unset `DATABRICKS_TOKEN` and run again → 4 skipped.

---

### v1/F-03 — Validation extract per short plant (VAL-01)

| Field | Value |
|---|---|
| Module / layer | `pipelines` — pipelines (TSD §4, §11.1) |
| Type | job (manual SQL script) |
| Size | S |
| Depends on / related to | v1/F-01 (depends on) — details in §2 below |
| PRD refs | PRD-MRPX-002 §3 (success measure), US-1, US-2, US-3, US-5 |
| TSD refs | §2.2 VAL-01, §5.2 T-01, §16 Q-03 |
| Standards applied | BR-09, skill:data_engineering references/delivery-specs.md §1, §4 |

#### 1. Context

The PRD's success measure is that planners of two plants chosen by the product owner confirm the listed transfer candidates are real and complete, and that description, criticality and product family match the material master. This feature gives the analyst one parameterised query over T-01 that produces exactly the list for one plant, in the column order planners read, so the confirmation happens on the governed view and not on an ad-hoc query.

#### 2. Related features — context from earlier work

| Feature | Set | Relationship | What it built that this feature uses (exact names) | Status |
|---|---|---|---|---|
| v1/F-01 | v1 | depends on | `sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair` columns `material`, `material_description`, `material_type`, `product_family`, `criticality`, `short_plant`, `short_plant_name`, `short_plant_country`, `stock_plant`, `stock_plant_name`, `stock_plant_country`, `shortage_qty`, `stock_qty`, `movable_qty`, `weeks_late`, `unit_of_measure`, `mrp_snapshot_date`, `inventory_month` | To do |

**Rules carried over from those features:** read only the gold view, never the sources (delivery-specs §1); `UNKNOWN PLANT` is a valid plant name (v1/F-01).

#### 3. Files

| Action | Path | Purpose |
|---|---|---|
| create | `MRPX-002/pipelines/sql/validation_extract_by_plant.sql` | parameterised SELECT with `:short_plant`, header comment with run instructions |

No other files may be created or changed.

#### 4. Data

| Table (TSD §5.2 ID) | Columns read | Columns written | Write mode |
|---|---|---|---|
| T-01 `sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair` | the 18 business columns listed in §2 | — | — |

**Joins (this feature):**

| Left | Right | Type | Condition | Filters | Expected result |
|---|---|---|---|---|---|
| — | — | — | none: single view | `short_plant = :short_plant` | all pairs of the plant; 6,256 rows for `3300` on 2026-08-30 |

#### 5. Interfaces

**API (TSD §6.1):** none.

**Functions added by this feature:** none.

| Input | Output |
|---|---|
| `:short_plant = '3300'` | 6,256 rows ordered by `movable_qty` desc, `material`, `stock_plant`; first row `1236-561-01` / `1000` / `336233.000` |

#### 6. Implementation steps

1. Create `MRPX-002/pipelines/sql/validation_extract_by_plant.sql` with the header comment: project id, feature id `v1/F-03`, purpose, and the instruction "Run in the Databricks SQL editor; set parameter `short_plant` to the 4-character plant code; export the result as CSV and share it with the plant's planners for confirmation (PRD §3)."
2. Add the query below.

```sql
-- MRPX-002 v1/F-03 VAL-01: all transfer candidates of one short plant, for planner confirmation (PRD §3).
SELECT material,
       material_description,
       material_type,
       product_family,
       criticality,
       short_plant,
       short_plant_name,
       short_plant_country,
       stock_plant,
       stock_plant_name,
       stock_plant_country,
       shortage_qty,
       stock_qty,
       movable_qty,
       weeks_late,
       unit_of_measure,
       mrp_snapshot_date,
       inventory_month
FROM sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair
WHERE short_plant = :short_plant
ORDER BY movable_qty DESC, material ASC, stock_plant ASC
```

Constants: none (the plant code is the parameter `:short_plant`).

#### 7. Edge cases and errors

| Case | Input | Expected behaviour |
|---|---|---|
| Plant with no candidates | `:short_plant = '9999'` | 0 rows, no error |
| Parameter not set | — | the SQL editor asks for the parameter; the query does not run without it |
| Lower-case code | `'35b0'` | 0 rows (codes are stored as given by SAP, upper case); the header comment states "use the code as shown in SAP" |

#### 8. Acceptance criteria and tests

Test file: none (manual SQL check, delivery-specs §4 allows one manual step) · fixtures: —

| AC ID | Given / When / Then | Test name | Fixture data | Expected |
|---|---|---|---|---|
| AC-F03-1 | Given T-01 at snapshot 2026-08-30, when the query runs with `:short_plant = '3300'`, then 6,256 rows return and the first row is `material 1236-561-01`, `stock_plant 1000`, `movable_qty 336233.000`, `weeks_late 9`, `criticality A`, `product_family PE` | manual: `validation_extract_3300` | `:short_plant = '3300'` | 6,256 rows; first row as stated |
| AC-F03-2 | Given the same, when the query runs with `:short_plant = '9999'`, then 0 rows return without error | manual: `validation_extract_unknown_plant` | `:short_plant = '9999'` | 0 rows |

Integration / evaluation checks (run by a human in dev): run both parameter values in the SQL editor; export the `3300` result to CSV; the row count equals `SELECT COUNT(*) FROM sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair WHERE short_plant = '3300'`.

#### 9. Build-ready checklist (Planner self-check)

- [x] Every related feature (this set or earlier sets) is listed in §2 with the exact names this feature uses
- [x] Every path, table, column, API, agent and config key exists in the TSD, in §2, or earlier in this feature
- [x] Every join is written out in §4 (tables, type, condition, filters, expected result)
- [x] Every step is exact; SQL given for non-trivial logic; all constants have values
- [x] Every acceptance criterion has a test with literal fixture data and expected output
- [x] Edge cases cover empty, invalid, not-found and permission cases where relevant
- [x] No open words (e.g., such as, appropriate, as needed, TBD, etc., choose, decide)

**Out of scope for this feature:** a notebook, job or scheduled export; writing the extract to a table or volume; a dashboard; joining back to the sources; adding columns not in T-01.

**How a human tests it:** (1) open the file in the SQL editor, set `short_plant = 3300`, run → 6,256 rows, first row `1236-561-01`. (2) set `short_plant = 9999`, run → 0 rows.

---

## 5. Change log

| Date | Change | Features | Source (PRD / CR) | Approved by |
|---|---|---|---|---|
| 2026-11-11 | Initial set | all | PRD-MRPX-002 v0.1 | |
