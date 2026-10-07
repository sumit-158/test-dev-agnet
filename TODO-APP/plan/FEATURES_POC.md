# Feature List — Team Todo (TODO-APP) — PoC

| Field | Value |
|---|---|
| PRD | PRD-TODO-001, version 1.0 |
| Stage | PoC |
| Status | Approved |
| Approved by / date | Sumit / 2026-10-07 |
| Planner model | Claude Opus 4.8 (system.ai.claude-opus-4-8) |

## 1. Solution Summary

**What will be built**: A storage layer for tasks (create/read/update/delete with per-owner access rules) and a
quick-add parser that turns one line of plain English into a title, due date and priority. The PoC is driven
from a notebook/API by the two developers — no UI — and proves the riskiest assumption: that one-line parsing
hits ≥ 90% accuracy on the golden set while CRUD works reliably.

| Component | Type | Why it is needed | Needed from stage |
|---|---|---|---|
| `tasks` table (`todo_dev.tasks`) | Data store | Holds the task records the app creates and reads (OUT-01, DS-01) | PoC |
| `task_store` module | Module / library (SQL + Python) | Deterministic CRUD and ownership rules — no AI needed (rubric: rules/SQL) | PoC |
| Quick-add parser (`ai_query` on the Foundation Model endpoint) | AI function | Single-step transform of one record (one line → structured fields); meets the quick-add need without an agent or ML model | PoC |
| Golden-set MLflow evaluation | Evaluation harness | Measures parse accuracy against §11B; this is the PoC exit gate (O-2 / LC-01) | PoC |

**Deliberately NOT included**:
- Any UI — PoC §11A explicitly excludes it; developers exercise the functions from a notebook/API.
- No ML model — no labelled history exists and free-text parsing with relative dates is better served by a Foundation Model via `ai_query` (rubric: ML only with labelled history on structured data).
- No agent — quick-add is a single-step transformation with no multi-step tool use, partial-information decisions or conversation, so an AI function is the simpler fit (rubric step 2 over step 3).
- No manual fallback form (G-04 / US-QA-03) — MVP; the PoC runs where the endpoint is available.
- No change history / `task_events` (US-AD-01, OUT-02) — MVP.
- No complete / reopen (US-TK-05) — MVP; `tasks.status` stays `open` in the PoC.
- No Databricks Asset Bundle / CI deploy (C-05) — MVP / Prod.
- No analytics events (§23) — MVP onward.

| Module | Folder | Responsibility | Interface other modules may use |
|---|---|---|---|
| `task_store` | `src/task_store` | CRUD on tasks and ownership enforcement | Python: `create_task(title, owner, due_date=None, priority="medium")`, `get_task(task_id)`, `list_tasks(owner=None)`, `update_task(task_id, owner, **fields)`, `delete_task(task_id, owner)`; table `todo_dev.tasks` (columns: `task_id`, `title`, `due_date`, `priority`, `status`, `owner`, `created_at`, `updated_at`) |
| `quick_add` | `src/quick_add` | Parse one line into structured fields | Python: `parse_quick_add(text, owner, today, tz="Asia/Kolkata") -> {title, due_date, priority, needs_title}` |

> **Storage decision (Q-03)**: use Lakebase Postgres database `todo_dev`, table `tasks`, per the PRD preference.
> D-02 is still *Requested* and could not be verified in this planning session (no Databricks tools available).
> If Lakebase is not provisioned when the Builder starts, fall back to a UC Delta table `todo_dev.tasks` with the
> same columns and function interface (D-02 fallback) — the `task_store` interface above is unchanged either way.

## 2. Stage Scope and Exit Criteria

| | This stage |
|---|---|
| Goal | Prove we can store tasks reliably and parse one-line input at ≥ 90% accuracy, run by developers via notebook/API |
| Data | Golden examples (§11B) + developer test tasks |
| In scope | Task storage with CRUD and ownership (F-01, F-02); quick-add parsing (F-02 of PRD §11) with golden-set evaluation (US-TK-01..04, US-QA-01, US-QA-02) |
| Out of scope | UI, "my/team" views, complete/reopen, change history, manual fallback, bundle/CI deploy, analytics events, assigning to others |

| ID | Exit criterion (stage is done when…) | How it is checked |
|---|---|---|
| EX-1 | Create, read, update and delete all work on `todo_dev.tasks` | Tests for F-01, F-02 pass |
| EX-2 | A user cannot edit or delete a task owned by someone else | Test AC-F02-3 passes |
| EX-3 | Quick-add parses the golden set with ≥ 90% all-fields-correct accuracy | MLflow evaluation score ≥ 0.90 (AC-F04-2) |
| EX-4 | A line with no task text (GX-10) creates no task and asks for a title | Test AC-F03-2 passes |

