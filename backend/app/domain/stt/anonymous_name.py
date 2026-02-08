"""Generate stable, human-friendly names for unknown speakers (e.g. 'Atlas Ridge' or 'Cedar Nimbus 0042')."""
from __future__ import annotations

import hashlib
import re
import secrets
from typing import Optional

_WORDS = [
    "Beacon", "Harbor", "Atlas", "Cedar", "Quartz", "Nimbus", "Ridge", "Orbit",
    "Juniper", "Saffron", "Echo", "Delta", "Nova", "Lumen", "Vertex", "Cobalt",
    "Canyon", "Ember", "Solstice", "Keystone", "Mosaic", "Aurora", "Crescent",
]

_UNKNOWN_N_PATTERN = re.compile(r"^Unknown_(\d+)$", re.IGNORECASE)
_ANON_N_PATTERN = re.compile(r"^Anon_(\d+)$", re.IGNORECASE)
_UNKNOWN_SPK_PATTERN = re.compile(r"^Unknown_spk_(\d+)$", re.IGNORECASE)
_SPK_PATTERN = re.compile(r"^spk_(\d+)$", re.IGNORECASE)


def anonymous_name(seed: Optional[str] = None) -> str:
    """
    Returns e.g. 'Atlas Ridge' or 'Cedar Nimbus 0042'
    - seed=None => random
    - seed='...' => stable/deterministic
    """
    if seed is None:
        w1, w2 = secrets.choice(_WORDS), secrets.choice(_WORDS)
        return f"{w1} {w2}"

    d = hashlib.blake2b(seed.encode("utf-8"), digest_size=8).digest()
    w1 = _WORDS[d[0] % len(_WORDS)]
    w2 = _WORDS[d[1] % len(_WORDS)]
    num = int.from_bytes(d[2:4], "big") % 10_000
    return f"{w1} {w2} {num:04d}"


def unknown_speaker_display_name(session_id: str, internal_label: str) -> str:
    """
    Map internal unknown speaker label to a stable display name for the client.
    - Unknown_N => anonymous_name(seed=session_id + '_' + N)
    - Any other label (user id, 'Unknown', etc.) => returned as-is.
    """
    if not internal_label:
        display_label = internal_label
        label_kind = {"kind": "empty"}
    else:
        m = _UNKNOWN_N_PATTERN.match(internal_label)
        if m:
            n = m.group(1)
            display_label = anonymous_name(seed=f"{session_id}_{n}")
            label_kind = {"kind": "unknown_n", "n": int(n)}
        else:
            lower = internal_label.lower()
            if lower.startswith("anon_"):
                suffix = internal_label.split("_", 1)[1] if "_" in internal_label else ""
                label_kind = (
                    {"kind": "anon_n", "n": int(suffix)}
                    if suffix.isdigit()
                    else {"kind": "anon_pref"}
                )
            elif lower.startswith("unknown_"):
                suffix = internal_label.split("_", 1)[1] if "_" in internal_label else ""
                label_kind = {"kind": "unknown_pref", "suffix": suffix[:32]}
            else:
                label_kind = {"kind": "other", "len": len(internal_label)}
            display_label = internal_label
    return display_label


def speaker_display_name(
    session_id: str, internal_label: str, *, nemo_speaker_id: Optional[str] = None
) -> str:
    """
    Unified display name for unknown/anonymous speakers across sources.
    - Unknown_N => stable anonymous_name (existing behavior)
    - Anon_N => stable anonymous_name
    - Unknown_spk_N / spk_N (NeMo) => stable anonymous_name
    - If nemo_speaker_id provided, use it as the canonical source key
    - Otherwise return internal_label unchanged
    """
    if not internal_label:
        return internal_label
    if nemo_speaker_id:
        return anonymous_name(seed=f"{session_id}_nemo:{nemo_speaker_id}")
    if _UNKNOWN_N_PATTERN.match(internal_label):
        return unknown_speaker_display_name(session_id, internal_label)
    m = _UNKNOWN_SPK_PATTERN.match(internal_label)
    if m:
        return anonymous_name(seed=f"{session_id}_nemo:spk_{m.group(1)}")
    if _SPK_PATTERN.match(internal_label):
        return anonymous_name(seed=f"{session_id}_nemo:{internal_label.lower()}")
    m = _ANON_N_PATTERN.match(internal_label)
    if m:
        return anonymous_name(seed=f"{session_id}_anon:{m.group(1)}")
    return internal_label
