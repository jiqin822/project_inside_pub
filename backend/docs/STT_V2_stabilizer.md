## STT V2 Stabilizer (speaker label commit rules)

This document defines the stabilization policy for the sample-indexed speaker timeline
used by STT V2. The goal is to minimize “twitchy” speaker changes while still reacting
to real speaker switches.

### Inputs
- `DiarFrame` with `label`, `conf`, and `range_samples` (sample-indexed).
- Optional special labels: `OVERLAP`, `UNCERTAIN`.

### State (per stream)
- `current_label`, `current_conf`, `current_duration_samples`
- `candidate_label`, `candidate_conf`, `candidate_duration_samples`
- `last_switch_sample`

### Commit rules (must all be true)
Switch from `current_label` to `candidate_label` only when:
1. `candidate_duration_samples >= switch_confirm_ms`
2. `time_since_last_switch >= cooldown_ms`
3. `current_duration_samples >= min_turn_ms`
4. `candidate_conf >= current_conf + switch_margin`

### Defaults (from STT_V2.plan.md §5)
- `min_turn_ms = 800`
- `switch_confirm_ms = 160`
- `cooldown_ms = 600`
- `switch_margin = 0.08`

### OVERLAP / UNCERTAIN handling
- Preserve these labels as honest states.
- Do not allow short `OVERLAP` or `UNCERTAIN` blips to cause a switch unless they
  persist long enough to satisfy the commit rules.

### Update flow
1. If incoming label == current label:
   - extend `current_duration_samples`
   - update `current_conf` with a smoothing factor (EMA)
   - clear candidate state
2. Else:
   - update candidate state (or reset if new candidate)
   - evaluate commit rules; if satisfied, commit switch and reset candidate
3. Emit timeline interval for the stabilized label only (not for candidate).

### Notes
- The stabilizer is intentionally conservative to preserve UX calmness.
- If latency becomes high, reduce `switch_confirm_ms` slightly while keeping `cooldown_ms`.
