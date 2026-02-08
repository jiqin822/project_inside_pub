# STT voice matching: guardrails, metrics, evaluation

This doc captures guardrails, metrics, and the evaluation plan for the voice-matching redesign (see `.cursor/plans/voice_matching_redesign_revised.plan.md` §7).

## Guardrails

- **Timebase**: All attribution uses sample indices. Queries outside the ring buffer retention window are logged (warning) in `routes_stt.py`; attribution is only performed for segments whose end is within the reliable horizon (`now_sample - L`, where L = `stt_diarization_reliable_lag_ms`).
- **Quality gates**: Track embeddings and enrollment updates use clean-speech only (non-overlap segments); see anti-poisoning rules in the plan §0.1.1.

## Metrics (per session)

Tracked on `SttSessionContext`:

- **segments_resolved_count**: Number of segments for which `stt.speaker_resolved` was sent.
- **overlap_resolved_count**: Number of those resolved as `OVERLAP`.
- **uncertain_resolved_count**: Number of those resolved as `UNCERTAIN`.

Debug logs emit when a segment is resolved as OVERLAP or UNCERTAIN (session_id, segment_id, counts). Use these for monitoring and evaluation.

## Evaluation plan and acceptance criteria

Define success on your own (or held-out) audio:

### Targets (tune to your data)

- **Label flip rate**: Reduce by X% vs baseline (measure label changes per minute or per session).
- **Known-user precision**: When we output a known user at confidence ≥ 0.85, we are correct ≥ Y% of the time (e.g. 90%+).
- **OVERLAP rate**: Keep below Z% of segments, or document as acceptable in overlap-heavy environments.

### Overlap torture set

- Build a small set of **overlap-heavy** clips (interruptions, crosstalk).
- Run **before/after** the redesign; ensure OVERLAP/UNCERTAIN are used appropriately and that wrong single-speaker labels do not increase on these clips.

### Cadence

- Run evaluation periodically (e.g. on each major change to diarization or track→user mapping).
