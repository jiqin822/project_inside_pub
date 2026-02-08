"""Real-time coaching analysis engine."""
from typing import Optional
from app.settings import settings


class RealtimeCoachingEngine:
    """Real-time coaching engine (rule-based)."""

    def __init__(self):
        # Use SR_THRESHOLD and OR_THRESHOLD from settings (defaults from env)
        self.sr_threshold = getattr(settings, 'sr_threshold', 2.0)
        self.or_threshold = getattr(settings, 'or_threshold', 0.25)

    def analyze_feature_frame(
        self, speaking_rate: float, overlap_ratio: float
    ) -> Optional[dict[str, any]]:
        """
        Analyze a feature frame and return nudge if needed.
        Returns None if no nudge needed, or dict with nudge info.
        
        Rules:
        - If speaking_rate > SR_THRESHOLD -> SLOW_DOWN nudge
        - If overlap_ratio > OR_THRESHOLD -> PAUSE nudge
        """
        nudge_type = None
        message = None
        intensity = 1

        if speaking_rate > self.sr_threshold:
            nudge_type = "SLOW_DOWN"
            message = "Try slowing down."
            intensity = min(3, max(1, int((speaking_rate - self.sr_threshold) * 2)))

        if overlap_ratio > self.or_threshold:
            # If both conditions met, prefer PAUSE
            nudge_type = "PAUSE"
            message = "Consider pausing to let the other person speak."
            intensity = min(3, max(1, int((overlap_ratio - self.or_threshold) * 10)))

        if nudge_type:
            return {
                "nudge_type": nudge_type,
                "intensity": intensity,
                "message": message,
            }

        return None
