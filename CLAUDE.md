# CLAUDE.md: Build rules for this project

Rules for anyone (human or AI) building this repo. Read [project.md](project.md) for the
architecture and [task.md](task.md) for the checklist before starting work.

---

## 1. Workflow and permissions

- **Commit locally without asking.** Make a commit after each completed task or coherent
  change. Small, focused commits.
- **Never push** to any remote, and never add a remote, create a GitHub repo, or open PRs.
- **Never install anything without asking first.** That covers pip, npm, system packages,
  and `ollama pull`. Editing `pyproject.toml` / `package.json` to declare a dependency is
  fine; actually installing it is not.
- **Never execute project code without asking first.** That covers `fitbit ...`, uvicorn,
  `npm run ...`, pytest, alembic, Python scripts, and anything that hits Google or Ollama.
  Read-only shell commands (`ls`, `cat`, `grep`, `git status/diff/log`) and `git add`/`git commit`
  are fine.
- **Follow `task.md` order.** Mark a box `[~]` when starting and `[x]` when done (including its
  tests), in the same commit as the work.
- **Stay in scope.** Implement what the task says. Don't add features, refactor unrelated
  code, or "improve" the plan on the side. Suggest it instead.
- **Don't change the tech stack** (project.md §2) or the architecture without asking. If a
  task can't be done as planned, stop and explain why.
- When `project.md` and the code disagree, ask which one is right, then update the other so
  they match.

### Commit messages
```
<area>: <imperative summary, ≤ 72 chars>

<optional body: what and why>
```
Areas: `cli`, `api`, `ingest`, `storage`, `analytics`, `ai`, `scheduler`, `frontend`,
`tests`, `docs`, `build`. Example: `ingest: add SyncEngine with per-type cursors`.

---

## 2. Boundaries

- **Google Health API details** (base URL, endpoint paths, scope strings, field names) must
  come from the official docs at `developers.google.com/health`, never from memory or
  guesses. Keep them only in `ingest/endpoints.py` and `ingest/scopes.py`. If something
  can't be verified, leave a `# TODO(verify): ...` comment and say so.
- **Option C (direct Bluetooth / `fitbit_air` plugin) is out of scope.** It is documentation only
  (project.md §15). Write no code for it.
- **No webhooks**; sync is by polling.
- **The LLM never receives raw time series**, only the feature pack from
  `analytics/features.py` / `ai/context.py`.
- **No medical claims.** AI output and UI copy are informational. No diagnoses.
- The app must keep working when Ollama is unreachable or AI is disabled.
- `.venv/bin/fitbit serve` must stay the single command that runs the app. Don't introduce
  anything that needs a second terminal (no separate worker, DB server, or queue).

---

## 3. Testing: pytest only

- **pytest is the only test framework.** No Vitest, Jest, Playwright, Cypress, or other
  runners. (pytest-asyncio and respx plugins are allowed.)
- Every backend module task needs tests before it is marked done:
  - `analytics/*`: unit tests over **synthetic data** (from a shared generator in
    `tests/fixtures/`), including edge cases: missing days, no sleep, partial data,
    timezone/midnight crossing.
  - `ingest/*`: mock HTTP with **respx**. Use hand-written fake responses shaped like the
    documented API. **No real network calls** in tests.
  - `storage/*`: temp SQLite DB per test (`tmp_path`).
  - `ai/*`: mock the Ollama client. **Never call a real model** in tests. Test prompt building,
    schema validation, retry-on-invalid-JSON, and degradation when Ollama is down.
  - `api/*`: FastAPI `TestClient` / `httpx.AsyncClient` with dependency overrides.
- **Never use real health data** in tests or fixtures, and never commit it.
- Layout: `tests/` mirrors `src/fitbit_app/` (`tests/analytics/test_recovery.py` etc.).
- Writing tests is always fine; **running** them requires asking (see §1).
- The frontend has no automated tests. Keep logic out of components (in `src/api/` and small
  pure helpers) so the UI stays thin.

---

## 4. Python conventions

- Python **3.12**, src layout, package `fitbit_app`.
- **Type hints everywhere** (public and private functions). Use built-in generics
  (`list[int]`, `X | None`).
- Format and lint with **ruff** (line length 100). Code should pass `ruff check` and `ruff format`.
- Naming: `snake_case` functions/modules, `PascalCase` classes, `UPPER_SNAKE` constants.
- **Async** for all I/O (httpx, Ollama, DB access from request handlers). Never block the event
  loop. Run CPU-heavy pandas work via `asyncio.to_thread`.
- **Analytics modules are pure functions**: DataFrame/values in, results out, with no DB,
  network, or clock access. Pass "today" in explicitly.
- Settings only through `config.py` (pydantic-settings). No `os.environ` reads elsewhere and no
  hard-coded paths, URLs, or model names.
- Pydantic models for API request/response bodies and LLM output schemas.
- SQLAlchemy 2.0 style (`select()`, typed `Mapped[...]`). **Every schema change gets an Alembic
  migration**; never edit an applied migration.
- All timestamps are **timezone-aware UTC** in storage. Convert to local time only at the edges
  (local-day assignment, API responses).
- Errors: raise specific exceptions (`fitbit_app.errors`). Catch at boundaries (API handlers,
  scheduler jobs, CLI) and log them there. No bare `except:`; no silently swallowed errors.
- Logging via the `logging` module (`logger = logging.getLogger(__name__)`), no `print` outside
  `cli.py`.
- Comments explain *why*, not *what*. Docstrings on public functions, short.
- Keep functions small. No new abstraction layers "for the future".

## 5. Frontend conventions

- React 18 + TypeScript **strict**, Vite, Tailwind, TanStack Query, React Router, ECharts.
- Function components + hooks only. Files: `PascalCase.tsx` for components, `camelCase.ts`
  otherwise.
- All server calls go through the typed client in `frontend/src/api/`. Components never call
  `fetch` directly.
- No secrets or tokens in frontend code. The backend owns all Google and Ollama access.
- Build output goes to `src/fitbit_app/static/` (gitignored), never committed.
- ESLint clean.

---

## 6. Security and privacy

- **Never commit** `.env`, `data/`, `*.db`, tokens, or exported health data. Check `git status`
  before each commit.
- **Never log** health values, tokens, client secrets, or full API responses. Log types,
  counts, date ranges, and status codes instead.
- Refresh tokens are stored encrypted (Fernet, key from `.env`). The DB file has permissions `0600`.
- Bind to `127.0.0.1` by default.
- Health data goes nowhere except Google (its source) and the local Ollama instance. Add no
  telemetry, analytics SDKs, CDNs, or external fonts.

---

## 7. Dependencies

- Use only the libraries listed in project.md §2. Adding a new one requires asking first, with
  a one-line justification.
- Pin minimum versions in `pyproject.toml` (`>=`); exact versions in `package-lock.json`.

---

## 8. Definition of done (per task)

1. Code implements the task as described in `task.md` / `project.md`.
2. pytest tests written for it (backend), using mocks/synthetic data only.
3. Type hints present, no obvious ruff issues.
4. No secrets or health data added. Logs are clean.
5. `task.md` checkbox updated, and `project.md` updated if the design changed (with approval).
6. Committed locally with a proper message. Not pushed.
7. Ask the user before running tests or the app to verify.
