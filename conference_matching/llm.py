from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")


def _ollama_available() -> bool:
    try:
        urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2)
        return True
    except Exception:
        return False


def compose_query_from_payload(payload: dict[str, Any]) -> str:
    """Same text union the matcher uses for intent and retrieval focus."""
    parts: list[str] = []
    for key in ("notes", "headline", "q"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    asks_raw = payload.get("asks")
    if isinstance(asks_raw, str) and asks_raw.strip():
        parts.append(asks_raw.strip())
    elif isinstance(asks_raw, list):
        parts.extend(str(item).strip() for item in asks_raw if str(item).strip())
    return " ".join(parts).strip()


def _truncate(text: str, limit: int = 320) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def llm_rerank_and_explain(
    query: str,
    matches: list[dict[str, Any]],
    query_profile: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Use a local LLM to add a short, evidence-grounded relevance line for each top result."""
    if not matches or not _ollama_available():
        return matches
    if not (query or "").strip():
        return matches

    top = matches[:5]
    intent = (query_profile or {}).get("search_intent", "mixed")
    sectors_hint = ", ".join(str(s) for s in (query_profile or {}).get("sectors", [])[:6])

    for m in top:
        name = m.get("name", "")
        role = m.get("role", "")
        entity_type = m.get("entity_type", "")
        org = m.get("organization", "")
        sectors = ", ".join(m.get("sectors", [])[:4])
        tags = ", ".join((m.get("tags") or [])[:4])
        bio = _truncate(str(m.get("bio", "")), 280)
        score = m.get("score", 0)
        engine_lines = m.get("explanation") or []
        if isinstance(engine_lines, str):
            engine_lines = [engine_lines]
        engine_hint = " ".join(str(line) for line in engine_lines[:2])

        prompt = (
            "You explain why an ATTENDEE profile matches a search query at a single large conference (e.g. GTC). "
            "Use ONLY the fields below—do not invent employers, paper titles, or sessions not hinted in the text.\n\n"
            f'User query: "{query}"\n'
            f"Match focus: {intent} (this app ranks people; agenda wording may appear inside bios/tags).\n"
        )
        if sectors_hint:
            prompt += f"Query sectors/themes (from profile): {sectors_hint}\n"
        prompt += (
            "\nResult row:\n"
            f"- kind: {entity_type} (role={role})\n"
            f"- name: {name}\n"
            f"- organization/venue: {org}\n"
            f"- sectors: {sectors}\n"
            f"- tags/events: {tags}\n"
            f"- bio snippet: {bio}\n"
            f"- match score (0–1-ish blend): {score}\n"
        )
        if engine_hint:
            prompt += f"- retrieval notes: {engine_hint}\n"
        prompt += (
            "\nWrite ONE sentence (max 45 words). Tie the match to interests, role, major, registered sessions "
            "mentioned in the profile, or sector overlap—never invent facts. "
            "If the fit is weak, say so briefly. Match the user query language when it is Chinese; otherwise English.\n"
            "Reply with only that sentence."
        )

        body = json.dumps(
            {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.12, "num_predict": 120},
            }
        ).encode()

        try:
            req = urllib.request.Request(
                f"{OLLAMA_URL}/api/generate",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=300) as resp:
                reason = json.loads(resp.read()).get("response", "").strip()
            if reason:
                m["llm_reason"] = reason
        except Exception as exc:
            print("LLM Error:", exc)

    return top + matches[5:]
