"""Cinematic startup sequence and live HUD overlay."""

from __future__ import annotations

import math

import cv2
import numpy as np

import config
from ui.effects import (
    DIM_GRAY,
    GRAY,
    NEON_CYAN,
    NEON_GREEN,
    NEON_PINK,
    NEON_PURPLE,
    NEON_RED,
    NEON_YELLOW,
    WHITE,
    bar,
    breathing_dot,
    clamp01,
    ease_out_cubic,
    led_orb,
    panel,
    scale_color,
    sparkline,
    text,
    text_centered,
    warning_pulse,
)
from vision.gesture_engine import FINGER_NAMES

STARTUP_LINES = [
    ("POWER SYSTEM", "ONLINE"),
    ("NEURAL LINK", "INITIALIZING"),
    ("VISION SYSTEM", "INITIALIZING"),
    ("ESP32 LINK", "SEARCHING"),
    ("GESTURE ENGINE", "LOADING"),
]

STARTUP_TOTAL_DURATION = 4.4
_LINE_START = 0.35
_LINE_GAP = 0.42
_LOGO_START = 2.55
_LOGO_DURATION = 1.0
_FINAL_START = 3.6
_OK_STATES = ("ONLINE", "READY", "FOUND", "ACTIVE", "CONNECTED", "VERIFIED")
_BAD_STATES = ("FAILED", "NOT FOUND", "OFFLINE", "ERROR")

HELP_LINES = [
    ("OPEN PALM", "LED ON"),
    ("FIST", "LED OFF"),
    ("PEACE", "LED BLINK (extended mode)"),
    ("", ""),
    ("[h]", "toggle this help"),
    ("[d]", "DEMO mode (virtual ESP32)"),
    ("[e]", "extended gestures on/off"),
    ("[s]", "screenshot"),
    ("[f]", "fullscreen"),
    ("[m]  [+/-]", "mute  /  volume"),
    ("[r]", "reset system"),
    ("[q]", "quit"),
]


def render_startup_frame(width, height, elapsed, boot_status, bg=None):
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    cx, cy = width // 2, height // 2
    if bg is not None:
        bg.update(1 / 30)
        bg.draw(frame, alpha=0.10)
    if elapsed < _LOGO_START + 0.3:
        pulse = math.sin(elapsed * 6) * 0.5 + 0.5
        cv2.circle(frame, (cx, cy - 150), 3 + int(pulse * 3), NEON_CYAN, -1, cv2.LINE_AA)
    for i, (label, default_status) in enumerate(STARTUP_LINES):
        appear_t = _LINE_START + i * _LINE_GAP
        if elapsed < appear_t:
            continue
        local_t = ease_out_cubic((elapsed - appear_t) / 0.3)
        y = cy - 70 + i * 30
        status = boot_status.get(label, default_status)
        if status in _OK_STATES:
            color = NEON_GREEN
        elif status in _BAD_STATES:
            color = NEON_RED
        else:
            color = NEON_YELLOW
        text(frame, f"{label:<16}{'.' * 22}", cx - 270, y, 0.5, scale_color(WHITE, local_t), 1)
        text(frame, status, cx + 140, y, 0.5, scale_color(color, local_t), 1)
    if elapsed >= _LOGO_START:
        lt = clamp01((elapsed - _LOGO_START) / _LOGO_DURATION)
        radius = int(18 + ease_out_cubic(lt) * 95)
        cv2.circle(frame, (cx, cy), radius, NEON_PINK, 1, cv2.LINE_AA)
        for k in range(8):
            ang = math.radians(elapsed * 130 + k * 45)
            cv2.line(
                frame,
                (int(cx + math.cos(ang) * radius), int(cy + math.sin(ang) * radius)),
                (int(cx + math.cos(ang) * (radius + 12)), int(cy + math.sin(ang) * (radius + 12))),
                NEON_CYAN,
                1,
                cv2.LINE_AA,
            )
        sweep_y = cy - radius + int((math.sin(elapsed * 4) * 0.5 + 0.5) * radius * 2)
        cv2.line(frame, (cx - radius, sweep_y), (cx + radius, sweep_y), NEON_CYAN, 1, cv2.LINE_AA)
        if lt > 0.5:
            title_t = ease_out_cubic((lt - 0.5) / 0.5)
            text_centered(frame, "AURA LINK", cx, cy + 8, 1.3, scale_color(WHITE, title_t), 2)
        if lt >= 0.999:
            text_centered(frame, "ROBOTIC CONTROL SYSTEM", cx, cy + 40, 0.5, NEON_CYAN, 1)
    if elapsed >= _FINAL_START:
        ft = ease_out_cubic((elapsed - _FINAL_START) / 0.5)
        text_centered(frame, "ALL SYSTEMS NOMINAL", cx, cy - 170, 0.55, scale_color(NEON_GREEN, ft), 1)
    text(frame, "press any key to skip", width - 260, height - 20, 0.4, DIM_GRAY, 1)
    return frame


