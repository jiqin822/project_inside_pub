## STT V2 Sentence Finalization and Split Heuristics

This document defines how STT V2 builds UI sentences from STT segments and pauses.

### Inputs
- `SttSegment(range_ms, text, stt_conf, is_final)`
- `PauseEvent(range_samples, pause_ms, conf)`

### Config defaults (from STT_V2.plan.md §5)
- `pause_split_ms = 600`
- `max_sentence_ms = 8000`
- `max_chars = 220`
- `min_chars = 12`
- `stt_jitter_buffer_ms = 300`

### Finalization order (priority)
1. **Strong punctuation**: finalize when text ends with `.`, `!`, or `?` AND length ≥ `min_chars`.
2. **Obvious pause**: finalize on `PauseEvent` where `pause_ms >= pause_split_ms`.
3. **Max duration**: finalize when sentence duration ≥ `max_sentence_ms`.
4. **Max chars**: finalize when text length ≥ `max_chars`, split at best boundary.

### Best boundary selection (for forced splits)
1. **Pause boundary within span** (if a pause event exists inside the sentence window).
2. **Soft punctuation**: `,`, `;`, `:`.
3. **Nearest whitespace** to the target length.

### Jitter buffer behavior
Hold STT segments for `stt_jitter_buffer_ms` to align with diarization and pause signals
when needed. This should not delay final sentence emission beyond the pause split
threshold when a strong pause occurs.

### Notes
- Aim for one label per “speaker sentence.”
- Splits should prefer obvious pauses to preserve readability and speaker flow.
