# PRD-TODO-001: Product Requirements Document — Team Todo

| Field | Value |
|---|---|
| Document ID | PRD-TODO-001 |
| Version | 1.0 |
| Status | APPROVED |
| Author(s) | Sumit Kumar |
| Product Owner (approver) | Sumit Kumar |
| Created | 2026-10-06 |
| Last Updated | 2026-10-06 |
| Source BRD | N/A — internal pilot to test the Dev Agent framework |
| Target stage for first build | PoC |
| Project ID for the Dev Agent | TODO-APP |

---

# Part 1 — Problem Alignment

## 1. General Information

| Field | Detail |
|---|---|
| Product Name | Team Todo |
| Product Owner | Sumit Kumar |
| Team | Global Operations AI |
| Target Release | R1 — MVP |
| Platform | Databricks (Databricks Apps, Lakebase, AI Functions / AI Gateway) |
| Primary Channel | Web application (Databricks App) |
| Business Unit | Global Operations |

## 2. Background & Product Vision

### Current State

The Global Operations AI team (2 developers today, more planned) tracks small tasks — follow-ups from business
meetings, data access requests, deployment chores — in personal notes, Teams chats and Excel. There is no shared
list, so tasks are missed and nobody can see who is doing what.

This process is:

* **Scattered** — tasks live in 3+ places; about 1 in 5 follow-ups is forgotten (team estimate).
* **Slow to capture** — writing a task with a due date and priority takes several clicks in Excel.
* **Invisible** — the team lead cannot see open or overdue work without asking.

### Product Vision

A simple shared todo app inside the ASM Databricks workspace. Anyone on the team can add a task in one line of
plain English ("Send SCO extract to Priya by Friday, high priority"), see their own and the team's tasks, and mark
them done. It also serves as the first pilot project for the autonomous Dev Agent.

**Vision statement**: *Every team task captured in one place in under 10 seconds.*

## 3. Problem Statement

**Who**: Members and the lead of the Global Operations AI team.

**Problem**: Tasks are spread across notes, chats and spreadsheets, so they are forgotten and no one has an overview
of open or overdue work.

**Impact**:

* Follow-ups to business stakeholders are missed or late.
* The team lead spends time each week asking for status.
* No history of what was done when.

**Desired Outcome**: All team tasks are in one shared list, captured in under 10 seconds, with overdue tasks visible at a glance.

## 4. Constraints & Preferences

| # | Constraint / Preference | Type | Why |
|---|---|---|---|
| C-01 | Must run entirely on Databricks; no external SaaS | Hard constraint | Data cannot leave ASM |
| C-02 | All LLM calls through Databricks AI Gateway / Foundation Model APIs | Hard constraint | Governance |
| C-03 | Users sign in with their Databricks workspace identity (no separate login) | Hard constraint | Security, simplicity |
| C-04 | Keep it simple: the smallest design that meets this PRD | Preference | It is a pilot |
| C-05 | Deploy with a Databricks Asset Bundle (dev and prod targets) | Hard constraint | Team standard |

## 5. Persona

### Primary: Team Member

| Attribute | Detail |
|---|---|
| Role | Data / AI engineer |
| Department | Global Operations AI |
| Technical Skill | High |
| Daily Task | Builds pipelines, agents and apps; handles requests from business |
| Pain Point | Forgets follow-ups that came in through chat or meetings |
| Goal | Capture a task in one line and see what is due |
| Tool Access | Browser (Databricks workspace) |
| Number of users | 2 now, up to 10 within a year |

### Secondary: Team Lead

| Attribute | Detail |
|---|---|
| Role | Team lead |
| Goal | See all open and overdue tasks across the team without asking |
| Number of users | 1 |

## 6. Customer Journey Map

### Current Journey

| Stage | Action | Pain Point | Time / Volume |
|---|---|---|---|
| 1. Request arrives | Someone asks in a meeting or chat | Not written down immediately | ~15 requests / week |
| 2. Capture | Note in personal notes or Excel | Several clicks; due date often skipped | 1–2 min each |
| 3. Track | Check own notes | No shared view | — |
| 4. Report | Lead asks for status | Interrupts work | ~30 min / week |

### Future Journey

