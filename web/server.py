"""Local dashboard HTTP server (stdlib). Default bind is 127.0.0.1."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import config
from services.logger import log
from web.api import parse_command_body, wifi_payload

WEB_ROOT = Path(__file__).resolve().parent
MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


class DashboardServer:
    def __init__(self, controller, host: str = "127.0.0.1", port: int = 8080) -> None:
        self.controller = controller
        self.host = host
        self.port = port
        handler = _make_handler(controller)
        self.httpd = ThreadingHTTPServer((host, port), handler)
        self.httpd.daemon_threads = True
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self.httpd.serve_forever, name="aura-web", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        try:
            self.httpd.shutdown()
            self.httpd.server_close()
        except Exception as error:
            log.warning("Dashboard stop: %s", error)


def _make_handler(controller):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            log.debug("HTTP " + fmt, *args)

        def _client_is_local(self) -> bool:
            host = self.client_address[0]
            return host in {"127.0.0.1", "::1", "localhost"}

        def _authorized(self) -> bool:
            if not controller.bind_requires_token():
                return True
            token = self.headers.get("X-Aura-Token")
            return controller.dashboard_token_ok(token)

        def _json(self, code: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> tuple[dict | None, str | None]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return None, "invalid content length"
            if length > config.API_MAX_BODY:
                return None, "payload too large"
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return None, "invalid JSON"
            if not isinstance(data, dict):
                return None, "JSON object required"
            return data, None

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.send_header("Allow", "GET, POST, OPTIONS")
            origin = self.headers.get("Origin", "")
            if origin.startswith("http://127.0.0.1") or origin.startswith("http://localhost"):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.end_headers()

        def do_GET(self) -> None:
            if not self._authorized():
                self._json(401, {"ok": False, "error": "missing or invalid X-Aura-Token"})
                return
            parsed = urlparse(self.path)
            path = parsed.path
            if path in {"/", "/index.html"}:
                self._file(WEB_ROOT / "templates" / "index.html")
                return
            if path.startswith("/static/"):
                rel = path[len("/static/") :]
                target = (WEB_ROOT / "static" / rel).resolve()
                try:
                    target.relative_to((WEB_ROOT / "static").resolve())
                except ValueError:
                    self._json(404, {"ok": False, "error": "not found"})
                    return
                self._file(target)
                return
            if path == "/api/state":
                self._json(200, {"ok": True, "state": controller.public_state()})
                return
            if path == "/api/cameras":
                self._json(200, {"ok": True, "cameras": controller.list_cameras()})
                return
            if path == "/stream/mjpeg":
                self._mjpeg()
                return
            self._json(404, {"ok": False, "error": "not found"})

        def do_POST(self) -> None:
            if not self._authorized():
                self._json(401, {"ok": False, "error": "missing or invalid X-Aura-Token"})
                return
            parsed = urlparse(self.path)
            path = parsed.path
            payload, err = self._read_json()
            if err:
                self._json(400, {"ok": False, "error": err})
                return
            assert payload is not None
            if path == "/api/command":
                command, err = parse_command_body(payload)
                if err:
                    self._json(400, {"ok": False, "error": err})
                    return
                result = controller.api_command(command, source="dashboard")
                code = 200 if result.get("ok") or result.get("pending") else 409
                self._json(code, {"ok": bool(result.get("ok")), **result})
                return
            if path == "/api/emergency-stop":
                result = controller.emergency_stop()
                self._json(200, {"ok": True, **result})
                return
            if path == "/api/settings":
                ok, message = controller.apply_settings(payload)
                self._json(200 if ok else 429, {"ok": ok, "message": message})
                return
            if path == "/api/wifi/provision":
                data, err = wifi_payload(payload)
                if err:
                    self._json(400, {"ok": False, "error": err})
                    return
                assert data is not None
                ok, message = controller.provision_wifi(
                    data["ssid"], data["password"], data["device_ip"] or None
                )
                self._json(200 if ok else 502, {"ok": ok, "message": message})
                return
            if path == "/api/shutdown":
                if not self._client_is_local():
                    self._json(403, {"ok": False, "error": "shutdown only from localhost"})
                    return
                controller.request_stop()
                self._json(200, {"ok": True, "message": "shutdown requested"})
                return
            self._json(404, {"ok": False, "error": "not found"})

        def _file(self, path: Path) -> None:
            if not path.is_file():
                self._json(404, {"ok": False, "error": "not found"})
                return
            data = path.read_bytes()
            mime = MIME.get(path.suffix.lower(), "application/octet-stream")
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def _mjpeg(self) -> None:
            self.send_response(200)
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            try:
                while True:
                    jpeg = controller.latest_jpeg()
                    if jpeg:
                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode("ascii"))
                        self.wfile.write(jpeg)
                        self.wfile.write(b"\r\n")
                    time.sleep(1.0 / max(1, config.STREAM_MAX_FPS))
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                return

    return Handler
