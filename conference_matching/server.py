from __future__ import annotations

import argparse
import json
import os
import re
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .engine import build_default_matcher
from .evaluation import evaluate
from .llm import llm_answer_general, llm_rerank_and_explain


REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_ROOT = REPO_ROOT / "static"
MATCHER = None
GREETING_PATTERN = re.compile(r"^\s*(hi|hello|hey|yo|sup|good morning|good afternoon|good evening)\b[!.? ]*$", re.I)
THANKS_PATTERN = re.compile(r"^\s*(thanks|thank you)\b[!.? ]*$", re.I)
GENERAL_QUESTION_PATTERN = re.compile(
    r"^\s*(what|how|why|when|where|who|can you explain|explain|define|tell me about)\b",
    re.I,
)
PEOPLE_HINTS = ("attendee", "attendees", "people", "person", "peer", "peers", "who", "meet", "connected")
SESSION_HINTS = ("session", "sessions", "event", "events", "schedule", "talk", "talks", "workshop", "panel")
RETRIEVAL_VERBS = ("find", "show", "search", "list", "match", "recommend", "surface", "look up")
SECTOR_HINTS = (
    ("health tech", "healthcare"),
    ("healthtech", "healthcare"),
    ("medtech", "healthcare"),
    ("biotech", "healthcare"),
    ("health ai", "healthcare"),
    ("health ai", "artificial intelligence"),
    ("ai", "artificial intelligence"),
    ("machine learning", "artificial intelligence"),
    ("health", "healthcare"),
    ("medical", "healthcare"),
    ("climate", "climate"),
    ("sustainability", "climate"),
    ("community", "community"),
    ("network", "community"),
    ("customer", "customer discovery"),
    ("startup", "entrepreneurship"),
    ("founder", "entrepreneurship"),
    ("invest", "fundraising"),
)


def get_matcher():
    global MATCHER
    if MATCHER is None:
        MATCHER = build_default_matcher()
    return MATCHER


def _query_mode(query_text: str) -> str:
    normalized = query_text.strip().lower()
    if not normalized:
        return "empty"
    if GREETING_PATTERN.match(normalized) or THANKS_PATTERN.match(normalized):
        return "greeting"

    has_people_hint = any(token in normalized for token in PEOPLE_HINTS)
    has_session_hint = any(token in normalized for token in SESSION_HINTS)
    has_retrieval_verb = any(token in normalized for token in RETRIEVAL_VERBS)

    if has_people_hint or has_session_hint or has_retrieval_verb:
        return "retrieval"
    if GENERAL_QUESTION_PATTERN.match(normalized) or normalized.endswith("?"):
        return "general"
    return "general"


def _detect_sectors(query_text: str) -> list[str]:
    normalized = query_text.lower()
    sectors: list[str] = []
    for needle, sector in SECTOR_HINTS:
        if needle in normalized and sector not in sectors:
            sectors.append(sector)
    return sectors


def _build_retrieval_query(query_text: str) -> dict[str, object]:
    normalized = query_text.lower()
    people_first = any(token in normalized for token in PEOPLE_HINTS)
    session_only = any(token in normalized for token in SESSION_HINTS) and not people_first

    if people_first:
        looking_for = ["peers"]
        target_roles = ["participant"]
    elif session_only:
        looking_for = ["sessions"]
        target_roles = ["session"]
    else:
        looking_for = ["sessions", "peers"]
        target_roles = ["participant", "session"]

    return {
        "role": "participant",
        "stage": "all",
        "looking_for": looking_for,
        "target_roles": target_roles,
        "sectors": _detect_sectors(query_text),
        "asks": query_text,
        "notes": query_text,
        "q": query_text,
    }


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
        matcher = get_matcher()
        query_text = str(payload.get("query") or payload.get("raw_query") or payload.get("notes") or payload.get("headline") or "").strip()
        mode = _query_mode(query_text)

        if mode == "empty":
            self._send_json(
                {
                    "conference": matcher.options().get("conference", {}),
                    "query_mode": mode,
                    "assistant_text": "Ask about attendees, event sessions, or a general conference topic.",
                    "matches": [],
                }
            )
            return

        if mode == "greeting":
            self._send_json(
                {
                    "conference": matcher.options().get("conference", {}),
                    "query_mode": mode,
                    "assistant_text": "Hi. I can search imported attendees and event sessions, or answer general questions about conference topics.",
                    "matches": [],
                }
            )
            return

        if mode == "general":
            answer = llm_answer_general(query_text, matcher.options().get("conference", {}))
            self._send_json(
                {
                    "conference": matcher.options().get("conference", {}),
                    "query_mode": mode,
                    "assistant_text": answer
                    or "I can answer general questions, but the local LLM is unavailable right now. I can still search the imported attendee and event data.",
                    "matches": [],
                }
            )
            return

        retrieval_payload = _build_retrieval_query(query_text) if query_text else payload
        result = matcher.match(retrieval_payload)
        result["query_mode"] = mode
        result["assistant_text"] = f'I searched the imported conference data for "{query_text}".'
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
