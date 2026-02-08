import numpy as np

from app.api.stt_v2.nemo_diarization_service import NemoDiarizationService
from app.domain.stt_v2.contracts import AudioWindow, DiarFrame, DiarPatch, TimeRangeSamples


def _window(stream_id: str, start: int, end: int, sr: int, amp: int) -> AudioWindow:
    pcm = (np.ones(end - start, dtype=np.int16) * amp)
    return AudioWindow(
        stream_id=stream_id,
        range_samples=TimeRangeSamples(start=start, end=end, sr=sr),
        pcm16_np=pcm,
    )


def test_fallback_diarize_emits_frames_and_patch():
    service = NemoDiarizationService(
        preview_mode=True,
        patch_window_s=1.0,
        patch_emit_s=0.1,
        energy_threshold=0.0001,
    )
    service._available = False

    window = _window("s1", 0, 16000, 16000, amp=1000)
    outputs = service.process_window(window)

    frames = [item for item in outputs if isinstance(item, DiarFrame)]
    patches = [item for item in outputs if isinstance(item, DiarPatch)]

    assert frames, "Expected diarization frames from fallback"
    assert patches, "Expected a patch when patch_emit_s is satisfied"
    assert patches[0].frames, "Patch should include at least one frame"
    assert all(frame.is_patch for frame in patches[0].frames)
