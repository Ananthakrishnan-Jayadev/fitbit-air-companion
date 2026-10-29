# Tasks

Implementation checklist for the plan in [project.md](project.md). Work top to bottom; each
phase should leave `.venv/bin/fitbit serve` runnable.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done

---

## Phase 0: Repo and tooling
- [x] Initialize git repo, `.gitignore`
- [x] Write `project.md` (architecture) and `task.md`
- [x] Write `CLAUDE.md` (build rules)
- [ ] `pyproject.toml`: package `fitbit_app` (src layout), Python ≥3.12, deps (fastapi,
      uvicorn[standard], typer, httpx, authlib, sqlalchemy, alembic, pydantic-settings,
      apscheduler, pandas, numpy, ollama, jinja2, cryptography), dev extras (pytest,
      pytest-asyncio, ruff, respx)
- [ ] `[project.scripts] fitbit = "fitbit_app.cli:app"`
- [ ] `.env.example` with all settings (Google, Ollama, paths, sync intervals)
- [ ] `README.md` with setup steps (project.md §12)
- [ ] ruff config; pytest config

## Phase 1: Backend skeleton and single-command runner
- [ ] `config.py`: pydantic-settings (`GOOGLE_CLIENT_ID/SECRET`, `OLLAMA_HOST`,
      `OLLAMA_MODEL=gemma4:31b`, `DATA_DIR`, `HOST`, `PORT`, `SYNC_INTERVAL_MIN`, flags)
- [ ] `main.py`: FastAPI app factory, lifespan hooks (DB init, scheduler start/stop),
      `/api/health`, static mount of `static/` with SPA fallback to `index.html`
- [ ] `cli.py` (Typer): `serve`, `sync`, `analyze`, `brief`, `build-ui`, `doctor`, `db upgrade`
- [ ] `serve`: run uvicorn programmatically; warn if `static/` missing ("run fitbit build-ui")
- [ ] `devserver.py`: `serve --dev` spawns `npm --prefix frontend run dev` as a child
      process, prefixes its output, terminates it on shutdown/Ctrl+C
- [ ] `doctor`: check `.env`, DB writable, Google token present/valid, Ollama reachable,
      model pulled

## Phase 2: Storage
- [ ] `storage/db.py`: SQLite engine, WAL + foreign keys pragmas, file permissions 0600
- [ ] `storage/models.py`: tables from project.md §6
- [ ] Alembic setup + initial migration
- [ ] Upsert helpers (idempotent on natural keys)

## Phase 3: Google Health API (Option A)
- [ ] Manual: create Google Cloud project, enable Google Health API, OAuth consent
      (Testing, self as test user), Web OAuth client with redirect
      `http://127.0.0.1:8000/api/auth/callback`
- [ ] Copy exact base URL, endpoint paths and scope strings from official docs into
      `ingest/endpoints.py` and `ingest/scopes.py`
- [ ] `ingest/oauth.py` + `api/auth.py`: login → consent → callback → store tokens
      (Fernet-encrypted refresh token)
- [ ] `ingest/client.py`: `GoogleHealthClient` with auto refresh, pagination, token-bucket
      rate limit, backoff on 429/5xx, `dataSourceFamily` filter support
- [ ] `ingest/registry.py`: Air-relevant data types (project.md §5.3) with granularity,
      endpoint version (v4 / v4beta) and enabled flag
- [ ] `ingest/sync.py`: `SyncEngine` with per-type cursors, 2 h overlap, chunked backfill
      (newest first), errors recorded in `sync_state`
- [ ] Store raw responses in `data_points`
- [ ] `storage/normalize.py`: raw → `hr_samples`, `hrv_samples`, `spo2_samples`,
      `activity_minutes`, `sleep_sessions`/`sleep_stages`, `exercise_sessions`, `daily_metrics`
- [ ] Timezone handling: UTC storage + local-day assignment (sleep crossing midnight)
- [ ] `api/sync.py`: trigger + status endpoints
- [ ] Unit tests with recorded/fake API responses (respx)

## Phase 4: Analytics engine
- [ ] Synthetic data generator for tests (realistic HR/HRV/sleep days)
- [ ] `baselines.py`: 30-day / 7-day rolling stats
- [ ] `sleep.py`: sleep performance score
- [ ] `recovery.py`: recovery score + component breakdown
- [ ] `strain.py`: TRIMP-based strain 0–21 + daily strain target
- [ ] `stress.py`: sedentary-HR-elevation stress timeline
- [ ] `anomaly.py`: illness/overreach multi-signal flags
- [ ] `load.py`: acute:chronic workload ratio
- [ ] `correlations.py`: journal tags vs next-day outcomes (with minimum N)
- [ ] `features.py`: compact feature pack (project.md §8.2)
- [ ] Recompute affected dates after each sync; `fitbit analyze` CLI
- [ ] Unit tests for every module

## Phase 5: AI layer (Ollama)
- [ ] `ai/client.py`: `ollama.AsyncClient`, timeout, model presence check, fallback model
- [ ] `ai/schemas.py`: pydantic schemas for brief / tips / weekly / anomaly explainer
- [ ] `ai/prompts/`: system prompt (grounded, non-diagnostic) + Jinja templates
- [ ] `ai/context.py`: feature pack builder + token budget guard
- [ ] `ai/service.py`: daily brief, weekly review, anomaly explainer (structured `format=`
      JSON, validate, retry once), dedupe by `prompt_hash`
- [ ] Coach chat: SSE streaming endpoint, history in `chat_messages`
- [ ] `/api/ai/status`, `/api/ai/insights`, `/api/ai/brief/regenerate`
- [ ] Graceful degradation when Ollama is down
- [ ] (Later) tool calling: `get_metric(name, range)`, `get_sleep(date)` for chat

## Phase 6: Scheduler
- [ ] `scheduler.py`: APScheduler in the FastAPI lifespan
- [ ] Jobs: intraday sync /15 min, daily+session sync /hour, analysis after sync,
      daily brief (after morning sleep lands, 09:00 fallback), weekly review (Mon 09:00)
- [ ] Prevent overlapping runs (max_instances=1, coalesce)

## Phase 7: Frontend (React + Vite + TS)
- [ ] Scaffold `frontend/` (Vite React-TS), Tailwind, React Router, TanStack Query, ECharts
- [ ] `vite.config.ts`: `outDir: ../src/fitbit_app/static`, dev proxy `/api` → `:8000`
- [ ] Typed API client (`src/api/`)
- [ ] Layout + nav; Ollama/Google status banners
- [ ] **Settings**: Connect Google, sync status + backfill, Ollama status, profile
- [ ] **Today**: score rings, strain target, AI brief + tips, flags
- [ ] **Heart**: zoomable intraday HR, HRV/RHR trends, zones, AFib notifications
- [ ] **Sleep**: hypnogram, stages, overnight SpO2, temp delta, consistency
- [ ] **Activity**: steps/AZM/calories, sedentary periods, stress timeline, workouts
- [ ] **Trends**: metric vs baseline band, 7/30/90/365 d
- [ ] **Journal**: daily tags + notes, correlations view
- [ ] **Coach**: streaming chat UI
- [ ] Server-side LTTB downsampling for large intraday series

## Phase 8: Hardening
- [ ] Structured logging to console + `data/logs/`
- [ ] Re-auth UX for expired Testing-mode tokens
- [ ] Data export (CSV/Parquet) from Settings
- [ ] Backup: copy SQLite DB command (`fitbit db backup`)
- [ ] README troubleshooting section

---

## Not planned
- Direct Bluetooth / Option C. Documented as research only in project.md §15.
- Webhooks (would need a public HTTPS tunnel).
