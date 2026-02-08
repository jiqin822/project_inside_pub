import { apiService } from '../api/apiService';

const getAccessToken = () => {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('access_token');
};

/** Use same base as apiService so WebSocket URL matches REST API (and any runtime base URL). */
const getWsBaseUrl = (baseUrl: string) => {
  if (baseUrl.startsWith('https://')) {
    return baseUrl.replace('https://', 'wss://');
  }
  if (baseUrl.startsWith('http://')) {
    return baseUrl.replace('http://', 'ws://');
  }
  return `ws://${baseUrl}`;
};

/** Speaker source for debug: 'google' (Google diarization), 'nemo' (NeMo fallback), 'voice_id' (embedding match only), 'none' */
export type SttSpeakerSource = 'google' | 'nemo' | 'voice_id' | 'none';

export interface SttV2DebugInfo {
  segmentation?: Record<string, unknown> | null;
  speaker?: Record<string, unknown> | null;
}

export type AnalysisSentiment = 'Positive' | 'Neutral' | 'Negative' | 'Hostile';
export type AnalysisHorseman =
  | 'None'
  | 'Criticism'
  | 'Contempt'
  | 'Defensiveness'
  | 'Stonewalling';

export interface SttTranscriptEvent {
  type: 'stt.transcript';
  text: string;
  speaker_label: string;
  speaker_tag?: number;
  is_final?: boolean;
  segment_id?: number;
  start_ms?: number;
  end_ms?: number;
  confidence?: number;
  audio_segment_base64?: string;
  label_conf?: number;
  coverage?: number;
  flags?: Record<string, boolean>;
  debug?: SttV2DebugInfo;
  split_from?: string | null;
  speaker_color?: string | null;
  ui_context?: Record<string, unknown> | null;
  best_score_pct?: number;
  second_score_pct?: number;
  score_margin_pct?: number;
  best_user_suffix?: string;
  second_user_suffix?: string;
  /** NeMo debug: who assigned speaker (google diarization, nemo fallback, or none) */
  speaker_source?: SttSpeakerSource;
  /** NeMo debug: diarization speaker id when speaker_source === 'nemo' */
  nemo_speaker_id?: string | null;
  speaker_label_before?: string | null;
  speaker_label_after?: string | null;
  speaker_change_at_ms?: number | null;
  speaker_change_word_index?: number | null;
}

/** One cluster (known user or Unknown_N) and its similarity score for a segment. */
export interface SttClusterScore {
  label: string;
  score_pct: number;
}

export interface SttSpeakerResolvedEvent {
  type: 'stt.speaker_resolved';
  segment_id: number;
  speaker_label: string;
  text?: string;
  start_ms?: number;
  end_ms?: number;
  best_score_pct?: number;
  second_score_pct?: number;
  score_margin_pct?: number;
  best_user_suffix?: string;
  second_user_suffix?: string;
  /** Similarity score (0–100) for every cluster (known users + Unknown_N), sorted by score descending. */
  all_scores?: SttClusterScore[];
  label_conf?: number;
  coverage?: number;
  flags?: Record<string, boolean>;
  debug?: SttV2DebugInfo;
  split_from?: string | null;
  speaker_color?: string | null;
  ui_context?: Record<string, unknown> | null;
  sentiment?: AnalysisSentiment;
  horseman?: AnalysisHorseman;
  level?: number;
  nudgeText?: string;
  suggestedRephrasing?: string;
  analysisSource?: 'backend' | 'live';
  analysisPrompt?: string;
  speaker_source?: SttSpeakerSource;
  nemo_speaker_id?: string | null;
  speaker_label_before?: string | null;
  speaker_label_after?: string | null;
  speaker_change_at_ms?: number | null;
  speaker_change_word_index?: number | null;
}

export interface SttEscalationEvent {
  type: 'stt.escalation';
  severity: 'low' | 'medium' | 'high';
  reason: string;
  message: string;
}

export interface SttErrorEvent {
  type: 'stt.error';
  message: string;
}

/** NeMo diarization segment (for STT debug popup). */
export interface SttNemoDiarSegment {
  start_s: number;
  end_s: number;
  speaker_id: string;
}

export interface SttNemoDiarSegmentsEvent {
  type: 'stt.nemo_diar_segments';
  segments: SttNemoDiarSegment[];
}

export interface SttSession {
  sendAudio: (data: Float32Array) => void;
  disconnect: () => void;
}

