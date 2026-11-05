---
version: 1
slug: "frontend-src-pages-todaypage-tsx"
primary_target: "frontend/src/pages/TodayPage.tsx"
related_targets: ["frontend/src/components/Layout.tsx"]
---

# Surface brief: app shell + Today

Scope: whole web app visual world (shell, all pages inherit), first surface Today. Mode: Operate.
Audience/job: the owner; morning phone glance (how ready am I) and laptop deep dive.
Keep: page set and nav items, light + dark + system themes, fluid charts (restyled ok), ⌘K palette and mobile tab bar.
Feels wrong: gamey/flashy (neon, rings, hype), generic dashboard kit. Success: instantly readable AND unmistakably its own.
Constraints: no external fonts at runtime (bundled font files only), no medical claims, status never by colour alone, WCAG AA both themes.

## Direction contract

THESIS: Each day is issued like a Blue Note sleeve: one score set at poster scale in condensed type on a flat ink field. Refuses the card grid with rings and the grey dashboard with one blue accent.

OWN-WORLD: Flat ink fields, no gradients or shadows. Cobalt shell rail; recovery field takes its band (green / ochre / vermilion, always labelled); sleep indigo, strain orange. Paper-white ground (light), near-black ground (dark). One grotesque with a width axis: condensed black for numbers and titles, regular width for UI. Square corners, 2px ink rules, mixed weights in one line. Raises: only the selected series in full ink (transit); one accent reserved for today/selected (orienteering); every sleeve carries its proof line vs normal (monochrome); on a phone the recovery sleeve owns the first screen (feed).

STORY: Open, read the sleeve: number, band, verdict, proof. Glance at sleep and strain sleeves, the week shelf, then descend into the day and the evidence.

FIRST VIEWPORT: Desktop: cobalt rail left (brand, search, nav, theme switch); header "TODAY" + date controls; left a square recovery sleeve (~520px) with the number bleeding off its field; right, sleep and strain sleeves with meters, target, flag; below, a 7-day shelf of thumbnail sleeves and the "Your day" ruled stat row. Phone: recovery sleeve full width as the first screen.

FORM: Blue Note record sleeves (Reid Miles typography), candidate 7 of 7 on the ordered list; seed:11efda5be5678c3f

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
