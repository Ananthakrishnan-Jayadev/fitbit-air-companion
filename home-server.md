# Home server: run the app 24/7 in Docker on a spare laptop

The app runs as a Docker container on an always-on home server (an old laptop), so data keeps
syncing while your main machine is off. Ollama stays on the main machine, which has the GPU.
You reach the app from the main machine through SSH.

## Why not a cloud host (Vercel + Supabase)?

The app is built to run as one long process on a machine you control. Vercel doesn't fit
that model:

| Part of the app | Problem on Vercel |
|---|---|
| Background sync (every 15 min / hourly) | Serverless functions only run per request; nothing runs in between. |
| Backfill / long syncs | The first sync takes minutes and exceeds function time limits. |
| Local AI (Ollama) | Vercel can't reach Ollama on your machine; a hosted LLM would send health data to a third party. |
| No login | The app has no authentication because it only listens locally. A public URL would expose your health data and your Google connection. |
| SQLite-specific code | Upserts, pragmas, file permissions and backups are SQLite-specific and would need porting to Postgres. |

It would also break the project rule that health data goes nowhere except Google and the
local Ollama instance (CLAUDE.md §6).

## Target setup

```
 Main machine (GPU)                              Home server (always on, Docker)
 ──────────────────                              ───────────────────────────────
 browser ── http://127.0.0.1:8000                container "fitbit" (fitbit serve)
    │                                             ├─ sync every 15 min ──▶ Google Health
    └── SSH tunnel ─────────────────────────────▶ ├─ scoring, SQLite in ./data
                                                  └─ UI + API on server's 127.0.0.1:8000
 ollama serve (qwen3.5:9b)  ◀── AI requests ──────┘   (OLLAMA_HOST)
```

| Machine | Runs | Notes |
|---|---|---|
| Home server | `fitbit` container: sync, scoring, database, UI | ~300–600 MB RAM; port published on its loopback only |
| Main machine | Ollama with `qwen3.5:9b` | Needs ~6–7 GB free RAM/VRAM for the model |

**When the main machine is off:** sync, scores and charts keep working. The AI brief and
Coach show as unavailable, and the brief for a missed day is written once Ollama is back.

**One copy only:** run the app on the server *or* the main machine, never both. Two copies
would both sync and their databases would diverge.

## What's in the repo

| File | Purpose |
|---|---|
| `Dockerfile` | Two stages: Node builds the UI, then a slim Python 3.12 image installs the app and runs `fitbit serve` as a non-root user |
| `compose.yaml` | Service `fitbit`: settings from `.env`, `./data` mounted at `/app/data`, port published on `127.0.0.1` only, `restart: unless-stopped`, rotated logs |
| `.dockerignore` | Keeps `.env`, `data/`, databases, `.git` and `node_modules` out of the image |

The image contains no secrets or health data: `.env` is read at run time and `data/` is a
mounted folder on the server.

## Steps

Replace `server` with however you SSH into the home server (e.g. `user@192.168.1.50`).

### 1. On the main machine: stop the app and back up

```bash
# stop `fitbit serve` (Ctrl+C), then:
.venv/bin/fitbit db backup
```

### 2. Put the code on the server

```bash
ssh server 'git clone https://github.com/Ananthakrishnan-Jayadev/fitbit-air-companion.git ~/server/fitbit'
```

If the repo is private (or you don't want git credentials on the server), copy it instead:

```bash
rsync -a --exclude .venv --exclude frontend/node_modules --exclude data --exclude .env \
  ./ server:~/server/fitbit/
```

### 3. Copy settings and data

```bash
scp .env server:~/server/fitbit/.env
rsync -a --exclude backups data/ server:~/server/fitbit/data/
ssh server 'chmod 600 ~/server/fitbit/.env ~/server/fitbit/data/*.db; id -u; id -g'
```

`.env` and `data/` must go together: the saved Google token is encrypted with
`FITBIT_SECRET_KEY` from `.env`.

The container runs as UID/GID 1000. If `id -u` / `id -g` on the server print something else,
build with your IDs in step 6: `UID=$(id -u) GID=$(id -g) docker compose up -d --build`.

### 4. Edit the server's `.env`

```bash
OLLAMA_HOST=http://<main-machine-ip>:11434
TZ=America/Toronto        # optional: timestamps in container logs
```

`HOST`, `PORT` and `DATA_DIR` are set by `compose.yaml`, so their `.env` values don't matter
here. Keep `GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/api/auth/callback` (see step 7).

Use the main machine's LAN IP, or its Tailscale IP if both machines are on Tailscale (that
also works away from home). A DHCP reservation on the router keeps the LAN IP stable.

