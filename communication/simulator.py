"""Virtual ESP32 used by DEMO MODE. No network I/O."""

from __future__ import annotations

import threading
import time


class VirtualESP32:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.led_state = "OFF"
        self.last_command: str | None = None
        self.last_ok = True
        self.online = True
        self.latency_ms = 0.4
        self._blink = False
        self._blink_t = 0.0

    def reset(self) -> None:
        with self._lock:
            self.led_state = "OFF"
            self.last_command = None
            self.last_ok = True
            self._blink = False

    def execute(self, command: str) -> tuple[bool, str]:
        with self._lock:
            if command == "LED_ON":
                self._blink = False
                self.led_state = "ON"
            elif command == "LED_OFF":
                self._blink = False
                self.led_state = "OFF"
            elif command == "LED_BLINK":
                self._blink = True
                self.led_state = "BLINK"
            elif command == "E_STOP":
                self._blink = False
                self.led_state = "OFF"
            else:
                self.last_ok = False
                self.last_command = command
                return False, self.led_state
            self.last_command = command
            self.last_ok = True
            return True, self.led_state

    def visible_led(self) -> str:
        with self._lock:
            if self.led_state != "BLINK":
                return self.led_state
            on = int(time.time() * 4) % 2 == 0
            return "ON" if on else "OFF"

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "led": self.led_state,
                "last_command": self.last_command,
                "ok": self.last_ok,
                "simulated": True,
            }
