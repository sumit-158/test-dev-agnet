# Feature Set v2 — Shortage Rebalancing: Short in One Plant, Stock Held in Another (MRPX-002) — PoC app

| Field | Value |
|---|---|
| Feature set | v2 — PoC app: Databricks App for the planners |
| TSD version | TSD-MRPX-002 v1.0 |
| Source PRD(s) | PRD-MRPX-002 §2, §4 (US-1 … US-7), §4b, §7, §9 |
| Status | Draft |
| Approved by / date | |
| Depends on sets | v1 merged |
| Context library version | 2026.11.04-1 |

## 1. What this feature set delivers

**Goal:** After this set the Databricks App `mrpx-002-transfer-candidates` runs in the dev workspace behind workspace SSO; a planner filters the transfer candidates of T-01 by plant, country, criticality and product family on SCR-01, sees the MRP result date and the inventory month, and opens one material on SCR-02 to see every plant holding stock for it.

**Builds on (already exists before this set):** T-01 `sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair` (v1/F-01); shared fixtures `golden_row`, `sample_rows`, `fake_connection`, `settings`, `client`, `integration_connection` in `MRPX-002/tests/conftest.py` (v1/F-02).

**Adds:** API-01, API-02, API-03, API-04 (TSD §6.1); EXT-01 (TSD §6.2); APP with SCR-01 and SCR-02 (TSD §4); bundle `databricks.yml` and `app.yaml` (TSD §10).

| In scope | Out of scope (later set or never) |
|---|---|
| FastAPI backend reading only T-01 through the SQL warehouse | Any write, transfer order or SAP change (never, PRD §8) |
| React frontend with two screens and all states of `ui_ux_design` §6 | Alerts, e-mails, Lakeview dashboard (never, PRD §4b) |
| Unit tests with fakes; one integration test against the real warehouse | Row-level plant restriction per user (never in PoC, D-14) |
| Asset Bundle deployment to target `dev` | Prod target, monitoring, SLAs (MVP / Prod sets) |

## 2. Set exit criteria

| ID | The set is done when… | Checked by |
|---|---|---|
| EX-v2-1 | `cd MRPX-002 && pytest -q` (unit) and `cd MRPX-002/frontend && npm test` pass with 0 failures | tests |
| EX-v2-2 | `test_f08_app_against_warehouse.py` passes: `GET /api/transfer-candidates?short_plant=3300&limit=50` returns `total = 6256`, first item `material = '1236-561-01'`, and five timed calls each finish under 2 s | test (integration) |
| EX-v2-3 | On the deployed app, SCR-01 filtered to plant 3300 shows the golden row first with `Movable 336,233 MM`, `9 weeks late`, `Criticality A`, `PE`, and the line `MRP result 30 Aug 2026 · Inventory month Aug 2026`; clicking it opens SCR-02 showing plant `1000 UNKNOWN PLANT` with stock `356,500` and `Covers 100%` | manual check against `plan/wireframe.html` (one step) |

## 3. Build order

| # | Feature | Title | Module | Depends on / related to | Size | Status | PR |
|---|---|---|---|---|---|---|---|
| 1 | v2/F-01 | Backend scaffold, settings, connection factory and health route (API-04) | `backend` | v1/F-02 | S | To do | |
| 2 | v2/F-02 | Repository and response models for T-01 | `backend` (repositories) | v2/F-01, v1/F-01, v1/F-02 | M | To do | |
| 3 | v2/F-03 | Candidate list and filter routes (API-01, API-03) | `backend` (services, routers) | v2/F-02 | M | To do | |
| 4 | v2/F-04 | Material detail route (API-02) | `backend` (services, routers) | v2/F-03 | S | To do | |
| 5 | v2/F-05 | Frontend scaffold, ASM tokens, API client and formatting | `frontend` | v2/F-03, v2/F-04 | S | To do | |
| 6 | v2/F-06 | SCR-01 Transfer candidates page | `frontend` | v2/F-05 | M | To do | |
| 7 | v2/F-07 | SCR-02 Material shortage detail page | `frontend` | v2/F-06 | M | To do | |
| 8 | v2/F-08 | Asset Bundle, dev deployment and warehouse integration test | `bundle` | v2/F-07 | S | To do | |

Feature references are written `v{set}/F-{nn}` so a link to a feature in another feature set is unambiguous.
Status: To do → In progress → In review → Human testing → Done (Blocked, Dropped). Only a human sets Done.

---

## 4. Features

### v2/F-01 — Backend scaffold, settings, connection factory and health route (API-04)

| Field | Value |
|---|---|
| Module / layer | `backend` — main, config, constants (TSD §4, §11.1) |
| Type | API |
| Size | S |
| Depends on / related to | v1/F-02 (depends on: fixtures `settings`, `client`) — details in §2 below |
| PRD refs | PRD-MRPX-002 §4b (Databricks App, SQL warehouse), §9 |
| TSD refs | §3 App framework and App data access, §4, §6.1 API-04, §6.2 EXT-01, §8, §10, §11.1, §11.2 |
| Standards applied | BR-09, skill:data_engineering §8 (no hard-coded environments, no secrets), skill:ui_ux_design §10 (static build served by the backend) |

#### 1. Context

Every later backend feature plugs into one app factory with settings read from the environment Databricks Apps provides (warehouse id from the `sql-warehouse` resource, service-principal credentials, catalog and schema from `app.yaml`). This feature creates that factory, the fail-fast settings, the project constants, the connection factory to the SQL warehouse, the health route API-04, and serving of the built frontend from `backend/static/`.

#### 2. Related features — context from earlier work

| Feature | Set | Relationship | What it built that this feature uses (exact names) | Status |
|---|---|---|---|---|
| v1/F-02 | v1 | depends on | fixtures in `MRPX-002/tests/conftest.py`: `settings` (`Settings(catalog='sandbox_others', schema_gold='gold', view_transfer_candidates='agg_mrpx_transfer_candidate_plant_pair', databricks_host='https://example.cloud.databricks.com', databricks_warehouse_id='abc123')`), `client` (`TestClient(create_app(settings, connection_factory=lambda: fake_connection))`), `fake_connection`; `pytest.ini` with marker `integration` | Done after v1 |

**Rules carried over from those features:** `client` and `settings` import `backend.config.Settings` and `backend.main.create_app` lazily; this feature makes those imports succeed (v1/F-02).

#### 3. Files

| Action | Path | Purpose |
|---|---|---|
| create | `MRPX-002/backend/__init__.py` | empty package marker |
| create | `MRPX-002/backend/config.py` | `Settings`, `load_settings()`, `make_connection_factory(settings)` |
| create | `MRPX-002/backend/constants.py` | constants listed in §6 |
| create | `MRPX-002/backend/main.py` | `create_app(settings, connection_factory)`, `get_app()`, API-04, static serving, 422 handler for `ValueError` |
| create | `MRPX-002/app.yaml` | Databricks App start command and environment |
| create | `MRPX-002/pyproject.toml` | project metadata, ruff config (line length 100), dependency pins |
| create | `MRPX-002/requirements.txt` | runtime pins for Databricks Apps |
| create | `MRPX-002/tests/unit/__init__.py` | empty package marker |
| create | `MRPX-002/tests/unit/test_f01_app_factory.py` | tests for this feature |

No other files may be created or changed.

#### 4. Data

| Table (TSD §5.2 ID) | Columns read | Columns written | Write mode |
|---|---|---|---|
| — | none (no SQL in this feature) | — | — |

**Joins (this feature):**

| Left | Right | Type | Condition | Filters | Expected result |
|---|---|---|---|---|---|
| — | — | — | none | — | — |

#### 5. Interfaces

**API (TSD §6.1):** `GET /api/health` — request none → response `200 {"status": "ok", "catalog": "sandbox_others", "schema_gold": "gold"}`; no error responses.

**Functions added by this feature:**

```python
@dataclass(frozen=True)
class Settings:
    catalog: str
    schema_gold: str
    view_transfer_candidates: str
    databricks_host: str
    databricks_warehouse_id: str

    @property
    def view_full_name(self) -> str:
        """Three-part name `{catalog}.{schema_gold}.{view_transfer_candidates}`."""

def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Read CATALOG, SCHEMA_GOLD, VIEW_TRANSFER_CANDIDATES, DATABRICKS_HOST, DATABRICKS_WAREHOUSE_ID.
    Raises RuntimeError("Missing required environment variable <NAME>") on the first missing or empty key."""

def make_connection_factory(settings: Settings) -> Callable[[], Any]:
    """Return a zero-argument callable opening a databricks.sql connection to the app's warehouse,
    authenticated with databricks.sdk.core.Config(host=settings.databricks_host).authenticate."""

def create_app(settings: Settings, connection_factory: Callable[[], Any]) -> FastAPI:
    """Build the FastAPI app: state.settings, state.connection_factory, API-04, static files, error handlers."""

def get_app() -> FastAPI:
    """Factory for uvicorn --factory: create_app(load_settings(), make_connection_factory(load_settings()))."""
```

| Input | Output |
|---|---|
| `load_settings({"CATALOG": "sandbox_others", "SCHEMA_GOLD": "gold", "VIEW_TRANSFER_CANDIDATES": "agg_mrpx_transfer_candidate_plant_pair", "DATABRICKS_HOST": "https://example.cloud.databricks.com", "DATABRICKS_WAREHOUSE_ID": "abc123"})` | `Settings(...)` with `view_full_name == "sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair"` |
| `load_settings({"CATALOG": "sandbox_others"})` | `RuntimeError("Missing required environment variable SCHEMA_GOLD")` |
| `client.get("/api/health")` | `200 {"status": "ok", "catalog": "sandbox_others", "schema_gold": "gold"}` |

#### 6. Implementation steps

1. Create `MRPX-002/pyproject.toml`: `[project] name = "mrpx-002-shortage-rebalancing"`, `version = "0.1.0"`, `requires-python = ">=3.11,<3.12"`, `dependencies` = the five runtime pins of TSD §3 (`fastapi==0.115.5`, `uvicorn==0.32.0`, `pydantic==2.9.2`, `databricks-sql-connector==3.6.0`, `databricks-sdk==0.38.0`); `[project.optional-dependencies] dev = ["pytest==8.3.3", "httpx==0.27.2", "ruff==0.7.3"]`; `[tool.ruff] line-length = 100`; `[tool.ruff.lint] select = ["E", "F", "I", "UP", "B"]`.
2. Create `MRPX-002/requirements.txt` with the same five runtime pins, one per line.
3. Create `MRPX-002/backend/constants.py` with exactly: `PAGE_SIZE_DEFAULT = 50`; `PAGE_SIZE_MAX = 200`; `SORT_COLUMNS = ("movable_qty", "shortage_qty", "stock_qty", "weeks_late")`; `SORT_DIRECTIONS = ("asc", "desc")`; `SORT_DEFAULT = "movable_qty"`; `SORT_DIR_DEFAULT = "desc"`; `CRITICALITY_VALUES = ("A", "B", "C", "NONE")`; `CRITICALITY_NONE = "NONE"`; `UNKNOWN_PLANT_NAME = "UNKNOWN PLANT"`; `PLANT_CODE_PATTERN = r"^[A-Z0-9]{1,4}$"`; `COUNTRY_PATTERN = r"^[A-Z]{2}$"`; `PRODUCT_FAMILY_PATTERN = r"^[A-Z0-9]{1,4}$"`; `MATERIAL_PATTERN = r"^[A-Za-z0-9._/-]{1,40}$"`; `ERROR_UNAVAILABLE = "The transfer candidates could not be loaded. Try again."`; `REQUIRED_ENV = ("CATALOG", "SCHEMA_GOLD", "VIEW_TRANSFER_CANDIDATES", "DATABRICKS_HOST", "DATABRICKS_WAREHOUSE_ID")`.
4. Create `MRPX-002/backend/config.py` with `Settings`, `load_settings` (iterates `REQUIRED_ENV` in order, uses `os.environ` when `environ` is `None`, strips values, raises on empty) and `make_connection_factory`: the returned callable runs `cfg = databricks.sdk.core.Config(host=settings.databricks_host)` and `return databricks.sql.connect(server_hostname=cfg.host.removeprefix("https://"), http_path=f"/sql/1.0/warehouses/{settings.databricks_warehouse_id}", credentials_provider=lambda: cfg.authenticate)`. Both imports (`databricks.sdk.core`, `databricks.sql`) happen inside the callable so unit tests never need network.
5. Create `MRPX-002/backend/main.py`:
   - `create_app(settings, connection_factory)`: `app = FastAPI(title="MRPX-002 Shortage Rebalancing", docs_url=None, redoc_url=None)`; set `app.state.settings = settings`, `app.state.connection_factory = connection_factory`; register `@app.exception_handler(ValueError)` returning `JSONResponse(status_code=422, content={"detail": str(exc)})`; add route `GET /api/health` returning `{"status": "ok", "catalog": settings.catalog, "schema_gold": settings.schema_gold}`; compute `static_dir = Path(__file__).parent / "static"`; if `static_dir.is_dir()`, mount `StaticFiles(directory=static_dir, html=True)` at `/` after the API routes and register a `404` handler that returns `FileResponse(static_dir / "index.html")` for any request path not starting with `/api/` (single-page-app fallback) and the default JSON 404 otherwise.
   - `get_app()`: `settings = load_settings(); return create_app(settings, make_connection_factory(settings))`.
