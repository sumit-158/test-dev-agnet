# Feature Set v2 — PIR / Source List Request Chat (SCO-001) — PoC app: stewards do the job end to end

| Field | Value |
|---|---|
| Feature set | v2 — PoC app: stewards do the job end to end |
| TSD version | TSD-SCO-001 v1.0 |
| Source PRD(s) | PRD-SCO-001 v0.1 §4 (US-1 … US-10), §6, §7 |
| Status | Approved |
| Approved by / date | Sumit/26-11-2026 |
| Depends on sets | v1 merged |
| Context library version | 2026.11.24-1 |

## 1. What this feature set delivers

**Goal:** The Databricks App `sco-001-pir-sl-chat` runs in dev with the split screen SCR-01, the attachment viewer SCR-02
and the export dialog SCR-03: a steward uploads a quotation, types the request, sees the request type within 5 s and
the line items within 60 s, clicks any value to see its yellow source box, sees conflicts, corrects by edit or by chat,
and downloads JSON or CSV.

**Builds on (already exists before this set):** v1 — `Settings`, constants and domain models (v1/F-01), T-01 (v1/F-02),
`GatewayRepository` and prompts `request_triage_chat`, `line_item_extraction_chat` (v1/F-03), `AttachmentService`,
`VolumeRepository`, `ParseRepository`, `source_locator` (v1/F-04), `RequestTriageAgent` (v1/F-05),
`LineItemExtractionAgent` (v1/F-06), `build_result`, `merge_result`, `apply_patches`, `add_line`, `remove_line`,
`set_request_type` (v1/F-07), evaluation run (v1/F-08).

**Adds:** API-01 … API-08, `session_service`, `extraction_service` orchestration, AG-04 and prompt `correction_chat`,
`export_service`, the frontend (SCR-01, SCR-02, SCR-03), deployment of the app to dev.

| In scope | Out of scope (later set or never) |
|---|---|
| Session API, upload API, message API with two-phase answer | Persisting sessions (never, PRD §8) |
| Correction by chat (AG-04) and direct edit | Audit trail, approval flow (never, PRD §8) |
| Export JSON / CSV | Sending to SAP (never) |
| SCR-01, SCR-02, SCR-03 with loading, empty, error, success states | Tablet or mobile layouts (PRD names none) |
| Deploy to dev with the bundle | Budgets, cost report, permission tests, runbook (v3) |

## 2. Set exit criteria

| ID | The set is done when… | Checked by |
|---|---|---|
| EX-v2-1 | In the deployed dev app, the golden example (message M1 text from `tests/fixtures/golden_message_M1.txt`, PDF from SRC-01 `GE-001`) shows request type `Update PIR` within 5 s and 2 PIR lines within 60 s; Plant shows `Missing`; C/R. of Origin shows `Conflict` with `KR` and `DE` | manual test (one step: send the request) plus `tests/integration/test_v2_golden_flow.py` |
| EX-v2-2 | Clicking Amount on line 1 highlights `7,000` in M1 and opens the PDF page with a yellow box containing the price; at 50 %, 100 % and 200 % zoom the box stays on the text | manual test |
| EX-v2-3 | Typing `line 2 amount is 8000` changes exactly line 2 Amount to `8000`, marks it `Corrected`, the assistant lists the change; a later message `also add part 2000-04275 same supplier` adds a line without touching the corrected cell | integration test `test_v2_f04_ac1_chat_correction` and manual test |
| EX-v2-4 | `GET /api/sessions/{id}/export?format=csv` returns the header `line_no,doc_type,action,supplier,material,vendor_material_no,plant,purchasing_org,country_of_origin,lead_time_days,standard_qty,amount,currency,pricing_unit,unit_of_measure,valid_from,valid_to,fixed_vendor` | test |
| EX-v2-5 | `pytest tests/unit` and `pytest -m integration tests/integration` pass in dev; `ruff check .` clean; `evals/run_eval.py --set-version 1 --endpoint-mode primary` still passes (no regression) | test / evaluation |

## 3. Build order

| # | Feature | Title | Module | Depends on / related to | Size | Status | PR |
|---|---|---|---|---|---|---|---|
| 1 | v2/F-01 | Build the session store and routes API-01, API-05, API-08 | `routers/sessions`, `services/session_service` | v1/F-01 | M | To do | |
| 2 | v2/F-02 | Build attachment upload and page image routes API-02, API-03 | `routers/attachments` | v2/F-01, v1/F-04 | S | To do | |
| 3 | v2/F-03 | Build the message route API-04 with triage, background extraction and merge | `routers/messages`, `services/extraction_service` | v2/F-01, v2/F-02, v1/F-05, v1/F-06, v1/F-07 | M | To do | |
| 4 | v2/F-04 | Build AG-04 correction and wire chat corrections | `agents/correction` | v2/F-03, v1/F-03, v1/F-07 | M | To do | |
| 5 | v2/F-05 | Build direct edit API-06 and export API-07 | `routers/results`, `services/export_service` | v2/F-03, v1/F-07 | S | To do | |
| 6 | v2/F-06 | Build the frontend shell and SCR-01 chat pane | `frontend` | v2/F-02, v2/F-03 | M | To do | |
| 7 | v2/F-07 | Build the line-item review table, direct edit and SCR-03 export | `frontend` | v2/F-06, v2/F-05 | M | To do | |
| 8 | v2/F-08 | Build evidence navigation and SCR-02 attachment viewer | `frontend` | v2/F-07 | M | To do | |

Feature references are written `v{set}/F-{nn}` so a link to a feature in another feature set is unambiguous.
Status: To do → In progress → In review → Human testing → Done (Blocked, Dropped). Only a human sets Done.

---

## 4. Features

### v2/F-01 — Build the session store and routes API-01, API-05, API-08

| Field | Value |
|---|---|
| Module / layer | `routers/sessions`, `services/session_service` — `backend/routers/sessions.py`, `backend/services/session_service.py` (TSD §4, §11.1) |
| Type | API |
| Size | M |
| Depends on / related to | v1/F-01 (depends on), v1/F-03 (uses), v1/F-04 (uses) |
| PRD refs | PRD-SCO-001 US-1, §8 (chat only for the browser session) |
| TSD refs | §5.2 `Session`; §6.1 API-01, API-05, API-08; §2.5 (no persistence); §10; §16 D-06, R-08 |
| Standards applied | BR-09, skill:ai_agents §4 (prompt loaded at start), skill:ui_ux_design §6 (states served by API-05) |

#### 1. Context

Sessions are the unit of everything the app shows. This feature creates the in-memory store with TTL, the three
session routes, registers the routers in `main.py`, loads both prompts at start (fail fast) and deploys the backend
to dev so that later features add routes to a running app.

#### 2. Related features — context from earlier work

| Feature | Set | Relationship | What it built that this feature uses (exact names) | Status |
|---|---|---|---|---|
| v1/F-01 | v1 | depends on | `models.Session, Message, Attachment, Page, Result`; `constants.SESSION_TTL_HOURS = 8`; `create_app(settings, volume_repository, parse_repository, gateway)`; `Settings` | Done (v1 merged) |
| v1/F-03 | v1 | uses | `GatewayRepository(settings)`; prompt names `request_triage_chat`, `line_item_extraction_chat`; `ValueError("Prompt <name>@<alias> not found")` | Done |
| v1/F-04 | v1 | uses | `VolumeRepository.delete_prefix(prefix)`; `ParseRepository(settings)` | Done |

**Rules carried over from those features:** settings only from `load_settings()`; never log message text (v1/F-01, TSD §11.2).

#### 3. Files

| Action | Path | Purpose |
|---|---|---|
| create | `SCO-001/backend/services/session_service.py` | `SessionService` |
| create | `SCO-001/backend/routers/sessions.py` | API-01, API-05, API-08 |
| modify | `SCO-001/backend/main.py` | register `sessions` router; build `SessionService`, `VolumeRepository`, `ParseRepository`, `GatewayRepository`, `AttachmentService` defaults; load the two prompts at start; add `app.state` holders only |
| modify | `SCO-001/backend/models.py` | add API models `SessionCreated`, `SessionView` (Session without `Page.words`, with `image_url` per page) only |
| create | `SCO-001/tests/unit/routers/test_f01_sessions.py` | tests for this feature |
| create | `SCO-001/tests/integration/__init__.py`, `SCO-001/tests/integration/conftest.py` | integration fixtures: `dev_client` = `TestClient` of the real app with `load_settings()` (marker `integration`) |

No other files may be created or changed.

#### 4. Data

| Table (TSD §5.2 ID) | Columns read | Columns written | Write mode |
|---|---|---|---|
| SRC-02 `uploads/{session_id}/` | — | — (deleted on API-08 and TTL) | delete prefix |

**Joins (this feature):** none.

#### 5. Interfaces

**API (TSD §6.1):**
- `POST /api/sessions` — no body → `201 {session_id: str, created_at: str}`.
- `GET /api/sessions/{session_id}` — → `200 SessionView` ; `404 {"detail": "Session not found"}`.
- `DELETE /api/sessions/{session_id}` — → `204`; `404`.

**Functions added by this feature:**

```python
class SessionService:
    def __init__(self, volume: VolumeRepository, ttl_hours: int = SESSION_TTL_HOURS, clock: Callable[[], datetime] = utcnow) -> None: ...
    def create(self) -> Session: ...
    def get(self, session_id: str) -> Session:
        """Raises KeyError when unknown or expired (expired sessions are deleted on access)."""
    def delete(self, session_id: str) -> None:
        """Remove from memory and volume.delete_prefix(f"{VOLUME_UPLOADS}/{session_id}/"). Raises KeyError."""
    def next_message_id(self, session: Session) -> str:  # "M1", "M2", ...
    def next_attachment_id(self, session: Session) -> str:  # "A1", "A2", ...
    def touch(self, session: Session) -> None:  # last_seen_at = now
    def sweep(self) -> int:
        """Delete sessions with last_seen_at older than ttl; returns count. Called by a background task every 10 minutes."""
    async def with_lock(self, session_id: str): ...  # asyncio.Lock per session (context manager)
def to_view(session: Session, base_url: str) -> SessionView:
    """Drop Page.words; set image_url = f"/api/sessions/{sid}/attachments/{aid}/pages/{page_no}.png"."""
```

| Input | Output |
|---|---|
| `create()` | `Session(session_id=<uuid4>, extraction_status="idle", messages=[], attachments=[], result=None)` |
| `get("unknown")` | `KeyError` → route 404 |
| `next_message_id(session with 2 messages)` | `"M3"` |

#### 6. Implementation steps

1. `SessionService` per §5; store `dict[str, Session]`; `_locks: dict[str, asyncio.Lock]`.
2. `routers/sessions.py`: `router = APIRouter(prefix="/api/sessions")`; routes per §5; `KeyError` → `HTTPException(404, "Session not found")`.
3. `main.py`: in `create_app` build defaults when not injected: `VolumeRepository(settings)`, `ParseRepository(settings)`, `GatewayRepository(settings)`, `AttachmentService(volume, parse)`, `SessionService(volume)`; store on `app.state`; include `sessions` router; on startup event: `gateway.load_prompt("request_triage_chat")`, `gateway.load_prompt("line_item_extraction_chat")` (fail fast on `ValueError`), start `asyncio.create_task(sweep_loop())` with a 600 s interval; mount `backend/static` at `/` when the folder exists (after `/api` routes).
4. `to_view` per §5.
5. Integration conftest: `dev_client` fixture skipped when `DATABRICKS_HOST` is unset.
6. Deploy: `databricks bundle deploy -t dev && databricks bundle run -t dev sco_001_pir_sl_chat` (README "Deploy to dev"); the app resources per TSD §10.

Constants: `SWEEP_INTERVAL_SECONDS = 600` (defined in `backend/services/session_service.py`).

#### 7. Edge cases and errors

