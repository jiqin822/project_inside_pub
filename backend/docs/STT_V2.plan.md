# Production-grade Streaming Diarization + STT Architecture
## Stack: Diart (streaming diarization) + Google Chirp3 (streaming STT, no diarization, no word-level timings)
## UI contract: one speaker label per “speaker sentence” (split long sentences on obvious pauses)

---

## 0) Design goals

### Primary goal
Maintain a **sample-indexed speaker timeline** (owned by diarization) that is **independent from STT text**, then attribute **STT segments → UI speaker sentences** to that timeline.

### UX goals
- Calm speaker labeling (anti-twitch): stable speaker bubbles and sentence labels.
- UI shows **one label per speaker sentence**.
- If a sentence gets long, break it at **obvious pauses** (silence gaps).
- Support **Preview** (~300–800ms latency) + **Refine/Patch** (2–6s context) without corrupting transcript logic.

### Constraints
- Single mixed audio channel is the hard case.
- Chirp3 provides streaming transcription but **no diarization** and **no word-level timestamps**.
- Therefore attribution is **segment-level / sentence-level**, not word-level.
- Diarization labels are **window-local**; stable identity requires a voiceprint mapping stage.

---

## 1) System overview (event-driven, decoupled services)

### Services / Modules
1. **Audio Ingest** (PCM16, sample clock)
2. **Pause/VAD Service** (pause events, speech regions)
3. **Diart Diarization Service** (streaming diarization → diar frames/segments)
4. **Speaker Timeline Store** (sample-indexed timeline, stabilization, patching)
5. **Chirp3 STT Service** (streaming transcripts at segment-level timestamps)
6. **Sentence Assembly Service** (STT segments + pauses → UI sentences)
7. **Sentence Attribution Service** (UI sentence → single diar label)
8. **Voice ID Mapping Service** (voiceprint mapping → stable user ID labels)
9. **Coach Engine** (safe nudges; speaker-specific only when stable)
10. **Session Orchestrator + EventBus** (wiring, backpressure)

### Key seam
- Diarization writes to **SpeakerTimelineStore**.
- STT produces text segments.
- UI sentences are assembled from STT + pauses.
- UI sentence speaker labels come from **timeline lookup**.

### Flowchart (inputs/outputs)

flowchart LR
  A[AudioIngestor] --> B[AudioChunker]
  B --> C[PauseVADService]
  B --> D[DiartDiarizationService]
  D --> E[SpeakerTimelineStore]
  A --> F[Chirp3SttService]
  F --> G[SentenceAssembler]
  C --> G
  E --> H[SentenceSpeakerAttributor]
  G --> H
  H --> I[VoiceIdMatcher]
  I --> J[SentenceStitcher]
  J --> K[CoachEngine]
  J --> L[UI Client]
  K --> L


## 2) Core data contracts (domain models)

### Time primitives
- `StreamId: str`
- `SampleIndex: int` (monotonic clock per stream)
- `TimeRangeSamples(start: SampleIndex, end: SampleIndex, sr: int)`
- `TimeRangeMs(start_ms: int, end_ms: int)`

### Audio events
- `AudioChunk(stream_id, range_samples, pcm16_bytes)`
- `AudioFrame(stream_id, range_samples, pcm16_np)`      # e.g., 20ms
- `AudioWindow(stream_id, range_samples, pcm16_np)`     # e.g., 1.0–1.6s

### Pause / VAD events
- `SpeechRegion(range_samples, vad_conf: float)`
- `PauseEvent(range_samples, pause_ms: int, conf: float)`  # “obvious pause” if pause_ms >= pause_split_ms

### Diarization labels
- `DiarLabel = spk0..spkK | OVERLAP | UNCERTAIN`
- `DiarFrame(range_samples, label: DiarLabel, conf: float, is_patch: bool=False)`
- `DiarPatch(range_samples, frames: list[DiarFrame], version: int)`

### STT (Chirp3) outputs
- `SttSegment(range_ms: TimeRangeMs, text: str, stt_conf: float, is_final: bool)`

### UI sentence outputs (what UI consumes)
- `UiSentence(id: str, range_ms: TimeRangeMs, text: str, is_final: bool=True)`
- `SpeakerSentence(ui_sentence: UiSentence, label: DiarLabel, label_conf: float, coverage: float, flags: dict)`

