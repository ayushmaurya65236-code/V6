"""HUD primitives and cinematic FX preserved from AURA LINK V5."""

from __future__ import annotations

import math
import random
import time

import cv2
import numpy as np

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
NEON_CYAN = (255, 255, 0)
NEON_PINK = (210, 0, 255)
NEON_PURPLE = (255, 60, 170)
NEON_GREEN = (110, 255, 60)
NEON_RED = (60, 60, 255)
NEON_YELLOW = (0, 230, 255)
GRAY = (130, 130, 140)
DIM_GRAY = (70, 70, 80)
PANEL_BG = (14, 12, 22)

CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
]


def lerp(a, b, t):
    return a + (b - a) * t


def clamp01(t):
    return max(0.0, min(1.0, t))


def ease_out_cubic(t):
    t = clamp01(t)
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    t = clamp01(t)
    return t * t * (3 - 2 * t)


def scale_color(color, k):
    return tuple(int(c * k) for c in color)


def text(frame, value, x, y, size=0.6, color=WHITE, thickness=1):
    cv2.putText(frame, value, (x, y), cv2.FONT_HERSHEY_SIMPLEX, size, color, thickness, cv2.LINE_AA)


def text_centered(frame, value, cx, y, size=0.6, color=WHITE, thickness=1):
    (tw, _), _ = cv2.getTextSize(value, cv2.FONT_HERSHEY_SIMPLEX, size, thickness)
    text(frame, value, cx - tw // 2, y, size, color, thickness)


def panel(frame, x1, y1, x2, y2, accent=NEON_PURPLE, alpha=0.82):
    overlay = frame.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), PANEL_BG, -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    cv2.rectangle(frame, (x1, y1), (x2, y2), accent, 1, cv2.LINE_AA)
    tick = 14
    for cx, cy, dx, dy in [(x1, y1, 1, 1), (x2, y1, -1, 1), (x1, y2, 1, -1), (x2, y2, -1, -1)]:
        cv2.line(frame, (cx, cy), (cx + dx * tick, cy), accent, 2, cv2.LINE_AA)
        cv2.line(frame, (cx, cy), (cx, cy + dy * tick), accent, 2, cv2.LINE_AA)


def bar(frame, x, y, w, h, fraction, color=NEON_GREEN):
    fraction = clamp01(fraction)
    cv2.rectangle(frame, (x, y), (x + w, y + h), DIM_GRAY, 1, cv2.LINE_AA)
    fill_w = int(w * fraction)
    if fill_w > 0:
        cv2.rectangle(frame, (x + 1, y + 1), (x + fill_w, y + h - 1), color, -1, cv2.LINE_AA)


def sparkline(frame, x, y, w, h, values, color=NEON_CYAN, vmax=None):
    cv2.rectangle(frame, (x, y), (x + w, y + h), DIM_GRAY, 1, cv2.LINE_AA)
    vals = list(values)
    if len(vals) < 2:
        return
    top = vmax or max(max(vals), 1.0)
    pts = [
        (x + int(i * w / (len(vals) - 1)), y + h - int(clamp01(v / top) * h))
        for i, v in enumerate(vals)
    ]
    cv2.polylines(frame, [np.array(pts, np.int32)], False, color, 1, cv2.LINE_AA)


def breathing_dot(frame, center, t, color=NEON_GREEN, base=3, amp=2, speed=3.0):
    r = base + int((math.sin(t * speed) * 0.5 + 0.5) * amp)
    cv2.circle(frame, center, r, color, -1, cv2.LINE_AA)


def warning_pulse(frame, center, t, color=NEON_RED, base=4, amp=4, speed=6.0):
    r = base + int((math.sin(t * speed) * 0.5 + 0.5) * amp)
    cv2.circle(frame, center, r, color, 2, cv2.LINE_AA)


def scan_line(frame, y, color=NEON_CYAN, alpha=0.12):
    h, w = frame.shape[:2]
    if 0 <= y < h:
        overlay = frame.copy()
        cv2.line(overlay, (0, y), (w, y), color, 1, cv2.LINE_AA)
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


