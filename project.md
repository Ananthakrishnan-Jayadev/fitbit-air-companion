# Fitbit Air Companion: Architecture Plan

A self-hosted, local-first app that pulls everything the Google Health API exposes for a
Google Fitbit Air and analyzes it with deeper scoring than the official app. It also writes
daily insights and coaching tips with a local Ollama model. Health data only leaves the
machine to come from Google; the AI analysis never leaves it.

_Last updated: 2026-10-29_

---

## 1. Goals and non-goals

**Goals**
- Ingest all Air-relevant data from the **Google Health API** (Option A), including the
  intraday (minute-level and finer) series that most apps ignore.
- Compute our own scores: recovery, strain, sleep performance, stress, and illness/anomaly
  flags, with personal baselines.
- Use a **local Ollama model** (`qwen3.5:9b` by default) for a daily brief, tips, and
  a chat "coach" grounded in the computed metrics.
- Run with **one command in one terminal**: `.venv/bin/fitbit serve`.

**Non-goals (for now)**
- Raw sensor access (PPG waveform, raw accelerometer/gyro, raw SpO2 red/IR). No route
  exposes these.
- Direct Bluetooth to the band (Option C). It is documented in §15 as future research only.
- Multi-user / cloud hosting. This is a single-user, personal app.
- Medical diagnosis. Every insight is informational only.

---

## 2. Tech stack (fixed)

| Layer | Choice | Why |
|---|---|---|
| Backend | **Python 3.12, FastAPI, Uvicorn** | Async, great for API + background jobs |
| CLI | **Typer** (console script `fitbit`) | Provides `.venv/bin/fitbit serve` |
| HTTP client | **httpx** (async) | Google Health API calls, OAuth token refresh |
| OAuth | **httpx** (hand-rolled, ~100 lines) | Auth-code + PKCE with refresh tokens; no extra dependency |
| Database | **SQLite** (WAL mode) via **SQLAlchemy 2.0** + **Alembic** | No DB server, which keeps it to one process |
| Analytics | **pandas + numpy** (scipy if needed) | Baselines, rolling stats, scoring |
| Scheduling | **APScheduler** (AsyncIOScheduler, in-process) | Periodic sync and nightly analysis without a second process |
| AI | **ollama** Python client (`AsyncClient`) | Local LLM; structured JSON output + streaming |
| Config | **pydantic-settings** + `.env` | Typed settings |
| Frontend | **React 18 + Vite + TypeScript** | |
| UI data | **TanStack Query**, **React Router** | Caching and routing |
| Charts | **Apache ECharts** (`echarts-for-react`) | Handles large intraday series (tens of thousands of points) |
| Animation | **Motion** (`motion/react`) | Enter/layout animations, count-ups; honours reduced motion (Phase 6, design.md) |
| Styling | **Tailwind CSS** | |
| Python tooling | `venv` + `pip install -e .`, **ruff**, **pytest** | |
| JS tooling | npm, ESLint | No JS test runner; **pytest is the only test framework** (see CLAUDE.md) |

---

## 3. How "one terminal" works

```
.venv/bin/fitbit serve            # production-style: one process, one port
.venv/bin/fitbit serve --dev      # dev: also spawns Vite (hot reload) as a child process
```

- `fitbit serve` starts **one Uvicorn process** that:
  1. serves the REST API under `/api/*`,
  2. serves the **pre-built React app** (static files in `src/fitbit_app/static/`) at `/`,
  3. runs the **APScheduler** sync jobs in the same event loop; each sync is followed by
     rescoring and, in the background, any due AI insight (brief / anomaly note / weekly review),
  4. starts fine without Ollama: AI features check it on demand and the UI shows its status.
- `fitbit serve --dev` additionally launches `npm run dev` for the frontend as a **child
  subprocess** and pipes its logs into the same terminal. Vite proxies `/api` to FastAPI.
  Ctrl+C stops both.
- Ollama is assumed to be running as its normal background service (`ollama serve` /
  systemd). It is an external dependency, not something this app starts.

Other CLI commands (same entry point):