**Guardrails that apply in this stage**:
- G-01 (human-in-the-loop): `parse_quick_add` only returns fields; it never writes a task. The developer reviews the parse and then calls `create_task` — parsing and saving are deliberately separate functions.
- G-02 (no empty title): enforced in `parse_quick_add` (returns `needs_title=true`, no save) and in `create_task` (title is not-null / rejected if blank).
- G-03 (input limit): `parse_quick_add` rejects input over 300 characters before any model call, and the input is used only for parsing.
- G-04 (fallback) does **not** apply in the PoC — MVP (US-QA-03).

## 3. Build Order (status board)

| # | ID | Feature | Module | Depends on | Status | PR |
|---|---|---|---|---|---|---|
| 1 | F-01 | Task store — schema, create & read | `task_store` | — | To do | |
| 2 | F-02 | Task store — edit, delete & ownership | `task_store` | F-01 | To do | |
| 3 | F-03 | Quick-add parsing (AI function) | `quick_add` | — | To do | |
| 4 | F-04 | Quick-add golden-set evaluation | `quick_add` | F-03 | To do | |

Status values: To do → In progress → In review → Human testing → Done (also Blocked, Dropped).
Only a human sets Done.

## 4. Features

### F-01 — Task store: schema, create & read

| Field | Value |
|---|---|
| Module | `task_store` |
| Type | Pipeline / Job (data store + Python) |
| Size | M |
| Depends on | — |
| PRD reference | US-TK-01; §8A DS-01 / OUT-01; §16A security |

**What to build**: Create the `todo_dev.tasks` table with columns `task_id` (generated id, PK), `title` (text,
not null), `due_date` (date, nullable), `priority` (text in {low, medium, high}, default `medium`), `status`
(text in {open, done}, default `open`), `owner` (text, user email), `created_at` (timestamp), `updated_at`
(timestamp). In `src/task_store`, implement `create_task(title, owner, due_date=None, priority="medium")`,
`get_task(task_id)` and `list_tasks(owner=None)`. This is the walking skeleton — store a task and read it back.

**Acceptance criteria**:

| ID | Given / When / Then | Checked by |
|---|---|---|
| AC-F01-1 | Given a title and owner, when `create_task` is called, then a row is stored with a generated `task_id`, `status="open"`, `created_at` set, and `priority="medium"` when not supplied | Test |
| AC-F01-2 | Given a blank/empty title, when `create_task` is called, then it is rejected and no row is written (G-02) | Test |
| AC-F01-3 | Given a stored `task_id`, when `get_task` is called, then it returns the stored title, due date, priority, status and owner | Test |
| AC-F01-4 | Given tasks owned by two users, when `list_tasks(owner=X)` is called, then only X's tasks are returned | SQL query / Test |

**Out of scope for this feature**: update, delete, ownership checks (F-02); complete/reopen; `task_events` history; any UI.

**How a human tests it**: In a dev notebook, call `create_task("Renew Databricks PAT", "me@asm.com")`, then
`get_task(<id>)` and confirm the fields; run `SELECT * FROM todo_dev.tasks` to see the row.

### F-02 — Task store: edit, delete & ownership

| Field | Value |
|---|---|
| Module | `task_store` |
| Type | Job (Python + SQL) |
| Size | S |
| Depends on | F-01 |
| PRD reference | US-TK-02, US-TK-03, US-TK-04; §16A security |

**What to build**: In `src/task_store`, implement `update_task(task_id, owner, **fields)` (title, due_date,
priority) and `delete_task(task_id, owner)`. Both check that `owner` matches the task's `owner`; a mismatch is
refused with no change. `update_task` sets `updated_at`.

**Acceptance criteria**:

| ID | Given / When / Then | Checked by |
|---|---|---|
| AC-F02-1 | Given a task I own, when `update_task` changes title, due date or priority, then the new value is stored and `updated_at` advances | Test |
| AC-F02-2 | Given a task I own, when `delete_task` is called, then `get_task` returns nothing and it is absent from `list_tasks` | Test |
| AC-F02-3 | Given a task owned by another user, when `update_task` or `delete_task` is called with my email, then the request is refused and the task is unchanged | Test |

