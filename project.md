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
- Use a **local Ollama model** (`gemma4:31b` by default) for a daily brief, tips, and
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
| OAuth | **authlib** (or google-auth-oauthlib) | Google OAuth 2.0 auth-code flow with refresh tokens |
| Database | **SQLite** (WAL mode) via **SQLAlchemy 2.0** + **Alembic** | No DB server, which keeps it to one process |
| Analytics | **pandas + numpy** (scipy if needed) | Baselines, rolling stats, scoring |
| Scheduling | **APScheduler** (AsyncIOScheduler, in-process) | Periodic sync and nightly analysis without a second process |
| AI | **ollama** Python client (`AsyncClient`) | Local LLM; structured JSON output + streaming |
| Config | **pydantic-settings** + `.env` | Typed settings |
| Frontend | **React 18 + Vite + TypeScript** | |
| UI data | **TanStack Query**, **React Router** | Caching and routing |
| Charts | **Apache ECharts** (`echarts-for-react`) | Handles large intraday series (tens of thousands of points) |
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
  3. runs the **APScheduler** jobs (sync + analysis + AI brief) inside the same event loop,
  4. checks on startup that Ollama is reachable and the model is present (warns, does not crash).
- `fitbit serve --dev` additionally launches `npm run dev` for the frontend as a **child
  subprocess** and pipes its logs into the same terminal. Vite proxies `/api` to FastAPI.
  Ctrl+C stops both.
- Ollama is assumed to be running as its normal background service (`ollama serve` /
  systemd). It is an external dependency, not something this app starts.

Other CLI commands (same entry point):

| Command | Purpose |
|---|---|
| `fitbit serve [--dev] [--port 8000] [--host 127.0.0.1]` | Run everything |
| `fitbit sync [--since 2026-09-01] [--types heart-rate,sleep]` | One-off sync / backfill |
| `fitbit analyze [--date YYYY-MM-DD]` | Recompute scores |
| `fitbit brief [--date]` | Regenerate the AI daily brief |
| `fitbit build-ui` | `npm --prefix frontend run build` → copies into `static/` |
| `fitbit doctor` | Checks config, DB, Google token, Ollama + model |
| `fitbit db upgrade` | Run Alembic migrations |

The console script is declared in `pyproject.toml`:

```toml
[project.scripts]
fitbit = "fitbit_app.cli:app"
```

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
                        │   │           │                   (gemma4:31b, localhost)   │   :11434
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
1. Create a Google Cloud project and enable the **Google Health API**.
2. Configure the OAuth consent screen (External, **Testing** mode, add yourself as a test user).
3. Create an OAuth client (type **Web application**) with redirect URI
   `http://127.0.0.1:8000/api/auth/callback`.
4. Put the client ID and secret in `.env`.

> Exact scope strings, base URL, and endpoint paths must be copied from the official docs
> (`developers.google.com/health`) during implementation. They are deliberately **not**
> hard-coded in this plan, to avoid guessing. Keep them in a single `ingest/scopes.py` /
> `ingest/endpoints.py` module.

### 5.2 Auth flow
- Settings page has a **Connect Google** button that hits `/api/auth/login`, which redirects to
  Google consent → `/api/auth/callback` stores tokens.
- Tokens live in the SQLite `oauth_tokens` table. The DB file is created with `0600`
  permissions, and the refresh token is optionally encrypted with a key from `.env`
  (`FITBIT_SECRET_KEY`, Fernet).
- `GoogleHealthClient` refreshes access tokens automatically and handles `401` by
  refreshing once, then marking the connection "needs re-auth".

### 5.3 Data types to sync (Air-relevant)

| Group | Data types | Granularity |
|---|---|---|
| Heart | `heart-rate`, `heart-rate-variability`, `daily-resting-heart-rate`, `daily-heart-rate-variability`, `irregular-rhythm-notification` | intraday + daily |
| Oxygen | `oxygen-saturation`, `daily-oxygen-saturation` | minute-level (sleep) + daily |
| Temperature | `daily-sleep-temperature-derivations`, `skin-temperature-sensors` (**v4beta**, behind a config flag) | nightly |
| Sleep | `sleep` (sessions + stages) | session |
| Activity | `steps`, `distance`, `activity-level`, `active-energy-burned`, `basal-energy-burned`, `total-calories`, `active-zone-minutes`, `calories-in-heart-rate-zone`, `sedentary-period` | intraday / interval |
| Workouts | `exercise`, `vo2-max`, `run-vo2-max` | session |
| Manual logs | `weight`, `body-fat`, `height`, `nutrition-log`, `moods`, `menstrual-period`, `symptoms` | event |