| Case | Input | Expected behaviour |
|---|---|---|
| Unknown session | `GET /api/sessions/nope` | `404 {"detail": "Session not found"}` |
| Expired session | `last_seen_at` 9 h ago | `get` deletes it and raises `KeyError` → 404; volume prefix deleted |
| Delete twice | second `DELETE` | `404` |
| Prompt missing at start | registry without alias | app start raises `ValueError("Prompt request_triage_chat@production not found")`, process exits |
| Volume delete fails | `UpstreamUnavailable` | session removed from memory, warning logged, `204` returned |
| Concurrent requests | two requests on one session | serialised by `with_lock` |

#### 8. Acceptance criteria and tests

Test file: `SCO-001/tests/unit/routers/test_f01_sessions.py` · fixtures: `client`, `fake_volume_repository`, `fake_gateway`

| AC ID | Given / When / Then | Test name | Fixture data | Expected |
|---|---|---|---|---|
| AC-F01-1 | Given the app, when `POST /api/sessions` then `GET`, then a new idle session is returned | `test_f01_ac1_create_and_get` | — | `201` with `session_id` (36 chars); `GET` → `200`, `extraction_status == "idle"`, `messages == []`, `attachments == []`, `result is None` |
| AC-F01-2 | Given a session, when `DELETE`, then 204 and the volume prefix is deleted; a second `GET` is 404 | `test_f01_ac2_delete` | `fake_volume_repository` holding `uploads/<sid>/A1/original.pdf` | `204`; file gone; `GET` → `404 {"detail": "Session not found"}` |
| AC-F01-3 | Given a session untouched for 9 h, when `sweep` runs, then it is removed | `test_f01_ac3_ttl_sweep` | `clock` returning `created + 9h` | `sweep() == 1`; `get` raises `KeyError` |
| AC-F01-4 | Given a gateway whose prompt loading raises, when the app starts, then start-up fails | `test_f01_ac4_fail_fast_prompts` | `fake_gateway.raise_for = {"request_triage_chat": ValueError("Prompt request_triage_chat@production not found")}` | `TestClient(app).__enter__()` raises `ValueError` with that message |

Integration / evaluation checks (run by a human in dev): after `bundle deploy` and `bundle run`, open `<app-url>/api/health` → `{"status":"ok"}`; `curl -X POST <app-url>/api/sessions` with the workspace token → `201`.

#### 9. Build-ready checklist (Planner self-check)

- [x] Every related feature (this set or earlier sets) is listed in §2 with the exact names this feature uses
- [x] Every path, table, column, API, agent and config key exists in the TSD, in §2, or earlier in this feature
- [x] Every join is written out in §4 (tables, type, condition, filters, expected result)
- [x] Every step is exact; SQL given for non-trivial logic; all constants have values
- [x] Every acceptance criterion has a test with literal fixture data and expected output
- [x] Edge cases cover empty, invalid, not-found and permission cases where relevant
- [x] No open words (e.g., such as, appropriate, as needed, TBD, etc., choose, decide)

**Out of scope for this feature:** uploads, messages, results, export routes; per-user ownership checks (every
authenticated steward may open any session id — PRD §8 excludes user management; ids are unguessable uuid4); a
database.

**How a human tests it:** 1) Deploy to dev. 2) `POST /api/sessions`, `GET` it, `DELETE` it, `GET` again → 404. 3) Check the app log shows `Prompts loaded: request_triage_chat v1, line_item_extraction_chat v1`.

---

### v2/F-02 — Build attachment upload and page image routes API-02, API-03

| Field | Value |
|---|---|
| Module / layer | `routers/attachments` — `backend/routers/attachments.py` (TSD §4) |
| Type | API |
| Size | S |
| Depends on / related to | v2/F-01 (depends on), v1/F-04 (depends on) |
| PRD refs | PRD-SCO-001 US-1, US-6, §5 (PDF, PNG, JPG), §7 (20 pages) |
| TSD refs | §6.1 API-02, API-03; §2.3 steps 1-4; §2.4 RF-01 steps 1-5 |
| Standards applied | BR-09, skill:data_engineering §3 (volumes), skill:ui_ux_design §6 (error copy) |

#### 1. Context

The upload route hands the file to `AttachmentService.ingest` (v1/F-04) under the session lock and returns the pages
so the chat pane can show previews; the image route streams a rendered page from SRC-02 for the viewer.

#### 2. Related features — context from earlier work

| Feature | Set | Relationship | What it built that this feature uses (exact names) | Status |
|---|---|---|---|---|
| v2/F-01 | v2 | depends on | `SessionService.get`, `next_attachment_id`, `touch`, `with_lock`; `to_view`; router registration pattern in `main.py` | To do |
| v1/F-04 | v1 | depends on | `AttachmentService.ingest(session_id, attachment_id, file_name, media_type, data) -> Attachment` raising `ValueError`, `PayloadTooLarge`, `UpstreamUnavailable`; `VolumeRepository.get(path)`; page image path `f"{VOLUME_UPLOADS}/{session_id}/{attachment_id}/pages/p{page_no:03d}.png"` | Done |
| v1/F-01 | v1 | uses | `constants.MAX_ATTACHMENTS_PER_SESSION = 10`, `ALLOWED_MEDIA_TYPES`; `errors.PayloadTooLarge`, `UpstreamUnavailable` | Done |

**Rules carried over from those features:** error texts come from `AttachmentService` unchanged (v1/F-04).

#### 3. Files

| Action | Path | Purpose |
|---|---|---|
| create | `SCO-001/backend/routers/attachments.py` | API-02, API-03 |
| modify | `SCO-001/backend/main.py` | include `attachments` router only |
| modify | `SCO-001/backend/models.py` | add `AttachmentView` (Attachment without `Page.words`/`elements`, pages with `image_url`) only |
| create | `SCO-001/tests/unit/routers/test_f02_attachments.py` | tests for this feature |

No other files may be created or changed.

#### 4. Data

| Table (TSD §5.2 ID) | Columns read | Columns written | Write mode |
|---|---|---|---|
| SRC-02 `uploads/{session_id}/{attachment_id}/pages/p{nnn}.png` | file bytes (API-03) | via `ingest` (API-02) | put |

**Joins (this feature):** none.

#### 5. Interfaces

**API (TSD §6.1):**
- `POST /api/sessions/{session_id}/attachments` — multipart field `file` (filename, content type) → `201 AttachmentView`; `404 Session not found`; `413 {"detail": "The file is larger than 20 MB"}`; `422 {"detail": "Only PDF, PNG and JPG files are supported"}` / `"An attachment may have at most 20 pages"` / `"The file is empty"` / `"The PDF is password protected"` / `"A request may have at most 10 attachments"`; `503 {"detail": "Storage is unavailable; try again"}`.
- `GET /api/sessions/{session_id}/attachments/{attachment_id}/pages/{page_no}.png` → `200 image/png` (header `Cache-Control: private, max-age=3600`); `404 {"detail": "Page not found"}`.

**Functions added by this feature:** none beyond the route handlers.

| Input | Output |
|---|---|
| upload `q.pdf` (`application/pdf`, 2 pages) | `201 {"attachment_id": "A1", "file_name": "q.pdf", "media_type": "application/pdf", "parse_status": "parsed", "pages": [{"page_no": 1, "width_px": 1240, "height_px": 1754, "image_url": "/api/sessions/<sid>/attachments/A1/pages/1.png"}, {...page 2}], "error": null}` |
| `GET .../A1/pages/3.png` on a 2-page attachment | `404 {"detail": "Page not found"}` |

#### 6. Implementation steps

1. Route handler API-02: `session = sessions.get(sid)`; `if len(session.attachments) >= MAX_ATTACHMENTS_PER_SESSION: raise HTTPException(422, "A request may have at most 10 attachments")`; media type = the multipart content type, with `.pdf/.png/.jpg/.jpeg` extension fallback when the browser sends `application/octet-stream`; `async with sessions.with_lock(sid)`: `aid = sessions.next_attachment_id(session)`; `attachment = await run_in_threadpool(attachment_service.ingest, sid, aid, file.filename, media_type, data)`; append to `session.attachments`; `touch`.
2. Map exceptions: `ValueError` → 422 with its message; `PayloadTooLarge` → 413; `UpstreamUnavailable` → 503 with its message.
3. Route handler API-03: find attachment and page; `volume.get(page.image_path)` → `Response(content, media_type="image/png")`.
4. Register the router in `main.py`.

Constants: none new.

#### 7. Edge cases and errors

| Case | Input | Expected behaviour |
|---|---|---|
| Unknown session | any upload | `404 Session not found` |
| 11th attachment | session with 10 | `422 A request may have at most 10 attachments`, nothing stored |
| Excel | `.xlsx` | `422 Only PDF, PNG and JPG files are supported` |
| Parse failed | warehouse down | `201` with `parse_status == "failed"`, `error == "The attachment could not be read"`; pages viewable |
| Missing page image | volume file gone | `404 Page not found` |
| Upload while extraction runs | `extraction_status == "extracting"` | allowed; the attachment joins the next message |

#### 8. Acceptance criteria and tests

Test file: `SCO-001/tests/unit/routers/test_f02_attachments.py` · fixtures: `client`, `fake_volume_repository`, `fake_parse_repository`, `tests/fixtures/two_pages_text.pdf`

