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


def llm_rerank_and_explain(query: str, matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Use a local LLM to add a natural language explanation to each top result."""
    if not matches or not _ollama_available():
        return matches

    top = matches[:5]

    for i, m in enumerate(top):
        name = m.get("name", "")
        role = m.get("role", "")
        sectors = ", ".join(m.get("sectors", [])[:3])
        prompt = (
            f'Query: "{query}"\n'
            f'Result: name="{name}", role={role}, topics={sectors}\n\n'
            f'In one sentence, explain why this result is or is not relevant to the query. '
            f'Reply with just the sentence, no extra text.'
        )

        payload = json.dumps({
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2},
        }).encode()

        try:
            req = urllib.request.Request(
                f"{OLLAMA_URL}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=300) as resp:
                reason = json.loads(resp.read()).get("response", "").strip()
            if reason:
                m["llm_reason"] = reason
        except Exception as e:
            print("LLM Error:", e)

    return top + matches[5:]