6. Create `MRPX-002/app.yaml`:

```yaml
command: ["uvicorn", "backend.main:get_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
env:
  - name: DATABRICKS_WAREHOUSE_ID
    valueFrom: sql-warehouse
  - name: CATALOG
    value: sandbox_others
  - name: SCHEMA_GOLD
    value: gold
  - name: VIEW_TRANSFER_CANDIDATES
    value: agg_mrpx_transfer_candidate_plant_pair
```

7. Write the tests of §8 in `MRPX-002/tests/unit/test_f01_app_factory.py` using the `settings` and `client` fixtures.

Constants: all in `MRPX-002/backend/constants.py` (step 3).

#### 7. Edge cases and errors

| Case | Input | Expected behaviour |
|---|---|---|
| Missing environment key | `DATABRICKS_WAREHOUSE_ID` absent | `RuntimeError("Missing required environment variable DATABRICKS_WAREHOUSE_ID")` at start-up; the app does not start |
| Empty value | `CATALOG=""` | same `RuntimeError` for `CATALOG` |
| No static build present | `backend/static` missing (unit tests) | API routes work; `GET /` returns 404 JSON `{"detail": "Not Found"}` |
| Unknown API path | `GET /api/nothing` | 404 JSON, not `index.html` |
| Unknown frontend path with build present | `GET /materials/1236-561-01/plants/3300` | `index.html` (200) so the router renders SCR-02 |
| `X-Forwarded-Email` header present | any | never read, never logged (PRD §9) |

#### 8. Acceptance criteria and tests

Test file: `MRPX-002/tests/unit/test_f01_app_factory.py` · fixtures: `settings`, `client`

| AC ID | Given / When / Then | Test name | Fixture data | Expected |
|---|---|---|---|---|
| AC-F01-1 | Given the five environment keys, when `load_settings(env)` runs, then `view_full_name` is the three-part name | `test_f01_ac1_settings_full_name` | the dict of §5 row 1 | `"sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair"` |
| AC-F01-2 | Given a dict missing `SCHEMA_GOLD`, when `load_settings` runs, then `RuntimeError` names the key | `test_f01_ac2_missing_key_fails_fast` | `{"CATALOG": "sandbox_others"}` | `pytest.raises(RuntimeError, match="SCHEMA_GOLD")` |
| AC-F01-3 | Given the app, when `GET /api/health` is called, then 200 with status, catalog and schema | `test_f01_ac3_health` | `client` | `{"status": "ok", "catalog": "sandbox_others", "schema_gold": "gold"}` |
| AC-F01-4 | Given no static build, when `GET /api/nothing` is called, then 404 JSON | `test_f01_ac4_unknown_api_path_404` | `client` | status 404, body `{"detail": "Not Found"}` |

Integration / evaluation checks (run by a human in dev): `cd MRPX-002 && CATALOG=sandbox_others SCHEMA_GOLD=gold VIEW_TRANSFER_CANDIDATES=agg_mrpx_transfer_candidate_plant_pair DATABRICKS_HOST=<host> DATABRICKS_WAREHOUSE_ID=<id> uvicorn backend.main:get_app --factory --port 8000` then `curl localhost:8000/api/health` → the JSON above.

#### 9. Build-ready checklist (Planner self-check)

- [x] Every related feature (this set or earlier sets) is listed in §2 with the exact names this feature uses
- [x] Every path, table, column, API, agent and config key exists in the TSD, in §2, or earlier in this feature
- [x] Every join is written out in §4 (tables, type, condition, filters, expected result)
- [x] Every step is exact; SQL given for non-trivial logic; all constants have values
- [x] Every acceptance criterion has a test with literal fixture data and expected output
- [x] Edge cases cover empty, invalid, not-found and permission cases where relevant
- [x] No open words (e.g., such as, appropriate, as needed, TBD, etc., choose, decide)

**Out of scope for this feature:** any route other than `/api/health`; any SQL; CORS middleware (frontend and API share one origin); authentication code (Databricks Apps provides SSO); logging of user identity; `databricks.yml` (v2/F-08).

**How a human tests it:** (1) run the uvicorn command above and `curl localhost:8000/api/health` → 200 JSON. (2) unset `DATABRICKS_WAREHOUSE_ID` and start again → process exits with the `RuntimeError` message.

---

### v2/F-02 — Repository and response models for T-01

| Field | Value |
|---|---|
| Module / layer | `backend` — repositories, models (TSD §4, §11.1) |
| Type | API (data access layer) |
| Size | M |
| Depends on / related to | v2/F-01 (depends on), v1/F-01 (reads T-01), v1/F-02 (fixtures) — details in §2 below |
| PRD refs | PRD-MRPX-002 US-1 … US-7, §7 (under 5 s) |
| TSD refs | §5.2 T-01, §6.1 API-01 … API-03 response shapes, §6.2 EXT-01, §9 Latency, §12 |
| Standards applied | BR-09, skill:data_engineering references/delivery-specs.md §1 (consumers read gold only), references/spark-and-python.md §3 (filter early, select only needed columns) |

#### 1. Context

All SQL of the app lives in one repository that reads only T-01 with parameterised statements, so routers and services never touch the warehouse and the view stays the single interface between data and app. This feature also defines the Pydantic models that API-01 … API-03 return, converting `Decimal` quantities to `float` and dates to ISO strings for the frontend.

#### 2. Related features — context from earlier work

| Feature | Set | Relationship | What it built that this feature uses (exact names) | Status |
|---|---|---|---|---|
| v1/F-01 | v1 | reads | `sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair` with columns `material` STRING, `material_description` STRING, `material_type` STRING, `product_family` STRING, `criticality` STRING (A, B, C or NULL), `short_plant` STRING, `short_plant_name` STRING, `short_plant_country` STRING, `stock_plant` STRING, `stock_plant_name` STRING, `stock_plant_country` STRING, `shortage_qty` DECIMAL(27,3), `stock_qty` DECIMAL(27,3), `movable_qty` DECIMAL(27,3), `weeks_late` INT, `unit_of_measure` STRING, `mrp_snapshot_date` DATE, `inventory_month` STRING | Done after v1 |
| v1/F-02 | v1 | depends on | fixtures `golden_row`, `sample_rows` (three dict rows), `fake_connection` (`FakeConnection.queued_results`, `FakeCursor.calls`, `FakeRow.asDict()`), `settings` | Done after v1 |
| v2/F-01 | v2 | depends on | `backend.config.Settings` (`view_full_name`), `backend.constants` (`SORT_COLUMNS`, `SORT_DIRECTIONS`, `CRITICALITY_NONE`, `ERROR_UNAVAILABLE`) | To do |

**Rules carried over from those features:** unmatched plant name `UNKNOWN PLANT` with NULL country (v1/F-01); blank master values are NULL (v1/F-01); repository raises, never logs identity (v2/F-01).

#### 3. Files

| Action | Path | Purpose |
|---|---|---|
| create | `MRPX-002/backend/models.py` | `CandidateFilters`, `CandidateRow`, `CandidatePage`, `HoldingPlant`, `MaterialDetail`, `PlantOption`, `FilterOptions`, `Freshness`, `HealthResponse` |
| create | `MRPX-002/backend/repositories/__init__.py` | empty package marker |
| create | `MRPX-002/backend/repositories/transfer_candidate_repository.py` | `DataUnavailableError`, `TransferCandidateRepository` |
| create | `MRPX-002/tests/unit/repositories/__init__.py` | empty package marker |
| create | `MRPX-002/tests/unit/repositories/test_f02_transfer_candidate_repository.py` | tests for this feature |

No other files may be created or changed.

#### 4. Data

| Table (TSD §5.2 ID) | Columns read | Columns written | Write mode |
|---|---|---|---|
| T-01 `sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair` | the 18 business columns of §2 (never `ETL_LOADDATE`, `SOURCE_SNAPSHOT_DATE`) | — | — |

**Joins (this feature):**

| Left | Right | Type | Condition | Filters | Expected result |
|---|---|---|---|---|---|
| — | — | — | none: single view, four statements (§6) | WHERE built from `CandidateFilters` | paged rows, count, detail, distinct options |

#### 5. Interfaces

**API (TSD §6.1):** none directly; this feature returns the response bodies of API-01 (`CandidatePage`), API-02 (`MaterialDetail`), API-03 (`FilterOptions`).

**Functions added by this feature:**

```python
class CandidateFilters(BaseModel):
    short_plants: list[str] = []
    countries: list[str] = []
    criticalities: list[str] = []      # values among A, B, C, NONE
    product_families: list[str] = []

class CandidateRow(BaseModel):
    material: str
    material_description: str | None
    material_type: str | None
    product_family: str | None
    criticality: str | None
    short_plant: str
    short_plant_name: str
    short_plant_country: str | None
    stock_plant: str
    stock_plant_name: str
    stock_plant_country: str | None
    shortage_qty: float
    stock_qty: float
    movable_qty: float
    weeks_late: int
    unit_of_measure: str | None
    mrp_snapshot_date: date
    inventory_month: str

class CandidatePage(BaseModel):
    items: list[CandidateRow]
    total: int
    mrp_snapshot_date: date | None
    inventory_month: str | None
    limit: int
    offset: int

class HoldingPlant(BaseModel):
    stock_plant: str
    stock_plant_name: str
    stock_plant_country: str | None
    stock_qty: float
    movable_qty: float

class MaterialDetail(BaseModel):
    material: str
    material_description: str | None
    material_type: str | None
    product_family: str | None
    criticality: str | None
    short_plant: str
    short_plant_name: str
    short_plant_country: str | None
    shortage_qty: float
    weeks_late: int
    unit_of_measure: str | None
    mrp_snapshot_date: date
    inventory_month: str
    holding_plants: list[HoldingPlant]

class PlantOption(BaseModel):
    code: str
    name: str
    country: str | None

class FilterOptions(BaseModel):
    short_plants: list[PlantOption]
    countries: list[str]
    criticalities: list[str]           # subset of A, B, C, NONE present in the view
    product_families: list[str]
    mrp_snapshot_date: date | None
    inventory_month: str | None

class Freshness(BaseModel):
    mrp_snapshot_date: date | None
    inventory_month: str | None

class HealthResponse(BaseModel):
    status: str
    catalog: str
    schema_gold: str

class DataUnavailableError(RuntimeError):
    """Raised when the warehouse or connector fails; message is ERROR_UNAVAILABLE."""

class TransferCandidateRepository:
    def __init__(self, settings: Settings, connection_factory: Callable[[], Any]) -> None: ...
    def fetch_candidates(self, filters: CandidateFilters, sort_by: str, sort_dir: str,
                         limit: int, offset: int) -> CandidatePage:
        """Rows + total for the filters. Raises ValueError when sort_by or sort_dir is not whitelisted."""
    def fetch_material_detail(self, material: str, short_plant: str) -> MaterialDetail | None:
        """All holding plants of one shortage, movable_qty desc; None when no row exists."""
    def fetch_filter_options(self) -> FilterOptions:
        """Distinct plants, countries, criticalities, families and the freshness."""
    def fetch_freshness(self) -> Freshness:
        """MAX(mrp_snapshot_date), MAX(inventory_month) of the view."""
```

| Input | Output |
|---|---|
| `fetch_candidates(CandidateFilters(short_plants=["3300"], criticalities=["A", "NONE"]), "movable_qty", "desc", 50, 0)` with `queued_results = [sample_rows, [{"total": 3}], [{"mrp_snapshot_date": date(2026, 8, 30), "inventory_month": "202608"}]]` | `CandidatePage(items=[3 rows], total=3, mrp_snapshot_date=date(2026, 8, 30), inventory_month="202608", limit=50, offset=0)`; first executed SQL contains `short_plant IN (:sp0)` and `(criticality IN (:cr0) OR criticality IS NULL)` with parameters `{"sp0": "3300", "cr0": "A", "limit": 50, "offset": 0}` |
| `fetch_material_detail("1236-561-01", "3300")` with `queued_results = [[golden_row]]` | `MaterialDetail(material="1236-561-01", ..., shortage_qty=336233.0, weeks_late=9, holding_plants=[HoldingPlant(stock_plant="1000", stock_plant_name="UNKNOWN PLANT", stock_plant_country=None, stock_qty=356500.0, movable_qty=336233.0)])` |
| `fetch_material_detail("0000-000-00", "3300")` with `queued_results = [[]]` | `None` |

#### 6. Implementation steps

