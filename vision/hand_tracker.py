"""MediaPipe Tasks hand landmarker. Supports up to two hands."""

from __future__ import annotations

from dataclasses import dataclass

import mediapipe as mp
import numpy as np

import config
from services.logger import log
from vision.gesture_engine import classify_gesture, compute_servo_angles, get_fingers
from vision.model_store import ensure_model


@dataclass
class TrackedHand:
    landmarks: object
    handedness: str
    role: str
    fingers: list[bool]
    gesture: str
    servo: dict[str, float]


class HandTracker:
    def __init__(self) -> None:
        self._landmarker = None
        self._ts = 0
        self._t0 = 0.0
        self.ready = False
        self.last_error: str | None = None

    def start(self) -> bool:
        if not ensure_model(config.HAND_MODEL_FILE, config.HAND_MODEL_URL):
            self.last_error = "hand model missing"
            return False
        BaseOptions = mp.tasks.BaseOptions
        HandLandmarker = mp.tasks.vision.HandLandmarker
        Options = mp.tasks.vision.HandLandmarkerOptions
        RunningMode = mp.tasks.vision.RunningMode
        options = Options(
            base_options=BaseOptions(model_asset_path=str(config.HAND_MODEL_FILE)),
            running_mode=RunningMode.VIDEO,
            num_hands=config.MAX_HANDS,
            min_hand_detection_confidence=config.HAND_CONFIDENCE,
            min_hand_presence_confidence=config.HAND_CONFIDENCE,
            min_tracking_confidence=config.HAND_CONFIDENCE,
        )
        try:
            self._landmarker = HandLandmarker.create_from_options(options)
        except Exception as error:
            self.last_error = str(error)
            log.error("Hand landmarker failed: %s", error)
            return False
        self.ready = True
        return True

    def detect(self, rgb: np.ndarray, now: float) -> list[TrackedHand]:
        if not self.ready or self._landmarker is None:
            return []
        if self._t0 == 0:
            self._t0 = now
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        self._ts = max(self._ts + 1, int((now - self._t0) * 1000))
        try:
            result = self._landmarker.detect_for_video(image, self._ts)
        except Exception as error:
            log.warning("Hand detect failed: %s", error)
            return []
        hands: list[TrackedHand] = []
        landmarks_list = result.hand_landmarks or []
        handedness_list = result.handedness or []
        for index, landmarks in enumerate(landmarks_list):
            label = "UNKNOWN"
            if index < len(handedness_list) and handedness_list[index]:
                cat = handedness_list[index][0]
                label = getattr(cat, "category_name", None) or getattr(cat, "display_name", "UNKNOWN")
            fingers = get_fingers(landmarks)
            hands.append(
                TrackedHand(
                    landmarks=landmarks,
                    handedness=str(label).upper(),
                    role="SECONDARY",
                    fingers=fingers,
                    gesture=classify_gesture(fingers),
                    servo=compute_servo_angles(landmarks),
                )
            )
        if hands:
            hands.sort(key=lambda h: 0 if h.handedness == "RIGHT" else 1)
            hands[0].role = "PRIMARY"
            if len(hands) > 1:
                hands[1].role = "SECONDARY"
        return hands

    def close(self) -> None:
        if self._landmarker is not None:
            try:
                self._landmarker.close()
            except Exception as error:
                log.warning("Hand tracker close failed: %s", error)
            self._landmarker = None
        self.ready = False
