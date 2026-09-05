from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event
from typing import Any, Dict, Optional

from src.system.services.promethean_service import PrometheanService


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

        self.send_error(404, "Not found")

    def log_message(self, format, *args):
        return

    def _send_json(self, payload: Dict[str, Any]):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
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