1. Create `MRPX-002/backend/models.py` with the classes of §5 (Pydantic v2, `model_config = ConfigDict(extra="forbid")`).
2. In `transfer_candidate_repository.py` define `COLUMNS = ("material", "material_description", "material_type", "product_family", "criticality", "short_plant", "short_plant_name", "short_plant_country", "stock_plant", "stock_plant_name", "stock_plant_country", "shortage_qty", "stock_qty", "movable_qty", "weeks_late", "unit_of_measure", "mrp_snapshot_date", "inventory_month")` and `SELECT_COLUMNS = ", ".join(COLUMNS)`.
3. Implement `_build_where(filters: CandidateFilters) -> tuple[str, dict[str, str]]`: for each non-empty list add one predicate with numbered parameters — `short_plant IN (:sp0, :sp1, …)`, `short_plant_country IN (:co0, …)`, `product_family IN (:pf0, …)`; for criticalities split `NONE` out: with values `V` and flag `has_none`, predicate is `criticality IN (:cr0, …)` when only values, `criticality IS NULL` when only `NONE`, `(criticality IN (:cr0, …) OR criticality IS NULL)` when both; join predicates with ` AND `; return `("WHERE " + joined, params)` or `("", {})` when no predicate.
4. Implement `_run(sql: str, params: dict) -> list[dict]`: `conn = self._connection_factory()`; `with conn.cursor() as cur: cur.execute(sql, parameters=params or None); rows = [r.asDict() for r in cur.fetchall()]`; `conn.close()`; wrap the body in `try/except Exception as exc: raise DataUnavailableError(ERROR_UNAVAILABLE) from exc`, except `ValueError` which is re-raised unchanged.
5. Implement `fetch_candidates`: validate `sort_by in SORT_COLUMNS` and `sort_dir in SORT_DIRECTIONS` else `ValueError(f"sort_by must be one of {', '.join(SORT_COLUMNS)}")` / `ValueError("sort_dir must be asc or desc")`; run statement A (rows), statement B (count), then `fetch_freshness()`; map rows with `_to_candidate_row(d)` (`float()` on the three quantities, `int()` on `weeks_late`).
6. Implement `fetch_material_detail`: run statement C; return `None` on no rows; build `MaterialDetail` from the first row and `holding_plants` from all rows in order.
7. Implement `fetch_filter_options`: run statements D1, D2, D3, D4 then `fetch_freshness()`; `criticalities` keeps the order `A, B, C, NONE` filtered to the values present.
8. Implement `fetch_freshness`: statement E.
9. Write the tests of §8.

```sql
-- Statement A (rows); {view} = settings.view_full_name; {where} from _build_where; {sort_by} {sort_dir} whitelisted
SELECT material, material_description, material_type, product_family, criticality,
       short_plant, short_plant_name, short_plant_country,
       stock_plant, stock_plant_name, stock_plant_country,
       shortage_qty, stock_qty, movable_qty, weeks_late, unit_of_measure,
       mrp_snapshot_date, inventory_month
FROM {view}
{where}
ORDER BY {sort_by} {sort_dir}, material ASC, stock_plant ASC
LIMIT :limit OFFSET :offset

-- Statement B (count)
SELECT COUNT(*) AS total FROM {view} {where}

-- Statement C (detail)
SELECT material, material_description, material_type, product_family, criticality,
       short_plant, short_plant_name, short_plant_country,
       stock_plant, stock_plant_name, stock_plant_country,
       shortage_qty, stock_qty, movable_qty, weeks_late, unit_of_measure,
       mrp_snapshot_date, inventory_month
FROM {view}
WHERE material = :material AND short_plant = :short_plant
ORDER BY movable_qty DESC, stock_plant ASC

-- Statement D1 (plants)
SELECT DISTINCT short_plant AS code, short_plant_name AS name, short_plant_country AS country
FROM {view} ORDER BY code ASC
-- Statement D2 (countries)
SELECT DISTINCT short_plant_country AS country FROM {view}
WHERE short_plant_country IS NOT NULL ORDER BY country ASC
-- Statement D3 (criticalities)
SELECT DISTINCT COALESCE(criticality, 'NONE') AS criticality FROM {view} ORDER BY criticality ASC
-- Statement D4 (families)
SELECT DISTINCT product_family FROM {view}
WHERE product_family IS NOT NULL ORDER BY product_family ASC

-- Statement E (freshness)
SELECT MAX(mrp_snapshot_date) AS mrp_snapshot_date, MAX(inventory_month) AS inventory_month FROM {view}
```

Constants: `COLUMNS`, `SELECT_COLUMNS` (step 2) in the repository file; `SORT_COLUMNS`, `SORT_DIRECTIONS`, `CRITICALITY_NONE`, `ERROR_UNAVAILABLE` from `backend/constants.py`.

#### 7. Edge cases and errors

| Case | Input | Expected behaviour |
|---|---|---|
| No filters | `CandidateFilters()` | `where = ""`, `params = {}`; all rows paged |
| Only `NONE` criticality | `criticalities=["NONE"]` | predicate `criticality IS NULL`, no `cr` parameters |
| Sort column not whitelisted | `sort_by="material_description"` | `ValueError` before any SQL runs; `FakeCursor.calls` empty |
| Warehouse error | connector raises `Exception("socket closed")` | `DataUnavailableError("The transfer candidates could not be loaded. Try again.")` with `__cause__` set |
| Detail not found | 0 rows | `None` |
| Empty view | statement E returns `(None, None)` | `Freshness(mrp_snapshot_date=None, inventory_month=None)`; `CandidatePage.total = 0` |
| Values with NULL country or description | `golden_row` | `None` in the model, never the string `"None"` |

#### 8. Acceptance criteria and tests

Test file: `MRPX-002/tests/unit/repositories/test_f02_transfer_candidate_repository.py` · fixtures: `settings`, `fake_connection`, `golden_row`, `sample_rows`

| AC ID | Given / When / Then | Test name | Fixture data | Expected |
|---|---|---|---|---|
| AC-F02-1 | Given queued `[sample_rows, [{"total": 3}], [{"mrp_snapshot_date": date(2026, 8, 30), "inventory_month": "202608"}]]`, when `fetch_candidates(CandidateFilters(short_plants=["3300"], criticalities=["A", "NONE"]), "movable_qty", "desc", 50, 0)` runs, then the page has 3 items, total 3, freshness set, and the first SQL contains `short_plant IN (:sp0)` and `(criticality IN (:cr0) OR criticality IS NULL)` with params `{"sp0": "3300", "cr0": "A", "limit": 50, "offset": 0}` | `test_f02_ac1_candidates_where_and_params` | as stated | items[0].material == "1236-561-01", items[0].movable_qty == 336233.0, total 3, params equal |
| AC-F02-2 | Given queued `[[golden_row]]`, when `fetch_material_detail("1236-561-01", "3300")` runs, then a `MaterialDetail` with one holding plant `1000` / `UNKNOWN PLANT` / `None` / 356500.0 / 336233.0 is returned and params are `{"material": "1236-561-01", "short_plant": "3300"}` | `test_f02_ac2_material_detail_golden` | `golden_row` | as stated; `shortage_qty == 336233.0`, `weeks_late == 9` |
| AC-F02-3 | Given queued `[[]]`, when `fetch_material_detail("0000-000-00", "3300")` runs, then `None` | `test_f02_ac3_material_detail_not_found` | — | `None` |
| AC-F02-4 | Given a connection factory raising `Exception("socket closed")`, when `fetch_freshness()` runs, then `DataUnavailableError` with message `ERROR_UNAVAILABLE`; and given `sort_by="material_description"`, `fetch_candidates` raises `ValueError` with no SQL executed | `test_f02_ac4_errors` | — | both assertions hold |

Integration / evaluation checks (run by a human in dev): none here (covered by v2/F-08).

#### 9. Build-ready checklist (Planner self-check)

- [x] Every related feature (this set or earlier sets) is listed in §2 with the exact names this feature uses
- [x] Every path, table, column, API, agent and config key exists in the TSD, in §2, or earlier in this feature
- [x] Every join is written out in §4 (tables, type, condition, filters, expected result)
- [x] Every step is exact; SQL given for non-trivial logic; all constants have values
- [x] Every acceptance criterion has a test with literal fixture data and expected output
- [x] Edge cases cover empty, invalid, not-found and permission cases where relevant
- [x] No open words (e.g., such as, appropriate, as needed, TBD, etc., choose, decide)

**Out of scope for this feature:** routes or services; caching; reading any table other than T-01; aggregations (sums of `movable_qty` across rows, R-01); free-text search; reading `ETL_LOADDATE` or `SOURCE_SNAPSHOT_DATE`; connection pooling.

**How a human tests it:** `cd MRPX-002 && pytest tests/unit/repositories -q` → 4 passed.

---

### v2/F-03 — Candidate list and filter routes (API-01, API-03)

| Field | Value |
|---|---|
| Module / layer | `backend` — services, routers (TSD §4, §11.1) |
| Type | API |
| Size | M |
| Depends on / related to | v2/F-02 (depends on), v2/F-01 (extends `create_app`) — details in §2 below |
| PRD refs | PRD-MRPX-002 US-1, US-2, US-3, US-4, US-6, US-7 |
| TSD refs | §6.1 API-01, API-03, §2.4 RF-01, §11.2 Errors |
| Standards applied | BR-04 (country filter on `short_plant_country`), skill:data_engineering references/delivery-specs.md §3 (filters are columns of the view), skill:ui_ux_design §6 (error copy) |

#### 1. Context

SCR-01 needs two routes: the filter options with freshness, and the filtered, sorted, paged list. This feature adds the service that validates every input against the whitelists and patterns of `backend/constants.py`, the two routers, the repository wiring in `create_app`, and the 503 handler for warehouse errors.

#### 2. Related features — context from earlier work

| Feature | Set | Relationship | What it built that this feature uses (exact names) | Status |
|---|---|---|---|---|
| v2/F-01 | v2 | extends | `backend.main.create_app(settings, connection_factory)` with `app.state.settings`, `app.state.connection_factory`, the `ValueError` → 422 handler; `backend.constants` (`PAGE_SIZE_DEFAULT`, `PAGE_SIZE_MAX`, `SORT_COLUMNS`, `SORT_DIRECTIONS`, `SORT_DEFAULT`, `SORT_DIR_DEFAULT`, `CRITICALITY_VALUES`, `PLANT_CODE_PATTERN`, `COUNTRY_PATTERN`, `PRODUCT_FAMILY_PATTERN`, `ERROR_UNAVAILABLE`) | To do |
| v2/F-02 | v2 | depends on | `backend.repositories.transfer_candidate_repository.TransferCandidateRepository(settings, connection_factory)` with `fetch_candidates(filters, sort_by, sort_dir, limit, offset) -> CandidatePage`, `fetch_filter_options() -> FilterOptions`; `DataUnavailableError`; models `CandidateFilters`, `CandidatePage`, `FilterOptions` in `backend/models.py` | To do |
| v1/F-02 | v1 | depends on | fixtures `client`, `fake_connection`, `sample_rows`, `golden_row` | Done after v1 |

**Rules carried over from those features:** routers never run SQL, services never import FastAPI (TSD §11.1); `NONE` means `criticality IS NULL` (v2/F-02); repository errors are `DataUnavailableError` (v2/F-02).

#### 3. Files

| Action | Path | Purpose |
|---|---|---|
| create | `MRPX-002/backend/services/__init__.py` | empty package marker |
| create | `MRPX-002/backend/services/transfer_candidate_service.py` | `list_candidates`, `get_filter_options`, validators |
| create | `MRPX-002/backend/routers/__init__.py` | empty package marker |
| create | `MRPX-002/backend/routers/transfer_candidates.py` | API-01 route |
| create | `MRPX-002/backend/routers/filters.py` | API-03 route |
| modify | `MRPX-002/backend/main.py` | in `create_app`: build `app.state.repository = TransferCandidateRepository(settings, connection_factory)`, include the two routers, add `DataUnavailableError` → 503 handler; nothing else changes |
| create | `MRPX-002/tests/unit/routers/__init__.py` | empty package marker |
| create | `MRPX-002/tests/unit/routers/test_f03_candidates_and_filters.py` | tests for this feature |

No other files may be created or changed.

#### 4. Data

| Table (TSD §5.2 ID) | Columns read | Columns written | Write mode |
|---|---|---|---|
| T-01 (through v2/F-02 only) | as v2/F-02 | — | — |

**Joins (this feature):**

| Left | Right | Type | Condition | Filters | Expected result |
|---|---|---|---|---|---|
| — | — | — | none (no SQL in this feature) | — | — |

#### 5. Interfaces

**API (TSD §6.1):**
- `GET /api/transfer-candidates` — query `short_plant: list[str]` (repeatable), `country: list[str]`, `criticality: list[str]`, `product_family: list[str]`, `sort_by: str = "movable_qty"`, `sort_dir: str = "desc"`, `limit: int = 50`, `offset: int = 0` → `200 CandidatePage`; errors `422 {"detail": "<validation message>"}`, `503 {"detail": "The transfer candidates could not be loaded. Try again."}`.
- `GET /api/filters` — no request → `200 FilterOptions`; error `503` as above.

