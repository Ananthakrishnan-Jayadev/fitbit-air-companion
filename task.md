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
- [ ] **Manual (you):** Google Cloud project, enable Google Health API, Web OAuth client with
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
- [ ] **After the first real sync:** resolve every `TODO(verify)` (filter prefixes for
      multi-word types, exercise `metricsSummary`, rollup value fields, `activityLevelType`
      values) by inspecting `data_points.value_json`, then normalize those fields

---

## Phase 3: Scores and dashboard
- [ ] `analytics/baselines.py`: 30-day / 7-day rolling stats
- [ ] `analytics/sleep.py`: sleep performance score
- [ ] `analytics/recovery.py`: recovery score + component breakdown
- [ ] `analytics/strain.py`: TRIMP strain 0–21 + daily target
- [ ] `analytics/stress.py`: sedentary-HR-elevation stress timeline
- [ ] `analytics/anomaly.py`: illness/overreach multi-signal flags
- [ ] `analytics/load.py`: acute:chronic workload ratio
- [ ] `analytics/features.py`: compact feature pack (project.md §8.2)
- [ ] Recompute affected dates after each sync; CLI `fitbit analyze [--date]`
- [ ] API: `/api/today`, `/api/daily`, `/api/heart/intraday` (LTTB), `/api/sleep`,
      `/api/sleep/range`, `/api/activity`, `/api/exercise`, `/api/trends`, `/api/settings`
- [ ] **Today**: score rings, strain target, flags, component breakdowns
- [ ] **Heart**: zoomable intraday HR, HRV/RHR trends, zones, AFib notifications
- [ ] **Sleep**: hypnogram, stages, overnight SpO2, temp delta, consistency
- [ ] **Activity**: steps/AZM/calories, sedentary periods, stress timeline, workouts
- [ ] **Trends**: metric vs baseline band, 7/30/90/365 d
- [ ] pytest: every analytics module (synthetic data + edge cases), all new endpoints

---

## Phase 4: Local AI coach (Ollama)
- [ ] `ai/client.py`: `ollama.AsyncClient`, timeout, model presence check, fallback model
- [ ] `ai/schemas.py`: pydantic schemas for brief / tips / weekly / anomaly explainer
- [ ] `ai/prompts/`: system prompt (grounded, non-diagnostic) + Jinja templates
- [ ] `ai/context.py`: feature pack → prompt context, token budget guard
- [ ] `ai/service.py`: daily brief, weekly review, anomaly explainer, using structured
      `format=` JSON, validation, one retry, `prompt_hash` dedupe
- [ ] Coach chat: SSE streaming endpoint, history in `chat_messages`
- [ ] API: `/api/ai/status`, `/api/ai/insights`, `/api/ai/brief/regenerate`, `/api/ai/chat`
- [ ] Scheduler: daily brief (after morning sleep lands, 09:00 fallback), weekly review
      (Mon 09:00), anomaly explainer on new flags
- [ ] CLI `fitbit brief [--date]`
- [ ] UI: brief + tips on **Today**, **Coach** page (streaming), Ollama status banner
- [ ] Graceful degradation when Ollama is down / `AI_ENABLED=false`
- [ ] pytest: prompt building, schema validation/retry, dedupe, degradation, chat endpoint
      (Ollama mocked)

---

## Phase 5: Journal, insights and hardening
- [ ] API `/api/journal` (GET/POST/DELETE)
- [ ] **Journal page**: daily tags + notes
- [ ] `analytics/correlations.py`: tags vs next-day outcomes (min N, bootstrap CI)
- [ ] API `/api/correlations` + "What affects you" view; add to feature pack
- [ ] Coach tool calling: `get_metric(name, range)`, `get_sleep(date)`
- [ ] Data export (CSV/Parquet) from Settings
- [ ] CLI `fitbit db backup`
- [ ] Log files in `data/logs/`; review logs for health values/secrets
- [ ] Re-auth UX polish; README troubleshooting; final `doctor` pass
- [ ] pytest: journal API, correlations, tool-call handling, export/backup

---

## Not planned
- Direct Bluetooth / Option C. Documented as research only in project.md §15.
- Webhooks (would need a public HTTPS tunnel).
