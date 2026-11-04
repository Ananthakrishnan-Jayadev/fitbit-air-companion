# Fitbit Air companion: one container running `fitbit serve` (API, UI, scheduled sync).
# Build: docker compose build   Run: docker compose up -d   (see home-server.md)

# --- Stage 1: build the React UI into src/fitbit_app/static ---------------------------------
FROM node:22-bookworm-slim AS ui
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json frontend/
RUN npm --prefix frontend ci
COPY frontend/ frontend/
RUN npm --prefix frontend run build

# --- Stage 2: Python runtime -----------------------------------------------------------------
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Match the host user that owns ./data so the 0600 database stays readable to us only.
ARG UID=1000
ARG GID=1000
RUN groupadd --gid "${GID}" app && useradd --uid "${UID}" --gid "${GID}" --create-home app

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ src/
COPY --from=ui /build/src/fitbit_app/static/ src/fitbit_app/static/
RUN pip install . && rm -rf src

# Inside the container the app must listen on all interfaces so the published port reaches it.
# compose.yaml publishes that port on the host's 127.0.0.1 only.
ENV HOST=0.0.0.0 \
    PORT=8000 \
    DATA_DIR=/app/data

RUN mkdir -p /app/data && chown app:app /app/data
USER app
VOLUME ["/app/data"]
EXPOSE 8000

HEALTHCHECK --interval=60s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"

CMD ["fitbit", "serve"]
