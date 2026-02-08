## STT V2 Patch Re-attribution and UI Patch Semantics

This document defines how refine patches are applied and how the UI is updated.

### Patch window
- Refine patches apply to the last **10–20s** of audio (default: `20s`).
- Re-attribute only sentences that overlap the patched range.

### Re-attribution behavior
1. Apply `DiarPatch` to the `SpeakerTimelineStore`.
2. Find UI sentences with time ranges overlapping the patch window.
3. Re-run attribution on those sentences.
4. Emit `ui.sentence.patch` events with updated label/coverage/flags.

### UI event contract
`ui.sentence.patch` should include:
- `id` (same as original sentence)
- `start_ms`, `end_ms`
- `label`, `label_conf`, `coverage`
- `flags` (with `"patched": true`)

### Nudge policy
- **Do not** retroactively emit “real-time” nudges based on patched labels.
- Patches are used for transcript accuracy and analytics only.

### Notes
- Keep patch window small to avoid UI churn.
- If a sentence is outside the patch window, it should not be updated.