Flags example:
- `{ "overlap": bool, "uncertain": bool, "patched": bool }`

---

## 3) Object-oriented module design (interfaces + responsibilities)

### 3.1 `AudioIngestor`
**Responsibility**
- Receive PCM16 mixed audio, assign sample indices, write to ring buffer.

**Methods**
- `push_pcm16(stream_id, pcm16_bytes, sr) -> TimeRangeSamples`

**Emits**
- `AudioChunk`

---

### 3.2 `AudioRingBuffer`
**Responsibility**
- Store recent PCM for windowing, debugging, patch refinement.
- Provide deterministic reads by sample range.

**Methods**
- `write(stream_id, range_samples, pcm16_bytes)`
- `read(stream_id, range_samples) -> np.ndarray`
- `latest_sample(stream_id) -> SampleIndex`

---

### 3.3 `AudioChunker`
**Responsibility**
- Convert chunk stream into fixed-size frames and diar windows.

**Config**
- `frame_ms = 20`
- `window_s = 1.0–1.6`
- `hop_s = 0.2–0.5`

**Methods**
- `on_audio_chunk(chunk) -> list[AudioFrame|AudioWindow]`

**Emits**
- `AudioFrame`, `AudioWindow`

---

### 3.4 `PauseVADService`
**Responsibility**
- Fast VAD + hangover.
- Produce `SpeechRegion` and `PauseEvent` (silence gaps).
- Define “obvious pause” boundary for sentence splitting.

**Config (shipping defaults)**
- `vad_frame_ms = 20`
- `vad_hangover_ms = 200–350`
- `pause_split_ms = 600`     # obvious pause boundary
- `pause_merge_ms = 200`     # ignore micro-gaps

**Methods**
- `process_frame(frame: AudioFrame) -> list[SpeechRegion|PauseEvent]`

---

### 3.5 `DiartDiarizationService`
**Responsibility**
- Run Diart streaming diarization over `AudioWindow`s.
- Normalize Diart output into `DiarFrame`s with sample-index ranges.
- Optionally produce refine patches (more context).

**Config**
- Diart pipeline parameters (model, window/hop, etc.)
- Preview vs refine mode toggles

**Methods**
- `start(stream_id, sr)`
- `process_window(window: AudioWindow) -> list[DiarFrame|DiarPatch]`

**Notes**
- Convert Diart timestamps → samples using sr.
- Enforce monotonic time ranges; clamp/round carefully.

---

### 3.6 `SpeakerTimelineStore`
**Responsibility**
- Maintain sample-indexed timeline, apply stabilization (anti-twitch),
  store as RLE intervals for efficiency.
- Apply patches with versioning.

**Storage**
- Interval map: `(start_sample, end_sample, label, conf)`
- Keep last N seconds/minutes per stream in memory (e.g., 5–15 min).

**Methods**
- `apply_frames(stream_id, frames: list[DiarFrame])`
- `apply_patch(stream_id, patch: DiarPatch)`
- `query(stream_id, range_samples) -> list[(range_samples, label, conf)]`
- `stats(stream_id) -> TimelineStats`

**Stabilizer (label commit)**
Maintain `current_label`, `candidate_label`, durations, cooldown.
Commit a speaker change only when:
- `candidate_duration >= switch_confirm_ms`
- `time_since_last_switch >= cooldown_ms`
- `current_duration >= min_turn_ms`
- `candidate_score >= current_score + switch_margin`

**Stabilizer defaults**
- `min_turn_ms = 600–1000`
- `switch_confirm_ms = 120–240`
- `cooldown_ms = 400–800`
- `switch_margin = 0.05–0.12` (score/conf-space proxy)

**Policy**
- Preserve `OVERLAP/UNCERTAIN` as honest states.
- Do not let short uncertain blips cause switches unless persistent.

---

### 3.7 `Chirp3SttService`
**Responsibility**
- Stream audio to Chirp3 STT; emit `SttSegment`.
- No diarization; no word timestamps.

**Methods**
- `start(stream_id, sr)`
- `process_frame_or_window(...) -> list[SttSegment]`

**Policy**
- Prefer emitting final segments (`is_final=True`) to reduce UI churn.
- If partials are needed, mark them tentative and update on final.

