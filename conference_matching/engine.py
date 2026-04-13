from __future__ import annotations

import math
import re
from collections import Counter
import numpy as np
from dataclasses import dataclass
from typing import Any

from .data import conference_entities, conference_metadata
from .ontology import CANONICAL_ROLE_ALIASES, PHRASE_TO_CONCEPT, STOPWORDS, TOKEN_TO_CONCEPT


TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9\-]+")

ROLE_COMPATIBILITY = {
    "founder": {
        "investor": 0.28,
        "mentor": 0.16,
        "participant": 0.13,
        "resource": 0.12,
        "session": 0.12,
        "founder": 0.07,
    },
    "investor": {
        "founder": 0.26,
        "mentor": 0.08,
        "participant": 0.08,
        "resource": 0.06,
        "session": 0.06,
    },
    "mentor": {
        "founder": 0.18,
        "participant": 0.12,
        "resource": 0.08,
        "session": 0.08,
        "investor": 0.06,
    },
    "participant": {
        "mentor": 0.16,
        "founder": 0.14,
        "resource": 0.12,
        "session": 0.12,
        "investor": 0.1,
        "participant": 0.08,
    },
    "resource": {
        "founder": 0.08,
        "participant": 0.08,
        "investor": 0.06,
    },
}

LOOKING_FOR_ROLE_MAP = {
    "funding": {"investor", "session", "resource"},
    "investors": {"investor"},
    "mentor": {"mentor"},
    "mentors": {"mentor"},
    "pilot partners": {"participant", "mentor", "resource", "session"},
    "pilot": {"participant", "mentor", "resource", "session"},
    "customers": {"participant", "mentor", "resource"},
    "bank partners": {"investor", "participant", "mentor", "resource"},
    "banking partners": {"investor", "participant", "mentor", "resource"},
    "warm introductions": {"participant", "mentor", "resource", "session"},
    "community": {"participant", "resource", "session"},
    "peers": {"founder", "participant"},
    "sessions": {"session", "resource"},
}

ALL_ROLES = ["founder", "investor", "mentor", "participant", "resource", "session"]


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().strip())


def _normalize_token(token: str) -> str:
    token = token.lower().strip("-")
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("s") and len(token) > 3 and not token.endswith("ss"):
        return token[:-1]
    return token


def _tokenize(text: str) -> list[str]:
    normalized = _normalize_text(text)
    tokens = [_normalize_token(match.group(0)) for match in TOKEN_PATTERN.finditer(normalized)]
    return [token for token in tokens if token not in STOPWORDS and len(token) > 1]


def _extract_concepts(text: str) -> list[str]:
    normalized = _normalize_text(text)
    concepts: list[str] = []
    for phrase, mapped in PHRASE_TO_CONCEPT.items():
        if phrase in normalized:
            concepts.extend(mapped)
    for token in _tokenize(normalized):
        concepts.extend(TOKEN_TO_CONCEPT.get(token, []))
    return concepts


def _flatten_values(entity: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in entity.items():
        if key in {
            "id",
            "conference_id",
            "contact_email",
            "contact_phone",
            "source_label",
            "source_dataset",
            "source_type",
            "raw_row_count",
            "attendee_count",
        }:
            continue
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(item) for item in value)
    return " ".join(parts)


def _cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    numerator = 0.0
    for key, value in left.items():
        numerator += value * right.get(key, 0.0)
    if numerator == 0:
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _idf_weight(num_docs: int, doc_freq: int) -> float:
    return math.log((1 + num_docs) / (1 + doc_freq)) + 1


def _weighted_counter(tokens: list[str], idf: dict[str, float]) -> Counter[str]:
    counts = Counter(tokens)
    weighted: Counter[str] = Counter()
    for token, count in counts.items():
        weighted[token] = count * idf.get(token, 1.0)
    return weighted


def _normalize_role(role: str) -> str:
    return CANONICAL_ROLE_ALIASES.get(role.strip().lower(), role.strip().lower())


