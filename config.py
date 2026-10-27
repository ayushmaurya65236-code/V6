"""AURA LINK V6 configuration. Values come from environment / optional .env."""

from __future__ import annotations

import os
from pathlib import Path

VERSION = "v6.0"
APP_NAME = "AURA LINK"
WINDOW_NAME = "AURA SYSTEM - AYUSH VISION"

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"
CAPTURE_DIR = BASE_DIR / "captures"
WEB_DIR = BASE_DIR / "web"
ENV_PATH = BASE_DIR / ".env"

HAND_MODEL_FILE = MODELS_DIR / "hand_landmarker.task"
HAND_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)
FACE_MODEL_FILE = MODELS_DIR / "face_landmarker.task"
FACE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)

HUD_W = 1280
HUD_H = 720
SAMPLE_RATE = 44100

DISCOVERY_MESSAGE = b"AURA_DISCOVER_V1"
DISCOVERY_REPLY_PREFIX = "AURA_LINK|"

# Hardware command allowlist. Motor/servo motion is intentionally omitted.
ALLOWED_COMMANDS = frozenset({
    "LED_ON",
    "LED_OFF",
    "LED_BLINK",
    "DISPLAY",
    "NONE",
    "E_STOP",
})

COMMAND_ROUTES = {
    "LED_ON": ("LED ON", "/led/on", "ON"),
    "LED_OFF": ("LED OFF", "/led/off", "OFF"),
    "LED_BLINK": ("LED BLINK", "/led/blink", "BLINK"),
    "E_STOP": ("E-STOP", "/stop", "OFF"),
}

DEFAULT_GESTURE_MAP = {
    "OPEN PALM": "LED_ON",
    "FIST": "LED_OFF",
    "PEACE": "LED_BLINK",
    "POINT": "DISPLAY",
    "THREE": "DISPLAY",
    "FOUR": "DISPLAY",
    "THUMBS UP": "DISPLAY",
    "ROCK": "DISPLAY",
    "SHAKA": "DISPLAY",
}

EXTENDED_ONLY_GESTURES = frozenset({"PEACE"})

GESTURE_LABELS = {
    "LED_ON": "LED ON",
    "LED_OFF": "LED OFF",
    "LED_BLINK": "LED BLINK",
    "DISPLAY": "HUD ONLY",
    "NONE": "UNASSIGNED",
    "E_STOP": "EMERGENCY STOP",
}


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv(ENV_PATH)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


WEB_HOST = os.environ.get("AURA_WEB_HOST", "127.0.0.1").strip() or "127.0.0.1"
WEB_PORT = _env_int("AURA_WEB_PORT", 8080)
ALLOW_LAN = _env_bool("AURA_ALLOW_LAN", False)
API_TOKEN = os.environ.get("AURA_API_TOKEN", "").strip()

CAMERA_INDEX = _env_int("AURA_CAMERA_INDEX", 0)
DEMO_MODE = _env_bool("AURA_DEMO_MODE", False)
EYE_TRACKING = _env_bool("AURA_EYE_TRACKING", False)
EXTENDED_DEFAULT = _env_bool("AURA_EXTENDED_GESTURES", False)

ESP32_IP = os.environ.get("AURA_ESP32_IP", "").strip() or None
ESP32_HTTP_PORT = _env_int("AURA_ESP32_HTTP_PORT", 80)
DISCOVERY_PORT = _env_int("AURA_DISCOVERY_PORT", 4210)
HTTP_TIMEOUT = _env_float("AURA_HTTP_TIMEOUT", 0.7)
PROVISION_TIMEOUT = _env_float("AURA_PROVISION_TIMEOUT", 8.0)
HEARTBEAT_SECONDS = _env_float("AURA_HEARTBEAT_SECONDS", 2.0)
RECONNECT_SECONDS = _env_float("AURA_RECONNECT_SECONDS", 5.0)

GESTURE_FRAMES = _env_int("AURA_GESTURE_FRAMES", 5)
SERVO_SMOOTHING = _env_float("AURA_SERVO_SMOOTHING", 0.25)
HAND_CONFIDENCE = _env_float("AURA_HAND_CONFIDENCE", 0.55)
MAX_HANDS = 2
COMMAND_RATE_LIMIT = _env_float("AURA_COMMAND_RATE_LIMIT", 0.25)

STREAM_JPEG_QUALITY = _env_int("AURA_STREAM_JPEG_QUALITY", 70)
STREAM_MAX_FPS = _env_int("AURA_STREAM_MAX_FPS", 15)
API_MAX_BODY = 4096

PROVISION_DEFAULT_IP = os.environ.get("AURA_PROVISION_IP", "192.168.4.1").strip()
