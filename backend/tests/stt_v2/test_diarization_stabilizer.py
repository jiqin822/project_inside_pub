from app.api.stt_v2.diarization_stabilizer import DiarizationStabilizer
from app.domain.stt_v2.contracts import DiarFrame, TimeRangeSamples, UNCERTAIN_LABEL


def _frame(start: int, end: int, sr: int, label: str, conf: float = 0.8) -> DiarFrame:
    return DiarFrame(
        range_samples=TimeRangeSamples(start=start, end=end, sr=sr),
        label=label,
        conf=conf,
        is_patch=False,
    )


def test_live_zone_marks_uncertain():
    sr = 16000
    stabilizer = DiarizationStabilizer(
        sample_rate=sr,
        live_zone_ms=2000,
        refine_zone_ms=10000,
        commit_zone_ms=10000,
        min_segment_ms=0,
        commit_conf_th=0.9,
        switch_confirm_ms=160,
        switch_margin=0.08,
    )
    now_sample = sr * 5
    frame = _frame(now_sample - sr, now_sample - (sr // 2), sr, "spkA", 0.8)
    outputs = stabilizer.stabilize_outputs([frame], now_sample)
    assert outputs
    assert outputs[0].label == UNCERTAIN_LABEL


def test_committed_zone_freezes_low_conf_switch():
    sr = 16000
    stabilizer = DiarizationStabilizer(
        sample_rate=sr,
        live_zone_ms=2000,
        refine_zone_ms=10000,
        commit_zone_ms=10000,
        min_segment_ms=0,
        commit_conf_th=0.9,
        switch_confirm_ms=160,
        switch_margin=0.08,
    )
    now_sample = sr * 20
    refine_frame = _frame(now_sample - (sr * 6), now_sample - (sr * 5), sr, "spkA", 0.8)
    outputs1 = stabilizer.stabilize_outputs([refine_frame], now_sample)
    assert outputs1
    stable_label = outputs1[0].label

    committed_frame = _frame(
        now_sample - (sr * 16), now_sample - (sr * 15), sr, "spkB", 0.2
    )
    outputs2 = stabilizer.stabilize_outputs([committed_frame], now_sample)
    assert outputs2
    assert outputs2[0].label == stable_label


def test_min_segment_merges_short_segment():
    sr = 16000
    stabilizer = DiarizationStabilizer(
        sample_rate=sr,
        live_zone_ms=2000,
        refine_zone_ms=10000,
        commit_zone_ms=10000,
        min_segment_ms=400,
        commit_conf_th=0.9,
        switch_confirm_ms=160,
        switch_margin=0.08,
    )
    now_sample = sr * 5
    frames = [
        _frame(0, int(sr * 0.5), sr, "spkA", 0.8),
        _frame(int(sr * 0.5), int(sr * 0.6), sr, "spkB", 0.8),
        _frame(int(sr * 0.6), int(sr * 1.1), sr, "spkA", 0.8),
    ]
    outputs = stabilizer.stabilize_outputs(frames, now_sample)
    labels = [item.label for item in outputs if isinstance(item, DiarFrame)]
    assert "spk1" not in labels