**Functions added by this feature:**

```python
def list_candidates(repo: TransferCandidateRepository, short_plant: list[str], country: list[str],
                    criticality: list[str], product_family: list[str], sort_by: str, sort_dir: str,
                    limit: int, offset: int) -> CandidatePage:
    """Validate inputs and return the page. Raises ValueError with the messages in §6 step 2."""

def get_filter_options(repo: TransferCandidateRepository) -> FilterOptions:
    """Return the filter options and freshness."""

def _validate_codes(values: list[str], pattern: str, field: str) -> list[str]:
    """Upper-case and strip each value; raise ValueError(f"{field} must match {pattern}") on mismatch."""
```

| Input | Output |
|---|---|
| `GET /api/transfer-candidates?short_plant=3300&criticality=A&criticality=NONE` with queued `[sample_rows, [{"total": 3}], [{"mrp_snapshot_date": date(2026, 8, 30), "inventory_month": "202608"}]]` | `200` body with `total 3`, `items[0].material "1236-561-01"`, `mrp_snapshot_date "2026-08-30"`, `inventory_month "202608"`, `limit 50`, `offset 0` |
| `GET /api/transfer-candidates?limit=500` | `422 {"detail": "limit must be between 1 and 200"}` |
| `GET /api/transfer-candidates?criticality=X` | `422 {"detail": "criticality must be one of A, B, C, NONE"}` |

#### 6. Implementation steps

1. In `transfer_candidate_service.py` implement `_validate_codes` with `re.fullmatch(pattern, value.strip().upper())`.
2. Implement `list_candidates`: validate `short_plant` with `PLANT_CODE_PATTERN` (field name `short_plant`), `country` with `COUNTRY_PATTERN`, `product_family` with `PRODUCT_FAMILY_PATTERN`; criticality: upper-case each value and require membership in `CRITICALITY_VALUES` else `ValueError("criticality must be one of A, B, C, NONE")`; `sort_by in SORT_COLUMNS` else `ValueError("sort_by must be one of movable_qty, shortage_qty, stock_qty, weeks_late")`; `sort_dir in SORT_DIRECTIONS` else `ValueError("sort_dir must be asc or desc")`; `1 <= limit <= PAGE_SIZE_MAX` else `ValueError("limit must be between 1 and 200")`; `offset >= 0` else `ValueError("offset must be 0 or more")`; then `return repo.fetch_candidates(CandidateFilters(short_plants=..., countries=..., criticalities=..., product_families=...), sort_by, sort_dir, limit, offset)`.
3. Implement `get_filter_options` as `return repo.fetch_filter_options()`.
4. In `routers/transfer_candidates.py` create `router = APIRouter(prefix="/api/transfer-candidates", tags=["transfer-candidates"])` and `GET ""` with `fastapi.Query` parameters (`short_plant: list[str] = Query(default=[])` and the others; defaults from `constants`); fetch `repo = request.app.state.repository`; return `list_candidates(...)`.
5. In `routers/filters.py` create `router = APIRouter(prefix="/api/filters", tags=["filters"])` and `GET ""` returning `get_filter_options(repo)`.
6. Modify `backend/main.py` `create_app`: after setting state, `app.state.repository = TransferCandidateRepository(settings, connection_factory)`; `app.include_router(transfer_candidates.router)`; `app.include_router(filters.router)`; add `@app.exception_handler(DataUnavailableError)` returning `JSONResponse(status_code=503, content={"detail": ERROR_UNAVAILABLE})`. Routers are included before the static mount.
7. Write the tests of §8.

Constants: all from `backend/constants.py` (v2/F-01); no new constants.

#### 7. Edge cases and errors

| Case | Input | Expected behaviour |
|---|---|---|
| Lower-case codes | `short_plant=3300&country=kr` | accepted, upper-cased to `KR` |
| Invalid plant code | `short_plant=33000` | 422 `short_plant must match ^[A-Z0-9]{1,4}$` |
| Invalid sort | `sort_by=material` | 422 message of step 2 |
| Non-integer limit | `limit=abc` | 422 (FastAPI type validation) |
| Warehouse down | repository raises `DataUnavailableError` | 503 with `ERROR_UNAVAILABLE` |
| No filters at all | `GET /api/transfer-candidates` | 200, first 50 rows by `movable_qty desc` |

#### 8. Acceptance criteria and tests

Test file: `MRPX-002/tests/unit/routers/test_f03_candidates_and_filters.py` · fixtures: `client`, `fake_connection`, `sample_rows`, `golden_row`

| AC ID | Given / When / Then | Test name | Fixture data | Expected |
|---|---|---|---|---|
| AC-F03-1 | Given queued `[sample_rows, [{"total": 3}], [{"mrp_snapshot_date": date(2026, 8, 30), "inventory_month": "202608"}]]`, when `GET /api/transfer-candidates?short_plant=3300&criticality=A&criticality=NONE` is called, then 200 with `total 3`, first item `1236-561-01`, `mrp_snapshot_date "2026-08-30"`, `inventory_month "202608"` | `test_f03_ac1_list_ok` | as stated | as stated |
| AC-F03-2 | Given the app, when `GET /api/transfer-candidates?limit=500` and `?criticality=X` are called, then 422 with the exact messages | `test_f03_ac2_validation_422` | — | `"limit must be between 1 and 200"`, `"criticality must be one of A, B, C, NONE"` |
| AC-F03-3 | Given queued `[[{"code": "3300", "name": "ASM Korea Ltd.", "country": "KR"}], [{"country": "KR"}], [{"criticality": "A"}, {"criticality": "C"}, {"criticality": "NONE"}], [{"product_family": "CP"}, {"product_family": "PE"}], [{"mrp_snapshot_date": date(2026, 8, 30), "inventory_month": "202608"}]]`, when `GET /api/filters` is called, then 200 with `short_plants == [{"code": "3300", "name": "ASM Korea Ltd.", "country": "KR"}]`, `countries == ["KR"]`, `criticalities == ["A", "C", "NONE"]`, `product_families == ["CP", "PE"]`, `mrp_snapshot_date == "2026-08-30"` | `test_f03_ac3_filters_ok` | as stated | as stated |
| AC-F03-4 | Given a `fake_connection` whose `cursor()` raises `Exception("socket closed")`, when `GET /api/filters` is called, then 503 `{"detail": "The transfer candidates could not be loaded. Try again."}` | `test_f03_ac4_warehouse_down_503` | — | as stated |

Integration / evaluation checks (run by a human in dev): none here (v2/F-08).

#### 9. Build-ready checklist (Planner self-check)

- [x] Every related feature (this set or earlier sets) is listed in §2 with the exact names this feature uses
- [x] Every path, table, column, API, agent and config key exists in the TSD, in §2, or earlier in this feature
- [x] Every step is exact; SQL given for non-trivial logic; all constants have values
- [x] Every join is written out in §4 (tables, type, condition, filters, expected result)
- [x] Every acceptance criterion has a test with literal fixture data and expected output
- [x] Edge cases cover empty, invalid, not-found and permission cases where relevant
- [x] No open words (e.g., such as, appropriate, as needed, TBD, etc., choose, decide)

**Out of scope for this feature:** the detail route (v2/F-04); CSV export; free-text search; per-user plant defaults; response caching; OpenAPI docs page.

**How a human tests it:** `cd MRPX-002 && pytest tests/unit/routers/test_f03_candidates_and_filters.py -q` → 4 passed.

---

### v2/F-04 — Material detail route (API-02)

| Field | Value |
|---|---|
| Module / layer | `backend` — services, routers (TSD §4, §11.1) |
| Type | API |
| Size | S |
| Depends on / related to | v2/F-03 (extends) — details in §2 below |
| PRD refs | PRD-MRPX-002 US-2, US-5, US-7 |
| TSD refs | §6.1 API-02, §2.4 RF-02, §11.2 Errors |
| Standards applied | BR-03 (unknown plant kept), skill:ui_ux_design §6 (not-found copy) |

#### 1. Context

SCR-02 shows one shortage (material in a short plant) with every plant holding stock for it. This feature adds the service function, the `NotFoundError`, its 404 handler and the route.

#### 2. Related features — context from earlier work

| Feature | Set | Relationship | What it built that this feature uses (exact names) | Status |
|---|---|---|---|---|
| v2/F-03 | v2 | extends | `backend/routers/transfer_candidates.py` with `router` (prefix `/api/transfer-candidates`); `backend/services/transfer_candidate_service.py` with `_validate_codes(values, pattern, field)`; `create_app` wiring `app.state.repository` | To do |
| v2/F-02 | v2 | depends on | `TransferCandidateRepository.fetch_material_detail(material, short_plant) -> MaterialDetail | None`; model `MaterialDetail` | To do |
| v2/F-01 | v2 | depends on | `backend.constants.MATERIAL_PATTERN`, `PLANT_CODE_PATTERN` | To do |
| v1/F-02 | v1 | depends on | fixtures `client`, `fake_connection`, `golden_row` | Done after v1 |

**Rules carried over from those features:** validation messages use the `_validate_codes` format (v2/F-03); material codes keep their case (pattern allows upper and lower case), plant codes are upper-cased (v2/F-03).

#### 3. Files

| Action | Path | Purpose |
|---|---|---|
| modify | `MRPX-002/backend/services/transfer_candidate_service.py` | add `NotFoundError` and `get_material_detail` only |
| modify | `MRPX-002/backend/routers/transfer_candidates.py` | add route `GET /{material}/{short_plant}` only |
| modify | `MRPX-002/backend/main.py` | add `NotFoundError` → 404 handler only |
| create | `MRPX-002/tests/unit/routers/test_f04_material_detail.py` | tests for this feature |

No other files may be created or changed.

#### 4. Data

| Table (TSD §5.2 ID) | Columns read | Columns written | Write mode |
|---|---|---|---|
| T-01 (through v2/F-02 only) | as v2/F-02 statement C | — | — |

**Joins (this feature):**

| Left | Right | Type | Condition | Filters | Expected result |
|---|---|---|---|---|---|
| — | — | — | none | — | — |

#### 5. Interfaces

**API (TSD §6.1):** `GET /api/transfer-candidates/{material}/{short_plant}` → `200 MaterialDetail`; `404 {"detail": "Material 1236-561-01 is not short in plant 3300 in the current MRP result."}`; `422` on an invalid code; `503` on warehouse error.

**Functions added by this feature:**

```python
class NotFoundError(LookupError):
    """Raised when no T-01 row exists for the material and short plant."""

def get_material_detail(repo: TransferCandidateRepository, material: str, short_plant: str) -> MaterialDetail:
    """Validate codes, fetch the detail. Raises NotFoundError(f"Material {material} is not short in plant {short_plant} in the current MRP result.")."""
```

| Input | Output |
|---|---|
| `GET /api/transfer-candidates/1236-561-01/3300` with queued `[[golden_row]]` | `200` with `material "1236-561-01"`, `shortage_qty 336233.0`, `weeks_late 9`, `holding_plants[0] == {"stock_plant": "1000", "stock_plant_name": "UNKNOWN PLANT", "stock_plant_country": null, "stock_qty": 356500.0, "movable_qty": 336233.0}` |
| `GET /api/transfer-candidates/0000-000-00/3300` with queued `[[]]` | `404 {"detail": "Material 0000-000-00 is not short in plant 3300 in the current MRP result."}` |

#### 6. Implementation steps

1. In the service add `NotFoundError(LookupError)` and `get_material_detail`: `material = _validate_codes([material], MATERIAL_PATTERN, "material")[0]` — the material pattern keeps case, so `_validate_codes` must not upper-case when `pattern is MATERIAL_PATTERN` (add a keyword argument `uppercase: bool = True` to `_validate_codes`, passed `False` here); `short_plant = _validate_codes([short_plant], PLANT_CODE_PATTERN, "short_plant")[0]`; `detail = repo.fetch_material_detail(material, short_plant)`; raise `NotFoundError(...)` when `None`.
2. In the router add `@router.get("/{material}/{short_plant}", response_model=MaterialDetail)` calling `get_material_detail(request.app.state.repository, material, short_plant)`.
3. In `main.py` add `@app.exception_handler(NotFoundError)` returning `JSONResponse(status_code=404, content={"detail": str(exc)})`.
4. Write the tests of §8.

Constants: none new.

#### 7. Edge cases and errors

| Case | Input | Expected behaviour |
|---|---|---|
| Not found | material with no rows | 404 with the exact message |
| Invalid material characters | `1236 561` (space) | 422 `material must match ^[A-Za-z0-9._/-]{1,40}$` |
| Lower-case plant | `/1236-561-01/3300` vs `/1236-561-01/33a0` | plant upper-cased to `33A0` before the query |
| Warehouse down | `DataUnavailableError` | 503 |

#### 8. Acceptance criteria and tests

Test file: `MRPX-002/tests/unit/routers/test_f04_material_detail.py` · fixtures: `client`, `fake_connection`, `golden_row`

