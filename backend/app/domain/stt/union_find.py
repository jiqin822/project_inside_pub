"""Union-find (disjoint set) for unknown speaker labels. Canonical root = smallest N in Unknown_N (Unknown_9 < Unknown_10)."""
from __future__ import annotations

import re
from typing import Dict

_UNKNOWN_PATTERN = re.compile(r"^Unknown_(\d+)$", re.IGNORECASE)


def _unknown_n(label: str) -> int | None:
    """Parse Unknown_N; return N as int or None if not Unknown_N."""
    m = _UNKNOWN_PATTERN.match(label)
    return int(m.group(1)) if m else None


def find(parent: Dict[str, str], x: str) -> str:
    """Return canonical root of x. Defensive: if x not in parent, add as singleton and return x."""
    if x not in parent:
        parent[x] = x
        return x
    if parent[x] == x:
        return x
    root = find(parent, parent[x])
    parent[x] = root  # path compression
    return root


def union(parent: Dict[str, str], x: str, y: str) -> None:
    """Merge sets containing x and y. Canonical root = smallest N in Unknown_N (parse with int())."""
    rx = find(parent, x)
    ry = find(parent, y)
    if rx == ry:
        return
    nx = _unknown_n(rx)
    ny = _unknown_n(ry)
    if nx is not None and ny is not None:
        root, other = (rx, ry) if nx <= ny else (ry, rx)
    else:
        root, other = rx, ry
    parent[other] = root


def union_prefer_root(
    parent: Dict[str, str], x: str, y: str, preferred_root: str | None = None
) -> None:
    """
    Merge sets containing x and y, preferring preferred_root if it is one of the roots.

    This preserves the existing Unknown_N ordering logic when no preferred root applies.
    """
    rx = find(parent, x)
    ry = find(parent, y)
    if rx == ry:
        return
    if preferred_root is not None and (preferred_root in parent or preferred_root in (x, y)):
        rpref = find(parent, preferred_root)
        if rpref == rx:
            parent[ry] = rx
            return
        if rpref == ry:
            parent[rx] = ry
            return
    union(parent, rx, ry)
