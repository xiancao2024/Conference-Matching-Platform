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

from conference_matching.data import conference_entities


def main() -> None:
    import os
    data_path = os.environ.get("CONFERENCE_DATA_PATH", str(Path(__file__).resolve().parent.parent / "data" / "conference_kaggle.json"))
    out_dir = Path(data_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    from sentence_transformers import SentenceTransformer
    import faiss

    print("Loading entities...", flush=True)
    entities = conference_entities(data_path)
    print(f"Loaded {len(entities)} entities.", flush=True)

    def _flatten(e: dict) -> str:
        skip = {"id","conference_id","contact_email","contact_phone","source_label","source_dataset","source_type"}
        parts = []
        for k, v in e.items():
            if k in skip:
                continue
            if isinstance(v, str):
                parts.append(v)
            elif isinstance(v, list):
                parts.extend(str(x) for x in v)
        return " ".join(parts)

    texts = [_flatten(e) for e in entities]
    entity_ids = [e["id"] for e in entities]

    print("Loading model...", flush=True)
    model = SentenceTransformer("all-MiniLM-L6-v2")

    print(f"Encoding {len(texts)} entities (batch_size=512)...", flush=True)
    vecs = np.array(
        model.encode(texts, normalize_embeddings=True, batch_size=512, show_progress_bar=True),
        dtype="float32",
    )

    emb_path = out_dir / "embeddings.npy"
    np.save(str(emb_path), vecs)
    print(f"Saved {emb_path}", flush=True)

    idx_path = out_dir / "faiss.index"
    index = faiss.IndexFlatIP(vecs.shape[1])
    index.add(vecs)
    faiss.write_index(index, str(idx_path))
    print(f"Saved {idx_path}", flush=True)

    with open(out_dir / "entity_ids.json", "w", encoding="utf-8") as f:
        json.dump(entity_ids, f)
    print(f"Done. Wrote {len(vecs)} embeddings to {out_dir}", flush=True)


if __name__ == "__main__":
    main()