---

### 3.8 `SentenceAssembler`
**Responsibility**
- Create UI “speaker sentences” from STT segments, using pause boundaries.
- If a sentence is too long, split at “obvious pauses” first.

**Inputs**
- `SttSegment`
- `PauseEvent`

**Outputs**
- `UiSentence` (finalized unit for UI labeling + rendering)

**Config (shipping defaults)**
- `pause_split_ms = 600`          # primary split rule
- `max_sentence_ms = 8000`        # backstop
- `max_chars = 220`               # readability
- `min_chars = 12`
- `stt_jitter_buffer_ms = 200–500` # hold to align timestamps

**Finalization rules (in priority order)**
1. Strong punctuation end (., !, ?) if length >= min_chars
2. Obvious pause boundary (pause >= pause_split_ms)
3. Max duration reached (>= max_sentence_ms)
4. Max chars reached (>= max_chars) → split at best boundary

**Best boundary for forced splits**
1. Pause boundary within sentence span
2. Soft punctuation (, ; :)
3. Nearest whitespace to target length

**Methods**
- `on_stt_segment(seg: SttSegment) -> list[UiSentence]`
- `on_pause_event(pause: PauseEvent) -> list[UiSentence]`

---

### 3.9 `SentenceSpeakerAttributor`
**Responsibility**
- Assign exactly **one label** to each `UiSentence` by timeline coverage.

**Inputs**
- `UiSentence(range_ms)`
- `SpeakerTimelineStore.query(range_samples)`

**Outputs**
- `SpeakerSentence` (single diar label + confidence + coverage + flags)

**Label policy (single label required)**
Compute coverage over sentence time span:
- `coverage(spkX)`, `overlap_ratio`, `uncertain_ratio`

Decision:
1. If `overlap_ratio >= overlap_sentence_th` → label = `OVERLAP`
2. Else if `uncertain_ratio >= uncertain_sentence_th` → label = `UNCERTAIN`
3. Else dominant speaker:
   - if `dominant_coverage < dominant_sentence_th` → `UNCERTAIN`
   - else label = dominant `spkX`

**Defaults**
- `dominant_sentence_th = 0.75`
- `overlap_sentence_th = 0.20`
- `uncertain_sentence_th = 0.30`

**Methods**
- `attribute(sentence: UiSentence) -> SpeakerSentence`

---

### 3.10 `VoiceIdMatcher`
**Responsibility**
- Map diarization labels (`spkX`) to **stable user IDs** using voiceprints and cache/smoothing.

**Inputs**
- `SpeakerSentence` from `SentenceSpeakerAttributor`
- `voice_embeddings` and `voice_embeddings_multi` in session context
- Audio span for the sentence (via `AudioProcessor` + ring buffer)

**Outputs**
- `SpeakerSentence` with `label = user_id` (or `Unknown_*`) and `flags.voice_id=true` when mapped

**Rules**
- Pass through `OVERLAP`/`UNCERTAIN`
- Thresholds: `stt_speaker_match_threshold`, `stt_speaker_match_margin`, `stt_prefer_known_over_unknown_gap`
- Cache `spkX → user_id` with TTL; allow relabel detection and switch only after persistence

**Methods**
- `map_label(ss: SpeakerSentence) -> SpeakerSentence`

---

### 3.11 `SentenceStitcher`
**Responsibility**
- Reduce fragmentation: merge adjacent speaker sentences when safe.

**Merge rule**
Stitch A+B if:
- same label
- gap < `stitch_gap_ms` (e.g., 300ms)
- combined duration < `max_stitched_ms` (e.g., 9000ms)
- optional: A does not end with strong punctuation

**Methods**
- `on_speaker_sentence(ss: SpeakerSentence) -> list[SpeakerSentence]`

---

### 3.12 `CoachEngine`
**Responsibility**
- Generate nudges safely; speaker-specific only when stable.

**Gating**
Speaker-specific nudges only if:
- `label` is `spkX`
- `coverage >= dominant_sentence_th`
- `flags.overlap == false` and `flags.uncertain == false`
- sentence duration >= `min_nudge_sentence_ms` (e.g., 800–1500ms)

Otherwise:
- emit generic de-escalation nudges (non-attributed)

