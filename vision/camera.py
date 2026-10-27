"""Single-owner webcam capture. The browser must not open the camera itself."""

from __future__ import annotations

import cv2
import numpy as np

import config
from services.logger import log


def list_cameras(max_index: int = 6) -> list[dict]:
    found = []
    for index in range(max_index):
        cap = cv2.VideoCapture(index)
        ok = bool(cap.isOpened())
        cap.release()
        if ok:
            found.append({"index": index, "label": f"Camera {index}"})
    return found


class Camera:
    def __init__(self, index: int | None = None, width: int = config.HUD_W, height: int = config.HUD_H) -> None:
        self.index = config.CAMERA_INDEX if index is None else index
        self.width = width
        self.height = height
        self.capture: cv2.VideoCapture | None = None
        self.read_failures = 0

    def open(self) -> bool:
        self.release()
        camera = cv2.VideoCapture(self.index)
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        if not camera.isOpened():
            log.error("Camera %s unavailable.", self.index)
            self.capture = None
            return False
        self.capture = camera
        self.read_failures = 0
        return True

    def reopen(self, index: int) -> bool:
        self.index = int(index)
        return self.open()

    def read(self) -> np.ndarray | None:
        if self.capture is None:
            return None
        success, frame = self.capture.read()
        if not success:
            self.read_failures += 1
            return None
        self.read_failures = 0
        if frame.shape[1] != self.width or frame.shape[0] != self.height:
            frame = cv2.resize(frame, (self.width, self.height))
        return cv2.flip(frame, 1)

    def placeholder(self, message: str = "CAMERA OFFLINE") -> np.ndarray:
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        cv2.putText(
            frame,
            message,
            (40, self.height // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.1,
            (60, 60, 255),
            2,
            cv2.LINE_AA,
        )
        return frame

    def release(self) -> None:
        if self.capture is not None:
            try:
                self.capture.release()
            except Exception as error:
                log.warning("Camera release failed: %s", error)
            self.capture = None