| Command | Purpose |
|---|---|
| `fitbit serve [--dev] [--port 8000] [--host 127.0.0.1]` | Run everything |
| `fitbit sync [--since YYYY-MM-DD] [--types heart-rate,sleep]` | One-off sync / backfill (rescoring follows) |
| `fitbit analyze [--date YYYY-MM-DD \| --all]` | Recompute scores (default: everything on first run, else last 4 days) |
| `fitbit brief [--date] [--kind daily_brief\|weekly_review\|anomaly] [--force]` | Generate an AI insight and print it |
| `fitbit export [--out file.zip] [--intraday]` | ZIP of CSV files (credentials never included) |
| `fitbit build-ui` | `npm run build` into `src/fitbit_app/static/` |
| `fitbit doctor` | Config, DB schema, Google connection, data freshness, UI build, Ollama + model |
| `fitbit db upgrade` | Run Alembic migrations |
| `fitbit db backup [--out DIR]` | Consistent SQLite copy to `data/backups/` (0600) |
| `fitbit db renormalize [--types ...]` | Rebuild typed tables from stored raw JSON (no download) |

The console script is declared in `pyproject.toml`:

```toml
[project.scripts]
fitbit = "fitbit_app.cli:app"
```

**Optional: Docker on a home server.** `Dockerfile` + `compose.yaml` run the same single
process (`fitbit serve`) in one container: the UI is built in a Node stage, the app runs as
a non-root user, `./data` is a mounted volume, settings come from `.env`, and the port is
published on the host's `127.0.0.1` only (reached via SSH tunnel). Ollama stays on the main
machine (`OLLAMA_HOST`). No code differs between the two ways of running. See
[home-server.md](home-server.md).

---

## 4. System architecture

```
                        ┌──────────────────────── your machine ───────────────────────────┐
                        │                                                                  │
 Fitbit Air ──BLE──► Google Health app (phone) ──► Google cloud                            │
                        │                              │                                   │
                        │                              │  HTTPS (OAuth 2.0)                │
                        │                              ▼                                   │
                        │   ┌──────────────── fitbit serve (1 process) ──────────────┐     │
                        │   │                                                         │    │
                        │   │  ingest/         GoogleHealthClient (httpx)             │    │
                        │   │    └─ SyncEngine ── per-type cursors, backfill, retry   │    │
                        │   │           │                                             │    │
                        │   │           ▼                                             │    │
                        │   │  storage/   SQLite (raw data_points + typed tables)     │    │
                        │   │           │                                             │    │
                        │   │           ▼                                             │    │
                        │   │  analytics/ baselines → scores → anomalies → features   │    │
                        │   │           │                                             │    │
                        │   │           ▼                                             │    │
                        │   │  ai/   ContextBuilder → prompts → ollama AsyncClient ───┼──► Ollama
                        │   │           │                   (qwen3.5:9b, localhost)   │   :11434
                        │   │           ▼                                             │    │
                        │   │  api/   FastAPI routers (/api/...) + SSE chat           │    │
                        │   │  web/   static React build at "/"                       │    │
                        │   │  scheduler/ APScheduler jobs                            │    │
                        │   └─────────────────────────────────────────────────────────┘    │
                        │                              ▲                                   │
                        │                     Browser (React UI) http://127.0.0.1:8000     │
                        └──────────────────────────────────────────────────────────────────┘
```

Data flow: **Air → Google Health app → Google cloud → (poll) SyncEngine → SQLite →
analytics → AI → UI.** The app never talks to the band.

---

## 5. Google Health API integration (Option A)

### 5.1 Setup (one-time, manual)
Per https://developers.google.com/health/setup:
1. Create a Google Cloud project and enable the **Google Health API** (`health.googleapis.com`).
2. Create an OAuth client of type **Web application** with redirect URIs
   `http://127.0.0.1:8000/api/auth/callback` and `http://localhost:8000/api/auth/callback`.
3. Audience: External, **Testing**, add yourself as a test user (refresh tokens then expire
   after **7 days**, so the UI offers "Reconnect").