Skipped for the Air (no hardware for them): `floors`, `altitude`, `electrocardiogram`,
`swim-lengths-data`. The design is table-driven, so enabling them later is one line in
`ingest/registry.py`.

**Not available from the API, so we compute our own:** Readiness, Sleep Score, Cardio Load,
stress. BMI and BMR also need to be derived client-side.

### 5.4 Sync strategy
- **Polling, not webhooks.** Webhooks need a public HTTPS URL, which a localhost app doesn't
  have. Webhooks could be added later behind a tunnel (Tailscale Funnel / cloudflared),
  but that is out of scope.
- `sync_state` table stores a per-data-type cursor (last synced end time).
- Jobs:
  - every **15 min**: incremental sync of intraday types (cursor → now, with a 2 h overlap
    to catch late-arriving phone syncs).
  - every **hour**: sessions + daily types for the last 3 days (sleep/HRV get revised).
  - **first run / `fitbit sync --since`**: backfill in day-sized chunks, newest first.
- Idempotent upserts keyed on `(data_type, start_time, end_time, source_id)`.
- Respect rate limits: token bucket in the client, exponential backoff on `429`/`5xx`.
- Use the `dataSourceFamily` filter to keep only device-sourced data where it matters.
- All timestamps are stored in **UTC**, along with the user's timezone offset at the time
  (needed for "day" boundaries and sleep that crosses midnight).

---

## 6. Storage (SQLite)

`data/fitbit.db` (gitignored). WAL mode for concurrent reads during sync.

| Table | Purpose |
|---|---|
| `oauth_tokens` | Google tokens (single row) |
| `sync_state` | Per-type cursor, last success/error |
| `data_points` | **Raw landing table**: `data_type, start_ts, end_ts, value_json, source_id, ingested_at`. Keeps everything losslessly |
| `hr_samples` | `ts, bpm`, a typed hot path for intraday HR (indexed by ts) |
| `hrv_samples`, `spo2_samples`, `activity_minutes` | Typed intraday series |
| `sleep_sessions`, `sleep_stages` | Session + stage segments |
| `exercise_sessions` | Workouts with HR zone breakdown |
| `daily_metrics` | One row per date: RHR, HRV, SpO2, temp delta, steps, AZM, calories… |
| `baselines` | Rolling personal baselines per metric (mean, sd, window) |
| `scores` | One row per date: recovery, strain, sleep_perf, stress, illness_risk + component breakdown JSON |
| `journal_entries` | User tags per day (caffeine, alcohol, late meal, sick, travel, free text) |
| `ai_insights` | Generated briefs/tips: date, kind, model, prompt_hash, content_json, created_at |
| `chat_messages` | Coach conversation history |

Raw → typed transformation happens in `storage/normalize.py`, so re-normalizing never needs
a re-download.

---

## 7. Analytics engine

Pure functions over pandas DataFrames (`analytics/`). They are easy to unit-test and have
no I/O.

| Module | Output | Method (initial) |
|---|---|---|
| `baselines.py` | Personal norms | 30-day rolling mean/SD for RHR, HRV (ln rMSSD), SpO2, temp delta, sleep duration. 7-day short window for trend |
| `sleep.py` | Sleep performance 0–100 | Duration vs need, efficiency, deep+REM share, consistency (bedtime SD), awakenings |
| `recovery.py` | Recovery 0–100 | Weighted z-scores: HRV ↑, RHR ↓, sleep perf, temp delta, SpO2 dip penalty |
| `strain.py` | Strain 0–21 + daily target | Banister TRIMP from intraday HR using HR reserve (RHR + estimated max HR), log-scaled. Target from recovery |
| `stress.py` | Intraday stress timeline | HR elevated vs resting baseline **while `activity-level` is sedentary**, so non-exercise arousal |
| `anomaly.py` | Illness / overreach flags | Multi-signal rule: temp delta > +0.5 °C **and** RHR > baseline + 2 SD **and/or** HRV < baseline − 1.5 SD, SpO2 drop |
| `load.py` | Acute:chronic workload | 7-day vs 28-day strain ratio, which flags spikes |
| `correlations.py` | "What affects you" | Journal tags vs next-day recovery/sleep (mean difference + bootstrap CI, minimum N) |
| `features.py` | **Compact feature summary** for the LLM | See §8.2 |

