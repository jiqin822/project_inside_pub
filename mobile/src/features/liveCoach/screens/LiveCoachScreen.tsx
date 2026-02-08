
import React, { useEffect, useRef, useState, useCallback, useLayoutEffect, useMemo } from 'react';
import { Mic, MicOff, Play, Square, BarChart2, Terminal, Bug, X } from 'lucide-react';
import { apiService } from '../../../shared/api/apiService';
import { connectLiveCoach, AnalysisData } from '../../../shared/services/geminiService';
import { connectSttSession, createSttSessionOnly, SttSession, SttSessionOptions, SttTranscriptEvent, SttSpeakerResolvedEvent, SttNemoDiarSegmentsEvent, SttEscalationEvent, SttV2DebugInfo } from '../../../shared/services/sttService';
import { getMicrophoneStream } from '../../../shared/utils/mediaDevices';
import { sendWatchNudge } from '../../../shared/services/watchNudge';
import { RoomLayout } from '../../../shared/ui/RoomLayout';
import { useSessionStore } from '../../../stores/session.store';
import { useRelationshipsStore } from '../../../stores/relationships.store';
import { useRealtimeStore } from '../../../stores/realtime.store';

/** When true, backend STT provides transcription and speaker identification; Gemini is used only for emotional coaching (sentiment, horseman) and turn definition, merged into STT rows. */
const USE_BACKEND_STT = true;
const ANALYSIS_LATENCY_LOG_MAX = 50;
const PROFILE_ENTRIES_MAX = 30;

/** Only resolve Unknown_* to a display name when best_score_pct is at least this (avoids labeling all segments as the same speaker when scores are low). */
const SPEAKER_RESOLVE_MIN_SCORE_PCT = 40;

const RING_SAMPLE_RATE = 16000;
const RING_SECONDS = 5;
const RING_CAPACITY = RING_SAMPLE_RATE * RING_SECONDS;
const VOICE_MATCH_SECONDS = 3;

/** Copy last N seconds of Float32 mono (16kHz) from ring buffer into a new Float32Array. */
function getLastNSamplesFromRing(
  buffer: Float32Array,
  writeIndex: number,
  totalWritten: number,
  sampleRate: number,
  seconds: number
): Float32Array {
  const want = Math.min(sampleRate * seconds, totalWritten, buffer.length);
  if (want <= 0) return new Float32Array(0);
  const out = new Float32Array(want);
  const start = (writeIndex - want + buffer.length) % buffer.length;
  for (let i = 0; i < want; i++) {
    out[i] = buffer[(start + i) % buffer.length];
  }
  return out;
}

/** Convert Float32Array (mono) to WAV Blob (16-bit PCM). */
function float32ToWavBlob(samples: Float32Array, sampleRate: number): Blob {
  const numSamples = samples.length;
  const dataLen = numSamples * 2;
  const buf = new ArrayBuffer(44 + dataLen);
  const view = new DataView(buf);
  const writeStr = (offset: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i));
  };
  writeStr(0, 'RIFF');
  view.setUint32(4, 36 + dataLen, true);
  writeStr(8, 'WAVE');
  writeStr(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, 'data');
  view.setUint32(40, dataLen, true);
  for (let i = 0; i < numSamples; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([buf], { type: 'audio/wav' });
}

interface Props {
  onExit: () => void;
}

interface TranscriptItem extends AnalysisData {
    id: string;
    timestamp: number;
    source?: 'STT' | 'Gemini'; // Shown in debug mode
    audioSegmentBase64?: string;
    speakerLabel?: string; // Raw speaker ID from STT (shown in debug)
    speakerColor?: string;
    uiContext?: Record<string, unknown> | null;
    splitFrom?: string | null;
    provisional?: boolean;
    segmentId?: number; // monotonic; match speaker_resolved by this
    start_ms?: number;
    end_ms?: number;
    analysisAttached?: boolean; // true when Gemini sentiment/horseman merged into this row
    analysisSource?: 'backend' | 'live'; // when set to 'backend', do not overwrite with Live reportAnalysis
    /** When set, debug popup opened from this row shows only the response with this _ts. */
    analysisResponseTs?: number;
    /** When set (backend analyze-turn with debug=true), shown in Gemini debug popup as LLM prompt. */
    analysisPrompt?: string;
    bestScorePct?: number;
    secondScorePct?: number;
    scoreMarginPct?: number;
    bestUserSuffix?: string;
    secondUserSuffix?: string;
    /** All cluster similarity scores (known users + Unknown_N), sorted by score descending. */
    allScores?: { label: string; score_pct: number }[];
    sttV2LabelConf?: number;
    sttV2Coverage?: number;
    sttV2Flags?: Record<string, boolean>;
    sttV2Debug?: SttV2DebugInfo;
    /** NeMo debug: who assigned speaker (google, nemo, voice_id, none) */
    speakerSource?: 'google' | 'nemo' | 'voice_id' | 'none';
    /** NeMo debug: diarization speaker id when speaker_source === 'nemo' */
    nemoSpeakerId?: string | null;
    speakerLabelBefore?: string | null;
    speakerLabelAfter?: string | null;
    speakerChangeAtMs?: number | null;
    speakerChangeWordIndex?: number | null;
    mergedSegmentIds?: number[];
}

/** Pick the unattached transcript row that should receive the next Gemini analysis. Prefer oldest (FIFO): min segmentId / min start_ms / min timestamp so the first bubble gets the first analysis. */
function pickMergeTarget(prev: TranscriptItem[]): TranscriptItem | null {
  const unattached = prev.filter((r) => !r.analysisAttached);
  if (unattached.length === 0) return null;

  const withSegmentId = unattached.filter((r) => r.segmentId != null);
  if (withSegmentId.length > 0) {
    return withSegmentId.reduce((a, b) => ((a.segmentId ?? 0) <= (b.segmentId ?? 0) ? a : b));
  }

  const withStartMs = unattached.filter((r) => r.start_ms != null);
  if (withStartMs.length > 0) {
    return withStartMs.reduce((a, b) => ((a.start_ms ?? 0) <= (b.start_ms ?? 0) ? a : b));
  }

  const withEndMs = unattached.filter((r) => r.end_ms != null);
  if (withEndMs.length > 0) {
    return withEndMs.reduce((a, b) => ((a.end_ms ?? 0) <= (b.end_ms ?? 0) ? a : b));
  }

  const withTimestamp = unattached.filter((r) => r.timestamp != null);
  if (withTimestamp.length > 0) {
    return withTimestamp.reduce((a, b) => ((a.timestamp ?? 0) <= (b.timestamp ?? 0) ? a : b));
  }
  return unattached[0];
}