**Methods**
- `on_speaker_sentence(ss: SpeakerSentence) -> list[NudgeEvent]`

---

### 3.13 `SessionOrchestrator` + `EventBus`
**Responsibility**
- Wire the pipeline. Ensure backpressure, bounded queues, and lifecycle control.

**Per-stream lifecycle**
- `start_session(stream_id, sr)`
- route audio → chunker → (pause/vad, diar, stt)
- diar → timeline store
- stt + pauses → sentence assembler
- ui sentence → sentence attributor → stitcher
- stitched speaker sentence → UI + CoachEngine
- diar patches → timeline store → re-attribute impacted UI sentences (optional window)

**Backpressure**
- Bounded queues per stream.
- Drop preview diar frames if overloaded; keep refine patches when possible.
- Prefer emitting only finalized STT segments to UI.

---

## 4) Two-phase output (Preview + Refine/Patch)

### Preview path (snappy)
- Diart emits near-real-time frames.
- Timeline store stabilizes and updates current speaker state.
- SentenceAssembler emits sentences mostly from final STT + pauses.
- SentenceAttributor assigns label from current timeline.

### Refine/Patch path (quality)
- Diart emits patch frames for last 2–6s.
- TimelineStore applies patch version.
- Re-attribute any UI sentences overlapping patched ranges (within a rolling window).
- UI receives `ui.sentence.patch` updates (optional; keep patch window small to avoid churn).

**Recommendation**
- Patch UI labels for transcript accuracy & analytics.
- Do NOT retroactively fire “real-time nudges” on patched labels.

---

## 5) Shipping configuration (practical defaults)

### Audio/chunking
- `frame_ms = 20`
- `diar_window_s = 1.0–1.6`
- `diar_hop_s = 0.2–0.5`
- Ring buffer: `60–120s` (memory) + optional disk debug

### Pause/VAD
- `vad_hangover_ms = 200–350`
- `pause_split_ms = 600`
- `pause_merge_ms = 200`

### Stabilizer (anti-twitch)
- `min_turn_ms = 800`
- `switch_confirm_ms = 160`
- `cooldown_ms = 600`
- `switch_margin = 0.08`

### Sentence assembly
- `stt_jitter_buffer_ms = 300`
- `max_sentence_ms = 8000`
- `max_chars = 220`
- Split long sentences: prefer pauses >= 600ms

### Sentence attribution
- `dominant_sentence_th = 0.75`
- `overlap_sentence_th = 0.20`
- `uncertain_sentence_th = 0.30`

### UI update cadence
- Preview speaker bubble: ~500ms
- Sentence events: emit on sentence finalize (pause/punctuation/final segment)
- Patch window: last 10–20s max

---

## 6) Observability & production hardening

### Metrics (per stream)
- Speaker switch rate (switches/min)  # twitchiness KPI
- %UNCERTAIN, %OVERLAP
- Avg dominant coverage for sentences
- Sentence length distribution (ms/chars)
- Patch rate and patch-induced label changes

### Debug bundle (for repro)
- last 30s audio (PCM)
- diar timeline intervals (pre/post patch versions)
- STT segments
- UI sentences + speaker labels

### Testing
- Unit tests: timeline stabilization, pause splitting, sentence split/stitch, attribution thresholds.
- Integration tests: fixed audio fixtures → stable KPIs.
- Shadow mode: evaluate threshold changes without affecting UI.

---

## 7) Frontend contract (single label per speaker sentence)

### Event: `ui.sentence`
- One sentence, one label.

Example:
```json
{
  "type": "ui.sentence",
  "id": "sent_123",
  "stream_id": "abc",
  "start_ms": 123450,
  "end_ms": 124980,
  "label": "spk1",
  "label_conf": 0.86,
  "coverage": 0.82,
  "text": "I’m not trying to argue — I just want us to feel like a team.",
  "flags": { "overlap": false, "uncertain": false, "patched": false }
}
```

---
## 8) Implementation TODOs

These tasks implement the goals in §0 (design goals & UX), the contracts in §2 (domain models) and §7 (frontend event), and the module interfaces in §3. Tasks are grouped by subsystem. Use prefixes: `Backend:`, `Frontend:`, `Observability:`, `Tests:`, `Design:`. Items marked **Design:** require a separate design/plan document before implementation.

