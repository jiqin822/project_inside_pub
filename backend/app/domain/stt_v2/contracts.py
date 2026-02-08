"""STT V2 domain contracts and time primitives."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

StreamId = str
SampleIndex = int


@dataclass(frozen=True)
class TimeRangeSamples:
    start: SampleIndex
    end: SampleIndex
    sr: int

    @property
    def duration_samples(self) -> int:
        return max(0, self.end - self.start)

    @property
    def duration_ms(self) -> int:
        if self.sr <= 0:
            return 0
        return int((self.duration_samples * 1000) / self.sr)


@dataclass(frozen=True)
class TimeRangeMs:
    start_ms: int
    end_ms: int

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)


@dataclass(frozen=True)
class AudioChunk:
    stream_id: StreamId
    range_samples: TimeRangeSamples
    pcm16_bytes: bytes


@dataclass(frozen=True)
class AudioFrame:
    stream_id: StreamId
    range_samples: TimeRangeSamples
    pcm16_np: np.ndarray


@dataclass(frozen=True)
class AudioWindow:
    stream_id: StreamId
    range_samples: TimeRangeSamples
    pcm16_np: np.ndarray


@dataclass(frozen=True)
class SpeechRegion:
    range_samples: TimeRangeSamples
    vad_conf: float


@dataclass(frozen=True)
class PauseEvent:
    range_samples: TimeRangeSamples
    pause_ms: int
    conf: float


DiarLabel = str
OVERLAP_LABEL: DiarLabel = "OVERLAP"
UNCERTAIN_LABEL: DiarLabel = "UNCERTAIN"


@dataclass(frozen=True)
class DiarFrame:
    range_samples: TimeRangeSamples
    label: DiarLabel
    conf: float
    is_patch: bool = False


@dataclass(frozen=True)
class DiarPatch:
    range_samples: TimeRangeSamples
    frames: List[DiarFrame]
    version: int


@dataclass(frozen=True)
class SttSegment:
    range_ms: TimeRangeMs
    text: str
    stt_conf: float
    is_final: bool


@dataclass(frozen=True)
class UiSentence:
    id: str
    range_ms: TimeRangeMs
    text: str
    is_final: bool = True
    segments: Optional[List["UiSentenceSegment"]] = None
    debug: Optional[Dict[str, Any]] = None
    ui_context: Optional[Dict[str, Any]] = None
    split_from: Optional[str] = None


@dataclass(frozen=True)
class UiSentenceSegment:
    range_ms: TimeRangeMs
    text: str
    stt_conf: float
    is_final: bool


@dataclass(frozen=True)
class SpeakerSentence:
    ui_sentence: UiSentence
    label: DiarLabel
    label_conf: float
    coverage: float
    flags: Dict[str, bool] = field(default_factory=dict)
    audio_segment_base64: Optional[str] = None
    debug: Optional[Dict[str, Any]] = None
    speaker_color: Optional[str] = None