4. Data Access: add the four read scopes below.
5. Put client ID/secret and a Fernet `FITBIT_SECRET_KEY` in `.env`.
6. The Google account must have a Google Health profile (signed in to the Google Health
   mobile app), otherwise the API answers `ACCOUNT_NOT_LINKED`.

Verified API facts (2026-10-29) live in code: base URL and paths in `ingest/endpoints.py`,
scopes in `ingest/scopes.py`. Base URL `https://health.googleapis.com`, user `users/me`.

### 5.2 Auth flow
- Settings → **Connect Google** → `/api/auth/login` builds the consent URL
  (`access_type=offline`, `prompt=consent`, PKCE S256, random `state` kept in memory for 10 min).
- `/api/auth/callback` exchanges the code, calls `GET /v4/users/me/identity` to confirm the
  account is linked, stores tokens, then starts the initial sync in the background.
- Tokens live in `oauth_tokens` (single row). The refresh token is Fernet-encrypted with
  `FITBIT_SECRET_KEY`. Access tokens are refreshed on demand 2 min before expiry.
- A `401` triggers one forced refresh; a rejected refresh (`invalid_grant`) sets
  `needs_reauth` and every later call fails fast until the user reconnects.
- Scopes (read-only): `googlehealth.activity_and_fitness.readonly`,
  `googlehealth.health_metrics_and_measurements.readonly`, `googlehealth.sleep.readonly`,
  `googlehealth.irn.readonly`. Consent is per-scope; missing scopes are shown in Settings.

### 5.3 Data types to sync (Air-relevant)
Source: https://developers.google.com/health/data-types. Table-driven in `ingest/registry.py`.

| Kind | Data types | Read with |
|---|---|---|
| Sample | `heart-rate` (1 s resolution), `heart-rate-variability`, `oxygen-saturation`, `respiratory-rate-sleep-summary`, `vo2-max`, `run-vo2-max`, `weight`, `body-fat` | `reconcile` |
| Interval | `steps`, `distance`, `active-energy-burned`, `activity-level`, `active-zone-minutes`, `sedentary-period`, `active-minutes`, `time-in-heart-rate-zone` | `reconcile` |
| Session | `sleep`, `exercise` (`reconcile`); `irregular-rhythm-notification` (`list` only) | see left |
| Daily | `daily-resting-heart-rate`, `daily-heart-rate-variability`, `daily-oxygen-saturation`, `daily-respiratory-rate`, `daily-sleep-temperature-derivations`, `daily-vo2-max`, `daily-heart-rate-zones` | `reconcile` |
| Daily rollup | `steps`, `distance`, `total-calories`, `active-energy-burned`, `active-zone-minutes` | `dailyRollUp` (≤14-day ranges) |
| Beta (opt-in) | `skin-temperature-sensors` (v4beta, `ENABLE_BETA_TYPES=true`) | `reconcile` |

Corrections vs. the original plan: `basal-energy-burned` does not exist; `total-calories` and
`calories-in-heart-rate-zone` are rollup-only; `moods`, `menstrual-period`, `symptoms` are
**write-only** (cannot be read). Breathing rate *is* available (`daily-respiratory-rate`).

Skipped for the Air: `floors`, `altitude`, `electrocardiogram`, `swim-lengths-data`,
nutrition types. Enabling one is a single registry entry.

**Not available from the API, so we compute our own:** Readiness, Sleep Score, Cardio Load,
stress. BMI and BMR also need to be derived client-side.

### 5.4 Sync strategy
- **Polling, not webhooks.** Webhooks need a public HTTPS URL, which a localhost app doesn't
  have. Could be added later behind a tunnel; out of scope.
- **Sources** (`dataSourceFamily`): sensor data from `google-wearables` (trackers only);
  `weight` / `body-fat` from `all-sources` (smart scales writing via Health Connect are not
  in `google-sources` in practice).
