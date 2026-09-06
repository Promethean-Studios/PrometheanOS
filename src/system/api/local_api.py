from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event
from typing import Any, Dict, Optional

from src.system.services.promethean_service import PrometheanService


CONTROL_CENTER_ROOT = Path(__file__).resolve().parents[2] / "desktop" / "control-center"


class PrometheanRequestHandler(BaseHTTPRequestHandler):
    server_version = "PrometheanLocalAPI/0.1"

    def do_GET(self):
        if self.path == "/health":
            self._send_json(self.server.service.status())
            return

        if self.path == "/status":
            self._send_json(self.server.service.snapshot())
            return

        if self.path == "/telemetry":
            self._send_json(self.server.service.snapshot())
            return

        if self.path == "/permissions":
            self._send_json(self.server.service.get_permissions())
            return

        parsed = urlparse(self.path)
        if parsed.path == "/control-center" or parsed.path.startswith("/control-center/"):
            self._send_control_center(parsed.path)
            return

        if parsed.path == "/models":
            self._send_json({"models": self.server.service.get_models()})
            return

        if parsed.path == "/models/recommend":
            name = parse_qs(parsed.query).get("name", [None])[0]
            profile = parse_qs(parsed.query).get("profile", ["balanced"])[0]
            model = next((item for item in self.server.service.model_manager.discover() if item.name == name), None)
            if model is None:
                self.send_error(404, "Model not found")
                return
            self._send_json(self.server.service.recommend_model(model, profile))
            return

        self.send_error(404, "Not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/models/launch":
            self.send_error(404, "Not found")
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, UnicodeDecodeError):
            self.send_error(400, "Request body must be JSON")
            return
        result = self.server.service.model_manager.launch(str(payload.get("name", "")))
        self._send_json(result, status=200 if result.get("ok") else 422)

    def log_message(self, format, *args):
        return

    def _send_json(self, payload: Dict[str, Any], status: int = 200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_control_center(self, request_path: str):
        relative = request_path.removeprefix("/control-center/") if request_path != "/control-center" else "index.html"
        candidate = (CONTROL_CENTER_ROOT / unquote(relative)).resolve()
        try:
            candidate.relative_to(CONTROL_CENTER_ROOT.resolve())
        except ValueError:
            self.send_error(404, "Not found")
            return
        if not candidate.is_file():
            self.send_error(404, "Not found")
            return
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        body = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class LocalPrometheanAPI:
    def __init__(self, service: Optional[PrometheanService] = None, host: str = "127.0.0.1", port: int = 8765):
        self.service = service or PrometheanService()
        self.host = host
        self.port = port
        self._server = None
        self._ready = Event()

    def serve_forever(self):
        self._server = ThreadingHTTPServer((self.host, self.port), PrometheanRequestHandler)
        self._server.service = self.service
        self._ready.set()
        self._server.serve_forever()

    def wait_until_ready(self, timeout: float = 5.0):
        return self._ready.wait(timeout)

    def shutdown(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        self._ready.clear()