| AC ID | Given / When / Then | Test name | Fixture data | Expected |
|---|---|---|---|---|
| AC-F02-1 | Given a session, when the 2-page PDF is uploaded, then `A1` with 2 pages and image urls | `test_f02_ac1_upload_pdf` | `two_pages_text.pdf`, `parse_result_two_pages.json` | `201`, `attachment_id == "A1"`, `len(pages) == 2`, `pages[0]["image_url"].endswith("/attachments/A1/pages/1.png")`, `parse_status == "parsed"`; `GET /api/sessions/<sid>` lists 1 attachment |
| AC-F02-2 | Given the uploaded PDF, when page 1 is requested, then PNG bytes | `test_f02_ac2_page_image` | from AC-1 | `200`, `content-type image/png`, body starts with `\x89PNG` |
| AC-F02-3 | Given an `.xlsx` upload, when posted, then 422 and nothing stored | `test_f02_ac3_reject_xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | `422 {"detail": "Only PDF, PNG and JPG files are supported"}`; no new attachment; volume unchanged |
| AC-F02-4 | Given a failing parse repository, when uploaded, then 201 with `failed` | `test_f02_ac4_parse_failed` | `fake_parse_repository.fail_for = {"A1"}` | `201`, `parse_status == "failed"`, `error == "The attachment could not be read"`, 2 pages with `image_url` |

Integration / evaluation checks (run by a human in dev): upload the golden PDF with `curl -F file=@...` → `201`; `SELECT path FROM read_files('/Volumes/sandbox_others/sco_001_poc/uploads/<sid>/A1/pages/', format => 'binaryFile')` lists the pages.

#### 9. Build-ready checklist (Planner self-check)

- [x] Every related feature (this set or earlier sets) is listed in §2 with the exact names this feature uses
- [x] Every path, table, column, API, agent and config key exists in the TSD, in §2, or earlier in this feature
- [x] Every join is written out in §4 (tables, type, condition, filters, expected result)
- [x] Every step is exact; SQL given for non-trivial logic; all constants have values
- [x] Every acceptance criterion has a test with literal fixture data and expected output
- [x] Edge cases cover empty, invalid, not-found and permission cases where relevant
- [x] No open words (e.g., such as, appropriate, as needed, TBD, etc., choose, decide)

**Out of scope for this feature:** deleting single attachments (a steward starts a new session instead); thumbnails;
virus scanning; resumable uploads; drag-and-drop (frontend, v2/F-06).

**How a human tests it:** 1) Upload the golden PDF to a dev session with `curl`. 2) Open the returned `image_url` in the browser → the page image. 3) Upload an `.xlsx` → 422 text.

---

### v2/F-03 — Build the message route API-04 with triage, background extraction and merge

| Field | Value |
|---|---|
| Module / layer | `routers/messages`, `services/extraction_service` — `backend/routers/messages.py`, `backend/services/extraction_service.py` (TSD §4) |
| Type | API |
| Size | M |
| Depends on / related to | v2/F-01, v2/F-02, v1/F-05, v1/F-06, v1/F-07 (depends on) |
| PRD refs | PRD-SCO-001 US-1, US-2, US-3, §7 (5 s, 60 s) |
| TSD refs | §2.4 RF-01, RF-03; §6.1 API-04, API-05; §7 AG-02, AG-03, M-01; §9 |
| Standards applied | BR-10, skill:ai_agents §7, references/eval-and-ops.md §4, skill:ui_ux_design §6, §8 (assistant copy) |

#### 1. Context

This is the heart of RF-01: the route stores the message, runs AG-02 synchronously (answer within 5 s), then runs AG-03
and the rules as a background task, merging with an existing result (M-01). `not_pir_sl` and `other` messages get a
plain assistant reply and no extraction. Corrections are routed to AG-04 in v2/F-04; until then they get a stub reply.

#### 2. Related features — context from earlier work

| Feature | Set | Relationship | What it built that this feature uses (exact names) | Status |
|---|---|---|---|---|
| v2/F-01 | v2 | depends on | `SessionService.get`, `next_message_id`, `touch`, `with_lock`; `app.state.gateway`, `app.state.sessions` | To do |
| v2/F-02 | v2 | depends on | `session.attachments` filled by API-02; `parse_status` values | To do |
| v1/F-05 | v1 | depends on | `RequestTriageAgent(gateway, settings).run(messages, attachments, result_summary) -> TriageDecision(request_type, message_kind, meta)` | Done |
| v1/F-06 | v1 | depends on | `LineItemExtractionAgent(gateway, settings).run(messages, attachments, request_type) -> ExtractionDraft` | Done |
| v1/F-07 | v1 | depends on | `extraction_service.build_result(draft, request_type, messages, existing) -> Result`; `merge_result` | Done |
| v1/F-01 | v1 | uses | `models.Message, ChangedField, Result`; `constants.MAX_MESSAGE_CHARS = 20000`, `REQUEST_TYPE_LABELS`, `FIELD_LABELS` | Done |

**Rules carried over from those features:** corrected fields are never overwritten by a re-extraction (v1/F-07 M-03);
segment ids `M<n>` match `Message.message_id` (v1/F-04).

#### 3. Files

| Action | Path | Purpose |
|---|---|---|
| create | `SCO-001/backend/routers/messages.py` | API-04 |
| modify | `SCO-001/backend/services/extraction_service.py` | add class `ExtractionOrchestrator` with `handle_message`, `run_extraction`, `result_summary`, `describe_changes`; existing rule functions unchanged |
| modify | `SCO-001/backend/main.py` | include `messages` router; build `ExtractionOrchestrator(gateway, settings, sessions)` on `app.state` only |
| modify | `SCO-001/backend/models.py` | add `MessageRequest(text: str, attachment_ids: list[str])`, `MessageAccepted(message_id, request_type, message_kind, extraction_status, assistant_message)` only |
| create | `SCO-001/tests/unit/routers/test_f03_messages.py` | tests for this feature |
| create | `SCO-001/tests/integration/test_v2_golden_flow.py` | golden example through the real dev app (marker `integration`) |

No other files may be created or changed.

#### 4. Data

| Table (TSD §5.2 ID) | Columns read | Columns written | Write mode |
|---|---|---|---|
| — | — | — | — (session memory only) |

**Joins (this feature):** none.

#### 5. Interfaces

**API (TSD §6.1):** `POST /api/sessions/{session_id}/messages` — request `{text: str, attachment_ids: list[str]}` →
`202 {message_id: str, request_type: RequestTypeResult, message_kind: str, extraction_status: str, assistant_message: Message | None}`;
errors `404 Session not found`; `422 {"detail": "Type a message or attach a file"}` (empty text and no attachments),
`422 {"detail": "A message may have at most 20000 characters"}`, `422 {"detail": "Unknown attachment A9"}`;
`503 {"detail": "The AI service did not answer; send the message again"}` (AG-02 failure; the message is not stored).

**Functions added by this feature:**

```python
class ExtractionOrchestrator:
    def __init__(self, gateway: GatewayRepository, settings: Settings, sessions: SessionService) -> None: ...

    async def handle_message(self, session: Session, message: Message, background: BackgroundTasks) -> MessageAccepted:
        """AG-02 synchronously; then by message_kind: request_content -> schedule run_extraction (unless not_pir_sl); correction -> stub reply (replaced in v2/F-04); other -> reply."""

    async def run_extraction(self, session_id: str) -> None:
        """Background: AG-03 on all messages and attachments, build_result with existing result (M-01), set extraction_status ready/failed, append assistant message describing added lines and changed values."""

    def result_summary(self, result: Result | None) -> str:
        """'' or 'Current result: <label>, <n> line items: 1 PIR 1038-967-34; 2 PIR 1038-967-04'."""

    def describe_changes(self, before: Result | None, after: Result) -> tuple[str, list[ChangedField]]:
        """Text 'Found 2 line items.' / 'Added 1 line item (3 PIR 2000-04275). Changed line 1 Plant: empty → 3300.'"""