| AC ID | Given / When / Then | Test name | Fixture data | Expected |
|---|---|---|---|---|
| AC-F04-1 | Given queued `[[golden_row]]`, when `GET /api/transfer-candidates/1236-561-01/3300` is called, then 200 with the body of §5 row 1 and params `{"material": "1236-561-01", "short_plant": "3300"}` recorded | `test_f04_ac1_detail_golden` | `golden_row` | as stated |
| AC-F04-2 | Given queued `[[]]`, when `GET /api/transfer-candidates/0000-000-00/3300` is called, then 404 with the exact message | `test_f04_ac2_detail_not_found` | — | `{"detail": "Material 0000-000-00 is not short in plant 3300 in the current MRP result."}` |
| AC-F04-3 | Given the app, when `GET /api/transfer-candidates/1236%20561/3300` is called, then 422 with `material must match ^[A-Za-z0-9._/-]{1,40}$` | `test_f04_ac3_detail_invalid_material` | — | as stated |

Integration / evaluation checks (run by a human in dev): none here (v2/F-08).

#### 9. Build-ready checklist (Planner self-check)

- [x] Every related feature (this set or earlier sets) is listed in §2 with the exact names this feature uses
- [x] Every path, table, column, API, agent and config key exists in the TSD, in §2, or earlier in this feature
- [x] Every join is written out in §4 (tables, type, condition, filters, expected result)
- [x] Every step is exact; SQL given for non-trivial logic; all constants have values
- [x] Every acceptance criterion has a test with literal fixture data and expected output
- [x] Edge cases cover empty, invalid, not-found and permission cases where relevant
- [x] No open words (e.g., such as, appropriate, as needed, TBD, etc., choose, decide)

**Out of scope for this feature:** material history across snapshots; links to SAP; aggregating stock across holding plants; any change to API-01 or API-03.

**How a human tests it:** `cd MRPX-002 && pytest tests/unit/routers/test_f04_material_detail.py -q` → 3 passed.

---

### v2/F-05 — Frontend scaffold, ASM tokens, API client and formatting

| Field | Value |
|---|---|
| Module / layer | `frontend` — frontend (TSD §4, §11.1) |
| Type | app page (scaffold) |
| Size | S |
| Depends on / related to | v2/F-03, v2/F-04 (calls their routes) — details in §2 below |
| PRD refs | PRD-MRPX-002 §4b (one app), §7 |
| TSD refs | §3 App framework, Allowed libraries; §4 frontend files; §11.2 UI; §12 Frontend unit |
| Standards applied | skill:ui_ux_design §2, §3, §4, §8, §9, §10 |

#### 1. Context

Both screens share one shell (navy header, page container, 1024 px breakpoint), one token set, one typed API client and one set of formatters. This feature builds that foundation so SCR-01 and SCR-02 only add pages and components.

#### 2. Related features — context from earlier work

| Feature | Set | Relationship | What it built that this feature uses (exact names) | Status |
|---|---|---|---|---|
| v2/F-03 | v2 | calls | `GET /api/transfer-candidates` (query `short_plant`, `country`, `criticality`, `product_family`, `sort_by`, `sort_dir`, `limit`, `offset`) → `CandidatePage`; `GET /api/filters` → `FilterOptions`; errors `422` / `503` with `{"detail": string}` | To do |
| v2/F-04 | v2 | calls | `GET /api/transfer-candidates/{material}/{short_plant}` → `MaterialDetail`; `404 {"detail": string}` | To do |
| v2/F-02 | v2 | mirrors | field names and types of `CandidateRow`, `CandidatePage`, `HoldingPlant`, `MaterialDetail`, `PlantOption`, `FilterOptions` (dates as ISO `YYYY-MM-DD` strings, quantities as numbers) | To do |
| v2/F-01 | v2 | serves | `backend/static/` is served at `/` with SPA fallback | To do |

**Rules carried over from those features:** the API returns `detail` strings written for users (v2/F-03, v2/F-04); criticality `NONE` means not set (v2/F-02).

#### 3. Files

| Action | Path | Purpose |
|---|---|---|
| create | `MRPX-002/frontend/package.json` | name `mrpx-002-frontend`, scripts `dev`, `build`, `test`, pinned dependencies of TSD §3 |
| create | `MRPX-002/frontend/vite.config.ts` | React plugin; `build.outDir = "../backend/static"`, `emptyOutDir = true`; dev proxy `/api` → `http://localhost:8000`; `test: { environment: "jsdom", setupFiles: ["src/__tests__/setup.ts"], globals: true }` |
| create | `MRPX-002/frontend/tsconfig.json` | strict TypeScript, `jsx: react-jsx`, `types: ["vitest/globals", "@testing-library/jest-dom"]` |
| create | `MRPX-002/frontend/tailwind.config.js` | `content: ["./index.html", "./src/**/*.{ts,tsx}"]`; `theme.extend.colors.asm` = the 11 tokens of §6 step 3; `fontFamily.sans = ["Inter", "system-ui", "sans-serif"]`, `fontFamily.mono = ["JetBrains Mono", "ui-monospace", "monospace"]`; `boxShadow.card` |
| create | `MRPX-002/frontend/postcss.config.js` | tailwindcss, autoprefixer |
| create | `MRPX-002/frontend/index.html` | `<div id="root">`, title "Shortage rebalancing", `lang="en"` |
| create | `MRPX-002/frontend/src/main.tsx` | renders `<App />` in `BrowserRouter` |
| create | `MRPX-002/frontend/src/App.tsx` | header, routes `/` and `/materials/:material/plants/:shortPlant`, placeholders replaced in F-06 / F-07 |
| create | `MRPX-002/frontend/src/index.css` | Tailwind layers; `:root` with the `--asm-*` variables; component classes `btn-primary`, `btn-outline`, `btn-ghost`, `card`, `chip-ok`, `chip-warn`, `chip-err`, `chip-mute`, `chip-crit-a`, `chip-crit-b`, `chip-crit-c`, `focus-ring` |
| create | `MRPX-002/frontend/src/types.ts` | TypeScript interfaces mirroring the models |
| create | `MRPX-002/frontend/src/api.ts` | `ApiError`, `fetchCandidates`, `fetchFilters`, `fetchMaterialDetail` |
| create | `MRPX-002/frontend/src/format.ts` | `formatQty`, `formatDate`, `formatMonth`, `daysOld`, `coveragePct` |
| create | `MRPX-002/frontend/src/__tests__/setup.ts` | `import "@testing-library/jest-dom/vitest"` |
| create | `MRPX-002/frontend/src/__tests__/format.test.ts` | tests for this feature |

No other files may be created or changed.

#### 4. Data

| Table (TSD §5.2 ID) | Columns read | Columns written | Write mode |
|---|---|---|---|
| — | none (HTTP only) | — | — |

**Joins (this feature):**

| Left | Right | Type | Condition | Filters | Expected result |
|---|---|---|---|---|---|
| — | — | — | none | — | — |

#### 5. Interfaces

**API (TSD §6.1):** consumes API-01, API-02, API-03 as listed in §2.

**Functions added by this feature:**

```ts
export class ApiError extends Error { constructor(public status: number, public detail: string) }

export interface CandidateQuery {
  shortPlant?: string[]; country?: string[]; criticality?: string[]; productFamily?: string[];
  sortBy?: "movable_qty" | "shortage_qty" | "stock_qty" | "weeks_late"; sortDir?: "asc" | "desc";
  limit?: number; offset?: number;
}
export async function fetchCandidates(q: CandidateQuery, signal?: AbortSignal): Promise<CandidatePage>
export async function fetchFilters(signal?: AbortSignal): Promise<FilterOptions>
export async function fetchMaterialDetail(material: string, shortPlant: string, signal?: AbortSignal): Promise<MaterialDetail>

export function formatQty(n: number): string          // en-GB grouping, up to 3 decimals, trailing zeros dropped
export function formatDate(iso: string): string       // "2026-08-30" -> "30 Aug 2026"
export function formatMonth(yyyymm: string): string   // "202608" -> "Aug 2026"
export function daysOld(iso: string, today: Date): number
export function coveragePct(movable: number, shortage: number): number  // 0..100, rounded, 0 when shortage is 0
```

| Input | Output |
|---|---|
| `formatQty(336233)` / `formatQty(2035876.5)` / `formatQty(60000)` | `"336,233"` / `"2,035,876.5"` / `"60,000"` |
| `formatDate("2026-08-30")` / `formatMonth("202608")` | `"30 Aug 2026"` / `"Aug 2026"` |
| `daysOld("2026-08-30", new Date("2026-11-11T08:00:00Z"))` | `73` |
| `coveragePct(336233, 336233)` / `coveragePct(60000, 2035876)` | `100` / `3` |
| `fetchCandidates({ shortPlant: ["3300"], criticality: ["A", "NONE"] })` | request URL `/api/transfer-candidates?short_plant=3300&criticality=A&criticality=NONE&sort_by=movable_qty&sort_dir=desc&limit=50&offset=0` |

#### 6. Implementation steps

1. Create `package.json` with the pinned versions of TSD §3 (runtime: react, react-dom, react-router-dom, lucide-react; dev: typescript, vite, @vitejs/plugin-react, tailwindcss, postcss, autoprefixer, vitest, @testing-library/react, @testing-library/jest-dom, jsdom, @types/react, @types/react-dom); scripts `"dev": "vite"`, `"build": "tsc --noEmit && vite build"`, `"test": "vitest run"`.
2. Create `vite.config.ts`, `tsconfig.json`, `postcss.config.js`, `index.html` as in §3.
3. Create `tailwind.config.js` with `colors.asm`: `ink "#1A1F36"`, `navy "#003B5C"`, `blue "#0E5CAD"`, `cyan "#00B4D8"`, `mist "#E6EEF5"`, `paper "#F7F9FC"`, `line "#D7DEE8"`, `muted "#6B7280"`, `ok "#10B981"`, `warn "#F59E0B"`, `err "#EF4444"`; `boxShadow.card = "0 1px 2px rgba(16,24,40,.06), 0 1px 3px rgba(16,24,40,.10)"`.
4. Create `index.css`: `@tailwind base; @tailwind components; @tailwind utilities;` then `:root { --asm-ink:#1A1F36; --asm-navy:#003B5C; --asm-blue:#0E5CAD; --asm-cyan:#00B4D8; --asm-mist:#E6EEF5; --asm-paper:#F7F9FC; --asm-line:#D7DEE8; --asm-muted:#6B7280; --asm-ok:#10B981; --asm-warn:#F59E0B; --asm-err:#EF4444; }`, `body { background: var(--asm-paper); color: var(--asm-ink); font-family: Inter, system-ui, sans-serif; }`, and in `@layer components`: `.btn-primary` (bg `asm-blue`, hover `asm-navy`, white text, 8 px radius, min height 44 px, `lg:min-h-[44px] min-h-[48px]`), `.btn-outline`, `.btn-ghost`, `.card` (white, 12 px radius, `shadow-card`, border `asm-line`), `.chip-ok` (emerald-700 on emerald-50), `.chip-warn` (amber-700 on amber-50), `.chip-err` (red-700 on red-50), `.chip-mute` (`asm-muted` on `asm-mist`), `.chip-crit-a` = `.chip-err` colours, `.chip-crit-b` = `.chip-warn` colours, `.chip-crit-c` = `.chip-ok` colours (all chips full radius, 12 px text desktop / 14 px tablet, always with the word "Criticality X" or the letter plus label), `.focus-ring` (`outline: 3px solid var(--asm-blue); outline-offset: 2px` on `:focus-visible`), `.tnum { font-variant-numeric: tabular-nums; }`.
5. Create `types.ts` mirroring v2/F-02 models with `camelCase` left as the API's `snake_case` keys (no renaming), dates as `string`.
6. Create `api.ts`: `buildQuery(q)` appends repeated keys for arrays (`short_plant`, `country`, `criticality`, `product_family`), always appends `sort_by` (default `movable_qty`), `sort_dir` (default `desc`), `limit` (default 50), `offset` (default 0); `request<T>(url, signal)` uses `fetch(url, { signal, headers: { Accept: "application/json" } })`; on `!res.ok` parse `{detail}` (fallback `"The transfer candidates could not be loaded. Try again."`) and `throw new ApiError(res.status, detail)`; `fetchMaterialDetail` encodes both path parts with `encodeURIComponent`.
7. Create `format.ts` with `Intl.NumberFormat("en-GB", { maximumFractionDigits: 3 })`, `Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric" })` (output `30 Aug 2026`), month formatter `{ month: "short", year: "numeric" }` on `new Date(Number(yyyymm.slice(0, 4)), Number(yyyymm.slice(4, 6)) - 1, 1)`; `daysOld` = floor of the UTC-midnight difference in days; `coveragePct` = `shortage <= 0 ? 0 : Math.round(Math.min(movable / shortage, 1) * 100)`.
8. Create `App.tsx`: header `bg-asm-navy text-white h-14 lg:h-14 max-lg:h-16` with the text "ASM" in a bordered box and the app name "Shortage rebalancing"; `<main className="mx-auto max-w-[1400px] px-6 py-6">` with `<Routes>`; two routes rendering `<Outlet />` placeholders `TransferCandidatesPage` and `MaterialDetailPage` imported from `./pages/...` — in this feature both files do not exist yet, so `App.tsx` renders `<div>Transfer candidates</div>` and `<div>Material detail</div>` inline; F-06 and F-07 replace them.
9. Write `format.test.ts` with the tests of §8.