### Directory layout (parallel to current STT)

Place the new implementation in **directories parallel** to the existing STT tree (no nesting under the current `stt` package):

- **API / pipeline**: `backend/app/api/stt_v2/` — parallel to `backend/app/api/stt/`. All V2 services and orchestration live here (AudioIngestor, AudioChunker, PauseVADService, DiartDiarizationService, SpeakerTimelineStore, Chirp3SttService, SentenceAssembler, SentenceSpeakerAttributor, SentenceStitcher, CoachEngine, SessionOrchestrator, routes).
- **Domain / contracts**: `backend/app/domain/stt_v2/` — parallel to `backend/app/domain/stt/`. All V2 domain types and time primitives live here (StreamId, SampleIndex, TimeRangeSamples, TimeRangeMs, AudioChunk, AudioFrame, AudioWindow, SpeechRegion, PauseEvent, DiarLabel, DiarFrame, DiarPatch, SttSegment, UiSentence, SpeakerSentence).

Current `app/api/stt/` and `app/domain/stt/` remain unchanged; V2 is developed and wired (e.g. feature flag or separate route) alongside.

### Domain & data contracts
- [x] **Backend:** Define `StreamId`, `SampleIndex`, `TimeRangeSamples`, `TimeRangeMs` (and sr conversion) in domain layer.
- [x] **Backend:** Define `AudioChunk`, `AudioFrame`, `AudioWindow` with `stream_id` and sample ranges.
- [x] **Backend:** Define `SpeechRegion`, `PauseEvent` with range and pause_ms/conf.
- [x] **Backend:** Define `DiarLabel` (spk0..spkK | OVERLAP | UNCERTAIN), `DiarFrame`, `DiarPatch` with version.
- [x] **Backend:** Define `SttSegment(range_ms, text, stt_conf, is_final)`.
- [x] **Backend:** Define `UiSentence(id, range_ms, text, is_final)` and `SpeakerSentence(ui_sentence, label, label_conf, coverage, flags)`.

### Backend: Audio pipeline
- [x] **Backend:** Implement `AudioIngestor.push_pcm16(stream_id, pcm16_bytes, sr) -> TimeRangeSamples`; assign sample indices; emit/write `AudioChunk`.
- [x] **Backend:** Implement `AudioRingBuffer`: `write`, `read(stream_id, range_samples) -> np.ndarray`, `latest_sample(stream_id)`; configurable retention (e.g. 60–120s).
- [x] **Backend:** Implement `AudioChunker`: config `frame_ms=20`, `diar_window_s`, `hop_s`; `on_audio_chunk(chunk) -> list[AudioFrame|AudioWindow]`.

### Backend: Pause / VAD
- [x] **Backend:** Implement `PauseVADService`: config `vad_frame_ms`, `vad_hangover_ms`, `pause_split_ms`, `pause_merge_ms`; `process_frame(frame) -> list[SpeechRegion|PauseEvent]`.

### Backend: Diarization
- [x] **Backend:** Implement `DiartDiarizationService`: `start(stream_id, sr)`, `process_window(window) -> list[DiarFrame|DiarPatch]`; convert Diart timestamps to sample ranges; monotonic/clamp handling.
- [x] **Backend:** Support Preview vs Refine mode (e.g. window/hop and patch emission) in Diart integration.

### Backend: Speaker timeline
- [x] **Backend:** Implement `SpeakerTimelineStore`: interval storage (start_sample, end_sample, label, conf), RLE-friendly; `apply_frames`, `apply_patch`, `query(stream_id, range_samples)`, `stats(stream_id)`; retention 5–15 min per stream.
- [x] **Design:** Output a plan for **timeline stabilizer** (commit rules: switch_confirm_ms, cooldown_ms, min_turn_ms, switch_margin; OVERLAP/UNCERTAIN policy; defaults from §5). Implement after plan is approved.
- [x] **Backend:** Implement stabilizer per §3.6 (current_label, candidate_label, commit conditions) and wire to store.

### Backend: STT
- [x] **Backend:** Implement `Chirp3SttService`: `start(stream_id, sr)`, stream audio to Chirp3; emit `SttSegment` with `is_final`; prefer finals to reduce UI churn.

