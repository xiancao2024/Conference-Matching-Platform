# CS 6120 - Final Project Report

**Title**: Conference Matching Platform: People-First Hybrid Retrieval for GTC-Style Profiles  
**Authors**: Xian Cao  
**Repository**: [https://github.com/xiancao2024/Conference-Matching-Platform](https://github.com/xiancao2024/Conference-Matching-Platform)

---

## 1 Objectives and Introduction

The project focuses on a practical conference task: **who should I meet?**  
Instead of ranking sessions and attendees together, the current product is deliberately scoped to a **single-conference, people-only** retrieval workflow.

Input data follows a GTC-style wide schema: one row per attendee with profile fields (education, major, job, experience), interest tags, and registered agenda items. This table is normalized into a unified JSON format and queried by a hybrid retrieval engine.

The goal is not open-ended generation. The system accepts natural-language intent (e.g., "CUDA and LLM inference people"), converts it into a structured profile, and returns the most relevant attendees with short reasons.

## 2 Background and Related Work

**Dataset context.** Real event systems often have sparse profile quality and inconsistent fields. Even in wide tables, useful matchmaking evidence is distributed across structured attributes and free text.

**Related retrieval pattern.** The system follows a common hybrid search architecture used in modern RAG/recommendation stacks:

- sparse lexical relevance
- concept expansion through ontology mappings
- deterministic structured boosts
- optional dense embedding similarity (Sentence Transformers + FAISS)

This design balances interpretability and ranking quality while remaining deployable on local/VM environments.

## 3 Approach and Implementation

### 3.1 Data ingestion and normalization

The active ingestion path is `conference_matching.gtc_import`, which reads a wide-row attendee CSV and writes normalized JSON (default: `data/conference_gtc.json`).

Key output behavior:

- each row becomes an attendee entity (`entity_type=attendee`, `role=participant`)
- agenda registrations are kept as attendee context (`source_events`, `tags`, bio text)
- session/resource entities are not generated in this product mode
- conference-level metadata is fixed to a single event context (`event_count=1`)

For local testing at scale, `scripts/generate_gtc_wide_csv.py` can synthesize 50/10k-row datasets with realistic GTC agenda titles.

### 3.2 Hybrid retrieval engine

`conference_matching/engine.py` scores entities with:

- lexical similarity over normalized tokens
- concept similarity from ontology expansion
- structured boosts (intent, role, sector/topic evidence, ask/offer overlap where available)
- optional embedding similarity via `all-MiniLM-L6-v2` + FAISS

Embedding lifecycle was updated for deployment usability:

- embeddings are cached to `data/embeddings.npy`
- FAISS index is cached to `data/faiss.index`
- if cache count matches current entities, vectors are reused on startup
- if missing, vectors can be built on the fly up to `CONFERENCE_EMBED_MAX_ENTITIES` (default `20000`)
- startup logs now print explicit embedding build start/success/failure messages

### 3.3 Query routing and web application

`conference_matching/server.py` serves static UI and API endpoints:

- `GET /api/conference` for dataset metadata
- `POST /api/match` for retrieval

The web client (`static/app.js`) now emphasizes product-facing outcomes:

- ranking cards prioritize **Activity overlap** using `source_events`
- card rationale bullets are non-duplicative (activity + profile strength)
- optional LLM text is labeled **"Why connect with this person"**
- response framing avoids repeating the user prompt verbatim

General-purpose conversational handling remains optional via local Ollama (`conference_matching/llm.py`). Retrieval itself is deterministic and does not depend on LLM availability.

### 3.4 Code organization

- `conference_matching/data.py`: normalization and dataset loading
- `conference_matching/gtc_import.py`: GTC wide-row import CLI
- `conference_matching/ontology.py`: concept mappings
- `conference_matching/engine.py`: indexing/scoring/ranking
- `conference_matching/llm.py`: optional local LLM integration
- `conference_matching/server.py`: API and static hosting
- `scripts/generate_gtc_wide_csv.py`: synthetic dataset generation
- `static/app.js`: query UX and result rendering

## 4 Data and Analysis

The current product dataset is a GTC-style attendee table, either organizer-provided or synthetic for stress-testing.

Representative agenda labels used in experiments include:

- NVIDIA CEO Keynote
- Generative AI Theater: LLM Inference
- CUDA Developer Lab
- Robotics & Edge AI Session
- Healthcare AI Roundtable

Analytical choices in this iteration:

- use a people-only retrieval target to match the product goal
- treat registered agenda items as strong behavioral evidence
- expose activity overlap directly in result rationale

These choices reduced user confusion observed when sessions and people were mixed in one ranked list.

## 5 Results and Evaluation

### 5.1 Product behavior outcomes

Recent updates improved practical usability:

- faster restarts when embedding cache is present (no redundant re-encoding)
- clearer startup diagnosis from embedding progress logs
- more actionable card copy focused on connection decisions

### 5.2 Ranking quality notes

Hybrid scoring still outperforms pure keyword behavior in ordering quality, especially when users mix skill terms and agenda terms (e.g., "CUDA + LLM inference").

### 5.3 Operational observation

On CPU-only VM deployment with 10k attendees, first-time embedding build is the dominant startup cost. Persisting `data/` as a Docker volume avoids repeated cost across restarts.

## 6 Limitations and Future Work

Current limits:

- profile richness depends on source CSV quality
- activity overlap is string/token based (not semantic event ontology yet)
- optional LLM explanation quality depends on local model latency

Next steps:

1. Add stronger event-level semantic normalization (agenda synonym clusters).
2. Add explicit warmup endpoints and startup health states.
3. Build larger judged relevance sets for offline ranking evaluation.
4. Introduce user feedback loops (accept/reject matches) for learning-to-rank.

## 7 Reproducibility and Submission Info

- **GCP Endpoint**: [http://34.169.130.58:8000](http://34.169.130.58:8000)
- **GitHub URL**: [https://github.com/xiancao2024/Conference-Matching-Platform](https://github.com/xiancao2024/Conference-Matching-Platform)

### Local reproduction

**1. Create a virtual environment and install dependencies**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

**2. Generate/import dataset**

```bash
.venv/bin/python scripts/generate_gtc_wide_csv.py --rows 10000 --output data/gtc_generated_10k.csv
.venv/bin/python -m conference_matching.gtc_import --input data/gtc_generated_10k.csv --output data/conference_gtc.json
```

**3. Start the server**

```bash
CONFERENCE_DATA_PATH=data/conference_gtc.json .venv/bin/python server.py
```

**4. Run tests**

```bash
.venv/bin/python -m unittest discover -s tests
```