- `sync_state` tracks the synced range `[synced_from, cursor)` per type. Each run does an
  incremental window `[cursor − overlap, now)` (overlap 2 h for samples/intervals, 3 days for
  sessions/daily, which Google revises), then continues any unfinished backfill down to
  `BACKFILL_DAYS` (default **90**) or `fitbit sync --since`. Windows go newest first and state is
  saved after each one, so interrupted runs resume.
- Jobs: intraday kinds every `SYNC_INTERVAL_MIN` (15), sessions/daily/rollups hourly; first
  runs 10 s / 60 s after startup. One sync at a time (shared lock).
- Rate limits: 300 req/min per user; Testing-mode apps 2.5 QPS → client spaces requests at
  `SYNC_REQUESTS_PER_S` (2.0), retries 429/5xx with backoff honouring `Retry-After`.
- One failing data type is recorded in `sync_state.last_error` and does not stop the others.
- Filters use the snake_case type name (`heart_rate.sample_time.physical_time`); the live API
  rejects camelCase for multi-word types. Reconciled points carry no `dataPointName` and no
  heart-rate `motionContext`, so sessions are keyed by start time and `hr_samples.motion_context`
  stays empty (activity context comes from `activity-level` instead).
- Enum labels seen live: activity level `SEDENTARY` / `LIGHTLY_ACTIVE` / `MODERATELY_ACTIVE` /
  `VERY_ACTIVE`; sleep stages `LIGHT` / `DEEP` / `REM` / `AWAKE` (+ `ASLEEP` for classic logs);
  HR zones `LIGHT` / `MODERATE` / `VIGOROUS` / `PEAK`.
- `fitbit db renormalize` re-applies the typed mapping to stored raw JSON after a mapping change.
- Timestamps are stored in **UTC**. Each API point carries its own UTC offset, which is used
  for local-day assignment (e.g. a night belongs to the local date you wake up on).

---

## 6. Storage (SQLite)

`data/fitbit.db` (gitignored). WAL mode for concurrent reads during sync.

| Table | Purpose |
|---|---|
| `oauth_tokens` | Google tokens (single row) |
| `sync_state` | Per-type synced range `[synced_from, cursor)`, last success/error |
| `data_points` | **Raw landing table**: `data_type, start_ts, end_ts, value_json, source_id, ingested_at`. Keeps every type losslessly except heart rate |
| `hr_samples` | `ts, bpm, motion_context`. Heart rate is stored **only** here (no raw JSON): at 1 s resolution raw JSON would be ~10 GB/year |
| `hrv_samples`, `spo2_samples`, `activity_minutes` | Typed intraday series |
| `sleep_sessions`, `sleep_stages` | Session + stage segments |
| `exercise_sessions` | Workouts with HR zone breakdown |
| `daily_metrics` | One row per date: RHR, HRV, SpO2, temp delta, respiratory rate, steps, AZM, calories… |
| `user_profile` | Age, max HR, sleep need (single row) |
| `baselines` | Rolling personal baselines per metric (mean, sd, window) |
| `scores` | One row per date: recovery, strain, sleep_perf, stress, illness_risk + component breakdown JSON |
| `journal_entries` | User tags per day (caffeine, alcohol, late meal, sick, travel, free text) |
| `ai_insights` | Generated briefs/tips: date, kind, model, prompt_hash, content_json, created_at |
| `chat_messages` | Coach conversation history |

The four intraday tables are `WITHOUT ROWID` (migration 0004): keyed by timestamp, so each
row is stored once, clustered by `ts`, instead of a rowid table plus a primary-key index
holding a second copy. Storage grows roughly linearly, about 1 GB a year at 1 s heart rate.

Raw → typed transformation happens in `storage/normalize.py`, so re-normalizing never needs
a re-download.

---

## 7. Analytics engine

Pure functions over pandas DataFrames (`analytics/`). They are easy to unit-test and have
no I/O.

