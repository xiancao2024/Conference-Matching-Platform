from __future__ import annotations

import argparse
import json
import os
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .engine import build_default_matcher
from .evaluation import evaluate
from .llm import compose_query_from_payload, llm_rerank_and_explain


REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_ROOT = REPO_ROOT / "static"
MATCHER = None
_matcher_ready = threading.Event()
_matcher_load_error: BaseException | None = None


def _load_matcher_worker() -> None:
    global MATCHER, _matcher_load_error
    try:
        MATCHER = build_default_matcher()
    except BaseException as exc:
        _matcher_load_error = exc
    finally:
        _matcher_ready.set()


def get_matcher():
    _matcher_ready.wait()
    if _matcher_load_error is not None:
        raise _matcher_load_error
    assert MATCHER is not None
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
        if route == "/api/attendee":
            qs = parse_qs(urlparse(self.path).query)
            raw_id = (qs.get("id") or [None])[0]
            if not raw_id:
                self.send_error(HTTPStatus.BAD_REQUEST, "Missing query parameter id")
                return
            record = get_matcher().attendee_public_record(raw_id.strip())
            if record is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Attendee not found")
                return
            self._send_json({"attendee": record})
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
        query_text = compose_query_from_payload(payload)
        result["matches"] = llm_rerank_and_explain(
            query_text,
            result.get("matches", []),
            result.get("query_profile"),
        )
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
    explicit = os.environ.get("CONFERENCE_DATA_PATH")
    if explicit:
        path = Path(explicit)
        if not path.exists():
            hint = (
                "Expected a normalized dataset JSON (set CONFERENCE_DATA_PATH). "
                "For GTC profiles: "
                "`python3 -m conference_matching.gtc_import --input <wide.csv> --output data/conference_gtc.json`. "
                "For Kaggle attendance: "
                "`python3 -m conference_matching.kaggle_import --input <zip-or-csv>`."
            )
            raise SystemExit(f"Configured CONFERENCE_DATA_PATH does not exist: {path}\n{hint}")

    threading.Thread(target=_load_matcher_worker, name="matcher-init", daemon=True).start()
    print(
        "Matcher initializing in background (large datasets / embeddings may take several minutes)...",
        flush=True,
    )
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
