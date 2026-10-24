"""Thread-safe in-process event bus."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any, Callable


Listener = Callable[[dict[str, Any]], None]


class EventBus:
    def __init__(self, history: int = 80) -> None:
        self._lock = threading.Lock()
        self._listeners: list[Listener] = []
        self._history: deque[dict[str, Any]] = deque(maxlen=history)

    def subscribe(self, listener: Listener) -> None:
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def unsubscribe(self, listener: Listener) -> None:
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def emit(self, kind: str, message: str, **payload: Any) -> dict[str, Any]:
        event = {
            "t": time.strftime("%H:%M:%S"),
            "kind": kind,
            "message": message,
            **payload,
        }
        with self._lock:
            self._history.append(event)
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(event)
            except Exception:
                # Listener failures must not break the vision loop.
                continue
        return event

    def recent(self, limit: int = 12) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._history)
        return items[-limit:]
