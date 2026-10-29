# Fitbit Air Companion

A local-first app for the Google Fitbit Air. It pulls your data from the Google Health
API, computes recovery/sleep/strain scores, and writes daily insights with a local Ollama
model.

- Architecture: [project.md](project.md)
- Phases: [development-plan.md](development-plan.md)
- Checklist: [task.md](task.md)
- Build rules: [CLAUDE.md](CLAUDE.md)

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

## Run (one terminal)

```bash
.venv/bin/fitbit serve            # http://127.0.0.1:8000
.venv/bin/fitbit serve --dev      # also starts Vite with hot reload: http://127.0.0.1:5173
```

`serve` creates the database and applies migrations on startup. Ctrl+C stops everything.

## Other commands

```bash
.venv/bin/fitbit doctor           # check config, database, UI build, Ollama
.venv/bin/fitbit db upgrade       # apply database migrations manually
.venv/bin/fitbit build-ui         # rebuild the frontend into the Python package
```

## Tests

```bash
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

## Troubleshooting
- **"UI not built" page**: run `.venv/bin/fitbit build-ui`.
- **`serve --dev` says node_modules is missing**: run `npm --prefix frontend install`.
- **Ollama warnings in `doctor`**: start Ollama, and pull the model named in `OLLAMA_MODEL`.
  The app works without AI; only AI features are disabled.
