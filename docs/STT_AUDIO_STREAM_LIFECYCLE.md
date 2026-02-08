# STT Incoming Audio Stream Lifecycle

This document describes the full lifecycle of an incoming audio stream through the STT (Speech-to-Text) pipeline: ingestion, segment and boundary computation, diarization combination, speaker attribution, analysis, and outbound messages at each stage.

---

## 1. Overview

High-level pipeline:

```
  Session                    Ingestion                    Workers
  ---------                  ---------                    -------
  POST /session  ──►  WS /stream  ──►  Binary chunk  ──┬──►  audio_queue      ──►  Google thread
       │                    │                          ├──►  sortformer_queue ──►  Sortformer task
       └────────────────────┘                          └──►  Ring buffer      ──►  NeMo diarization task
                                                                                            │
  Response path                                                                              │
  -------------                                                                              ▼
  handle_stt_response_message  ◄──  Google thread     (responses scheduled on event loop)
       │
       └──► build_segments_from_result ──┬──► _handle_final_segment   ──► stt.transcript + stt.speaker_resolved
                                        └──► _handle_interim_segment  ──► stt.transcript
```

Before streaming, a client creates a session and then connects over WebSocket.

- **POST /session** ([backend/app/api/stt/routes_stt.py](backend/app/api/stt/routes_stt.py): `create_stt_session`  
  Creates the session: loads voice embeddings for `candidate_user_ids`, registers `SttSessionContext` in `stt_registry`, and returns `session_id` for the WebSocket. The context holds `voice_embeddings`, `speaker_timeline` (initially empty), `speaker_tag_to_label`, and NeMo/ring-buffer–related state.

- **WS /stream/{session_id}**  
  `stream_stt` accepts the WebSocket; `validate_stream_stt_request` checks token and session ownership; `ensure_stt_credentials_and_client` creates the Google Speech client. Then:
  - **Queues/buffers**: `audio_queue` (raw chunks for Google), `sortformer_queue` (chunk + start_sample, end_sample for NeMo), `AudioRingBuffer` (sample-indexed rolling PCM).
  - **Workers started**: `run_google_streaming_recognize` runs in a **thread** (blocking); optionally `run_nemo_diarization_worker` and `run_sortformer_timeline_worker` as **async tasks** when NeMo fallback is on and Google diarization is off.

---

## 2. Ingestion

Each binary chunk received on the WebSocket is fed to three consumers:

```
  Client                    stream_stt
    │                            │
    │  receive_bytes(chunk)      │
    ├──────────────────────────►│
    │                            │  append(chunk)
    │                            ├──────────────► Ring buffer
    │                            │  put(chunk)
    │                            ├──────────────► audio_queue  ──► Google thread (request_generator_sync)
    │                            │  put((chunk, start_sample, end_sample))
    │                            └──────────────► sortformer_queue ──► Sortformer worker (accumulate → diarize_pcm16 → speaker_timeline)
                                                                      NeMo worker reads ring buffer tail → diarize_pcm16 → nemo_latest_segments
```

- **Functions**: In `stream_stt`, the receive loop calls `websocket.receive_bytes()`, then `ring_buffer.append(chunk)`, `audio_queue.put(chunk)`, and `sortformer_queue.put((chunk, start_sample, end_sample))`.
- **Timebase**: All sample indices are relative to the ring buffer. `stream_base = ctx.stream_start_samples` when the Google stream starts, so stream-relative seconds = `(sample - stream_base) / 16000` (16 kHz).

---

## 3. Segment building

The **thread** `run_google_streaming_recognize` consumes `request_generator_sync(enable_diarization)` (first config + streaming_config, then one request per chunk until `None`). For each Google `response`, it schedules on the event loop:

- `handle_stt_response_message(response, stream_base, deps, last_escalation_at_ref)`.

**handle_stt_response_message** iterates `response.results`; for each result with alternatives it calls:

- **build_segments_from_result(result, deps, stream_base)**  
  Returns `(segments_to_send, diarization_script_intervals, timeline_snapshot)`.

Segment-building branches:

```
  StreamingRecognize result
           │
           ├── result.is_final and words? ──Yes──► _group_words_by_speaker
           │                                              │
           │                                    one group? ──Yes──► one segment (word start/end)
           │                                    many? ──Yes──► one segment per group
           │
           └── No ──► result.is_final and text? ──Yes──► timeline or nemo?
           │                    │                              │
           │                    │                    Yes ──► derive_and_segment
           │                    │                              │
           │                    │                              ├── script span (timeline or nemo)
           │                    │                              ├── stream intervals
           │                    │                              ├── sub_spans_from_length_heuristic
           │                    │                              └── assign_text_to_sub_spans ──► segments (from_diarization=True)
           │                    │                              No ──► one segment, no times
           │                    └── No ──► one interim segment
```

### Segment and boundary logic inside build_segments_from_result

**Final result with word-level times (Google words):**

- **One speaker group**: one segment `(text, words, speaker_tag, start_s, end_s from first/last word, False)`.
- **Multiple speaker groups**: `_group_words_by_speaker(words)`; per group, segment = `(seg_text, group, seg_tag, raw_start_s, raw_end_s, False)`.
- Boundaries = word offsets converted via `_duration_to_seconds(words[0].start_offset)` / `words[-1].end_offset`.

**Final result with no/minimal word times but speaker_timeline or NeMo available:**

- Takes `timeline_snapshot` from `ctx.speaker_timeline` (under `timeline_lock`) and `nemo_snapshot = ctx.nemo_latest_segments`.
- **derive_and_segment** ([backend/app/domain/stt/script_boundary.py](backend/app/domain/stt/script_boundary.py)):
  - **Script span**: from `derive_script_span_from_timeline(timeline, stream_base, total_samples, lag_ms)` or `derive_script_span_from_nemo(nemo_segments, stream_base, max_end_s)`.
  - **Stream intervals**: from timeline or NeMo in that script window (`_timeline_to_stream_intervals` / `_nemo_to_stream_intervals`).
  - **sub_spans_from_length_heuristic(script_start_s, script_end_s, intervals)**: splits into sub-spans using pause length (e.g. 800 ms long pause, 500 ms soft, 350 ms candidate), MIN_SEG_LEN_S (1.2 s), SOFT_MAX (12 s), HARD_MAX (15 s).
- **assign_text_to_sub_spans(text, sub_spans)**: assigns transcript text to sub-spans by duration proportion; returns `(text_chunk, start_s, end_s)`.
- Segments = one per sub-span with `from_diarization=True`; **diarization_script_intervals** = the stream intervals used for later audio extraction.
- Audio boundaries at this stage = sub-span (start_s, end_s) from the length heuristic; exact bounds for extraction are refined with **intervals_in_sub_span** in the next step.

**Interim result:** one segment `(text, words, speaker_tag, None, None, False)`.

---

## 4. Audio boundaries and extraction (final segments only)

**extract_segment_audio** ([backend/app/api/stt/routes_stt.py](backend/app/api/stt/routes_stt.py))  
Given a segment, ring buffer, `stream_base`, `timeline_snapshot`, and `diarization_script_intervals`:

```
  Segment (raw_start_s, raw_end_s, from_diarization)
           │
           ├── result_is_final? ──No──► samples = None
           │
           └── Yes ──► raw_start_s and raw_end_s?
                        │
                        ├── Yes ──► from_diarization and intervals?
                        │              │
                        │              ├── Yes ──► intervals_in_sub_span → min/max, clamp → ring_buffer.slice
                        │              │              └── timeline_snapshot? → extract_clean_pcm_for_segment → (samples, start_sample, end_sample)
                        │              └── No ──► pad raw times, min 3s window → ring_buffer.slice → (samples, start_sample, end_sample)
                        │
                        └── No ──► has_voice_embeddings? ──Yes──► trailing 4s window → (samples, start_sample, end_sample)
                                                └── No ──► samples = None
```

- If **from_diarization** and **diarization_script_intervals**: uses **intervals_in_sub_span((raw_start_s, raw_end_s), diarization_script_intervals)** ([backend/app/domain/stt/script_boundary.py](backend/app/domain/stt/script_boundary.py)) to get sub-intervals clipped to the segment span, then min(start)/max(end) of those (with MIN_SEGMENT_DURATION_S and clamp to buffer). Converts to `start_sample`/`end_sample`, slices the ring buffer. If **timeline_snapshot** is present, **extract_clean_pcm_for_segment** ([backend/app/domain/stt/speaker_timeline_attribution.py](backend/app/domain/stt/speaker_timeline_attribution.py)) keeps only single-speaker regions and replaces segment PCM for better embedding quality.
- Else (Google word times): uses raw_start_s/raw_end_s with small padding and a minimum window (e.g. 3 s), then slice.
- Else (final but no times, has voice embeddings): fallback trailing window (e.g. 4 s).

Returns `(samples, start_sample, end_sample, seg_abs_start_s, seg_abs_end_s)`.

---

## 5. Diarization combination and speaker sources

Two diarization feeds (when NeMo fallback is on and Google diarization is off):

```
  Sortformer timeline              NeMo rolling window
  -------------------              -------------------
  sortformer_queue                 Ring buffer tail
         │                                  │
         ▼                                  ▼
  Accumulate chunks                diarize_pcm16
         │                                  │
         ▼                                  ▼
  diarize_pcm16                    ctx.nemo_latest_segments
         │
         ├──► ctx.speaker_timeline
         └──► spk_tracks, track embeddings
```

**Speaker timeline (Sortformer):**  
`run_sortformer_timeline_worker` consumes `sortformer_queue`, accumulates chunks until a window (e.g. 12 s), runs **diarize_pcm16** (NeMo), and appends **DiarInterval** `(start_sample, end_sample, spk_id, conf, overlap_flag)` to **ctx.speaker_timeline** (under `timeline_lock`). It also updates **spk_tracks** with clean speech and track embeddings; **update_track_label_from_embedding** maps tracks to known users when possible.

**NeMo rolling window:**  
`run_nemo_diarization_worker` periodically slices the ring buffer tail, runs **diarize_pcm16**, and sets **ctx.nemo_latest_segments** = `[(start_s, end_s, speaker_id), ...]` in stream time. It may send **stt.nemo_diar_segments** to the client.

**Final-segment speaker/source** ([backend/app/api/stt/routes_stt.py](backend/app/api/stt/routes_stt.py)): **_resolve_final_segment_speaker_and_source**

- If NeMo fallback is on and Google diarization is off: **best_overlap_speaker_id(ctx.nemo_latest_segments, seg_abs_start_s, seg_abs_end_s)** yields nemo_speaker_id; under **nemo_label_lock**, **get_or_assign_nemo_tag** / **get_or_assign_nemo_label** (Anon_K or known). Source = **SPEAKER_SOURCE_NEMO**.
- Else if the segment has a Google tag/words: source = **SPEAKER_SOURCE_GOOGLE**.
- Else **SPEAKER_SOURCE_NONE**.

---

## 6. Speaker ID (attribution) and responses

Final-segment attribution and outbound flow:

```
  Final segment (samples, start_sample, end_sample)
           │
           ▼
  _resolve_final_segment_speaker_and_source
           │
           ▼
  end_sample <= reliable_end?
           │
     Yes   │   No
     ┌─────┴─────┐
     ▼           └──────────────────────────────┐
  query_speaker_timeline                          │
     │                                            ▼
     ▼                                    voice_embeddings?
  label and not UNCERTAIN?                        │
     │                                      Yes   │   No
     │ Yes     │ No                            ┌──┴──┐
     ▼         ▼                              ▼     └──► send stt.transcript only
  send stt.transcript +              _get_pcm_for_embedding
  stt.speaker_resolved                       │
  (speaker_source=voice_id)                  ▼
                                    _schedule_speaker_resolution
                                             │
                                    NeMo Anon and attempt?
                                       │ Yes    │ No
                                       ▼        ▼
                              run_nemo_label   run_voice_id_then_send
                              _then_send             │
                                  │                  ▼
                                  │           _match_speaker_label
                                  │                  │
                                  └──────┬───────────┘
                                         ▼
                                send stt.speaker_resolved
```

**Timeline attribution** (when the segment is inside the “reliable” window):  
**_query_timeline_attribution** uses **diarization_reliable_end_sample** (now - lag_ms) and **query_speaker_timeline** ([backend/app/domain/stt/speaker_timeline_attribution.py](backend/app/domain/stt/speaker_timeline_attribution.py)) over `[start_sample, end_sample]`: it sums per-speaker overlap samples and returns dominant speaker label (or OVERLAP / UNCERTAIN), confidence, is_overlap, and attribution_source.

**If timeline attribution returns a label:**  
Send **stt.transcript** (`build_transcript_payload`) then **stt.speaker_resolved** (`build_speaker_resolved_payload`) with speaker_source=voice_id; no async voice-id task.

**Else (voice embeddings path):**  
**_get_pcm_for_embedding** chooses clean PCM (from timeline) when in the reliable window, else full segment; **_schedule_speaker_resolution** schedules either:

- **run_nemo_label_then_send**: match segment embedding to known users only; if match, update nemo_speaker_id_to_label and send **stt.speaker_resolved** (source NeMo).
- **run_voice_id_then_send**: **_match_speaker_label** (voice_embeddings + unknown_voice_embeddings, threshold/margin); send **stt.speaker_resolved** with scores and optional label change; may append to **user_segment_embeddings** for session-end centroid.

**Interim segments:**  
**_resolve_interim_speaker_label** (speaker_tag_to_label / Unknown_N under voice_id_lock); only **stt.transcript** (is_final=False) is sent; no speaker_resolved.

---

## 7. Analysis and other outbound messages

**Escalation:**  
For each segment text, **detect_escalation(seg_text)** ([backend/app/domain/stt/escalation.py](backend/app/domain/stt/escalation.py)); if present, **_send_escalation_if_allowed** (cooldown) sends **stt.escalation** (severity, reason, message).

**Errors:**  
**stt.error** is sent for validation failures, credentials/recognizer issues, or when `run_google_streaming_recognize` raises (e.g. after retrying without diarization).

---

## 8. Outbound messages summary

When each message type is sent:

```
  Trigger                      Message
  ------                       -------
  Interim result               ──► stt.transcript
  Final + timeline label       ──► stt.transcript + stt.speaker_resolved
  Final + voice-id or NeMo     ──► stt.transcript, then (async) stt.speaker_resolved
  Escalation                   ──► stt.escalation
  NeMo diarization             ──► stt.nemo_diar_segments
  Error                        ──► stt.error
```

| Step / trigger | Message type | When |
|----------------|-------------|------|
| Interim result | stt.transcript | Every interim segment; is_final=False; no audio, no speaker_resolved. |
| Final segment (timeline-attributed) | stt.transcript + stt.speaker_resolved | Segment in reliable window and query_speaker_timeline returns a label. |
| Final segment (voice-id / NeMo) | stt.transcript then (async) stt.speaker_resolved | After run_voice_id_then_send or run_nemo_label_then_send. |
| Escalation | stt.escalation | When detect_escalation fires and cooldown elapsed. |
| NeMo diarization (optional) | stt.nemo_diar_segments | Periodic from run_nemo_diarization_worker. |
| Error / close | stt.error | Validation or Google/client errors. |

Payloads are built by **build_transcript_payload** (text, speaker_label, is_final, start_ms, end_ms, confidence, audio_segment_base64 for final, speaker_source, etc.) and **build_speaker_resolved_payload** (segment_id, speaker_label, speaker_source, confidence, scores, attribution_source, etc.).

---

## 9. Shutdown

On WebSocket disconnect or error, **stream_stt** runs `finally`:

- **_stream_stt_shutdown**: sets stop_event and nemo_worker_stop, cancels NeMo and Sortformer tasks, puts None into audio and sortformer queues, cancels and gathers pending_voice_id_tasks and pending_nemo_label_tasks, then sleeps SESSION_END_SLEEP_BEFORE_CENTROID_S.
- **_update_voice_centroids_after_session**: if enabled and ctx has user_segment_embeddings, blends session segment embeddings into user voice profiles and persists via VoiceRepository.
- Executor shutdown and **stt_registry.delete(session_id)**.
