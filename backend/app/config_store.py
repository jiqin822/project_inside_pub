"""Config store: config file (master over env) + pushable overrides."""
import json
import logging
import threading
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


def _read_config_file(path: Path) -> dict[str, Any]:
    """Read YAML or JSON config file to a flat dict. Returns {} on error."""
    if not path.exists():
        logger.debug("Config file not found: %s (optional; using env/defaults)", path)
        return {}
    try:
        raw = path.read_text()
    except OSError as e:
        logger.warning("Could not read config file %s: %s", path, e)
        return {}
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        if not _HAS_YAML:
            logger.warning("YAML config file requested but pyyaml not installed; skipping file")
            return {}
        try:
            data = yaml.safe_load(raw)
        except yaml.YAMLError as e:
            logger.warning("Invalid YAML in %s: %s", path, e)
            return {}
    elif suffix == ".json":
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON in %s: %s", path, e)
            return {}
    else:
        logger.warning("Config file must be .yaml, .yml, or .json: %s", path)
        return {}
    if not isinstance(data, dict):
        logger.warning("Config file must contain a dict; got %s", type(data).__name__)
        return {}
    return data


def _env_dict(SettingsCls: type) -> dict[str, Any]:
    """Build dict from env/.env using Pydantic (env-only load)."""
    return SettingsCls().model_dump()


class ConfigStore:
    """
    Holds config from env, optional config file (master over env), and push overrides.
    Precedence: push overrides > config file > env > defaults.
    """

    def __init__(self, SettingsCls: type, config_file_path: Optional[str] = None):
        self._SettingsCls = SettingsCls
        self._file_path: Optional[Path] = None
        if config_file_path:
            self._file_path = Path(config_file_path).expanduser().resolve()
        self._overrides: dict[str, Any] = {}
        self._current: Optional[Any] = None  # Settings instance
        self._lock = threading.RLock()

    def load_initial(self) -> None:
        """Build settings: env, then file (overwrites env), then overrides. Call once at startup."""
        with self._lock:
            env_dict = _env_dict(self._SettingsCls)
            file_dict: dict[str, Any] = {}
            if self._file_path:
                file_dict = _read_config_file(self._file_path)
                if file_dict:
                    logger.info("Loaded config file (master over env): %s", self._file_path)
            merged = {**env_dict, **file_dict, **self._overrides}
            self._current = self._SettingsCls(**merged)

    def get_settings(self) -> Any:
        """Return current Settings instance. If not yet loaded, load_initial() first."""
        with self._lock:
            if self._current is None:
                self.load_initial()
            return self._current

    def update(self, overrides: dict[str, Any]) -> None:
        """Merge overrides into in-memory overrides and rebuild Settings. Keeps previous on validation error."""
        with self._lock:
            if self._current is None:
                self.load_initial()
            try:
                merged = {**self._current.model_dump(), **self._overrides, **overrides}
                self._current = self._SettingsCls(**merged)
                self._overrides.update(overrides)
            except Exception as e:
                logger.warning("Config update validation failed; keeping previous config: %s", e)

    def reload_from_file(self) -> None:
        """Re-read config file and apply saved overrides. File remains master over env."""
        with self._lock:
            env_dict = _env_dict(self._SettingsCls)
            file_dict = _read_config_file(self._file_path) if self._file_path else {}
            merged = {**env_dict, **file_dict, **self._overrides}
            try:
                self._current = self._SettingsCls(**merged)
            except Exception as e:
                logger.warning("Config reload validation failed; keeping previous config: %s", e)

    def clear_overrides(self) -> None:
        """Drop pushed overrides and reset to file (master) + env."""
        with self._lock:
            self._overrides.clear()
            if self._current is not None:
                env_dict = _env_dict(self._SettingsCls)
                file_dict = _read_config_file(self._file_path) if self._file_path else {}
                self._current = self._SettingsCls(**{**env_dict, **file_dict})