def led_orb(frame, center, state, t, radius=24):
    if state == "OFF":
        cv2.circle(frame, center, radius, (30, 28, 40), -1, cv2.LINE_AA)
        cv2.circle(frame, center, radius, DIM_GRAY, 2, cv2.LINE_AA)
        return
    on = True
    if state == "BLINK":
        on = int(t * 4) % 2 == 0
    if not on:
        cv2.circle(frame, center, radius, DIM_GRAY, 2, cv2.LINE_AA)
        return
    glow = frame.copy()
    pulse = 0.5 + 0.5 * math.sin(t * 4)
    cv2.circle(glow, center, int(radius * (2.0 + pulse * 0.4)), NEON_GREEN, -1, cv2.LINE_AA)
    cv2.addWeighted(glow, 0.18, frame, 0.82, 0, frame)
    cv2.circle(frame, center, radius, NEON_GREEN, -1, cv2.LINE_AA)
    cv2.circle(frame, center, radius // 2, WHITE, -1, cv2.LINE_AA)
    cv2.circle(frame, center, radius + 4, NEON_GREEN, 1, cv2.LINE_AA)


class NeuralBackground:
    def __init__(self, width, height, node_count=24, seed=7):
        self.width = width
        self.height = height
        rng = random.Random(seed)
        self.nodes = [
            {"x": rng.uniform(0, width), "y": rng.uniform(0, height),
             "vx": rng.uniform(-10, 10), "vy": rng.uniform(-10, 10)}
            for _ in range(node_count)
        ]
        self.link_dist = min(width, height) * 0.16
        self.pulses = []
        self._last_pulse = 0.0

    def update(self, dt):
        for n in self.nodes:
            n["x"] += n["vx"] * dt
            n["y"] += n["vy"] * dt
            if n["x"] < 0 or n["x"] > self.width:
                n["vx"] *= -1
                n["x"] = max(0, min(self.width, n["x"]))
            if n["y"] < 0 or n["y"] > self.height:
                n["vy"] *= -1
                n["y"] = max(0, min(self.height, n["y"]))
        now = time.time()
        if now - self._last_pulse > 1.3 and len(self.nodes) >= 2:
            self._last_pulse = now
            a, b = random.sample(self.nodes, 2)
            if math.hypot(a["x"] - b["x"], a["y"] - b["y"]) < self.link_dist * 1.6:
                self.pulses.append({"a": a, "b": b, "t": 0.0})
        for p in self.pulses:
            p["t"] += dt * 0.7
        self.pulses = [p for p in self.pulses if p["t"] < 1.0]

    def draw(self, frame, alpha=0.30):
        overlay = frame.copy()
        for i, a in enumerate(self.nodes):
            for b in self.nodes[i + 1:]:
                d = math.hypot(a["x"] - b["x"], a["y"] - b["y"])
                if d < self.link_dist:
                    col = scale_color(NEON_PURPLE, 1 - d / self.link_dist)
                    cv2.line(overlay, (int(a["x"]), int(a["y"])), (int(b["x"]), int(b["y"])), col, 1, cv2.LINE_AA)
        for n in self.nodes:
            cv2.circle(overlay, (int(n["x"]), int(n["y"])), 2, NEON_CYAN, -1, cv2.LINE_AA)
        for p in self.pulses:
            x = lerp(p["a"]["x"], p["b"]["x"], p["t"])
            y = lerp(p["a"]["y"], p["b"]["y"], p["t"])
            cv2.circle(overlay, (int(x), int(y)), 3, NEON_PINK, -1, cv2.LINE_AA)
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


class TransmissionFX:
    def __init__(self):
        self.active = []

    def trigger(self, source, target, color=NEON_CYAN, count=12, duration=0.5):
        self.active.append({"src": source, "dst": target, "t0": time.time(),
                            "dur": duration, "color": color, "count": count})

    def update_draw(self, frame):
        now = time.time()
        still = []
        for tx in self.active:
            t = (now - tx["t0"]) / tx["dur"]
            if t >= 1.0:
                continue
            still.append(tx)
            sx, sy = tx["src"]
            dx, dy = tx["dst"]
            cv2.line(frame, tx["src"], tx["dst"], scale_color(tx["color"], 0.25), 1, cv2.LINE_AA)
            for i in range(tx["count"]):
                pt = (t + i / tx["count"] * 0.2) % 1.0
                e = ease_in_out(pt)
                cv2.circle(frame, (int(lerp(sx, dx, e)), int(lerp(sy, dy, e))), 2, tx["color"], -1, cv2.LINE_AA)
        self.active = still


class ParticleTrail:
    def __init__(self, max_particles=90):
        self.max = max_particles
        self.p = []

    def emit(self, x, y, color=NEON_PINK, n=2):
        for _ in range(n):
            if len(self.p) >= self.max:
                self.p.pop(0)
            self.p.append([x + random.uniform(-4, 4), y + random.uniform(-4, 4),
                           random.uniform(-35, 35), random.uniform(-45, 15), 1.0, color])

    def update_draw(self, frame, dt):
        if not self.p:
            return
        overlay = frame.copy()
        alive = []
        for x, y, vx, vy, life, color in self.p:
            life -= dt * 1.8
            if life <= 0:
                continue
            x += vx * dt
            y += vy * dt
            cv2.circle(overlay, (int(x), int(y)), max(1, int(4 * life)), color, -1, cv2.LINE_AA)
            alive.append([x, y, vx, vy, life, color])
        cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)
        self.p = alive