| Module | Output | Method (as built) |
|---|---|---|
| `baselines.py` | Personal norms | 30-day mean/SD over the days *before* the scored day (min 7 days); ln scale for HRV; SD floors so stable stretches don't inflate z-scores |
| `sleep.py` | Sleep performance 0–100 | Duration vs need 45%, efficiency 20% (75%→0, 95%→100), deep+REM share 20% (≥45%→100), bedtime consistency 15% (SD ≤15 min→100, ≥90→0); weights renormalized over available parts |
| `recovery.py` | Recovery 0–100 | 50 ± 20 per SD: HRV 40%, resting HR 25% (inverted), sleep 25%, breathing 10% (inverted); −10 if skin temp ≥ +0.5 °C, −5 if SpO2 z ≤ −2; needs HRV or RHR |
| `strain.py` | Strain 0–21 + target | Banister TRIMP on HR reserve, only time at HRR ≥ 0.3; `21·ln(1+TRIMP)/ln(401)`. Max HR: profile → 208−0.7·age → observed 99.5th pct (clamped 170–210) → 190. Target by recovery: ≥67 → 14–18, ≥34 → 10–14, else 6–10 |
| `stress.py` | Stress timeline 0–100 | Minute HR above resting / 30 bpm, only for SEDENTARY, awake minutes with no activity in the previous 10 min; daily average needs ≥30 minutes |
| `anomaly.py` | Flags + illness risk 0–1 | temp ≥ +0.5 °C, RHR z ≥ 2, HRV z ≤ −1.5, breathing z ≥ 2, SpO2 z ≤ −2; `illness_watch` = temp + a cardio/breathing signal, or any 3; 3-day HRV z ≤ −1 streak |
| `load.py` | Acute:chronic ratio | 7-day / 28-day mean strain (needs 21 days); ≥1.5 `load_spike`, ≤0.8 `load_low` |
| `activity.py` | Sedentary minutes/day | Raw sedentary periods split at local midnight |
| `downsample.py` | Chart series | LTTB (keeps peaks) |
| `correlations.py` | "What affects you" | Journal tag on day D vs outcome on D+1 (recovery, sleep, HRV, RHR); only logged days count; ≥5 days with and without; bootstrap 95% CI; "confident" when it excludes 0 |
| `features.py` | Feature pack for the LLM | See §8.2 |

`scoring.py` (ScoreService) runs these per local day, oldest first, after every sync (all
days on the first run, then the last 4 plus any day with data but no score yet) and via `fitbit analyze`. A local day is defined by
that day's wake-up UTC offset (`daily_metrics.tz_offset_min`), so DST and travel are handled.

Scores are recomputed for affected dates after each sync (sleep revisions shift past days).

---

## 8. AI layer (local Ollama)

### 8.1 Configuration
```
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3.5:9b
OLLAMA_TIMEOUT_S=300
OLLAMA_NUM_CTX=16384
AI_ENABLED=true
```
Local generation is slow compared to page loads, so **all generation is asynchronous and cached**.
The UI never blocks on the LLM except in chat, which streams.

### 8.2 Principle: the LLM never sees raw series
The analytics engine produces numbers; the LLM explains them. `ai/context.py` builds a
small JSON "feature pack" (capped at ~6k characters). Shape as built (values illustrative):

```json
{
  "date": "2026-10-29",
  "scores": {"recovery": 50.4, "sleep_perf": 87.8, "strain_so_far_today": 11.4,
             "strain_yesterday": 7.6, "strain_target_low": 10, "strain_target_high": 14},
  "metrics": {"resting_hr": 57, "hrv_rmssd_ms": 41, "spo2_avg": 96.2, "steps": 8400},
  "vs_baseline_z": {"hrv_rmssd_ms": -0.89, "resting_hr": 0.3},
  "trend_7d": {"recovery": "up", "hrv": "flat", "strain": "down"},
  "sleep": {"bedtime_local": "23:40", "wake_local": "07:12", "asleep_min": 440, "deep_min": 70},
  "flags": [],
  "journal": ["late_meal"],
  "recovery_drivers": {"hrv": 32, "resting_hr": 55, "sleep": 88},
  "known_effects": [{"tag": "alcohol", "next_day_recovery_change": -11.2, "days_with_tag": 9}],
  "workouts": [{"date": "2026-10-28", "type": "strength_training", "duration_min": 45}]
}
```
This keeps prompts fast and grounded, and it reduces hallucinated numbers.