def draw_live_hud(frame, ctx: dict) -> None:
    height, width = frame.shape[:2]
    now = ctx["now"]
    link = ctx["link"]
    audio = ctx["audio"]
    fps = ctx["fps"]
    hand_count = ctx["hand_count"]
    current_gesture = ctx["current_gesture"]
    gesture_confidence = ctx["gesture_confidence"]
    ring_color = ctx["ring_color"]
    active_cmd = ctx["active_cmd"]
    fingers = ctx["fingers"]
    smoothed_servo = ctx["smoothed_servo"]
    events = ctx["events"]
    eye = ctx["eye"]
    show_help = ctx["show_help"]
    dashboard_url = ctx["dashboard_url"]
    estop = ctx["estop"]
    version = config.VERSION

    panel(frame, 20, 20, 390, 108, accent=NEON_PINK)
    text(frame, "AURA SYSTEM", 40, 58, 0.85, WHITE, 2)
    text(frame, f"AYUSH VISION  //  {version}", 40, 88, 0.5, NEON_CYAN, 1)
    breathing_dot(frame, (205, 64), now, color=NEON_PINK, base=3, amp=2)

    badge_y = 40
    if link.simulate:
        text_centered(frame, "DEMO MODE", width // 2, badge_y, 0.6, NEON_YELLOW, 2)
        badge_y += 24
    if ctx["extended"]:
        text_centered(frame, "EXTENDED GESTURES", width // 2, badge_y, 0.45, NEON_CYAN, 1)
        badge_y += 20
    if estop:
        text_centered(frame, "E-STOP ACTIVE", width // 2, badge_y, 0.5, NEON_RED, 2)

    panel(frame, width - 380, 20, width - 20, 258, accent=NEON_CYAN)
    if link.online:
        link_status, link_color = "ONLINE", NEON_GREEN
        breathing_dot(frame, (width - 355, 50), now, color=link_color, base=4, amp=2)
    elif link.simulate:
        link_status, link_color = "SIMULATED", NEON_YELLOW
        breathing_dot(frame, (width - 355, 50), now, color=link_color, base=4, amp=2)
    else:
        link_status, link_color = "OFFLINE", NEON_RED
        warning_pulse(frame, (width - 355, 50), now, color=link_color)

    text(frame, f"AURA LINK : {link_status}", width - 340, 55, 0.6, link_color, 2)
    text(frame, f"ESP32 : {link.ip or 'NOT FOUND'}", width - 355, 85, 0.46, WHITE)
    text(frame, f"LED : {link.led_state}", width - 355, 112, 0.46,
         NEON_GREEN if link.led_state != "OFF" else GRAY)
    text(frame, f"FPS : {fps:.1f}", width - 355, 139, 0.46, WHITE)
    text(frame, f"HANDS : {hand_count}", width - 355, 166, 0.46, WHITE)
    ping_txt = f"{link.latency_ms:.0f} ms" if link.latency_ms is not None else "-- ms"
    text(frame, f"PING : {ping_txt}", width - 355, 193, 0.46, WHITE)
    eye_txt = f"EYES : {eye.get('status', 'DISABLED')}"
    text(frame, eye_txt, width - 355, 220, 0.42, NEON_CYAN if eye.get("detected") else GRAY)
    sparkline(frame, width - 225, 236, 185, 28, link.latency_hist, color=NEON_GREEN, vmax=200)
    led_orb(frame, (width - 75, 125), link.led_state, now)

    panel(frame, 20, height - 160, 420, height - 20, accent=NEON_PINK)
    text(frame, "GESTURE", 40, height - 122, 0.46, NEON_CYAN, 1)
    gesture_color = ring_color if active_cmd else WHITE
    flash_boost = ctx.get("flash_boost", 0.0)
    display_color = tuple(min(255, int(c + (255 - c) * flash_boost)) for c in gesture_color)
    text(frame, current_gesture, 40, height - 80, 0.82, display_color, 2)
    bar(frame, 40, height - 62, 360, 10, gesture_confidence, color=gesture_color)
    hint = "OPEN PALM = ON  |  FIST = OFF" + ("  |  PEACE = BLINK" if ctx["extended"] else "")
    text(frame, hint, 40, height - 38, 0.4, GRAY)

    panel(frame, 440, height - 160, 700, height - 20, accent=NEON_PURPLE)
    text(frame, "FINGER STATUS", 460, height - 122, 0.42, NEON_CYAN, 1)
    for i, name in enumerate(FINGER_NAMES):
        if i < len(fingers):
            state = "UP" if fingers[i] else "DOWN"
            color = NEON_GREEN if fingers[i] else NEON_RED
        else:
            state, color = "--", GRAY
        text(frame, f"{name:<7}: {state}", 460, height - 95 + i * 16, 0.34, color)

    from ui.effects import draw_servo_readout

    panel(frame, 720, height - 220, 990, height - 20, accent=NEON_CYAN)
    draw_servo_readout(frame, 740, height - 190, smoothed_servo, accent=NEON_CYAN)

    panel(frame, 1010, height - 220, width - 20, height - 20, accent=NEON_CYAN)
    text(frame, "EVENT STREAM", 1030, height - 190, 0.42, NEON_CYAN, 1)
    for i, event in enumerate(list(events)[-5:]):
        msg = event.get("message", "")
        kind = event.get("kind", "info")
        col = NEON_GREEN if kind in {"ok", "info"} else NEON_RED if kind in {"warn", "error"} else WHITE
        if event.get("color") == "cyan":
            col = NEON_CYAN
        if event.get("color") == "yellow":
            col = NEON_YELLOW
        text(frame, f"{event.get('t', '')}  {msg}"[:42], 1030, height - 160 + i * 17, 0.32, col)

    mute_label = "MUTED" if audio.muted else f"VOL {int(audio.volume * 100)}%"
    text(frame, f"AURA LINK {version} // [h] help  [q] quit  [m] {mute_label}",
         width - 520, height - 8, 0.34, DIM_GRAY)
    text(frame, dashboard_url, 20, height - 8, 0.34, DIM_GRAY)

    if show_help:
        x1, y1 = width // 2 - 230, height // 2 - 190
        panel(frame, x1, y1, x1 + 460, y1 + 380, accent=NEON_PINK, alpha=0.92)
        text_centered(frame, "CONTROL MANUAL", width // 2, y1 + 40, 0.75, WHITE, 2)
        for i, (k, v) in enumerate(HELP_LINES):
            if k:
                text(frame, k, x1 + 30, y1 + 80 + i * 24, 0.5, NEON_CYAN, 1)
                text(frame, v, x1 + 170, y1 + 80 + i * 24, 0.5, WHITE, 1)
