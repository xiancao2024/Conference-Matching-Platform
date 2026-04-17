from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .data import load_dataset
from .engine import build_default_matcher


def precision_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    top_k = ranked_ids[:k]
    if not top_k:
        return 0.0
    return sum(1 for item in top_k if item in relevant_ids) / len(top_k)


def recall_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    return sum(1 for item in ranked_ids[:k] if item in relevant_ids) / len(relevant_ids)


def ndcg_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    gains = []
    for idx, item in enumerate(ranked_ids[:k], start=1):
        gain = 1.0 if item in relevant_ids else 0.0
        gains.append(gain / math_log2(idx + 1))
    dcg = sum(gains)
    ideal = sum(1.0 / math_log2(idx + 1) for idx in range(1, min(len(relevant_ids), k) + 1))
    if ideal == 0:
        return 0.0
    return dcg / ideal


def reciprocal_rank(ranked_ids: list[str], relevant_ids: set[str]) -> float:
    for idx, item in enumerate(ranked_ids, start=1):
        if item in relevant_ids:
            return 1.0 / idx
    return 0.0


def math_log2(value: float) -> float:
    import math

    return math.log2(value)


def build_attendance_benchmarks(dataset: dict[str, Any], limit: int = 25) -> list[dict[str, Any]]:
    entities = dataset.get("entities", [])
    sessions_by_name = {
        entity["name"]: entity
        for entity in entities
        if entity.get("role") == "session" and entity.get("entity_type") == "resource"
    }
    attendees = [entity for entity in entities if entity.get("entity_type") == "attendee"]

    benchmarks: list[dict[str, Any]] = []
    for attendee in attendees:
        source_events = attendee.get("source_events", [])
        relevant_ids = {sessions_by_name[name]["id"] for name in source_events if name in sessions_by_name}
        if not relevant_ids:
            continue
        benchmarks.append(
            {
                "name": attendee["name"],
                "query": {
                    "role": "participant",
                    "stage": "all",
                    "sectors": attendee.get("sectors", []),
                    "looking_for": ["sessions", "peers"],
                    "target_roles": ["session"],
                    "asks": source_events,
                    "offers": attendee.get("offers", []),
                    "notes": attendee.get("bio", ""),
                },
                "relevant_ids": relevant_ids,
            }
        )
        if len(benchmarks) >= limit:
            break
    return benchmarks


def build_gtc_people_benchmarks(dataset: dict[str, Any], limit: int = 50) -> list[dict[str, Any]]:
    """Weak labels for people-only GTC data: relevant = self + attendees who share any registered agenda title."""
    attendees = [e for e in dataset.get("entities", []) if e.get("entity_type") == "attendee"]
    benchmarks: list[dict[str, Any]] = []
    for att in attendees:
        if len(benchmarks) >= limit:
            break
        my_events = set(att.get("source_events") or [])
        if not my_events:
            continue
        relevant_ids: set[str] = {att["id"]}
        for other in attendees:
            if other["id"] == att["id"]:
                continue
            if my_events & set(other.get("source_events") or []):
                relevant_ids.add(other["id"])
        if len(relevant_ids) < 2:
            continue
        interests = att.get("asks") or []
        notes = (" ".join(str(x) for x in interests[:4]) + " " + " ".join(list(my_events)[:3])).strip()
        benchmarks.append(
            {
                "name": att["name"],
                "query": {
                    "role": "participant",
                    "stage": "all",
                    "looking_for": ["peers"],
                    "target_roles": ["participant"],
                    "search_intent": "people",
                    "sectors": (att.get("sectors") or [])[:6],
                    "asks": interests[:8],
                    "notes": notes,
                },
                "relevant_ids": relevant_ids,
            }
        )
    return benchmarks


def _dataset_has_session_entities(dataset: dict[str, Any]) -> bool:
    return any(
        e.get("entity_type") == "resource" or str(e.get("role", "")).lower() == "session"
        for e in dataset.get("entities", [])
    )