### 8.3 Features
| Feature | Trigger | Output |
|---|---|---|
| **Daily brief** | After a sync, once today's score has last night's sleep (one automatic brief per day; **Regenerate** any time) | Headline, 3–5 sentence summary, 1–3 tips → `ai_insights` |
| **Weekly review** | First sync on a Monday, for the week ending Sunday | Headline, summary vs previous week, wins, watch-outs, one focus |
| **Anomaly note** | After a sync, when today's score has flags | What the signals together could mean, suggestions, when to see a doctor |
| **Coach chat** | User, `POST /api/ai/chat` (SSE) | Conversational answers grounded on today's feature pack + last 7 days |

Triggers piggyback on the post-sync hook (syncs run every 15 min) instead of fixed-time jobs,
so the brief appears as soon as sleep lands. Generation runs as a background task and never
holds up syncing.

### 8.4 Implementation details
- `ai/client.py` (`LLM`): picks `OLLAMA_MODEL`, else `OLLAMA_FALLBACK_MODEL`. Structured
  outputs use `format=<JSON schema>` from the pydantic models in `ai/schemas.py`, validated,
  with one corrective retry. `OLLAMA_THINK` (default off) controls reasoning mode; it is
  dropped automatically for models that don't support it.
- Prompts: `ai/prompts/*.md` rendered by `ai/templates.py` (Jinja2, strict undefined).
  System prompt: coach persona, explains each metric, use only given numbers, never diagnose.
- `ai/context.py`: the feature pack (scores, daily values, z-scores, 7-day trends, flags,
  sleep summary, recovery drivers, recent workouts), capped at ~6k characters by dropping
  optional sections.
- `ai/service.py` (`AIService`): one generation at a time (lock), results deduped by
  `prompt_hash` (model + prompt), chat history in `chat_messages` (last 12 messages sent).
- API: `GET /api/ai/status`, `GET /api/ai/insights?date`, `POST /api/ai/generate {kind, date}`,
  `POST /api/ai/chat` (SSE: `conversation_id`, `delta`…, `done`/`error`),
  `GET /api/ai/chat/{conversation_id}`. CLI: `fitbit brief [--date] [--kind] [--force]`.
- If Ollama is down or `AI_ENABLED=false`, everything else works; AI cards show why.
- Chat **tool calling** (`ai/tools.py`): `get_metric_history`, `get_day_summary`,
  `get_journal`, `get_tag_effects`. Read-only, arguments validated (bad ones are returned to
  the model as an error), ranges capped at 366 days, at most 3 tool rounds per reply.

---

## 9. Backend API (FastAPI)

```
GET  /api/health                          app + db + ollama + google status
GET  /api/session | POST /api/session/login | POST /api/session/logout   (app login, APP_PASSWORD)
GET  /api/auth/login | /api/auth/callback | /api/auth/status | POST /api/auth/logout
GET/PUT /api/profile                      age, max HR, sleep need
POST /api/sync            {types?, since?} trigger sync (background); GET /api/sync/status
GET  /api/today?date                      scores, flags, components, metrics, baseline bands
GET  /api/daily?start&end                 daily metrics + scores per day
GET  /api/trends?metric&days&end          daily series + baseline band
GET  /api/heart?date&points[&start_ms&end_ms]  HR series (LTTB-downsampled; optional window for zoom), RHR, HRV, Google zones
GET  /api/sleep?date | /api/sleep/range?start&end
GET  /api/activity?date                   hourly steps/calories, levels, stress timeline, workouts
GET  /api/exercise?start&end
GET  /api/body?days                      weigh-ins, latest weight/body fat, changes, fat/lean mass
GET  /api/journal?start&end | PUT/DELETE /api/journal/{date} | GET /api/journal/tags
GET  /api/correlations?outcome&days&end   tag effects with 95% CI
GET  /api/ai/status | GET /api/ai/insights?date
POST /api/ai/generate {kind, date}        background (re)generation
POST /api/ai/chat  (text/event-stream)    GET /api/ai/chat/{conversation_id}
GET  /api/export?intraday                 ZIP of CSV files
```