| Stage | Action | Improvement | Who acts |
|---|---|---|---|
| 1. Capture | Type one line in the app | Title, due date, priority filled in automatically | User + system |
| 2. Review | Check "My tasks" sorted by due date | One place, overdue highlighted | User |
| 3. Complete | Click "Done" | History kept | User |
| 4. Overview | Lead opens "Team" view | No status meetings needed | Lead |

## 7. Objectives & Goals

| # | Objective | Key Result | Baseline today | Timeframe |
|---|---|---|---|---|
| O-1 | Fast capture | Median time to add a task < 10 seconds | 1–2 minutes | MVP |
| O-2 | Accurate quick-add | ≥ 90% of one-line tasks parsed correctly (title, due date, priority) on the golden set | Not applicable | PoC |
| O-3 | Single source of truth | 100% of team tasks for the pilot month in the app | ~0% | Prod + 1 month |
| O-4 | Visibility | Lead can see all overdue tasks in one view | Not possible | MVP |

## 8. Assumptions & Dependencies

### Assumptions

| ID | Assumption | Impact if Invalid |
|---|---|---|
| A-01 | All users have access to the Databricks workspace | Users outside the workspace cannot use the app |
| A-02 | Fewer than 10,000 tasks in the first year | Storage/indexing design may need revisiting |
| A-03 | Task text contains no customer PII (internal work items only) | Would need PII masking before LLM calls |

### Dependencies

| # | Dependency | Owner | Status | Needed from stage | Risk if Unavailable |
|---|---|---|---|---|---|
| D-01 | Databricks Apps enabled in the workspace | Workspace admin | Available | MVP | No UI |
| D-02 | Lakebase (Postgres) project for app data | Workspace admin | Requested | PoC | Fall back to a UC Delta table |
| D-03 | A Foundation Model (chat) endpoint via AI Gateway | Workspace admin | Available | PoC | No quick-add parsing |

## 8A. Data Sources & Access

