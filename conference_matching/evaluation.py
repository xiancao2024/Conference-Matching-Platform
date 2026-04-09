from __future__ import annotations

import json
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


def _empty_metrics() -> dict[str, float]:
    return {"precision_at_5": 0.0, "recall_at_5": 0.0, "ndcg_at_5": 0.0, "mrr": 0.0}


def evaluate() -> dict[str, Any]:
    dataset = load_dataset()
    benchmarks = build_attendance_benchmarks(dataset)
    matcher = build_default_matcher()
    if not benchmarks:
        return {
            "summary": {"hybrid": _empty_metrics(), "keyword": _empty_metrics()},
            "rows": [],
            "note": "No weak-label evaluation queries could be built from the imported attendance data.",
            "query_count": 0,
        }

    rows = []
    systems = {"hybrid": [], "keyword": []}
    for benchmark in benchmarks:
        hybrid_results = matcher.match(benchmark["query"], limit=5)["matches"]
        keyword_results = matcher.keyword_search(benchmark["query"], limit=5)
        for system_name, results in (("hybrid", hybrid_results), ("keyword", keyword_results)):
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

    summary = {}
    for system_name, metrics in systems.items():
        summary[system_name] = {
            "precision_at_5": round(sum(item["precision_at_5"] for item in metrics) / len(metrics), 4),
            "recall_at_5": round(sum(item["recall_at_5"] for item in metrics) / len(metrics), 4),
            "ndcg_at_5": round(sum(item["ndcg_at_5"] for item in metrics) / len(metrics), 4),
            "mrr": round(sum(item["mrr"] for item in metrics) / len(metrics), 4),
        }
    return {
        "summary": summary,
        "rows": rows,
        "query_count": len(benchmarks),
        "note": "Weak-label evaluation uses each attendee's known session history as the relevant set.",
    }


def main() -> None:
    print(json.dumps(evaluate(), indent=2))


if __name__ == "__main__":
    main()
