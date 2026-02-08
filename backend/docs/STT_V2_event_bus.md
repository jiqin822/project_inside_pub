## STT V2 EventBus and Backpressure

This document defines queueing and backpressure behavior for the STT V2 pipeline.

### Goals
- Bounded queues per stream to prevent memory growth.
- Keep refine patches when overloaded; drop preview frames first.
- Maintain deterministic lifecycle and cleanup on disconnect.

### Queues (per stream)
- `audio_queue` (raw PCM chunks)
- `frame_queue` (AudioFrame)
- `window_queue` (AudioWindow)
- `diar_queue` (DiarFrame / DiarPatch)
- `stt_queue` (SttSegment)
- `ui_queue` (UiSentence / SpeakerSentence)

### Backpressure policy
1. If `window_queue` or `diar_queue` are full:
   - drop **preview** diar frames first
   - keep **refine** patches whenever possible
2. If `audio_queue` is full:
   - drop oldest chunk (or backoff on input)
3. If `stt_queue` is full:
   - prefer emitting **final** segments only; drop partials

### Lifecycle
- On `start_session(stream_id, sr)`: initialize queues, services, and worker tasks.
- On disconnect:
  - cancel worker tasks
  - flush pending final UI sentences
  - release per-stream buffers and queues

### Metrics (for tuning)
- queue depth and drop rate per queue
- preview frame drop ratio
- patch retention ratio

### Notes
- Async `asyncio.Queue(maxsize=...)` is sufficient for an initial implementation.
- Drop policy should be centralized in the orchestrator to ensure consistent behavior.