def _normalize_list(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw_parts = re.split(r"[,;/\n]", values)
        return [part.strip() for part in raw_parts if part.strip()]
    if isinstance(values, list):
        return [str(item).strip() for item in values if str(item).strip()]
    return [str(values).strip()]


def _normalize_stage_label(value: str) -> str:
    lowered = value.lower().strip()
    if lowered in {"pre seed", "pre-seed", "preseed"}:
        return "pre-seed"
    if lowered in {"seriesa", "series a"}:
        return "series a"
    return lowered


def _build_query_text(query: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("headline", "notes", "asks", "offers", "looking_for", "sectors", "target_roles", "stage"):
        value = query.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif value:
            parts.append(str(value))
    return " ".join(parts)


def _infer_target_roles(query: dict[str, Any]) -> set[str]:
    explicit = {_normalize_role(role) for role in _normalize_list(query.get("target_roles"))}
    looking_for = {item.lower() for item in _normalize_list(query.get("looking_for"))}
    inferred = set(explicit)
    for item in looking_for:
        inferred.update(LOOKING_FOR_ROLE_MAP.get(item, set()))
    return {role for role in inferred if role in ALL_ROLES}


def _canonical_overlap(left: list[str], right: list[str]) -> list[str]:
    left_concepts = set()
    right_concepts = set()
    for value in left:
        left_concepts.update(_extract_concepts(value))
        left_concepts.update(_tokenize(value))
    for value in right:
        right_concepts.update(_extract_concepts(value))
        right_concepts.update(_tokenize(value))
    overlap = left_concepts & right_concepts
    return sorted(overlap)


def _adjacent_stages(query_stage: str) -> set[str]:
    if query_stage == "pre-seed":
        return {"pre-seed", "seed"}
    if query_stage == "seed":
        return {"pre-seed", "seed", "series a"}
    if query_stage == "series a":
        return {"seed", "series a"}
    return {query_stage}


@dataclass
class IndexedEntity:
    entity: dict[str, Any]
    lexical_tokens: list[str]
    lexical_vector: Counter[str]
    concept_vector: Counter[str]
    searchable_text: str


class ConferenceMatcher:
    def __init__(self, source: str | None = None) -> None:
        self.metadata = conference_metadata(source)
        raw_entities = conference_entities(source)
        doc_tokens = [_tokenize(_flatten_values(entity)) for entity in raw_entities]
        doc_concepts = [_extract_concepts(_flatten_values(entity)) for entity in raw_entities]
        lexical_df: Counter[str] = Counter()
        concept_df: Counter[str] = Counter()
        for tokens in doc_tokens:
            lexical_df.update(set(tokens))
        for concepts in doc_concepts:
            concept_df.update(set(concepts))
        self.lexical_idf = {token: _idf_weight(len(raw_entities), freq) for token, freq in lexical_df.items()}
        self.concept_idf = {token: _idf_weight(len(raw_entities), freq) for token, freq in concept_df.items()}
        self.entities: list[IndexedEntity] = []
        for entity, tokens, concepts in zip(raw_entities, doc_tokens, doc_concepts):
            searchable_text = _flatten_values(entity)
            self.entities.append(
                IndexedEntity(
                    entity=entity,
                    lexical_tokens=tokens,
                    lexical_vector=_weighted_counter(tokens, self.lexical_idf),
                    concept_vector=_weighted_counter(concepts, self.concept_idf),
                    searchable_text=searchable_text,
                )
            )
        # Optional semantic embeddings (sentence-transformers + faiss)
        self._has_embeddings = False
        try:
            from sentence_transformers import SentenceTransformer
            import faiss

            model_name = "all-MiniLM-L6-v2"
            self._embed_model = SentenceTransformer(model_name)
            texts = [ie.searchable_text for ie in self.entities]
            if texts:
                vecs = np.array(self._embed_model.encode(texts, normalize_embeddings=True), dtype="float32")
                dim = vecs.shape[1]
                index = faiss.IndexFlatIP(dim)
                index.add(vecs)
                self._faiss_index = index
                self._embeddings = vecs
                self._has_embeddings = True
        except Exception:
            # sentence-transformers or faiss not available; continue without embeddings
            self._has_embeddings = False

    def options(self) -> dict[str, Any]:
        sectors = sorted({sector for entity in self.entities for sector in entity.entity.get("sectors", [])})
        roles = sorted(
            {
                _normalize_role(entity.entity.get("role", "participant"))
                for entity in self.entities
                if _normalize_role(entity.entity.get("role", "participant")) not in {"resource", "session"}
            }
        )
        target_roles = sorted({_normalize_role(entity.entity.get("role", "participant")) for entity in self.entities})
        stages = sorted({stage for entity in self.entities for stage in entity.entity.get("stage", [])}) or ["all"]
        return {
            "conference": self.metadata,
            "roles": roles or ["participant"],
            "target_roles": target_roles or ["participant", "session"],
            "sectors": sectors,
            "stages": stages,
            "goals": [
                "sessions",
                "community",
                "peers",
                "warm introductions",
            ],
        }

    def keyword_search(self, query: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
        query_text = _build_query_text(query)
        query_tokens = _tokenize(query_text)
        query_vector = _weighted_counter(query_tokens, self.lexical_idf)
        ranked = []
        for indexed in self.entities:
            score = _cosine_similarity(query_vector, indexed.lexical_vector)
            ranked.append(self._result_payload(indexed, score, "keyword", {}, query))
        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked[:limit]

    def match(self, query: dict[str, Any], limit: int = 5) -> dict[str, Any]:
        normalized_query = {
            "conference_id": query.get("conference_id", self.metadata["id"]),
            "role": _normalize_role(query.get("role", "participant")),
            "stage": _normalize_stage_label(query.get("stage", "")) if query.get("stage") else "",
            "sectors": _normalize_list(query.get("sectors")),
            "looking_for": _normalize_list(query.get("looking_for")),
            "target_roles": list(_infer_target_roles(query)),
            "asks": _normalize_list(query.get("asks")),
            "offers": _normalize_list(query.get("offers")),
            "notes": query.get("notes", "").strip(),
            "headline": query.get("headline", "").strip(),
        }
        query_text = _build_query_text(normalized_query)
        query_tokens = _tokenize(query_text)
        query_concepts = _extract_concepts(query_text)
        query_lexical = _weighted_counter(query_tokens, self.lexical_idf)
        query_semantic = _weighted_counter(query_concepts, self.concept_idf)

        ranked = []
        for indexed in self.entities:
            breakdown = self._structured_score(normalized_query, indexed.entity)
            lexical_score = _cosine_similarity(query_lexical, indexed.lexical_vector)
            semantic_score = _cosine_similarity(query_semantic, indexed.concept_vector)
            embedding_score = 0.0
            if self._has_embeddings:
                try:
                    qvec = np.array(self._embed_model.encode([indexed.searchable_text], normalize_embeddings=True), dtype="float32")[0]
                    # compute dot with all embeddings if needed; faster to use index but we compute pairwise here
                    # compute cosine (dot since normalized)
                    # find corresponding vector by matching id - entities aligned with embeddings
                    # use index search for single vector
                    D, I = self._faiss_index.search(qvec.reshape(1, -1), 1)
                    embedding_score = float(D[0][0])
                except Exception:
                    embedding_score = 0.0
            # Combine scores: lexical, concept-based semantic, embedding-based semantic, and structured boosts
            total = lexical_score * 0.25 + semantic_score * 0.2 + embedding_score * 0.35 + breakdown["structured_total"]
            breakdown["lexical"] = round(lexical_score, 4)
            breakdown["semantic"] = round(semantic_score, 4)
            breakdown["embedding"] = round(embedding_score, 4)
            ranked.append(self._result_payload(indexed, total, "hybrid", breakdown, normalized_query))

        ranked.sort(key=lambda item: item["score"], reverse=True)
        keyword = self.keyword_search(normalized_query, limit=limit)
        return {
            "conference": self.metadata,
            "query_profile": normalized_query,
            "matches": ranked[:limit],
            "keyword_baseline": keyword,
        }

    def _structured_score(self, query: dict[str, Any], entity: dict[str, Any]) -> dict[str, float]:
        score = 0.0
        boosts = {
            "role_fit": 0.0,
            "sector_fit": 0.0,
            "stage_fit": 0.0,
            "ask_offer_fit": 0.0,
            "intent_fit": 0.0,
        }

        entity_role = _normalize_role(entity.get("role", "participant"))
        requester_role = _normalize_role(query.get("role", "participant"))
        target_roles = {_normalize_role(role) for role in query.get("target_roles", [])}
        if entity_role in target_roles:
            boosts["role_fit"] += 0.22
        boosts["role_fit"] += ROLE_COMPATIBILITY.get(requester_role, {}).get(entity_role, 0.0)

        sector_overlap = _canonical_overlap(query.get("sectors", []), entity.get("sectors", []) + entity.get("tags", []))
        if sector_overlap:
            boosts["sector_fit"] = min(0.18, 0.06 * len(sector_overlap))

        query_stage = query.get("stage", "")
        entity_stages = {_normalize_stage_label(stage) for stage in entity.get("stage", [])}
        if query_stage and query_stage in entity_stages:
            boosts["stage_fit"] = 0.09
        elif query_stage and (_adjacent_stages(query_stage) & entity_stages):
            boosts["stage_fit"] = 0.05

        ask_offer_overlap = _canonical_overlap(query.get("asks", []), entity.get("offers", []))
        offer_ask_overlap = _canonical_overlap(query.get("offers", []), entity.get("asks", []))
        boosts["ask_offer_fit"] = min(0.2, 0.05 * len(ask_offer_overlap) + 0.03 * len(offer_ask_overlap))

        looking_for = {item.lower() for item in query.get("looking_for", [])}
        if looking_for:
            for item in looking_for:
                mapped_roles = LOOKING_FOR_ROLE_MAP.get(item, set())
                if entity_role in mapped_roles:
                    boosts["intent_fit"] += 0.05
            if entity.get("entity_type") == "resource" and {"sessions", "warm introductions", "pilot partners"} & looking_for:
                boosts["intent_fit"] += 0.06
        boosts["intent_fit"] = min(boosts["intent_fit"], 0.18)

        for value in boosts.values():
            score += value
        boosts["structured_total"] = round(score, 4)
        return boosts

    def _result_payload(
        self,
        indexed: IndexedEntity,
        score: float,
        mode: str,
        breakdown: dict[str, float],
        query: dict[str, Any],
    ) -> dict[str, Any]:
        entity = indexed.entity
        payload = {
            "id": entity["id"],
            "name": entity["name"],
            "entity_type": entity["entity_type"],
            "role": entity["role"],
            "title": entity["title"],
            "organization": entity["organization"],
            "bio": entity["bio"],
            "sectors": entity.get("sectors", []),
            "stage": entity.get("stage", []),
            "offers": entity.get("offers", []),
            "asks": entity.get("asks", []),
            "tags": entity.get("tags", []),
            "score": round(score, 4),
            "mode": mode,
            "score_breakdown": breakdown,
            "explanation": self._explain(entity, query, breakdown),
        }
        return payload

    def _explain(self, entity: dict[str, Any], query: dict[str, Any], breakdown: dict[str, float]) -> list[str]:
        reasons: list[str] = []
        target_roles = {_normalize_role(role) for role in query.get("target_roles", [])}
        entity_role = _normalize_role(entity.get("role", "participant"))
        if entity_role in target_roles:
            reasons.append(f"Direct role fit: this {entity_role} matches the roles you said you want to meet.")

        sector_overlap = _canonical_overlap(query.get("sectors", []), entity.get("sectors", []) + entity.get("tags", []))
        if sector_overlap:
            reasons.append(
                "Shared themes: "
                + ", ".join(sector_overlap[:4])
                + " appear across your query and this profile."
            )

        ask_offer_overlap = _canonical_overlap(query.get("asks", []), entity.get("offers", []))
        if ask_offer_overlap:
            reasons.append(
                "Need-to-offer match: their offers line up with your asks around "
                + ", ".join(ask_offer_overlap[:4])
                + "."
            )

        query_stage = query.get("stage", "")
        entity_stages = {_normalize_stage_label(stage) for stage in entity.get("stage", [])}
        if query_stage and query_stage in entity_stages:
            reasons.append(f"Stage alignment: they actively work with {query_stage} teams.")
        elif query_stage and (_adjacent_stages(query_stage) & entity_stages):
            reasons.append("Stage adjacency: their focus is close to the stage you selected.")

        if entity.get("entity_type") == "resource":
            reasons.append("Resource fit: this session/resource can convert the match into an actual conference interaction.")

        if breakdown.get("semantic", 0.0) >= 0.18 and not sector_overlap:
            reasons.append("Semantic fit: the profile matches the intent of your query even where wording differs.")

        if not reasons:
            reasons.append("Relevant profile based on overall lexical and structured overlap with your search profile.")
        return reasons[:3]


def build_default_matcher(source: str | None = None) -> ConferenceMatcher:
    return ConferenceMatcher(source)