Scores are recomputed for affected dates after each sync (sleep revisions shift past days).

---

## 8. AI layer (local Ollama)

### 8.1 Configuration
```
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=gemma4:31b
OLLAMA_TIMEOUT_S=300
OLLAMA_NUM_CTX=16384
AI_ENABLED=true
```
A 31B model is slow on consumer hardware, so **all generation is asynchronous and cached**.
The UI never blocks on the LLM except in chat, which streams.

### 8.2 Principle: the LLM never sees raw series
The analytics engine produces numbers; the LLM explains them. `ai/context.py` builds a
small JSON "feature pack" (~1–3k tokens):

```json
{
  "date": "2026-10-29",
  "scores": {"recovery": 62, "sleep_perf": 71, "strain_yesterday": 13.4, "strain_target": [10, 13]},
  "vs_baseline": {"hrv_z": -1.1, "rhr_z": 0.8, "temp_delta_c": 0.3, "spo2_avg": 95.8},
  "sleep": {"duration_h": 6.4, "deep_pct": 14, "rem_pct": 19, "bedtime_shift_min": 48},
  "trend_7d": {"hrv": "down", "rhr": "up", "sleep_duration": "flat"},
  "flags": ["hrv_suppressed_2_days"],
  "journal": {"yesterday": ["alcohol", "late_meal"]},
  "known_correlations": [{"tag": "alcohol", "effect": "recovery -11 (n=9)"}]
}
```
This keeps prompts fast and grounded, and it reduces hallucinated numbers.

### 8.3 Features
| Feature | Trigger | Output |
|---|---|---|
| **Daily brief** | Scheduler, after morning sleep data lands (first sync after wake, or 09:00 fallback) | 3–5 sentence summary + 3 actionable tips, stored in `ai_insights` |
| **Weekly review** | Monday 09:00 | Trends, wins, one focus for the week |
| **Anomaly explainer** | When `anomaly.py` raises a flag | Plain-language "what this might mean / what to watch" (non-diagnostic) |
| **Coach chat** | User, `/api/ai/chat` (SSE streaming) | Conversational Q&A grounded on the feature pack plus recent insights |

### 8.4 Implementation details
- `ollama.AsyncClient(host=...)`. Structured outputs use `format=<JSON schema>` (pydantic
  model `.model_json_schema()`) for briefs/tips, validated with pydantic and retried once
  on invalid JSON.
- Prompt templates live in `ai/prompts/*.md` (Jinja2) with a fixed system prompt: coach
  persona, cite only the provided numbers, no diagnoses, suggest seeing a doctor for
  persistent anomalies.
- Chat: last N messages + fresh feature pack injected as system context. Later
  enhancement: Ollama **tool calling** so the model can request `get_metric(name, range)`
  and answer questions like "how did my HRV look in September?"
- `ai_insights.prompt_hash` dedupes: the same features produce no regeneration.
- `/api/ai/status` reports Ollama reachability, model presence (`client.list()`), last error.
- If Ollama is down, the app works fully without AI. The UI shows a banner.

---

## 9. Backend API (FastAPI)

```
GET  /api/health                         app + db + ollama + google status
GET  /api/auth/login | /api/auth/callback | POST /api/auth/logout
POST /api/sync            {types?, since?}   trigger sync (runs as background task)
GET  /api/sync/status
GET  /api/today                          scores + key metrics + latest brief
GET  /api/daily?from&to                  daily_metrics + scores
GET  /api/heart/intraday?date            HR series (downsampled server-side via LTTB if > N points)
GET  /api/sleep?date | /api/sleep/range?from&to
GET  /api/activity?date
GET  /api/exercise?from&to
GET  /api/trends?metric&window
GET  /api/correlations
GET/POST/DELETE /api/journal
GET  /api/ai/insights?date&kind
POST /api/ai/brief/regenerate {date}
POST /api/ai/chat  (text/event-stream)
GET  /api/ai/status
GET/PUT /api/settings                    sync interval, max HR, sleep need, AI on/off
```