Intraday series are `[epoch_ms, value]` pairs. Day-level dates are local days.

---

## 10. Frontend (React)

| Page | Contents |
|---|---|
| **Today** | 7-day recovery strip; recovery hero (count-up number, status glow + label, coach verdict, "Ask why"), sleep / strain (with target) / stress tiles, flags, activity tiles, "compared with your normal" table, recovery + sleep breakdowns, coach's brief (+ anomaly note, weekly review) |
| **Heart** | Intraday HR with resting line, Google HR zones, 60-day resting HR and HRV trends |
| **Sleep** | Hypnogram, minutes per stage, overnight SpO2 and HRV, breathing rate, skin temperature, last 14 nights |
| **Activity** | Daily totals, steps by hour, minutes per activity level, stress timeline, workouts |
| **Body** | Weight and body fat from a smart scale (via Health Connect → Google Health): latest values, 7/30-day change, fat/lean mass, trends |
| **Trends** | Any metric over 30/90/180/365 days vs baseline band |
| **Journal** | Tag chips (presets + custom) and notes per day, "What affects you" table, last 14 days |
| **Coach** | Streaming chat with the local model (can look up history via tools) |
| **Settings** | Google connection, per-type sync status + backfill, profile, data download, system status, app sign-out (when a password is set) |
| **Login** | Password form shown instead of the app when `APP_PASSWORD` is set and the browser has no session |

App shell (Phase 6, see design.md): Light / Dark / Auto theme toggle, ⌘K command palette,
skip link and focus rings, mobile header + bottom tab bar, and Motion animations (page fade,
staggered cards, count-up numbers, filling meters) that respect the OS reduce-motion setting.
"Ask the coach" links on scores and charts open the Coach page with a prepared question.

Charts: ECharts (tree-shaken, own chunk), reference dataviz palette as CSS tokens (light/dark),
one y-axis per chart, hover tooltips, and a table view on every chart. Chart pages load lazily.

Build output goes to `src/fitbit_app/static/` so the Python package serves it directly.

---

## 11. Repository layout

```
fitbit/
├── README.md · project.md · development-plan.md · task.md · CLAUDE.md
├── pyproject.toml             # deps + [project.scripts] fitbit = "fitbit_app.cli:app"
├── .env.example · alembic.ini
├── data/                      # fitbit.db, logs/, backups/ (gitignored)
├── src/fitbit_app/
│   ├── cli.py                 # Typer: serve, sync, analyze, brief, export, build-ui, doctor, db …
│   ├── config.py              # pydantic-settings (.env)
│   ├── main.py                # app factory, lifespan (DB, scheduler, services), SPA serving
│   ├── devserver.py · doctor.py · logging_setup.py · errors.py
│   ├── scheduler.py           # APScheduler: intraday sync /15 min, daily/sessions hourly
│   ├── scoring.py             # ScoreService: per-day analytics pipeline
│   ├── journal.py             # tag normalization, journal + correlation queries
│   ├── api/                   # health, auth, sync, profile, dashboard, details, journal, ai, export
│   ├── ingest/                # endpoints, scopes, registry, oauth, client, sync, service, timeutil
│   ├── storage/               # db, models, types, migrate, migrations/, upsert, normalize,
│   │                          # queries, export (CSV ZIP + backup)
│   ├── analytics/             # baselines, sleep, recovery, strain, stress, anomaly, load,
│   │                          # activity, correlations, downsample, features (all pure)
│   ├── ai/                    # status, client (LLM), schemas, templates, prompts/*.md,
│   │                          # context, tools, service
│   └── static/                # built React app (gitignored)
├── frontend/src/              # pages/, components/ (charts/, settings/), api/, hooks/,
│                              # format.ts, metrics.ts, navigation.ts
└── tests/                     # mirrors src/; fixtures/ (synthetic data, fake Google API, fake LLM)
```