**Out of scope for this feature**: complete/reopen (US-TK-05, MVP); recording change events; soft-delete / retention.

**How a human tests it**: In a dev notebook, create a task as `a@asm.com`, call `update_task` as `a@asm.com`
and confirm the change; then call `delete_task` as `b@asm.com` and confirm it is refused and the row remains.

### F-03 — Quick-add parsing (AI function)

| Field | Value |
|---|---|
| Module | `quick_add` |
| Type | Agent / AI function (`ai_query` on the Foundation Model endpoint) |
| Size | M |
| Depends on | — |
| PRD reference | US-QA-01, US-QA-02; §11B; G-01, G-02, G-03; D-03 |

**What to build**: In `src/quick_add`, implement `parse_quick_add(text, owner, today, tz="Asia/Kolkata")` that
calls the Foundation Model chat endpoint via `ai_query` (C-02) with a prompt carrying `today` and `tz`, and
returns `{title, due_date (ISO date or null), priority (low|medium|high), needs_title (bool)}`. Resolve relative
dates ("tomorrow", "next Monday", "end of month", "in N days", "fri"), absolute dates with no year, and ISO
dates, all relative to `today`. Map priority words/shorthand ("urgent"→high, "!low", "priority: HIGH",
default medium). The function returns fields only — it never writes a task (G-01).

**Acceptance criteria**:

| ID | Given / When / Then | Checked by |
|---|---|---|
| AC-F03-1 | Given representative lines GX-01, GX-04, GX-06, GX-07, GX-09, GX-12 with `today=2026-10-07`, when parsed, then title, due date and priority match §11B expectations (relative, "next Monday", "15 Oct", "end of month", "in 3 days", explicit labels) | Test |
| AC-F03-2 | Given a line with no task text (GX-10 "tomorrow"), when parsed, then `needs_title=true`, no fields are returned for save, and the caller is told to ask for a title (G-02) | Test |
| AC-F03-3 | Given input longer than 300 characters, when `parse_quick_add` is called, then it is rejected before any model call and used only for parsing (G-03) | Test |
| AC-F03-4 | Given any parse, when it returns, then `priority` is in {low, medium, high} (default medium) and `due_date` is an ISO date or null | Test |

**Out of scope for this feature**: the aggregate ≥90% metric (F-04); writing the task (F-01); manual fallback when the endpoint is down (G-04 / US-QA-03, MVP); PII masking (A-03 assumes none).

**How a human tests it**: In a dev notebook, call `parse_quick_add("Book demo with planners next Monday !low",
"me@asm.com", today=date(2026,10,7))` and confirm `{title: "Book demo with planners", due_date: "2026-10-12",
priority: "low"}`; then call it with `"tomorrow"` and confirm `needs_title=true`.

### F-04 — Quick-add golden-set evaluation

| Field | Value |
|---|---|
| Module | `quick_add` |
| Type | ML evaluation (MLflow) |
| Size | S |
| Depends on | F-03 |
| PRD reference | US-QA-01; O-2; §9 quick-add accuracy; LC-01 |

**What to build**: An MLflow evaluation that runs `parse_quick_add` over all of GX-01..GX-12 (§11B) with
`today=2026-10-07`, `tz=Asia/Kolkata`, scoring each line as correct only when title, due date and priority all
match the expected output (GX-10 counts correct when it is rejected with `needs_title=true`). Log the accuracy
as an MLflow metric and store the per-line results. This produces the PoC exit score and the baseline for LC-01.

**Acceptance criteria**:

| ID | Given / When / Then | Checked by |
|---|---|---|
| AC-F04-1 | Given the full golden set, when the evaluation runs, then an accuracy metric (share of all-fields-correct lines) is logged to MLflow with per-line pass/fail | MLflow eval |
| AC-F04-2 | Given the logged accuracy, when compared to the target, then it is ≥ 0.90 (≥ 11 of 12 lines correct) | MLflow eval (threshold ≥ 0.90) |

**Out of scope for this feature**: latency measurement (NFR applies from MVP); MLflow tracing in the app (MVP); any model fine-tuning or prompt A/B framework.

**How a human tests it**: Run the evaluation notebook/job, open the MLflow run, and confirm the accuracy metric
is ≥ 0.90 and that the per-line table shows which golden examples passed.

## 5. Change Log

| Date | Change | Features affected | Requested by | Approved by |
|---|---|---|---|---|
| 2026-10-07 | Initial list | All | — |  |
| 2026-10-07 | Approved | All | — | Sumit |
