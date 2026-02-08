"""Voice ID mapping for STT V2 speaker sentences."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Dict, List, Optional, Tuple

from app.api.stt.constants import LABEL_UNKNOWN_PREFIX
from app.api.stt.audio_processor import AudioProcessor
from app.api.stt_v2.audio_ring_buffer import AudioRingBuffer
from app.domain.stt.session_registry import SttSessionContext
from app.domain.stt.union_find import find as uf_find, union_prefer_root
from app.domain.stt_v2.contracts import (
    OVERLAP_LABEL,
    UNCERTAIN_LABEL,
    SpeakerSentence,
    StreamId,
    TimeRangeSamples,
)
from app.domain.voice.embeddings import (
    ECAPA_EMBEDDING_DIM,
    cosine_similarity,
    score_user_multi_embedding,
)
from app.settings import settings


@dataclass
class _MappingEntry:
    user_id: str
    score: float
    last_ms: int


@dataclass
class _PendingSwitch:
    user_id: str
    score: float
    first_ms: int
    count: int = 1


@dataclass
class _VoiceIdState:
    spk_to_user: Dict[str, _MappingEntry] = field(default_factory=dict)
    user_to_spk: Dict[str, str] = field(default_factory=dict)
    pending: Dict[str, _PendingSwitch] = field(default_factory=dict)


class VoiceIdMatcher:
    """Map diarization labels (spkX) to known user IDs with cache + smoothing."""

    def __init__(
        self,
        *,
        sample_rate: int,  # The sample rate of the audio (in Hz)
        ttl_ms: int = 45000,  # Time-to-live for label-to-user assignments in milliseconds
        persist_sentences: int = 1,  # How many past sentences to persist mapping for
        persist_ms: int = 800,  # How many ms to persist mapping for each assignment
        min_audio_ms: int = 400,  # Minimum length of audio (in ms) to consider for embedding
        embedding_provider: Optional[Callable[[bytes], Optional[list[float]]]] = None,  # Function to compute audio embeddings from bytes
    ) -> None:
        self.sample_rate = sample_rate
        self.ttl_ms = ttl_ms
        self.persist_sentences = max(1, persist_sentences)
        self.persist_ms = max(0, persist_ms)
        self.min_audio_ms = max(0, min_audio_ms)
        self.embedding_provider = embedding_provider
        self._streams: Dict[StreamId, _VoiceIdState] = {}

    def reset(self, stream_id: StreamId) -> None:
        self._streams.pop(stream_id, None)

    def map_label(
        self,
        stream_id: StreamId,
        sentence: SpeakerSentence,
        ctx: Optional[SttSessionContext],
        ring_buffer: AudioRingBuffer,
        audio_processor: AudioProcessor,
        *,
        debug_enabled: bool = False,
    ) -> SpeakerSentence:
        """
        Args:
            stream_id (StreamId): The ID of the audio stream.
            sentence (SpeakerSentence): The sentence to map.
            ctx (SttSessionContext): The session context containing voice embeddings.
            ring_buffer (AudioRingBuffer): The ring buffer containing audio samples.
            audio_processor (AudioProcessor): The audio processor to compute embeddings.
            debug_enabled (bool, optional): Whether to enable debug mode. Defaults to False.
        """
        if ctx is None or not (ctx.voice_embeddings or ctx.voice_embeddings_multi):
            return sentence

        label = sentence.label
        if label in (OVERLAP_LABEL, UNCERTAIN_LABEL):
            if label == UNCERTAIN_LABEL:
                mapped = self._map_uncertain_label(
                    stream_id,
                    sentence,
                    ctx,
                    ring_buffer,
                    audio_processor,
                    debug_enabled=debug_enabled,
                )
                if mapped is not None:
                    return mapped
            return sentence
        if not label.startswith("spk"):
            return sentence

        now_ms = sentence.ui_sentence.range_ms.end_ms
        state = self._state(stream_id)
        # Expire stale mappings so old speakers don't anchor new labels forever.
        self._expire(state, now_ms)
        cached = state.spk_to_user.get(label)

        audio_bytes = self._read_audio_bytes(sentence, stream_id, ring_buffer)
        if audio_bytes is None or self._audio_too_short(audio_bytes):
            return self._apply_cached_or_unknown(
                sentence, state, label, cached, now_ms, debug_enabled, ctx, reason="short_audio"
            )

        embedding = self._compute_embedding(audio_bytes, audio_processor)
        if embedding is None or len(embedding) != ECAPA_EMBEDDING_DIM:
            return self._apply_cached_or_unknown(
                sentence, state, label, cached, now_ms, debug_enabled, ctx, reason="no_embedding"
            )

        best_user, best_score = self._best_known_user(ctx, embedding)
        all_scores = (
            self._all_candidate_scores(ctx, embedding) if debug_enabled else None
        )
        threshold = settings.stt_speaker_match_threshold
        if best_user is None or best_score < threshold:
            return self._apply_cached_or_unknown(
                sentence, state, label, cached, now_ms, debug_enabled, ctx,
                reason="below_threshold", all_scores=all_scores,
            )

        # If the best match agrees with the cached mapping, refresh TTL and keep it stable.
        if cached and best_user == cached.user_id:
            self._refresh_mapping(state, label, cached.user_id, best_score, now_ms)
            return self._apply_mapping(
                sentence, cached.user_id, best_score, debug_enabled,
                reason="cached_match", all_scores=all_scores
            )

        if cached and best_user != cached.user_id:
            # Candidate switch: require margin + persistence to avoid flip-flopping.
            if best_score < cached.score + settings.stt_speaker_match_margin:
                self._refresh_mapping(state, label, cached.user_id, cached.score, now_ms)
                return self._apply_mapping(
                    sentence,
                    cached.user_id,
                    cached.score,
                    debug_enabled,
                    reason="margin_hold",
                    all_scores=all_scores,
                )
            pending = state.pending.get(label)
            if pending is None or pending.user_id != best_user:
                pending = _PendingSwitch(
                    user_id=best_user, score=best_score, first_ms=now_ms, count=1
                )
                state.pending[label] = pending
            else:
                pending.count += 1
                pending.score = max(pending.score, best_score)
            if pending.count < self.persist_sentences and (now_ms - pending.first_ms) < self.persist_ms:
                # Not enough evidence yet; keep the previous mapping for this label.
                self._refresh_mapping(state, label, cached.user_id, cached.score, now_ms)
                return self._apply_mapping(
                    sentence,
                    cached.user_id,
                    cached.score,
                    debug_enabled,
                    reason="pending_switch",
                    all_scores=all_scores,
                )

        if cached is None:
            pending = state.pending.pop(label, None)
            if pending and pending.user_id == best_user:
                best_score = max(best_score, pending.score)
        state.pending.pop(label, None)
        # Commit mapping and ensure a user_id does not remain bound to two labels.
        self._commit_mapping(state, label, best_user, best_score, now_ms, ctx)
        return self._apply_mapping(
            sentence, best_user, best_score, debug_enabled, reason="switched",
            all_scores=all_scores,
        )

    def _state(self, stream_id: StreamId) -> _VoiceIdState:
        if stream_id not in self._streams:
            self._streams[stream_id] = _VoiceIdState()
        return self._streams[stream_id]

    def _expire(self, state: _VoiceIdState, now_ms: int) -> None:
        for spk_label, entry in list(state.spk_to_user.items()):
            if now_ms - entry.last_ms > self.ttl_ms:
                state.spk_to_user.pop(spk_label, None)
                if state.user_to_spk.get(entry.user_id) == spk_label:
                    state.user_to_spk.pop(entry.user_id, None)
                state.pending.pop(spk_label, None)

    def _read_audio_bytes(
        self, sentence: SpeakerSentence, stream_id: StreamId, ring_buffer: AudioRingBuffer
    ) -> Optional[bytes]:
        start_ms = sentence.ui_sentence.range_ms.start_ms
        end_ms = sentence.ui_sentence.range_ms.end_ms
        if start_ms is None or end_ms is None or end_ms <= start_ms:
            return None
        start_sample = int((start_ms * self.sample_rate) / 1000)
        end_sample = int((end_ms * self.sample_rate) / 1000)
        if end_sample <= start_sample:
            return None
        samples = ring_buffer.read(
            stream_id,
            TimeRangeSamples(start=start_sample, end=end_sample, sr=self.sample_rate),
        )
        if samples is None or len(samples) == 0:
            return None
        return samples.tobytes()

    def _audio_too_short(self, pcm_bytes: bytes) -> bool:
        if self.min_audio_ms <= 0:
            return False
        min_samples = int(self.sample_rate * self.min_audio_ms / 1000)
        min_bytes = min_samples * 2
        return len(pcm_bytes) < min_bytes

    def _compute_embedding(
        self, pcm_bytes: bytes, audio_processor: AudioProcessor
    ) -> Optional[list[float]]:
        if self.embedding_provider:
            return self.embedding_provider(pcm_bytes)
        return audio_processor.compute_embedding_sync(pcm_bytes)

    def _best_known_user(
        self, ctx: SttSessionContext, embedding: list[float]
    ) -> Tuple[Optional[str], float]:
        best_user: Optional[str] = None
        best_score = 0.0
        for user_id, multi in ctx.voice_embeddings_multi.items():
            embeddings, meta = multi
            score = score_user_multi_embedding(
                embedding, embeddings, embeddings_meta=meta
            )
            if score > best_score:
                best_score = score
                best_user = user_id
        for user_id, centroid in ctx.voice_embeddings.items():
            if user_id in ctx.voice_embeddings_multi:
                continue
            score = cosine_similarity(embedding, centroid)
            if score > best_score:
                best_score = score
                best_user = user_id
        return best_user, best_score

    def _all_candidate_scores(
        self, ctx: SttSessionContext, embedding: list[float]
    ) -> List[Tuple[str, float]]:
        """Return (user_id, similarity) for every candidate, sorted by score descending."""
        scores: List[Tuple[str, float]] = []
        for user_id, multi in ctx.voice_embeddings_multi.items():
            embeddings, meta = multi
            score = score_user_multi_embedding(
                embedding, embeddings, embeddings_meta=meta
            )
            scores.append((user_id, score))
        for user_id, centroid in ctx.voice_embeddings.items():
            if user_id in ctx.voice_embeddings_multi:
                continue
            score = cosine_similarity(embedding, centroid)
            scores.append((user_id, score))
        scores.sort(key=lambda x: -x[1])
        return scores

    def _apply_cached_or_unknown(
        self,
        sentence: SpeakerSentence,
        state: _VoiceIdState,
        spk_label: str,
        cached: Optional[_MappingEntry],
        now_ms: int,
        debug_enabled: bool,
        ctx: SttSessionContext,
        *,
        reason: str,
        all_scores: Optional[List[Tuple[str, float]]] = None,
    ) -> SpeakerSentence:
        if cached:
            self._refresh_mapping(state, spk_label, cached.user_id, cached.score, now_ms)
            return self._apply_mapping(
                sentence, cached.user_id, cached.score, debug_enabled,
                reason=reason, all_scores=all_scores,
            )
        unknown_label = self._canonical_label(ctx, self._unknown_label(spk_label))
        return self._apply_mapping(
            sentence, unknown_label, sentence.label_conf, debug_enabled,
            voice_id=False, reason=reason, all_scores=all_scores,
        )

    def _map_uncertain_label(
        self,
        stream_id: StreamId,
        sentence: SpeakerSentence,
        ctx: SttSessionContext,
        ring_buffer: AudioRingBuffer,
        audio_processor: AudioProcessor,
        *,
        debug_enabled: bool = False,
    ) -> Optional[SpeakerSentence]:
        """
        Attempt to resolve an 'uncertain' speaker label by generating a voice embedding
        for the sentence's associated audio and matching it to known user embeddings. 
        
        If the audio is invalid, too short, or the computed embedding is not suitable, 
        returns None. If a best match score between the embedding and any known user is below 
        a configured threshold, also returns None. Otherwise, returns a SpeakerSentence mapped 
        to the most likely user.

        Args:
            stream_id (StreamId): The stream for which recognition is active.
            sentence (SpeakerSentence): The incoming sentence with an uncertain label.
            ctx (SttSessionContext): Session context containing known voice embeddings.
            ring_buffer (AudioRingBuffer): Ring buffer holding recent audio to extract features from.
            audio_processor (AudioProcessor): Extractor for voice embeddings.
            debug_enabled (bool, optional): Whether to include extra debug info in mapping result.
        
        Returns:
            Optional[SpeakerSentence]: The sentence mapped to a user if resolved, else None.
        """
        audio_bytes = self._read_audio_bytes(sentence, stream_id, ring_buffer)
        if audio_bytes is None or self._audio_too_short(audio_bytes):
            return None
        embedding = self._compute_embedding(audio_bytes, audio_processor)
        if embedding is None or len(embedding) != ECAPA_EMBEDDING_DIM:
            return None
        best_user, best_score = self._best_known_user(ctx, embedding)
        threshold = settings.stt_speaker_match_threshold
        if best_user is None or best_score < threshold:
            return None
        all_scores = (
            self._all_candidate_scores(ctx, embedding) if debug_enabled else None
        )
        flags = dict(sentence.flags or {})
        flags["uncertain"] = False
        return self._apply_mapping(
            replace(sentence, flags=flags),
            best_user,
            best_score,
            debug_enabled,
            reason="uncertain_voice_id",
            all_scores=all_scores,
        )

    def _unknown_label(self, label: str) -> str:
        if label.startswith(LABEL_UNKNOWN_PREFIX):
            return label
        return f"{LABEL_UNKNOWN_PREFIX}{label}"

    def _canonical_label(self, ctx: SttSessionContext, label: str) -> str:
        return uf_find(ctx.unknown_label_parent, label)

    def _union_spk_with_user(
        self, ctx: SttSessionContext, spk_label: str, user_id: str
    ) -> None:
        if getattr(ctx, "disable_speaker_union_join", False):
            return
        unknown_label = self._unknown_label(spk_label)
        union_prefer_root(
            ctx.unknown_label_parent,
            unknown_label,
            user_id,
            preferred_root=user_id,
        )

    def _refresh_mapping(
        self, state: _VoiceIdState, spk_label: str, user_id: str, score: float, now_ms: int
    ) -> None:
        state.spk_to_user[spk_label] = _MappingEntry(user_id=user_id, score=score, last_ms=now_ms)
        state.user_to_spk[user_id] = spk_label

    def _commit_mapping(
        self,
        state: _VoiceIdState,
        spk_label: str,
        user_id: str,
        score: float,
        now_ms: int,
        ctx: SttSessionContext,
    ) -> None:
        existing_spk = state.user_to_spk.get(user_id)
        if existing_spk and existing_spk != spk_label:
            # Enforce one-to-one mapping: a user_id can only own one spk label at a time.
            state.spk_to_user.pop(existing_spk, None)
            state.pending.pop(existing_spk, None)
            self._union_spk_with_user(ctx, existing_spk, user_id)
        self._refresh_mapping(state, spk_label, user_id, score, now_ms)
        self._union_spk_with_user(ctx, spk_label, user_id)

    def _apply_mapping(
        self,
        sentence: SpeakerSentence,
        label: str,
        score: float,
        debug_enabled: bool,
        *,
        voice_id: bool = True,
        reason: str,
        all_scores: Optional[List[Tuple[str, float]]] = None,
    ) -> SpeakerSentence:
        flags = dict(sentence.flags) if sentence.flags else {}
        if voice_id:
            flags["voice_id"] = True
        debug = sentence.debug
        if debug_enabled:
            debug = dict(debug or {})
            voice_id_debug: Dict = {
                "label": label,
                "score": float(score),
                "reason": reason,
            }
            if all_scores is not None:
                voice_id_debug["candidate_similarities"] = [
                    {"label": u, "score_pct": round(s * 100)} for u, s in all_scores
                ]
            debug["voice_id"] = voice_id_debug
        return SpeakerSentence(
            ui_sentence=sentence.ui_sentence,
            label=label,
            label_conf=score,
            coverage=sentence.coverage,
            flags=flags,
            audio_segment_base64=sentence.audio_segment_base64,
            debug=debug,
        )
