from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import Any

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")


def _ollama_available() -> bool:
    try:
        urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2)
        return True
    except Exception:
        return False


def summarize_matches(query: str, matches: list[dict[str, Any]]) -> str | None:
    """Call Ollama llama3 to generate a natural language summary of top matches."""
    if not matches or not _ollama_available():
        return None

    top = matches[:4]
    items = "\n".join(
        f"{i+1}. {m['name']} ({m['role']}) at {m['organization']} — "
        f"sectors: {', '.join(m.get('sectors', [])[:2]) or 'general'}. "
        f"{(m.get('explanation') or [''])[0]}"
        for i, m in enumerate(top)
    )

    prompt = (
        f"A user searched a conference database for: \"{query}\"\n\n"
        f"The top matches found are:\n{items}\n\n"
        f"In 2-3 sentences, explain why these are good matches and what the user should do next. "
        f"Be concise and helpful."
    )

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }).encode()

    try:
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return result.get("response", "").strip()
    except Exception:
        return None