```

| Input | Output |
|---|---|
| golden message with `attachment_ids ["A1"]`, fake triage `update_pir` / `request_content` | `202 {"message_id": "M1", "request_type": {"value": "update_pir", ...}, "message_kind": "request_content", "extraction_status": "extracting", "assistant_message": null}`; after the background task `GET` shows `extraction_status == "ready"`, `result.line_items` length 2, assistant message `M2` text `Found 2 line items.` |
| text `Thanks for your help last week!`, fake triage `not_pir_sl` | `202` with `extraction_status == "idle"` and `assistant_message.text == "This is not a PIR or Source List request, so nothing was extracted."` |

#### 6. Implementation steps

1. Route: validate per §5; unknown attachment id → 422; `async with sessions.with_lock(sid)`: `message = Message(message_id=sessions.next_message_id(session), role="user", text=text, attachment_ids=attachment_ids, created_at=now)`; call `orchestrator.handle_message`; on `UpstreamUnavailable` from AG-02 → do not append the message, return 503; else append message, `touch`, return `202`.
2. `handle_message`: wait for every referenced attachment with `parse_status == "pending"` (poll every 0.5 s, up to 30 s; after that proceed without its elements and add note `Attachment A1 is still being read`); `decision = triage.run(session.messages + [message], session.attachments, result_summary(session.result))`; branches:
   - `request_type == not_pir_sl` and `session.result is None`: assistant reply `This is not a PIR or Source List request, so nothing was extracted.`; `extraction_status` stays `idle`.
   - `message_kind == other`: reply `I can only help with PIR and Source List requests.`; no extraction.
   - `message_kind == correction` and `session.result is None`: reply `There is nothing to correct yet; send the request first.`
   - `message_kind == correction` and result exists: v2/F-04 replaces this branch; until then reply `Corrections by chat come in the next version; edit the value directly.`
   - `message_kind == request_content`: set `session.extraction_status = "extracting"`, `background.add_task(self.run_extraction, session.session_id)`.
   - Store `decision.request_type` into `session.result.request_type` when a result exists and `request_type.corrected` is false; when no result exists yet keep it in `session.pending_request_type` (add this optional field to `Session` in `models.py` — allowed modification: `pending_request_type: RequestTypeResult | None = None`).
3. `run_extraction`: `async with sessions.with_lock(sid)`: snapshot messages, attachments, request type; release the lock during the model call (`await run_in_threadpool(extract.run, ...)`); re-acquire; `fresh = build_result(draft, request_type, messages, None)`; `after = merge_result(session.result, fresh) if session.result else fresh`; `text, changes = describe_changes(session.result, after)`; `session.result = after`; `extraction_status = "ready"`; append `Message(role="assistant", text=text, changed_fields=changes)`; on `UpstreamUnavailable(reason)` → `extraction_status = "failed"`, `session.error = reason`, append assistant message `The line items could not be extracted: <reason>`.
4. `describe_changes`: compare line keys and field values; wording per §5; labels from `REQUEST_TYPE_LABELS` and `FIELD_LABELS`; `empty` for `None`.
5. Integration test `test_v2_golden_flow.py`: create session, upload SRC-01 `GE-001` PDF (read through `VolumeRepository.get` of `/Volumes/sandbox_others/sco_001_poc/demo_requests/GE-001/BE25112601_RAIL-DIN 35MM X 7.5MM.pdf`), post `golden_message_M1.txt`, assert `202` within 5 s and `request_type.value == "update_pir"`, poll `GET` every 2 s up to 60 s until `ready`, assert 2 lines and the PRD §6 values (`amount 7000`, `plant` missing, `country_of_origin` value `KR`).

Constants: `PARSE_WAIT_SECONDS = 30`, `PARSE_POLL_SECONDS = 0.5` (defined in `backend/services/extraction_service.py`); assistant texts as literal module constants `MSG_NOT_PIR_SL`, `MSG_OTHER`, `MSG_NOTHING_TO_CORRECT`, `MSG_CORRECTION_STUB`, `MSG_EXTRACTION_FAILED`.

#### 7. Edge cases and errors

| Case | Input | Expected behaviour |
|---|---|---|
| Empty message, no attachments | `{"text": "", "attachment_ids": []}` | `422 Type a message or attach a file` |
| Only attachments | `{"text": "", "attachment_ids": ["A1"]}` | accepted; triage runs on elements |
| Too long | 20001 chars | `422 A message may have at most 20000 characters` |
| Triage fails | `UpstreamUnavailable` | `503`, message not stored, session unchanged |
| Extraction fails | AG-03 raises | `extraction_status failed`, `error` set, assistant message with reason; user input kept |
| Second request message while extracting | new `request_content` | accepted; `run_extraction` scheduled again; the lock serialises the two runs; the second run merges on the first's result |
| Attachment failed to parse | `parse_status failed` | extraction proceeds on messages; note `Attachment A1 could not be read` in `result.notes` |
| `not_pir_sl` after a result exists | later message classified `not_pir_sl` as `request_content` | treated as `other` reply; result unchanged |

#### 8. Acceptance criteria and tests

Test file: `SCO-001/tests/unit/routers/test_f03_messages.py` · fixtures: `client`, `fake_gateway`, `fake_parse_repository`, `golden_messages`, `golden_triage_output`, `golden_extraction_output`, `two_pages_text.pdf`

| AC ID | Given / When / Then | Test name | Fixture data | Expected |
|---|---|---|---|---|
| AC-F03-1 | Given an uploaded attachment and the golden text, when posted, then 202 with `update_pir` and, after the background task, a ready result with 2 lines and an assistant message | `test_f03_ac1_golden_message_flow` | `fake_gateway` `{"request_triage_chat": [golden_triage_output], "line_item_extraction_chat": [golden_extraction_output]}`; `fake_parse_repository` returning `parsed_golden_A1.json` | `202`, `message_id == "M1"`, `request_type.value == "update_pir"`, `extraction_status == "extracting"`; `GET` → `extraction_status == "ready"`, 2 line items, `line_items[0].fields.amount.value == "7000"`, `line_items[0].fields.plant.status == "missing"`, assistant `M2` text `Found 2 line items.` |
| AC-F03-2 | Given a thank-you text, when posted, then no extraction and the fixed reply | `test_f03_ac2_not_pir_sl` | triage answer `{"request_type": "not_pir_sl", "message_kind": "request_content", "reason": "Thanks only", "evidence": []}` | `202`, `extraction_status == "idle"`, `assistant_message.text == "This is not a PIR or Source List request, so nothing was extracted."`; `fake_gateway.calls` has no `line_item_extraction_chat` |
| AC-F03-3 | Given a ready result with line 1 `amount` corrected to `8000` (via `apply_patches` in the test), when a new `request_content` message arrives and extraction returns `7000`, then the corrected value stays and a new part is appended | `test_f03_ac3_reextraction_merge` | second extraction output = golden plus a third line `material 2000-04275` | after the task: 3 lines; line 1 `amount.value == "8000"`, `status == "corrected"`; assistant text `Added 1 line item (3 PIR 2000-04275).` |
| AC-F03-4 | Given a failing triage, when posted, then 503 and nothing stored | `test_f03_ac4_triage_failure` | `fake_gateway.raise_for = {"request_triage_chat": UpstreamUnavailable("The AI service did not answer within 60 seconds")}` | `503 {"detail": "The AI service did not answer; send the message again"}`; `GET` → `messages == []` |

Integration / evaluation checks (run by a human in dev): `pytest -m integration tests/integration/test_v2_golden_flow.py` passes (`202` in < 5 s, `ready` in < 60 s, PRD §6 values).

#### 9. Build-ready checklist (Planner self-check)

- [x] Every related feature (this set or earlier sets) is listed in §2 with the exact names this feature uses
- [x] Every path, table, column, API, agent and config key exists in the TSD, in §2, or earlier in this feature
- [x] Every join is written out in §4 (tables, type, condition, filters, expected result)
- [x] Every step is exact; SQL given for non-trivial logic; all constants have values
- [x] Every acceptance criterion has a test with literal fixture data and expected output
- [x] Edge cases cover empty, invalid, not-found and permission cases where relevant
- [x] No open words (e.g., such as, appropriate, as needed, TBD, etc., choose, decide)

**Out of scope for this feature:** the correction agent (v2/F-04); streaming tokens; WebSockets; retrying extraction
automatically; translating assistant replies (English only in the PoC).

**How a human tests it:** 1) Run the integration test. 2) In the dev app API, post `Thanks for your help last week!` → the fixed reply. 3) Post the golden message twice; the second run adds no lines (same materials) and the assistant says `No changes.`

---

### v2/F-04 — Build AG-04 correction and wire chat corrections

| Field | Value |
|---|---|
| Module / layer | `agents/correction` — `backend/agents/correction/agent.py`, `schema.py`, `prompts/correction_chat.md` (TSD §4) |
| Type | LLM call |
| Size | M |
| Depends on / related to | v2/F-03 (depends on), v1/F-03, v1/F-07 (depends on) |
| PRD refs | PRD-SCO-001 US-9 (chat corrections, asks back, marks corrected, source = chat message) |
| TSD refs | §2.4 RF-02; §7 AG-04, `CorrectionOutput`, M-02, M-03, M-04 |
| Standards applied | skill:ai_agents §1 (level 3), §4, §7, references/eval-and-ops.md §2, §4; skill:ui_ux_design §8 (reply copy) |

#### 1. Context

A steward types `line 2 amount is 8000` or `add plant 3300 to all lines`. AG-04 turns the instruction into patches
against the current line items, or a clarification question when the instruction is unclear. The code applies only the
patches that match fields named in the instruction, marks them `corrected` with the chat message as source, and
replies with the exact changes.

#### 2. Related features — context from earlier work

| Feature | Set | Relationship | What it built that this feature uses (exact names) | Status |
|---|---|---|---|---|
| v2/F-03 | v2 | depends on | `ExtractionOrchestrator.handle_message` branch `message_kind == correction` (stub to replace); `describe_changes`; assistant message append pattern; `MSG_NOTHING_TO_CORRECT` | To do |
| v1/F-03 | v1 | depends on | `GatewayRepository.complete_json`; `evals/register_prompts.py` (registers every `prompts/*.md`) | Done |
| v1/F-07 | v1 | depends on | `apply_patches(result, patches, source) -> (Result, list[ChangedField], list[str])`, `Patch(line_no, field, value)`, `add_line(result, doc_type, action, values, source)`, `remove_line(result, line_no)`, `set_request_type(result, value, source)` | Done |
| v1/F-04 | v1 | uses | `locate_message(text, quote)` for the source span | Done |
| v1/F-02 | v1 | uses | T-01 cases tagged `correction` (`COR-001..008`): `messages_json` holds the request and the correction message; `expected_line_items_json` is the result after the correction | Done |
| v1/F-08 | v1 | extends | `evals/run_eval.py` — this feature adds `--include-corrections` | Done |

**Rules carried over from those features:** `apply_patches` skips unknown lines / fields and reports them (v1/F-07); corrected fields are never overwritten (M-03).

#### 3. Files

| Action | Path | Purpose |
|---|---|---|
| create | `SCO-001/backend/agents/correction/__init__.py`, `schema.py`, `agent.py` | AG-04 |
| create | `SCO-001/prompts/correction_chat.md` | prompt text v1 |
| modify | `SCO-001/backend/services/extraction_service.py` | replace the correction stub branch with `apply_correction`; add `MSG_CLARIFY_PREFIX` | 
| modify | `SCO-001/backend/main.py` | load prompt `correction_chat` at start only |
| modify | `SCO-001/evals/run_eval.py` | add flag `--include-corrections` running `COR-*` cases through triage → extraction → correction and scoring `patch_exact_match`, `clarification_on_ambiguous`, `no_unrequested_change` |
| modify | `SCO-001/evals/scorers.py` | add the three scorers only |
| create | `SCO-001/tests/unit/agents/test_f04_correction.py` | tests for this feature |
| create | `SCO-001/tests/integration/test_v2_f04_chat_correction.py` | chat correction on the golden example in dev |

No other files may be created or changed.

#### 4. Data

| Table (TSD §5.2 ID) | Columns read | Columns written | Write mode |
|---|---|---|---|
| T-01 | rows with `array_contains(tags, 'correction')` (evaluation only) | — | — |

**Joins (this feature):** none.

#### 5. Interfaces

**API (TSD §6.1):** API-04 unchanged in shape; for `message_kind == correction` the `202` carries `assistant_message` with `changed_fields` filled or `clarification = true`.

**Functions added by this feature:**

```python
class CorrectionAgent:
    def run(self, instruction: Message, result: Result, messages: list[Message]) -> CorrectionOutput:
        """Prompt correction_chat on ENDPOINT_EXTRACT with variables instruction, line_items (compact JSON: line_no, doc_type, action, field: value), request_type, pir_fields, sl_fields."""

def apply_correction(self, session: Session, instruction: Message, output: CorrectionOutput) -> Message:
    """ExtractionOrchestrator method. clarification_question -> assistant Message(clarification=True). Else: guard, apply patches / add_lines / remove_line_nos / request_type with source = Source(kind='message', message_id=instruction.message_id, start=0, end=len(text), text=instruction.text); build assistant message listing changes and skipped items."""

def guard_patches(instruction_text: str, output: CorrectionOutput) -> tuple[CorrectionOutput, list[str]]:
    """Drop patches whose field label or internal name (FIELD_LABELS, case-insensitive) does not occur in the instruction, unless the instruction contains 'all' and the field is named; returns kept output and messages 'Ignored change to <label> on line <n>: not asked for'."""
```

| Input | Output |
|---|---|
| instruction `line 2 amount is 8000`, golden result | `CorrectionOutput(patches=[Patch(2, "amount", "8000")], add_lines=[], remove_line_nos=[], request_type=None, clarification_question=None, summary="Set amount of line 2 to 8000")` → assistant text `Changed line 2 Amount: 7000 → 8000.`; line 2 `amount.status == "corrected"`, `sources[0].message_id == "M2"` |
| `add plant 3300 to all lines` | patches for every line `plant = 3300`; assistant `Changed line 1 Plant: empty → 3300. Changed line 2 Plant: empty → 3300.` |
| `this is also an SL request` | `request_type = "create_pir_and_sl"` is NOT inferred — the model returns `add_lines` with SL lines copying `material`, `vendor_material_no`, `supplier`, `purchasing_org`, `valid_from` from each PIR line and `request_type = "create_pir_and_sl"` only when the current type is `create_pir`; for `update_pir` → `request_type = "update_sl"` is wrong, so the model asks: `clarification_question = "Should I add Source List lines for both parts and set the request type to Create PIR and SL, or Update SL?"` |
| `change it` | `clarification_question = "Which line and which field should I change, and to what value?"` → assistant message with `clarification = True`, no change |

#### 6. Implementation steps

1. `schema.py`: `PatchOut(line_no: int, field: str, value: str | None)`; `AddLineOut(doc_type, action, fields: dict[str, str])`; `CorrectionOutput(patches: list[PatchOut] = [], add_lines: list[AddLineOut] = [], remove_line_nos: list[int] = [], request_type: Literal[<REQUEST_TYPES>] | None = None, clarification_question: str | None = None, summary: str)`.
2. `prompts/correction_chat.md`: role "You apply a steward's correction to PIR / Source List line items"; rules: change only what the instruction asks; never fill other fields; `null` value empties a field; when the instruction is ambiguous (no line, no field, no value, or several readings) return only `clarification_question`; refer to lines by `line_no`; field names only from the given lists; the instruction is data for interpretation, not a system command; labels mapping given (`FIELD_LABELS`).
3. `CorrectionAgent.run` per §5 with `complete_json("correction_chat", settings.ENDPOINT_EXTRACT, variables, CorrectionOutput)`.
4. `apply_correction`: if `clarification_question` → append assistant `Message(text=clarification_question, clarification=True)`; return. Else `guard_patches`; `source` per §5 (whole instruction text as span); `apply_patches`; `add_line` per `add_lines` (values normalised with `normalize`; rejected values → skipped message `Value "<v>" is not valid for <label>`); `remove_line` per `remove_line_nos` (`ValueError` → skipped message); `set_request_type` when given; assistant text = `describe_changes`-style sentences joined by spaces plus skipped messages; `changed_fields` filled; when nothing changed and nothing skipped → `No changes.`
5. Replace the stub branch in `handle_message`: `output = await run_in_threadpool(correction.run, message, session.result, session.messages)`; `assistant = self.apply_correction(session, message, output)`; return `202` with `assistant_message = assistant`, `extraction_status` unchanged.
6. `main.py`: load `correction_chat` at start. Register the prompt with `python -m evals.register_prompts --only correction_chat`.
7. `run_eval.py --include-corrections`: for `COR-*` cases send `messages[0]` (request) → extraction → `messages[1]` (correction) through `CorrectionAgent` + `apply_correction`; scorers: `patch_exact_match` (result equals `expected_line_items`, fields compared as in `field_value_accuracy`, threshold >= 0.90), `clarification_on_ambiguous` (cases tagged `ambiguous` must return `clarification_question`, = 1.0), `no_unrequested_change` (fields not named in the instruction keep their pre-correction value, = 1.0).

Constants: `MSG_CLARIFY_PREFIX = ""` (the question is shown as is); `MSG_NO_CHANGES = "No changes."` (defined in `backend/services/extraction_service.py`).

#### 7. Edge cases and errors

| Case | Input | Expected behaviour |
|---|---|---|
| No result yet | correction before extraction | `MSG_NOTHING_TO_CORRECT` reply (v2/F-03) |
| Ambiguous | `change it` | clarification, no change |
| Unknown line | `line 9 amount is 1` | assistant `Line 9 does not exist.`; no change |
| Patch to unmentioned field | model returns `currency` patch for `line 2 amount is 8000` | dropped by `guard_patches`; assistant adds `Ignored change to Cond. Currency on line 2: not asked for` |
| Empty a field | `remove the plant on line 1` | `Patch(1, "plant", None)` → `Changed line 1 Plant: 3300 → empty.` |
| Invalid value | `line 1 purchasing org is S33` | `normalize` rejects → skipped `Value "S33" is not valid for Purchasing Org.`; no change |
| Model failure | `UpstreamUnavailable` | assistant `I could not apply that change; edit the value directly.`; `202` |
| Remove and re-extract | line 2 removed, later message re-extracts the same part | M-01 appends it again as a new line (`line_no 3`) — accepted, the steward removed it knowingly |

#### 8. Acceptance criteria and tests

Test file: `SCO-001/tests/unit/agents/test_f04_correction.py` · fixtures: `client`, `fake_gateway`, golden flow of v2/F-03 AC-1 as setup

| AC ID | Given / When / Then | Test name | Fixture data | Expected |
|---|---|---|---|---|
| AC-F04-1 | Given the golden result, when `line 2 amount is 8000` is posted (triage `correction`, correction output with one patch), then only that cell changes and is sourced to M2 | `test_f04_ac1_single_patch` | triage answer `message_kind correction`; correction answer `{"patches":[{"line_no":2,"field":"amount","value":"8000"}],"add_lines":[],"remove_line_nos":[],"request_type":null,"clarification_question":null,"summary":"s"}` | `202`; `assistant_message.text == "Changed line 2 Amount: 7000 → 8000."`; `changed_fields == [{"line_no":2,"field":"amount","old_value":"7000","new_value":"8000"}]`; `GET` → line 2 `amount.value "8000"`, `status "corrected"`, `sources[0].message_id "M2"`, `sources[0].text == "line 2 amount is 8000"`; line 1 `amount` unchanged |
| AC-F04-2 | Given `change it`, when posted, then a clarification and no change | `test_f04_ac2_clarification` | correction answer `{"patches":[],...,"clarification_question":"Which line and which field should I change, and to what value?","summary":""}` | `assistant_message.clarification == true`, text equals the question; result unchanged (`updated_at` equal) |
| AC-F04-3 | Given a model patch to `currency` for the instruction `line 2 amount is 8000`, when applied, then it is ignored and reported | `test_f04_ac3_guard_unrequested` | correction answer with patches `amount 8000` and `currency USD` on line 2 | `amount` changed; `currency.value == "KRW"`; assistant text contains `Ignored change to Cond. Currency on line 2: not asked for` |
| AC-F04-4 | Given `add plant 3300 to all lines`, when applied, then both lines get `plant` corrected | `test_f04_ac4_all_lines` | patches for lines 1 and 2 `plant 3300` | both `plant.value == "3300"`, `status corrected`; text `Changed line 1 Plant: empty → 3300. Changed line 2 Plant: empty → 3300.` |

Integration / evaluation checks (run by a human in dev): `pytest -m integration tests/integration/test_v2_f04_chat_correction.py` (golden flow, then `line 2 amount is 8000`, asserts AC-1 on the real endpoint); `python -m evals.run_eval --set-version 1 --endpoint-mode primary --include-corrections` reports `patch_exact_match >= 0.90`, `clarification_on_ambiguous = 1.0`, `no_unrequested_change = 1.0`.

#### 9. Build-ready checklist (Planner self-check)

- [x] Every related feature (this set or earlier sets) is listed in §2 with the exact names this feature uses
- [x] Every path, table, column, API, agent and config key exists in the TSD, in §2, or earlier in this feature
- [x] Every join is written out in §4 (tables, type, condition, filters, expected result)
- [x] Every step is exact; SQL given for non-trivial logic; all constants have values
- [x] Every acceptance criterion has a test with literal fixture data and expected output
- [x] Edge cases cover empty, invalid, not-found and permission cases where relevant
- [x] No open words (e.g., such as, appropriate, as needed, TBD, etc., choose, decide)

**Out of scope for this feature:** undo; multi-turn clarification memory beyond the chat history (the next message is
triaged afresh); corrections that call SAP; natural-language export commands.

**How a human tests it:** 1) Golden flow in the dev app, then type `line 2 amount is 8000` → one cell marked Corrected and the
reply lists it. 2) Type `change it` → the assistant asks which line and field. 3) Type `add plant 3300 to all lines` → both Plant cells filled and marked Corrected.

---

### v2/F-05 — Build direct edit API-06 and export API-07

| Field | Value |
|---|---|
| Module / layer | `routers/results`, `services/export_service` — `backend/routers/results.py`, `backend/services/export_service.py` (TSD §4) |
| Type | API |
| Size | S |
| Depends on / related to | v2/F-03 (depends on), v1/F-07 (depends on) |
| PRD refs | PRD-SCO-001 US-9 (direct edit), US-10 (JSON / CSV) |
| TSD refs | §6.1 API-06, API-07; §7 M-02, M-04; §5.2 `PIR_FIELDS`, `SL_FIELDS` |
| Standards applied | BR-09 (export visible to stewards only), skill:ui_ux_design §8 (file naming) |

#### 1. Context

Direct edits are the second correction path with the same result as chat corrections: status `corrected`, source
`user_edit`, never overwritten. The export renders the reviewed line items in the PRD field order as JSON or CSV.

#### 2. Related features — context from earlier work

| Feature | Set | Relationship | What it built that this feature uses (exact names) | Status |
|---|---|---|---|---|
| v2/F-03 | v2 | depends on | `session.result` filled by `run_extraction`; `extraction_status`; `with_lock` | To do |
| v1/F-07 | v1 | depends on | `apply_patches`, `Patch`, `add_line`, `remove_line`, `set_request_type`, `normalize` | Done |
| v1/F-01 | v1 | uses | `constants.PIR_FIELDS, SL_FIELDS, FIELD_LABELS, REQUEST_TYPES`; `errors.ConflictError` | Done |

**Rules carried over from those features:** invalid values are rejected by `normalize` with the N-rule issue text (v1/F-07); `line_no` never reused (M-04).

#### 3. Files

| Action | Path | Purpose |
|---|---|---|
| create | `SCO-001/backend/routers/results.py` | API-06, API-07 |
| create | `SCO-001/backend/services/export_service.py` | `to_json(result) -> str`, `to_csv(result) -> str` |
| modify | `SCO-001/backend/main.py` | include `results` router only |
| modify | `SCO-001/backend/models.py` | add `ResultPatchRequest(op, line_no, field, value, doc_type, action, request_type)` only |
| create | `SCO-001/tests/unit/routers/test_f05_results.py` | tests for this feature |

No other files may be created or changed.

#### 4. Data

| Table (TSD §5.2 ID) | Columns read | Columns written | Write mode |
|---|---|---|---|
| — | — | — | — |

**Joins (this feature):** none.

#### 5. Interfaces

**API (TSD §6.1):**
- `PATCH /api/sessions/{session_id}/result` — `{op: "set_field"|"add_line"|"remove_line"|"set_request_type", line_no?: int, field?: str, value?: str|null, doc_type?: "PIR"|"SL", action?: "create"|"update", request_type?: str}` → `200 Result`; `404 Session not found`; `409 {"detail": "There is no result to edit yet"}`; `422` with `Line <n> does not exist` / `Field <f> does not exist on line <n>` / `Value "<v>" is not valid for <label>: <issue>` / `Unknown op <op>` / `request_type must be one of ...`.
- `GET /api/sessions/{session_id}/export?format=json|csv` → `200`, `Content-Disposition: attachment; filename="sco_request_<sid[:8]>.<ext>"`; `409` when no result; `422 {"detail": "format must be json or csv"}`.

**Functions added by this feature:**

```python
def to_json(result: Result) -> str:
    """{"request_type": "<value>", "line_items": [{"line_no": 1, "doc_type": "PIR", "action": "update", "supplier": "18570", ..., "fixed_vendor": null}]} — every field of EXPORT_COLUMNS present, null when empty; indent 2; ensure_ascii False."""

def to_csv(result: Result) -> str:
    """Header EXPORT_COLUMNS; one row per line item; empty string for null; UTF-8 with BOM; CRLF line ends; values quoted when they contain , or quotes."""
```

`EXPORT_COLUMNS = ["line_no", "doc_type", "action", "supplier", "material", "vendor_material_no", "plant", "purchasing_org", "country_of_origin", "lead_time_days", "standard_qty", "amount", "currency", "pricing_unit", "unit_of_measure", "valid_from", "valid_to", "fixed_vendor"]` (defined in `backend/services/export_service.py`).

| Input | Output |
|---|---|
| `PATCH {"op": "set_field", "line_no": 1, "field": "plant", "value": "3300"}` | `200`; line 1 `plant.value "3300"`, `status "corrected"`, `sources == [{"kind": "user_edit", "text": "Edited by the steward", ...}]` |
| `PATCH {"op": "set_field", "line_no": 1, "field": "purchasing_org", "value": "S33"}` | `422 {"detail": "Value \"S33\" is not valid for Purchasing Org.: \"S33\" is not a purchasing organisation (3000, 3300, 8000)"}` |
| `GET .../export?format=csv` on the golden result | first line `line_no,doc_type,action,supplier,material,vendor_material_no,plant,purchasing_org,country_of_origin,lead_time_days,standard_qty,amount,currency,pricing_unit,unit_of_measure,valid_from,valid_to,fixed_vendor`; second line `1,PIR,update,18570,1038-967-34,RAIL-DIN 35MM X 7.5MM X 450MM LG,,3300,KR,7,1,7000,KRW,1,EA,2025-11-26,,` |

#### 6. Implementation steps

1. API-06 handler: `session = sessions.get(sid)`; `if session.result is None: raise ConflictError` → 409; `async with with_lock`: by `op`: `set_field` → `normalize(field, Candidate(value_raw=value, ...), ctx)` when `value` is not null; rejected → 422; then `apply_patches(result, [Patch(line_no, field, normalised)], Source(kind="user_edit", text="Edited by the steward"))`; skipped messages → 422 with the first message; `add_line` → `add_line(result, doc_type, action, {}, source)`; `remove_line` → `remove_line`; `set_request_type` → validate against `REQUEST_TYPES`, `set_request_type`; update `session.result`, `touch`; return `Result`.
2. API-07 handler: `format` validation; `to_json` / `to_csv`; `Response(content, media_type, headers={"Content-Disposition": ...})`; `application/json; charset=utf-8` or `text/csv; charset=utf-8`.
3. `export_service` per §5; SL lines leave PIR-only columns empty; PIR lines leave `fixed_vendor` empty.

Constants: `EXPORT_COLUMNS` as above; `USER_EDIT_TEXT = "Edited by the steward"`.

#### 7. Edge cases and errors

| Case | Input | Expected behaviour |
|---|---|---|
| No result | `PATCH` before extraction | `409 There is no result to edit yet` |
| Unknown op | `{"op": "rename"}` | `422 Unknown op rename` |
| Unknown field for doc type | `fixed_vendor` on a PIR line | `422 Field fixed_vendor does not exist on line 1` |
| Empty value | `value: null` | field emptied, `status corrected` |
| Remove last line | `remove_line` on the only line | `200`, `line_items == []`; export still works (header only) |
| Export during extraction | `extraction_status extracting` | allowed on the current result; `409` when none |
| CSV injection | value starting with `=` | prefixed with a single quote `'` in CSV |

#### 8. Acceptance criteria and tests

Test file: `SCO-001/tests/unit/routers/test_f05_results.py` · fixtures: `client`, golden flow of v2/F-03 AC-1 as setup

| AC ID | Given / When / Then | Test name | Fixture data | Expected |
|---|---|---|---|---|
| AC-F05-1 | Given the golden result, when `set_field plant 3300` on line 1, then corrected with `user_edit` source | `test_f05_ac1_set_field` | `{"op":"set_field","line_no":1,"field":"plant","value":"3300"}` | `200`; `line_items[0].fields.plant.value == "3300"`, `status == "corrected"`, `sources[0].kind == "user_edit"`; line 2 `plant` still `missing` |
| AC-F05-2 | Given the golden result, when `set_field purchasing_org S33`, then 422 with the N-05 issue | `test_f05_ac2_invalid_value` | `{"op":"set_field","line_no":1,"field":"purchasing_org","value":"S33"}` | `422`, detail starts with `Value "S33" is not valid for Purchasing Org.`; value unchanged `3300` |
| AC-F05-3 | Given the golden result, when `add_line SL create` then `remove_line 1`, then line numbering is stable | `test_f05_ac3_add_remove` | two PATCH calls | after add: 3 lines, `line_items[2].line_no == 3`, `doc_type == "SL"`, all 8 SL fields `missing`; after remove: lines `[2, 3]` |
| AC-F05-4 | Given the golden result, when exported as CSV and JSON, then the PRD columns and values | `test_f05_ac4_export` | — | CSV header equals `EXPORT_COLUMNS` joined by `,`; row 1 equals the §5 example row; JSON `line_items[0]["amount"] == "7000"`, `["plant"] is None`, `request_type == "update_pir"`; `Content-Disposition` contains `sco_request_` |

Integration / evaluation checks (run by a human in dev): in the dev app API, `PATCH` plant on the golden session, then download CSV and open it in Excel: 2 rows, 18 columns, Plant `3300` on line 1 only.

#### 9. Build-ready checklist (Planner self-check)

- [x] Every related feature (this set or earlier sets) is listed in §2 with the exact names this feature uses
- [x] Every path, table, column, API, agent and config key exists in the TSD, in §2, or earlier in this feature
- [x] Every join is written out in §4 (tables, type, condition, filters, expected result)
- [x] Every step is exact; SQL given for non-trivial logic; all constants have values
- [x] Every acceptance criterion has a test with literal fixture data and expected output
- [x] Edge cases cover empty, invalid, not-found and permission cases where relevant
- [x] No open words (e.g., such as, appropriate, as needed, TBD, etc., choose, decide)

**Out of scope for this feature:** Excel (`.xlsx`) export; SAP upload template layout; sending anywhere; bulk edits in one
call (one op per request); edit history.

**How a human tests it:** 1) `PATCH` plant `3300` on line 1 of the golden session. 2) `GET export?format=csv` and open it. 3) `PATCH` `purchasing_org` `S33` → 422 text.

---

### v2/F-06 — Build the frontend shell and SCR-01 chat pane

| Field | Value |
|---|---|
| Module / layer | `frontend` — `frontend/src/main.tsx`, `App.tsx`, `api.ts`, `types.ts`, `index.css`, `pages/RequestWorkspace.tsx`, `components/ChatPane.tsx`, `Composer.tsx`, `AttachmentCard.tsx`, `RequestTypeChip.tsx` (TSD §4) |
| Type | app page |
| Size | M |
| Depends on / related to | v2/F-02, v2/F-03 (depends on) |
| PRD refs | PRD-SCO-001 US-1, US-2, US-5, §7 (5 s), §9 |
| TSD refs | §4 screens SCR-01; §6.1 API-01 … API-05; §2.4 RF-01 steps 13-15; `plan/wireframe.html` SCR-01 |
| Standards applied | skill:ui_ux_design §2 (desktop 1440 × 900), §3 (tokens), §4 (layout), §5 (review / approve archetype), §6 (states), §7, §8, §9, §10 |

#### 1. Context

SCR-01 is the one screen stewards live in: chat with attachment previews on the left (40 %), request type and line
items on the right (60 %). This feature builds the shell, the left pane with composer, uploads, messages, the request
type chip, and the states (empty, uploading, extracting, failed, session ended). The right pane table follows in v2/F-07.

#### 2. Related features — context from earlier work

| Feature | Set | Relationship | What it built that this feature uses (exact names) | Status |
|---|---|---|---|---|
| v2/F-01 | v2 | depends on | `POST /api/sessions` → `{session_id}`; `GET /api/sessions/{id}` → `SessionView` (`messages[]`, `attachments[]` with `pages[].image_url`, `result`, `extraction_status`, `error`, `pending_request_type`); `DELETE` | To do |
| v2/F-02 | v2 | depends on | `POST /api/sessions/{id}/attachments` multipart `file` → `AttachmentView`; error details (422 / 413 / 503 texts) | To do |
| v2/F-03 | v2 | depends on | `POST /api/sessions/{id}/messages` `{text, attachment_ids}` → `202 MessageAccepted`; assistant messages with `changed_fields`, `clarification`; `extraction_status` values `idle / extracting / ready / failed` | To do |
| v1/F-01 | v1 | uses | `frontend/package.json`, `frontend/tailwind.config.ts` with the `asm.*` tokens; `REQUEST_TYPE_LABELS` (copied into `types.ts`) | Done |

**Rules carried over from those features:** error texts are shown as returned by the API (`detail`), never rephrased (v2/F-02, v2/F-03).

#### 3. Files

| Action | Path | Purpose |
|---|---|---|
| create | `SCO-001/frontend/index.html`, `vite.config.ts`, `tsconfig.json`, `postcss.config.js`, `src/index.css` | Vite app; Tailwind with `asm.*` tokens; font stack `Inter, system-ui, sans-serif`; shared classes `btn-primary`, `btn-outline`, `btn-ghost`, `card`, `chip-ok`, `chip-warn`, `chip-err`, `chip-mute` |
| create | `SCO-001/frontend/src/main.tsx`, `src/App.tsx` | mount; `App` creates a session on load (`POST /api/sessions`) and renders `RequestWorkspace` |
| create | `SCO-001/frontend/src/api.ts` | typed client for API-01 … API-08 (`createSession`, `getSession`, `uploadAttachment`, `sendMessage`, `patchResult`, `exportUrl`, `deleteSession`) |
| create | `SCO-001/frontend/src/types.ts` | TypeScript mirrors of `SessionView`, `Message`, `AttachmentView`, `Result`, `LineItem`, `FieldValue`, `Source`; `REQUEST_TYPE_LABELS`, `FIELD_LABELS`, `PIR_FIELDS`, `SL_FIELDS` |
| create | `SCO-001/frontend/src/pages/RequestWorkspace.tsx` | SCR-01 layout; polling of `GET /api/sessions/{id}` every 2000 ms while `extraction_status === "extracting"`; `selectedSource` state (used by v2/F-08) |
| create | `SCO-001/frontend/src/components/ChatPane.tsx`, `Composer.tsx`, `AttachmentCard.tsx`, `RequestTypeChip.tsx` | left pane |
| create | `SCO-001/frontend/src/components/RightPanePlaceholder.tsx` | right pane until v2/F-07 (empty state text) — replaced in v2/F-07 |
| modify | `SCO-001/pyproject.toml` | none — frontend build output goes to `backend/static/` via `vite build --outDir ../backend/static`; add to `README.md` "Run locally": `cd frontend && npm ci && npm run build` |
| modify | `SCO-001/README.md` | build steps only |

No other files may be created or changed.

#### 4. Data

| Table (TSD §5.2 ID) | Columns read | Columns written | Write mode |
|---|---|---|---|
| — | — | — | — |

**Joins (this feature):** none.

#### 5. Interfaces

**API (TSD §6.1):** consumes API-01, API-02, API-03, API-04, API-05, API-08 as listed in §2.

**Components added by this feature (props):**

```ts
RequestWorkspace()                                   // owns session state, polling, selectedSource
ChatPane({ messages, attachments, selectedSource, onOpenAttachment })
Composer({ disabled, onSend(text, attachmentIds), onUpload(file) })     // textarea + "Attach files" + "Send"
AttachmentCard({ attachment, onOpen(page_no) })      // thumbnail of page 1 (image_url), name, page count, chip: Reading… / Read / Could not be read
RequestTypeChip({ requestType, status })             // label from REQUEST_TYPE_LABELS; chip-mute while idle; chip-ok when set; chip-warn for not_pir_sl; "Corrected" tag when corrected
```

| Input | Output |
|---|---|
| App load | `POST /api/sessions`; header `ASM · PIR / SL request chat`; empty state in chat `Type the request and attach the quotation (PDF, PNG or JPG). Then press Send.`; right pane empty state `The request type and line items appear here after you send.` |
| Upload golden PDF | card `BE25112601_RAIL-DIN 35MM X 7.5MM.pdf · 1 page · Reading…` → `Read` |
| Send golden text | user bubble `M1`; chip `Update PIR` within 5 s; right pane skeleton rows `Reading the request and the quotation…`; after `ready` the assistant bubble `Found 2 line items.` |

#### 6. Implementation steps

1. Tailwind config: `theme.extend.colors.asm` from `tailwind.config.ts` (v1/F-01); `index.css` component classes per skill `ui_ux_design` §10: `.btn-primary` (`bg-asm-blue text-white hover:bg-asm-navy rounded-lg h-11 px-4 focus:ring-[3px] focus:ring-asm-blue`), `.btn-outline`, `.btn-ghost`, `.card` (`bg-white rounded-xl shadow-card border border-asm-line`), chips (`rounded-full text-sm px-2 py-0.5` with emerald-50/emerald-700, amber-50/amber-700, red-50/red-700, asm-mist/asm-ink).
2. Layout (desktop 1440 × 900, min 1280): header `h-14 bg-asm-navy text-white` with the ASM wordmark text `ASM`, app name `PIR / SL request chat`, user e-mail from `window.__USER__` (injected by the backend into `index.html` as the `X-Forwarded-Email` value) and a `New request` ghost button (calls `DELETE` then `POST /api/sessions`); below: `grid grid-cols-[2fr_3fr] h-[calc(100vh-56px)]`; left column `ChatPane` + `Composer` (sticky bottom); right column `RequestTypeChip` row + table area.
3. `Composer`: textarea (`min-h-24`, Shift+Enter newline, Enter sends), hidden `<input type=file multiple accept=".pdf,.png,.jpg,.jpeg">`, drop zone over the chat pane, `Attach files` outline button, `Send` primary button (disabled while a message is in flight or when text is empty and no new attachments). Uploads start on selection (one `POST` per file, in order); cards show `Reading…` until the response; a failed upload shows the API `detail` text under the composer in `text-red-700` with a `Dismiss` ghost button; the text typed is kept.
4. Send: `POST messages` with `attachment_ids` of attachments not yet referenced by a message; on `202` append the user message and set chip from `request_type`; start polling when `extraction_status === "extracting"`; on `503` show the detail text under the composer and keep the text.
5. Polling: `getSession` every 2000 ms; stop on `ready` / `failed`; after 120 s of `extracting` show the inline text `Still working on a large request…` and keep polling. On `404` show the full-pane state `Your session ended; start a new request` with a `New request` button (R-08).
6. States of SCR-01 (skill §6): empty (both panes), loading (skeleton rows right, `Reading…` chips left), error (API detail under the composer; right pane card `The line items could not be extracted: <reason>` with `Send again` ghost button that re-posts the last text with no attachments), not a PIR/SL request (chip `Not a PIR/SL request` in `chip-warn`, assistant bubble, right pane text `Nothing was extracted.`), success toast `Request type: Update PIR` is NOT shown — the chip is the confirmation (skill §7: remove one accessory).
7. Accessibility: visible focus ring, labels on inputs, `aria-live="polite"` on the assistant message list, keyboard-only operation.
8. `npm run build` outputs to `backend/static/`; `backend/main.py` already serves it (v2/F-01).

Constants: `POLL_INTERVAL_MS = 2000`, `SLOW_NOTICE_MS = 120000` (defined in `frontend/src/pages/RequestWorkspace.tsx`).

#### 7. Edge cases and errors

| Case | Input | Expected behaviour |
|---|---|---|
| Send with empty text and no files | Enter | button disabled; nothing sent |
| Unsupported file | `.xlsx` dropped | inline text `Only PDF, PNG and JPG files are supported`; other files continue |
| 11th file | drop 11 files | the 11th shows `A request may have at most 10 attachments` |
| Session expired | `GET` → 404 | `Your session ended; start a new request` |
| Long message | 20001 chars | counter turns red at 20000; Send disabled with text `A message may have at most 20000 characters` |
| Many messages | 30 messages | chat scrolls; newest at the bottom; auto-scroll only when the user is at the bottom |
| Reduced motion | OS setting | no skeleton shimmer animation |

#### 8. Acceptance criteria and tests

Test file: none (D-13) · behaviour checked by the human tests below and the API integration tests of v2/F-03.

| AC ID | Given / When / Then | Test name | Fixture data | Expected |
|---|---|---|---|---|
| AC-F06-1 | Given the dev app, when opened, then SCR-01 renders the empty state with header, composer and both pane texts | manual `SCR-01 empty` | — | header `PIR / SL request chat`; texts of §5 row 1; `Send` disabled |
| AC-F06-2 | Given the golden PDF is dropped, when upload finishes, then the card shows name, `1 page`, chip `Read` and a thumbnail | manual `SCR-01 upload` | SRC-01 `GE-001` PDF | card as §5 row 2 |
| AC-F06-3 | Given the golden text is sent, when 5 s pass, then the chip shows `Update PIR` and the right pane shows skeleton rows; when ready, the assistant bubble `Found 2 line items.` | manual `SCR-01 send` | `golden_message_M1.txt` | as §5 row 3 |
| AC-F06-4 | Given an `.xlsx` is dropped, when rejected, then the API text shows inline and the typed text is kept | manual `SCR-01 error` | any `.xlsx` | text `Only PDF, PNG and JPG files are supported`; textarea content unchanged |

Integration / evaluation checks (run by a human in dev): `npm run build && databricks bundle deploy -t dev`; open the app URL; walk AC-1 … AC-4.

#### 9. Build-ready checklist (Planner self-check)

- [x] Every related feature (this set or earlier sets) is listed in §2 with the exact names this feature uses
- [x] Every path, table, column, API, agent and config key exists in the TSD, in §2, or earlier in this feature
- [x] Every join is written out in §4 (tables, type, condition, filters, expected result)
- [x] Every step is exact; SQL given for non-trivial logic; all constants have values
- [x] Every acceptance criterion has a test with literal fixture data and expected output
- [x] Edge cases cover empty, invalid, not-found and permission cases where relevant
- [x] No open words (e.g., such as, appropriate, as needed, TBD, etc., choose, decide)

**Out of scope for this feature:** the line-item table (v2/F-07), the viewer and highlights (v2/F-08), tablet / mobile
layout, dark mode, left navigation (one screen only), markdown rendering of messages (plain text with preserved line
breaks), a session list.

**How a human tests it:** 1) Open the dev app at 1440 × 900 and check the empty state. 2) Drop the golden PDF and send the golden text; stopwatch the chip (< 5 s). 3) Drop an `.xlsx` and read the inline text.

---

### v2/F-07 — Build the line-item review table, direct edit and SCR-03 export

| Field | Value |
|---|---|
| Module / layer | `frontend` — `frontend/src/components/LineItemTable.tsx`, `FieldCell.tsx`, `ExportDialog.tsx`; modify `pages/RequestWorkspace.tsx` (TSD §4) |
| Type | app page |
| Size | M |
| Depends on / related to | v2/F-06 (depends on), v2/F-05 (depends on) |
| PRD refs | PRD-SCO-001 US-3, US-4, US-8, US-9 (direct edit), US-10 |
| TSD refs | §4 SCR-01 right pane, SCR-03; §6.1 API-06, API-07; §5.2 `FieldValue.status`; `plan/wireframe.html` SCR-01, SCR-03 |
| Standards applied | skill:ui_ux_design §3 (status colour + word), §5 (review / approve), §6, §7, §8, §9 |

#### 1. Context

The right pane is where the steward decides. Each line is a row group with the PRD §4 fields in PRD order; each cell
shows the value and its status word (Found, Missing, Conflict, Corrected, Rejected) with the matching chip colour and
an icon, is editable in place, and has an evidence button (wired in v2/F-08). The export dialog (SCR-03) offers JSON or
CSV, copy or download.

#### 2. Related features — context from earlier work

| Feature | Set | Relationship | What it built that this feature uses (exact names) | Status |
|---|---|---|---|---|
| v2/F-06 | v2 | depends on | `RequestWorkspace` state (`session`, `selectedSource`, `setSelectedSource`), `RightPanePlaceholder` to replace, `types.ts` (`Result`, `LineItem`, `FieldValue`, `FIELD_LABELS`, `PIR_FIELDS`, `SL_FIELDS`), `api.ts` (`patchResult`, `exportUrl`), classes `chip-ok/warn/err/mute`, `btn-*` | To do |
| v2/F-05 | v2 | depends on | `PATCH /api/sessions/{id}/result` ops and 422 texts; `GET .../export?format=json|csv` | To do |
| v1/F-07 | v1 | uses | statuses `found / missing / conflict / corrected / rejected`; `derivation computed` with `computation`; `candidates[]` with `value_raw`, `issue`, `source` | Done |

**Rules carried over from those features:** display labels are `FIELD_LABELS` (PRD §4), including the PRD's mapping `material → Vendor Material No.`, `vendor_material_no → Material` (TSD Q-03); `lead_time_days` is shown as `<days> d (<weeks> wk)` (N-07).

#### 3. Files

| Action | Path | Purpose |
|---|---|---|
| create | `SCO-001/frontend/src/components/LineItemTable.tsx` | rows per line item, group header `Line 1 · PIR · Update`, actions `Remove line`, footer `Add PIR line` / `Add SL line` |
| create | `SCO-001/frontend/src/components/FieldCell.tsx` | value, status chip, inline edit, evidence button, candidates list for conflicts |
| create | `SCO-001/frontend/src/components/ExportDialog.tsx` | SCR-03 |
| create | `SCO-001/frontend/src/components/RequestTypeSelect.tsx` | change the request type (direct edit) |
| modify | `SCO-001/frontend/src/pages/RequestWorkspace.tsx` | replace `RightPanePlaceholder` with the table, export button, request type select |
| delete | `SCO-001/frontend/src/components/RightPanePlaceholder.tsx` | replaced |

No other files may be created or changed.

#### 4. Data

| Table (TSD §5.2 ID) | Columns read | Columns written | Write mode |
|---|---|---|---|
| — | — | — | — |

**Joins (this feature):** none.

#### 5. Interfaces

**API (TSD §6.1):** consumes API-06 (`set_field`, `add_line`, `remove_line`, `set_request_type`) and API-07.

**Components added by this feature (props):**

```ts
LineItemTable({ result, onPatch(op), onShowSource(source[]) })
FieldCell({ lineNo, field, value: FieldValue, docType, onPatch, onShowSource })
RequestTypeSelect({ value, corrected, onChange })
ExportDialog({ open, sessionId, onClose })           // radio JSON / CSV; buttons "Copy", "Download"; preview of the first 5 lines
```

Cell rendering rules:

| status | chip class | icon (Lucide) | cell text |
|---|---|---|---|
| `found` | none (plain text) | — | value; `computed` values get a suffix badge `calc` with tooltip `computation` |
| `missing` | `chip-warn` | `alert-circle` | `Missing` (+ tooltip `issue` when present) |
| `conflict` | `chip-warn` | `git-compare` | selected value + `Conflict`; below: one row per candidate `value_raw · <source kind>` with a `Use` ghost button → `set_field` |
| `corrected` | `chip-ok` | `check` | value + `Corrected` |
| `rejected` | `chip-err` | `x-circle` | `Missing` + tooltip `issue` (value stays empty) |

| Input | Output |
|---|---|
| golden ready result | header `Update PIR` select; `2 line items`; group `Line 1 · PIR · Update` with 14 cells: Supplier `18570`, Vendor Material No. `1038-967-34`, Material `RAIL-DIN 35MM X 7.5MM X 450MM LG`, Plant `Missing`, Purchasing Org. `3300`, C/R. of Origin `KR Conflict` with candidates `KR · message`, `DE · attachment p.1`, Pl. Deliv. Time `7 d (1.0 wk)`, Standard Qty `1`, Amount `7000`, Cond. Currency `KRW`, Pricing Unit `1`, Unit of Measure `EA`, Valid-From Date `2025-11-26`, Valid To Date `Missing` |
| double-click Plant on line 1, type `3300`, Enter | `PATCH set_field` → cell `3300 Corrected` |
| Export → CSV → Download | file `sco_request_<sid8>.csv` |

#### 6. Implementation steps

1. `LineItemTable`: one `<section>` per line item (`card` on `asm-paper`), header row with `Line <n> · <doc_type> · <Action>` and a `Remove line` ghost button (confirm inline: `Remove line 2? [Remove] [Keep]`); body: a 2-column definition grid (label left in `text-asm-muted`, cell right) with the fields in `PIR_FIELDS` / `SL_FIELDS` order; footer buttons `Add PIR line`, `Add SL line` (`add_line` with `action` = the current request type's action: `create` for `create_*`, `update` for `update_*`, `create` otherwise).
2. `FieldCell`: rendering per the table in §5; numbers right-aligned with `tabular-nums`; IDs (`material`, `supplier` codes) in `font-mono`; inline edit on double-click or Enter when focused: input pre-filled with the value, Enter → `onPatch({op: "set_field", ...})`, Escape cancels, empty input → `value: null`; 422 → red text under the cell with the API detail, value reverted; evidence button `Show source` (icon `locate`) visible when `sources.length > 0` → `onShowSource(value.sources)` (wired in v2/F-08; until then it sets `selectedSource` only).
3. `RequestTypeSelect`: `<select>` with `REQUEST_TYPE_LABELS`; change → `set_request_type`; shows `Corrected` chip when `corrected`.
4. `ExportDialog`: modal (`card` with stronger shadow), title `Export reviewed line items`, radio `JSON` / `CSV`, preview `<pre>` of the first 5 lines fetched from API-07, `Copy` (clipboard; toast `Copied`), `Download` (`<a href={exportUrl} download>`), `Close`. Primary button `Download`.
5. Right pane header: `RequestTypeSelect`, line count `2 line items`, `Export` primary button (disabled until `ready`). One primary action per view: `Export` on the right, `Send` on the left (skill §4: the two panes are two views side by side — recorded as a design assumption in TSD D-01 context; the composer's Send is the chat's primary action).
6. States: `idle` → placeholder text; `extracting` → 2 skeleton line cards; `ready` with 0 lines → `No line items were found. Add a line or send more details.`; `failed` → error card (v2/F-06).

Constants: `PREVIEW_LINES = 5` (defined in `frontend/src/components/ExportDialog.tsx`).

#### 7. Edge cases and errors

| Case | Input | Expected behaviour |
|---|---|---|
| 50 line items | large request | page scrolls; group headers sticky; no virtualisation |
| Long description | 120-char `vendor_material_no` | truncated with tooltip (skill §6) |
| Edit while extracting | double-click during `extracting` | editing allowed; the merge keeps corrected cells (M-03) |
| 422 on edit | `S33` | API detail shown under the cell; value reverted |
| Export with no result | button disabled | tooltip `Send the request first` |
| Clipboard blocked | `navigator.clipboard` rejects | text `Copy failed; use Download` |
| Remove the only line | confirm | empty state text; export header-only |

#### 8. Acceptance criteria and tests

Test file: none (D-13) · behaviour checked by the human tests below and v2/F-05 API tests.

| AC ID | Given / When / Then | Test name | Fixture data | Expected |
|---|---|---|---|---|
| AC-F07-1 | Given the golden result, when rendered, then both lines show the PRD §6 values and statuses | manual `SCR-01 table` | golden flow | cells as §5 row 1; Plant `Missing` with warning chip; C/R. of Origin `Conflict` with two candidates |
| AC-F07-2 | Given line 1 Plant, when edited to `3300`, then the cell shows `3300 Corrected`; when edited to `12` then the API text `Value "12" is not valid for Plant: ...` appears and the cell reverts | manual `SCR-01 edit` | — | as stated |
| AC-F07-3 | Given the conflict cell, when `Use` on `DE` is clicked, then the cell shows `DE Corrected` | manual `SCR-01 conflict` | — | value `DE`, status `Corrected`, candidates still listed |
| AC-F07-4 | Given a ready result, when Export → CSV → Download, then a CSV with 18 columns and 2 rows downloads; Copy → `Copied` toast | manual `SCR-03` | — | file `sco_request_<sid8>.csv` |

Integration / evaluation checks (run by a human in dev): walk AC-1 … AC-4 in the deployed app.

#### 9. Build-ready checklist (Planner self-check)

- [x] Every related feature (this set or earlier sets) is listed in §2 with the exact names this feature uses
- [x] Every path, table, column, API, agent and config key exists in the TSD, in §2, or earlier in this feature
- [x] Every join is written out in §4 (tables, type, condition, filters, expected result)
- [x] Every step is exact; SQL given for non-trivial logic; all constants have values
- [x] Every acceptance criterion has a test with literal fixture data and expected output
- [x] Edge cases cover empty, invalid, not-found and permission cases where relevant
- [x] No open words (e.g., such as, appropriate, as needed, TBD, etc., choose, decide)

**Out of scope for this feature:** evidence navigation and the viewer (v2/F-08); column sorting or filtering; bulk edit;
keyboard shortcuts beyond Enter / Escape; SAP template layout; a wide spreadsheet-style table (the PRD's 14 fields per
line read better as one card per line — design assumption, TSD D-01).

**How a human tests it:** 1) Golden flow, compare the two line cards with PRD §6. 2) Edit Plant to `3300`, then to `12`. 3) Export CSV and open it.

---

### v2/F-08 — Build evidence navigation and SCR-02 attachment viewer

| Field | Value |
|---|---|
| Module / layer | `frontend` — `frontend/src/components/AttachmentViewer.tsx`, `BoundingBoxOverlay.tsx`, `SourcePopover.tsx`; modify `ChatPane.tsx`, `FieldCell.tsx`, `RequestWorkspace.tsx` (TSD §4) |
| Type | app page |
| Size | M |
| Depends on / related to | v2/F-07 (depends on) |
| PRD refs | PRD-SCO-001 US-6, US-7, US-8 (both sources boxed), US-9 (chat correction as source), §7 (zoom) |
| TSD refs | §4 SCR-02; §5.2 `Source` (fractions, offsets); §6.1 API-03; §7 C-04; §9 bounding boxes; `plan/wireframe.html` SCR-02 |
| Standards applied | skill:ui_ux_design §3 (`asm.warn` as fill, never meaning by colour alone), §5 (detail archetype), §6, §9 |

#### 1. Context

Clicking a value must show why the AI chose it: the chat scrolls to the message and highlights the exact span, or the
viewer opens the attachment at the page with a yellow box around the text. Several sources are all shown; computed values
show their computation and box the numbers. Because boxes are fractions of the rendered PNG, they stay aligned at any zoom.

#### 2. Related features — context from earlier work

| Feature | Set | Relationship | What it built that this feature uses (exact names) | Status |
|---|---|---|---|---|
| v2/F-07 | v2 | depends on | `FieldCell` `Show source` button calling `onShowSource(sources)`; `RequestWorkspace.selectedSource: Source[] | null` | To do |
| v2/F-06 | v2 | depends on | `ChatPane` message list (bubbles with `id="msg-M1"`), `AttachmentCard.onOpen(page_no)`, `api.ts` image URLs (`pages[].image_url`), `attachments[].pages[].width_px/height_px` | To do |
| v2/F-02 | v2 | uses | `GET /api/sessions/{id}/attachments/{aid}/pages/{n}.png` | To do |
| v1/F-04 | v1 | uses | `Source` shape: `kind message` with `start`, `end` in `Message.text`; `kind attachment` with `page_no`, `bbox` fractions `(x0, y0, x1, y1)`; `kind user_edit` | Done |

**Rules carried over from those features:** bbox values are fractions of the page PNG (v1/F-04 D-03); chat corrections have `kind message` with the whole instruction as span (v2/F-04 M-02).

#### 3. Files

| Action | Path | Purpose |
|---|---|---|
| create | `SCO-001/frontend/src/components/AttachmentViewer.tsx` | SCR-02: page image, page nav, zoom 50 / 100 / 200 %, overlay |
| create | `SCO-001/frontend/src/components/BoundingBoxOverlay.tsx` | absolutely positioned boxes in % of the image box |
| create | `SCO-001/frontend/src/components/SourcePopover.tsx` | list of sources for a value with `Go to` buttons; computation text |
| modify | `SCO-001/frontend/src/components/ChatPane.tsx` | highlight spans (`<mark>`) in the selected message, scroll into view |
| modify | `SCO-001/frontend/src/components/FieldCell.tsx` | `Show source` opens `SourcePopover` |
| modify | `SCO-001/frontend/src/pages/RequestWorkspace.tsx` | `viewer` state `{attachmentId, pageNo, boxes}`; render `AttachmentViewer` in the left pane when open |

No other files may be created or changed.

#### 4. Data

| Table (TSD §5.2 ID) | Columns read | Columns written | Write mode |
|---|---|---|---|
| SRC-02 page PNGs via API-03 | image bytes | — | — |

**Joins (this feature):** none.

#### 5. Interfaces

**API (TSD §6.1):** consumes API-03.

**Components added by this feature (props):**

```ts
SourcePopover({ value: FieldValue, onGo(source) })  // rows: "Message M1 — '7,000'", "BE25112601… page 1 — '7,000'", "Edited by the steward"; computed: line "Calculated: 1 week × 7"
AttachmentViewer({ attachment, pageNo, boxes: Source[], zoom, onClose, onPage(n), onZoom(z) })
BoundingBoxOverlay({ boxes: Source[], width, height })   // each box: left = x0*100%, top = y0*100%, width = (x1-x0)*100%, height = (y1-y0)*100%; border 2px asm.warn; fill asm.warn at 25% opacity; label = text
```

| Input | Output |
|---|---|
| click `Show source` on Amount line 1 (sources: M1 span, A1 p1 bbox) | popover with 2 rows; `Go to` on row 1 scrolls the chat to `M1` and wraps `7,000` in `<mark class="bg-amber-200 ring-2 ring-asm-warn">`; `Go to` on row 2 opens the viewer on A1 page 1 with one yellow box labelled `7,000` |
| click `Show source` on C/R. of Origin (conflict) | popover rows `KR — Message M1`, `DE — BE25112601… page 1`; `Show all` boxes both: the chat span and the viewer box |
| click `Show source` on Pl. Deliv. Time (computed candidate from A1) | row `Calculated: 1 week × 7` and the box around `1 week` |
| zoom 200 % | image doubles; boxes stay on the text (percent positioning) |

#### 6. Implementation steps

1. `BoundingBoxOverlay`: wrapper `relative inline-block`; `<img>` with `width = zoom * width_px / 2` CSS px (so 100 % shows a 150 dpi page at 72 dpi-equivalent width 620 px for A4; 200 % = 1240 px) and the overlay `absolute inset-0` with boxes in percentages per §5; label `text-xs bg-asm-warn text-asm-ink px-1 rounded-sm` above each box; `aria-label="Source: <text>"`.
2. `AttachmentViewer`: header `<file_name> · page <n> of <total>`, buttons `Previous`, `Next`, zoom segmented control `50 % / 100 % / 200 %`, `Close`; body scrollable; on open scroll the first box into the centre; `parse_status failed` or a page with no elements → notice `This page could not be read; the values here were typed or come from the message.`; loading state skeleton until the image `onload`.
3. `ChatPane`: when `selectedSource` contains message sources, render that message's text with `<mark>` around each `[start, end)` span (sorted, non-overlapping) and `scrollIntoView({block: "center"})`; the mark fades after 6 s to `bg-amber-100` but stays until another source is selected.
4. `SourcePopover`: anchored to the cell; rows per source kind; `Show all` button when > 1 source: highlights all message spans and opens the viewer on the first attachment source with all boxes of that page; `user_edit` rows have no `Go to`.
5. `RequestWorkspace`: `viewer` state; when open, the left pane shows the viewer above the chat (chat shrinks to 40 % height) so message and page are visible together (US-5); `AttachmentCard.onOpen(page)` opens the viewer without boxes.
6. Keyboard: `Escape` closes the viewer; `ArrowLeft/Right` page; `+ / -` zoom.

Constants: `ZOOM_LEVELS = [0.5, 1, 2]`, `MARK_FADE_MS = 6000` (defined in `frontend/src/components/AttachmentViewer.tsx` and `ChatPane.tsx`).

#### 7. Edge cases and errors

| Case | Input | Expected behaviour |
|---|---|---|
| Source message scrolled off | M1 far above | smooth scroll to centre, mark visible |
| Page image 404 | file deleted | viewer text `The page image is no longer available` |
| Several boxes on one page | 3 sources | all drawn; labels do not overlap each other by more than their height (stack labels downward when y0 within 2 %) |
| Box at the page edge | `x1 = 1.0` | clamped inside the image |
| Value without sources | `missing` cell | `Show source` hidden |
| Corrected via chat | source `M2` span | chat highlights the whole correction message |
| Window resize | 1280 px | layout keeps 2fr / 3fr; viewer zoom unchanged; boxes stay aligned (percent) |

#### 8. Acceptance criteria and tests

Test file: none (D-13) · behaviour checked by the human tests below; alignment is proven by construction (percent positioning) and by TSD §9 manual check.

| AC ID | Given / When / Then | Test name | Fixture data | Expected |
|---|---|---|---|---|
| AC-F08-1 | Given the golden result, when `Show source` → `Go to` on Amount line 1 message source, then the chat scrolls to M1 and `7,000` is marked | manual `SCR-02 message source` | golden flow | mark around `7,000` in the table row of M1 |
| AC-F08-2 | Given the same cell, when `Go to` on the attachment source, then the viewer opens at page 1 with one yellow box containing the price; at 50 %, 100 % and 200 % the box stays on the text | manual `SCR-02 attachment source` | golden PDF | as stated (PRD §7) |
| AC-F08-3 | Given the C/R. of Origin conflict, when `Show all`, then `KR` is marked in M1 and `DE` is boxed in the PDF | manual `SCR-02 conflict` | — | both visible at once (US-8) |
| AC-F08-4 | Given a chat correction `line 2 amount is 8000`, when `Show source` on line 2 Amount, then the row `Message M2` and `Go to` highlights that message | manual `SCR-02 correction source` | v2/F-04 flow | whole M2 text marked |

Integration / evaluation checks (run by a human in dev): walk AC-1 … AC-4; also run `evals/run_eval.py` unchanged to confirm `source_contains_value >= 0.90` still holds (no backend change in this feature).

#### 9. Build-ready checklist (Planner self-check)

- [x] Every related feature (this set or earlier sets) is listed in §2 with the exact names this feature uses
- [x] Every path, table, column, API, agent and config key exists in the TSD, in §2, or earlier in this feature
- [x] Every join is written out in §4 (tables, type, condition, filters, expected result)
- [x] Every step is exact; SQL given for non-trivial logic; all constants have values
- [x] Every acceptance criterion has a test with literal fixture data and expected output
- [x] Edge cases cover empty, invalid, not-found and permission cases where relevant
- [x] No open words (e.g., such as, appropriate, as needed, TBD, etc., choose, decide)

**Out of scope for this feature:** a PDF.js viewer (the app shows its own PNGs); drawing or moving boxes by the user; text
selection inside the page image; OCR correction; printing.

**How a human tests it:** 1) Golden flow; click `Show source` on Amount line 1 and follow both `Go to` rows. 2) Zoom to 50 % and 200 % and check the box stays on `7,000`. 3) Click `Show all` on C/R. of Origin.

---

## 5. Change log

| Date | Change | Features | Source (PRD / CR) | Approved by |
|---|---|---|---|---|
| 2026-11-26 | Initial set | all | PRD-SCO-001 v0.1 | |
