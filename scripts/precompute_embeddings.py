#!/usr/bin/env python3
"""
Precompute embeddings and FAISS index for the conference dataset.

Writes to `repo/data/`:
 - `embeddings.npy` (numpy array of vectors)
 - `faiss.index` (if faiss supports writing on the host)
 - `entity_ids.json` (list of entity ids in same order as vectors)
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np

from conference_matching.engine import ConferenceMatcher


def main() -> None:
    out_dir = Path(__file__).resolve().parent.parent / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    matcher = ConferenceMatcher()
    if not getattr(matcher, "_has_embeddings", False):
        print("Embeddings not available (sentence-transformers/faiss missing).")
        return

    embeddings = getattr(matcher, "_embeddings", None)
    faiss_index = getattr(matcher, "_faiss_index", None)
    if embeddings is None:
        print("No embeddings found on matcher.")
        return

    np.save(out_dir / "embeddings.npy", embeddings)

    try:
        import faiss

        if faiss_index is not None:
            faiss.write_index(faiss_index, str(out_dir / "faiss.index"))
    except Exception as exc:  # pragma: no cover - optional environment-specific
        print("Failed to write faiss index:", exc)

    entity_ids = [ie.entity["id"] for ie in matcher.entities]
    with open(out_dir / "entity_ids.json", "w", encoding="utf-8") as handle:
        json.dump(entity_ids, handle, indent=2)

    print("Wrote embeddings.npy, faiss.index (if possible), and entity_ids.json to", out_dir)


if __name__ == "__main__":
    main()
