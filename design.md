# Design

The app's visual design, newest decisions first in effect. Product context lives in
[PRODUCT.md](PRODUCT.md); the direction contract for the current world is in
`.impeccable/surfaces/`.

**Current state (2026-11-06):** visual world **"Blue Note Sleeve"** (Phase 8), toned down to
muted colours; wide-screen layout with side panels (Phase 8 layout); motion shows change and
charts glide (Phase 7). Phase 6 and 7 notes below are kept for history; where they conflict
with Phase 8, Phase 8 wins (e.g. system fonts → bundled Archivo, stone neutrals → remapped
paper-to-ink ramp, rounded cards → square).

## Phase 8: visual world "Blue Note Sleeve" (2026-11-05)

Chosen on the Impeccable decision page (assigned direction; alternates were Morning Forecast,
Baseline Spectrum, Grid Specimen and the category standard). Each day is issued like a
Blue Note record sleeve: one score at poster scale in condensed type on a flat field.

- **Type:** Archivo variable (weight + width axes), bundled via `@fontsource-variable/archivo`.
  Condensed (`font-stretch: 62%`), extra-bold, upper case for page titles (`.page-title`),
  section openers (`.section-title`, 2px ink rule), card titles and figures; regular width for
  UI text. Mixed weights in one line ("RECOVERY **high**" = black + light).
- **Colour** (tokens in `src/index.css`, muted to ~70% saturation after feedback):

  | Role | Light | Dark | Text on it |
  |---|---|---|---|
  | Shell rail + today/selected accent | `#34508f` | `#4a64a8` | white |
  | Recovery high | `#3d6b55` | `#3f7059` | off-white `#f3f1ea` |
  | Recovery moderate | `#c9a55c` | `#c4a15a` | ink `#1a1a1c` |
  | Recovery low | `#a9503d` | `#a9503d` | off-white |
  | Sleep | `#4b4690` | `#5a549e` | off-white |
  | Strain | `#cf8a55` | `#cc8754` | ink |

  All text/field pairs pass WCAG AA (checked). Fields are flat (no gradients, glows or
  shadows) and always carry a text label. Other chart series are ink; only the selected or
  current series is in full ink.
- **Shape:** square corners (radius ≤ 3px; dots stay round); hairline panels; 2px ink rules
  open sections; target ranges drawn as ink brackets on meters.
- **Neutrals:** Tailwind `stone` remapped to a paper (`#f6f6f3`) → ink (`#0e0e10`) ramp in
  `tailwind.config.ts`.
- **Signature:** the sleeve. Today: recovery sleeve (square on desktop, the whole first
  screen on a phone), sleep/strain sleeves, a 7-day shelf of thumbnail sleeves; Coach repeats
  the three as small sleeves.
- **Raises from the declined directions:** only the selected series in full ink (transit);
  one accent for today/selected (orienteering); one complete state owns the phone's first
  screen (vertical feed); every score shows its proof vs normal (monochrome product).

## Phase 6: UI refresh (2026-10-31)

Based on Figma's "Top web design trends for 2026".

### Principles
1. **Calm, data-first.** The numbers are the hero. No decoration that competes with data.
2. **Small moments of delight.** Motion that explains change (a meter filling, a number
   counting up), never motion for its own sake.
3. **Accessible by default.** Works with keyboard only, screen readers, reduced motion, and
   both themes at WCAG AA contrast.
4. **Local and lean.** System fonts, no CDNs, no external assets. One new dependency: Motion.

### Trends adopted
| Trend (Figma) | How we use it |
|---|---|
| Dark mode + toggle | Light / Dark / System toggle in the header, remembered per browser |
| Motion design | Motion (`motion/react`): page fade-in, staggered cards, count-up numbers, filling meters, chat messages sliding in |
| Bold typography | One oversized recovery number as the page hero; larger page titles; tabular figures only in tables |
| Proactive AI chatbot | "Ask about this" links on scores, flags and charts open **the Coach page** with a prepared question; suggested follow-ups after each answer |
| Vibrant colour (accent only) | A soft glow behind the recovery hero, tinted by status, always with a text label; charts keep the validated palette |
| Modern navigation | ⌘K / Ctrl+K command palette (pages, jump to a day, ask the coach); bottom tab bar on mobile |
| Accessible, sustainable design | Skip link, visible focus rings, `aria-live` for streaming chat, contrast check in both themes |

### Trends rejected (and why)
- **Gamification:** your call; also avoids nagging and pressure around health data.
- **Voice interfaces:** browser speech recognition sends audio to Google/Apple servers.
- **3D/WebGL, neumorphism, retrofuturism, maximalism, collage, neo-brutalism:** wrong tone
  for health data, low contrast, or heavy for no information gain.

## Phase 7 refinement (2026-11-05): colour, layout, motion, fluid charts

Driven by PRODUCT.md: readiness first (morning phone check), long-term trends (laptop deep
dive), private by construction. Changes below supersede the Phase 6 notes they contradict.

### Colour
- **Neutrals are warm** (Tailwind `stone`), matching the chart tokens; the sidebar sits on
  a second, slightly darker neutral layer.
