# Love Map: Original Look – Differences & Fix Plan

## What’s Different (Current vs Original)

### 1. **Background grid**
- **Original:** Very subtle, light gray grid (20px spacing).
- **Current:** Dark slate `#1e293b` at `opacity-20` in `RoomLayout` – reads darker than the original.
- **Fix:** Use a lighter grid (e.g. lighter color or lower opacity) so it matches the “subtle, light gray” look.

### 2. **Tab label**
- **Original:** Active tab label is “EXPLORATION” (all caps).
- **Current:** “Exploration” (only first letter capitalized).
- **Fix:** Use uppercase label, e.g. “EXPLORATION”, to match the original.

### 3. **Target Subject section**
- **Original:**
  - Label: “TARGET SUBJECT” (all caps).
  - White box, thick dark gray border, drop shadow `4px 4px 0 rgba(0,0,0,0.1)`.
  - ID badge: light blue rectangular badge (“ID: 3507”).
- **Current:**
  - Label: “Target Subject” (not all caps).
  - Shadow uses `rgba(30,41,59,0.1)` (slate tint).
  - ID badge: indigo (`indigo-50` / `indigo-600`).
- **Fix:** Uppercase “TARGET SUBJECT”; use neutral black shadow `rgba(0,0,0,0.1)`; style ID badge as light blue (e.g. `sky-100` / `blue-100` + dark text).

### 4. **Love map path – structure and shapes**
- **Original:**
  - **Start:** “START POINT” (gray) + small black dot, then vertical line.
  - **Play node:** One large **circle** – vibrant blue border, white interior, dark blue play icon.
  - **THE BASICS:** **Rectangular** white card – thick dark border, same 4px shadow, content stacked: “EASY” (light gray) above “THE BASICS” (bold black).
  - **Connector:** Thin light gray vertical line.
  - **Locked node:** Large **circle** – light gray, padlock icon.
  - **Connector:** Thin light gray vertical line.
  - **PREFERENCES:** **Rectangular** white card (same style as THE BASICS) – “EASY” and “PREFERENCES” in light gray (locked).
- **Current:**
  - Start + dot + line: correct.
  - **All levels** are **circles** (play / lock / check) with a **separate** small label box below.
  - No rectangular “module” cards in the path; level title/difficulty live in a floating label under the circle.
- **Fix:** Match original layout:
  - Keep **one play circle** at the top (current level when not locked).
  - Render **level modules as rectangular cards** (white, thick dark border, `shadow-[4px_4px_0px_rgba(0,0,0,0.1)]`), with “EASY” (or difficulty) and level title stacked inside; locked = same card with gray text and optional lock icon.
  - Keep **locked** as a **circle** (gray + padlock) between cards, or integrate into card style per original.
  - Use thin light gray vertical connectors between nodes.

### 5. **Drop shadows**
- **Original:** Content boxes use a single, consistent shadow: `4px 4px 0 rgba(0,0,0,0.1)`.
- **Current:** Target Subject and some cards use `rgba(30,41,59,0.1)`.
- **Fix:** Standardize on `shadow-[4px_4px_0px_rgba(0,0,0,0.1)]` for Target Subject and all path module cards.

### 6. **Header / tab borders**
- **Original:** Header has a clear separation from tabs; tab bar has a thin dark line below.
- **Current:** `RoomLayout` uses `border-b-4 border-slate-900` on the header; tab bar has `border-b border-slate-200`.
- **Fix:** Optional: use a slightly stronger tab bar bottom border (e.g. `border-slate-300`) so the “thin dark line” below tabs is more visible; keep header as-is unless design asks for a thinner header border.

---

## Implementation Plan (in order)

1. **RoomLayout grid** – Softer grid when `showGridBackground`: lighter color or reduced opacity (e.g. `opacity-10` or `#94a3b8` at low opacity) so it matches “subtle, light gray”.
2. **LoveMapsScreen tabs** – Change “Exploration” to “EXPLORATION” (or add `uppercase` class).
3. **Target Subject** – Uppercase “TARGET SUBJECT”; shadow `rgba(0,0,0,0.1)`; ID badge light blue.
4. **Path: rectangular module cards** – For each level, render a **card** (rectangle) with thick border and `shadow-[4px_4px_0px_rgba(0,0,0,0.1)]`, difficulty + title stacked; current = optional play icon; locked = gray text + lock icon or gray styling.
5. **Path: play circle** – Only the first “current” level can show as a circle (vibrant blue border, white fill, play icon); or keep play circle as a separate node before the first card, then cards for THE BASICS, locked circle, PREFERENCES card.
6. **Path: connectors** – Keep thin `bg-slate-300` vertical lines between nodes.
7. **Shadows** – Replace any `rgba(30,41,59,0.1)` with `rgba(0,0,0,0.1)` on Target Subject and path cards.

After implementation, the Love Map screen should match the original look: header (Training / LOVE MAPS, Global XP), tabs (EXPLORATION, MY SPECS, DISCOVER), subtle grid, Target Subject box, and path with start dot → play circle → rectangular THE BASICS → locked circle → rectangular PREFERENCES, all with consistent borders and shadows.
