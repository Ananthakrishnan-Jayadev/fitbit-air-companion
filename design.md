# Design direction (Phase 6: UI refresh)

Based on Figma's "Top web design trends for 2026", filtered for a personal, local-first
health dashboard. Decisions (2026-10-31): **no gamification**, **Coach stays its own page**,
**use the Motion library** for animation.

## Principles
1. **Calm, data-first.** The numbers are the hero. No decoration that competes with data.
2. **Small moments of delight.** Motion that explains change (a meter filling, a number
   counting up), never motion for its own sake.
3. **Accessible by default.** Works with keyboard only, screen readers, reduced motion, and
   both themes at WCAG AA contrast.
4. **Local and lean.** System fonts, no CDNs, no external assets. One new dependency: Motion.

## Trends adopted
| Trend (Figma) | How we use it |
|---|---|
| Dark mode + toggle | Light / Dark / System toggle in the header, remembered per browser |
| Motion design | Motion (`motion/react`): page fade-in, staggered cards, count-up numbers, filling meters, chat messages sliding in |
| Bold typography | One oversized recovery number as the page hero; larger page titles; tabular figures only in tables |
| Proactive AI chatbot | "Ask about this" links on scores, flags and charts open **the Coach page** with a prepared question; suggested follow-ups after each answer |
| Vibrant colour (accent only) | A soft glow behind the recovery hero, tinted by status, always with a text label; charts keep the validated palette |
| Modern navigation | ⌘K / Ctrl+K command palette (pages, jump to a day, ask the coach); bottom tab bar on mobile |
| Accessible, sustainable design | Skip link, visible focus rings, `aria-live` for streaming chat, contrast check in both themes |

## Trends rejected (and why)
- **Gamification:** your call; also avoids nagging and pressure around health data.
- **Voice interfaces:** browser speech recognition sends audio to Google/Apple servers.
- **3D/WebGL, neumorphism, retrofuturism, maximalism, collage, neo-brutalism:** wrong tone
  for health data, low contrast, or heavy for no information gain.

## Motion system
| Token | Value | Used for |
|---|---|---|
| `fast` | 150 ms, ease-out | hover, focus, small state changes |
| `base` | 220 ms, ease-out | cards and panels entering, page transitions |
| `count` | ~800 ms spring (no overshoot) | hero number count-up, meter fill |
| stagger | 40 ms between items | card grids, lists |

- Enter: fade + 8 px rise. Exit: fade only. Charts animate once on first render.
- `MotionConfig reducedMotion="user"`: with *reduce motion* on, transforms are skipped and
  values appear immediately.
- Never animate while data is refetching (hold the previous render, as today).

## Theme
- Tailwind switches from `media` to `class` dark mode; `<html class="dark">` is set from the
  stored choice (`light` | `dark` | `system`), following the OS when `system`.
- Chart tokens are CSS variables keyed off the same class, and charts re-read them when the
  theme changes.

## Page changes
- **Today:**
  - Hero: large recovery number counts up, status label, tinted glow, coach verdict line
    (brief headline), and an "Ask why" link.
  - A 7-day strip of recovery (number + status label per day, links to that day).
  - Existing tiles, tables and the brief card animate in.
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
