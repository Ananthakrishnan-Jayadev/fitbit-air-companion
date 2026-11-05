# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

One person: the owner of a Google Fitbit Air, who is also the app's builder and operator.
Nobody else signs in or views the data. The optional password (`APP_PASSWORD`) exists to keep
other devices on the home network out, not to support more users.

Two recurring situations:

- **Morning phone check.** Just woken up, at home, on a phone over home Wi-Fi: how did I
  sleep, how recovered am I, what should today's load be? Seconds, not minutes.
- **Laptop deep dive.** Sitting down on a laptop to explore: trends against baseline, sleep
  and heart detail, journal tags and what affects them, weight and body fat, the coach.

## Product Purpose

Turns everything the Fitbit Air records into readiness guidance and long-term understanding,
with deeper analysis than the official Fitbit / Google Health app, while keeping all data and
AI on machines the owner controls.

What the owner values most, in order of the answers given:

1. **Readiness scores:** recovery, strain with a daily target, sleep performance, stress and
   anomaly flags, all computed from personal baselines rather than population norms.
2. **Long-term trends:** months of HRV, resting HR, sleep, steps, weight and body fat against
   the personal baseline.
3. **Privacy and ownership:** data comes only from Google, lives in a local SQLite file, and
   is fully exportable; AI runs on a local model.

The local AI (daily brief, weekly review, coach chat) is supporting, not the headline: it
explains the numbers, it doesn't replace them.

Success: the morning check answers "how ready am I today" at a glance, and the deep dive
makes long-term patterns and their causes visible.

## Positioning

A private, self-hosted readiness and trends companion for one person's Fitbit Air. Scores are
computed in the app from raw intraday data (1-second heart rate, HRV, SpO2, minute activity,
sleep stages) against the owner's own baselines, and the AI reads only a derived feature pack
on a local model. Health data never goes to a third party beyond its source (Google).

## Operating Context

- Runs as one process (`fitbit serve`), locally or as a Docker container on an always-on
  home server. Reached from the laptop (directly or via SSH tunnel) and from the phone at
  `http://<server-ip>:8000` on home Wi-Fi only.
- Ollama with `qwen3.5:9b` runs on the owner's main machine. When it's off, AI features are
  unavailable and everything else keeps working.
- Data syncs every 15 minutes (intraday) and hourly (daily, sleep, workouts) from the Google
  Health API. The OAuth app is in Testing mode, so Google must be reconnected about weekly,
  always via `127.0.0.1`.
- Inputs beyond the band: a Renpho smart scale (weight, body fat) via Health Connect, and
  daily journal tags entered in the app.
- Pages: Today, Heart, Sleep, Activity, Body, Trends, Journal, Coach, Settings, plus a login
  page when a password is set.

## Capabilities and Constraints

- Single-user. No accounts, sharing, social features or multi-tenant hosting.
- **No medical claims.** Scores, flags and AI output are informational; no diagnoses.
- **No gamification** (decided 2026-10-31): no streaks, badges or points.
- **Local and lean:** no telemetry, analytics SDKs, CDNs or external fonts. The UI is served
  by the app itself.
- Must keep working when Ollama is unreachable or AI is disabled.
- The AI never receives raw time series, only computed features.
- Data can be sparse: weight only on weigh-in days, scores need baselines (first weeks are
  thin), some types depend on Google permissions granted.
- Out of scope: direct Bluetooth access to the band (research notes only), webhooks.
- Stack is fixed (see project.md §2): FastAPI + React 18/TypeScript, Tailwind, TanStack Query,
  ECharts, Motion.

## Evidence on Hand

- Real data exists only in the owner's private database and must never appear in the repo,
  fixtures, screenshots or design assets. Tests use synthetic data
  (`tests/fixtures/`).
- No testimonials, users, benchmarks or validation studies exist; none may be implied.
- The scoring methods are documented in project.md §7; they are the app's own heuristics,
  not clinically validated.

## Product Principles

1. **Readiness first.** The most important answer (how recovered am I, what load suits
   today) must be reachable in seconds on a phone.
2. **Personal baseline over population norms.** Every number is framed against the owner's
   own history.
3. **Depth on demand.** The deep dive has the detail; the glance doesn't carry it.
4. **Private by construction.** Nothing about the product may require sending health data
   anywhere new.
5. **Honest numbers.** Informational framing, visible uncertainty (sparse data, thin
   baselines, confidence intervals), no medical claims and no motivational pressure.

## Accessibility & Inclusion

Target WCAG AA contrast in both light and dark themes. Fully keyboard operable, visible focus,
screen-reader labels for charts and status, honours the OS reduce-motion setting, and status
is never conveyed by colour alone.