---

## 12. Setup

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
npm --prefix frontend install
.venv/bin/fitbit build-ui
cp .env.example .env              # add Google OAuth client id/secret
ollama pull qwen3.5:9b            # if not already present
.venv/bin/fitbit serve            # open http://127.0.0.1:8000 → Settings → Connect Google
```

---

## 13. Security and privacy
- Binds to `127.0.0.1` by default. `--host 0.0.0.0` only when you choose to (e.g. over
  Tailscale or the home network).
- **Optional login** (`APP_PASSWORD`, `fitbit_app/login.py`): required whenever the app is
  reachable from other devices. One password; a successful login sets an HttpOnly,
  SameSite=Lax cookie holding an HMAC-signed issue time (valid `SESSION_DAYS`, default 30).
  The key is derived from `FITBIT_SECRET_KEY` and the password, so changing the password signs
  out every device. All `/api` routes need the cookie except `/api/health` and
  `/api/session*`; the built UI files are public and show the login form on 401. At most 5
  wrong passwords per minute. With no password and a non-loopback host, `serve` logs a
  warning and `doctor` warns.
- `.env`, `data/` (DB, logs, backups) and tokens are gitignored. The DB, backups and CLI
  exports are created with permissions `0600`; the refresh token is Fernet-encrypted.
- Logs never contain health values or tokens; OAuth `code`/`state` are redacted from access logs.
- Exports contain health data but never credentials (`oauth_tokens` is excluded); the API
  builds them in `data/` and deletes the temp file after sending.
- The LLM is local. Do not use Ollama `*-cloud` models: they run remotely and would send
  health data off the machine. No health data is sent to any third party besides Google, which is the
  source of the data anyway.
- OAuth app stays in "Testing" mode (personal use; test-user tokens may expire after 7 days
  in Testing mode, which the UI surfaces as "reconnect").

---

## 14. Risks and open questions
| Risk | Mitigation |
|---|---|
| Google Health API is new; types like `skin-temperature-sensors` are **v4beta** | Registry flags per type; beta behind config; tolerate 404/unsupported |
| Endpoint/scope details may change | Single `endpoints.py`/`scopes.py`; `fitbit doctor` validates |
| Historical depth available via API is unknown | Backfill tolerant to empty ranges; log earliest available date |
| Intraday volume (2–5 s HR) | Typed tables with indexes; LTTB downsampling for charts; optional Parquet archive later |
| Local model latency / RAM (qwen3.5:9b ≈ 6.6 GB) | Async + cached generation; configurable smaller model fallback (`OLLAMA_FALLBACK_MODEL`) |
| Testing-mode token expiry | Clear re-auth UX |
| Home-made scores are not validated | Show component breakdowns; label as estimates |

---

## 15. Future research: direct Bluetooth (Option C), documentation only

Not planned for implementation. Recorded here for later.

- The community Flutter plugin **`fitbit_air`** (pub.dev) reverse-engineers the Air's private
  BLE stack: Android BLE → Gattlink → DTLS session → CoAP. It reuses the open-source
  Golden Gate transport.
- What it can do: haptics (tap/vibrate/pulse, strength), live HR stream (only while "Share
  heart rate" is on in Google Health), battery (%/mV/charging), device info, RSSI,
  experimental wrist-presence events. The live activity resource is rejected (`4.01`),
  and there is no tap detection.
- Constraints: **Android-only** (arm64 tested), must run on the phone the Air is paired to
  through Google Health, shares the secure channel with Google Health, can break on any
  firmware update, and is unofficial (possible ToS issues).
- Possible future shape: a small Flutter Android companion app that streams live HR to
  `POST /api/live/hr` (WebSocket) over LAN/Tailscale and polls `GET /api/live/commands` for
  haptic nudges (sedentary reminder, HR-zone alerts, AI-triggered "breathe" cue). The
  backend would need a `live/` module and a WebSocket channel; none of this is in scope
  now.
- Raw PPG/accelerometer/SpO2 signals are **not** reachable by any known route, including this one.
