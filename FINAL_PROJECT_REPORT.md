# CS 6120 - Final Project Report

**Title**: Conference Matching Platform: Hybrid Retrieval over Real Attendance Data  
**Authors**: Xian Cao  
**Repository**: [https://github.com/xiancao2024/Conference-Matching-Platform](https://github.com/xiancao2024/Conference-Matching-Platform)

---

## 1 Objectives and Introduction

Large conferences create two linked discovery problems: participants need help finding relevant sessions, and they also need help identifying other attendees with overlapping interests. This project builds a conference matching platform that works directly on real attendance logs instead of on hand-authored profile cards.

The current system is centered on the public Kaggle Event Attendance Dataset (`cankatsrc/event-attendance-dataset`). Raw CSV rows are normalized into a conference schema with attendee entities and event/session entities. On top of that normalized data, the platform provides a hybrid retrieval engine, a local web interface, weak-label evaluation, and an optional local LLM layer for conversational responses and lightweight result explanations.

The main goal is practical rather than purely generative: accept natural-language requests such as "find climate attendees" or "show AI sessions", map them into a retrieval query, and rank the most relevant imported entities using lexical, conceptual, structural, and optional embedding-based evidence.

## 2 Background and Related Work

**Dataset context.** The Kaggle Event Attendance Dataset contains noisy operational records rather than curated user profiles. Typical fields include event identifiers, event names, locations, timestamps, attendee names, emails, and phone numbers. This makes the task interesting because useful matchmaking signals must be inferred from sparse event metadata rather than read from rich biographies.

**Related work.** The project is inspired by hybrid retrieval systems used in modern search and RAG pipelines. Instead of retrieving document passages for question answering, this system retrieves structured entities representing attendees and event resources. The implementation combines sparse lexical matching, concept expansion through a small ontology, structured boosts, and optional dense retrieval with Sentence Transformers plus FAISS.

## 3 Approach and Implementation

### 3.1 Data ingestion and normalization

The import pipeline accepts a Kaggle zip file, a CSV file, or an extracted directory. It searches for the best matching CSV using column alias rules, reads attendance rows, and writes a normalized JSON dataset.

Normalization produces two entity types:

- **Attendees**: role `participant`, with name, inferred organization, sector tags, asks/offers, and the list of source events they attended.
- **Events**: stored as `resource` entities with role `session`, with name, location, date metadata, attendee counts, and inferred topical sectors.

Several fields are derived heuristically:

- organization is inferred from email domains
- sectors and tags are inferred from event names and locations through phrase and token mappings
- attendee bios and event bios are synthesized from imported attendance history

This design keeps the pipeline robust even though the source dataset does not contain explicit founder/investor labels or rich self-descriptions.

### 3.2 Hybrid retrieval engine

The matcher in `conference_matching/engine.py` builds an index over normalized entities and scores them with several signals:

- **Lexical similarity**: TF-IDF-style cosine similarity over normalized tokens
- **Concept similarity**: ontology-driven concept overlap, such as mapping "health AI" to healthcare and AI concepts
- **Structured score**: boosts for role fit, sector fit, stage fit, ask/offer overlap, and intent fit
- **Optional embedding score**: dense similarity from `all-MiniLM-L6-v2` when local embeddings and FAISS are available

The final score is a weighted combination of lexical, concept, embedding, and structured components. For topical people-search queries, the matcher also applies a stricter filter: if the user is searching for people and mentions explicit topics/events, attendees must show topic evidence and, in some cases, event-link evidence through their `source_events`.

The system also exposes a keyword-only baseline used for evaluation.

### 3.3 Query routing and web application

`conference_matching/server.py` provides a lightweight HTTP server and routes requests into four modes:

- empty query
- greeting/thanks
- general question
- retrieval request

General questions are answered through the optional local Ollama integration in `conference_matching/llm.py`. Retrieval requests are converted into a structured query profile and passed to the matcher. The browser client then renders ranked session and attendee cards with short summaries.

An important implementation detail is that the deterministic engine already produces rule-based explanations. If Ollama is available, the system also adds an extra one-sentence `llm_reason` to the top retrieved items, but retrieval itself does not depend on the LLM.

### 3.4 Code organization

- `conference_matching/data.py`: dataset discovery, CSV loading, normalization, and dataset access
- `conference_matching/kaggle_import.py`: CLI entrypoint for import
- `conference_matching/ontology.py`: phrase/token concept mappings and role aliases
- `conference_matching/engine.py`: indexing, scoring, ranking, explanations, and keyword baseline
- `conference_matching/llm.py`: optional Ollama-based general answers and top-result explanations
- `conference_matching/evaluation.py`: weak-label benchmark construction and ranking metrics
- `conference_matching/server.py`: local API and static file server

## 4 Data and Analysis

**Data source**:

- Kaggle: [https://www.kaggle.com/datasets/cankatsrc/event-attendance-dataset](https://www.kaggle.com/datasets/cankatsrc/event-attendance-dataset)

The source data is intentionally limited. It tells us who attended which event, but not why they attended, what role they play professionally, or what they are explicitly looking for. Because of that, the project leans on conservative inference rather than aggressive hallucinated enrichment.

The main analytical choices are:

- treat attendance as the strongest observed relation in the dataset
- infer topical sectors from event metadata rather than from nonexistent biographies
- keep all entities in one searchable space so attendee and session results can be ranked together

This makes the project a good example of retrieval over weakly structured real data rather than over idealized benchmark data.

## 5 Results and Evaluation

### 5.1 Evaluation methodology

The evaluation module builds weak labels directly from attendance history. Each attendee becomes a query, and the sessions/events they are known to have attended become the relevant set. The system then compares:

- the full hybrid matcher
- a keyword-only baseline

Metrics reported are Precision@5, Recall@5, nDCG@5, and Mean Reciprocal Rank (MRR).

### 5.2 Quantitative results

The repository already includes an evaluation snapshot in `eval_output.json` for a 3-query benchmark fixture:

| Metric | Hybrid Matcher | Keyword Baseline | Relative Improvement |
| --- | --- | --- | --- |
| Precision@5 | 0.20 | 0.20 | 0% |
| Recall@5 | 1.00 | 1.00 | 0% |
| nDCG@5 | 1.0000 | 0.5436 | +83.9% |
| MRR | 1.0000 | 0.3889 | +157.1% |

### 5.3 Interpretation

Both systems reach perfect Recall@5 on this small fixture because the relevant event is usually somewhere in the top five results. The more meaningful difference is ranking quality: the hybrid system consistently places the relevant event first, while the keyword baseline often ranks the attendee record itself above the matching event.

That pattern matches the current implementation. The hybrid model benefits from concept expansion, structured intent scoring, and optional dense similarity, while the keyword baseline only sees surface token overlap.

## 6 Limitations and Future Work

The project still inherits strong limits from the source dataset:

- attendee roles are inferred heuristically rather than observed directly
- asks/offers are synthetic placeholders derived from attendance context
- quality depends on topic mappings in the ontology and on event naming quality
- embedding support is optional and depends on local model/index availability

Promising next steps are:

1. Add richer benchmark sets with manually judged relevance, not only weak labels.
2. Distinguish more event types and attendee intents beyond the current participant/session framing.
3. Expand the frontend to expose score breakdowns and evaluation views directly in the UI.
4. Add safer profile enrichment pipelines only where external evidence is explicit and attributable.

## 7 Reproducibility and Submission Info

- **GCP Endpoint**: [http://34.169.130.58:8000](http://34.169.130.58:8000)
- **GitHub URL**: [https://github.com/xiancao2024/Conference-Matching-Platform](https://github.com/xiancao2024/Conference-Matching-Platform)

### Local reproduction

**1. Create a virtual environment and install dependencies**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

**2. Import the Kaggle dataset**

```bash
python3 -m conference_matching.kaggle_import --input /path/to/event-attendance-dataset.zip
```

Or, if using `kagglehub`:

```bash
.venv/bin/python -m pip install kagglehub
.venv/bin/python -m conference_matching.kaggle_import
```

**3. Start the server**

```bash
.venv/bin/python server.py
```

**4. Run evaluation**

```bash
.venv/bin/python -m conference_matching.evaluation
```

**5. Run tests**

```bash
.venv/bin/python -m unittest discover -s tests
```