Constants: `DEFAULT_LIMIT = 50`, `DEFAULT_SORT_BY = "movable_qty"`, `DEFAULT_SORT_DIR = "desc"`, `ERROR_UNAVAILABLE = "The transfer candidates could not be loaded. Try again."` in `src/api.ts`.

#### 7. Edge cases and errors

| Case | Input | Expected behaviour |
|---|---|---|
| Non-JSON error body | 503 with HTML | `ApiError(503, ERROR_UNAVAILABLE)` |
| Aborted request | `signal.abort()` | `fetch` rejects with `AbortError`; callers ignore it |
| `formatQty` of negative or 0 | `0` | `"0"` |
| `formatMonth` of bad input | `"2026"` | returns the input unchanged |
| `coveragePct` with movable > shortage | `(400000, 336233)` | `100` (capped) |

#### 8. Acceptance criteria and tests

Test file: `MRPX-002/frontend/src/__tests__/format.test.ts` · fixtures: literals

| AC ID | Given / When / Then | Test name | Fixture data | Expected |
|---|---|---|---|---|
| AC-F05-1 | Given the numbers 336233, 2035876.5, 0, when `formatQty` runs, then en-GB grouping with trailing zeros dropped | `f05 ac1 formatQty groups and trims` | as stated | `"336,233"`, `"2,035,876.5"`, `"0"` |
| AC-F05-2 | Given `"2026-08-30"` and `"202608"`, when `formatDate` / `formatMonth` run, then `"30 Aug 2026"` / `"Aug 2026"`; `daysOld("2026-08-30", new Date("2026-11-11T08:00:00Z"))` is 73 | `f05 ac2 dates` | as stated | as stated |
| AC-F05-3 | Given `fetch` mocked to resolve `{ ok: true, json: () => ({ items: [], total: 0, ... }) }`, when `fetchCandidates({ shortPlant: ["3300"], criticality: ["A", "NONE"] })` runs, then `fetch` was called with `/api/transfer-candidates?short_plant=3300&criticality=A&criticality=NONE&sort_by=movable_qty&sort_dir=desc&limit=50&offset=0` | `f05 ac3 query string` | mocked fetch | exact URL |
| AC-F05-4 | Given `fetch` mocked to resolve `{ ok: false, status: 503, json: () => { throw new Error() } }`, when `fetchFilters()` runs, then it rejects with `ApiError` status 503 and detail `ERROR_UNAVAILABLE` | `f05 ac4 api error` | mocked fetch | as stated |

Integration / evaluation checks (run by a human in dev): `cd MRPX-002/frontend && npm ci && npm run build` → `../backend/static/index.html` exists; `npm test` → 4 passed.

#### 9. Build-ready checklist (Planner self-check)

- [x] Every related feature (this set or earlier sets) is listed in §2 with the exact names this feature uses
- [x] Every path, table, column, API, agent and config key exists in the TSD, in §2, or earlier in this feature
- [x] Every join is written out in §4 (tables, type, condition, filters, expected result)
- [x] Every step is exact; SQL given for non-trivial logic; all constants have values
- [x] Every acceptance criterion has a test with literal fixture data and expected output
- [x] Edge cases cover empty, invalid, not-found and permission cases where relevant
- [x] No open words (e.g., such as, appropriate, as needed, TBD, etc., choose, decide)

**Out of scope for this feature:** any page content (F-06, F-07); state libraries; a dark theme; web fonts loaded from a CDN (Inter is used through the system font stack; `ui_ux_design` §3 names Inter and the environment has no CDN); i18n; analytics.

**How a human tests it:** (1) `npm ci && npm test` → 4 passed. (2) `npm run dev` with the backend on port 8000 → the navy header with "Shortage rebalancing" renders at `http://localhost:5173`.

---

### v2/F-06 — SCR-01 Transfer candidates page

| Field | Value |
|---|---|
| Module / layer | `frontend` — frontend (TSD §4, §11.1) |
| Type | app page |
| Size | M |
| Depends on / related to | v2/F-05 (depends on), v2/F-03 (calls) — details in §2 below |
| PRD refs | PRD-MRPX-002 US-1, US-2, US-3, US-4, US-6, US-7, §7 |
| TSD refs | §4 SCR-01, §2.4 RF-01, §6.1 API-01, API-03, §9 Freshness, §16 R-01 |
| Standards applied | BR-04, BR-07 (freshness), BR-09, skill:ui_ux_design §2, §4, §5 (List / queue), §6, §7, §8, §9; skill:data_engineering references/delivery-specs.md §3 (filters are view columns, freshness indicator, empty state) |

#### 1. Context

SCR-01 is the planner's daily screen: pick a plant (or a country as team lead), narrow by criticality and product family, and read the candidates sorted by movable quantity with the weeks late next to them. The screen states the MRP result date and the inventory month so the planner trusts the figures, and warns when the MRP result is older than yesterday. Screens: `SCR-01` (see `plan/wireframe.html`).

#### 2. Related features — context from earlier work

| Feature | Set | Relationship | What it built that this feature uses (exact names) | Status |
|---|---|---|---|---|
| v2/F-05 | v2 | depends on | `src/api.ts` (`fetchCandidates(q, signal)`, `fetchFilters(signal)`, `ApiError`, `CandidateQuery`), `src/format.ts` (`formatQty`, `formatDate`, `formatMonth`, `daysOld`, `coveragePct`), `src/types.ts` (`CandidatePage`, `CandidateRow`, `FilterOptions`, `PlantOption`), `src/index.css` classes (`btn-primary`, `btn-outline`, `btn-ghost`, `card`, `chip-warn`, `chip-mute`, `chip-crit-a`, `chip-crit-b`, `chip-crit-c`, `focus-ring`, `tnum`), `App.tsx` route `/` placeholder | To do |
| v2/F-03 | v2 | calls | API-01 and API-03 contracts (query names `short_plant`, `country`, `criticality`, `product_family`, `sort_by`, `sort_dir`, `limit`, `offset`) | To do |

**Rules carried over from those features:** criticality value `NONE` is shown as "Not set" (v2/F-02, v2/F-03); errors carry a user-facing `detail` (v2/F-03); no colour without a word (v2/F-05 chips).

#### 3. Files

| Action | Path | Purpose |
|---|---|---|
| create | `MRPX-002/frontend/src/pages/TransferCandidatesPage.tsx` | page: URL-synced filters, data loading, states, table, paging |
| create | `MRPX-002/frontend/src/components/FilterBar.tsx` | plant select, country select, criticality chips, family select, "Clear filters"; collapsible under 1024 px |
| create | `MRPX-002/frontend/src/components/CandidatesTable.tsx` | sortable table, desktop 11 columns / tablet 5 columns, row click to SCR-02 |
| create | `MRPX-002/frontend/src/components/FreshnessLine.tsx` | "MRP result 30 Aug 2026 · Inventory month Aug 2026" with the stale warning |
| create | `MRPX-002/frontend/src/components/StateMessage.tsx` | loading skeleton, empty, error blocks |
| modify | `MRPX-002/frontend/src/App.tsx` | route `/` renders `<TransferCandidatesPage />` only |
| create | `MRPX-002/frontend/src/__tests__/fixtures.ts` | `goldenRow`, `sampleRows`, `samplePage`, `sampleFilters` as JSON mirrors of TSD §12 |
| create | `MRPX-002/frontend/src/__tests__/TransferCandidatesPage.test.tsx` | tests for this feature |

No other files may be created or changed.

#### 4. Data

| Table (TSD §5.2 ID) | Columns read | Columns written | Write mode |
|---|---|---|---|
| — | none (HTTP via API-01, API-03) | — | — |

**Joins (this feature):**

| Left | Right | Type | Condition | Filters | Expected result |
|---|---|---|---|---|---|
| — | — | — | none | — | — |

#### 5. Interfaces

**API (TSD §6.1):** calls API-03 once on mount and API-01 on every change of filters, sort or page.

**Functions added by this feature:**

```ts
export interface ListParams { plant: string | ""; country: string | ""; crit: string[]; family: string | "";
                              sortBy: CandidateQuery["sortBy"]; sortDir: "asc" | "desc"; page: number }
export function readParams(search: URLSearchParams): ListParams   // keys: plant, country, crit (comma list), family, sort, dir, page
export function writeParams(p: ListParams): URLSearchParams
export default function TransferCandidatesPage(): JSX.Element
export function FilterBar(props: { options: FilterOptions | null; params: ListParams; onChange: (p: ListParams) => void }): JSX.Element
export function CandidatesTable(props: { rows: CandidateRow[]; sortBy: string; sortDir: string; onSort: (col: CandidateQuery["sortBy"]) => void; onOpen: (row: CandidateRow) => void }): JSX.Element
export function FreshnessLine(props: { mrpSnapshotDate: string | null; inventoryMonth: string | null; today: Date }): JSX.Element
export function StateMessage(props: { kind: "loading" | "empty" | "error"; message?: string; onAction?: () => void; actionLabel?: string }): JSX.Element
```

| Input | Output |
|---|---|
| URL `/?plant=3300&crit=A,NONE&sort=movable_qty&dir=desc&page=1` | `fetchCandidates({ shortPlant: ["3300"], country: [], criticality: ["A", "NONE"], productFamily: [], sortBy: "movable_qty", sortDir: "desc", limit: 50, offset: 0 })` |
| `samplePage` (3 items, total 3, date `2026-08-30`, month `202608`) | first row shows `1236-561-01`, `EMI GASKET / SPIRAL / SSN-053W`, chip `Criticality A`, `PE`, `HALB`, `3300 ASM Korea Ltd.`, `336,233`, `9 wk`, `1000 UNKNOWN PLANT`, `356,500`, `336,233 MM`; count line `3 transfer candidates`; freshness `MRP result 30 Aug 2026 · Inventory month Aug 2026` |

#### 6. Implementation steps

1. `FreshnessLine`: render `MRP result {formatDate(d)} · Inventory month {formatMonth(m)}`; when `d` is null render `No MRP result loaded yet`; when `daysOld(d, today) > 1` append a `chip-warn` with text `{n} days old` and an inline `AlertTriangle` icon (lucide, 16 px) and the sentence `The daily refresh has not run since {formatDate(d)}.`
2. `StateMessage`: `loading` renders 10 skeleton rows (`animate-pulse` bars in `asm-mist`); `empty` renders the heading `No transfer candidates match these filters.` and a `btn-outline` "Clear filters" (calls `onAction`); `error` renders `message` and a `btn-primary` "Try again" (calls `onAction`). Text left-aligned; no icons besides `AlertTriangle` on error.
3. `FilterBar`: label above each control (`ui_ux_design` §5 form rule): `Short plant` `<select>` with option `All plants` and one option per `options.short_plants` formatted `{code} · {name}` (`UNKNOWN PLANT` shown as given); `Country` `<select>` with `All countries` and `options.countries`; `Criticality` as four toggle buttons `A`, `B`, `C`, `Not set` (values `A`, `B`, `C`, `NONE`, `aria-pressed`), rendered only for values present in `options.criticalities`; `Product family` `<select>` with `All families` and `options.product_families`; `Clear filters` `btn-ghost` shown when any filter is set. Under 1024 px the bar collapses behind a `btn-outline` labelled `Filters ({count})` that toggles the panel; controls have min height 48 px.
4. `CandidatesTable`: `<table>` with sticky header; desktop columns in order: Material (mono code, description underneath in `asm-muted` 12 px, truncated with `title`), Criticality (chip `Criticality A` with `chip-crit-a` and so on; `Not set` with `chip-mute`), Family, Type, Short plant (`{code}` mono and `{name}` underneath), Shortage (right, `tnum`), Weeks late (right, `{n} wk`), Plant holding stock (`{code}` mono and `{name}` underneath), Stock (right), Movable (right, `font-semibold`, `{qty} {unit_of_measure}`, with a 4 px bar underneath whose width is `coveragePct(movable, shortage)%` in `asm-cyan` on `asm-mist` and the text `{pct}% of shortage`). Sortable headers: Shortage, Weeks late, Stock, Movable (button with `aria-sort`, arrow `ChevronUp`/`ChevronDown`). Row: `tabIndex=0`, `role="link"`, hover `bg-asm-mist`, Enter or click → `onOpen(row)`. Under 1024 px hide Type, Family, Short plant, Shortage, Stock columns (`hidden lg:table-cell`) and move Shortage into the Movable cell as `of {shortage}`.
5. `TransferCandidatesPage`: read `ListParams` from `useSearchParams`; on mount `fetchFilters` → `options` (error → error state); on every change of params call `fetchCandidates` with an `AbortController`, `limit 50`, `offset (page-1)*50`; render in order: `<h1>Transfer candidates</h1>`, `FreshnessLine` (dates from the page response, fallback from `options`), `FilterBar`, the count line `{formatQty(total)} transfer candidates{plant ? ` for ${plantName} (${plant})` : ""}`, then `StateMessage loading` / `empty` / `error`, or `CandidatesTable` followed by paging `Showing {from}–{to} of {total}` with `btn-outline` "Previous" / "Next" (disabled at the ends). `onOpen(row)` navigates to `/materials/${encodeURIComponent(row.material)}/plants/${row.short_plant}` with `state: { from: location.search }`. Changing a filter resets `page` to 1. `onSort` toggles direction when the same column is clicked, else sets `desc`.
6. Replace the `/` placeholder in `App.tsx` with `<TransferCandidatesPage />`.
7. Create `fixtures.ts` with `goldenRow`, `sampleRows` (the three TSD §12 rows as JSON with numbers and ISO dates), `samplePage = { items: sampleRows, total: 3, mrp_snapshot_date: "2026-08-30", inventory_month: "202608", limit: 50, offset: 0 }`, `sampleFilters = { short_plants: [{ code: "3300", name: "ASM Korea Ltd.", country: "KR" }], countries: ["KR"], criticalities: ["A", "C", "NONE"], product_families: ["CP", "PE"], mrp_snapshot_date: "2026-08-30", inventory_month: "202608" }`.
8. Write the tests of §8 with `vi.spyOn(api, "fetchCandidates")` and `vi.spyOn(api, "fetchFilters")`, rendering inside `MemoryRouter` with `initialEntries`.