| # | Data source | Location | Owner | Contains PII? | Volume / frequency | Sample available for PoC? | Access status |
|---|---|---|---|---|---|---|---|
| DS-01 | Tasks (created by the app) | Lakebase database `todo_dev` (table `tasks`) | GO AI team | No (assumption A-03) | ~50 / week | Yes — golden examples §11B | Requested |
| DS-02 | Team members | Workspace identity (user email from the app's auth headers) | Databricks | Name / email (internal) | ≤ 10 users | Yes — the 2 developers | Granted |

**Outputs the system must write**

| # | Output | Location | Consumer |
|---|---|---|---|
| OUT-01 | Task records (create, update, complete, delete) | Lakebase `tasks` | The app |
| OUT-02 | Task change history | Lakebase `task_events` | Team lead (audit) |

## 9. Success Metrics

| Metric | Definition | Baseline | Target | Measurement Method | Frequency |
|---|---|---|---|---|---|
| Quick-add accuracy | Share of golden-set lines where title, due date and priority are all correct | — | ≥ 90% | MLflow evaluation on §11B | Each build |
| Time to add a task | Median seconds from opening the input to saving | 60–120 s | < 10 s | App event timestamps | Weekly |
| Adoption | Active users per week / team size | 0% | 100% | Distinct users in `task_events` | Weekly |
| Overdue tasks | Open tasks past due date | Unknown | Visible daily; trend down | Query on `tasks` | Weekly |

## 10. Value Statement

**For** members of the Global Operations AI team
**Who** lose track of follow-ups spread across chats, notes and spreadsheets
**The** Team Todo app **is a** shared task list inside Databricks
**That** captures a task from one line of plain English in seconds
**Unlike** personal notes and Excel
**Our product** gives one shared, auditable list with overdue tasks visible to the whole team.

---

# Part 2 — Solution Alignment

## 11. Key Features

| # | Feature | Description | Priority | Stage | Linked stories |
|---|---|---|---|---|---|
| F-01 | **Task storage** | Create, read, update, delete tasks with title, due date, priority, status, owner | Must Have | PoC | US-TK-01..04 |
| F-02 | **Quick-add (plain English)** | Turn one line of text into title, due date and priority | Must Have | PoC | US-QA-01..03 |
| F-03 | **My tasks view** | List my open tasks sorted by due date; overdue highlighted | Must Have | MVP | US-VW-01 |
| F-04 | **Team view** | All open tasks by owner, with filters | Must Have | MVP | US-VW-02 |
| F-05 | **Complete / reopen** | Mark done, reopen, with history | Must Have | MVP | US-TK-05 |
| F-06 | **Change history** | Every change recorded with who and when | Should Have | MVP | US-AD-01 |
| F-07 | **Daily overdue digest** | Lead sees a count of overdue tasks per person each morning (in-app banner) | Could Have | Prod | US-VW-03 |

## 11A. Stage Scope — PoC / MVP / Prod

| | PoC | MVP | Prod |
|---|---|---|---|
| Question it answers | Can we store tasks and parse one-line input accurately? | Will the 2 developers use it daily? | Can the whole team rely on it? |
| Users | Developers only, via API / notebook | 2 developers in the app | Whole team (≤ 10) |
| Data | Golden examples + test tasks | Real tasks (dev workspace) | Real tasks (prod target) |
| Must include | F-01, F-02 | F-01..F-06 | F-01..F-07 |
| Explicitly NOT included | Any UI; history | Overdue digest; mobile layout | — |
| Exit criteria (business) | Quick-add ≥ 90% on golden set; CRUD works | Both developers use it for 2 weeks; median add time < 10 s | Launch criteria §20 met |

## 11B. Golden Examples — inputs and expected outputs

Today's date for all examples: **Wednesday 2026-10-07** (user time zone Asia/Kolkata). Default priority = medium. No date given = no due date.

| # | Input (quick-add line) | Expected title | Expected due date | Expected priority | Why this example matters |
|---|---|---|---|---|---|
| GX-01 | Send SCO extract to Priya by Friday, high priority | Send SCO extract to Priya | 2026-10-09 | high | Happy path |
| GX-02 | Review BRD agent PR tomorrow | Review BRD agent PR | 2026-10-08 | medium | Relative date |
| GX-03 | Renew Databricks PAT | Renew Databricks PAT | (none) | medium | No date, no priority |
| GX-04 | Book demo with planners next Monday !low | Book demo with planners | 2026-10-12 | low | "next Monday" + shorthand priority |
| GX-05 | Fix QI camera bug urgent | Fix QI camera bug | (none) | high | "urgent" means high |
| GX-06 | Update runbook on 15 Oct | Update runbook | 2026-10-15 | medium | Absolute date, no year |
| GX-07 | Prepare QSR slides by end of month | Prepare QSR slides | 2026-10-31 | medium | "end of month" |
| GX-08 | Call vendor re: license 2026-11-03 high | Call vendor re: license | 2026-11-03 | high | ISO date |
| GX-09 | Ask IT for Lakebase access in 3 days | Ask IT for Lakebase access | 2026-10-10 | medium | "in N days" |
| GX-10 | tomorrow | (rejected — no task text) | — | — | Must not create an empty task; ask user for a title |
| GX-11 | Archive old notebooks by yesterday | Archive old notebooks | 2026-10-06 | medium | Past date allowed but flagged as overdue |
| GX-12 | Write unit tests for planner, priority: HIGH, due fri | Write unit tests for planner | 2026-10-09 | high | Mixed-case, explicit labels |

## 12. User Flow

### 12.1 Happy Path — Quick-add

```
1. User opens the app and types one line in the quick-add box
2. System parses title, due date and priority and shows them for confirmation
3. User presses Enter (or edits a field, then Enter)
4. System saves the task with the user as owner and records a "created" event
5. Task appears in "My tasks" in due-date order
```

### 12.2 Alternate Flow — Parsing unsure

```
1. User types an ambiguous line (e.g. only a date, or an unclear date)
2. System cannot fill the title, or the date is ambiguous
3. System shows the fields it is sure of and highlights the rest for the user to fill
4. Nothing is saved until the user confirms
```

### 12.3 Alternate Flow — AI service unavailable

```
1. The model endpoint fails or times out (> 3 s)
2. System falls back to a plain form (title, due date, priority fields)
3. User fills the form manually; the task is saved normally
```

## 13. Product Roadmap

| Release | Stage | Theme | Target |
|---|---|---|---|
| **R1** | PoC | Storage + quick-add parsing | Oct 2026 |
| R2 | MVP | App with my / team views, history | Nov 2026 |
| R3 | Prod | Whole team, overdue digest, monitoring | Dec 2026 |

## 14. Expected Timeline

| Stage | Duration | Start | End | Key Deliverables |
|---|---|---|---|---|
| PoC | 2 weeks | 2026-10-12 | 2026-10-23 | Task store, quick-add with evaluation |
| MVP | 4 weeks | 2026-10-26 | 2026-11-20 | Databricks App, views, history |
| Prod | 2 weeks | 2026-11-23 | 2026-12-04 | Prod deploy, digest, monitoring |

## 15. User Stories

### 15.1 Tasks

**Epic**: As a team member, I want to keep my tasks in one place so that nothing is forgotten.

| Story ID | User Story | Acceptance Criteria (Given / When / Then) | Priority | Stage |
|---|---|---|---|---|
| US-TK-01 | As a member, I want to create a task so I can track it | Given a title, when I create a task, then it is stored with me as owner, status "open", created timestamp | Must Have | PoC |
| US-TK-02 | As a member, I want to edit a task so I can correct it | Given an existing task I own, when I change its title, due date or priority, then the change is stored | Must Have | PoC |
| US-TK-03 | As a member, I want to delete a task so I can remove mistakes | Given a task I own, when I delete it, then it no longer appears in any list | Must Have | PoC |
| US-TK-04 | As a member, I only want to change my own tasks | Given a task owned by someone else, when I try to edit or delete it, then the request is refused | Must Have | PoC |
| US-TK-05 | As a member, I want to mark a task done or reopen it | Given an open task, when I mark it done, then status is "done" with a completed timestamp; reopening sets it back to "open" | Must Have | MVP |

### 15.2 Quick-add

| Story ID | User Story | Acceptance Criteria (Given / When / Then) | Priority | Stage |
|---|---|---|---|---|
| US-QA-01 | As a member, I want to type a task in plain English so I can capture it fast | Given the golden set GX-01..GX-12, when quick-add parses each line, then ≥ 90% have title, due date and priority all correct | Must Have | PoC |
| US-QA-02 | As a member, I don't want empty tasks created | Given a line with no task text (GX-10), when parsed, then no task is created and the user is asked for a title | Must Have | PoC |
| US-QA-03 | As a member, I still want to add tasks when AI is down | Given the model endpoint is unavailable, when I add a task, then a manual form is offered and the task saves | Must Have | MVP |

### 15.3 Views

| Story ID | User Story | Acceptance Criteria (Given / When / Then) | Priority | Stage |
|---|---|---|---|---|
| US-VW-01 | As a member, I want to see my open tasks by due date | Given I have open tasks, when I open "My tasks", then they are sorted by due date (no date last) and overdue ones are highlighted | Must Have | MVP |
| US-VW-02 | As the lead, I want to see all open tasks by owner | Given tasks from several owners, when I open "Team", then I see them grouped by owner with a filter for overdue only | Must Have | MVP |
| US-VW-03 | As the lead, I want a daily overdue count | Given overdue tasks exist, when I open the app on a new day, then a banner shows overdue count per person | Could Have | Prod |

### 15.4 Audit

| Story ID | User Story | Acceptance Criteria (Given / When / Then) | Priority | Stage |
|---|---|---|---|---|
| US-AD-01 | As the lead, I want a history of changes | Given any create, edit, complete, reopen or delete, then an event is stored with task id, action, user and timestamp | Should Have | MVP |

## 16. UX Mockup / Wireframe

```
Team Todo                         [My tasks] [Team]
+ Send SCO extract to Priya by Friday, high priority  [Add]
  -> Title: Send SCO extract to Priya  Due: Fri 9 Oct  High
[ ] Review BRD agent PR            Thu 8 Oct    Medium
[ ] Send SCO extract to Priya      Fri 9 Oct    High
[ ] Archive old notebooks          Tue 6 Oct    Medium  (overdue)
[ ] Renew Databricks PAT           —            Medium
```

## 16A. Non-Functional Requirements

| Area | Requirement | Stage it applies from |
|---|---|---|
| Latency | Quick-add parse < 3 s (p95); list loads < 1 s for 500 tasks | MVP |
| Volume | ≤ 10 users, ≤ 10,000 tasks | Prod |
| Availability | Business hours; best effort | MVP |
| Security & access | Workspace SSO only; users edit only their own tasks; app service principal has least privilege | PoC |
| Privacy | No task text in logs beyond what debugging needs | PoC |
| Audit | All changes recorded (US-AD-01) | MVP |
| Retention | Keep tasks and history for 2 years | Prod |
| Cost | Model spend < $5 / month at expected volume | Prod |
| Observability | MLflow tracing on quick-add calls; app errors visible in app logs | MVP |

## 16B. Guardrails & Responsible AI

| # | Rule | Type | Enforced how |
|---|---|---|---|
| G-01 | The AI only fills fields; the user always confirms before a task is saved | Human-in-the-loop | |
| G-02 | Never create a task without a title | Output | |
| G-03 | Quick-add input is limited to 300 characters and is not used for anything except parsing | Input | |
| G-04 | If parsing fails or times out, fall back to the manual form | Output | |

## 17. Questions / Edge Cases

| # | Question / Edge Case | Current Decision | Status |
|---|---|---|---|
| Q-01 | Which time zone for relative dates? | User's browser time zone; default Asia/Kolkata | Decided |
| Q-02 | Can tasks be assigned to someone else? | Not in R1–R3; owner = creator | Decided |
| Q-03 | Lakebase vs UC Delta table for storage? | Prefer Lakebase (transactional app data); Architect to confirm | Open (does not block PoC) |

## 18. Out of Scope

| # | Exclusion | Rationale | Planned Stage / Release |
|---|---|---|---|
| X-1 | Assigning tasks to others | Keep the pilot simple | Future |
| X-2 | Email / Teams notifications | Needs integration approval | Future |
| X-3 | Mobile app | Browser is enough | Future |
| X-4 | Sub-tasks, tags, attachments | Not needed for the pilot | Future |

## 19. RICE Prioritisation (optional)

N/A — small pilot; priorities set in §11.

---

# Part 3 — Launch

## 20. Launch Criteria

| # | Criterion | Verification Method | Owner |
|---|---|---|---|
| LC-01 | Quick-add accuracy ≥ 90% on golden set | MLflow evaluation run | Dev team |
| LC-02 | Users can only change their own tasks | Automated test | Dev team |
| LC-03 | App deployed to prod target via bundle from CI | Deployment log | Dev team |
| LC-04 | Manual fallback works when the model is down | Test with endpoint disabled | Dev team |

## 21. Launch Checklist

| # | Task | Owner | Status |
|---|---|---|---|
| [ ] | Lakebase database and tables deployed via bundle | Dev team | Not started |
| [ ] | App deployed to prod target | Dev team | Not started |
| [ ] | App service principal permissions configured | Dev team | Not started |
| [ ] | Golden-set evaluation baseline recorded | Dev team | Not started |
| [ ] | Monitoring (app errors, MLflow traces) in place | Dev team | Not started |
| [ ] | Runbook and rollback documented | Dev team | Not started |
| [ ] | Product owner sign-off | Sumit Kumar | Not started |

## 22. Future Feature Works

| # | Feature | Description | Target Stage / Release | Dependencies |
|---|---|---|---|---|
| FF-01 | Assign to others | Create tasks for a teammate | Future | Notifications |
| FF-02 | Teams notifications | Reminder before due date | Future | Teams integration approval |

## 23. Analytics Event Tracker

| Event Name | Trigger | Properties | Purpose |
|---|---|---|---|
| `task.created` | Task saved | `task_id`, `user`, `via_quick_add`, `parse_ms`, `timestamp` | Adoption, add-time metric |
| `task.completed` | Marked done | `task_id`, `user`, `timestamp` | Throughput |
| `quickadd.fallback` | Manual form used after AI failure | `user`, `reason`, `timestamp` | Reliability |
| `session.started` | App opened | `user`, `timestamp` | Active users |

## 24. Glossary

| Term | Definition |
|---|---|
| Quick-add | Adding a task by typing one line of plain English |
| Golden set | The examples in §11B used to measure parsing accuracy |
| Lakebase | Databricks managed Postgres for transactional app data |

## 25. Document Revision History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | 2026-10-06 | Sumit Kumar | Initial PRD for the Dev Agent pilot |

---

## Appendix — Definition of Ready

- [x] Every Must Have feature in §11 has a stage and at least one user story in §15.
- [x] Every user story has a Given / When / Then acceptance criterion.
- [x] Every input and output is listed in §8A with a location and an access status.
- [x] 12 golden examples in §11B.
- [x] §11A states what PoC, MVP and Prod must and must not include.
- [x] §16A and §16B are filled in.
- [x] §4 contains constraints and preferences only.
- [x] Open question Q-03 does not block the PoC.
