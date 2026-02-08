"""Bounded event queues for STT V2 with drop policy."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Generic, Iterable, Optional, TypeVar

T = TypeVar("T")


class EventQueue(Generic[T]):
    def __init__(self, maxsize: int) -> None:
        self.maxsize = maxsize
        self._items: Deque[T] = deque()

    def push(self, item: T, *, drop_preview_first: bool = False) -> None:
        if self.maxsize <= 0:
            return
        if len(self._items) >= self.maxsize:
            if drop_preview_first:
                removed = self._drop_first_preview()
                if not removed:
                    self._items.popleft()
            else:
                self._items.popleft()
        self._items.append(item)

    def pop_all(self) -> list[T]:
        items = list(self._items)
        self._items.clear()
        return items

    def _drop_first_preview(self) -> bool:
        # Preview items are defined by attribute is_patch == False when present.
        for idx, item in enumerate(self._items):
            is_patch = getattr(item, "is_patch", False)
            if not is_patch:
                del self._items[idx]
                return True
        return False


@dataclass
class EventBus:
    audio_queue: EventQueue
    frame_queue: EventQueue
    window_queue: EventQueue
    diar_queue: EventQueue
    stt_queue: EventQueue