### 5. On the main machine: let the server reach Ollama

By default Ollama only listens on localhost:

```bash
sudo systemctl edit ollama
#   [Service]
#   Environment="OLLAMA_HOST=0.0.0.0"
sudo systemctl restart ollama
```

Ollama has no password, so allow port 11434 **only from the server**:

```bash
sudo ufw allow from <server-ip> to any port 11434 proto tcp
sudo ufw deny 11434/tcp
sudo ufw enable            # if ufw isn't on yet; check `sudo ufw status` first
```

(With Tailscale: `sudo ufw allow in on tailscale0 to any port 11434 proto tcp` instead.)

### 6. Start the container

```bash
ssh server
cd ~/server/fitbit
docker compose up -d --build          # first build takes a few minutes
docker compose logs -f                # Ctrl+C to stop following
docker compose exec fitbit fitbit doctor
```

`doctor` should show the database, Google and Ollama as OK. Database migrations run
automatically when the container starts.

If port 8000 is taken by another container, set `FITBIT_PORT=8001` in the server's `.env`
(compose reads it) and use that port on the server side of the tunnel below.

### 7. Open the app (and reconnect Google)

From the main machine:

```bash
ssh -N -L 8000:127.0.0.1:8000 server        # or -L 8000:127.0.0.1:8001 with FITBIT_PORT
```

Then open `http://127.0.0.1:8000`. Make sure no local `fitbit serve` is using port 8000.

Google only redirects to `http://127.0.0.1:8000/api/auth/callback`. Through the tunnel the
browser is on `127.0.0.1:8000`, so **Settings → Reconnect Google** works unchanged. In
Testing mode that's needed about once a week.

Tip: add a host entry to `~/.ssh/config` on the main machine so it's one short command:

```
Host fitbit-server
    HostName <server-ip>
    User <user>
    LocalForward 8000 127.0.0.1:8000
```

`ssh -N fitbit-server` then opens the tunnel.

### 8. Everyday commands (on the server, in `~/server/fitbit`)

| Task | Command |
|---|---|
| Status / health | `docker compose ps` |
| Logs | `docker compose logs -f --tail 100` |
| Update after `git pull` | `git pull && docker compose up -d --build` |
| Restart / stop | `docker compose restart` / `docker compose down` |
| Any CLI command | `docker compose exec fitbit fitbit sync` (or `analyze`, `brief`, `doctor`…) |
| Backup | `docker compose exec fitbit fitbit db backup` → `./data/backups/` |
| Shrink the DB file | `docker compose stop && sqlite3 data/fitbit.db 'VACUUM;' && docker compose start` |

The container restarts on crashes and after reboots (as long as Docker starts at boot:
`sudo systemctl enable docker`).

### 9. Backups off the server

Backups are health data; keep them on encrypted disks only. For example, from the main
machine, weekly:

```bash
ssh server 'cd ~/server/fitbit && docker compose exec -T fitbit fitbit db backup'
rsync -a server:~/server/fitbit/data/backups/ ~/fitbit-backups/
```

Delete old backups on the server now and then; each is a full copy of the database.

## Security checklist

- [ ] Port published as `127.0.0.1:8000:8000`, never `8000:8000`. Docker bypasses ufw, so a
      bare port mapping would expose the app, which has no login, to your whole network.
- [ ] No router port forwarding for 8000 or 11434.
- [ ] Ollama port allowed only from the server (or only over Tailscale).
- [ ] `.env` and `data/*.db` are `chmod 600` on the server.
- [ ] Server disk encrypted if possible (it holds your health data).
- [ ] Only one copy of the app running.

## Optional: open it from your phone

Phones can't easily hold an SSH tunnel. With Tailscale on the server and the phone, change
the port line in `compose.yaml` to the server's Tailscale IP:

```yaml
      - "<server-tailscale-ip>:8000:8000"
```

Only devices on your tailnet can reach that address. Google reconnects still go through the
SSH tunnel from the main machine, since the redirect must land on `127.0.0.1`.