export const LiveCoachScreen: React.FC<Props> = ({ onExit }) => {
  const { me: user } = useSessionStore();
  const { relationships } = useRelationshipsStore();
  const addNotificationFromEvent = useRealtimeStore((s) => s.addNotificationFromEvent);
  const useSttV2 = String(import.meta.env.VITE_USE_STT_V2 || '').toLowerCase() === 'true';
  
  if (!user) {
    return null; // Should not happen, but guard against it
  }
  // Match inside/LiveCoachMode: ensure partner name for coach (first loved one or partnerName)
  const partnerName = user.partnerName ?? (relationships?.length ? relationships[0].name : undefined) ?? (user.lovedOnes?.length ? user.lovedOnes[0].name : undefined) ?? 'Partner';
  const userForCoach = { ...user, partnerName };
  const [isActive, setIsActive] = useState(false);
  const [status, setStatus] = useState<'disconnected' | 'connecting' | 'active'>('disconnected');
  const [statusDetail, setStatusDetail] = useState<string>(''); // e.g. "Mic...", "Session...", "Ready" — shows where we are / what failed
  const [nudge, setNudge] = useState<string | null>(null);
  const [escalationPrompt, setEscalationPrompt] = useState<string | null>(null);
  
  // Analysis State
  const [transcripts, setTranscripts] = useState<TranscriptItem[]>([]);
  const visibleTranscripts = transcripts.filter(
    (t) => (t.transcript ?? '').trim().length > 0
  );
  const [interimTranscript, setInterimTranscript] = useState<TranscriptItem | null>(null);
  const [activeHorseman, setActiveHorseman] = useState<string | null>(null);
  const [currentSentiment, setCurrentSentiment] = useState<string>('Neutral');
  /** Sticky coaching annotation: only updated when horseman/sentiment is non-neutral, never cleared by later analysis; cleared only on stop. */
  const [coachingSticky, setCoachingSticky] = useState<{ horseman: string | null; sentiment: string }>({ horseman: null, sentiment: 'Neutral' });

  // Audio Refs
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const outputAudioContextRef = useRef<AudioContext | null>(null);
  
  const liveSessionRef = useRef<{ sendAudio: (d: Float32Array) => void; sendInitMarker: () => void; disconnect: () => void } | null>(null);
  const sttSessionRef = useRef<SttSession | null>(null);
  const sttAvailableRef = useRef<boolean>(true);
  const sttConnectingRef = useRef<boolean>(false);
  const lastSttSpeakerRef = useRef<string | null>(null);
  const lastKnownSpeakerRef = useRef<string | null>(null);
  const lastGeminiSpeakerRef = useRef<string | null>(null);
  const lastEscalationNudgeAtRef = useRef<number>(0);
  const debugFinalCountRef = useRef<number>(0);
  /** When Gemini analysis arrives before a transcript row exists, buffer and attach to next new row. */
  const pendingAnalysesRef = useRef<Array<{ sentiment: AnalysisData['sentiment']; horseman: AnalysisData['horseman']; level?: number; nudgeText?: string; suggestedRephrasing?: string }>>([]);

  const nextStartTimeRef = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  /** Mic waveform: 30 band levels (0–1) from last chunk, updated in onaudioprocess. */
  const waveformBandsRef = useRef<Float32Array>(new Float32Array(30));
  const [waveformHeights, setWaveformHeights] = useState<number[]>(() => Array(30).fill(4));
  const connectionTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const drainTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** Time of last stopSession (Cut); ignore Init clicks within this cooldown to avoid same-spot accidental re-init. */
  const lastStopSessionAtRef = useRef<number>(0);
  /** Init button disabled until this time (ms); prevents spurious click right after Cut/drain. */
  const [initCooldownEndAt, setInitCooldownEndAt] = useState(0);
  /** Gemini Live session resumption handle; store from onResumptionHandle, pass on reconnect. */
  const resumptionHandleRef = useRef<string | null>(null);
  /** Ring buffer of last RING_SECONDS of mic audio (16kHz Float32) for voice matching on Gemini-sourced rows. */
  const audioRingRef = useRef<{ buffer: Float32Array; writeIndex: number; totalWritten: number } | null>(null);
  const [playingAudioId, setPlayingAudioId] = useState<string | null>(null);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  /** Debug log lines shown when debug mode is on (after Init). */
  const [debugLogs, setDebugLogs] = useState<{ ts: number; msg: string }[]>([]);
  const addDebugLog = useCallback((msg: string) => {
    setDebugLogs((prev) => [...prev.slice(-99), { ts: Date.now(), msg }]);
  }, []);
  const showDebug = user?.preferences?.showDebug ?? (typeof localStorage !== 'undefined' ? localStorage.getItem('inside_show_debug') !== 'false' : true);
  const debugQueryOverride = typeof window !== 'undefined'
    && new URLSearchParams(window.location.search).get('debug') === '1';
  const debugLocalOverride = typeof localStorage !== 'undefined'
    && localStorage.getItem('inside_force_debug') === 'true';
  const debugEnabled = showDebug || debugQueryOverride || debugLocalOverride || import.meta.env.DEV;
  const liveCoachKnownSpeakersOnly = user.preferences?.liveCoachKnownSpeakersOnly ?? false;
  const [showDebugPanel, setShowDebugPanel] = useState(false);
  /** When debugEnabled: Gemini system prompt and reportAnalysis responses for the debug popup. */
  const [geminiSystemPrompt, setGeminiSystemPrompt] = useState<string | null>(null);
  const [geminiResponses, setGeminiResponses] = useState<Array<Record<string, unknown>>>([]);
  const [showGeminiDebugPopup, setShowGeminiDebugPopup] = useState(false);
  /** When set, debug popup shows only the response for this transcript row (from row's Gemini button). */
  const [geminiDebugForRow, setGeminiDebugForRow] = useState<TranscriptItem | null>(null);
  /** When debugEnabled: row id whose STT voice ID debug popup is open (null = closed). */
  const [sttDebugRowId, setSttDebugRowId] = useState<string | null>(null);
  /** Snapshot of NeMo segments at time of opening STT debug popup. */
  const [sttDebugNemoSegments, setSttDebugNemoSegments] = useState<Array<{ start_s: number; end_s: number; speaker_id: string }>>([]);
  /** Latest NeMo diarization segments (for STT debug popup). */
  const [nemoDiarSegments, setNemoDiarSegments] = useState<Array<{ start_s: number; end_s: number; speaker_id: string }>>([]);
  /** When true (STT v2 only), skip diarization and use sentence boundary + embedding matching only. Persisted in localStorage. Default true. */
  const [skipDiarization, setSkipDiarization] = useState(
    () => typeof localStorage === 'undefined' || localStorage.getItem('inside_skip_diarization') !== 'false'
  );
  /** Segment IDs for which voice feedback was already sent; hide Me/Not me after send. */
  const [feedbackSentForSegmentIds, setFeedbackSentForSegmentIds] = useState<number[]>([]);
  /** Segment ID showing brief "Thanks, we'll use this to improve voice ID" (cleared after 3s). */
  const [confirmationForSegmentId, setConfirmationForSegmentId] = useState<number | null>(null);
  /** Error to show under a segment's feedback row (code-derived message). */
  const [feedbackError, setFeedbackError] = useState<{ segmentId: number; message: string } | null>(null);
  /** Segment ID currently submitting feedback (disable buttons during request). */
  const [feedbackPendingSegmentId, setFeedbackPendingSegmentId] = useState<number | null>(null);
  /** Segment IDs for which the "Me / Not me" feedback row is expanded. */
  const [feedbackExpandedSegmentIds, setFeedbackExpandedSegmentIds] = useState<number[]>([]);
  /** Analysis latency log for debug: last N entries from live_audio, backend_text, backend_text_with_history. */
  const [analysisLatencyLog, setAnalysisLatencyLog] = useState<Array<{
    source: 'live_audio' | 'backend_text' | 'backend_text_with_history';
    segment_id?: number;
    latency_ms?: number;
    backend_latency_ms?: number;
    t_received: number;
  }>>([]);
  /** Time of last STT final (for live_audio lag proxy). */
  const lastSttFinalAtRef = useRef<number>(0);
  const MERGE_CONTIGUOUS_MS = 2000;
  /** Latest transcripts (avoids stale closure in callbacks). */
  const transcriptsRef = useRef<TranscriptItem[]>([]);
  /** Buffer speaker_resolved until transcript row exists. */
  const pendingSpeakerResolvedRef = useRef<Map<number, SttSpeakerResolvedEvent>>(new Map());
  const interimTranscriptRef = useRef<TranscriptItem | null>(null);
  /** Profiling mode: record live_audio latency per segment. Ref kept in sync for callbacks. */
  const [profilingMode, setProfilingMode] = useState(false);
  const profilingModeRef = useRef(profilingMode);
  useEffect(() => {
    profilingModeRef.current = profilingMode;
  }, [profilingMode]);
  /** Profile entry per segment (same turn): t0 + live_audio latency. */
  type ProfileEntry = {
    segment_id: number;
    t0: number;
    latency_live_audio?: number;
  };
  const [profileEntries, setProfileEntries] = useState<ProfileEntry[]>([]);
  /** Pending segments for Live: FIFO so next reportAnalysis is assigned to oldest segment. */
  const pendingProfileSegmentsRef = useRef<Array<{ segment_id: number; t0: number }>>([]);

  const toggleFeedbackExpanded = useCallback((segmentId: number) => {
    setFeedbackExpandedSegmentIds((prev) =>
      prev.includes(segmentId) ? prev.filter((id) => id !== segmentId) : [...prev, segmentId]
    );
  }, []);

  const openSttDebug = useCallback((row: TranscriptItem) => {
    if (row.start_ms != null && row.end_ms != null) {
      const startMs = row.start_ms;
      const endMs = row.end_ms;
      const overlap = nemoDiarSegments.filter((seg) => {
        const segStartMs = seg.start_s * 1000;
        const segEndMs = seg.end_s * 1000;
        return segStartMs <= endMs && segEndMs >= startMs;
      });
      setSttDebugNemoSegments(overlap);
    } else {
      setSttDebugNemoSegments([]);
    }
    setSttDebugRowId(row.id);
  }, [debugEnabled, nemoDiarSegments]);

  const openGeminiDebug = useCallback((row: TranscriptItem | null) => {
    setGeminiDebugForRow(row);
    setShowGeminiDebugPopup(true);
  }, [debugEnabled]);

  const resolveKnownSpeakerName = useCallback(
    (label?: string | null) => {
      if (!label) return null;
      if (label === user.id || label === user.name) return user.name;
      const lovedOneMatch = (user.lovedOnes ?? []).find(
        (lovedOne) => lovedOne.id === label || lovedOne.name === label
      );
      return lovedOneMatch?.name ?? null;
    },
    [user.id, user.name, user.lovedOnes]
  );

  const resolveKnownSpeakerBySuffix = useCallback(
    (suffix?: string | null) => {
      if (!suffix) return null;
      if (user.id.endsWith(suffix)) return user.name;
      const lovedOneMatch = (user.lovedOnes ?? []).find((l) =>
        l.id.endsWith(suffix)
      );
      return lovedOneMatch?.name ?? null;
    },
    [user.id, user.name, user.lovedOnes]
  );

  const resolveSpeakerDisplay = useCallback(
    (
      label?: string | null,
      options?: { bestUserSuffix?: string | null; scorePct?: number; fallback?: string }
    ) => {
      const known = resolveKnownSpeakerName(label);
      if (known) {
        lastKnownSpeakerRef.current = known;
        return known;
      }
      const isUnknownLabel = /^Unknown(_\d+)?$/i.test(String(label ?? ''));
      const allowBySuffix = Boolean(options?.bestUserSuffix)
        && (liveCoachKnownSpeakersOnly
          || (isUnknownLabel && (options?.scorePct ?? 0) >= SPEAKER_RESOLVE_MIN_SCORE_PCT));
      if (allowBySuffix) {
        const bySuffix = resolveKnownSpeakerBySuffix(options?.bestUserSuffix);
        if (bySuffix) {
          lastKnownSpeakerRef.current = bySuffix;
          return bySuffix;
        }
      }
      if (liveCoachKnownSpeakersOnly) {
        return lastKnownSpeakerRef.current ?? user.name;
      }
      return label ?? options?.fallback ?? 'Unknown';
    },
    [
      resolveKnownSpeakerName,
      resolveKnownSpeakerBySuffix,
      liveCoachKnownSpeakersOnly,
      user.name,
    ]
  );

  const applySpeakerResolvedToRows = useCallback(
    (rows: TranscriptItem[], event: SttSpeakerResolvedEvent, displaySpeaker: string) =>
      rows.map((row) =>
        row.segmentId === event.segment_id
          ? {
              ...row,
              transcript: event.text ?? row.transcript,
              speaker: displaySpeaker,
              speakerLabel: event.speaker_label,
              speakerColor: event.speaker_color ?? row.speakerColor,
              uiContext: event.ui_context ?? row.uiContext,
              splitFrom: event.split_from ?? row.splitFrom,
              provisional: event.flags?.provisional === false ? false : row.provisional,
              start_ms: event.start_ms ?? row.start_ms,
              end_ms: event.end_ms ?? row.end_ms,
              bestScorePct: event.best_score_pct,
              secondScorePct: event.second_score_pct,
              scoreMarginPct: event.score_margin_pct,
              bestUserSuffix: event.best_user_suffix,
              secondUserSuffix: event.second_user_suffix,
              allScores: event.all_scores ?? row.allScores,
              sttV2LabelConf: event.label_conf ?? row.sttV2LabelConf,
              sttV2Coverage: event.coverage ?? row.sttV2Coverage,
              sttV2Flags: event.flags ?? row.sttV2Flags,
              sttV2Debug: event.debug ?? row.sttV2Debug,
              sentiment: event.sentiment ?? row.sentiment,
              horseman: event.horseman ?? row.horseman,
              level: event.level ?? row.level,
              nudgeText: event.nudgeText ?? row.nudgeText,
              suggestedRephrasing: event.suggestedRephrasing ?? row.suggestedRephrasing,
              analysisAttached:
                event.sentiment != null || event.horseman != null || event.level != null
                  ? true
                  : row.analysisAttached,
              analysisSource: event.analysisSource ?? row.analysisSource,
              analysisPrompt: event.analysisPrompt ?? row.analysisPrompt,
              speakerSource: event.speaker_source ?? row.speakerSource,
              nemoSpeakerId: event.nemo_speaker_id ?? row.nemoSpeakerId,
              speakerLabelBefore: event.speaker_label_before ?? row.speakerLabelBefore,
              speakerLabelAfter: event.speaker_label_after ?? row.speakerLabelAfter,
              speakerChangeAtMs: event.speaker_change_at_ms ?? row.speakerChangeAtMs,
              speakerChangeWordIndex: event.speaker_change_word_index ?? row.speakerChangeWordIndex,
            }
          : row
      ),
    []
  );

  const handleVoiceFeedback = useCallback(
    async (segmentId: number, isMe: boolean, audioSegmentBase64?: string | null) => {
      if (feedbackPendingSegmentId != null) return;
      setFeedbackError((prev) => (prev?.segmentId === segmentId ? null : prev));
      setFeedbackPendingSegmentId(segmentId);
      const result = await apiService.submitVoiceFeedback(segmentId, isMe, audioSegmentBase64 ?? undefined);
      setFeedbackPendingSegmentId(null);
      if (!result.success) {
        const code = 'code' in result ? result.code : undefined;
        const errorMessage = 'message' in result ? result.message : undefined;
        const message =
          code === 'VOICE_ENROLLMENT_REQUIRED'
            ? 'Complete voice enrollment first so we can learn your voice.'
            : code === 'AUDIO_TOO_SHORT' || code === 'AUDIO_INVALID'
              ? errorMessage || 'That clip was too short or invalid.'
              : errorMessage || 'Something went wrong.';
        setFeedbackError({ segmentId, message });
        return;
      }
      setFeedbackSentForSegmentIds((prev) => (prev.includes(segmentId) ? prev : [...prev, segmentId]));
      setConfirmationForSegmentId(segmentId);
      window.setTimeout(() => setConfirmationForSegmentId((id) => (id === segmentId ? null : id)), 3000);
    },
    [feedbackPendingSegmentId]
  );

  const playAudioSegment = useCallback((audioBase64: string, transcriptId: string, rowSegmentId?: number, textPreview?: string) => {
    if (audioElementRef.current) {
      audioElementRef.current.pause();
      audioElementRef.current = null;
    }
    if (playingAudioId === transcriptId) {
      setPlayingAudioId(null);
      return;
    }
    try {
      const audio = new Audio(`data:audio/wav;base64,${audioBase64}`);
      audioElementRef.current = audio;
      setPlayingAudioId(transcriptId);
      audio.onended = () => {
        setPlayingAudioId(null);
        audioElementRef.current = null;
      };
      audio.onerror = () => {
        setPlayingAudioId(null);
        audioElementRef.current = null;
      };
      audio.play().catch(() => {
        setPlayingAudioId(null);
        audioElementRef.current = null;
      });
    } catch (err) {
      setPlayingAudioId(null);
    }
  }, [playingAudioId]);

  useEffect(() => {
    transcriptsRef.current = transcripts;
  }, [transcripts]);

  useEffect(() => {
    if (pendingSpeakerResolvedRef.current.size === 0) return;
    const pendingEntries = Array.from(pendingSpeakerResolvedRef.current.entries());
    const hasMatch = pendingEntries.some(([segmentId]) =>
      transcripts.some((row) => row.segmentId === segmentId)
    );
    if (!hasMatch) return;
    setTranscripts((prev) => {
      let next = prev;
      for (const [segmentId, pendingResolved] of pendingEntries) {
        if (!next.some((row) => row.segmentId === segmentId)) continue;
        const displaySpeaker = resolveSpeakerDisplay(pendingResolved.speaker_label, {
          bestUserSuffix: pendingResolved.best_user_suffix,
          scorePct: pendingResolved.best_score_pct,
        });
        next = applySpeakerResolvedToRows(next, pendingResolved, displaySpeaker);
        pendingSpeakerResolvedRef.current.delete(segmentId);
      }
      return next;
    });
  }, [transcripts, resolveSpeakerDisplay, applySpeakerResolvedToRows]);

  useEffect(() => {
    interimTranscriptRef.current = interimTranscript;
  }, [interimTranscript]);

  const clearConnectionTimeout = () => {
    if (connectionTimeoutRef.current) {
      clearTimeout(connectionTimeoutRef.current);
      connectionTimeoutRef.current = null;
    }
  };
  const clearDrainTimeout = () => {
    if (drainTimeoutRef.current) {
      clearTimeout(drainTimeoutRef.current);
      drainTimeoutRef.current = null;
    }
  };

  /** Fire backend analyze-turn asynchronously; on response merge into row by segment_id and set analysisSource = 'backend'. */
  const fireBackendAnalyzeTurn = useCallback((segmentId: number, transcript: string, speaker?: string | null) => {
    const tSent = Date.now();
    const prevTranscripts = transcriptsRef.current;
    const history = prevTranscripts.slice(-10).map((t) => ({
      speaker: t.speaker ?? 'Unknown',
      transcript: (t.transcript ?? '').trim(),
    })).filter((t) => t.transcript.length > 0);
    apiService
      .analyzeTurn({
        transcript: transcript.trim(),
        segment_id: segmentId,
        include_history: history.length > 0,
        history: history.length > 0 ? history : undefined,
        speaker: speaker ?? null,
        debug: showDebug,
      })
      .then((res) => {
        const tReceived = Date.now();
        const latencyMs = tReceived - tSent;
        const backendMs = res.data?.latency_ms;
        const source = history.length > 0 ? ('backend_text_with_history' as const) : ('backend_text' as const);
        setAnalysisLatencyLog((prev) => [
          ...prev.slice(-(ANALYSIS_LATENCY_LOG_MAX - 1)),
          { source, segment_id: segmentId, latency_ms: latencyMs, backend_latency_ms: backendMs, t_received: tReceived },
        ]);
        const existing = transcriptsRef.current.find((r) => r.segmentId === segmentId);
        const displaySpeaker = existing?.speaker ?? speaker ?? 'Unknown';
        const sentiment = (res.data?.sentiment ?? 'Neutral') as AnalysisData['sentiment'];
        const horseman = (res.data?.horseman ?? 'None') as AnalysisData['horseman'];
        const analysisPatch: SttSpeakerResolvedEvent = {
          type: 'stt.speaker_resolved',
          segment_id: segmentId,
          speaker_label: existing?.speakerLabel ?? speaker ?? '',
          sentiment,
          horseman,
          level: res.data?.level,
          nudgeText: res.data?.nudgeText,
          suggestedRephrasing: res.data?.suggestedRephrasing,
          analysisSource: 'backend',
          analysisPrompt: res.data?.debug_prompt ?? undefined,
        };
        setTranscripts((prev) => applySpeakerResolvedToRows(prev, analysisPatch, displaySpeaker));
        setCurrentSentiment(sentiment);
        if (horseman !== 'None') {
          setActiveHorseman(horseman);
          setNudge(`${horseman} Detected`);
          setCoachingSticky((p) => ({ ...p, horseman }));
        }
        if (sentiment !== 'Neutral') {
          setCoachingSticky((p) => ({ ...p, sentiment }));
        }
      })
      .catch((err) => {
        console.warn('[LiveCoach] Backend analyze-turn failed:', err);
      });
  }, [showDebug]);

  const maybeSendEscalationNudge = async (event: SttEscalationEvent) => {
    const lastSpeaker = lastSttSpeakerRef.current;
    if (!lastSpeaker || !isSpeakerUser(lastSpeaker)) return;

    const hapticsEnabled = user.preferences?.hapticFeedback ?? true;
    const notificationsEnabled = user.preferences?.notifications ?? true;
    const now = Date.now();
    if (now - lastEscalationNudgeAtRef.current < 10000) return;

    lastEscalationNudgeAtRef.current = now;
    if (hapticsEnabled) {
      const delivered = await sendWatchNudge({
        reason: event.reason || 'escalation',
        severity: event.severity || 'medium',
        speaker: lastSpeaker,
      });
      if (!delivered && notificationsEnabled) {
        addNotificationFromEvent('alert', 'Escalation Detected', event.message);
      }
      return;
    }

    if (notificationsEnabled) {
      addNotificationFromEvent('alert', 'Escalation Detected', event.message);
    }
  };

  const connectBackendStt = async (sttOptions: SttSessionOptions) => {
    if (sttSessionRef.current || sttConnectingRef.current) return null;
    sttConnectingRef.current = true;
    try {
      addDebugLog('Connecting to STT…');
      const result = await connectSttSession({ ...sttOptions, useV2: useSttV2, debug: useSttV2 ? showDebug : undefined }, {
        onTranscript: (event: SttTranscriptEvent) => {
          const segmentId = event.segment_id;
          const hasProvisionalRow = segmentId != null
            ? (transcriptsRef.current ?? []).some((r) => r.segmentId === segmentId && r.provisional)
            : false;
          const pendingResolved = segmentId != null
            ? pendingSpeakerResolvedRef.current.get(segmentId)
            : null;
          const pendingDisplaySpeaker = pendingResolved
            ? resolveSpeakerDisplay(pendingResolved.speaker_label, {
                bestUserSuffix: pendingResolved.best_user_suffix,
                scorePct: pendingResolved.best_score_pct,
              })
            : null;
          if (event.flags?.provisional) {
            if (pendingResolved && segmentId != null) {
              pendingSpeakerResolvedRef.current.delete(segmentId);
              lastSttSpeakerRef.current = pendingDisplaySpeaker ?? lastSttSpeakerRef.current;
            }
          } else if (event.speaker_label?.startsWith?.('spk_embed_')) {
          }
          let displaySpeaker = resolveSpeakerDisplay(event.speaker_label, {
            bestUserSuffix: event.best_user_suffix,
            scorePct: event.best_score_pct,
          });
          lastSttSpeakerRef.current = displaySpeaker;
          const text = typeof event.text === 'string' ? event.text : '';
          const trimmedText = text.trim();
          const classifyChar = (value: string | undefined) => {
            if (!value) return 'none';
            if (/\s/.test(value)) return 'space';
            if (/[a-zA-Z]/.test(value)) return 'alpha';
            if (/[0-9]/.test(value)) return 'digit';
            if (/[.,!?;:]/.test(value)) return 'punct';
            return 'other';
          };
          const labelKind = (() => {
            if (!event.speaker_label) return 'empty';
            if (event.speaker_label === user.id) return 'user';
            if ((user.lovedOnes ?? []).some((lovedOne) => lovedOne.id === event.speaker_label)) return 'loved_one';
            if (/^Unknown(_\d+)?$/i.test(String(event.speaker_label))) return 'unknown';
            if (/overlap|uncertain/i.test(String(event.speaker_label))) return 'special';
            return 'other';
          })();
          const firstCharType = classifyChar(text[0]);
          const lastCharType = classifyChar(text[text.length - 1]);
          const prevRows = transcriptsRef.current ?? [];
          const prevLast = prevRows.length > 0 ? prevRows[prevRows.length - 1] : undefined;
          const prevLastText = typeof prevLast?.transcript === 'string' ? prevLast?.transcript : '';
          const prevLastCharType = classifyChar(prevLastText[prevLastText.length - 1]);
          const prevHasSameSegment = event.segment_id != null ? prevRows.some((r) => r.segmentId === event.segment_id) : false;
          const isProvisional = Boolean(event.flags?.provisional);
          if (isProvisional) {
            const segmentId = event.segment_id;
            setTranscripts((prev) => {
              const existingIdx = segmentId != null
                ? prev.findIndex((r) => r.segmentId === segmentId)
                : -1;
              const resolvedLabel = pendingResolved?.speaker_label ?? event.speaker_label;
              const resolvedDisplay = pendingDisplaySpeaker ?? displaySpeaker;
              const resolvedFlags = pendingResolved?.flags ?? event.flags;
              const nextRow = {
                transcript: event.text,
                speaker: resolvedDisplay,
                sentiment: 'Neutral' as const,
                horseman: 'None' as const,
                level: undefined,
                nudgeText: undefined,
                suggestedRephrasing: undefined,
                id: `seg-${segmentId ?? Date.now()}`,
                timestamp: Date.now(),
                source: 'STT' as const,
                audioSegmentBase64: event.audio_segment_base64,
                speakerLabel: resolvedLabel,
                speakerColor: pendingResolved?.speaker_color ?? event.speaker_color ?? undefined,
                uiContext: pendingResolved?.ui_context ?? event.ui_context ?? undefined,
                splitFrom: pendingResolved?.split_from ?? event.split_from ?? undefined,
                provisional: resolvedFlags?.provisional === false ? false : true,
                segmentId: event.segment_id,
                start_ms: event.start_ms,
                end_ms: event.end_ms,
                analysisAttached: false,
                bestScorePct: pendingResolved?.best_score_pct,
                secondScorePct: pendingResolved?.second_score_pct,
                scoreMarginPct: pendingResolved?.score_margin_pct,
                bestUserSuffix: pendingResolved?.best_user_suffix,
                secondUserSuffix: pendingResolved?.second_user_suffix,
                allScores: pendingResolved?.all_scores,
                sttV2LabelConf: pendingResolved?.label_conf ?? event.label_conf,
                sttV2Coverage: pendingResolved?.coverage ?? event.coverage,
                sttV2Flags: resolvedFlags,
                sttV2Debug: pendingResolved?.debug ?? event.debug,
                speakerSource: pendingResolved?.speaker_source ?? event.speaker_source,
                nemoSpeakerId: pendingResolved?.nemo_speaker_id ?? event.nemo_speaker_id ?? undefined,
                speakerLabelBefore: pendingResolved?.speaker_label_before ?? event.speaker_label_before ?? undefined,
                speakerLabelAfter: pendingResolved?.speaker_label_after ?? event.speaker_label_after ?? undefined,
                speakerChangeAtMs: pendingResolved?.speaker_change_at_ms ?? event.speaker_change_at_ms ?? undefined,
                speakerChangeWordIndex: pendingResolved?.speaker_change_word_index ?? event.speaker_change_word_index ?? undefined,
              };
              if (existingIdx >= 0) {
                const next = [...prev];
                next[existingIdx] = { ...next[existingIdx], ...nextRow };
                return next;
              }
              return [...prev, nextRow];
            });
            return;
          }
          if (event.is_final !== true) {
            const newInterim = {
              transcript: event.text,
              speaker: displaySpeaker,
              sentiment: 'Neutral' as const,
              horseman: 'None' as const,
              id: 'interim',
              timestamp: Date.now(),
            };
            setInterimTranscript(newInterim);
            return;
          }
          setInterimTranscript(null);
          lastSttFinalAtRef.current = Date.now();
          const pending = pendingAnalysesRef.current;
          const attached = pending.length > 0 ? pending.shift()! : null;
          const bestNum = event.best_score_pct != null && !Number.isNaN(Number(event.best_score_pct)) ? Number(event.best_score_pct) : undefined;
          const secondNum = event.second_score_pct != null && !Number.isNaN(Number(event.second_score_pct)) ? Number(event.second_score_pct) : undefined;
          addDebugLog(bestNum != null ? `STT final: Best ${bestNum}%${secondNum != null ? ` 2nd ${secondNum}%` : ''}` : 'STT final: no voice score');
          const id = `seg-${segmentId}`;
          let didMerge = false;
          setTranscripts((prev) => {
            const last = prev.length > 0 ? prev[prev.length - 1] : undefined;
            const lastText = typeof last?.transcript === 'string' ? last.transcript : '';
            const prevEndsSentence = /[.!?…。！？]$/.test(lastText.trim());
            const newStartsWithSpace = /^\s/.test(text);
            const lastSpeakerKey = last?.nemoSpeakerId || last?.speakerLabel || last?.speaker || '';
            const nextSpeakerKey = event.nemo_speaker_id || event.speaker_label || displaySpeaker || '';
            const sameSpeaker = Boolean(lastSpeakerKey && nextSpeakerKey && lastSpeakerKey === nextSpeakerKey);
            const contiguousMs = last?.end_ms != null && event.start_ms != null
              ? Math.abs((event.start_ms ?? 0) - (last.end_ms ?? 0))
              : null;
            const isContiguous = contiguousMs != null ? contiguousMs <= MERGE_CONTIGUOUS_MS : false;
            const isSequentialSegment = last?.segmentId != null && event.segment_id != null
              ? event.segment_id === last.segmentId + 1
              : false;
            const startsLowercase = /^[a-z]/.test(text.trimStart());
            const allowSentenceMerge = prevEndsSentence && startsLowercase;
            const hasSplitFrom = Boolean(event.split_from);
            const shouldMergeFinal = Boolean(
              event.is_final === true
              && text.trim().length > 0
              && last
              && last.source === 'STT'
              && sameSpeaker
              && (isContiguous || isSequentialSegment)
              && (!prevEndsSentence || allowSentenceMerge)
              && !hasSplitFrom
            );
            const hasProvisional = segmentId != null
              ? prev.some((r) => r.segmentId === segmentId && r.provisional)
              : false;
            if (event.is_final === true && text.trim().length === 0) {
              return prev;
            }
            if (shouldMergeFinal && prev.length > 0) {
              const endsWithSpace = /\s$/.test(lastText);
              const startsWithSpace = /^\s/.test(text);
              const lastIsWordChar = /[A-Za-z0-9]$/.test(lastText);
              const nextIsWordChar = /^[A-Za-z0-9]/.test(text);
              const needsSpace = !endsWithSpace && !startsWithSpace && !(lastIsWordChar && nextIsWordChar);
              const mergedText = `${lastText}${needsSpace ? ' ' : ''}${text}`;
              const mergedSegmentIds = Array.isArray(last.mergedSegmentIds) ? [...last.mergedSegmentIds] : [];
              if (segmentId != null && !mergedSegmentIds.includes(segmentId)) {
                mergedSegmentIds.push(segmentId);
              }
              const next = [...prev];
              next[next.length - 1] = {
                ...last,
                transcript: mergedText,
                end_ms: event.end_ms ?? last.end_ms,
                mergedSegmentIds,
                audioSegmentBase64: last.audioSegmentBase64 ?? event.audio_segment_base64,
                speakerColor: event.speaker_color ?? last.speakerColor,
                uiContext: event.ui_context ?? last.uiContext,
                splitFrom: event.split_from ?? last.splitFrom,
                provisional: false,
                sttV2LabelConf: event.label_conf ?? last.sttV2LabelConf,
                sttV2Coverage: event.coverage ?? last.sttV2Coverage,
                sttV2Flags: event.flags ?? last.sttV2Flags,
                sttV2Debug: event.debug ?? last.sttV2Debug,
                timestamp: Date.now(),
              };
              didMerge = true;
              return next;
            }
            const pendingResolved = segmentId != null ? pendingSpeakerResolvedRef.current.get(segmentId) : null;
            let pendingDisplaySpeaker = displaySpeaker;
            if (pendingResolved) {
              pendingDisplaySpeaker = resolveSpeakerDisplay(
                pendingResolved.speaker_label,
                {
                  bestUserSuffix: pendingResolved.best_user_suffix,
                  scorePct: pendingResolved.best_score_pct,
                }
              );
            }
            return [
              ...prev,
              {
                transcript: event.text,
                speaker: displaySpeaker,
                sentiment: attached?.sentiment ?? 'Neutral',
                horseman: attached?.horseman ?? 'None',
                level: attached?.level,
                nudgeText: attached?.nudgeText,
                suggestedRephrasing: attached?.suggestedRephrasing,
                id: `seg-${segmentId}`,
                timestamp: Date.now(),
                source: 'STT' as const,
                audioSegmentBase64: event.audio_segment_base64,
                speakerLabel: event.speaker_label,
                speakerColor: event.speaker_color ?? undefined,
                uiContext: event.ui_context ?? undefined,
                splitFrom: event.split_from ?? undefined,
                provisional: false,
                segmentId: event.segment_id,
                start_ms: event.start_ms,
                end_ms: event.end_ms,
                analysisAttached: !!attached,
                bestScorePct: bestNum,
                secondScorePct: secondNum,
                scoreMarginPct: event.score_margin_pct != null && !Number.isNaN(Number(event.score_margin_pct)) ? Number(event.score_margin_pct) : undefined,
                bestUserSuffix: event.best_user_suffix ?? undefined,
                secondUserSuffix: event.second_user_suffix ?? undefined,
                sttV2LabelConf: event.label_conf,
                sttV2Coverage: event.coverage,
                sttV2Flags: event.flags,
                sttV2Debug: event.debug,
                speakerSource: event.speaker_source,
                nemoSpeakerId: event.nemo_speaker_id ?? undefined,
                speakerLabelBefore: event.speaker_label_before ?? undefined,
                speakerLabelAfter: event.speaker_label_after ?? undefined,
                speakerChangeAtMs: event.speaker_change_at_ms ?? undefined,
                speakerChangeWordIndex: event.speaker_change_word_index ?? undefined,
              },
            ].map((row, index, arr) => {
              if (index !== arr.length - 1) return row;
              if (pendingResolved && segmentId != null) {
                pendingSpeakerResolvedRef.current.delete(segmentId);
                return {
                  ...row,
                  speaker: pendingDisplaySpeaker,
                  speakerLabel: pendingResolved.speaker_label,
                  speakerColor: pendingResolved.speaker_color ?? row.speakerColor,
                  uiContext: pendingResolved.ui_context ?? row.uiContext,
                  splitFrom: pendingResolved.split_from ?? row.splitFrom,
                  provisional: pendingResolved.flags?.provisional === false ? false : row.provisional,
                  bestScorePct: pendingResolved.best_score_pct,
                  secondScorePct: pendingResolved.second_score_pct,
                  scoreMarginPct: pendingResolved.score_margin_pct,
                  bestUserSuffix: pendingResolved.best_user_suffix,
                  secondUserSuffix: pendingResolved.second_user_suffix,
                  allScores: pendingResolved.all_scores ?? row.allScores,
                  sttV2LabelConf: pendingResolved.label_conf ?? row.sttV2LabelConf,
                  sttV2Coverage: pendingResolved.coverage ?? row.sttV2Coverage,
                  sttV2Flags: pendingResolved.flags ?? row.sttV2Flags,
                  sttV2Debug: pendingResolved.debug ?? row.sttV2Debug,
                  speakerSource: pendingResolved.speaker_source ?? row.speakerSource,
                  nemoSpeakerId: pendingResolved.nemo_speaker_id ?? row.nemoSpeakerId,
                  speakerLabelBefore: pendingResolved.speaker_label_before ?? row.speakerLabelBefore,
                  speakerLabelAfter: pendingResolved.speaker_label_after ?? row.speakerLabelAfter,
                  speakerChangeAtMs: pendingResolved.speaker_change_at_ms ?? row.speakerChangeAtMs,
                  speakerChangeWordIndex: pendingResolved.speaker_change_word_index ?? row.speakerChangeWordIndex,
                };
              }
              return row;
            });
          });
          if (profilingModeRef.current && event.text?.trim()) {
            const t0 = Date.now();
            setProfileEntries((prev) => {
              const next = prev.filter((e) => e.segment_id !== segmentId);
              next.push({ segment_id: segmentId, t0 });
              return next.slice(-PROFILE_ENTRIES_MAX);
            });
            pendingProfileSegmentsRef.current.push({ segment_id: segmentId, t0 });
          }
          if (debugFinalCountRef.current < 3) {
            debugFinalCountRef.current += 1;
          }
          if (USE_BACKEND_STT && event.text?.trim() && !didMerge) {
            fireBackendAnalyzeTurn(event.segment_id, event.text, displaySpeaker);
          }
        },
        onSpeakerResolved: (event: SttSpeakerResolvedEvent) => {
          const displaySpeaker = resolveSpeakerDisplay(event.speaker_label, {
            bestUserSuffix: event.best_user_suffix,
            scorePct: event.best_score_pct,
          });
          const hasRow = (transcriptsRef.current ?? []).some((r) => r.segmentId === event.segment_id);
          if (!hasRow && event.segment_id != null) {
            pendingSpeakerResolvedRef.current.set(event.segment_id, event);
            return;
          }
          const existingRow = (transcriptsRef.current ?? []).find(
            (r) => r.segmentId === event.segment_id
          );
          const textForAnalysis =
            (event.text ?? existingRow?.transcript ?? '').trim();
          const shouldAnalyze =
            USE_BACKEND_STT
            && event.flags?.provisional === false
            && textForAnalysis.length > 0
            && !existingRow?.analysisAttached;
          setTranscripts((prev) => applySpeakerResolvedToRows(prev, event, displaySpeaker));
          if (shouldAnalyze) {
            fireBackendAnalyzeTurn(event.segment_id, textForAnalysis, displaySpeaker);
          }
        },
        onNemoDiarSegments: (event: SttNemoDiarSegmentsEvent) => {
          setNemoDiarSegments(event.segments ?? []);
        },
        onEscalation: (event: SttEscalationEvent) => {
          setEscalationPrompt(event.message);
          setTimeout(() => setEscalationPrompt(null), 6000);
          void maybeSendEscalationNudge(event);
        },
        onError: (event) => {
          sttAvailableRef.current = false;
          const msg = event?.message || 'STT WebSocket error';
          addDebugLog(msg);
          const detail = msg.toLowerCase().includes('websocket error')
            ? 'STT: WebSocket failed to connect. On remote server run: sudo ./deploy/nginx_ensure_stt_websocket.sh then reload Nginx.'
            : `STT: ${msg}`;
          setStatusDetail((prev) => (prev ? `${prev}; ${detail}` : detail));
        },
        onClose: () => {
          sttAvailableRef.current = false;
          addDebugLog('STT WebSocket closed');
        },
      });
      sttSessionRef.current = result.sttSession;
      sttAvailableRef.current = true;
      addDebugLog('STT connected');
      return result;
    } catch (err: any) {
      sttAvailableRef.current = false;
      const msg = err?.message || String(err);
      addDebugLog(msg);
      setStatusDetail((prev) => (prev ? `${prev}; STT: ${msg}` : `STT: ${msg}`));
      return null;
    } finally {
      sttConnectingRef.current = false;
    }
  };

  const startSession = async () => {
    const now = Date.now();
    const cutCooldownMs = 6000;
    const sinceCut = now - lastStopSessionAtRef.current;
    if (sinceCut < cutCooldownMs) {
      return;
    }
    setStatus('connecting');
    setStatusDetail('Requesting microphone…');
    clearConnectionTimeout();
    connectionTimeoutRef.current = setTimeout(() => {
      setStatus((s) => {
        if (s === 'connecting') {
          setStatusDetail('Connection timed out. Check GEMINI_API_KEY and network.');
          return 'disconnected';
        }
        return s;
      });
      connectionTimeoutRef.current = null;
    }, 15000);
    const wasDrainPending = !!drainTimeoutRef.current;
    clearDrainTimeout();
    if (wasDrainPending) {
      // If user restarts quickly after CUT, don't reuse sessions that were scheduled for drain/disconnect.
      const live = liveSessionRef.current;
      const stt = sttSessionRef.current;
      try { live?.disconnect?.(); } catch (_) {}
      try { stt?.disconnect?.(); } catch (_) {}
      liveSessionRef.current = null;
      sttSessionRef.current = null;
    }
    setDebugLogs([]);
    addDebugLog('Session init…');
    try {
      const stream = await getMicrophoneStream({ audio: true });
      streamRef.current = stream;
      addDebugLog('Voice streaming started');
      setStatusDetail('Creating audio context…');
      const inputCtx = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });
      audioContextRef.current = inputCtx;
      const source = inputCtx.createMediaStreamSource(stream);
      sourceRef.current = source;
      const processor = inputCtx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      const outputCtx = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 24000 });
      outputAudioContextRef.current = outputCtx;
      nextStartTimeRef.current = 0;

      const hadSession = !!liveSessionRef.current;
      let session: { sendAudio: (d: Float32Array) => void; sendInitMarker: () => void; disconnect: () => void } | null = liveSessionRef.current;
      let combinedVoiceSampleBase64: string | null = null;
      let speakerUserIdsInOrder: string[] = [];
      if (!session) {
      const candidateUserIds = Array.from(
        new Set([user.id, ...(user.lovedOnes ?? []).map((lovedOne) => lovedOne.id).filter(Boolean)])
      );
      const lovedOnesWithVoiceProfile = (user.lovedOnes ?? []).filter((lovedOne) => !!lovedOne.voiceProfileId);
      setStatusDetail('Creating session…');
      addDebugLog('Connecting to STT…');
      const sttOptions = {
        candidateUserIds,
        languageCode: user.preferences?.sttLanguageCode ?? (typeof localStorage !== 'undefined' ? localStorage.getItem('inside_stt_language') : null) ?? 'auto',
        minSpeakerCount: 1,
        maxSpeakerCount: 2,
        skipDiarization: useSttV2 ? skipDiarization : undefined,
        disableSpeakerUnionJoin: user.preferences?.sttDisableUnionJoin ?? false,
      };
      if (USE_BACKEND_STT) {
        if (!sttSessionRef.current) {
          const result = await connectBackendStt(sttOptions);
          if (result) {
            combinedVoiceSampleBase64 = result.combinedVoiceSampleBase64;
            speakerUserIdsInOrder = result.speakerUserIdsInOrder;
          }
        } else {
          addDebugLog('STT already connected');
        }
      } else {
        const result = await createSttSessionOnly(sttOptions);
        combinedVoiceSampleBase64 = result.combinedVoiceSampleBase64;
        speakerUserIdsInOrder = result.speakerUserIdsInOrder;
        sttSessionRef.current = null;
        sttAvailableRef.current = false;
      }

      const speakerNamesInOrder = speakerUserIdsInOrder.map((uid) =>
        uid === user.id ? user.name : (user.lovedOnes ?? []).find((l) => l.id === uid)?.name ?? 'Unknown'
      );
      const voiceOptions =
        !USE_BACKEND_STT && combinedVoiceSampleBase64 && speakerNamesInOrder.length > 0
          ? { combinedVoiceSampleBase64, speakerNamesInOrder }
          : undefined;
      const liveCoachOptions = { ...(voiceOptions || {}), useBackendStt: USE_BACKEND_STT };

      const geminiCallbacks = {
        onOpen: () => {
          addDebugLog('Gemini connected');
          clearConnectionTimeout();
          setStatusDetail('');
          setStatus('active');
          setIsActive(true);
        },
        onClose: () => {
          clearConnectionTimeout();
          setStatus('disconnected');
          setIsActive(false);
          setStatusDetail('Session ended. Click Init to continue.');
        },
        onError: (err: any) => {
          clearConnectionTimeout();
          console.error('[LiveCoach] onError:', err);
          setStatus('disconnected');
          setStatusDetail(err?.message ? `Error: ${err.message}` : 'Connection error');
        },
        onAnalysis: (data: AnalysisData) => {
            addDebugLog('Gemini analysis received');
            const responseTs = Date.now();
            setGeminiResponses((prev) => [...prev.slice(-99), { speaker: data.speaker, sentiment: data.sentiment, horseman: data.horseman, level: data.level, nudgeText: data.nudgeText, suggestedRephrasing: data.suggestedRephrasing, _ts: responseTs }]);
            const t_received = responseTs;
            if (profilingModeRef.current && pendingProfileSegmentsRef.current.length > 0) {
              const pending = pendingProfileSegmentsRef.current.shift()!;
              const latencyLive = t_received - pending.t0;
              setProfileEntries((prev) =>
                prev.map((e) =>
                  e.segment_id === pending.segment_id ? { ...e, latency_live_audio: latencyLive } : e
                )
              );
            }
            const lagFromTranscript = lastSttFinalAtRef.current ? t_received - lastSttFinalAtRef.current : undefined;
            const targetForLive = pickMergeTarget(transcriptsRef.current);
            setAnalysisLatencyLog((prev) => [
              ...prev.slice(-(ANALYSIS_LATENCY_LOG_MAX - 1)),
              { source: 'live_audio' as const, segment_id: targetForLive?.segmentId, latency_ms: lagFromTranscript, t_received },
            ]);
            // Logic to fallback if model returns generic names (match inside/LiveCoachMode)
            let displaySpeaker = data.speaker;
            if (displaySpeaker === 'Speaker 1') {
                displaySpeaker = user.name;
            } else if (displaySpeaker === 'Speaker 2') {
                displaySpeaker = partnerName;
            } else if (displaySpeaker === 'Unknown' || displaySpeaker === 'Detecting...') {
                displaySpeaker = lastGeminiSpeakerRef.current ?? user.name;
            }
            if (displaySpeaker !== 'Unknown' && displaySpeaker !== 'Detecting...') {
                lastGeminiSpeakerRef.current = displaySpeaker;
            }

            // When USE_BACKEND_STT: never add a row from Gemini — only merge or push to pending (avoids duplicate STT + Gemini rows). Do not overwrite rows that already have backend analysis.
            if (USE_BACKEND_STT) {
              setTranscripts((prev) => {
                const target = pickMergeTarget(prev);
                if (target != null && target.analysisSource === 'backend') {
                  pendingAnalysesRef.current.push({ sentiment: data.sentiment, horseman: data.horseman, level: data.level, nudgeText: data.nudgeText, suggestedRephrasing: data.suggestedRephrasing });
                  return prev;
                }
                const unattached = prev.filter((r) => !r.analysisAttached);
                const lastRow = prev.length > 0 ? prev[prev.length - 1] : null;
                const targetIsLast = lastRow != null && target?.id === lastRow.id;
                if (target != null) {
                  const idx = prev.findIndex((r) => r === target);
                  if (idx >= 0) {
                    const next = [...prev];
                    next[idx] = { ...next[idx], sentiment: data.sentiment, horseman: data.horseman, level: data.level, nudgeText: data.nudgeText, suggestedRephrasing: data.suggestedRephrasing, analysisAttached: true, analysisSource: 'live' as const, analysisResponseTs: responseTs };
                    return next;
                  }
                }
                pendingAnalysesRef.current.push({ sentiment: data.sentiment, horseman: data.horseman, level: data.level, nudgeText: data.nudgeText, suggestedRephrasing: data.suggestedRephrasing });
                return prev;
              });
            } else if (!sttAvailableRef.current) {
              // STT unavailable: Gemini fallback — add row and optionally run voice matching
              const transcriptText = (data.transcript || '').trim();
              const candidateUserIds = Array.from(new Set([user.id, ...(user.lovedOnes ?? []).map((l) => l.id).filter(Boolean)]));
              const ring = audioRingRef.current;
              const hasEnoughAudio = ring && ring.totalWritten >= RING_SAMPLE_RATE * 1;
              const addGeminiRow = (speaker: string) => {
                setTranscripts((prev) => {
                  if (transcriptText.length > 0 && prev.length > 0) {
                    const last = prev[prev.length - 1];
                    const lastText = (last.transcript || '').trim();
                    const sameOrContained = lastText === transcriptText
                      || (lastText.length > 0 && transcriptText.includes(lastText))
                      || (transcriptText.length > 3 && lastText.includes(transcriptText));
                    if (sameOrContained) {
                      return [
                        ...prev.slice(0, -1),
                        { ...last, transcript: transcriptText || last.transcript, speaker, sentiment: data.sentiment, horseman: data.horseman, level: data.level, nudgeText: data.nudgeText, suggestedRephrasing: data.suggestedRephrasing, source: 'Gemini' as const },
                      ];
                    }
                  }
                  return [...prev, { ...data, speaker, id: Date.now().toString(), timestamp: Date.now(), source: 'Gemini' as const }];
                });
              };
              if (hasEnoughAudio && ring && candidateUserIds.length > 0) {
                const lastSamples = getLastNSamplesFromRing(
                  ring.buffer,
                  ring.writeIndex,
                  ring.totalWritten,
                  RING_SAMPLE_RATE,
                  VOICE_MATCH_SECONDS
                );
                if (lastSamples.length > 0) {
                  const wavBlob = float32ToWavBlob(lastSamples, RING_SAMPLE_RATE);
                  apiService
                    .identifySpeaker(candidateUserIds, wavBlob)
                    .then((res) => {
                      const matchedId = res.data?.user_id ?? null;
                      const speaker =
                        matchedId === user.id
                          ? user.name
                          : matchedId
                            ? (user.lovedOnes ?? []).find((l) => l.id === matchedId)?.name ?? displaySpeaker
                            : displaySpeaker;
                      addGeminiRow(speaker);
                    })
                    .catch(() => addGeminiRow(displaySpeaker));
                  return;
                }
              }
              addGeminiRow(displaySpeaker);
            } else {
              // STT provides transcript rows: attach to target from pickMergeTarget (max end_ms / min start_ms / min timestamp / min segmentId)
              setTranscripts((prev) => {
                const target = pickMergeTarget(prev);
                if (target != null) {
                  const idx = prev.findIndex((r) => r === target);
                  if (idx >= 0) {
                    const next = [...prev];
                    next[idx] = { ...next[idx], sentiment: data.sentiment, horseman: data.horseman, level: data.level, nudgeText: data.nudgeText, suggestedRephrasing: data.suggestedRephrasing, analysisAttached: true, analysisResponseTs: responseTs };
                    return next;
                  }
                }
                pendingAnalysesRef.current.push({ sentiment: data.sentiment, horseman: data.horseman, level: data.level, nudgeText: data.nudgeText, suggestedRephrasing: data.suggestedRephrasing });
                return prev;
              });
            }

            // Update Dashboard State (sentiment indicator)
            setCurrentSentiment(data.sentiment);

            if (data.horseman !== 'None') {
                setActiveHorseman(data.horseman);
                setNudge(`${data.horseman} Detected`);
                setCoachingSticky(prev => ({ ...prev, horseman: data.horseman }));
            }
            if (data.sentiment !== 'Neutral') {
                setCoachingSticky(prev => ({ ...prev, sentiment: data.sentiment }));
            }
        },
        onAudioData: (buffer) => {
          if (!outputAudioContextRef.current) return;
          const ctx = outputAudioContextRef.current;
          
          if (ctx.state === 'closed') return;

          const src = ctx.createBufferSource();
          src.buffer = buffer;
          src.connect(ctx.destination);
          
          const currentTime = ctx.currentTime;
          if (nextStartTimeRef.current < currentTime) {
            nextStartTimeRef.current = currentTime;
          }
          src.start(nextStartTimeRef.current);
          nextStartTimeRef.current += buffer.duration;
        },
      };

      if (!USE_BACKEND_STT) {
        setStatusDetail('Connecting to Gemini…');
        addDebugLog('Connecting to Gemini…');
        const liveSession = await connectLiveCoach(userForCoach, geminiCallbacks, {
          ...liveCoachOptions,
          resumptionHandle: resumptionHandleRef.current,
          onResumptionHandle: (h) => { resumptionHandleRef.current = h; },
          onGoAway: () => { setStatusDetail('Connection closing…'); },
        });
        session = liveSession;
        liveSessionRef.current = liveSession;
        setGeminiSystemPrompt(liveSession.systemInstruction ?? null);
        setGeminiResponses([]);
      }
      } // end if (!session)

      if (!session && !USE_BACKEND_STT) throw new Error('No session');
      // When Gemini is used for transcription (no backend STT), send "init" before mic so Gemini only transcribes after init. When backend STT is used, skip init.
      if (!USE_BACKEND_STT) session.sendInitMarker();
      // Ring buffer for voice matching on Gemini-sourced transcripts
      audioRingRef.current = {
        buffer: new Float32Array(RING_CAPACITY),
        writeIndex: 0,
        totalWritten: 0,
      };
      let firstProcess = true;
      let audioProcessCount = 0;
      processor.onaudioprocess = (e) => {
        audioProcessCount++;
        if (firstProcess) {
          firstProcess = false;
          addDebugLog('Sending audio to STT & Gemini');
        }
        const inputData = e.inputBuffer.getChannelData(0);
        const ring = audioRingRef.current;
        if (ring && inputData.length > 0) {
          const len = Math.min(inputData.length, RING_CAPACITY);
          for (let i = 0; i < len; i++) {
            ring.buffer[ring.writeIndex] = inputData[i];
            ring.writeIndex = (ring.writeIndex + 1) % RING_CAPACITY;
          }
          ring.totalWritten = Math.min(RING_CAPACITY, ring.totalWritten + len);
        }
        const bands = waveformBandsRef.current;
        const chunkSize = Math.max(1, Math.floor(inputData.length / bands.length));
        for (let b = 0; b < bands.length; b++) {
          const start = b * chunkSize;
          const end = Math.min(start + chunkSize, inputData.length);
          let sumSq = 0;
          for (let i = start; i < end; i++) sumSq += inputData[i] * inputData[i];
          const rms = Math.sqrt(sumSq / (end - start)) || 0;
          bands[b] = Math.min(1, rms * 14);
        }
        liveSessionRef.current?.sendAudio(inputData);
        sttSessionRef.current?.sendAudio(inputData);
      };

      source.connect(processor);
      processor.connect(inputCtx.destination);
      inputCtx.resume().catch(() => {});
      outputCtx.resume().catch(() => {});

      if (hadSession || USE_BACKEND_STT) {
        setStatus('active');
        setStatusDetail('');
        setIsActive(true);
      }
    } catch (err: any) {
      clearConnectionTimeout();
      const msg = err?.message || String(err);
      console.error('[LiveCoach] Failed to start session:', msg, err);
      setStatus('disconnected');
      setStatusDetail(`Error: ${msg}`);
      alert(`Could not start Dialogue Deck: ${msg}`);
    }
  };

  const stopSession = (fromUserCut?: boolean) => {
    if (fromUserCut) {
      lastStopSessionAtRef.current = Date.now();
      setInitCooldownEndAt(Date.now() + 6000);
    }
    clearConnectionTimeout();
    // Clear any previous drain timeout (e.g. double Cut)
    if (drainTimeoutRef.current) {
      clearTimeout(drainTimeoutRef.current);
      drainTimeoutRef.current = null;
    }

    // 1. Stop capturing and sending new audio immediately (mic off, audio graph torn down)
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (processorRef.current) {
      try { processorRef.current.disconnect(); } catch (_) {}
      processorRef.current.onaudioprocess = null;
      processorRef.current = null;
    }
    if (sourceRef.current) {
      try { sourceRef.current.disconnect(); } catch (_) {}
      sourceRef.current = null;
    }
    if (audioContextRef.current) {
      if (audioContextRef.current.state !== 'closed') {
        audioContextRef.current.close().catch(console.error);
      }
      audioContextRef.current = null;
    }
    if (outputAudioContextRef.current) {
      if (outputAudioContextRef.current.state !== 'closed') {
        outputAudioContextRef.current.close().catch(console.error);
      }
      outputAudioContextRef.current = null;
    }

    if (audioElementRef.current) {
      audioElementRef.current.pause();
      audioElementRef.current = null;
    }
    setPlayingAudioId(null);
    setInterimTranscript(null);
    setIsActive(false);
    setStatus('disconnected');
    setStatusDetail('');
    audioRingRef.current = null;
    waveformBandsRef.current.fill(0);
    setWaveformHeights(Array(30).fill(4));

    // 2. Keep STT and Gemini connections open briefly so in-flight audio can be processed and shown
    const liveSession = liveSessionRef.current;
    const sttSession = sttSessionRef.current;
    const DRAIN_MS = 4000;
    setStatusDetail('Processing remaining audio…');
    drainTimeoutRef.current = setTimeout(() => {
      drainTimeoutRef.current = null;
      setStatusDetail('');
      setCoachingSticky({ horseman: null, sentiment: 'Neutral' });
      if (liveSession) {
        try { liveSession.disconnect(); } catch (_) {}
        if (liveSessionRef.current === liveSession) liveSessionRef.current = null;
      }
      if (sttSession) {
        try { sttSession.disconnect(); } catch (_) {}
        if (sttSessionRef.current === sttSession) sttSessionRef.current = null;
      }
    }, DRAIN_MS);
  };

  const handleExit = () => {
      stopSession();
      onExit();
  };

  // When user exits Dialogue Deck (unmount), close sockets immediately.
  useEffect(() => {
    return () => {
      if (drainTimeoutRef.current) {
        clearTimeout(drainTimeoutRef.current);
        drainTimeoutRef.current = null;
      }
      const live = liveSessionRef.current;
      const stt = sttSessionRef.current;
      try { live?.disconnect?.(); } catch (_) {}
      try { stt?.disconnect?.(); } catch (_) {}
      liveSessionRef.current = null;
      sttSessionRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (initCooldownEndAt <= 0) return;
    const remaining = initCooldownEndAt - Date.now();
    if (remaining <= 0) {
      setInitCooldownEndAt(0);
      return;
    }
    const t = setTimeout(() => setInitCooldownEndAt(0), remaining);
    return () => clearTimeout(t);
  }, [initCooldownEndAt]);

  useEffect(() => {
    if (scrollRef.current) {
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [transcripts]);

  const sttDebugRow = useMemo(() => {
    if (!sttDebugRowId) return null;
    const base = transcripts.find((row) => row.id === sttDebugRowId) ?? null;
    if (!base || base.segmentId == null) return base;
    const sameSegment = transcripts.filter((row) => row.segmentId === base.segmentId);
    const withVoiceId = sameSegment.find((row) => {
      const speaker = row.sttV2Debug?.speaker as Record<string, unknown> | null | undefined;
      return Boolean(speaker && 'voice_id' in speaker);
    });
    if (withVoiceId) return withVoiceId;
    const nonProvisional = sameSegment.find((row) => row.provisional === false);
    return nonProvisional ?? base;
  }, [sttDebugRowId, transcripts]);
  const hasSttV2Debug = Boolean(
    sttDebugRow?.sttV2Debug
    || sttDebugRow?.sttV2LabelConf != null
    || sttDebugRow?.sttV2Coverage != null
    || (sttDebugRow?.sttV2Flags && Object.keys(sttDebugRow.sttV2Flags).length > 0)
  );

  // sttDebugRow selection handled by useMemo above; no side effects needed.

  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    if (!interimTranscript) return;
    // Only autoscroll if user is already near bottom
    const distanceFromBottom = el.scrollHeight - (el.scrollTop + el.clientHeight);
    const shouldScroll = distanceFromBottom < 160;
    if (shouldScroll) {
      el.scrollTop = el.scrollHeight;
    }
  }, [interimTranscript?.transcript, interimTranscript?.speaker]);

  useEffect(() => {
    if (!isActive) return;
    const interval = setInterval(() => {
      const bands = waveformBandsRef.current;
      setWaveformHeights((prev) =>
        Array.from(bands, (v) => Math.max(4, Math.min(32, 4 + v * 28)))
      );
    }, 60);
    return () => clearInterval(interval);
  }, [isActive]);

  // Preconnect STT WebSocket on enter to warm up diarization before Init.
  useEffect(() => {
    setStatus('disconnected');
    setStatusDetail('Click Init to start');
    if (USE_BACKEND_STT) {
      const candidateUserIds = Array.from(
        new Set([user.id, ...(user.lovedOnes ?? []).map((lovedOne) => lovedOne.id).filter(Boolean)])
      );
      const sttOptions = {
        candidateUserIds,
        languageCode: user.preferences?.sttLanguageCode ?? (typeof localStorage !== 'undefined' ? localStorage.getItem('inside_stt_language') : null) ?? 'auto',
        minSpeakerCount: 1,
        maxSpeakerCount: 2,
        skipDiarization: useSttV2 ? skipDiarization : undefined,
        disableSpeakerUnionJoin: user.preferences?.sttDisableUnionJoin ?? false,
      };
      void connectBackendStt(sttOptions);
    }
    return () => {
      stopSession();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    return () => stopSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const getHorsemanColor = (h: string) => {
      switch(h) {
          case 'Criticism': return 'text-orange-500 border-orange-500 bg-orange-500/10';
          case 'Contempt': return 'text-red-500 border-red-500 bg-red-500/10';
          case 'Defensiveness': return 'text-yellow-500 border-yellow-500 bg-yellow-500/10';
          case 'Stonewalling': return 'text-slate-400 border-slate-400 bg-slate-400/10';
          default: return 'text-slate-700 border-slate-800 bg-slate-900';
      }
  };

  /** Only treat as current user when speaker is actually the user (name or id). Avoids "Unknown_1" matching due to "1". */
  const isSpeakerUser = (speaker: string) => {
      return speaker === user.name || speaker === user.id;
  };

  /** Format backend unknown labels for display: Unknown_N → "UNKNOWN N", Unknown/UNKNOWN → "UNKNOWN"; else return label unchanged. */
  const formatUnknownSpeakerDisplay = (label: string): string => {
    if (!label) return label;
    const unknownN = /^Unknown_(\d+)$/i.exec(label);
    if (unknownN) return `UNKNOWN ${unknownN[1]}`;
    if (/^Unknown$/i.test(label)) return 'UNKNOWN';
    return label;
  };

  /** True when speaker is assigned (known name or Unknown_N cluster); false only for unassigned/streaming. */
  const isSpeakerAssigned = (speaker: string) => {
    if (!speaker) return false;
    // Unknown_N clusters are assigned (they get colors); only unassigned/streaming are not
    return true;
  };

  /** Grey styling for unassigned (streaming or not yet resolved) bubbles, tail, and meta. */
  const GREY_BUBBLE_CLASS = 'bg-gray-200 text-gray-800 border-2 border-gray-400 dark:bg-gray-600 dark:text-gray-200 dark:border-gray-500';
  const GREY_TAIL_CLASS = 'border-r-gray-400 dark:border-r-gray-500';
  const GREY_META_CLASS = 'text-gray-600 dark:text-gray-400';

  /** Sentiment score for tone bar: positive 1–5 → 1/5 to 1, negative -1 to -5 → -1/5 to -1, 0 neutral. Bar length uses abs(score). */
  const sentimentBarScore = (t: TranscriptItem): number => {
    if (t.level != null && t.level !== 0) {
      const clamped = Math.max(-5, Math.min(5, t.level));
      return clamped / 5; // -1..1
    }
    if (t.sentiment === 'Positive') return 1;
    if (t.sentiment === 'Hostile') return -1;
    if (t.sentiment === 'Negative' || (t.horseman && t.horseman !== 'None')) return -0.6;
    return 0; // Neutral
  };

  /** Up to 5 speakers: Dialogue Deck palette (spk-blue, spk-orange, spk-green, spk-purple, spk-yellow). */
  const SPEAKER_BUBBLE_CLASSES = [
    'bg-spk-blue text-white border-2 border-gray-900 dark:border-gray-200',
    'bg-spk-orange text-gray-900 dark:text-gray-100 border-2 border-gray-900 dark:border-gray-200',
    'bg-spk-green text-white border-2 border-gray-900 dark:border-gray-200',
    'bg-spk-purple text-white border-2 border-gray-900 dark:border-gray-200',
    'bg-spk-yellow text-gray-900 dark:text-gray-100 border-2 border-gray-900 dark:border-gray-200',
  ] as const;
  const SPEAKER_BAR_CLASSES = [
    'bg-spk-blue',
    'bg-spk-orange',
    'bg-spk-green',
    'bg-spk-purple',
    'bg-spk-yellow',
  ] as const;
  const SPEAKER_META_CLASSES = [
    'text-blue-200 dark:text-blue-100',
    'text-gray-900 dark:text-gray-100 opacity-70',
    'text-green-200 dark:text-green-100',
    'text-purple-200 dark:text-purple-100',
    'text-gray-900 dark:text-gray-100 opacity-70',
  ] as const;
  /** Map display speaker to a canonical key so the same person always gets the same color (e.g. user vs partner vs Unknown_1). */
  const canonicalSpeaker = useCallback((speaker: string) => {
    if (isSpeakerUser(speaker)) return user.name;
    if (speaker === partnerName) return partnerName;
    const lovedOne = (user.lovedOnes ?? []).find((l) => l.name === speaker);
    if (lovedOne) return lovedOne.name;
    return speaker;
  }, [user.name, user.lovedOnes, partnerName]);

  const speakerOrder = React.useMemo(() => {
    const order: string[] = [user.name];
    const seen = new Set<string>([user.name]);
    if (partnerName && !seen.has(partnerName)) {
      seen.add(partnerName);
      order.push(partnerName);
    }
    for (const l of user.lovedOnes ?? []) {
      if (l.name && !seen.has(l.name)) {
        seen.add(l.name);
        order.push(l.name);
      }
    }
    for (const t of transcripts) {
      const key = canonicalSpeaker(t.speaker);
      if (!seen.has(key)) {
        seen.add(key);
        order.push(key);
      }
    }
    if (interimTranscript) {
      const key = canonicalSpeaker(interimTranscript.speaker);
      if (!seen.has(key)) order.push(key);
    }
    return order.slice(0, 5);
  }, [transcripts, interimTranscript?.speaker, user.name, user.lovedOnes, partnerName, canonicalSpeaker]);
  const getSpeakerIndex = (speaker: string) => {
    const unknownMatch = /^Unknown(_(\d+))?$/i.exec(speaker);
    if (unknownMatch) {
      const N = unknownMatch[2] ? parseInt(unknownMatch[2], 10) : 1;
      return 2 + ((N - 1) % 3);
    }
    const key = canonicalSpeaker(speaker);
    const i = speakerOrder.indexOf(key);
    return i >= 0 ? i : 0;
  };
  /** Tail (speech pointer) border color to match bubble — same palette as bubbles. */
  const SPEAKER_TAIL_CLASSES = ['border-r-spk-blue', 'border-r-spk-orange', 'border-r-spk-green', 'border-r-spk-purple', 'border-r-spk-yellow'] as const;
  const getBubbleClasses = (speaker: string) => SPEAKER_BUBBLE_CLASSES[getSpeakerIndex(speaker)] ?? SPEAKER_BUBBLE_CLASSES[0];
  const getBarClasses = (speaker: string) => SPEAKER_BAR_CLASSES[getSpeakerIndex(speaker)] ?? SPEAKER_BAR_CLASSES[0];
  const getMetaClasses = (speaker: string) => SPEAKER_META_CLASSES[getSpeakerIndex(speaker)] ?? SPEAKER_META_CLASSES[0];
  const getTailClass = (speaker: string) => SPEAKER_TAIL_CLASSES[getSpeakerIndex(speaker)] ?? SPEAKER_TAIL_CLASSES[0];

  const toneBadgeClass = currentSentiment === 'Hostile'
    ? 'bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300 border-red-300 dark:border-red-700'
    : currentSentiment === 'Negative'
    ? 'bg-amber-100 dark:bg-amber-900 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-700'
    : currentSentiment === 'Positive'
    ? 'bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 border-green-300 dark:border-green-700'
    : 'bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 border-green-300 dark:border-green-700';
  const formatTime = (ts: number) => {
    const d = new Date(ts);
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
  };

  return (
    <div className="h-full flex flex-col bg-background-light dark:bg-background-dark text-gray-900 dark:text-gray-100 min-h-screen font-sans relative overflow-hidden min-w-0">
      <div className="absolute inset-0 z-0 pointer-events-none bg-[length:20px_20px] opacity-60 bg-[image:linear-gradient(to_right,#E5E7EB_1px,transparent_1px),linear-gradient(to_bottom,#E5E7EB_1px,transparent_1px)] dark:bg-[image:linear-gradient(to_right,#1E293B_1px,transparent_1px),linear-gradient(to_bottom,#1E293B_1px,transparent_1px)]" />
      <header className="relative z-10 px-4 pt-6 pb-4 flex flex-wrap justify-between items-start gap-2 border-b-2 border-gray-900 dark:border-gray-700 bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm min-w-0">
        <div className="min-w-0 flex-shrink">
          <div className="flex items-center gap-2 mb-1">
            <span className={`w-2 h-2 rounded-full ${status === 'active' ? 'bg-green-500 animate-pulse' : status === 'connecting' ? 'bg-amber-500 animate-pulse' : 'bg-gray-400'}`} />
            <span className="font-mono text-xs font-bold tracking-widest text-gray-500 dark:text-gray-400 uppercase">
              Signal: {status === 'active' ? 'Live' : status === 'connecting' ? 'Connecting…' : 'Waiting'}
            </span>
          </div>
          {statusDetail && (
            <p className="font-mono text-[10px] text-gray-500 dark:text-gray-400 truncate max-w-[200px]" title={statusDetail}>{statusDetail}</p>
          )}
          <h1 className="font-display text-3xl md:text-4xl uppercase tracking-tighter leading-none text-gray-900 dark:text-white">Dialogue<br />Deck</h1>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2 flex-shrink-0">
          {showDebug && useSttV2 && (
            <label className="flex items-center gap-1.5 font-mono text-[10px] text-gray-600 dark:text-gray-400 cursor-pointer shrink-0" title="Use sentence boundaries + voice embedding matching only (no diarization model)">
              <input
                type="checkbox"
                checked={skipDiarization}
                onChange={(e) => {
                  const v = e.target.checked;
                  setSkipDiarization(v);
                  if (typeof localStorage !== 'undefined') localStorage.setItem('inside_skip_diarization', v ? 'true' : 'false');
                }}
                className="rounded border-gray-400 dark:border-gray-500"
              />
              <span className="hidden sm:inline">Skip diarization</span>
            </label>
          )}
          {showDebug && debugEnabled && (
            <button
              type="button"
              onClick={() => setShowDebugPanel((p) => !p)}
              className="relative p-1.5 rounded border border-gray-300 dark:border-gray-600 hover:bg-gray-100/80 dark:hover:bg-gray-800/80 text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-400"
              title={showDebugPanel ? 'Hide debug log' : 'Show debug log'}
              aria-label="Toggle debug log"
            >
              <Bug className="w-3.5 h-3.5" />
              {debugLogs.length > 0 && (
                <span className="absolute -top-0.5 -right-0.5 flex h-3 min-w-[12px] items-center justify-center rounded-full bg-gray-500 px-0.5 text-[7px] font-medium text-white">
                  {Math.min(99, debugLogs.length)}
                </span>
              )}
            </button>
          )}
          <button type="button" onClick={handleExit} className="w-8 h-8 flex items-center justify-center border-2 border-gray-200 dark:border-gray-500 text-gray-400 dark:text-gray-500 hover:border-gray-900 dark:hover:border-gray-200 hover:text-gray-900 dark:hover:text-gray-200 transition-colors" aria-label="Close">
            <X size={20} />
          </button>
        </div>
      </header>

      {escalationPrompt && (
        <div className="relative z-10 mx-4 mt-2 border-2 border-red-500 bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300 font-mono text-[10px] uppercase tracking-widest p-2 rounded-sm">
          {escalationPrompt}
        </div>
      )}

      <div className="relative z-10 border-b-2 border-gray-900 dark:border-gray-700 bg-slate-50 dark:bg-slate-800 p-3 min-w-0">
        <div className="flex items-center justify-between gap-2 mb-2 min-w-0">
          <div className="flex items-center gap-2 text-accent-blue dark:text-blue-400 min-w-0">
            <BarChart2 className="w-[18px] h-[18px] shrink-0" />
            <span className="font-mono text-xs font-bold uppercase tracking-wider truncate">Conversation barometer</span>
          </div>
          <span className={`font-mono text-xs font-bold px-2 py-0.5 rounded border shrink-0 ${toneBadgeClass}`}>
            {currentSentiment.toUpperCase()}
          </span>
        </div>
        <div className="relative flex items-center justify-center gap-0.5 h-14 w-full overflow-x-auto">
          <div className="absolute left-0 right-0 top-1/2 h-0.5 -translate-y-1/2 bg-gray-300 dark:bg-gray-600 z-0" aria-hidden />
          <div className="relative z-10 flex items-center justify-center gap-1 min-w-full py-1">
            {visibleTranscripts.length > 0 && visibleTranscripts.slice(-32).map((t) => {
                const score = sentimentBarScore(t);
                const isUser = isSpeakerUser(t.speaker);
                const magnitude = Math.min(1, Math.abs(score));
                const barHeight = magnitude === 0 ? 3 : Math.round(3 + magnitude * 21);
                const colorClass = getBarClasses(t.speaker);
                const half = 24;
                return (
                  <div
                    key={t.id}
                    className="flex flex-col items-center justify-end w-2 shrink-0"
                    style={{ height: '48px' }}
                    title={t.level != null && t.level !== 0
                      ? `${isUser ? 'You' : formatUnknownSpeakerDisplay(t.speaker)}: ${t.sentiment ?? 'Neutral'} (level ${t.level > 0 ? t.level : t.level})`
                      : `${isUser ? 'You' : formatUnknownSpeakerDisplay(t.speaker)}: ${t.sentiment ?? 'Neutral'}`}
                  >
                    {score > 0 ? (
                      <>
                        <div style={{ height: `${half - barHeight}px`, minHeight: 0 }} />
                        <div className={`w-1.5 rounded-t-sm transition-all duration-300 ${colorClass}`} style={{ height: `${barHeight}px` }} />
                        <div style={{ height: `${half}px`, minHeight: 0 }} />
                      </>
                    ) : score < 0 ? (
                      <>
                        <div style={{ height: `${half}px`, minHeight: 0 }} />
                        <div className={`w-1.5 rounded-b-sm transition-all duration-300 ${colorClass}`} style={{ height: `${barHeight}px` }} />
                        <div style={{ height: `${half - barHeight}px`, minHeight: 0 }} />
                      </>
                    ) : (
                      <>
                        <div style={{ height: `${half - 1}px`, minHeight: 0 }} />
                        <div className={`w-1.5 rounded-sm ${colorClass}`} style={{ height: '2px' }} />
                        <div style={{ height: `${half - 1}px`, minHeight: 0 }} />
                      </>
                    )}
                  </div>
                );
              })}
          </div>
        </div>
      </div>

      <main className="relative z-10 flex-1 overflow-y-auto overflow-x-hidden p-4 space-y-6 min-h-0 min-w-0" ref={scrollRef}>
        {visibleTranscripts.length === 0 && !interimTranscript && isActive && (
          <div className="text-center py-8 font-mono text-xs text-gray-500 dark:text-gray-400 uppercase">Listening for speech patterns...</div>
        )}
        {visibleTranscripts.map((t) => {
          const isUser = isSpeakerUser(t.speaker);
          const isPlaying = playingAudioId === t.id;
          const displayName = isUser ? user.name : formatUnknownSpeakerDisplay(t.speaker);
          const isMerged = t.source === 'STT' && t.analysisAttached;
          return (
            <div key={t.id} className={`flex flex-col animate-fade-in ${isUser ? 'items-start' : 'items-end'}`}>
              <div className="flex items-center gap-2 mb-1">
                {isUser && (
                  <button
                    type="button"
                    onClick={() => t.audioSegmentBase64 && playAudioSegment(t.audioSegmentBase64, t.id, t.segmentId, t.transcript)}
                    className="w-4 h-4 bg-gray-900 dark:bg-gray-200 text-white dark:text-gray-900 flex items-center justify-center text-[10px] font-bold rounded-sm hover:opacity-80"
                    title="Play"
                  >
                    {t.audioSegmentBase64 ? (isPlaying ? <Square size={8} /> : <Play size={8} />) : '–'}
                  </button>
                )}
                <span className="font-mono text-[10px] text-gray-500 dark:text-gray-400 font-bold uppercase">{displayName}</span>
                {showDebug && (isMerged ? (
                  <>
                    <button type="button" onClick={() => openSttDebug(t)} className="font-mono text-[10px] font-bold px-1 py-0.5 rounded border bg-sky-100 dark:bg-sky-900/50 text-sky-800 dark:text-sky-200 border-sky-300 dark:border-sky-600 hover:opacity-90 cursor-pointer" title="Transcript from speech-to-text — click to show voice ID scores (debug)">STT</button>
                    <button type="button" onClick={() => openGeminiDebug(t)} className="font-mono text-[10px] font-bold px-1 py-0.5 rounded border bg-amber-100 dark:bg-amber-900/50 text-amber-800 dark:text-amber-200 border-amber-300 dark:border-amber-600 hover:opacity-90 cursor-pointer" title="Sentiment & horseman from Gemini — click to show response for this bubble (debug)">Gemini</button>
                  </>
                ) : (t.source === 'Gemini' || !t.source) ? (
                  <button type="button" onClick={() => openGeminiDebug(t)} className="font-mono text-[10px] font-bold px-1 py-0.5 rounded border bg-amber-100 dark:bg-amber-900/50 text-amber-800 dark:text-amber-200 border-amber-300 dark:border-amber-600 hover:opacity-90 cursor-pointer" title="Transcript from Gemini — click to show response for this bubble (debug)">Gemini</button>
                ) : t.source === 'STT' ? (
                  <button type="button" onClick={() => openSttDebug(t)} className="font-mono text-[10px] font-bold px-1 py-0.5 rounded border bg-sky-100 dark:bg-sky-900/50 text-sky-800 dark:text-sky-200 border-sky-300 dark:border-sky-600 hover:opacity-90 cursor-pointer" title="Transcript from speech-to-text — click to show voice ID scores (debug)">STT</button>
                ) : null)}
                {!isUser && (
                  <button
                    type="button"
                    onClick={() => t.audioSegmentBase64 && playAudioSegment(t.audioSegmentBase64, t.id, t.segmentId, t.transcript)}
                    className="w-4 h-4 bg-gray-900 dark:bg-gray-200 text-white dark:text-gray-900 flex items-center justify-center text-[10px] font-bold rounded-sm hover:opacity-80"
                    title="Play"
                  >
                    {t.audioSegmentBase64 ? (isPlaying ? <Square size={8} /> : <Play size={8} />) : '–'}
                  </button>
                )}
              </div>
              <div
                role={t.segmentId != null ? 'button' : undefined}
                tabIndex={t.segmentId != null ? 0 : undefined}
                onClick={t.segmentId != null ? () => toggleFeedbackExpanded(t.segmentId!) : undefined}
                onKeyDown={t.segmentId != null ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleFeedbackExpanded(t.segmentId!); } } : undefined}
                className={`relative p-4 max-w-[90%] neo-brutal-shadow rounded-sm ${isSpeakerAssigned(t.speaker) ? getBubbleClasses(t.speaker) : GREY_BUBBLE_CLASS} ${t.segmentId != null ? 'cursor-pointer' : ''}`}
              >
                {isUser && (
                  <>
                    <div className="absolute -left-[9px] top-4 w-0 h-0 border-t-[8px] border-t-transparent border-r-[10px] border-r-gray-900 dark:border-r-gray-200 border-b-[8px] border-b-transparent" />
                    <div className={`absolute -left-[6px] top-4 w-0 h-0 border-t-[8px] border-t-transparent border-r-[10px] ${isSpeakerAssigned(t.speaker) ? getTailClass(t.speaker) : GREY_TAIL_CLASS} border-b-[8px] border-b-transparent`} />
                  </>
                )}
                <p className="font-mono text-sm md:text-base leading-relaxed">{t.transcript}</p>
                <div className={`mt-2 text-[10px] font-mono space-y-0.5 ${isSpeakerAssigned(t.speaker) ? getMetaClasses(t.speaker) : GREY_META_CLASS} opacity-90`}>
                  <div>{formatTime(t.timestamp)}</div>
                  <div title="Analysis for this entry">
                    <span className="opacity-90">Sentiment: </span>
                    <strong>{t.analysisAttached ? (t.sentiment ?? '—') : 'Analyzing…'}</strong>
                    {t.analysisAttached && t.horseman && t.horseman !== 'None' && (
                      <>
                        <span className="opacity-90"> · Horseman: </span>
                        <strong className="text-yellow-500 dark:text-yellow-400">{t.horseman}</strong>
                      </>
                    )}
                    {t.analysisAttached && (!t.horseman || t.horseman === 'None') && (
                      <span className="opacity-70"> · Horseman: —</span>
                    )}
                    {!t.analysisAttached && <span className="opacity-70"> · Horseman: —</span>}
                  </div>
                </div>
              </div>
              {(t.nudgeText || t.suggestedRephrasing) && (
                <div className={`mt-2 p-3 rounded-sm border border-[#0D9488]/40 dark:border-teal-500/40 bg-[#F0FDFA] dark:bg-teal-900/20 text-[#0f766e] dark:text-teal-100 ${isUser ? 'ml-2' : 'mr-2'}`}>
                  {t.nudgeText && (
                    <p className="font-mono text-xs leading-relaxed mb-1">
                      <strong className="text-[#0D9488] dark:text-teal-300">Kai:</strong>{' '}
                      {t.level != null && t.level >= 4 && '✓ '}
                      {t.level != null && t.level <= -4 && '⏸️ '}
                      {t.nudgeText}
                    </p>
                  )}
                  {t.suggestedRephrasing && (
                    <p className="font-mono text-xs leading-relaxed opacity-90">
                      Try saying: «{t.suggestedRephrasing}»
                    </p>
                  )}
                </div>
              )}
              {t.segmentId != null && feedbackExpandedSegmentIds.includes(t.segmentId) && (
                <div className={`mt-1.5 flex flex-wrap items-center gap-2 font-mono text-[10px] ${isUser ? 'ml-2' : 'mr-2'}`}>
                  {feedbackSentForSegmentIds.includes(t.segmentId) ? (
                    confirmationForSegmentId === t.segmentId && (
                      <span className="text-green-600 dark:text-green-400 opacity-90">Thanks, we&apos;ll use this to improve voice ID</span>
                    )
                  ) : (
                    <>
                      <button
                        type="button"
                        disabled={!t.audioSegmentBase64 || feedbackPendingSegmentId === t.segmentId}
                        onClick={() => t.audioSegmentBase64 && handleVoiceFeedback(t.segmentId!, true, t.audioSegmentBase64)}
                        className="px-2 py-1 rounded border border-gray-900 dark:border-gray-400 bg-white dark:bg-slate-800 text-gray-900 dark:text-gray-200 hover:enabled:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed font-bold"
                        title={t.audioSegmentBase64 ? "That was me" : "Audio not available for this segment"}
                      >
                        Me
                      </button>
                      <button
                        type="button"
                        disabled={feedbackPendingSegmentId === t.segmentId}
                        onClick={() => handleVoiceFeedback(t.segmentId!, false, undefined)}
                        className="px-2 py-1 rounded border border-gray-900 dark:border-gray-400 bg-white dark:bg-slate-800 text-gray-900 dark:text-gray-200 hover:enabled:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed font-bold"
                        title="That wasn't me"
                      >
                        Not me
                      </button>
                    </>
                  )}
                  {feedbackError?.segmentId === t.segmentId && (
                    <span className="text-amber-600 dark:text-amber-400">{feedbackError.message}</span>
                  )}
                </div>
              )}
            </div>
          );
        })}

        {interimTranscript && (
          <div className={`flex flex-col ${isSpeakerUser(interimTranscript.speaker) ? 'items-start' : 'items-end'}`}>
            <div className="flex items-center gap-2 mb-1">
              {isSpeakerUser(interimTranscript.speaker) && <div className="w-4 h-4 bg-gray-900 dark:bg-gray-200 text-white dark:text-gray-900 flex items-center justify-center text-[10px] font-bold rounded-sm">–</div>}
              <span className="font-mono text-[10px] text-gray-500 dark:text-gray-400 font-bold uppercase">
                {isSpeakerUser(interimTranscript.speaker) ? user.name : formatUnknownSpeakerDisplay(interimTranscript.speaker)}
              </span>
              <span className="font-mono text-[10px] text-amber-600 dark:text-amber-400 font-bold animate-pulse" aria-hidden>LIVE</span>
            </div>
            <div className={`relative p-4 max-w-[90%] neo-brutal-shadow rounded-sm border-2 border-amber-400/50 dark:border-amber-500/50 ${isSpeakerAssigned(interimTranscript.speaker) ? getBubbleClasses(interimTranscript.speaker) : GREY_BUBBLE_CLASS}`}>
              <p className="font-mono text-sm md:text-base leading-relaxed">
                {interimTranscript.transcript}
                <span className="inline-block w-0.5 h-4 ml-0.5 align-middle bg-gray-600 dark:bg-gray-400 animate-pulse" aria-hidden />
              </p>
            </div>
          </div>
        )}

        {showDebugPanel && showDebug && (
          <div className="mt-8 border-2 border-gray-900 dark:border-gray-600 bg-gray-50 dark:bg-slate-900 rounded-sm overflow-hidden">
            <div className="bg-gray-200 dark:bg-slate-800 px-3 py-1 border-b-2 border-gray-900 dark:border-gray-600 flex items-center gap-2">
              <Terminal className="w-4 h-4" />
              <span className="font-mono text-xs font-bold uppercase">Debug Log</span>
            </div>
            <div className="p-3 font-mono text-[10px] md:text-xs text-gray-600 dark:text-gray-400 space-y-1 h-32 overflow-y-auto">
              {debugLogs.map((entry, i) => {
                const timeStr = new Date(entry.ts).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3 });
                const isGreen = /connected|STT connected|Gemini connected/i.test(entry.msg);
                const isBlue = /Connecting|Connecting to/i.test(entry.msg);
                return (
                  <div key={i} className="flex gap-2">
                    <span className="opacity-50 shrink-0">{timeStr}</span>
                    <span className={isGreen ? 'text-green-600 dark:text-green-400' : isBlue ? 'text-accent-blue dark:text-blue-400' : undefined}>{entry.msg}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </main>

      <footer className="relative z-10 border-t-2 border-gray-900 dark:border-gray-700 bg-white dark:bg-slate-900 p-4 pb-8">
        <div className="relative flex justify-center items-center h-20 w-full">
          <svg
            className="absolute left-0 right-0 top-1/2 w-full h-10 -translate-y-1/2 text-primary dark:text-blue-400 opacity-95 z-0 pointer-events-none"
            viewBox="0 0 30 24"
            preserveAspectRatio="none"
            aria-hidden
          >
            <polyline
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              points={waveformHeights
                .map((h, i) => {
                  const x = i;
                  const normalized = (h - 4) / 28;
                  const y = 12 - normalized * 11;
                  return `${x},${Math.max(1, Math.min(23, y))}`;
                })
                .join(' ')}
            />
          </svg>
          {!isActive ? (
            <button
              type="button"
              disabled={initCooldownEndAt > 0}
              onClick={() => {
                void startSession();
              }}
              className="relative z-10 group w-20 h-20 bg-white dark:bg-slate-800 rounded-full border-2 border-gray-900 dark:border-gray-500 flex flex-col items-center justify-center neo-brutal-shadow hover:translate-y-1 hover:shadow-none transition-all active:translate-y-1 active:shadow-none disabled:opacity-50 disabled:pointer-events-none disabled:cursor-not-allowed"
              title={initCooldownEndAt > 0 ? 'Wait a moment after Cut' : 'Start recording'}
            >
              <Mic className="w-8 h-8 text-primary group-hover:scale-110 transition-transform" />
              <span className="font-mono text-[10px] font-bold text-gray-900 dark:text-white mt-1 group-hover:text-primary transition-colors">INIT</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={() => {
                stopSession(true);
              }}
              className="relative z-10 group w-20 h-20 bg-white dark:bg-slate-800 rounded-full border-2 border-gray-900 dark:border-gray-500 flex flex-col items-center justify-center neo-brutal-shadow hover:translate-y-1 hover:shadow-none transition-all active:translate-y-1 active:shadow-none"
            >
              <div className="relative">
                <MicOff className="w-8 h-8 text-red-500 group-hover:scale-110 transition-transform" />
                <span className="absolute -top-0.5 -right-0.5 flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500" />
                </span>
              </div>
              <span className="font-mono text-[10px] font-bold text-gray-900 dark:text-white mt-1">CUT</span>
            </button>
          )}
        </div>
      </footer>

      {showGeminiDebugPopup && showDebug && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60" role="dialog" aria-modal="true" aria-labelledby="gemini-debug-title" onClick={() => { setShowGeminiDebugPopup(false); setGeminiDebugForRow(null); }}>
          <div className="bg-white dark:bg-slate-900 border-2 border-gray-900 dark:border-gray-600 rounded-sm shadow-lg max-w-2xl w-full max-h-[85vh] flex flex-col neo-brutal-shadow" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-3 py-2 border-b-2 border-gray-900 dark:border-gray-600 bg-amber-100 dark:bg-amber-900/30">
              <h2 id="gemini-debug-title" className="font-mono text-xs font-bold uppercase">{geminiDebugForRow ? 'Gemini response for this bubble' : 'Gemini prompt &amp; responses'}</h2>
              <button type="button" onClick={() => { setShowGeminiDebugPopup(false); setGeminiDebugForRow(null); }} className="font-mono text-xs font-bold px-2 py-1 rounded border border-gray-900 dark:border-gray-200 hover:bg-gray-200 dark:hover:bg-gray-700">Close</button>
            </div>
            <div className="flex-1 overflow-y-auto p-3 font-mono text-[10px] md:text-xs text-gray-800 dark:text-gray-200 space-y-4">
              <section>
                <h3 className="font-bold uppercase text-amber-700 dark:text-amber-400 mb-1">
                  {geminiDebugForRow?.analysisSource === 'backend' && geminiDebugForRow?.analysisPrompt
                    ? 'LLM prompt (backend analyze-turn)'
                    : 'System prompt'}
                </h3>
                <pre className="whitespace-pre-wrap break-words bg-gray-100 dark:bg-slate-800 p-2 rounded border border-gray-300 dark:border-gray-600 max-h-64 overflow-y-auto">
                  {geminiDebugForRow?.analysisSource === 'backend' && geminiDebugForRow?.analysisPrompt
                    ? geminiDebugForRow.analysisPrompt
                    : (geminiSystemPrompt ?? '—')}
                </pre>
              </section>
              <section>
                <h3 className="font-bold uppercase text-amber-700 dark:text-amber-400 mb-1">
                  {USE_BACKEND_STT ? 'Analysis (backend only)' : (geminiDebugForRow ? 'reportAnalysis response (this bubble)' : `reportAnalysis responses (${geminiResponses.length})`)}
                </h3>
                {USE_BACKEND_STT && <p className="text-[10px] opacity-80 mb-2">Analysis from POST /coach/analyze-turn; no Live reportAnalysis.</p>}
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {(() => {
                    if (geminiDebugForRow) {
                      const ts = geminiDebugForRow.analysisResponseTs;
                      const matched = ts != null ? geminiResponses.filter((r) => (r._ts as number) === ts) : [];
                      if (matched.length > 0) {
                        return matched.map((r, i) => (
                          <pre key={i} className="whitespace-pre-wrap break-words bg-gray-100 dark:bg-slate-800 p-2 rounded border border-gray-300 dark:border-gray-600">
                            {JSON.stringify({ ...r, _ts: r._ts ? new Date(r._ts as number).toISOString() : r._ts }, null, 2)}
                          </pre>
                        ));
                      }
                      return (
                        <pre className="whitespace-pre-wrap break-words bg-gray-100 dark:bg-slate-800 p-2 rounded border border-gray-300 dark:border-gray-600">
                          {JSON.stringify({ speaker: geminiDebugForRow.speaker, sentiment: geminiDebugForRow.sentiment, horseman: geminiDebugForRow.horseman, level: geminiDebugForRow.level, nudgeText: geminiDebugForRow.nudgeText, suggestedRephrasing: geminiDebugForRow.suggestedRephrasing, _note: 'From row (e.g. backend analyze-turn); no Live response stored.' }, null, 2)}
                        </pre>
                      );
                    }
                    if (geminiResponses.length === 0) return <p className="opacity-70">{USE_BACKEND_STT ? 'Backend only — analysis from analyze-turn (see row bubbles).' : 'No responses yet.'}</p>;
                    return geminiResponses.map((r, i) => (
                      <pre key={i} className="whitespace-pre-wrap break-words bg-gray-100 dark:bg-slate-800 p-2 rounded border border-gray-300 dark:border-gray-600">
                        {JSON.stringify({ ...r, _ts: r._ts ? new Date(r._ts as number).toISOString() : r._ts }, null, 2)}
                      </pre>
                    ));
                  })()}
                </div>
              </section>
              <section>
                <h3 className="font-bold uppercase text-amber-700 dark:text-amber-400 mb-1">Analysis latency (last {analysisLatencyLog.length})</h3>
                <p className="text-[10px] opacity-80 mb-2">
                  {USE_BACKEND_STT ? 'Backend only: Backend text / Backend+history when STT final triggers analyze-turn. Live audio N/A.' : 'Live audio: when Gemini sends reportAnalysis. Backend text / Backend+history: when STT final triggers analyze-turn (transcript only or with history).'}
                </p>
                <div className="flex flex-wrap gap-4 mb-3">
                  <label className="flex items-center gap-2 cursor-pointer font-mono text-[10px]" title="Record live_audio latency per segment">
                    <input
                      type="checkbox"
                      checked={profilingMode}
                      onChange={(e) => setProfilingMode(e.target.checked)}
                      className="rounded border-gray-500"
                    />
                    Profiling mode
                  </label>
                </div>
                {analysisLatencyLog.length === 0 ? (
                  <p className="opacity-70">{USE_BACKEND_STT ? 'No entries yet. Speak to see backend analyze-turn latency.' : 'No entries yet. Speak to see live_audio latency; backend entries appear when STT final triggers analyze-turn.'}</p>
                ) : (
                  <>
                    <div className="grid grid-cols-[auto_1fr_1fr_1fr] gap-x-2 gap-y-1 text-[10px] mb-2">
                      <span className="font-bold">source</span>
                      <span className="font-bold">segment_id</span>
                      <span className="font-bold">latency_ms</span>
                      <span className="font-bold">backend_ms</span>
                      {analysisLatencyLog.slice(-20).reverse().map((e, i) => (
                        <React.Fragment key={i}>
                          <span>{e.source}</span>
                          <span>{e.segment_id != null ? String(e.segment_id) : '—'}</span>
                          <span>{e.latency_ms != null ? `${e.latency_ms}` : '—'}</span>
                          <span>{e.backend_latency_ms != null ? `${e.backend_latency_ms}` : '—'}</span>
                        </React.Fragment>
                      ))}
                    </div>
                    <div className="mt-2 pt-2 border-t border-gray-300 dark:border-gray-600 font-mono text-[10px] space-y-1">
                      {(() => {
                        const liveEntries = analysisLatencyLog.filter((e) => e.source === 'live_audio' && e.latency_ms != null);
                        const liveCount = liveEntries.length;
                        const liveAvg = liveCount > 0 ? Math.round(liveEntries.reduce((s, e) => s + (e.latency_ms ?? 0), 0) / liveCount) : 0;
                        const backendEntries = analysisLatencyLog.filter((e) => e.source === 'backend_text' && e.latency_ms != null);
                        const backendCount = backendEntries.length;
                        const backendAvg = backendCount > 0 ? Math.round(backendEntries.reduce((s, e) => s + (e.latency_ms ?? 0), 0) / backendCount) : 0;
                        const backendHistoryEntries = analysisLatencyLog.filter((e) => e.source === 'backend_text_with_history' && e.latency_ms != null);
                        const backendHistoryCount = backendHistoryEntries.length;
                        const backendHistoryAvg = backendHistoryCount > 0 ? Math.round(backendHistoryEntries.reduce((s, e) => s + (e.latency_ms ?? 0), 0) / backendHistoryCount) : 0;
                        return (
                          <>
                            {!USE_BACKEND_STT && <div>Live audio: avg {liveAvg} ms ({liveCount})</div>}
                            <div>Backend text: avg {backendAvg} ms ({backendCount})</div>
                            <div>Backend+history: avg {backendHistoryAvg} ms ({backendHistoryCount})</div>
                          </>
                        );
                      })()}
                    </div>
                  </>
                )}
              </section>
              {profilingMode && (
                <section>
                  <h3 className="font-bold uppercase text-amber-700 dark:text-amber-400 mb-1">Profiling (same segment)</h3>
                  <p className="text-[10px] opacity-80 mb-2">{USE_BACKEND_STT ? 'Backend only: Live audio N/A; backend latency from STT final to analyze-turn response.' : 'One row per segment: live_audio latency from STT final to reportAnalysis.'}</p>
                  {profileEntries.length === 0 ? (
                    <p className="opacity-70">No profile entries yet. Speak with Profiling mode on.</p>
                  ) : (
                    <>
                      <div className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-1 text-[10px] mb-2">
                        <span className="font-bold">segment_id</span>
                        <span className="font-bold">{USE_BACKEND_STT ? 'Live (N/A)' : 'Live audio (ms)'}</span>
                        {[...profileEntries].reverse().slice(0, 20).map((e, i) => (
                          <React.Fragment key={`${e.segment_id}-${i}`}>
                            <span>{e.segment_id}</span>
                            <span>{USE_BACKEND_STT ? '—' : (e.latency_live_audio != null ? `${e.latency_live_audio}` : '—')}</span>
                          </React.Fragment>
                        ))}
                      </div>
                      {(() => {
                        if (USE_BACKEND_STT) return <div className="mt-2 pt-2 border-t border-gray-300 dark:border-gray-600 font-mono text-[10px]">Backend only — Live audio N/A.</div>;
                        const withLive = profileEntries.filter((e) => e.latency_live_audio != null);
                        if (withLive.length === 0) return null;
                        const avgLive = Math.round(withLive.reduce((s, e) => s + (e.latency_live_audio ?? 0), 0) / withLive.length);
                        return (
                          <div className="mt-2 pt-2 border-t border-gray-300 dark:border-gray-600 font-mono text-[10px]">
                            <div>Segments with Live audio: {withLive.length}</div>
                            <div>Live audio avg: {avgLive} ms</div>
                          </div>
                        );
                      })()}
                    </>
                  )}
                </section>
              )}
            </div>
          </div>
        </div>
      )}

      {sttDebugRow != null && showDebug && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60"
          role="dialog"
          aria-modal="true"
          aria-labelledby="stt-debug-title"
          onClick={() => { setSttDebugRowId(null); setSttDebugNemoSegments([]); }}
        >
          <div className="bg-white dark:bg-slate-900 border-2 border-gray-900 dark:border-gray-600 rounded-sm shadow-lg max-w-md w-full neo-brutal-shadow" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-3 py-2 border-b-2 border-gray-900 dark:border-gray-600 bg-sky-100 dark:bg-sky-900/30">
              <h2 id="stt-debug-title" className="font-mono text-xs font-bold uppercase text-sky-800 dark:text-sky-200">Voice ID scores (STT)</h2>
              <button type="button" onClick={() => { setSttDebugRowId(null); setSttDebugNemoSegments([]); }} className="font-mono text-xs font-bold px-2 py-1 rounded border border-gray-900 dark:border-gray-200 hover:bg-gray-200 dark:hover:bg-gray-700">Close</button>
            </div>
            <div className="p-3 font-mono text-[10px] md:text-xs text-gray-800 dark:text-gray-200 space-y-3 max-h-[70vh] overflow-y-auto">
              <div className="space-y-2 border-b-2 border-gray-300 dark:border-gray-600 pb-2">
                <div className="font-bold uppercase text-sky-700 dark:text-sky-300">Current Segment</div>
                <div><span className="opacity-80">segment_id:</span> <strong>{sttDebugRow.segmentId ?? '—'}</strong></div>
                <div><span className="opacity-80">timestamp:</span> <strong>{sttDebugRow.timestamp != null ? formatTime(sttDebugRow.timestamp) : '—'}</strong> <span className="opacity-70">({sttDebugRow.timestamp ?? '—'})</span></div>
                <div><span className="opacity-80">start_ms:</span> <strong>{sttDebugRow.start_ms != null ? sttDebugRow.start_ms : '—'}</strong></div>
                <div><span className="opacity-80">end_ms:</span> <strong>{sttDebugRow.end_ms != null ? sttDebugRow.end_ms : '—'}</strong></div>
                <div><span className="opacity-80">speaker_label:</span> <strong>{sttDebugRow.speakerLabel ?? '—'}</strong></div>
                <div><span className="opacity-80">speaker (display):</span> <strong>{sttDebugRow.speaker ?? '—'}</strong></div>
                {!hasSttV2Debug && (
                  <>
                    <div><span className="opacity-80">best_user_suffix:</span> <strong>{sttDebugRow.bestUserSuffix ?? '—'}</strong></div>
                    <div><span className="opacity-80">best_score_pct:</span> <strong>{typeof sttDebugRow.bestScorePct === 'number' ? `${sttDebugRow.bestScorePct}%` : '—'}</strong></div>
                    <div><span className="opacity-80">second_user_suffix:</span> <strong>{sttDebugRow.secondUserSuffix ?? '—'}</strong></div>
                    <div><span className="opacity-80">second_score_pct:</span> <strong>{typeof sttDebugRow.secondScorePct === 'number' ? `${sttDebugRow.secondScorePct}%` : '—'}</strong></div>
                    <div><span className="opacity-80">score_margin_pct:</span> <strong>{typeof sttDebugRow.scoreMarginPct === 'number' ? `${sttDebugRow.scoreMarginPct}%` : '—'}</strong></div>
                    {Array.isArray(sttDebugRow.allScores) && sttDebugRow.allScores.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-gray-300 dark:border-gray-600">
                        <div className="font-bold uppercase text-sky-700 dark:text-sky-300 mb-1">All cluster scores (known + unknown)</div>
                        <div className="space-y-0.5 text-[10px] max-h-32 overflow-y-auto">
                          {sttDebugRow.allScores.map((entry, i) => (
                            <div key={i} className="flex justify-between gap-2">
                              <span className="font-mono truncate" title={entry.label}>{entry.label}</span>
                              <strong>{entry.score_pct}%</strong>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {(sttDebugRow.speakerSource != null || sttDebugRow.nemoSpeakerId != null || sttDebugRow.speakerLabelBefore != null || sttDebugRow.speakerLabelAfter != null) && (
                      <>
                        <div className="font-bold uppercase text-sky-700 dark:text-sky-300 mt-2 pt-2 border-t border-gray-300 dark:border-gray-600">NeMo speaker label (debug)</div>
                        <div><span className="opacity-80">speaker_source:</span> <strong>{sttDebugRow.speakerSource ?? '—'}</strong></div>
                        <div><span className="opacity-80">nemo_speaker_id:</span> <strong>{sttDebugRow.nemoSpeakerId ?? '—'}</strong></div>
                        {(sttDebugRow.speakerLabelBefore != null || sttDebugRow.speakerLabelAfter != null) && (
                          <div><span className="opacity-80">speaker_label_change:</span> <strong>{String(sttDebugRow.speakerLabelBefore ?? '—')} → {String(sttDebugRow.speakerLabelAfter ?? '—')}</strong></div>
                        )}
                        {sttDebugRow.speakerChangeWordIndex != null && (
                          <div><span className="opacity-80">speaker_change_word_index:</span> <strong>{sttDebugRow.speakerChangeWordIndex}</strong></div>
                        )}
                        {sttDebugRow.speakerChangeWordIndex == null && sttDebugRow.speakerChangeAtMs != null && (
                          <div><span className="opacity-80">speaker_change_at_ms:</span> <strong>{sttDebugRow.speakerChangeAtMs}</strong></div>
                        )}
                      </>
                    )}
                  </>
                )}
              </div>
              {(() => {
                const v2Seg = sttDebugRow.sttV2Debug?.segmentation as Record<string, any> | null | undefined;
                const v2Speaker = sttDebugRow.sttV2Debug?.speaker as Record<string, any> | null | undefined;
                const hasSeg = v2Seg != null;
                const hasSpeaker =
                  v2Speaker != null
                  || sttDebugRow.sttV2LabelConf != null
                  || sttDebugRow.sttV2Coverage != null
                  || (sttDebugRow.sttV2Flags && Object.keys(sttDebugRow.sttV2Flags).length > 0);
                if (!hasSeg && !hasSpeaker) return null;
                const segParts = v2Seg && v2Seg.merged && Array.isArray(v2Seg.parts) ? v2Seg.parts : (v2Seg ? [v2Seg] : []);
                const coverageList = Array.isArray(v2Speaker?.coverage_by_label) ? v2Speaker.coverage_by_label : [];
                const intervalList = Array.isArray(v2Speaker?.intervals) ? v2Speaker.intervals : [];
                return (
                  <div className="space-y-2 border-b-2 border-gray-300 dark:border-gray-600 pb-2">
                    <div className="font-bold uppercase text-sky-700 dark:text-sky-300">STT v2 debug</div>
                    {hasSeg ? (
                      <div className="space-y-2">
                        <div className="font-semibold uppercase text-sky-600 dark:text-sky-300">Segmentation</div>
                        {segParts.map((seg, i) => {
                          const details = (seg?.details ?? {}) as Record<string, unknown>;
                          const segments = Array.isArray(seg?.segments) ? seg.segments : [];
                          const pauseMs = details.pause_ms as number | undefined;
                          const pauseConf = details.pause_conf as number | undefined;
                          const pauseSplitMs = details.pause_split_ms as number | undefined;
                          const maxChars = details.max_chars as number | undefined;
                          const currentChars = details.current_chars as number | undefined;
                          const maxSentenceMs = details.max_sentence_ms as number | undefined;
                          const durationMs = details.duration_ms as number | undefined;
                          const punct = details.punct as string | undefined;
                          return (
                            <div key={`seg-${i}`} className="pl-2 border-l-2 border-gray-300 dark:border-gray-600 space-y-1">
                              <div><span className="opacity-80">policy:</span> <strong>{seg?.policy ?? (seg?.merged ? 'merged' : '—')}</strong></div>
                              {(seg?.start_ms != null || seg?.end_ms != null) && (
                                <div><span className="opacity-80">range_ms:</span> <strong>{seg?.start_ms ?? '—'}–{seg?.end_ms ?? '—'}</strong></div>
                              )}
                              {pauseMs != null && (
                                <div><span className="opacity-80">pause_ms:</span> <strong>{pauseMs}</strong>{pauseConf != null && <span className="opacity-70"> (conf {pauseConf.toFixed(2)})</span>}{pauseSplitMs != null && <span className="opacity-70"> split {pauseSplitMs}ms</span>}</div>
                              )}
                              {punct && (
                                <div><span className="opacity-80">punctuation:</span> <strong>{punct}</strong></div>
                              )}
                              {maxChars != null && (
                                <div><span className="opacity-80">max_chars:</span> <strong>{maxChars}</strong>{currentChars != null && <span className="opacity-70"> (current {currentChars})</span>}</div>
                              )}
                              {maxSentenceMs != null && (
                                <div><span className="opacity-80">max_sentence_ms:</span> <strong>{maxSentenceMs}</strong>{durationMs != null && <span className="opacity-70"> (duration {durationMs})</span>}</div>
                              )}
                              {Array.isArray(segments) && segments.length > 0 && (
                                <div className="mt-1 pt-1 border-t border-gray-300 dark:border-gray-600">
                                  <div className="font-semibold opacity-90">STT segments</div>
                                  <div className="space-y-0.5">
                                    {segments.map((s: any, idx: number) => (
                                      <div key={`segpart-${i}-${idx}`} className="flex justify-between gap-2">
                                        <span className="opacity-80">{s.start_ms ?? '—'}–{s.end_ms ?? '—'}</span>
                                        <span className="truncate" title={String(s.text ?? '')}>{String(s.text ?? '')}</span>
                                        <span className="opacity-80">{s.conf != null ? s.conf.toFixed(2) : '—'}</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="text-[10px] opacity-80">No v2 segmentation debug for this bubble.</div>
                    )}
                    {hasSpeaker ? (
                      <div className="space-y-2">
                        <div className="font-semibold uppercase text-sky-600 dark:text-sky-300">Speaker decision</div>
                        <div><span className="opacity-80">decision:</span> <strong>{v2Speaker?.decision ?? '—'}</strong></div>
                        <div><span className="opacity-80">label_conf:</span> <strong>{sttDebugRow.sttV2LabelConf ?? v2Speaker?.label_conf ?? '—'}</strong></div>
                        <div><span className="opacity-80">coverage_ratio:</span> <strong>{sttDebugRow.sttV2Coverage ?? v2Speaker?.coverage_ratio ?? '—'}</strong></div>
                        {sttDebugRow.sttV2Flags && Object.keys(sttDebugRow.sttV2Flags).length > 0 && (
                          <div><span className="opacity-80">flags:</span> <strong>{Object.entries(sttDebugRow.sttV2Flags).map(([k, v]) => `${k}=${v}`).join(', ')}</strong></div>
                        )}
                        {(v2Speaker?.overlap_ratio != null || v2Speaker?.uncertain_ratio != null || v2Speaker?.dominant_ratio != null) && (
                          <div className="opacity-80">
                            overlap {v2Speaker?.overlap_ratio ?? '—'} | uncertain {v2Speaker?.uncertain_ratio ?? '—'} | dominant {v2Speaker?.dominant_ratio ?? '—'}
                          </div>
                        )}
                        {Array.isArray(coverageList) && coverageList.length > 0 && (
                          <div className="mt-1 pt-1 border-t border-gray-300 dark:border-gray-600">
                            <div className="font-semibold opacity-90">Coverage by label</div>
                            <div className="space-y-0.5">
                              {coverageList.map((entry: any, idx: number) => (
                                <div key={`cov-${idx}`} className="flex justify-between gap-2">
                                  <span className="truncate" title={String(entry.label ?? '')}>{String(entry.label ?? '')}</span>
                                  <span className="opacity-80">{entry.ratio != null ? entry.ratio.toFixed(3) : '—'}</span>
                                  <span className="opacity-80">{entry.conf_avg != null ? entry.conf_avg.toFixed(2) : '—'}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {Array.isArray(intervalList) && intervalList.length > 0 && (
                          <div className="mt-1 pt-1 border-t border-gray-300 dark:border-gray-600">
                            <div className="font-semibold opacity-90">Diarization intervals</div>
                            <div className="space-y-0.5">
                              {intervalList.map((entry: any, idx: number) => (
                                <div key={`int-${idx}`} className="flex justify-between gap-2">
                                  <span className="opacity-80">{entry.start_ms ?? '—'}–{entry.end_ms ?? '—'}</span>
                                  <span className="truncate" title={String(entry.label ?? '')}>{String(entry.label ?? '')}</span>
                                  <span className="opacity-80">{entry.conf != null ? entry.conf.toFixed(2) : '—'}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {(() => {
                          const voiceId = v2Speaker && 'voice_id' in v2Speaker ? (v2Speaker as { voice_id?: { label?: string; reason?: string; candidate_similarities?: Array<{ label: string; score_pct: number }> } }).voice_id : undefined;
                          if (!voiceId) return null;
                          const candidates = Array.isArray(voiceId.candidate_similarities) ? voiceId.candidate_similarities : [];
                          return (
                            <div className="mt-1 pt-1 border-t border-gray-300 dark:border-gray-600">
                              <div className="font-semibold opacity-90">Voice ID (embedding match)</div>
                              <div><span className="opacity-80">chosen:</span> <strong>{voiceId.label ?? '—'}</strong> <span className="opacity-70">({voiceId.reason ?? '—'})</span></div>
                              {candidates.length > 0 && (
                                <div className="mt-1 pt-1 border-t border-gray-300 dark:border-gray-600">
                                  <div className="font-semibold opacity-90">Speaker embedding similarity (all candidates)</div>
                                  <div className="space-y-0.5 text-[10px] max-h-32 overflow-y-auto">
                                    {candidates.map((entry: { label: string; score_pct: number }, i: number) => (
                                      <div key={i} className="flex justify-between gap-2">
                                        <span className="font-mono truncate" title={entry.label}>{entry.label}</span>
                                        <strong>{entry.score_pct}%</strong>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })()}
                      </div>
                    ) : (
                      <div className="text-[10px] opacity-80">No v2 speaker debug for this bubble.</div>
                    )}
                  </div>
                );
              })()}
              {!hasSttV2Debug && (
                <div className="space-y-2 border-b-2 border-gray-300 dark:border-gray-600 pb-2">
                  <div className="font-bold uppercase text-sky-700 dark:text-sky-300">NeMo diarization segments (this bubble, snapshot)</div>
                  {(sttDebugRow.start_ms == null || sttDebugRow.end_ms == null) ? (
                    <div className="text-[10px] opacity-80">No timing for this bubble; cannot match NeMo segments.</div>
                  ) : sttDebugNemoSegments.length === 0 ? (
                    <div className="text-[10px] opacity-80">No matching segments for this bubble.</div>
                  ) : (
                    <div className="space-y-1 text-[10px]">
                      {sttDebugNemoSegments.map((seg, i) => (
                        <div key={i} className="flex gap-2">
                          <span><span className="opacity-80">start_s:</span> <strong>{seg.start_s.toFixed(2)}</strong></span>
                          <span><span className="opacity-80">end_s:</span> <strong>{seg.end_s.toFixed(2)}</strong></span>
                          <span><span className="opacity-80">speaker_id:</span> <strong>{seg.speaker_id}</strong></span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {(() => {
                const unknownClusters = new Map<string, { count: number; bestScorePct: number[]; secondScorePct: number[]; scoreMarginPct: number[]; bestUserSuffix: Set<string>; secondUserSuffix: Set<string> }>();
                for (const t of transcripts) {
                  const label = t.speakerLabel ?? t.speaker;
                  if (label && /^Unknown(_\d+)?$/i.test(label)) {
                    const key = label;
                    if (!unknownClusters.has(key)) {
                      unknownClusters.set(key, { count: 0, bestScorePct: [], secondScorePct: [], scoreMarginPct: [], bestUserSuffix: new Set(), secondUserSuffix: new Set() });
                    }
                    const cluster = unknownClusters.get(key)!;
                    cluster.count++;
                    if (typeof t.bestScorePct === 'number') cluster.bestScorePct.push(t.bestScorePct);
                    if (typeof t.secondScorePct === 'number') cluster.secondScorePct.push(t.secondScorePct);
                    if (typeof t.scoreMarginPct === 'number') cluster.scoreMarginPct.push(t.scoreMarginPct);
                    if (t.bestUserSuffix) cluster.bestUserSuffix.add(t.bestUserSuffix);
                    if (t.secondUserSuffix) cluster.secondUserSuffix.add(t.secondUserSuffix);
                  }
                }
                const sortedClusters = Array.from(unknownClusters.entries()).sort((a, b) => {
                  const numA = /^Unknown_(\d+)$/i.exec(a[0])?.[1] ? parseInt(/^Unknown_(\d+)$/i.exec(a[0])![1], 10) : 0;
                  const numB = /^Unknown_(\d+)$/i.exec(b[0])?.[1] ? parseInt(/^Unknown_(\d+)$/i.exec(b[0])![1], 10) : 0;
                  return numA - numB;
                });
                if (sortedClusters.length === 0) return null;
                return (
                  <div className="space-y-2 border-t-2 border-gray-300 dark:border-gray-600 pt-2">
                    <div className="font-bold uppercase text-sky-700 dark:text-sky-300">Unknown Speaker Clusters</div>
                    {sortedClusters.map(([label, stats]) => {
                      const avgBest = stats.bestScorePct.length > 0 ? Math.round(stats.bestScorePct.reduce((s, v) => s + v, 0) / stats.bestScorePct.length) : null;
                      const avgSecond = stats.secondScorePct.length > 0 ? Math.round(stats.secondScorePct.reduce((s, v) => s + v, 0) / stats.secondScorePct.length) : null;
                      const avgMargin = stats.scoreMarginPct.length > 0 ? Math.round(stats.scoreMarginPct.reduce((s, v) => s + v, 0) / stats.scoreMarginPct.length) : null;
                      const bestSuffixes = Array.from(stats.bestUserSuffix);
                      const secondSuffixes = Array.from(stats.secondUserSuffix);
                      return (
                        <div key={label} className="pl-2 border-l-2 border-gray-300 dark:border-gray-600 space-y-1">
                          <div className="font-semibold">{formatUnknownSpeakerDisplay(label)} <span className="opacity-70">({stats.count} segment{stats.count !== 1 ? 's' : ''})</span></div>
                          <div className="pl-2 space-y-0.5 text-[9px] opacity-90">
                            {avgBest != null && <div>Avg best: <strong>{avgBest}%</strong> {bestSuffixes.length > 0 && <span className="opacity-70">({bestSuffixes.join(', ')})</span>}</div>}
                            {avgSecond != null && <div>Avg 2nd: <strong>{avgSecond}%</strong> {secondSuffixes.length > 0 && <span className="opacity-70">({secondSuffixes.join(', ')})</span>}</div>}
                            {avgMargin != null && <div>Avg margin: <strong>{avgMargin}%</strong></div>}
                            {stats.bestScorePct.length > 0 && <div className="opacity-70">Range: {Math.min(...stats.bestScorePct)}%–{Math.max(...stats.bestScorePct)}%</div>}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                );
              })()}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
