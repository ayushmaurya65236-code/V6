"""Coordinates vision, HUD, ESP32, audio, and the local dashboard."""

from __future__ import annotations

import math
import queue
import threading
import time
from collections import deque
from typing import Any

import cv2
import numpy as np

import config
from communication.esp32_client import Esp32Client
from core.event_bus import EventBus
from core.state_manager import StateManager
from services.audio_engine import SOUND_FOR_LABEL, AudioEngine
from services.command_router import CommandRouter
from services.logger import log
from ui.effects import (
    NEON_CYAN,
    NEON_PINK,
    NEON_PURPLE,
    NeuralBackground,
    ParticleTrail,
    TransmissionFX,
    draw_robotic_hand,
    ease_out_cubic,
    lerp,
    scan_line,
)
from ui.hud import (
    STARTUP_TOTAL_DURATION,
    _FINAL_START,
    _LINE_START,
    _LOGO_START,
    draw_live_hud,
    render_startup_frame,
)
from vision.camera import Camera, list_cameras
from vision.eye_tracker import EyeTracker
from vision.gesture_engine import FINGER_NAMES, GestureStabilizer
from vision.hand_tracker import HandTracker
from web.server import DashboardServer


class AppController:
    def __init__(self) -> None:
        self.events = EventBus()
        self.state = StateManager()
        self.audio = AudioEngine()
        self.link = Esp32Client(simulate=config.DEMO_MODE)
        self.router = CommandRouter(self.link, self.events)
        self.camera = Camera()
        self.hands = HandTracker()
        self.eyes = EyeTracker()
        self.web: DashboardServer | None = None
        self._stop = threading.Event()
        self._actions: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=32)
        self._last_jpeg_t = 0.0
        self._dashboard_url = f"http://127.0.0.1:{config.WEB_PORT}"
        self._bound_host = "127.0.0.1"
        self.events.subscribe(self._on_event)

    def _on_event(self, event: dict[str, Any]) -> None:
        recent = self.events.recent(8)
        self.state.update(events=recent)

    def public_state(self) -> dict[str, Any]:
        snap = self.state.snapshot()
        snap["gesture_map"] = self.router.mappings_public()
        snap["muted"] = self.audio.muted
        snap["volume"] = self.audio.volume
        snap["estop"] = self.router.estop
        return snap

    def latest_jpeg(self) -> bytes | None:
        return self.state.latest_jpeg()

    def list_cameras(self) -> list[dict]:
        return list_cameras()

    def dashboard_token_ok(self, token: str | None) -> bool:
        if not self.bind_requires_token():
            return True
        return bool(config.API_TOKEN) and token == config.API_TOKEN

    def bind_requires_token(self) -> bool:
        return self._bound_host not in {"127.0.0.1", "localhost", "::1"}

    def api_command(self, command: str, source: str = "api") -> dict[str, Any]:
        result = self.router.execute(command, source=source)
        if result.get("pending") and self.link.simulate:
            self._drain_link_results(force_audio=True)
            result = dict(self.router.last_result or result)
            result["ok"] = True
            result["pending"] = False
        return result

    def emergency_stop(self) -> dict[str, Any]:
        result = self.router.emergency_stop("api")
        self.events.emit("warn", "EMERGENCY STOP", color="red")
        self.audio.play("warning")
        return result

    def provision_wifi(self, ssid: str, password: str, device_ip: str | None) -> tuple[bool, str]:
        ok, message = self.link.provision_wifi(ssid, password, device_ip or None)
        self.events.emit("info" if ok else "error", message, color="cyan" if ok else "red")
        return ok, message

    def apply_settings(self, payload: dict[str, Any]) -> tuple[bool, str]:
        try:
            self._actions.put_nowait(("settings", payload))
        except queue.Full:
            return False, "Settings queue is busy."
        return True, "Settings queued."

    def request_stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        log.info("======================================================")
        log.info("AURA SYSTEM %s", config.VERSION)
        log.info("AYUSH VISION")
        log.info("======================================================")
        try:
            self._boot()
            if self._stop.is_set():
                return
            self._live_loop()
        finally:
            self.shutdown()

    def _boot(self) -> None:
        boot_status: dict[str, str] = {}
        log.info("Audio: %s", "SoundDevice mixer online [OK]" if self.audio.available else "running silent")

        log.info("Vision engine...")
        if not self.hands.start():
            boot_status["VISION SYSTEM"] = "FAILED"
            boot_status["GESTURE ENGINE"] = "FAILED"
            log.error("Hand tracker failed to start.")
        else:
            boot_status["VISION SYSTEM"] = "ONLINE"
            boot_status["GESTURE ENGINE"] = "READY"
            log.info("[OK] Vision engine ready")

        if config.EYE_TRACKING:
            if self.eyes.start():
                log.info("[OK] Eye tracking enabled (approximate, not medical)")
            else:
                log.warning("Eye tracking requested but unavailable.")

        log.info("Hardware discovery...")
        if self.link.simulate:
            boot_status["ESP32 LINK"] = "FOUND"
            log.info("DEMO MODE on — using virtual ESP32")
        elif self.link.ip and self.link.verify():
            boot_status["ESP32 LINK"] = "FOUND"
            log.info("[OK] AURA LINK VERIFIED at %s", self.link.ip)
        elif self.link.discover() and self.link.verify():
            boot_status["ESP32 LINK"] = "FOUND"
            log.info("[OK] AURA LINK VERIFIED")
        else:
            boot_status["ESP32 LINK"] = "NOT FOUND"
            log.warning("ESP32 not found (background retry; [d] DEMO mode)")
            self.audio.play("warning")
        self.link.start()

        log.info("Camera...")
        if self.camera.open():
            boot_status["NEURAL LINK"] = "ONLINE"
            log.info("[OK] Camera ready")
        else:
            boot_status["NEURAL LINK"] = "FAILED"
            log.error("Camera unavailable — HUD will show offline frame; dashboard still starts.")
            self.audio.play("warning")

        boot_status["POWER SYSTEM"] = "ONLINE"
        self._start_web()
        self.state.update(
            running=True,
            camera_ok=self.camera.capture is not None,
            camera_index=self.camera.index,
            vision_ok=self.hands.ready,
            eye_enabled=self.eyes.enabled,
            demo=self.link.simulate,
            dashboard_url=self._dashboard_url,
            web_bound=self._bound_host,
            allow_lan=config.ALLOW_LAN,
            version=config.VERSION,
        )
        self.events.emit("ok", "SYSTEM READY")

        cv2.namedWindow(config.WINDOW_NAME, cv2.WINDOW_NORMAL)
        self._startup_animation(boot_status)

    def _start_web(self) -> None:
        host = config.WEB_HOST
        if config.ALLOW_LAN:
            if not config.API_TOKEN:
                log.warning("AURA_ALLOW_LAN is set without AURA_API_TOKEN; binding localhost only.")
                host = "127.0.0.1"
            else:
                host = "0.0.0.0"
                log.warning(
                    "LAN bind enabled. Anyone on this network who has the token can send hardware commands. "
                    "This is not authenticated end-to-end encryption."
                )
        else:
            host = "127.0.0.1"
        self._bound_host = host
        display_host = "127.0.0.1" if host in {"127.0.0.1", "0.0.0.0"} else host
        self._dashboard_url = f"http://{display_host}:{config.WEB_PORT}"
        self.web = DashboardServer(self, host=host, port=config.WEB_PORT)
        self.web.start()
        log.info("Dashboard: %s", self._dashboard_url)

    def _startup_animation(self, boot_status: dict[str, str]) -> None:
        startup_bg = NeuralBackground(config.HUD_W, config.HUD_H, node_count=18)
        self.audio.play("power")
        started = {"activate": False, "scan": False, "rise": False, "ready": False}
        t0 = time.time()
        while not self._stop.is_set():
            elapsed = time.time() - t0
            if elapsed >= STARTUP_TOTAL_DURATION:
                break
            frame = render_startup_frame(config.HUD_W, config.HUD_H, elapsed, boot_status, bg=startup_bg)
            if elapsed > 0.6 and not started["activate"]:
                self.audio.play("activate")
                started["activate"] = True
            if elapsed > _LINE_START and not started["scan"]:
                self.audio.play("scan")
                started["scan"] = True
            if elapsed > _LOGO_START and not started["rise"]:
                self.audio.play("rise")
                started["rise"] = True
            if elapsed > _FINAL_START and not started["ready"]:
                self.audio.play("ready")
                started["ready"] = True
            self._publish_jpeg(frame)
            cv2.imshow(config.WINDOW_NAME, frame)
            if cv2.waitKey(16) & 0xFF != 255:
                self.audio.play("click")
                break

    def _live_loop(self) -> None:
        stabilizer = GestureStabilizer(config.GESTURE_FRAMES)
        neural_bg = NeuralBackground(config.HUD_W, config.HUD_H, node_count=22)
        transmit_fx = TransmissionFX()
        trail = ParticleTrail()
        smoothed_servo = {name: 180.0 if name != "THUMB" else 0.0 for name in FINGER_NAMES}
        previous_time = time.time()
        fps = 0.0
        current_gesture = "NONE"
        previous_command = None
        blocked_label = None
        previous_hand_count = 0
        last_flash_gesture = None
        gesture_flash_t0 = None
        shot_requested = False
        shot_flash_t0 = None
        fullscreen = False
        show_help = False
        core_point = (205, 64)
        esp_point = (config.HUD_W - 200, 64)
        from ui.effects import NEON_GREEN

        while not self._stop.is_set():
            self._apply_queued_actions(stabilizer)
            frame = self.camera.read()
            camera_ok = frame is not None
            if frame is None:
                if self.camera.read_failures > 30:
                    frame = self.camera.placeholder("CAMERA STOPPED")
                    if self.camera.capture is not None:
                        log.error("Camera stopped delivering frames.")
                        self.camera.release()
                else:
                    frame = self.camera.placeholder()
                    cv2.waitKey(10)

            now = time.time()
            dt = now - previous_time
            previous_time = now
            if dt > 0:
                fps = fps * 0.90 + (1 / dt) * 0.10
            dt_safe = dt if dt > 0 else 1 / 30

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            tracked = self.hands.detect(rgb, now) if self.hands.ready else []
            hand_count = len(tracked)
            if hand_count > 0 and previous_hand_count == 0:
                self.audio.play("hand_acquire")
                self.events.emit("info", "TARGET ACQUIRED", color="cyan")
            elif hand_count == 0 and previous_hand_count > 0:
                self.audio.play("hand_lost")
                self.events.emit("info", "TARGET LOST")
            previous_hand_count = hand_count

            primary = next((h for h in tracked if h.role == "PRIMARY"), None)
            fingers: list = []
            raw_servo: dict = {}
            detected_gesture = "NONE"
            if primary:
                fingers = primary.fingers
                detected_gesture = primary.gesture
                raw_servo = primary.servo
                current_gesture = stabilizer.update(detected_gesture)
            else:
                stabilizer.reset()
                current_gesture = "NO HAND"
            gesture_confidence = stabilizer.confidence()

            eye_state = self.eyes.detect(rgb, now) if self.eyes.enabled else None
            eye_payload = {
                "detected": bool(eye_state and eye_state.detected),
                "status": eye_state.status if eye_state else ("DISABLED" if not self.eyes.enabled else "UNAVAILABLE"),
                "confidence": eye_state.confidence if eye_state else 0.0,
                "blink": bool(eye_state and eye_state.blink),
                "note": eye_state.note if eye_state else "Eye tracking off",
            }
            if eye_state and eye_state.blink:
                self.events.emit("info", "BLINK (approx)", color="cyan")

            for name in FINGER_NAMES:
                target = raw_servo.get(name, smoothed_servo[name])
                smoothed_servo[name] = lerp(smoothed_servo[name], target, config.SERVO_SMOOTHING)

            if current_gesture != last_flash_gesture and current_gesture not in ("NONE", "NO HAND"):
                gesture_flash_t0 = now
                last_flash_gesture = current_gesture
                self.audio.play("pulse")
            if current_gesture in ("NONE", "NO HAND"):
                last_flash_gesture = None

            neural_bg.update(dt_safe)
            neural_bg.draw(frame, alpha=0.22)
            sweep_y = int((math.sin(now * 0.6) * 0.5 + 0.5) * frame.shape[0])
            scan_line(frame, sweep_y, color=NEON_CYAN, alpha=0.05)

            mapping = self.router.mappings_public()
            ginfo = mapping.get(current_gesture)
            active_hardware = bool(
                ginfo
                and ginfo["command"] in {"LED_ON", "LED_OFF", "LED_BLINK", "E_STOP"}
                and ginfo["active"]
            )
            ring_color = NEON_GREEN if active_hardware else NEON_CYAN
            from ui.effects import NEON_YELLOW as YEL, NEON_RED as RED

            cmd_colors = {"LED_ON": NEON_GREEN, "LED_OFF": RED, "LED_BLINK": YEL}
            if ginfo:
                ring_color = cmd_colors.get(ginfo["command"], NEON_CYAN)

            height, width = frame.shape[:2]
            for hand in tracked:
                is_primary = hand.role == "PRIMARY"
                draw_robotic_hand(
                    frame,
                    hand.landmarks,
                    accent=NEON_PINK if is_primary else NEON_PURPLE,
                    progress=gesture_confidence if (is_primary and active_hardware) else 0.0,
                    ring_color=ring_color,
                    locked=is_primary and active_hardware and gesture_confidence >= 1.0,
                    t=now,
                    label=f"{hand.role}/{hand.handedness}",
                )
                if is_primary:
                    tip = hand.landmarks[8]
                    trail.emit(int(tip.x * width), int(tip.y * height), NEON_PINK)
            trail.update_draw(frame, dt_safe)

            if active_hardware and current_gesture == stabilizer.last and gesture_confidence >= 1.0:
                label = config.GESTURE_LABELS.get(ginfo["command"], ginfo["command"])
                usable = self.link.online or self.link.simulate
                if usable:
                    if previous_command != label:
                        previous_command = label
                        blocked_label = None
                        result = self.router.execute(ginfo["command"], source=f"gesture:{current_gesture}")
                        if not result.get("duplicate"):
                            transmit_fx.trigger(core_point, esp_point, color=ring_color)
                elif blocked_label != label:
                    blocked_label = label
                    self.audio.play("warning")
                    self.events.emit("warn", "ESP32 OFFLINE - cmd blocked", color="red")
            elif not active_hardware:
                blocked_label = None
                if ginfo and ginfo["command"] == "DISPLAY" and gesture_confidence >= 1.0:
                    self.router.handle_stable_gesture(current_gesture)

            self._drain_link_results()
            transmit_fx.update_draw(frame)

            flash_boost = 0.0
            if gesture_flash_t0 is not None:
                fdt = now - gesture_flash_t0
                if fdt < 0.6:
                    flash_boost = ease_out_cubic(1 - fdt / 0.6) * 0.5
                else:
                    gesture_flash_t0 = None

            draw_live_hud(
                frame,
                {
                    "now": now,
                    "link": self.link,
                    "audio": self.audio,
                    "fps": fps,
                    "hand_count": hand_count,
                    "current_gesture": current_gesture,
                    "gesture_confidence": gesture_confidence,
                    "ring_color": ring_color,
                    "active_cmd": active_hardware,
                    "fingers": fingers,
                    "smoothed_servo": smoothed_servo,
                    "events": self.events.recent(6),
                    "eye": eye_payload,
                    "show_help": show_help,
                    "dashboard_url": self._dashboard_url,
                    "estop": self.router.estop,
                    "extended": self.router.extended,
                    "flash_boost": flash_boost,
                },
            )

            if shot_requested:
                shot_requested = False
                try:
                    config.CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
                    path = config.CAPTURE_DIR / time.strftime("aura_%Y%m%d_%H%M%S.png")
                    cv2.imwrite(str(path), frame)
                    self.events.emit("info", "SCREENSHOT SAVED", color="cyan")
                    log.info("Screenshot saved: %s", path)
                except Exception as error:
                    self.events.emit("error", "SCREENSHOT FAILED", color="red")
                    log.error("Screenshot error: %s", error)
                self.audio.play("shutter")
                shot_flash_t0 = now
            if shot_flash_t0 is not None:
                sdt = now - shot_flash_t0
                if sdt < 0.18:
                    a = 0.6 * (1 - sdt / 0.18)
                    cv2.addWeighted(np.full_like(frame, 255), a, frame, 1 - a, 0, frame)
                else:
                    shot_flash_t0 = None

            secondary = next((h for h in tracked if h.role == "SECONDARY"), None)
            self.state.update(
                camera_ok=camera_ok,
                camera_index=self.camera.index,
                vision_ok=self.hands.ready,
                eye_enabled=self.eyes.enabled,
                eye_status=eye_payload["status"],
                eye_confidence=eye_payload["confidence"],
                eyes_open=None if not eye_payload["detected"] else eye_payload["status"] == "EYES OPEN",
                blink=eye_payload["blink"],
                hands=hand_count,
                hand_roles=[{"role": h.role, "handedness": h.handedness, "gesture": h.gesture} for h in tracked],
                gesture=current_gesture,
                gesture_confidence=gesture_confidence,
                finger_status=[
                    {"name": n, "up": bool(fingers[i]) if i < len(fingers) else None}
                    for i, n in enumerate(FINGER_NAMES)
                ],
                secondary_fingers=(
                    [{"name": n, "up": bool(secondary.fingers[i])} for i, n in enumerate(FINGER_NAMES)]
                    if secondary
                    else []
                ),
                servo={k: round(v, 1) for k, v in smoothed_servo.items()},
                fps=round(fps, 1),
                extended=self.router.extended,
                demo=self.link.simulate,
                simulated=self.link.simulate,
                esp32_online=self.link.online,
                esp32_ip=self.link.ip,
                esp32_reconnecting=self.link.reconnecting,
                led=self.link.led_state,
                latency_ms=self.link.latency_ms,
                latency_hist=list(self.link.latency_hist),
                estop=self.router.estop,
                last_command=self.router.last_result,
            )
            self._publish_jpeg(frame)
            cv2.imshow(config.WINDOW_NAME, frame)
            key = cv2.waitKey(1) & 0xFF
            if cv2.getWindowProperty(config.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
            if key == ord("q"):
                self.audio.play("power_down")
                time.sleep(0.6)
                break
            if key == ord("r"):
                stabilizer.reset()
                previous_command = None
                blocked_label = None
                self.router.reset_lock()
                self.audio.play("reset")
                self.events.emit("info", "SYSTEM RESET", color="yellow")
            elif key == ord("m"):
                self.audio.toggle_mute()
            elif key in (ord("+"), ord("=")):
                self.audio.change_volume(0.1)
                self.events.emit("info", f"VOLUME {int(self.audio.volume * 100)}%")
            elif key in (ord("-"), ord("_")):
                self.audio.change_volume(-0.1)
                self.events.emit("info", f"VOLUME {int(self.audio.volume * 100)}%")
            elif key == ord("h"):
                show_help = not show_help
                self.audio.play("click")
            elif key == ord("e"):
                self.router.set_extended(not self.router.extended)
                previous_command = None
                self.audio.play("click")
                self.events.emit("info", "EXTENDED " + ("ON" if self.router.extended else "OFF"), color="cyan")
            elif key == ord("d"):
                self.link.set_simulate(not self.link.simulate)
                previous_command = None
                self.audio.play("reconnect" if self.link.simulate else "click")
                self.events.emit("info", "DEMO MODE " + ("ON" if self.link.simulate else "OFF"), color="yellow")
            elif key == ord("s"):
                shot_requested = True
            elif key == ord("f"):
                fullscreen = not fullscreen
                cv2.setWindowProperty(
                    config.WINDOW_NAME,
                    cv2.WND_PROP_FULLSCREEN,
                    cv2.WINDOW_FULLSCREEN if fullscreen else cv2.WINDOW_NORMAL,
                )

    def _drain_link_results(self, force_audio: bool = False) -> None:
        while True:
            try:
                label, ok, err = self.link.results.get_nowait()
            except queue.Empty:
                break
            if label == "__lost__":
                self.audio.play("warning")
                self.events.emit("warn", "WARNING: ESP32 LINK LOST", color="red")
                self.router.clear_command_lock()
            elif label == "__reconnected__":
                self.audio.play("reconnect")
                self.events.emit("ok", f"ESP32 RECONNECTED {self.link.ip}")
            elif ok:
                self.audio.play(SOUND_FOR_LABEL.get(label, "click"))
                self.events.emit("ok", f"{label} confirmed{' (simulated)' if self.link.simulate else ''}")
                self.router.last_result = {
                    "ok": True,
                    "label": label,
                    "simulated": self.link.simulate,
                    "error": None,
                }
            else:
                self.audio.play("warning")
                self.events.emit("error", f"{label} FAILED" + (f" ({err})" if err else ""), color="red")
                self.router.last_result = {
                    "ok": False,
                    "label": label,
                    "simulated": self.link.simulate,
                    "error": err or "device did not confirm",
                }
                self.router.clear_command_lock()

    def _apply_queued_actions(self, stabilizer: GestureStabilizer) -> None:
        while True:
            try:
                kind, payload = self._actions.get_nowait()
            except queue.Empty:
                break
            if kind != "settings" or not isinstance(payload, dict):
                continue
            if "demo" in payload:
                self.link.set_simulate(bool(payload["demo"]))
            if "extended" in payload:
                self.router.set_extended(bool(payload["extended"]))
            if "muted" in payload:
                self.audio.set_muted(bool(payload["muted"]))
            if "volume" in payload:
                self.audio.set_volume(float(payload["volume"]))
            if "gesture_frames" in payload:
                stabilizer.set_required(int(payload["gesture_frames"]))
            if "eye_tracking" in payload:
                want = bool(payload["eye_tracking"])
                if want and not self.eyes.ready:
                    self.eyes.start()
                self.eyes.enabled = want and self.eyes.ready
            if "camera_index" in payload:
                idx = int(payload["camera_index"])
                if idx != self.camera.index:
                    self.camera.reopen(idx)
            if "mapping" in payload and isinstance(payload["mapping"], dict):
                g = str(payload["mapping"].get("gesture", ""))
                c = str(payload["mapping"].get("command", ""))
                ok, msg = self.router.set_mapping(g, c)
                self.events.emit("info" if ok else "error", msg)
            self.audio.play("click")
            self.events.emit("info", "SETTINGS UPDATED", color="cyan")

    def _publish_jpeg(self, frame) -> None:
        now = time.time()
        if now - self._last_jpeg_t < 1.0 / max(1, config.STREAM_MAX_FPS):
            return
        self._last_jpeg_t = now
        ok, buf = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), config.STREAM_JPEG_QUALITY],
        )
        if ok:
            self.state.set_jpeg(buf.tobytes())

    def shutdown(self) -> None:
        log.info("Shutting down...")
        self._stop.set()
        self.state.update(running=False)
        if self.web:
            self.web.stop()
        self.link.stop()
        self.audio.close()
        self.camera.release()
        self.hands.close()
        self.eyes.close()
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
        log.info("AURA SYSTEM SHUTDOWN.")
