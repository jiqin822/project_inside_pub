"""Application settings and configuration."""
import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config_store import ConfigStore


def _default_app_public_url() -> str:
    """Use APP_PUBLIC_URL if set; else VITE_API_BASE_URL or VITE_API_URL (same app origin as frontend)."""
    return (
        os.environ.get("APP_PUBLIC_URL")
        or os.environ.get("VITE_API_BASE_URL")
        or os.environ.get("VITE_API_URL")
        or "http://localhost:3000"
    )


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields (like old speaking_rate_threshold)
    )

    # App
    app_name: str = "Project Inside API"
    app_version: str = "0.1.0"
    debug: bool = False
    api_v1_prefix: str = "/v1"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/project_inside"
    database_echo: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_queue_url: str = "redis://localhost:6379/1"

    # Security
    secret_key: str = "change-me-in-production-use-env-var"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # CORS
    cors_origins: list[str] = ["http://localhost:*", "http://127.0.0.1:*", "http://192.168.*.*:*"]

    # WebSocket
    websocket_heartbeat_interval: int = 30
    websocket_timeout: int = 60

    # Rate limiting
    nudge_rate_limit_seconds: int = 10

    # Realtime engine thresholds (from env: SR_THRESHOLD, OR_THRESHOLD)
    # Support both old and new env var names for backward compatibility
    sr_threshold: float = 2.0  # SR_THRESHOLD (or SPEAKING_RATE_THRESHOLD for backward compat)
    or_threshold: float = 0.25  # OR_THRESHOLD (or OVERLAP_RATIO_THRESHOLD for backward compat)
    
    # Store feature frames (from env: STORE_FRAMES)
    store_frames: bool = False  # STORE_FRAMES

    # Email / invite links (fallback to VITE_API_BASE_URL so one env var can serve both frontend and backend)
    app_public_url: str = Field(default_factory=_default_app_public_url)
    email_blocked_domains: str = ""  # Comma-separated in env, parsed as list via property
    sendgrid_api_key: str = ""  # SendGrid API key for email sending
    email_from_address: str = "noreply@projectinside.app"  # From email address
    email_from_name: str = "Project Inside"  # From name
    
    # Voiceprint API
    voiceprint_api_url: str = "http://localhost:8005"
    voiceprint_api_token: str = ""  # Will be read from voiceprint-api config
    
    # Compass: threshold of unprocessed events before consolidation runs
    compass_consolidation_threshold: int = 5

    # Gemini API (for Love Maps quiz generation)
    gemini_api_key: str = ""  # Google Generative AI API key
    # Default model for text-from-text generation (e.g. analyze-turn, activity recommendations)
    llm_default_text_model: str = "gemini-2.0-flash"
    llm_backup_text_model: str = "gemini-2.5-flash"

    # Default image model (provider inferred from name: gpt-* -> OpenAI, gemini-* -> Gemini)
    llm_default_image_model: str = "gpt-image-1"
    # Image size and quality (used when model is OpenAI-type, e.g. gpt-image-1)
    llm_default_image_size: str = "1024x1024"
    llm_default_image_quality: str = "low"

    # OpenAI API (scrapbook sticker image generation via GPT Image / gpt-image-1)
    openai_api_key: str = ""  # OpenAI API key for images.generate

    # Push notifications (FCM)
    push_enabled: bool = False  # Set True when GOOGLE_APPLICATION_CREDENTIALS is set
    google_application_credentials: str = ""  # Path to Firebase service account JSON (optional; can use env GOOGLE_APPLICATION_CREDENTIALS)
    google_application_credentials_json: str = ""  # Full JSON or base64-encoded JSON (PaaS; .env does not set os.environ, so we sync to os.environ at startup)

    # GCP STT v2
    stt_recognizer: str = "projects/940733179670/locations/us/recognizers/livecoach"
    stt_speaker_match_threshold: float = 0.3  # ECAPA-TDNN; 30% cosine similarity to attribute speaker
    stt_speaker_match_margin: float = 0.03  # ECAPA-TDNN 192-dim embeddings
    stt_prefer_known_over_unknown_gap: float = 0.03  # only attribute to unknown when unknown is at least this much better than best known (0–1)
    stt_audio_buffer_seconds: int = 30
    stt_escalation_cooldown_seconds: int = 5
    # Optional NeMo diarization fallback (used when Google streaming diarization is unavailable, e.g. language_code=auto/chirp_3)
    # STT NeMo Diarization Fallback settings:
    # - stt_enable_nemo_diarization_fallback:
    #     If True, enables the NeMo-based speaker diarization fallback when Google streaming diarization is unavailable.
    stt_enable_nemo_diarization_fallback: bool = True

    # - stt_nemo_diarization_window_s:
    #     The window size in seconds for NeMo diarization analysis (i.e., each chunk of audio analyzed for speaker changes).
    stt_nemo_diarization_window_s: float = 1.6

    # - stt_nemo_diarization_hop_s:
    #     The hop size in seconds for sliding the analysis window across the input audio.
    #     This determines how often the diarization runs (lower = more frequent, greater overlap; higher = faster but more lag).
    stt_nemo_diarization_hop_s: float = 0.4

    # - stt_nemo_diarization_timeout_s:
    #     Maximum time in seconds to wait for the NeMo diarization response before considering it timed out or failed.
    stt_nemo_diarization_timeout_s: float = 4.0

    # - stt_nemo_diarization_max_speakers:
    #     The maximum number of speakers that NeMo diarization will attempt to identify in the audio stream.
    stt_nemo_diarization_max_speakers: int = 4
    # Diarization reliable horizon: only resolve speakers for segments ending before now_sample - L (ms).
    # Sortformer output lags; L typically 500–1500 ms depending on chunking.
    stt_diarization_reliable_lag_ms: int = 2200

    # Streaming diarization worker settings
    # Maximum backlog in seconds before trimming (prevents latency spiral)
    stt_diarization_max_backlog_s: float = 5.0
    # Gap threshold in seconds to trigger streaming state reset (mobile hiccups)
    stt_diarization_gap_reset_s: float = 2.5
    # Hysteresis: require K consecutive frames before switching speakers
    stt_diarization_hysteresis_k: int = 7
    # Overlap / uncertainty detection thresholds for streaming timeline
    stt_diarization_overlap_min_conf: float = 0.55
    stt_diarization_overlap_margin: float = 0.15

    # STT V2 (Diart + Chirp3) configuration. diart=Diart diarization; nemo=NeMo streaming; none=no diarization (no model loaded).
    stt_v2_diar_backend: str = "diart"
    stt_v2_audio_buffer_seconds: int = 120
    stt_v2_frame_ms: int = 20
    stt_v2_diar_window_s: float = 1.6
    stt_v2_diar_hop_s: float = 0.4
    stt_v2_vad_frame_ms: int = 20
    stt_v2_vad_hangover_ms: int = 300
    stt_v2_pause_split_ms: int = 280  # Very short silence → new sentence (very aggressive boundaries)
    stt_v2_pause_merge_ms: int = 120
    stt_v2_min_turn_ms: int = 800
    stt_v2_switch_confirm_ms: int = 160
    stt_v2_cooldown_ms: int = 600
    stt_v2_switch_margin: float = 0.08
    stt_v2_stt_jitter_buffer_ms: int = 300
    stt_v2_max_sentence_ms: int = 3200  # Break long utterances sooner
    stt_v2_max_chars: int = 90  # Break on length sooner
    stt_v2_min_chars: int = 5  # Allow shorter fragments
    stt_v2_dominant_sentence_th: float = 0.75
    stt_v2_overlap_sentence_th: float = 0.20
    stt_v2_uncertain_sentence_th: float = 0.30
    stt_v2_stitch_gap_ms: int = 900  # Merge consecutive same-speaker segments with gap up to 900 ms
    stt_v2_max_stitched_ms: int = 15000  # Allow longer merged same-speaker runs
    stt_v2_min_nudge_sentence_ms: int = 800
    stt_v2_diar_live_zone_ms: int = 2000
    stt_v2_diar_refine_zone_ms: int = 10000
    stt_v2_diar_commit_zone_ms: int = 10000
    stt_v2_diar_min_segment_ms: int = 400
    stt_v2_diar_commit_conf_th: float = 0.9
    stt_v2_patch_window_ms: int = 20000
    stt_v2_patch_emit_s: float = 2.0
    stt_v2_timeline_max_minutes: int = 10
    stt_v2_audio_queue_max: int = 50
    stt_v2_frame_queue_max: int = 200
    stt_v2_window_queue_max: int = 50
    stt_v2_diar_queue_max: int = 200
    stt_v2_stt_queue_max: int = 200
    stt_v2_debug_bundle_enabled: bool = False
    stt_v2_debug_bundle_dir: str = "backend/.debug/stt_v2"
    stt_v2_shadow_mode: bool = False

    # Session-end voice centroid: update user voice profile with centroid of segment embeddings attributed to them
    stt_update_voice_centroid_after_session: bool = True
    stt_voice_centroid_min_segments: int = 2  # only update if user has at least this many segments
    stt_voice_centroid_blend_alpha: float = 0.3  # new = (1 - alpha) * old + alpha * centroid; 1.0 = replace
    stt_voice_centroid_max_segments_per_user: int = 50  # cap per-user list to bound memory

    # GCP Speech-to-Text (Realtime STT)
    gcp_project_id: str = ""
    gcp_stt_location: str = "global"
    gcp_stt_recognizer: str = ""  # Optional full recognizer path
    gcp_stt_language_code: str = "en-US"
    stt_min_speakers: int = 1
    stt_max_speakers: int = 2
    stt_escalation_cooldown_seconds: int = 5
    
    @property
    def email_blocked_domains_list(self) -> list[str]:
        """Parse email_blocked_domains from env."""
        if not self.email_blocked_domains:
            return []
        return [d.strip() for d in self.email_blocked_domains.split(",") if d.strip()]


# Config file path: CONFIG_FILE env or default backend/config.yaml (config file is master over env)
_config_file = os.environ.get("CONFIG_FILE") or str(
    Path(__file__).resolve().parent.parent / "config.yaml"
)
_config_store = ConfigStore(Settings, _config_file)
_config_store.load_initial()


class _SettingsProxy:
    """Proxy so 'settings.attr' always returns current value from config store (push/reload safe)."""

    def __getattr__(self, name: str):
        return getattr(_config_store.get_settings(), name)


settings: Settings = _SettingsProxy()  # type: ignore[assignment]


def get_settings() -> Settings:
    """Return current Settings snapshot (use after push/reload for latest values)."""
    return _config_store.get_settings()


def get_config_store() -> ConfigStore:
    """Return the config store for update(), reload_from_file(), clear_overrides()."""
    return _config_store
