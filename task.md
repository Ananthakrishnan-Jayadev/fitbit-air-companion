# Tasks

Implementation checklist. Phases match [development-plan.md](development-plan.md) (goals,
deliverables, exit criteria). Architecture is in [project.md](project.md) and rules in
[CLAUDE.md](CLAUDE.md). Work top to bottom; each phase should leave
`.venv/bin/fitbit serve` runnable.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done

---

## Setup (done)
- [x] Initialize git repo, `.gitignore`
- [x] Write `project.md` (architecture) and `task.md`
- [x] Write `CLAUDE.md` (build rules)
- [x] Write `development-plan.md` (5 phases)

---

## Phase 1: Foundation
### Tooling
- [x] `pyproject.toml`: package `fitbit_app` (src layout), Python ≥3.12, deps (fastapi,
      uvicorn[standard], typer, httpx, sqlalchemy, alembic, pydantic-settings,
      apscheduler, pandas, numpy, ollama, jinja2, cryptography), dev extras (pytest,
      pytest-asyncio, respx, ruff)
- [x] `[project.scripts] fitbit = "fitbit_app.cli:app"`
- [x] `.env.example` with all settings (Google, Ollama, paths, sync intervals)
- [x] `README.md` with setup steps (project.md §12)
- [x] ruff config, pytest config

### Backend skeleton
- [x] `config.py`: pydantic-settings (`GOOGLE_CLIENT_ID/SECRET`, `FITBIT_SECRET_KEY`,
      `OLLAMA_HOST`, `OLLAMA_MODEL=qwen3.5:9b`, `OLLAMA_FALLBACK_MODEL`, `DATA_DIR`, `HOST`,
      `PORT`, `SYNC_INTERVAL_MIN`, `AI_ENABLED`)
- [x] `errors.py` (exception hierarchy) + logging setup
- [x] `main.py`: app factory, lifespan hooks, `/api/health`, static mount with SPA fallback
- [x] `cli.py` (Typer): `serve`, `build-ui`, `doctor`, `db upgrade` (other commands are
      stubbed until their phase)
- [x] `serve`: uvicorn programmatically; warn if `static/` missing
- [x] `devserver.py`: `serve --dev` spawns `npm --prefix frontend run dev`, prefixes output,
      terminates on shutdown/Ctrl+C
- [x] `doctor`: `.env`, DB writable, Ollama reachable + model present (Google check in Phase 2)

### Storage
- [x] `storage/db.py`: engine/session, WAL + foreign keys, file mode 0600
- [x] `storage/models.py`: all tables from project.md §6
- [x] Alembic setup + initial migration
- [x] Upsert helpers (idempotent on natural keys)

### Frontend shell
- [x] Scaffold `frontend/` (Vite React-TS), Tailwind, React Router, TanStack Query, ECharts
- [x] `vite.config.ts`: `outDir: ../src/fitbit_app/static`, dev proxy `/api` → `:8000`
- [x] Typed API client (`src/api/`)
- [x] Layout + nav with placeholder pages (Today, Heart, Sleep, Activity, Trends, Journal,
      Coach, Settings)

### Tests
- [x] `tests/fixtures/`: synthetic data generator (HR, HRV, SpO2, sleep, activity days)
- [x] pytest: config, `/api/health`, DB/migration, `doctor` (Ollama mocked)

---

## Phase 2: Data in (Google Health API)
- [x] **Manual (you):** Google Cloud project, enable Google Health API, Web OAuth client with
      redirects `http://127.0.0.1:8000/api/auth/callback` + `http://localhost:8000/...`,
      Audience = Testing + self as test user, add the 4 read scopes, fill `.env`
- [x] Copy exact base URL, endpoint paths, scope strings from official docs →
      `ingest/endpoints.py`, `ingest/scopes.py`
- [x] `ingest/oauth.py` + `api/auth.py`: login (PKCE) → callback (identity check) → store
      tokens (Fernet-encrypted refresh token), logout, re-auth state
- [x] `ingest/client.py`: `GoogleHealthClient` with auto refresh, pagination, rate limit,
      backoff on 429/5xx, `dataSourceFamily` filter
- [x] `ingest/registry.py`: Air-relevant types (project.md §5.3), v4/v4beta, beta flag
- [x] `ingest/sync.py`: `SyncEngine` with per-type synced range, overlap, newest-first
      resumable backfill (90 days), errors stored in `sync_state`
- [x] Raw responses → `data_points` (all types except heart rate)
- [x] `storage/normalize.py`: → `hr_samples`, `hrv_samples`, `spo2_samples`,
      `activity_minutes`, `sleep_sessions`/`sleep_stages`, `exercise_sessions`, `daily_metrics`
- [x] Timezone handling: UTC storage + local day from each point's UTC offset
- [x] `scheduler.py`: APScheduler in lifespan, intraday /15 min, daily+session /hour
- [x] CLI `fitbit sync [--since] [--types]`; `doctor` checks the Google connection
- [x] `api/sync.py`: trigger + status; `api/profile.py`
- [x] **Settings page:** Connect Google, per-type sync status, backfill, profile
- [x] pytest: client (respx), OAuth refresh/re-auth, sync cursors/backfill/idempotency,
      normalization incl. midnight-crossing sleep, auth/sync/profile API
- [x] Filter prefixes: snake_case (`heart_rate.…`), verified live 2026-10-29
- [x] Redact OAuth `code`/`state` from access logs; quiet per-request httpx logging
- [x] Resolve remaining `TODO(verify)` from live data: exercise `metricsSummary`
      (calories, distance, avg HR, zone durations), rollup totals (distance, calories,
      active calories, AZM), `activityLevelType` labels
