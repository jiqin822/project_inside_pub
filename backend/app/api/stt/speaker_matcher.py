"""
Speaker matching logic for STT stream.

Encapsulates resolution of segment embeddings to speaker labels (user_id or Unknown_N)
using voice_embeddings, unknown_voice_embeddings, union-find, and NeMo tag/label mapping.
"""
from __future__ import annotations

from typing import Optional

from app.domain.stt.session_registry import SttSessionContext
from app.domain.stt.union_find import find as uf_find
from app.domain.voice.embeddings import (
    ECAPA_EMBEDDING_DIM,
    cosine_similarity,
)

from app.api.stt.constants import (
    DEFAULT_LARGE_MARGIN,
    DEFAULT_MATCH_MARGIN,
    LABEL_ANON_PREFIX,
    LABEL_UNKNOWN_PREFIX,
)
from app.settings import settings


class SpeakerMatcher:
    """
    Resolves segment embeddings to speaker labels (user_id or Unknown_N).

    Uses session voice_embeddings, unknown_voice_embeddings, union-find for
    unknown canonicalization, and optional NeMo speaker tag/label mapping.
    """

    def get_or_assign_nemo_tag(self, ctx: SttSessionContext, nemo_speaker_id: str) -> int:
        """
        Return a stable numeric tag for a NeMo speaker id (for WebSocket contract).
        First time we see this id we assign the next tag and store it; later we return the same tag.
        """
        existing = ctx.nemo_speaker_id_to_tag.get(nemo_speaker_id)
        if existing is not None:
            return existing
        tag = ctx.nemo_next_tag
        ctx.nemo_next_tag += 1
        ctx.nemo_speaker_id_to_tag[nemo_speaker_id] = tag
        return tag

    def get_or_assign_nemo_label(self, ctx: SttSessionContext, nemo_speaker_id: str) -> str:
        """
        Return a display label for a NeMo speaker id: existing mapping or new Anon_N.
        Used when we have no embedding match yet; may be replaced by user_id after labeling.
        """
        existing = ctx.nemo_speaker_id_to_label.get(nemo_speaker_id)
        if existing:
            return existing
        ctx.nemo_anon_counter += 1
        label = f"{LABEL_ANON_PREFIX}{ctx.nemo_anon_counter}"
        ctx.nemo_speaker_id_to_label[nemo_speaker_id] = label
        return label

    def match_known_user_only(
        self, ctx: SttSessionContext, segment_embedding: Optional[list[float]]
    ) -> Optional[str]:
        """
        Return user_id if best known match >= threshold (no Unknown_N logic).
        Used for one-shot NeMo speaker labeling; does not create or update unknown labels.
        """
        if not segment_embedding or len(segment_embedding) != ECAPA_EMBEDDING_DIM:
            return None
        best_label = None
        best_score = 0.0
        for user_id, embedding in ctx.voice_embeddings.items():
            score = cosine_similarity(segment_embedding, embedding)
            if score > best_score:
                best_score = score
                best_label = user_id
        if best_label and best_score >= settings.stt_speaker_match_threshold:
            return best_label
        return None

    def canonical_unknown(self, ctx: SttSessionContext, label: str) -> str:
        """Return canonical unknown label (union-find root). Defensive find so interim-created labels never KeyError."""
        return uf_find(ctx.unknown_label_parent, label)

    def match_unknown_speaker(
        self,
        segment_embedding: list[float],
        unknown_voice_embeddings: dict[str, list[float]],
    ) -> Optional[str]:
        """Return best-matching unknown label if score >= threshold (and margin when multiple unknowns), else None."""
        if not segment_embedding or not unknown_voice_embeddings:
            return None
        match_margin = getattr(settings, "stt_speaker_match_margin", DEFAULT_MATCH_MARGIN)
        best_label = None
        best_score = 0.0
        second_score = 0.0
        for label, embedding in unknown_voice_embeddings.items():
            score = cosine_similarity(segment_embedding, embedding)
            if score > best_score:
                second_score = best_score
                best_score = score
                best_label = label
            elif score > second_score:
                second_score = score
        if not best_label or best_score < settings.stt_speaker_match_threshold:
            return None
        if len(unknown_voice_embeddings) <= 1 or (best_score - second_score) >= match_margin:
            return best_label
        return None

    def best_unknown_score(
        self,
        segment_embedding: list[float],
        unknown_voice_embeddings: dict[str, list[float]],
    ) -> float:
        """Return the best cosine similarity score to any unknown embedding, or 0.0 if none."""
        if not segment_embedding or not unknown_voice_embeddings:
            return 0.0
        best = 0.0
        for embedding in unknown_voice_embeddings.values():
            s = cosine_similarity(segment_embedding, embedding)
            if s > best:
                best = s
        return best

    def score_known_voice_embeddings(
        self,
        ctx: SttSessionContext,
        segment_embedding: Optional[list[float]],
    ) -> tuple[Optional[str], float, Optional[str], float]:
        """Score segment against known users; return (best_label, best_score, second_label, second_score)."""
        best_label: Optional[str] = None
        best_score = 0.0
        second_label: Optional[str] = None
        second_score = 0.0
        if segment_embedding:
            for user_id, embedding in ctx.voice_embeddings.items():
                score = cosine_similarity(segment_embedding, embedding)
                if score > best_score:
                    second_score = best_score
                    second_label = best_label
                    best_score = score
                    best_label = user_id
                elif score > second_score:
                    second_score = score
                    second_label = user_id
        return (best_label, best_score, second_label, second_score)

    def accept_best_known_by_large_margin(
        self,
        ctx: SttSessionContext,
        best_label: Optional[str],
        best_score: float,
        second_label: Optional[str],
        second_score: float,
    ) -> Optional[str]:
        """Return best_label if it is a clear winner by large margin (>=2 known users), else None."""
        if not best_label or best_label not in ctx.voice_embeddings:
            return None
        if len(ctx.voice_embeddings) < 2 or (best_score - second_score) < DEFAULT_LARGE_MARGIN:
            return None
        return best_label

    def create_new_unknown(
        self, ctx: SttSessionContext, segment_embedding: Optional[list[float]]
    ) -> str:
        """Create a new Unknown_N label, register in union-find and optionally store embedding; return canonical label."""
        ctx.unknown_counter += 1
        unknown_label = f"{LABEL_UNKNOWN_PREFIX}{ctx.unknown_counter}"
        ctx.unknown_label_parent[unknown_label] = unknown_label
        if segment_embedding is not None:
            ctx.unknown_voice_embeddings[unknown_label] = segment_embedding
        return self.canonical_unknown(ctx, unknown_label)

    def match_speaker_label_no_tag(
        self, ctx: SttSessionContext, segment_embedding: Optional[list[float]]
    ) -> str:
        """
        Resolve speaker label when there is no speaker_tag (no diarization).
        Uses voice_embeddings and unknown_voice_embeddings with threshold and margin;
        creates new Unknown_N and updates union-find when no match.
        """
        best_label, best_score, second_label, second_score = self.score_known_voice_embeddings(
            ctx, segment_embedding
        )
        match_margin = getattr(settings, "stt_speaker_match_margin", DEFAULT_MATCH_MARGIN)
        if (
            best_label
            and best_label in ctx.voice_embeddings
            and best_score >= settings.stt_speaker_match_threshold
        ):
            if len(ctx.voice_embeddings) <= 1 or (best_score - second_score) >= match_margin:
                return best_label
            # Two known users close in score: prefer known only if unknown isn't clearly better
            if not segment_embedding or not ctx.unknown_voice_embeddings:
                return best_label
            best_unknown_s = self.best_unknown_score(
                segment_embedding, ctx.unknown_voice_embeddings
            )
            prefer_known_gap = getattr(
                settings, "stt_prefer_known_over_unknown_gap", DEFAULT_MATCH_MARGIN
            )
            if best_unknown_s <= best_score + prefer_known_gap:
                return best_label
            matched_unknown = self.match_unknown_speaker(
                segment_embedding, ctx.unknown_voice_embeddings
            )
            if matched_unknown:
                return self.canonical_unknown(ctx, matched_unknown)
            return self.create_new_unknown(ctx, segment_embedding)
        large_margin_label = self.accept_best_known_by_large_margin(
            ctx, best_label, best_score, second_label, second_score
        )
        if large_margin_label is not None:
            return large_margin_label
        if segment_embedding:
            matched_unknown = self.match_unknown_speaker(
                segment_embedding, ctx.unknown_voice_embeddings
            )
            if matched_unknown:
                return self.canonical_unknown(ctx, matched_unknown)
        return self.create_new_unknown(ctx, segment_embedding)

    def match_speaker_label_with_tag(
        self,
        speaker_tag: int,
        ctx: SttSessionContext,
        segment_embedding: Optional[list[float]],
    ) -> str:
        """
        Resolve speaker label when we have a speaker_tag (Google/NeMo diarization).
        Scores against voice_embeddings and unknown_voice_embeddings; caches result in
        speaker_tag_to_label. Reuses cached label when no embedding (e.g. interim).
        """
        best_label, best_score, second_label, second_score = self.score_known_voice_embeddings(
            ctx, segment_embedding
        )
        if (
            best_label
            and best_label in ctx.voice_embeddings
            and best_score >= settings.stt_speaker_match_threshold
        ):
            ctx.speaker_tag_to_label[speaker_tag] = best_label
            return best_label
        large_margin_label = self.accept_best_known_by_large_margin(
            ctx, best_label, best_score, second_label, second_score
        )
        if large_margin_label is not None:
            ctx.speaker_tag_to_label[speaker_tag] = large_margin_label
            return large_margin_label
        if segment_embedding:
            matched_unknown = self.match_unknown_speaker(
                segment_embedding, ctx.unknown_voice_embeddings
            )
            if matched_unknown:
                canonical = self.canonical_unknown(ctx, matched_unknown)
                ctx.speaker_tag_to_label[speaker_tag] = canonical
                return canonical
        # No embedding this time: reuse cached label if it's a valid Unknown_N or known user
        if not segment_embedding and speaker_tag in ctx.speaker_tag_to_label:
            cached = ctx.speaker_tag_to_label[speaker_tag]
            if cached and (
                cached.startswith(LABEL_UNKNOWN_PREFIX) or cached in ctx.voice_embeddings
            ):
                return (
                    self.canonical_unknown(ctx, cached)
                    if cached.startswith(LABEL_UNKNOWN_PREFIX)
                    else cached
                )
            ctx.speaker_tag_to_label.pop(speaker_tag, None)
        canonical = self.create_new_unknown(ctx, segment_embedding)
        ctx.speaker_tag_to_label[speaker_tag] = canonical
        return canonical

    def match_speaker_label(
        self,
        speaker_tag: Optional[int],
        ctx: SttSessionContext,
        segment_embedding: Optional[list[float]],
    ) -> str:
        """
        Return speaker label: user_id if known match above threshold, else canonical unknown (union-find).
        Dispatches to match_speaker_label_no_tag (no diarization) or match_speaker_label_with_tag.
        """
        if speaker_tag is None:
            return self.match_speaker_label_no_tag(ctx, segment_embedding)
        return self.match_speaker_label_with_tag(speaker_tag, ctx, segment_embedding)
