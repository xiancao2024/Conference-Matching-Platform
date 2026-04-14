from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")


def _ollama_available() -> bool:
    try:
        urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2)
        return True
    except Exception:
        return False


def llm_rerank_and_explain(query: str, matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Use llama3 to rerank matches and add a natural language explanation to each result."""
    if not matches or not _ollama_available():
        return matches

    top = matches[:5]
    candidates = "\n".join(
        f"{i+1}. name={m['name']}, role={m['role']}, org={m['organization']}, "
        f"sectors={','.join(m.get('sectors',[])[:2])}, score={m['score']}"
        for i, m in enumerate(top)
    )

    prompt = (
        f"A user searched a conference database with query: \"{query}\"\n\n"
        f"Here are the top candidate matches:\n{candidates}\n\n"
        f"For each candidate, write one sentence explaining why it is or is not relevant to the query. "
        f"Reply ONLY as a JSON array of objects with keys \"rank\" (1-based int) and \"reason\" (string). "
        f"Example: [{\"rank\":1,\"reason\":\"...\"}]"
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
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = json.loads(resp.read()).get("response", "").strip()
        # extract JSON array from response
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start == -1 or end == 0:
            return matches
        items = json.loads(raw[start:end])
        rank_map = {item["rank"]: item["reason"] for item in items if "rank" in item and "reason" in item}
        for i, m in enumerate(top):
            reason = rank_map.get(i + 1)
            if reason:
                m["llm_reason"] = reason
        return top + matches[5:]
    except Exception:
        return matches