---

## 10. Frontend (React)

| Page | Contents |
|---|---|
| **Today** | Recovery / Sleep / Strain rings, strain target, AI brief + tips, flags |
| **Heart** | Intraday HR (ECharts, zoomable), HRV, RHR trend, zones, AFib notifications |
| **Sleep** | Hypnogram, stage %, SpO2 overnight, temp delta, consistency chart |
| **Activity** | Steps/AZM/calories, sedentary periods, stress timeline, workouts list |
| **Trends** | Any metric over 7/30/90/365 days vs baseline band |
| **Journal** | Daily tags + notes; "what affects you" correlations |
| **Coach** | Streaming chat with the local model |
| **Settings** | Connect Google, sync status/backfill, Ollama status/model, profile (age, max HR, sleep need) |

Build output goes to `src/fitbit_app/static/` so the Python package serves it directly.

---

## 11. Repository layout

```
fitbit/
├── project.md                 # this file
├── task.md                    # implementation checklist
├── README.md
├── pyproject.toml             # deps + [project.scripts] fitbit = "fitbit_app.cli:app"
├── .env.example
├── alembic.ini
├── data/                      # sqlite db + logs (gitignored)
├── src/fitbit_app/
│   ├── cli.py                 # Typer: serve, sync, analyze, brief, build-ui, doctor, db
│   ├── config.py              # pydantic-settings
│   ├── main.py                # FastAPI app factory, lifespan (scheduler start/stop), static mount
│   ├── devserver.py           # spawns/stops Vite child process for --dev
│   ├── api/                   # routers: auth, sync, today, heart, sleep, activity, trends, journal, ai, settings
│   ├── ingest/
│   │   ├── client.py          # GoogleHealthClient (httpx, retries, rate limit)
│   │   ├── oauth.py
│   │   ├── endpoints.py       # base URL + paths (from official docs)
│   │   ├── scopes.py
│   │   ├── registry.py        # data type → endpoint, granularity, normalizer, enabled
│   │   └── sync.py            # SyncEngine
│   ├── storage/
│   │   ├── db.py              # engine/session, WAL pragma
│   │   ├── models.py          # SQLAlchemy models
│   │   ├── normalize.py       # raw data_points → typed tables
│   │   └── migrations/        # alembic
│   ├── analytics/             # baselines, sleep, recovery, strain, stress, anomaly, load, correlations, features
│   ├── ai/
│   │   ├── client.py          # Ollama wrapper
│   │   ├── context.py         # feature pack builder
│   │   ├── schemas.py         # pydantic output schemas
│   │   ├── service.py         # brief, weekly, explainer, chat
│   │   └── prompts/*.md
│   ├── scheduler.py           # APScheduler job definitions
│   └── static/                # built React app (gitignored)
├── frontend/
│   ├── package.json
│   ├── vite.config.ts         # outDir ../src/fitbit_app/static, proxy /api → :8000
│   └── src/{pages,components,api,hooks}/
└── tests/                     # pytest: analytics (synthetic data), normalize, API
```

---

## 12. Setup (once implemented)

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
npm --prefix frontend install
.venv/bin/fitbit build-ui
cp .env.example .env              # add Google OAuth client id/secret
ollama pull gemma4:31b            # if not already present
.venv/bin/fitbit serve            # open http://127.0.0.1:8000 → Settings → Connect Google
```

---

## 13. Security and privacy
- Binds to `127.0.0.1` by default. `--host 0.0.0.0` only when you choose to (e.g. over
  Tailscale).
- `.env`, `data/` and tokens are gitignored. The DB file is created with permissions `0600`.
- The LLM is local. No health data is sent to any third party besides Google, which is the
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
| `gemma4:31b` latency / RAM | Async + cached generation; configurable smaller model fallback (`OLLAMA_FALLBACK_MODEL`) |
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