Constants: `PAGE_SIZE = 50`, `STALE_AFTER_DAYS = 1`, `COPY_EMPTY = "No transfer candidates match these filters."`, `COPY_CLEAR = "Clear filters"`, `COPY_RETRY = "Try again"` at the top of `TransferCandidatesPage.tsx`.

#### 7. Edge cases and errors

| Case | Input | Expected behaviour |
|---|---|---|
| Filters match nothing | `total 0` | empty state with "Clear filters" |
| Warehouse down | `ApiError(503)` | error state with the API `detail` and "Try again" re-running the request |
| Invalid URL params | `?plant=33000` | API 422 → error state with the message; "Clear filters" resets the URL |
| Stale MRP result | `mrp_snapshot_date` 2026-08-30 on 2026-11-11 | warn chip `73 days old` |
| 0 results but options loaded | — | freshness line still shows the dates from `options` |
| Long description | 80 characters | truncated with `title` attribute on desktop; wraps on tablet |
| 10,000 rows | `total 10000` | paging 200 pages; table never renders more than 50 rows |
| Keyboard user | Tab to a row, Enter | opens SCR-02 |

#### 8. Acceptance criteria and tests

Test file: `MRPX-002/frontend/src/__tests__/TransferCandidatesPage.test.tsx` · fixtures: `samplePage`, `sampleFilters` from `fixtures.ts`

| AC ID | Given / When / Then | Test name | Fixture data | Expected |
|---|---|---|---|---|
| AC-F06-1 | Given `fetchFilters` → `sampleFilters` and `fetchCandidates` → `samplePage`, when the page renders at `/?plant=3300`, then `fetchCandidates` was called with `shortPlant ["3300"]`, `sortBy "movable_qty"`, `sortDir "desc"`, `limit 50`, `offset 0`, the first body row contains `1236-561-01`, `Criticality A`, `336,233`, `9 wk`, and the count line reads `3 transfer candidates for ASM Korea Ltd. (3300)` | `f06 ac1 renders golden row first` | as stated | as stated |
| AC-F06-2 | Given the same, when the page renders with `today = 2026-11-11`, then the text `MRP result 30 Aug 2026 · Inventory month Aug 2026` and a chip `73 days old` are present | `f06 ac2 freshness and stale warning` | as stated | as stated |
| AC-F06-3 | Given `fetchCandidates` → `{ ...samplePage, items: [], total: 0 }`, when the page renders, then `No transfer candidates match these filters.` and a `Clear filters` button are present, and clicking it sets the URL search to `?sort=movable_qty&dir=desc&page=1` | `f06 ac3 empty state clears filters` | as stated | as stated |
| AC-F06-4 | Given `fetchCandidates` rejecting with `new ApiError(503, "The transfer candidates could not be loaded. Try again.")`, when the page renders, then that message and a `Try again` button are present, and clicking it calls `fetchCandidates` a second time | `f06 ac4 error state retries` | as stated | 2 calls |

Integration / evaluation checks (run by a human in dev): with the backend on 8000 and `npm run dev`, open `http://localhost:5173/?plant=3300` → the golden row first with `336,233 MM`, page under 5 s; resize to 1024 px → filters collapse behind `Filters (1)`, table shows 5 columns.

#### 9. Build-ready checklist (Planner self-check)

- [x] Every related feature (this set or earlier sets) is listed in §2 with the exact names this feature uses
- [x] Every path, table, column, API, agent and config key exists in the TSD, in §2, or earlier in this feature
- [x] Every join is written out in §4 (tables, type, condition, filters, expected result)
- [x] Every step is exact; SQL given for non-trivial logic; all constants have values
- [x] Every acceptance criterion has a test with literal fixture data and expected output
- [x] Edge cases cover empty, invalid, not-found and permission cases where relevant
- [x] No open words (e.g., such as, appropriate, as needed, TBD, etc., choose, decide)

**Out of scope for this feature:** KPI tiles or any sum of `movable_qty` (R-01); CSV export; multi-select of plants in the UI (the API supports it; the screen offers one plant, as US-1 says "my plant"); saved filters per user; charts; a "Request transfer" button (PRD §8); SCR-02 (v2/F-07).

**How a human tests it:** (1) open `/?plant=3300` → golden row first, chips, freshness line. (2) toggle `Criticality A` → the list re-queries and the URL shows `crit=A`. (3) pick plant with no candidates or a family without rows → empty state; click `Clear filters`.

---

### v2/F-07 — SCR-02 Material shortage detail page

| Field | Value |
|---|---|
| Module / layer | `frontend` — frontend (TSD §4, §11.1) |
| Type | app page |
| Size | M |
| Depends on / related to | v2/F-06 (extends navigation), v2/F-05 (depends on), v2/F-04 (calls) — details in §2 below |
| PRD refs | PRD-MRPX-002 US-2, US-5, US-7 |
| TSD refs | §4 SCR-02, §2.4 RF-02, §6.1 API-02 |
| Standards applied | BR-03, skill:ui_ux_design §5 (Detail), §6, §7, §8, §9 |

#### 1. Context

When a planner has found a candidate, SCR-02 shows what the material is (description, type, family, criticality), how short the plant is and how late, and every plant that holds normal stock of it with the quantity that could move and the share of the shortage it covers. It is read-only: the transfer request happens in SAP, outside this product. Screens: `SCR-02` (see `plan/wireframe.html`).

#### 2. Related features — context from earlier work

| Feature | Set | Relationship | What it built that this feature uses (exact names) | Status |
|---|---|---|---|---|
| v2/F-06 | v2 | extends | navigation from `CandidatesTable` to `/materials/:material/plants/:shortPlant` with `location.state.from` (the SCR-01 search string); `FreshnessLine`, `StateMessage` components; `fixtures.ts` (`goldenRow`) | To do |
| v2/F-05 | v2 | depends on | `fetchMaterialDetail(material, shortPlant, signal)`, `ApiError`, `formatQty`, `formatDate`, `formatMonth`, `coveragePct`, `types.ts` (`MaterialDetail`, `HoldingPlant`), css classes | To do |
| v2/F-04 | v2 | calls | API-02 contract and the 404 message format | To do |

**Rules carried over from those features:** `Not set` for NULL criticality, chips carry words (v2/F-06); back navigation restores the SCR-01 filters from `state.from` (v2/F-06).

#### 3. Files

| Action | Path | Purpose |
|---|---|---|
| create | `MRPX-002/frontend/src/pages/MaterialDetailPage.tsx` | page: load detail, header, key fields, holding plants, states, back link |
| create | `MRPX-002/frontend/src/components/HoldingPlantsTable.tsx` | table of holding plants with coverage bar |
| modify | `MRPX-002/frontend/src/App.tsx` | route `/materials/:material/plants/:shortPlant` renders `<MaterialDetailPage />` only |
| create | `MRPX-002/frontend/src/__tests__/MaterialDetailPage.test.tsx` | tests for this feature |

No other files may be created or changed.

#### 4. Data

| Table (TSD §5.2 ID) | Columns read | Columns written | Write mode |
|---|---|---|---|
| — | none (HTTP via API-02) | — | — |

**Joins (this feature):**

| Left | Right | Type | Condition | Filters | Expected result |
|---|---|---|---|---|---|
| — | — | — | none | — | — |

#### 5. Interfaces

**API (TSD §6.1):** calls API-02 once on mount and on "Try again".

**Functions added by this feature:**

```ts
export default function MaterialDetailPage(): JSX.Element
export function HoldingPlantsTable(props: { plants: HoldingPlant[]; shortageQty: number; unit: string | null }): JSX.Element
```

| Input | Output |
|---|---|
| `fetchMaterialDetail` → detail built from `goldenRow` | heading `1236-561-01` (mono) with `EMI GASKET / SPIRAL / SSN-053W`; chips `Criticality A`, `Family PE`, `Type HALB`; key fields `Short plant 3300 · ASM Korea Ltd. · KR`, `Shortage 336,233 MM`, `Expected 9 weeks late`, `MRP result 30 Aug 2026`, `Inventory month Aug 2026`; table heading `Plants holding stock (1)`; row `1000`, `UNKNOWN PLANT`, `—`, `356,500`, `336,233`, `Covers 100%` |
| `fetchMaterialDetail` rejecting `ApiError(404, "Material 0000-000-00 is not short in plant 3300 in the current MRP result.")` | not-found state with that sentence and the link `Back to transfer candidates` |

#### 6. Implementation steps

1. `HoldingPlantsTable`: columns Plant (mono code), Name, Country (`—` when null), Stock (right, `tnum`), Movable (right, `font-semibold`, `{qty} {unit}`), Covers (`{coveragePct(movable, shortageQty)}%` with the 4 px `asm-cyan` bar as in SCR-01). Sorted as delivered by the API (`movable_qty desc`). On tablet hide Name and Country (`hidden lg:table-cell`) and show the name under the code.
2. `MaterialDetailPage`: read `material`, `shortPlant` from `useParams`; `from = location.state?.from ?? ""`; load with `fetchMaterialDetail` and an `AbortController`; render: back link `btn-ghost` with `ArrowLeft` icon and text `Back to transfer candidates` (`to={"/" + from}`); `StateMessage loading` while pending; on `ApiError` with status 404 render the heading `Not in the current MRP result` and the API `detail` sentence plus the back link; on other errors `StateMessage error` with "Try again"; on success render the header (`<h1>` mono code 24 px, description 16 px `asm-ink`, or `No description in the material master` in `asm-muted` when null), the three chips (`Criticality {A|B|C}` with `chip-crit-*`, `Not set` with `chip-mute`; `Family {x}` or `Family not set`; `Type {x}` or `Type not set`), a two-column `card` grid of key fields (desktop) / single column (tablet) with the five fields of §5, then `<h2>Plants holding stock ({n})</h2>` and `HoldingPlantsTable`. Under 1024 px the back link also renders as a full-width `btn-outline` in a sticky bottom bar.
3. Replace the detail placeholder route in `App.tsx`.
4. Write the tests of §8 with `vi.spyOn(api, "fetchMaterialDetail")`, `MemoryRouter initialEntries={["/materials/1236-561-01/plants/3300"]}` and `Routes` using the real path pattern.

Constants: `COPY_NOT_FOUND_TITLE = "Not in the current MRP result"`, `COPY_BACK = "Back to transfer candidates"`, `COPY_NO_DESCRIPTION = "No description in the material master"` at the top of `MaterialDetailPage.tsx`.

#### 7. Edge cases and errors

| Case | Input | Expected behaviour |
|---|---|---|
| Not found | 404 | not-found state, back link |
| Warehouse down | 503 | error state with "Try again" |
| No description / blank criticality | nulls | `No description in the material master`; chip `Not set` |
| Unknown plant | `stock_plant_name UNKNOWN PLANT`, country null | shown as given, country `—` |
| Many holding plants | 34 rows | table scrolls within the page; no paging |
| Direct deep link (no `state.from`) | open URL in a new tab | back link goes to `/` |
| Coverage above 100 | movable > shortage never happens (view rule) | capped at 100 by `coveragePct` |

#### 8. Acceptance criteria and tests

Test file: `MRPX-002/frontend/src/__tests__/MaterialDetailPage.test.tsx` · fixtures: `goldenRow` from `fixtures.ts` mapped to a `MaterialDetail`