def draw_robotic_hand(frame, landmarks, accent=NEON_PINK, progress=0.0,
                      ring_color=NEON_GREEN, locked=False, t=0.0, label=None):
    height, width = frame.shape[:2]
    points = [(int(lm.x * width), int(lm.y * height)) for lm in landmarks]
    glow = frame.copy()
    for a, b in CONNECTIONS:
        cv2.line(glow, points[a], points[b], accent, 9, cv2.LINE_AA)
    cv2.addWeighted(glow, 0.22, frame, 0.78, 0, frame)
    for a, b in CONNECTIONS:
        cv2.line(frame, points[a], points[b], NEON_CYAN, 2, cv2.LINE_AA)
        cv2.line(frame, points[a], points[b], BLACK, 1, cv2.LINE_AA)
    for idx, (x, y) in enumerate(points):
        s = 5 if idx in (4, 8, 12, 16, 20) else 3
        cv2.rectangle(frame, (x - s, y - s), (x + s, y + s), WHITE, -1, cv2.LINE_AA)
        cv2.rectangle(frame, (x - s - 2, y - s - 2), (x + s + 2, y + s + 2), accent, 1, cv2.LINE_AA)
    palm = points[9]
    if progress > 0:
        r = 46
        cv2.circle(frame, palm, r, scale_color(ring_color, 0.25), 2, cv2.LINE_AA)
        cv2.ellipse(frame, palm, (r, r), -90, 0, 360 * clamp01(progress), ring_color, 3, cv2.LINE_AA)
    if locked:
        pr = 58 + int((math.sin(t * 5.0) * 0.5 + 0.5) * 10)
        cv2.circle(frame, palm, pr, ring_color, 1, cv2.LINE_AA)
    if label:
        wx, wy = points[0]
        text(frame, label, wx - 28, wy + 28, 0.4, accent, 1)
    return points


def draw_servo_readout(frame, x, y, smoothed, accent=NEON_CYAN):
    from vision.gesture_engine import FINGER_NAMES

    text(frame, "SERVO TELEMETRY", x, y, 0.42, accent, 1)
    for i, name in enumerate(FINGER_NAMES):
        val = smoothed.get(name, 0.0)
        row_y = y + 24 + i * 18
        text(frame, f"{name:<7} SERVO", x, row_y, 0.36, GRAY, 1)
        text(frame, f"{val:5.1f}deg", x + 190, row_y, 0.36, WHITE, 1)
        bar(frame, x, row_y + 5, 160, 4, val / 180.0, color=accent)