### Backend: Sentence assembly & attribution
- [x] **Backend:** Implement `SentenceAssembler`: config `pause_split_ms`, `max_sentence_ms`, `max_chars`, `min_chars`, `stt_jitter_buffer_ms`; `on_stt_segment`, `on_pause_event` → `list[UiSentence]`.
- [x] **Design:** Output a plan for **sentence finalization and split heuristics** (priority order: strong punctuation, pause boundary, max duration, max chars; best-boundary for forced splits; jitter buffer behavior). Implement after plan is approved.
- [x] **Backend:** Implement `SentenceSpeakerAttributor`: `attribute(sentence) -> SpeakerSentence`; coverage computation; label policy (OVERLAP/UNCERTAIN/dominant) with §3.9 defaults.

### Backend: Voice ID mapping
- [x] **Backend:** Add `VoiceIdMatcher` module to map `spkX → user_id` using `voice_embeddings` and `voice_embeddings_multi`.
- [x] **Backend:** Insert mapping stage after `SentenceSpeakerAttributor` and before `SentenceStitcher`; set `flags.voice_id=true` when mapping succeeds.
- [x] **Backend:** Add cache/smoothing rules (TTL, relabel detection, persistence) using thresholds `stt_speaker_match_threshold`, `stt_speaker_match_margin`, `stt_prefer_known_over_unknown_gap`.

### Backend: Sentence stitching
- [x] **Backend:** Implement `SentenceStitcher`: merge adjacent same-label sentences per §3.11 (stitch_gap_ms, max_stitched_ms, optional punctuation check).

### Backend: Coach
- [x] **Backend:** Implement `CoachEngine`: `on_speaker_sentence(ss) -> list[NudgeEvent]`; gate speaker-specific nudges (label spkX, coverage ≥ th, no overlap/uncertain, min duration); generic nudges otherwise.

### Backend: Orchestration & event bus
- [x] **Backend:** Implement `SessionOrchestrator`: `start_session(stream_id, sr)`; wire audio → chunker → (PauseVAD, Diart, Chirp3); diar → timeline; stt + pauses → assembler → attributor → stitcher → UI + Coach; patch path → timeline → re-attribute impacted sentences.
- [x] **Design:** Output a plan for **EventBus and backpressure** (bounded queues per stream; drop policy: prefer keeping refine patches, drop preview frames when overloaded; lifecycle and cleanup). Implement after plan is approved.

### Preview + Refine/Patch
- [x] **Backend:** Preview path: ensure Diart frames → timeline → stabilized state; assembler uses final STT + pauses; attributor uses current timeline.
- [x] **Backend:** Refine path: Diart patch → `TimelineStore.apply_patch`; re-attribute UI sentences overlapping patched range within rolling window.
- [x] **Design:** Output a plan for **patch re-attribution and UI patch semantics** (which sentences to re-attribute, patch window 10–20s, `ui.sentence.patch` payload and cadence; no retroactive real-time nudges). Implement after plan is approved.

### Configuration
- [x] **Backend:** Wire shipping defaults from §5 (audio/chunking, Pause/VAD, stabilizer, sentence assembly, attribution) into config/settings.

### Observability & production hardening
- [x] **Observability:** Emit per-stream metrics: speaker switch rate (switches/min), %UNCERTAIN, %OVERLAP, avg dominant coverage, sentence length distribution, patch rate and patch-induced label changes.
- [x] **Observability:** Implement debug bundle for repro: last 30s PCM, diar timeline pre/post patch, STT segments, UI sentences + labels.

### Testing
- [x] **Tests:** Unit tests: timeline stabilization (commit rules, cooldown, OVERLAP/UNCERTAIN); pause splitting (pause_split_ms, merge); sentence split/stitch and attribution thresholds.
- [x] **Tests:** Integration tests: fixed audio fixtures → stable KPIs (switch rate, coverage, sentence lengths).
- [x] **Tests:** Shadow mode: evaluate threshold/config changes without affecting live UI.

### Frontend contract
- [x] **Frontend:** Consume `ui.sentence` events; render one label per speaker sentence; display `text`, `label`, `label_conf`, `coverage`, `flags` (overlap, uncertain, patched).
- [x] **Frontend:** If supported by backend plan: consume `ui.sentence.patch` for label/flag updates within patch window; avoid re-firing real-time nudge UX on patched labels.