| AC ID | Given / When / Then | Test name | Fixture data | Expected |
|---|---|---|---|---|
| AC-F07-1 | Given `fetchMaterialDetail` → the golden detail (`holding_plants` = one plant `1000`), when the page renders at `/materials/1236-561-01/plants/3300`, then the texts `1236-561-01`, `EMI GASKET / SPIRAL / SSN-053W`, `Criticality A`, `Family PE`, `Type HALB`, `Shortage`, `336,233 MM`, `9 weeks late`, `MRP result 30 Aug 2026`, `Inventory month Aug 2026`, `Plants holding stock (1)`, `UNKNOWN PLANT`, `356,500`, `Covers 100%` are present and `fetchMaterialDetail` was called with `("1236-561-01", "3300")` | `f07 ac1 renders golden detail` | as stated | as stated |
| AC-F07-2 | Given `fetchMaterialDetail` rejecting `ApiError(404, "Material 0000-000-00 is not short in plant 3300 in the current MRP result.")`, when the page renders, then `Not in the current MRP result`, that sentence and a link `Back to transfer candidates` with `href="/"` are present | `f07 ac2 not found` | as stated | as stated |
| AC-F07-3 | Given the page opened with router state `{ from: "?plant=3300&crit=A" }`, when it renders successfully, then the back link `href` is `/?plant=3300&crit=A` | `f07 ac3 back link keeps filters` | golden detail | as stated |

Integration / evaluation checks (run by a human in dev): from SCR-01 (`/?plant=3300`) click the first row → SCR-02 shows plant `1000` covering 100 %; click `Back to transfer candidates` → SCR-01 still filtered to 3300.

#### 9. Build-ready checklist (Planner self-check)

- [x] Every related feature (this set or earlier sets) is listed in §2 with the exact names this feature uses
- [x] Every path, table, column, API, agent and config key exists in the TSD, in §2, or earlier in this feature
- [x] Every join is written out in §4 (tables, type, condition, filters, expected result)
- [x] Every step is exact; SQL given for non-trivial logic; all constants have values
- [x] Every acceptance criterion has a test with literal fixture data and expected output
- [x] Edge cases cover empty, invalid, not-found and permission cases where relevant
- [x] No open words (e.g., such as, appropriate, as needed, TBD, etc., choose, decide)

**Out of scope for this feature:** a "Request transfer" or "Create STO" action (PRD §8); material history; stock by storage location; links to SAP or to other materials; editing anything.

**How a human tests it:** (1) open `/materials/1236-561-01/plants/3300` → header, chips, five key fields, one holding plant with `Covers 100%`. (2) open `/materials/0000-000-00/plants/3300` → not-found state with the back link.

---

### v2/F-08 — Asset Bundle, dev deployment and warehouse integration test

| Field | Value |
|---|---|
| Module / layer | `bundle` — databricks.yml and its deployment test (TSD §4, §10) |
| Type | job (deployment) |
| Size | S |
| Depends on / related to | v2/F-07 (depends on: full app), v2/F-01 (`app.yaml`, `get_app`), v1/F-01 (T-01 grants) — details in §2 below |
| PRD refs | PRD-MRPX-002 §4b (workspace login, SQL warehouse), §7 (under 5 s) |
| TSD refs | §8, §9, §10, §13, §16 D-08, Q-03 |
| Standards applied | skill:data_engineering §8 (parameterised environments, no secrets), §9 (bundles, serverless, project_id tag); skill:data_engineering references/delivery-specs.md §3 (first load under 5 s) |

#### 1. Context

The PoC ends with planners opening the app in the dev workspace. This feature makes the deployment repeatable with an Asset Bundle, grants the app's service principal read access to T-01, and adds the one integration test that runs the real app in-process against the real warehouse to prove the golden example and the latency target.

#### 2. Related features — context from earlier work

| Feature | Set | Relationship | What it built that this feature uses (exact names) | Status |
|---|---|---|---|---|
| v2/F-01 | v2 | depends on | `MRPX-002/app.yaml` (command `uvicorn backend.main:get_app --factory`, env `DATABRICKS_WAREHOUSE_ID valueFrom sql-warehouse`, `CATALOG`, `SCHEMA_GOLD`, `VIEW_TRANSFER_CANDIDATES`); `backend.config.load_settings`, `make_connection_factory`; `backend.main.create_app` | To do |
| v2/F-05 … F-07 | v2 | depends on | `npm run build` writes `MRPX-002/backend/static/` | To do |
| v1/F-01 | v1 | depends on | `sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair` (grant target) | Done after v1 |
| v1/F-02 | v1 | depends on | `pytest.ini` marker `integration`; environment variables `DATABRICKS_HOST`, `DATABRICKS_WAREHOUSE_ID`, `DATABRICKS_TOKEN` | Done after v1 |

**Rules carried over from those features:** no secrets in files (v2/F-01); `account users` already have `SELECT` on T-01 (v1/F-01, D-08) — the service principal grant is still explicit because service principals are not members of `account users` in every workspace.

#### 3. Files

| Action | Path | Purpose |
|---|---|---|
| create | `MRPX-002/databricks.yml` | bundle with app resource and target `dev` |
| create | `MRPX-002/pipelines/sql/grant_app_service_principal.sql` | the three `GRANT` statements with the placeholder `${app_sp}` |
| create | `MRPX-002/tests/integration/test_f08_app_against_warehouse.py` | tests for this feature |

No other files may be created or changed.

#### 4. Data

| Table (TSD §5.2 ID) | Columns read | Columns written | Write mode |
|---|---|---|---|
| T-01 (through the app) | as v2/F-02 | — | — |

**Joins (this feature):**

| Left | Right | Type | Condition | Filters | Expected result |
|---|---|---|---|---|---|
| — | — | — | none | — | — |

#### 5. Interfaces

**API (TSD §6.1):** exercises API-04, API-03, API-01, API-02 on the real warehouse.

**Functions added by this feature:** none (configuration and tests).

| Input | Output |
|---|---|
| `databricks bundle deploy -t dev --var="warehouse_id=<id>"` then `databricks bundle run mrpx_002_transfer_candidates -t dev` | app `mrpx-002-transfer-candidates` running; URL printed |
| `GET /api/transfer-candidates?short_plant=3300&limit=50` on the in-process app with real settings | `total 6256`, `items[0].material "1236-561-01"`, each of five calls under 2 s |

#### 6. Implementation steps

1. Create `MRPX-002/databricks.yml`:

```yaml
bundle:
  name: mrpx-002-shortage-rebalancing

variables:
  warehouse_id:
    description: Serverless SQL warehouse the app queries (passed with --var)

resources:
  apps:
    mrpx_002_transfer_candidates:
      name: mrpx-002-transfer-candidates
      description: "MRPX-002 Shortage Rebalancing - transfer candidates for supply planners (PoC)"
      source_code_path: ./
      resources:
        - name: sql-warehouse
          sql_warehouse:
            id: ${var.warehouse_id}
            permission: CAN_USE

targets:
  dev:
    mode: development
    default: true
    workspace:
      host: https://dbc-715176d6-3961.cloud.databricks.com
```

2. Create `grant_app_service_principal.sql`:

```sql
-- MRPX-002 v2/F-08: run after the first deploy; replace ${app_sp} with the application id shown by
-- `databricks apps get mrpx-002-transfer-candidates` (field service_principal_client_id).
GRANT USE CATALOG ON CATALOG sandbox_others TO `${app_sp}`;
GRANT USE SCHEMA ON SCHEMA sandbox_others.gold TO `${app_sp}`;
GRANT SELECT ON TABLE sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair TO `${app_sp}`;
```

3. Build and deploy (documented in the pull-request description): `cd MRPX-002/frontend && npm ci && npm run build`; `cd .. && databricks bundle validate -t dev`; `databricks bundle deploy -t dev --var="warehouse_id=<id>"`; `databricks bundle run mrpx_002_transfer_candidates -t dev`; `databricks apps get mrpx-002-transfer-candidates` → copy `service_principal_client_id`; run the grant file in the SQL editor with the id substituted; in the app's Permissions page grant `CAN USE` to the planners of the two validation plants named by the product owner (Q-03).
4. Write `test_f08_app_against_warehouse.py` (`pytestmark = pytest.mark.integration`): skip unless `DATABRICKS_HOST`, `DATABRICKS_WAREHOUSE_ID`, `DATABRICKS_TOKEN` are set; build `settings = load_settings({"CATALOG": "sandbox_others", "SCHEMA_GOLD": "gold", "VIEW_TRANSFER_CANDIDATES": "agg_mrpx_transfer_candidate_plant_pair", "DATABRICKS_HOST": host, "DATABRICKS_WAREHOUSE_ID": wid})`; `client = TestClient(create_app(settings, make_connection_factory(settings)))` (the SDK `Config` picks up `DATABRICKS_TOKEN` from the environment); implement the four tests of §8; timing with `time.perf_counter()` after one warm-up call.

Constants: `GOLDEN_PLANT = "3300"`, `GOLDEN_MATERIAL = "1236-561-01"`, `GOLDEN_TOTAL = 6256`, `GOLDEN_SNAPSHOT = "2026-08-30"`, `MAX_SECONDS = 2.0`, `TIMED_CALLS = 5` at the top of the test file.

#### 7. Edge cases and errors

| Case | Input | Expected behaviour |
|---|---|---|
| Snapshot moved on | `MAX(mrp_snapshot_date) <> 2026-08-30` | AC-F08-2 skipped with reason "snapshot moved on"; latency test still runs |
| Grant not yet run | app SP without `SELECT` | app returns 503 on API-01; `/api/health` still 200; fix by running the grant file |
| Warehouse stopped | serverless warehouse starting | first call slower; the warm-up call absorbs it; timed calls follow |
| Bundle variable missing | no `--var` | `databricks bundle validate` fails naming `warehouse_id` |
| User without `CAN USE` | opens the app URL | Databricks Apps shows its own access-denied page (permission state, `ui_ux_design` §6) |

#### 8. Acceptance criteria and tests

Test file: `MRPX-002/tests/integration/test_f08_app_against_warehouse.py` · fixtures: environment variables (see step 4)

| AC ID | Given / When / Then | Test name | Fixture data | Expected |
|---|---|---|---|---|
| AC-F08-1 | Given real settings, when `GET /api/health` and `GET /api/filters` are called, then 200 each and `filters.short_plants` contains code `3300` | `test_f08_ac1_health_and_filters` | real view | as stated |
| AC-F08-2 | Given snapshot 2026-08-30, when `GET /api/transfer-candidates?short_plant=3300&limit=50` is called, then `total == 6256`, `items[0].material == "1236-561-01"`, `items[0].stock_plant == "1000"`, `items[0].movable_qty == 336233.0`, `mrp_snapshot_date == "2026-08-30"`, `inventory_month == "202608"` | `test_f08_ac2_golden_plant_page` | real view | as stated (skipped when the snapshot moved on) |
| AC-F08-3 | Given the same call after one warm-up, when it runs 5 times, then every call finishes under 2.0 s (proves PRD §7) | `test_f08_ac3_latency_under_two_seconds` | real view | 5 durations < 2.0 |
| AC-F08-4 | Given snapshot 2026-08-30, when `GET /api/transfer-candidates/1236-561-01/3300` is called, then 200 with one holding plant `1000` and `shortage_qty 336233.0` | `test_f08_ac4_golden_detail` | real view | as stated (skipped when the snapshot moved on) |

Integration / evaluation checks (run by a human in dev): open the app URL printed by `databricks bundle run` in a browser with the workspace login → SCR-01 loads under 5 s; filter to 3300 → golden row first; open it → SCR-02 as in `plan/wireframe.html`.

#### 9. Build-ready checklist (Planner self-check)

- [x] Every related feature (this set or earlier sets) is listed in §2 with the exact names this feature uses
- [x] Every path, table, column, API, agent and config key exists in the TSD, in §2, or earlier in this feature
- [x] Every join is written out in §4 (tables, type, condition, filters, expected result)
- [x] Every step is exact; SQL given for non-trivial logic; all constants have values
- [x] Every acceptance criterion has a test with literal fixture data and expected output
- [x] Edge cases cover empty, invalid, not-found and permission cases where relevant
- [x] No open words (e.g., such as, appropriate, as needed, TBD, etc., choose, decide)

**Out of scope for this feature:** a `prod` target; CI pipeline files; monitoring, alerts or dashboards for the app; custom domains; moving T-01 ownership to a service principal (D-07, MVP).

**How a human tests it:** (1) run the deploy commands of step 3 → the app URL opens with workspace SSO. (2) `DATABRICKS_HOST=<host> DATABRICKS_WAREHOUSE_ID=<id> DATABRICKS_TOKEN=<pat> pytest -m integration tests/integration/test_f08_app_against_warehouse.py -q` → 4 passed (or 2 skipped when the snapshot moved on).

---

## 5. Change log

| Date | Change | Features | Source (PRD / CR) | Approved by |
|---|---|---|---|---|
| 2026-11-11 | Initial set | all | PRD-MRPX-002 v0.1 | |