- **Hue means something** (tokens in `src/index.css`):

  | Role | Light / dark | Where |
  |---|---|---|
  | Status `good` / `warning` / `critical` | validated palette | recovery band, week strip, flags |
  | Pillar `sleep` (violet) | `#6650d0` / `#9d8df0` | Sleep tile, Sleep page title dot and charts, sleep metrics on Trends, sleep breakdown |
  | Pillar `strain` (teal) | `#0b7f8c` / `#3fb6c2` | Strain tile, Activity page title dot and step bars, strain/AZM on Trends |
  | `series-1` (blue) | unchanged | every other single-series chart, focus ring, selection |

- Pillar and status hues are for **marks only** (dots, bars, lines, tints), never body text,
  and every one is paired with a text label.
- The recovery panel is tinted with its band colour (9% `color-mix`) instead of a glow.
- Browser surfaces follow the palette: text selection, caret, scrollbar, link underline
  offset; numerals are tabular app-wide.

### Layout (Today)
1. **Recovery panel** leads (number up to 6rem, band label, meter, verdict, "Ask why"), with
   the 7-day strip inside it: recovery history belongs to recovery.
2. **Sleep and Strain** tiles beside it on wide screens, below it on a phone. Each links to
   its page; the strain meter shades today's suggested range.
3. Warnings, then the coach's brief.
4. **Your day:** steps, AZM, calories, distance, sedentary time, stress in one hairline grid
   (not a row of cards).
5. **Behind the scores:** comparison table and the two breakdowns.

Rhythm: 16 px inside a group, 40 px between groups. Stress moved from a top tile into "Your
day" (it isn't a readiness pillar).

### Motion
| Token | Value | Used for |
|---|---|---|
| `fast` | 150 ms, ease-out | hover, page cross-fade, nav highlight slide |
| `base` | 220 ms, ease-out | week-strip selection slide, overlays, chat messages |
| `count` | 800 ms, ease-out | numbers and meters moving to a new value |
| chart update | 480 ms, cubic in-out | chart lines gliding between days/metrics |

- **Motion shows change, not arrival.** First paint is static: no count-up from zero, no
  staggered card entrances, no chart draw-in. Switching day rolls each number and meter from
  the previous day's value to the new one.
- Selection indicators slide (sidebar item, mobile tab bar, week strip) via shared layout.
- `prefers-reduced-motion`: Motion skips transforms (`MotionConfig reducedMotion="user"`),
  numbers jump to their value, and charts turn animation off.

### Fluid charts (the one ambitious moment)
- Each chart keeps a single ECharts instance; new data merges into series matched by id, so
  lines **glide** from one day to the next (Heart, Sleep, Activity) and from one metric to
  another (Trends) instead of being redrawn.
- **Heart, zoomable day:** drag or brush the strip under the chart (touch and mouse), or
  Ctrl/⌘ + scroll / pinch on a trackpad. Below a 4-hour window the chart fetches **every
  reading** in view (`GET /api/heart?start_ms&end_ms`, up to 5000 points) and sharpens on top
  of the simplified day line. "Show whole day" resets. The table view lists the zoomed
  readings.
- In-plot drag zoom is enabled only with a precise pointer, so it never traps page scroll on
  a phone.

## Phase 8 layout: using wide screens (2026-11-06)

Made for a 1920px monitor without hurting laptops or phones.

- **Width:** pages grow to 100rem (1600px) instead of stopping at 768–1152px
  (`components/PageLayout.tsx`: `Page`).
- **Side panel:** `WithAside` puts context beside the main column from `xl` (1280px), 22rem
  wide (25rem from `2xl`), sticky while the main column scrolls; below `xl` it stacks under the
  main content.
- **Chart height** scales with the screen inside `Chart`: the given height on a laptop, ×1.2
  from 1280px, ×1.4 from 1536px.

| Page | Main column | Side panel |
|---|---|---|
| Today | sleeve, sleep/strain; at `2xl` a third column with warnings + coach's brief | — |
| Trends | chart + "Moves with …" (3 related metrics, small) | stats: latest, 7/30-day average, normal, change, highest/lowest, days with data (`trendStats.ts`) |
| Heart | zoomable day + RHR/HRV trends | 4 stats + heart-rate zones |
| Sleep | stats, stages, overnight SpO2/HRV | last 14 nights (compact) |
| Activity | totals, steps by hour, levels, stress | workouts as a list |
| Body | weight and body-fat charts, taller | latest values + note on day-to-day swings |
| Coach | the chat (bubbles capped at 68ch) | latest day as three small sleeves, suggested questions, what the coach sees |
| Journal | entry and "What affects you" side by side, history below | — |
| Settings | cards in two columns | — |

## Theme
- Tailwind switches from `media` to `class` dark mode; `<html class="dark">` is set from the
  stored choice (`light` | `dark` | `system`), following the OS when `system`.
- Chart tokens are CSS variables keyed off the same class, and charts re-read them when the
  theme changes.

## Page changes
- **Today:** see "Layout (Today)" above (Phase 7 replaced the Phase 6 hero and tiles).
- **Coach:**
  - Opens with `?q=` prefilled from "Ask about this" links. The question is placed in the
    input box and not sent automatically, so you stay in control.
  - Shows 3 suggested follow-ups after each answer.
  - Messages animate in; the streaming reply is announced via `aria-live="polite"`.
- **Heart / Sleep / Activity:** an "Ask about this" link per chart card (prefilled question
  for that day and chart).
- **Global:**
  - Theme toggle, ⌘K palette, skip link, focus rings.
  - Mobile: a bottom tab bar (Today, Sleep, Activity, Coach, More), with the sidebar
    hidden below `md`.
