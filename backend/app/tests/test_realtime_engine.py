"""Real-time engine tests."""
from app.domain.coach.analyzers.realtime_engine import RealtimeCoachingEngine


def test_realtime_engine_slow_down():
    """Test realtime engine detects slow down nudge."""
    engine = RealtimeCoachingEngine()
    
    # High speaking rate should trigger SLOW_DOWN
    nudge = engine.analyze_feature_frame(speaking_rate=4.0, overlap_ratio=0.1)
    assert nudge is not None
    assert nudge["nudge_type"] == "SLOW_DOWN"
    assert "message" in nudge


def test_realtime_engine_pause():
    """Test realtime engine detects pause nudge."""
    engine = RealtimeCoachingEngine()
    
    # High overlap ratio should trigger PAUSE
    nudge = engine.analyze_feature_frame(speaking_rate=2.0, overlap_ratio=0.5)
    assert nudge is not None
    assert nudge["nudge_type"] == "PAUSE"
    assert "message" in nudge


def test_realtime_engine_no_nudge():
    """Test realtime engine doesn't nudge for normal values."""
    engine = RealtimeCoachingEngine()
    
    # Normal values should not trigger nudge
    nudge = engine.analyze_feature_frame(speaking_rate=2.0, overlap_ratio=0.1)
    assert nudge is None