def build_benchmarks(dataset: dict[str, Any], limit: int = 50) -> tuple[list[dict[str, Any]], str]:
    if _dataset_has_session_entities(dataset):
        return build_attendance_benchmarks(dataset, limit=limit), "session_history"
    return build_gtc_people_benchmarks(dataset, limit=limit), "gtc_agenda_overlap"


def _empty_metrics() -> dict[str, float]:
    return {"precision_at_5": 0.0, "recall_at_5": 0.0, "ndcg_at_5": 0.0, "mrr": 0.0}


def evaluate() -> dict[str, Any]:
    dataset = load_dataset()
    benchmarks, label_mode = build_benchmarks(dataset)
    matcher = build_default_matcher()
    has_semantic = bool(matcher._has_embeddings and matcher._embeddings is not None)  # noqa: SLF001

    if not benchmarks:
        return {
            "summary": {"hybrid": _empty_metrics(), "keyword": _empty_metrics(), "semantic": _empty_metrics()},
            "rows": [],
            "note": "No weak-label evaluation queries could be built from the current dataset.",
            "query_count": 0,
            "benchmark_mode": label_mode,
            "semantic_available": has_semantic,
        }

    rows: list[dict[str, Any]] = []
    systems: dict[str, list[dict[str, Any]]] = {"hybrid": [], "keyword": [], "semantic": []}
    for benchmark in benchmarks:
        hybrid_results = matcher.match(benchmark["query"], limit=5)["matches"]
        keyword_results = matcher.keyword_search(benchmark["query"], limit=5)
        semantic_results = matcher.semantic_search(benchmark["query"], limit=5)
        for system_name, results in (
            ("hybrid", hybrid_results),
            ("keyword", keyword_results),
            ("semantic", semantic_results),
        ):
            ranked_ids = [item["id"] for item in results]
            relevant_ids = benchmark["relevant_ids"]
            row = {
                "query": benchmark["name"],
                "system": system_name,
                "precision_at_5": round(precision_at_k(ranked_ids, relevant_ids, 5), 4),
                "recall_at_5": round(recall_at_k(ranked_ids, relevant_ids, 5), 4),
                "ndcg_at_5": round(ndcg_at_k(ranked_ids, relevant_ids, 5), 4),
                "mrr": round(reciprocal_rank(ranked_ids, relevant_ids), 4),
                "top_matches": ranked_ids,
            }
            systems[system_name].append(row)
            rows.append(row)

    summary: dict[str, Any] = {}
    for system_name, metrics in systems.items():
        summary[system_name] = {
            "precision_at_5": round(sum(item["precision_at_5"] for item in metrics) / len(metrics), 4),
            "recall_at_5": round(sum(item["recall_at_5"] for item in metrics) / len(metrics), 4),
            "ndcg_at_5": round(sum(item["ndcg_at_5"] for item in metrics) / len(metrics), 4),
            "mrr": round(sum(item["mrr"] for item in metrics) / len(metrics), 4),
        }

    note = (
        "Hybrid combines lexical, ontology, structured boosts, and (when available) dense embeddings. "
        "Keyword search is sparse lexical cosine only (bag-of-tokens + IDF). "
        "Semantic search ranks solely by embedding cosine between the query text and each profile embedding."
    )
    if label_mode == "session_history":
        note += " Weak labels: each attendee's known session rows as relevant set."
    else:
        note += (
            " Weak labels (GTC): relevant attendees = query person plus anyone who shares at least one "
            "registered agenda title (source_events overlap)."
        )
    if not has_semantic:
        note += " Semantic row is empty when embeddings are unavailable."

    return {
        "summary": summary,
        "rows": rows,
        "query_count": len(benchmarks),
        "benchmark_mode": label_mode,
        "semantic_available": has_semantic,
        "note": note,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Weak-label retrieval evaluation (hybrid vs keyword vs semantic).")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write full JSON results to this path (e.g. eval_output.json).",
    )
    args = parser.parse_args()
    payload = evaluate()
    text = json.dumps(payload, indent=2)
    print(text)
    if args.output:
        args.output.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
