"""Optional face/eye openness estimates using MediaPipe Face Landmarker.

This is not identity verification and not a medical diagnostic. Glasses, low
light, profile views, and occlusions reduce confidence. Blendshapes plus a
simple eye-aspect ratio are combined only when a face is present.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import mediapipe as mp
import numpy as np

import config
from services.logger import log
from vision.model_store import ensure_model

# MediaPipe Face Mesh indices (468-point topology).
_LEFT = (33, 160, 158, 133, 153, 144)
_RIGHT = (362, 385, 387, 263, 373, 380)


@dataclass
class EyeState:
    detected: bool
    confidence: float
    left_open: float
    right_open: float
    blink: bool
    status: str
    note: str


def _ear(landmarks, idx) -> float:
    p1, p2, p3, p4, p5, p6 = (landmarks[i] for i in idx)

    def dist(a, b) -> float:
        return math.hypot(a.x - b.x, a.y - b.y)

    denom = 2.0 * dist(p1, p4)
    if denom < 1e-6:
        return 0.0
    return (dist(p2, p6) + dist(p3, p5)) / denom


class EyeTracker:
    def __init__(self) -> None:
        self.enabled = False
        self.ready = False
        self.last_error: str | None = None
        self._landmarker = None
        self._ts = 0
        self._t0 = 0.0
        self._blink_arm = False
        self._cooldown = 0.0

    def start(self) -> bool:
        if not ensure_model(config.FACE_MODEL_FILE, config.FACE_MODEL_URL):
            self.last_error = "face model missing"
            self.ready = False
            return False
        BaseOptions = mp.tasks.BaseOptions
        FaceLandmarker = mp.tasks.vision.FaceLandmarker
        Options = mp.tasks.vision.FaceLandmarkerOptions
        RunningMode = mp.tasks.vision.RunningMode
        options = Options(
            base_options=BaseOptions(model_asset_path=str(config.FACE_MODEL_FILE)),
            running_mode=RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_face_blendshapes=True,
        )
        try:
            self._landmarker = FaceLandmarker.create_from_options(options)
        except Exception as error:
            self.last_error = str(error)
            log.error("Face landmarker failed: %s", error)
            return False
        self.ready = True
        self.enabled = True
        return True

    def detect(self, rgb: np.ndarray, now: float) -> EyeState:
        note = (
            "Approximate eye openness from Face Landmarker landmarks/blendshapes. "
            "Not identity. Not medical."
        )
        if not self.enabled:
            return EyeState(False, 0.0, 0.0, 0.0, False, "DISABLED", note)
        if not self.ready or self._landmarker is None:
            return EyeState(False, 0.0, 0.0, 0.0, False, "UNAVAILABLE", note)
        if self._t0 == 0:
            self._t0 = now
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        self._ts = max(self._ts + 1, int((now - self._t0) * 1000))
        try:
            result = self._landmarker.detect_for_video(image, self._ts)
        except Exception as error:
            log.warning("Eye detect failed: %s", error)
            return EyeState(False, 0.0, 0.0, 0.0, False, "ERROR", note)

        faces = result.face_landmarks or []
        if not faces:
            self._blink_arm = False
            return EyeState(False, 0.0, 0.0, 0.0, False, "NO FACE", note)

        lm = faces[0]
        left_ear = _ear(lm, _LEFT)
        right_ear = _ear(lm, _RIGHT)
        # Typical open EAR is ~0.2-0.32; closed ~0.08-0.15. Normalize coarsely.
        left_open = min(1.0, max(0.0, (left_ear - 0.10) / 0.18))
        right_open = min(1.0, max(0.0, (right_ear - 0.10) / 0.18))

        blink_l = blink_r = 0.0
        blends = result.face_blendshapes[0] if result.face_blendshapes else []
        for item in blends:
            name = getattr(item, "category_name", "")
            if name == "eyeBlinkLeft":
                blink_l = float(item.score)
            elif name == "eyeBlinkRight":
                blink_r = float(item.score)
        if blends:
            left_open = max(0.0, min(1.0, 0.5 * left_open + 0.5 * (1.0 - blink_l)))
            right_open = max(0.0, min(1.0, 0.5 * right_open + 0.5 * (1.0 - blink_r)))

        confidence = (left_open + right_open) / 2.0
        if blends:
            confidence = max(confidence, 1.0 - abs((blink_l + blink_r) / 2.0 - 0.5) * 0.2)

        closed = (left_open + right_open) / 2.0 < 0.35
        blink = False
        if confidence >= 0.45:
            if closed:
                self._blink_arm = True
            elif self._blink_arm and now >= self._cooldown:
                blink = True
                self._blink_arm = False
                self._cooldown = now + 0.25
        else:
            self._blink_arm = False

        status = "EYES CLOSED" if closed else "EYES OPEN"
        return EyeState(True, float(min(1.0, max(0.2, confidence))), left_open, right_open, blink, status, note)

    def close(self) -> None:
        if self._landmarker is not None:
            try:
                self._landmarker.close()
            except Exception as error:
                log.warning("Eye tracker close failed: %s", error)
            self._landmarker = None
        self.ready = False
        self.enabled = False