export interface SttCallbacks {
  onTranscript: (event: SttTranscriptEvent) => void;
  onSpeakerResolved?: (event: SttSpeakerResolvedEvent) => void;
  onNemoDiarSegments?: (event: SttNemoDiarSegmentsEvent) => void;
  onEscalation?: (event: SttEscalationEvent) => void;
  onError?: (error: SttErrorEvent) => void;
  onOpen?: () => void;
  onClose?: () => void;
}

interface CreateSessionResponse {
  session_id: string;
  combined_voice_sample_base64?: string | null;
  speaker_user_ids_in_order?: string[];
}

export interface SttSessionOptions {
  candidateUserIds?: string[];
  languageCode?: string;
  minSpeakerCount?: number;
  maxSpeakerCount?: number;
  useV2?: boolean;
  debug?: boolean;
  /** When true (STT v2 only), skip diarization and use sentence boundary heuristic + embedding matching only. */
  skipDiarization?: boolean;
  /** When true, disable union-join of speaker labels in matching. */
  disableSpeakerUnionJoin?: boolean;
}

const float32ToInt16 = (data: Float32Array) => {
  const int16 = new Int16Array(data.length);
  for (let i = 0; i < data.length; i++) {
    const s = Math.max(-1, Math.min(1, data[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return int16.buffer;
};

export const createUiSentenceIdMapper = () => {
  const uiSentenceIdToSegmentId = new Map<string, number>();
  let uiSentenceCounter = 1;
  return (id: string | undefined) => {
    if (!id) return undefined;
    const existing = uiSentenceIdToSegmentId.get(id);
    if (existing != null) return existing;
    const hasSplitSuffix = /_a$|_b$/i.test(String(id));
    const numeric = Number(String(id).replace(/\D/g, ''));
    const assigned =
      !hasSplitSuffix && Number.isFinite(numeric) && numeric > 0
        ? numeric
        : uiSentenceCounter++;
    uiSentenceIdToSegmentId.set(id, assigned);
    return assigned;
  };
};

export const mapUiSentenceMessage = (
  message: {
    id?: string;
    text?: string;
    label?: string;
    start_ms?: number;
    startMs?: number;
    end_ms?: number;
    endMs?: number;
    label_conf?: number;
    labelConf?: number;
    coverage?: number;
    flags?: Record<string, boolean>;
    split_from?: string;
    splitFrom?: string;
    speaker_color?: string;
    speakerColor?: string;
    ui_context?: Record<string, unknown>;
    uiContext?: Record<string, unknown>;
    debug?: SttV2DebugInfo;
    audio_segment_base64?: string;
    audioSegmentBase64?: string;
  },
  getSegmentId: (id: string | undefined) => number | undefined
): SttTranscriptEvent => {
  return {
    type: 'stt.transcript',
    text: message.text ?? '',
    speaker_label: message.label ?? '',
    is_final: true,
    segment_id: getSegmentId(message.id),
    start_ms: message.start_ms ?? message.startMs,
    end_ms: message.end_ms ?? message.endMs,
    label_conf: message.label_conf ?? message.labelConf,
    coverage: message.coverage,
    flags: message.flags,
    split_from: message.split_from ?? message.splitFrom ?? null,
    speaker_color: message.speaker_color ?? message.speakerColor ?? null,
    ui_context: message.ui_context ?? message.uiContext ?? null,
    debug: message.debug,
    audio_segment_base64: message.audio_segment_base64 ?? message.audioSegmentBase64,
  };
};

export const mapUiSentencePatchMessage = (
  message: {
    id?: string;
    text?: string;
    label?: string;
    start_ms?: number;
    startMs?: number;
    end_ms?: number;
    endMs?: number;
    label_conf?: number;
    labelConf?: number;
    coverage?: number;
    flags?: Record<string, boolean>;
    split_from?: string;
    splitFrom?: string;
    speaker_color?: string;
    speakerColor?: string;
    ui_context?: Record<string, unknown>;
    uiContext?: Record<string, unknown>;
    sentiment?: string;
    horseman?: string;
    level?: number;
    nudgeText?: string;
    suggestedRephrasing?: string;
    debug?: SttV2DebugInfo;
  },
  getSegmentId: (id: string | undefined) => number | undefined
): SttSpeakerResolvedEvent | null => {
  const segmentId = getSegmentId(message.id);
  if (segmentId == null) return null;
  return {
    type: 'stt.speaker_resolved',
    segment_id: segmentId,
    speaker_label: message.label ?? '',
    text: message.text,
    start_ms: message.start_ms ?? message.startMs,
    end_ms: message.end_ms ?? message.endMs,
    speaker_source: 'none',
    label_conf: message.label_conf ?? message.labelConf,
    coverage: message.coverage,
    flags: message.flags,
    split_from: message.split_from ?? message.splitFrom ?? null,
    speaker_color: message.speaker_color ?? message.speakerColor ?? null,
    ui_context: message.ui_context ?? message.uiContext ?? null,
    sentiment: message.sentiment,
    horseman: message.horseman,
    level: message.level,
    nudgeText: message.nudgeText,
    suggestedRephrasing: message.suggestedRephrasing,
    debug: message.debug,
  };
};

export interface ConnectSttSessionResult {
  sttSession: SttSession;
  combinedVoiceSampleBase64: string | null;
  speakerUserIdsInOrder: string[];
}

/** Create STT session (HTTP only) and return voice sample + speaker order for Gemini. No WebSocket stream. */
export const createSttSessionOnly = async (
  options: SttSessionOptions
): Promise<{ combinedVoiceSampleBase64: string | null; speakerUserIdsInOrder: string[] }> => {
  const response = await apiService.createSttSession({
    candidate_user_ids: options.candidateUserIds ?? [],
    language_code: options.languageCode ?? undefined,
    min_speaker_count: options.minSpeakerCount,
    max_speaker_count: options.maxSpeakerCount,
    debug: options.debug,
    disable_speaker_union_join: options.disableSpeakerUnionJoin,
  });
  const payload = response.data as CreateSessionResponse;
  return {
    combinedVoiceSampleBase64: payload.combined_voice_sample_base64 ?? null,
    speakerUserIdsInOrder: payload.speaker_user_ids_in_order ?? [],
  };
};

export const connectSttSession = async (
  options: SttSessionOptions,
  callbacks: SttCallbacks
): Promise<ConnectSttSessionResult> => {
  const response = await apiService.createSttSession({
    candidate_user_ids: options.candidateUserIds ?? [],
    language_code: options.languageCode,
    min_speaker_count: options.minSpeakerCount,
    max_speaker_count: options.maxSpeakerCount,
    debug: options.debug,
    skip_diarization: options.skipDiarization,
    disable_speaker_union_join: options.disableSpeakerUnionJoin,
  });
  const payload = response.data as CreateSessionResponse;
  const token = apiService.getAccessToken() || getAccessToken();
  if (!token) {
    throw new Error('Missing access token for STT session');
  }
  const wsBase = getWsBaseUrl(apiService.getBaseUrl());
  const wsPath = options.useV2 ? '/v1/stt-v2/stream' : '/v1/stt/stream';
  const wsUrl = `${wsBase}${wsPath}/${payload.session_id}?token=${encodeURIComponent(token)}`;
  if (import.meta.env?.DEV) {
    console.log('[STT] WebSocket URL (token redacted):', wsUrl.replace(/\btoken=[^&]+/, 'token=…'));
  }
  const ws = new WebSocket(wsUrl);
  ws.binaryType = 'arraybuffer';
  const getSegmentIdForUiSentence = createUiSentenceIdMapper();

  ws.onopen = () => {
    callbacks.onOpen?.();
  };

  ws.onerror = (error) => {
    callbacks.onError?.({ type: 'stt.error', message: 'WebSocket error' });
  };

  ws.onclose = (event) => {
    callbacks.onClose?.();
  };

  ws.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data);
      if (message?.type === 'stt.transcript') {
        // Normalize: backend sends snake_case; accept camelCase from any source
        const normalized: SttTranscriptEvent = {
          type: 'stt.transcript',
          text: message.text ?? message.transcript ?? '',
          speaker_label: message.speaker_label ?? message.speakerLabel ?? '',
          speaker_tag: message.speaker_tag ?? message.speakerTag,
          is_final: message.is_final ?? message.isFinal,
          segment_id: message.segment_id ?? message.segmentId,
          start_ms: message.start_ms ?? message.startMs,
          end_ms: message.end_ms ?? message.endMs,
          confidence: message.confidence,
          audio_segment_base64: message.audio_segment_base64 ?? message.audioSegmentBase64,
          best_score_pct: message.best_score_pct ?? message.bestScorePct,
          second_score_pct: message.second_score_pct ?? message.secondScorePct,
          score_margin_pct: message.score_margin_pct ?? message.scoreMarginPct,
          best_user_suffix: message.best_user_suffix ?? message.bestUserSuffix,
          second_user_suffix: message.second_user_suffix ?? message.secondUserSuffix,
          speaker_source: message.speaker_source ?? message.speakerSource,
          nemo_speaker_id: message.nemo_speaker_id ?? message.nemoSpeakerId ?? null,
          speaker_label_before: message.speaker_label_before ?? message.speakerLabelBefore ?? null,
          speaker_label_after: message.speaker_label_after ?? message.speakerLabelAfter ?? null,
          speaker_change_at_ms: message.speaker_change_at_ms ?? message.speakerChangeAtMs ?? null,
          speaker_change_word_index: message.speaker_change_word_index ?? message.speakerChangeWordIndex ?? null,
        };
        callbacks.onTranscript(normalized);
        return;
      }
      if (message?.type === 'ui.sentence') {
        callbacks.onTranscript(mapUiSentenceMessage(message, getSegmentIdForUiSentence));
        return;
      }
      if (message?.type === 'ui.sentence.patch') {
        const resolved = mapUiSentencePatchMessage(message, getSegmentIdForUiSentence);
        if (resolved) callbacks.onSpeakerResolved?.(resolved);
        return;
      }
      if (message?.type === 'stt.speaker_resolved') {
        const resolved: SttSpeakerResolvedEvent = {
          type: 'stt.speaker_resolved',
          segment_id: message.segment_id ?? message.segmentId,
          speaker_label: message.speaker_label ?? message.speakerLabel ?? '',
          best_score_pct: message.best_score_pct ?? message.bestScorePct,
          second_score_pct: message.second_score_pct ?? message.secondScorePct,
          score_margin_pct: message.score_margin_pct ?? message.scoreMarginPct,
          best_user_suffix: message.best_user_suffix ?? message.bestUserSuffix,
          second_user_suffix: message.second_user_suffix ?? message.secondUserSuffix,
          all_scores: message.all_scores ?? message.allScores,
          speaker_source: message.speaker_source ?? message.speakerSource,
          nemo_speaker_id: message.nemo_speaker_id ?? message.nemoSpeakerId ?? null,
          speaker_label_before: message.speaker_label_before ?? message.speakerLabelBefore ?? null,
          speaker_label_after: message.speaker_label_after ?? message.speakerLabelAfter ?? null,
          speaker_change_at_ms: message.speaker_change_at_ms ?? message.speakerChangeAtMs ?? null,
          speaker_change_word_index: message.speaker_change_word_index ?? message.speakerChangeWordIndex ?? null,
        };
        callbacks.onSpeakerResolved?.(resolved);
        return;
      }
      if (message?.type === 'stt.nemo_diar_segments') {
        const segs = message.segments ?? [];
        const normalized: SttNemoDiarSegmentsEvent = {
          type: 'stt.nemo_diar_segments',
          segments: segs.map((s: { start_s?: number; end_s?: number; speaker_id?: string }) => ({
            start_s: s.start_s ?? 0,
            end_s: s.end_s ?? 0,
            speaker_id: s.speaker_id ?? '',
          })),
        };
        callbacks.onNemoDiarSegments?.(normalized);
        return;
      }
      if (message?.type === 'stt.escalation') {
        callbacks.onEscalation?.(message as SttEscalationEvent);
        return;
      }
      if (message?.type === 'stt.error') {
        callbacks.onError?.(message as SttErrorEvent);
        return;
      }
    } catch (err) {
      callbacks.onError?.({ type: 'stt.error', message: 'Failed to parse STT message' });
    }
  };

  ws.onerror = () => {
    callbacks.onError?.({ type: 'stt.error', message: 'STT WebSocket error' });
  };

  ws.onclose = (event) => {
    callbacks.onClose?.();
  };

  let sttSendCount = 0;
  const sttSession: SttSession = {
    sendAudio: (data: Float32Array) => {
      if (ws.readyState !== WebSocket.OPEN) {
        return;
      }
      sttSendCount++;
      ws.send(float32ToInt16(data));
    },
    disconnect: () => {
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    },
  };

  return {
    sttSession,
    combinedVoiceSampleBase64: payload.combined_voice_sample_base64 ?? null,
    speakerUserIdsInOrder: payload.speaker_user_ids_in_order ?? [],
  };
};
