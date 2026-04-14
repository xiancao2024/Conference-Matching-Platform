from __future__ import annotations

import argparse
import json
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .engine import build_default_matcher
from .evaluation import evaluate
from .llm import llm_rerank_and_explain


REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_ROOT = REPO_ROOT / "static"
MATCHER = None


def get_matcher():
    global MATCHER
    if MATCHER is None:
        MATCHER = build_default_matcher()
    return MATCHER


class ConferenceRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_ROOT), **kwargs)

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route == "/api/conference":
            self._send_json(get_matcher().options())
            return
        if route == "/api/evaluate":
            self._send_json(evaluate())
            return
        if route == "/" or route == "":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        if route != "/api/match":
            self.send_error(HTTPStatus.NOT_FOUND, "Route not found")
            return
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON body")
            return
        result = get_matcher().match(payload)
        query_text = payload.get("notes") or payload.get("headline") or ""
        result["matches"] = llm_rerank_and_explain(query_text, result.get("matches", []))
        self._send_json(result)

    def log_message(self, format: str, *args) -> None:
        return

    def _send_json(self, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _resolve_host_port(host: str | None = None, port: int | None = None) -> tuple[str, int]:
    resolved_host = host or os.environ.get("HOST", "127.0.0.1")
    resolved_port = port or int(os.environ.get("PORT", "8000"))
    return resolved_host, resolved_port


def run(host: str | None = None, port: int | None = None) -> None:
    resolved_host, resolved_port = _resolve_host_port(host, port)
    try:
        get_matcher()
    except FileNotFoundError as exc:
        raise SystemExit(
            "No imported Kaggle dataset is available yet. "
            "Run `python3 -m conference_matching.kaggle_import --input <zip-or-csv>` first."
        ) from exc
    server = ThreadingHTTPServer((resolved_host, resolved_port), ConferenceRequestHandler)
    print(f"Conference matching demo listening on http://{resolved_host}:{resolved_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the conference matching demo server.")
    parser.add_argument("--host", default=None, help="Host interface to bind. Defaults to HOST env var or 127.0.0.1.")
    parser.add_argument("--port", type=int, default=None, help="Port to bind. Defaults to PORT env var or 8000.")
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    run(host=args.host, port=args.port)
