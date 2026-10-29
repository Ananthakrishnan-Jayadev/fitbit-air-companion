# Development Plan

Five phases, each ending in something you can open and use. Architecture is in
[project.md](project.md), checkbox-level tasks are in [task.md](task.md), and build rules are in
[CLAUDE.md](CLAUDE.md).

```
Phase 1          Phase 2           Phase 3              Phase 4          Phase 5
Foundation  ──►  Data in      ──►  Scores +        ──►  Local AI    ──►  Journal, insights
(runs, empty)    (real data)       dashboard            coach            & hardening
```

Each phase depends on the previous one. Phases 3 and 4 could overlap once the feature pack
(Phase 3) exists, but the plan runs them in order.

---

## Phase 1: Foundation
**Goal:** `.venv/bin/fitbit serve` starts the app in one terminal and serves an empty UI.

**Scope**
- `pyproject.toml` (deps declared, `fitbit` console script), `.env.example`, `README.md`, ruff
  and pytest config
- `config.py` (pydantic-settings), `errors.py`, logging setup
- FastAPI app factory with lifespan, `/api/health`, static mount with SPA fallback
- Typer CLI: `serve`, `serve --dev` (spawns Vite as a child process), `build-ui`, `doctor`, `db upgrade`
- SQLite engine (WAL, `0600`), all SQLAlchemy models from project.md §6, Alembic initial migration
- Frontend scaffold: Vite + React + TS + Tailwind + Router + TanStack Query, layout and nav
  with placeholder pages, typed API client, build output to `src/fitbit_app/static/`
- Shared synthetic-data generator in `tests/fixtures/`

**Deliverable:** you open `http://127.0.0.1:8000` and see the app shell. `fitbit doctor`
reports config, DB, and Ollama status.

**Exit criteria**
- `serve` and `serve --dev` both work from a single terminal; Ctrl+C stops everything
- Migration creates all tables
- pytest: config, health endpoint, DB setup, CLI `doctor` (Ollama mocked)

**Size:** M

---

## Phase 2: Data in (Google Health API)
**Goal:** your real Fitbit Air data lands in SQLite and stays up to date automatically.

**Scope**
- Manual Google Cloud setup (project, API, OAuth consent in Testing mode, web client)
- Verify base URL, endpoints, and scopes against the official docs → `endpoints.py`, `scopes.py`
- OAuth login/callback/logout, encrypted refresh-token storage, auto refresh, re-auth state
- `GoogleHealthClient`: pagination, rate limiting, backoff, `dataSourceFamily` filter
- Data type registry (Air-relevant types, v4 / v4beta flag)
- `SyncEngine`: per-type cursors, 2 h overlap, newest-first backfill, error tracking
- Raw `data_points` storage + normalization into typed tables, UTC + local-day logic
- Scheduler: intraday sync /15 min, daily+session sync /hour
- CLI `fitbit sync [--since] [--types]`, API `/api/sync`, `/api/sync/status`
- **Settings page:** Connect Google, sync status per type, backfill button, profile fields

**Deliverable:** connect Google in Settings, run a backfill, and see per-type row counts and
last-sync times.

**Exit criteria**
- Backfill of 30+ days completes. Re-running is idempotent (no duplicates)
- Incremental sync picks up new data without manual action
- Expired/revoked token shows "reconnect", not a crash
- pytest: client (respx), sync cursors/backfill/idempotency, normalization incl. midnight sleep

**Size:** L (most of the uncertainty is here: new API, possible beta changes)

---

## Phase 3: Scores and dashboard
**Goal:** your own recovery, sleep, strain, and stress scores, plus charts of all the data.

**Scope**
- Analytics (pure functions): baselines, sleep performance, recovery, strain + daily target,
  stress timeline, anomaly/illness flags, acute:chronic load
- `features.py`: compact feature pack (needed by Phase 4)
- Recompute affected dates after each sync, plus CLI `fitbit analyze`
- API: `/api/today`, `/api/daily`, `/api/heart/intraday` (LTTB downsampling), `/api/sleep`,
  `/api/activity`, `/api/exercise`, `/api/trends`
- Pages: **Today** (score rings, strain target, flags), **Heart**, **Sleep**, **Activity**,
  **Trends**

**Deliverable:** a dashboard comparable to Pulse/WHOOP-style apps, built from your own data.

**Exit criteria**
- Scores computed for every day with enough data. Days without enough data show "insufficient
  data" instead of failing
- Each score shows its component breakdown in the UI
- Intraday HR chart stays responsive over a full day
- pytest: every analytics module over synthetic data + edge cases, all API endpoints

**Size:** L

---

## Phase 4: Local AI coach (Ollama)
**Goal:** `qwen3.5:9b` explains your data and gives tips, fully offline.

**Scope**
- Ollama client wrapper: timeout, model-present check, fallback model, status endpoint
- Prompt templates + grounded, non-diagnostic system prompt
- Context builder with token budget, using the Phase 3 feature pack
- Structured outputs (`format=` JSON schema) with validation and one retry
- Daily brief + tips, weekly review, anomaly explainer, all cached with `prompt_hash` dedupe
- Scheduler: brief after morning sleep data arrives (09:00 fallback), weekly review Monday 09:00
- Coach chat with SSE streaming and stored history
- UI: brief + tips on **Today**, new **Coach** page, Ollama status banner
- CLI `fitbit brief [--date]`

**Deliverable:** every morning a brief and tips are waiting on Today, and you can chat with
the coach about your data.

**Exit criteria**
- App fully works with Ollama stopped (AI sections show a banner)
- No raw time series reaches the model (only the feature pack)
- Generation never blocks page loads; chat streams
- pytest: prompt building, schema validation/retry, dedupe, degradation, chat endpoint
  (Ollama mocked)

**Size:** M

---

## Phase 5: Journal, insights and hardening
**Goal:** learn what affects *you*, and make the app solid for daily use.

**Scope**
- **Journal page:** daily tags (caffeine, alcohol, late meal, sick, travel…) + notes, API CRUD
- Correlations: tags vs next-day recovery/sleep (minimum N, confidence intervals), "What
  affects you" view, which also feeds the AI feature pack
- Coach tool calling (`get_metric`, `get_sleep`) for questions about history
- Data export (CSV/Parquet) and `fitbit db backup`
- Log files under `data/logs/`, log hygiene review (no health values or secrets)
- Re-auth UX polish, README troubleshooting, full pass over `doctor`

**Deliverable:** after a few weeks of tagging, the app tells you which habits move your
recovery, and the coach can answer "how was my HRV in September?"

**Exit criteria**
- Correlations hidden until enough samples exist
- Export and backup restore cleanly into a fresh DB
- pytest: journal API, correlations, tool-call handling, export/backup

**Size:** M

---

## Out of scope (all phases)
- Direct Bluetooth / Option C (research notes in project.md §15)
- Webhooks, multi-user, cloud hosting, non-pytest test tooling
