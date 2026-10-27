"""JSON API helpers used by the local HTTP server. Testable without sockets."""

from __future__ import annotations

from typing import Any, Protocol

import config


class ControllerAPI(Protocol):
    def public_state(self) -> dict[str, Any]: ...
    def apply_settings(self, payload: dict[str, Any]) -> tuple[bool, str]: ...
    def api_command(self, command: str, source: str = "api") -> dict[str, Any]: ...
    def emergency_stop(self) -> dict[str, Any]: ...
    def provision_wifi(self, ssid: str, password: str, device_ip: str | None) -> tuple[bool, str]: ...
    def list_cameras(self) -> list[dict]: ...
    def latest_jpeg(self) -> bytes | None: ...
    def dashboard_token_ok(self, token: str | None) -> bool: ...
    def bind_requires_token(self) -> bool: ...


def parse_command_body(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    if not isinstance(payload, dict):
        return None, "JSON object required"
    command = str(payload.get("command") or payload.get("name") or "").strip()
    if not command:
        return None, "command is required"
    key = command.upper().replace(" ", "_").replace("-", "_")
    aliases = {
        "ON": "LED_ON",
        "OFF": "LED_OFF",
        "BLINK": "LED_BLINK",
        "LEDON": "LED_ON",
        "LEDOFF": "LED_OFF",
        "STOP": "E_STOP",
        "ESTOP": "E_STOP",
        "EMERGENCY_STOP": "E_STOP",
    }
    key = aliases.get(key, key)
    if key not in config.ALLOWED_COMMANDS or key in {"NONE", "DISPLAY"}:
        return None, "command is not allowed"
    return key, None


def wifi_payload(payload: dict[str, Any]) -> tuple[dict[str, str] | None, str | None]:
    if not isinstance(payload, dict):
        return None, "JSON object required"
    ssid = str(payload.get("ssid") or "").strip()
    password = str(payload.get("password") or "")
    device_ip = str(payload.get("device_ip") or payload.get("ip") or "").strip()
    if not ssid:
        return None, "ssid is required"
    if len(ssid) > 32:
        return None, "ssid is too long"
    if len(password) > 63:
        return None, "password is too long"
    return {"ssid": ssid, "password": password, "device_ip": device_ip}, None
