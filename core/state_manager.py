"""Thread-safe system state used by the HUD, API, and workers."""

from __future__ import annotations

import threading
import time
from typing import Any


class StateManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jpeg: bytes | None = None
        self._jpeg_t = 0.0
        self._data: dict[str, Any] = {
            "version": "v6.0",
            "running": False,
            "camera_ok": False,
            "camera_index": 0,
            "vision_ok": False,
            "eye_enabled": False,
            "eye_status": "DISABLED",
            "eye_confidence": 0.0,
            "eyes_open": None,
            "blink": False,
            "hands": 0,
            "hand_roles": [],
            "gesture": "NO HAND",
            "gesture_confidence": 0.0,
            "finger_status": [],
            "secondary_fingers": [],
            "servo": {},
            "fps": 0.0,
            "extended": False,
            "demo": False,
            "simulated": True,
            "esp32_online": False,
            "esp32_ip": None,
            "esp32_reconnecting": False,
            "led": "OFF",
            "latency_ms": None,
            "latency_hist": [],
            "estop": False,
            "last_command": None,
            "last_command_ok": None,
            "last_command_source": None,
            "events": [],
            "gesture_map": {},
            "dashboard_url": "http://127.0.0.1:8080",
            "web_bound": "127.0.0.1",
            "allow_lan": False,
        }

    def update(self, **fields: Any) -> None:
        with self._lock:
            self._data.update(fields)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            data = dict(self._data)
            data["latency_hist"] = list(self._data.get("latency_hist") or [])
            data["events"] = list(self._data.get("events") or [])
            data["hand_roles"] = list(self._data.get("hand_roles") or [])
            data["finger_status"] = list(self._data.get("finger_status") or [])
            data["secondary_fingers"] = list(self._data.get("secondary_fingers") or [])
            data["servo"] = dict(self._data.get("servo") or {})
            data["gesture_map"] = dict(self._data.get("gesture_map") or {})
            return data

    def set_jpeg(self, jpeg: bytes) -> None:
        with self._lock:
            self._jpeg = jpeg
            self._jpeg_t = time.time()

    def latest_jpeg(self) -> bytes | None:
        with self._lock:
            return self._jpeg