- [x] CLI `fitbit db renormalize [--types]`: rebuild typed tables from raw JSON
- Note for Phase 3: `daily_metrics.sedentary_min` and per-workout max HR are not in the API;
  derive them from `sedentary-period` raw data and `hr_samples`

---

## Phase 3: Scores and dashboard
- [x] `analytics/baselines.py`: 30-day rolling mean/SD (ln for HRV), SD floors, z-scores
- [x] `analytics/sleep.py`: sleep performance (duration, efficiency, deep+REM, consistency)
- [x] `analytics/recovery.py`: recovery score + component breakdown + penalties
- [x] `analytics/strain.py`: TRIMP strain 0–21 (HRR ≥ 0.3) + daily target; max HR estimate
- [x] `analytics/stress.py`: calm-minute HR elevation timeline + daily average
- [x] `analytics/anomaly.py`: illness/overreach multi-signal flags + 3-day HRV streak
- [x] `analytics/load.py`: acute:chronic workload ratio
- [x] `analytics/activity.py`: sedentary minutes per local day (from raw periods)
- [x] `analytics/downsample.py`: LTTB for charts
- [x] `analytics/features.py`: compact feature pack + trend direction (used in Phase 4)
- [x] `scoring.py` ScoreService: per-day pipeline, runs after every sync; CLI
      `fitbit analyze [--date | --all]`; local days from wake-up UTC offset
- [x] API: `/api/today`, `/api/daily`, `/api/trends`, `/api/heart`, `/api/sleep`,
      `/api/sleep/range`, `/api/activity`, `/api/exercise`
- [x] **Today**: recovery hero + meter, sleep/strain/stress tiles, flags, vs-normal table,
      component breakdowns
- [x] **Heart**: intraday HR (LTTB) with resting line, Google zones, 60-day RHR/HRV trends
- [x] **Sleep**: hypnogram, stage minutes, overnight SpO2 + HRV, temp delta, last 14 nights
- [x] **Activity**: totals, steps by hour, activity levels, stress timeline, workouts
- [x] **Trends**: any metric vs baseline band, 30/90/180/365 d
- [x] pytest: every analytics module, ScoreService integration, all new endpoints
- [ ] AFib (irregular rhythm) notifications on Heart page: none in the data yet; add when
      one exists to design against
- [x] **You:** run checks; `fitbit db renormalize` then `fitbit analyze --all` on the real
      database; review scores in the UI

---

## Phase 4: Local AI coach (Ollama)
- [x] `ai/client.py`: `ollama.AsyncClient`, timeout, model presence check, fallback model,
      optional `think` (auto-disabled for models without it)
- [x] `ai/schemas.py`: pydantic schemas for brief / tips / weekly / anomaly note
- [x] `ai/prompts/` + `ai/templates.py`: grounded, non-diagnostic system prompt + Jinja templates
- [x] `ai/context.py`: feature pack, weekly context, recent days, size budget
- [x] `ai/service.py`: daily brief, weekly review, anomaly note; structured JSON, validation,
      one retry, `prompt_hash` dedupe, one generation at a time
- [x] Coach chat: SSE streaming endpoint, history in `chat_messages`
- [x] API: `/api/ai/status`, `/api/ai/insights`, `/api/ai/generate`, `/api/ai/chat`,
      `/api/ai/chat/{id}`
- [x] Triggers: after each sync (brief once sleep is in, anomaly note on flags, weekly on
      Mondays) instead of fixed-time jobs
- [x] CLI `fitbit brief [--date] [--kind] [--force]`
- [x] UI: coach's brief (+ anomaly note, weekly review) on **Today**, **Coach** chat page
- [x] Graceful degradation when Ollama is down / `AI_ENABLED=false`
- [x] pytest: client (fake Ollama), templates, context, service, API incl. SSE (fake LLM)
- [ ] **You:** run checks, then try a real brief (`fitbit brief`) and the Coach page

---

## Phase 5: Journal, insights and hardening
- [x] API `/api/journal` (GET/PUT/DELETE) + `/api/journal/tags`; tag normalization
- [x] **Journal page**: preset + custom tag chips, notes, last 14 days
- [x] `analytics/correlations.py`: tag vs next-day outcome, bootstrap 95% CI, ≥5 days each
- [x] API `/api/correlations` + "What affects you" table; yesterday's tags and confident
      effects added to the coach's context
- [x] Coach tool calling: `get_metric_history`, `get_day_summary`, `get_journal`,
      `get_tag_effects` (read-only, validated, ≤3 rounds per reply)
- [x] Data export: ZIP of CSVs from Settings (`/api/export`) and `fitbit export`
      (CSV rather than Parquet: no new dependency); credentials never exported
- [x] CLI `fitbit db backup` (SQLite online backup, 0600)
- [x] Log file `data/logs/fitbit.log` (rotating); logs carry no health values or secrets
- [x] Global "reconnect Google" banner; `doctor` data-freshness check; README troubleshooting
- [x] Frontend code splitting (lazy chart pages, separate ECharts chunk)
- [x] pytest: correlations, journal API, tools, export/backup, log file
- [ ] **You:** run checks; try the Journal, a coach question about older data
      ("How was my HRV in September?"), and an export

---

## Not planned
- Direct Bluetooth / Option C. Documented as research only in project.md §15.
- Webhooks (would need a public HTTPS tunnel).
