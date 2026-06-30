"""Vercel serverless function — https://<domain>/api/health"""
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
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
