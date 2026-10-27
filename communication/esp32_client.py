"""Background HTTP client for the ESP32. Never call from the video thread."""

from __future__ import annotations

import json
import queue
import threading
import time
import urllib.error
import urllib.request
from collections import deque

import config
from communication.device_discovery import discover_esp32
from communication.simulator import VirtualESP32
from services.logger import log


class Esp32Client:
    def __init__(self, simulate: bool = False) -> None:
        self.ip = config.ESP32_IP
        self.online = False
        self.led_state = "OFF"
        self.simulate = simulate
        self.latency_ms: float | None = None
        self.latency_hist: deque[float] = deque(maxlen=60)
        self.results: queue.Queue[tuple[str, bool, str | None]] = queue.Queue()
        self.simulator = VirtualESP32()
        self.reconnecting = False
        self._cmds: queue.Queue[tuple[str, str, str | None]] = queue.Queue(maxsize=8)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._fails = 0
        self._lock = threading.Lock()

    def set_simulate(self, enabled: bool) -> None:
        with self._lock:
            self.simulate = enabled
            if enabled:
                self.reconnecting = False

    def discover(self, timeout: float = 3.0, verbose: bool = True) -> bool:
        ip = discover_esp32(timeout=timeout, verbose=verbose)
        if ip:
            self.ip = ip
            return True
        return False

    def request(self, path: str, timeout: float | None = None) -> tuple[str | None, float | None]:
        if not self.ip:
            return None, None
        timeout = config.HTTP_TIMEOUT if timeout is None else timeout
        url = f"http://{self.ip}:{config.ESP32_HTTP_PORT}{path}"
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                body = response.read().decode("utf-8", errors="ignore")
            return body, (time.perf_counter() - t0) * 1000.0
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return None, None

    def post_json(self, path: str, payload: dict, timeout: float) -> tuple[int, str | None]:
        if not self.ip:
            return 0, None
        url = f"http://{self.ip}:{config.ESP32_HTTP_PORT}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = response.read().decode("utf-8", errors="ignore")
                return int(response.status), body
        except urllib.error.HTTPError as error:
            return int(error.code), None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return 0, None

    def _record(self, ms: float | None) -> None:
        if ms is not None:
            self.latency_ms = ms
            self.latency_hist.append(ms)

    def verify(self) -> bool:
        body, ms = self.request("/status")
        if body and "AURA LINK" in body and "ESP32" in body and "ONLINE" in body:
            self.online = True
            self._record(ms)
            if "LED=" in body:
                token = body.split("LED=", 1)[1].split("|", 1)[0].strip()
                if token in {"ON", "OFF", "BLINK"}:
                    self.led_state = token
            return True
        return False

    def send(self, label: str, path: str, led: str | None = None) -> None:
        if self.simulate:
            cmd_key = {
                "LED ON": "LED_ON",
                "LED OFF": "LED_OFF",
                "LED BLINK": "LED_BLINK",
                "E-STOP": "E_STOP",
            }.get(label, label)
            ok, state = self.simulator.execute(cmd_key)
            if ok:
                self.led_state = state
            self.results.put((label, ok, None if ok else "simulator rejected command"))
            return
        if not self.online:
            self.results.put((label, False, "ESP32 offline"))
            return
        try:
            self._cmds.put_nowait((label, path, led))
        except queue.Full:
            self.results.put((label, False, "command queue full"))

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._worker, name="aura-esp32", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.5)
            self._thread = None

    def _drop(self) -> None:
        if self.online:
            self.online = False
            self.latency_ms = None
            self.results.put(("__lost__", False, "link lost"))

    def _worker(self) -> None:
        last_heartbeat = time.time()
        last_retry = 0.0
        while not self._stop.is_set():
            try:
                label, path, led = self._cmds.get(timeout=0.25)
            except queue.Empty:
                label = None

            if label is not None:
                body, ms = self.request(path)
                if body is not None:
                    self._fails = 0
                    self._record(ms)
                    if led:
                        self.led_state = led
                    self.results.put((label, True, None))
                else:
                    self._fails += 1
                    if self._fails >= 2:
                        self._drop()
                    self.results.put((label, False, "no HTTP response"))
                continue

            now = time.time()
            if self.simulate:
                self.reconnecting = False
                continue
            if self.online and now - last_heartbeat >= config.HEARTBEAT_SECONDS:
                last_heartbeat = now
                if self.verify():
                    self._fails = 0
                    self.reconnecting = False
                else:
                    self._fails += 1
                    if self._fails >= 3:
                        self._drop()
            elif not self.online and now - last_retry >= config.RECONNECT_SECONDS:
                last_retry = now
                self.reconnecting = True
                found = (self.ip and self.verify()) or (
                    self.discover(1.5, verbose=False) and self.verify()
                )
                if found:
                    self._fails = 0
                    self.reconnecting = False
                    self.results.put(("__reconnected__", True, None))

    def provision_wifi(self, ssid: str, password: str, device_ip: str | None = None) -> tuple[bool, str]:
        """Forward credentials to firmware. Password is never logged or stored."""
        target = (device_ip or config.PROVISION_DEFAULT_IP).strip()
        if not _valid_ipv4(target):
            return False, "Invalid ESP32 address."
        if not _valid_ssid(ssid):
            return False, "SSID must be 1-32 characters."
        if len(password) > 63:
            return False, "Password is too long."
        previous_ip = self.ip
        self.ip = target
        status, body = self.post_json(
            "/wifi/config",
            {"ssid": ssid, "password": password},
            timeout=config.PROVISION_TIMEOUT,
        )
        self.ip = previous_ip
        if status == 200:
            return True, "Credentials sent. The ESP32 will reconnect to Wi-Fi. Password was not stored."
        if status == 400:
            return False, "ESP32 rejected the network name or password format."
        if status == 0:
            return False, (
                f"No response from {target}. Connect this PC to the ESP32 setup "
                "access point, or enter the device IP shown on the firmware serial log."
            )
        return False, f"ESP32 returned HTTP {status}."


def _valid_ipv4(value: str) -> bool:
    parts = value.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(p) <= 255 for p in parts)
    except ValueError:
        return False


def _valid_ssid(ssid: str) -> bool:
    return 1 <= len(ssid) <= 32
