# Home server: run the app 24/7 on a spare laptop

A plan for running the app on an old laptop that is always on, so data keeps syncing while
your main machine is off. The AI model stays on your main machine. No code changes are
needed: everything below is configuration.

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
local Ollama instance (CLAUDE.md §6). A spare laptop on a private network avoids all of this.

## Target setup

```
 ┌─────────────── Tailscale (private network, your devices only) ───────────────┐
 │                                                                              │
 │  Old laptop (always on)                     Main machine (on when you use it)│
 │  ─────────────────────                      ─────────────────────────────────│
 │  fitbit serve                               ollama serve                     │
 │   ├─ sync every 15 min ──▶ Google Health    qwen3.5:9b                       │
 │   ├─ scoring, baselines                        ▲                             │
 │   ├─ SQLite (data/)                            │ AI requests                  │
 │   └─ web UI :8000  ────────────────────────────┘ (OLLAMA_HOST)               │
 │         ▲                                                                    │
 │         └── browser on laptop / phone (SSH tunnel or Tailscale IP)           │
 └──────────────────────────────────────────────────────────────────────────────┘
```

| Machine | Runs | Needs |
|---|---|---|
| Old laptop | `fitbit serve`: sync, scoring, database, UI | ~1–2 GB free RAM, stays on, Python 3.12 |
| Main machine | Ollama with `qwen3.5:9b` | ~6–7 GB free RAM/VRAM for the model |

**When the main machine is off:** sync, scores and charts keep working. The AI brief and
Coach show as unavailable, and the brief for a missed day is written once Ollama is back.
The app already handles an unreachable Ollama (CLAUDE.md §2).

## Can the old laptop run the AI too?

Probably not well. `qwen3.5:9b` needs about 6–7 GB of memory, and 4 GB of system RAM also has
to hold the OS and the app. A small (~4B, quantized) model might fit, but only on a supported
NVIDIA or AMD GPU with ~4 GB of its own memory, and its output would be noticeably weaker.

Check the hardware first. On the old laptop:

```bash
free -h                     # total / available RAM
lspci | grep -iE 'vga|3d'   # GPU model
nvidia-smi                  # NVIDIA only: driver, VRAM
```

## Steps

### 1. Prepare the old laptop

- Install a lightweight Linux (e.g. Ubuntu Server or Debian). Turn on **full-disk
  encryption** during install: the database holds your health data.
- Keep it running with the lid closed. In `/etc/systemd/logind.conf` set
  `HandleLidSwitch=ignore` and `HandleLidSwitchExternalPower=ignore`, then
  `sudo systemctl restart systemd-logind`. Disable automatic suspend.
- Leave it plugged in. Consider capping battery charge (if the BIOS supports it) to protect
  an old battery.

### 2. Install Tailscale on both machines (and your phone)

- Install Tailscale on the old laptop, the main machine and your phone, signed in to the same
  account. Note each machine's Tailscale IP (`tailscale ip -4`) or MagicDNS name.
- Enable SSH on the old laptop (`openssh-server`) so you can manage it from the main machine.

### 3. Move the app

On the old laptop:

```bash
git clone <your repo> fitbit && cd fitbit
python3.12 -m venv .venv && .venv/bin/pip install -e .
```

Build the UI on the main machine (`fitbit build-ui`) and copy `src/fitbit_app/static/` over,
or install Node.js on the old laptop and build there.

Then **stop `fitbit serve` on the main machine** and copy `.env` and `data/` across:

```bash
scp .env old-laptop:fitbit/.env
rsync -a data/ old-laptop:fitbit/data/
ssh old-laptop 'chmod 600 fitbit/.env fitbit/data/*.db'
```

`.env` and `data/` must go together: the saved Google token is encrypted with
`FITBIT_SECRET_KEY` from `.env`. Afterwards, run the app on only one machine at a time:
two copies would both sync and diverge.

### 4. Point the app at Ollama on the main machine

In the old laptop's `.env`:

```bash
OLLAMA_HOST=http://<main-machine-tailscale-ip>:11434
```

On the main machine, let Ollama accept connections from the network (by default it only
listens on localhost):

```bash
sudo systemctl edit ollama
#   [Service]
#   Environment="OLLAMA_HOST=0.0.0.0"
sudo systemctl restart ollama
```

Ollama has no password, so allow port 11434 **only over Tailscale**:

```bash
sudo ufw allow in on tailscale0 to any port 11434 proto tcp
sudo ufw deny 11434/tcp
```

Check from the old laptop: `.venv/bin/fitbit doctor` should show Ollama OK.

### 5. Start the app automatically

`fitbit serve` stays the single command; systemd just starts it at boot and restarts it if
it crashes. As your user on the old laptop:

```ini
# ~/.config/systemd/user/fitbit.service
[Unit]
Description=Fitbit Air companion
After=network-online.target

[Service]
WorkingDirectory=%h/fitbit
ExecStart=%h/fitbit/.venv/bin/fitbit serve
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now fitbit
sudo loginctl enable-linger $USER     # keep running without being logged in
journalctl --user -u fitbit -f        # follow the logs
```

### 6. Open the app

**Option A: SSH tunnel (recommended).** The app stays bound to `127.0.0.1`, so it is never on
the network:

```bash
ssh -N -L 8000:127.0.0.1:8000 old-laptop
# then open http://127.0.0.1:8000 on the main machine
```

**Option B: from your phone.** Phones can't easily hold an SSH tunnel. Set `HOST=0.0.0.0` in
the old laptop's `.env` and allow port 8000 only over Tailscale:

```bash
sudo ufw allow in on tailscale0 to any port 8000 proto tcp
sudo ufw deny 8000/tcp
```

Then open `http://<old-laptop-tailscale-ip>:8000` on the phone. The app has no login, so this
relies on Tailscale and the firewall: only your own devices can reach it. Never forward this
port on your router.

### 7. Reconnect Google (weekly, in Testing mode)

Google only redirects back to `http://127.0.0.1:8000/api/auth/callback`. Always reconnect
through the SSH tunnel from step 6A: open `http://127.0.0.1:8000` → Settings → Reconnect
Google. The browser lands on `127.0.0.1`, the tunnel carries it to the old laptop, and the
redirect matches. Refresh tokens last 7 days while the OAuth app is in Testing mode.

### 8. Backups

Add a weekly copy off the laptop, e.g. a cron job on the main machine:

```bash
ssh old-laptop 'cd fitbit && .venv/bin/fitbit db backup'
rsync -a old-laptop:fitbit/data/backups/ ~/fitbit-backups/
```

Backups are health data: keep them on encrypted disks only.

## Checklist

- [ ] Check old laptop RAM / GPU (`free -h`, `lspci`, `nvidia-smi`)
- [ ] Linux with full-disk encryption; lid-close and suspend disabled
- [ ] Tailscale on old laptop, main machine and phone; SSH on old laptop
- [ ] Repo, venv and built UI on the old laptop
- [ ] Stop the app on the main machine; copy `.env` + `data/`; `chmod 600`
- [ ] `OLLAMA_HOST` on the old laptop → main machine; Ollama on `0.0.0.0` + firewall
- [ ] `fitbit doctor` all OK from the old laptop
- [ ] systemd user service enabled, linger on
- [ ] Access via SSH tunnel (and optionally phone over Tailscale + firewall)
- [ ] Google reconnect tested through the tunnel
- [ ] Weekly backup copied off the laptop

## Later (optional)

- If the old laptop's GPU can run a small model, use it as a backup for when the main
  machine is off. This would need the app to try a second Ollama host, which is a code change
  to discuss first.
