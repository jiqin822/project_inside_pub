# Rituals (Game Room) — Local-Only / Prototype

**Status:** Rituals in the Game Room (e.g. “6-Second Kiss”, “Stress-Reducing Talk”, “State of the Union”) are **local-only** and **not persisted to the backend**.

## Current behavior

- **Inside app:** Rituals are stored on the selected loved one’s client-side state (`LovedOne.rituals`). Streaks and “last completed” are updated in memory only and are lost on refresh or when switching devices.
- **Mobile app:** Same idea if rituals are shown there; no server persistence.
- **Backend:** There are **no** Compass/API models or endpoints for rituals. No sync, no history, no cross-device.

## Rationale

Rituals are a **prototype** for Gottman-style “Shared Meaning” and small recurring connection habits. Keeping them local allows quick iteration on UX and copy without schema or API churn. A future phase can add:

- A `rituals` (or similar) table and API
- Sync and streak persistence
- Optional reminders

## For product/engineering

- **Design:** Treat rituals as “demo/prototype” until backend support exists.
- **Docs:** This file is the single source of truth for “rituals are local-only.”
- **Future:** When adding backend support, consider consistency with `dyad_activity_history` and event emission (e.g. `ritual_checked_in`) for personalization.
