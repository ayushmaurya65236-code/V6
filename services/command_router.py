"""Map validated gestures and API actions onto the hardware allowlist."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

import config
from communication.esp32_client import Esp32Client
from core.event_bus import EventBus


SendFn = Callable[[str, str, str | None], None]


class CommandRouter:
    def __init__(self, link: Esp32Client, events: EventBus) -> None:
        self.link = link
        self.events = events
        self.extended = config.EXTENDED_DEFAULT
        self.estop = False
        self.gesture_map = dict(config.DEFAULT_GESTURE_MAP)
        self._lock = threading.Lock()
        self._last_label: str | None = None
        self._last_t = 0.0
        self.last_result: dict[str, Any] | None = None

    def set_extended(self, enabled: bool) -> None:
        with self._lock:
            self.extended = bool(enabled)
            self._last_label = None

    def set_mapping(self, gesture: str, command: str) -> tuple[bool, str]:
        command = command.strip().upper().replace(" ", "_")
        gesture = gesture.strip().upper()
        if command not in config.ALLOWED_COMMANDS:
            return False, "Command is not on the allowlist."
        if gesture not in config.DEFAULT_GESTURE_MAP:
            return False, "Unknown gesture."
        with self._lock:
            self.gesture_map[gesture] = command
        return True, f"{gesture} -> {command}"

    def mappings_public(self) -> dict[str, dict[str, str]]:
        with self._lock:
            items = dict(self.gesture_map)
            extended = self.extended
        out = {}
        for gesture, command in items.items():
            out[gesture] = {
                "command": command,
                "label": config.GESTURE_LABELS.get(command, command),
                "extended_only": gesture in config.EXTENDED_ONLY_GESTURES,
                "active": not (gesture in config.EXTENDED_ONLY_GESTURES and not extended),
            }
        return out

    def clear_command_lock(self) -> None:
        with self._lock:
            self._last_label = None

    def reset_lock(self) -> None:
        with self._lock:
            self._last_label = None
            self.estop = False

    def emergency_stop(self, source: str = "api") -> dict[str, Any]:
        with self._lock:
            self.estop = True
            self._last_label = None
        return self.execute("E_STOP", source=source, force=True)

    def handle_stable_gesture(self, gesture: str) -> None:
        with self._lock:
            command = self.gesture_map.get(gesture, "NONE")
            extended = self.extended
        if gesture in config.EXTENDED_ONLY_GESTURES and not extended:
            return
        if command in {"NONE", "DISPLAY"}:
            self._note_display(gesture, command)
            return
        self.execute(command, source=f"gesture:{gesture}")

    def execute(self, command: str, source: str = "api", force: bool = False) -> dict[str, Any]:
        command = command.strip().upper().replace(" ", "_")
        if command not in config.ALLOWED_COMMANDS or command in {"NONE", "DISPLAY"}:
            result = {
                "ok": False,
                "command": command,
                "source": source,
                "simulated": self.link.simulate,
                "error": "invalid or non-hardware command",
            }
            self.last_result = result
            return result

        with self._lock:
            if self.estop and command != "E_STOP" and not force:
                result = {
                    "ok": False,
                    "command": command,
                    "source": source,
                    "simulated": self.link.simulate,
                    "error": "emergency stop is active",
                }
                self.last_result = result
                return result
            now = time.time()
            label, path, led = config.COMMAND_ROUTES[command]
            if not force and self._last_label == label and (now - self._last_t) < 2.0:
                result = {
                    "ok": True,
                    "command": command,
                    "source": source,
                    "simulated": self.link.simulate,
                    "duplicate": True,
                    "label": label,
                }
                return result
            if now - self._last_t < config.COMMAND_RATE_LIMIT:
                result = {
                    "ok": False,
                    "command": command,
                    "source": source,
                    "simulated": self.link.simulate,
                    "error": "rate limited",
                }
                self.last_result = result
                return result
            self._last_label = label
            self._last_t = now

        usable = self.link.online or self.link.simulate
        if not usable:
            result = {
                "ok": False,
                "command": command,
                "source": source,
                "simulated": False,
                "error": "ESP32 offline (enable DEMO MODE or connect hardware)",
                "label": label,
            }
            self.last_result = result
            self.events.emit("warn", f"ESP32 OFFLINE - {label} blocked", color="red")
            return result

        self.link.send(label, path, led)
        result = {
            "ok": None,
            "pending": True,
            "command": command,
            "source": source,
            "simulated": self.link.simulate,
            "label": label,
            "note": "waiting for device confirmation" if not self.link.simulate else "simulated",
        }
        self.last_result = result
        return result

    def _note_display(self, gesture: str, command: str) -> None:
        label = f"{gesture} / {config.GESTURE_LABELS.get(command, command)}"
        with self._lock:
            if self._last_label == label:
                return
            self._last_label = label
            self._last_t = time.time()
        self.events.emit("info", f"{gesture} recognized (no hardware action)", color="cyan")
