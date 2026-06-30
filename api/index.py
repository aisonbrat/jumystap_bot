"""
Vercel serverless function — https://<domain>/api

Uses BaseHTTPRequestHandler (official Vercel Python pattern).
Do NOT use FastAPI here — it is unreliable on @vercel/python.
"""
import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from vercel_app import handle_http


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        status, payload = handle_http("GET", self.path, b"", dict(self.headers))
        self._send_json(status, payload)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        status, payload = handle_http("POST", self.path, body, dict(self.headers))
        self._send_json(status, payload)

    def log_message(self, fmt: str, *args) -> None:
        # Log to Vercel runtime logs
        sys.stderr.write("%s - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), fmt % args))

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
