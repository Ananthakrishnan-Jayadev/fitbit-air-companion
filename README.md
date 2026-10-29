# Fitbit Air Companion

A local-first app for the Google Fitbit Air. It pulls your data from the Google Health
API, computes recovery/sleep/strain scores, and writes daily insights with a local Ollama
model.

- Architecture (as built): [project.md](project.md)
- Original phase plan: [development-plan.md](development-plan.md)
- Checklist + next steps: [task.md](task.md)
- Build rules: [CLAUDE.md](CLAUDE.md)

## What it does
- **Syncs** everything the Fitbit Air exposes through the Google Health API (heart rate at
  ~3 s resolution, HRV, SpO2, breathing rate, skin temperature, sleep stages, activity,
  workouts), 90 days back, then every 15 min / hourly. Stored locally in SQLite.
- **Scores** each day against your own 30-day baseline: recovery, sleep, strain (with a
  daily target), stress, and illness / overreach warnings.
- **Pages:** Today, Heart, Sleep, Activity, Trends, Journal ("what affects you"), Coach,
  Settings. Every chart has a table view.
- **Local AI coach** (Ollama, default `qwen3.5:9b`): daily brief, weekly review, anomaly
  notes, and a chat that can look up your history. It sees summaries only, never raw data,
  and nothing leaves your machine except the Google sync itself.

## Requirements
- Python 3.12+
- Node.js 20+ and npm (only to build the UI)
- [Ollama](https://ollama.com) running locally, with the model from `.env` pulled

## Setup

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
npm --prefix frontend install
.venv/bin/fitbit build-ui
cp .env.example .env              # then fill in values
ollama pull qwen3.5:9b            # if not already present
```

**Google access (one-time):** create a Google Cloud project with the Google Health API, a
*Web application* OAuth client and yourself as a test user, then put the client ID/secret and
a `FITBIT_SECRET_KEY` in `.env`. Step-by-step: [project.md §5.1](project.md#51-setup-one-time-manual).
Then run `fitbit serve` and use **Settings → Connect Google**.

## Run (one terminal)

```bash
.venv/bin/fitbit serve            # http://127.0.0.1:8000
.venv/bin/fitbit serve --dev      # also starts Vite with hot reload: http://127.0.0.1:5173
```

`serve` creates the database and applies migrations on startup. Ctrl+C stops everything.

## Other commands

```bash
.venv/bin/fitbit doctor                      # check config, DB, Google, data freshness, UI, Ollama
.venv/bin/fitbit sync [--since YYYY-MM-DD]   # sync now / backfill further back
.venv/bin/fitbit analyze [--all | --date D]  # recompute scores
.venv/bin/fitbit brief [--kind K] [--force]  # write an AI brief / weekly_review / anomaly note
.venv/bin/fitbit export [--intraday]         # ZIP of CSV files (never includes credentials)
.venv/bin/fitbit db backup                   # consistent copy of the DB in data/backups
.venv/bin/fitbit db renormalize              # rebuild typed tables from stored raw data
.venv/bin/fitbit db upgrade                  # apply database migrations manually
.venv/bin/fitbit build-ui                    # rebuild the frontend into the Python package
```

Logs: console, plus `data/logs/fitbit.log` (rotated at 5 MB, 3 kept). Logs never contain
health values or tokens.

## Tests

```bash
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
npm --prefix frontend run lint
```

## Troubleshooting
- **"UI not built" page**: run `.venv/bin/fitbit build-ui`.
- **`serve --dev` says node_modules is missing**: run `npm --prefix frontend install`.
- **`redirect_uri_mismatch` when connecting Google**: the OAuth client's Authorized redirect
  URIs must contain `http://127.0.0.1:8000/api/auth/callback` exactly (no trailing slash), and
  you must open the app at `127.0.0.1`, matching `GOOGLE_REDIRECT_URI`.
- **"Account not linked"**: sign in to the Google Health mobile app with the same account first.
- **Banner says the Google connection expired**: normal in Testing mode (refresh tokens last
  7 days). Settings → Reconnect Google. Syncing resumes where it stopped.
- **A data type shows "Error" in Settings → Sync**: hover it for the message; the log has
  `Sync of <type> failed: ...`. Other types keep syncing.
- **`doctor` says data is stale**: is `fitbit serve` running and Google connected? Run
  `fitbit sync` to see errors directly.
- **Ollama warnings in `doctor`**: start Ollama, and pull the model named in `OLLAMA_MODEL`.
  The app works without AI; only AI features are disabled.
- **Brief fails with "did not return valid structured output"**: the log line lists the
  failing fields. Re-run `fitbit brief --force`; if it persists, try `OLLAMA_THINK=true`
  (slower, follows the format strictly). Never use `*-cloud` models: they send data off-machine.
- **Scores look off after changing your age / max HR**: run `fitbit analyze --all`.
- **"What affects you" is empty**: it needs at least 5 tagged days with and 5 without a tag.
