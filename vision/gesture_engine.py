"""Finger-state classification and hold-to-confirm stabilization from V5."""

from __future__ import annotations

import math

import numpy as np


FINGER_NAMES = ["THUMB", "INDEX", "MIDDLE", "RING", "PINKY"]
FINGER_JOINTS = {
    "THUMB": (2, 3, 4),
    "INDEX": (5, 6, 7),
    "MIDDLE": (9, 10, 11),
    "RING": (13, 14, 15),
    "PINKY": (17, 18, 19),
}


def distance(a, b) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


def angle(a, b, c) -> float:
    ba = np.array([a.x - b.x, a.y - b.y, a.z - b.z])
    bc = np.array([c.x - b.x, c.y - b.y, c.z - b.z])
    denominator = np.linalg.norm(ba) * np.linalg.norm(bc)
    if denominator == 0:
        return 0
    return math.degrees(math.acos(np.clip(np.dot(ba, bc) / denominator, -1, 1)))


def finger_extended(lm, mcp, pip, dip, tip) -> bool:
    angle_test = angle(lm[mcp], lm[pip], lm[dip]) > 150 and angle(lm[pip], lm[dip], lm[tip]) > 145
    palm_size = max(distance(lm[0], lm[mcp]), 0.01)
    distance_test = distance(lm[0], lm[tip]) > palm_size * 1.35
    return angle_test and distance_test


def thumb_extended(lm) -> bool:
    angle_test = angle(lm[2], lm[3], lm[4]) > 145
    distance_test = distance(lm[0], lm[4]) > distance(lm[0], lm[2]) * 1.15
    return angle_test and distance_test


def get_fingers(lm) -> list[bool]:
    return [
        thumb_extended(lm),
        finger_extended(lm, 5, 6, 7, 8),
        finger_extended(lm, 9, 10, 11, 12),
        finger_extended(lm, 13, 14, 15, 16),
        finger_extended(lm, 17, 18, 19, 20),
    ]


def classify_gesture(fingers: list[bool]) -> str:
    thumb, index, middle, ring, pinky = fingers
    total = sum(fingers)
    if total == 5:
        return "OPEN PALM"
    if total == 0:
        return "FIST"
    if not thumb and index and middle and not ring and not pinky:
        return "PEACE"
    if not thumb and index and not middle and not ring and not pinky:
        return "POINT"
    if not thumb and index and middle and ring and not pinky:
        return "THREE"
    if not thumb and index and middle and ring and pinky:
        return "FOUR"
    if thumb and not index and not middle and not ring and not pinky:
        return "THUMBS UP"
    if not thumb and index and not middle and not ring and pinky:
        return "ROCK"
    if thumb and not index and not middle and not ring and pinky:
        return "SHAKA"
    return f"{total} FINGERS"


def compute_servo_angles(landmarks, angle_fn=angle) -> dict[str, float]:
    return {
        name: angle_fn(landmarks[a], landmarks[b], landmarks[c])
        for name, (a, b, c) in FINGER_JOINTS.items()
    }


class GestureStabilizer:
    def __init__(self, required: int = 5) -> None:
        self.required = max(1, int(required))
        self.last: str | None = None
        self.counter = 0
        self.stable = "NONE"

    def update(self, gesture: str) -> str:
        if gesture == self.last:
            self.counter += 1
        else:
            self.last = gesture
            self.counter = 1
        if self.counter >= self.required:
            self.stable = gesture
        return self.stable

    def confidence(self) -> float:
        return min(self.counter / self.required, 1.0)

    def reset(self) -> None:
        self.last = None
        self.counter = 0
        self.stable = "NONE"

    def set_required(self, required: int) -> None:
        self.required = max(1, int(required))
        self.counter = 0
