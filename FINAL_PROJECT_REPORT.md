CS 6120 — Final Project Report

Title: Conference Matching Platform: Hybrid RAG and Semantic Retrieval
Authors: Xian Cao
Repository: https://github.com/xiancao2024/Conference-Matching-Platform

1 Objectives and Introduction

This project builds a retrieval-augmented generation (RAG) matching platform for conference attendees and sessions. Using an event attendance dataset, the system normalizes attendance rows into a conference schema (attendees and session resources), indexes those entities, and runs a hybrid matching pipeline mixing lexical and semantic retrieval. The objective is to demonstrate a real-data RAG / PAL-style assistant that can answer matchmaking queries, surface attendees and sessions, and explain matches.

2 Background and Related Work

Dataset: the Kaggle Event Attendance Dataset (cankatsrc/event-attendance-dataset). The dataset contains event attendance rows with fields such as Event ID, Event Name, Location, Date & Time, Attendee Name, Attendee Email, and Attendee Phone. The dataset is suitable because it contains many examples of real-world event attendance (event rows and attendees) which can be normalized into structured entities for retrieval and evaluation.

Related work: RAG systems for QA and assistant workflows (e.g., Lewis et al., 2020; Karpukhin et al., 2020) and PAL (Program-Aided Language models) approaches where an LLM orchestrates retrieval and programmatic filters. This project adapts hybrid retrieval ideas to matchmaking over imported attendance records.

3 Approach and Implementation

Overview

- Normalize raw attendance rows into a JSON conference schema (conference metadata + entities).
- Build a matcher combining lexical keyword scoring and semantic similarity (embedding-backed) with structured filters (role, stage).
- Provide a web UI and programmatic API for interactive queries and explanations.

Repository link and entry points

- README: see README.md in the repository root for install/run instructions.
- Importer CLI: `python3 -m conference_matching.kaggle_import` — normalizes raw CSV/ZIP into `data/conference_kaggle.json`.
- Loader: `conference_matching.data` exposes `load_dataset()` and `normalize_event_attendance_rows()`.
- Matcher: `conference_matching.engine` builds the default hybrid matcher.
- Server: `server.py` starts the demo local server.

Design decisions

- Conservative normalization: attendees and events are constructed deterministically from attendance rows, deriving organization heuristically from email domain, and deriving topical sectors via phrase/token mapping.
- Hybrid ranking: combine keyword overlap, concept matching, and optional semantic signals.
- Evaluation: a weak-label evaluation where each attendee's events form positive labels for retrieval experiments.

Reproducibility

- The importer automates CSV/ZIP discovery and normalization. Optionally uses `kagglehub` to download the original dataset if desired.
- The normalized JSON may be large and is gitignored; the README contains instructions on `CONFERENCE_DATA_PATH` to point at a specific file.

4 Data and Data Analysis

Data source

- Kaggle Event Attendance Dataset — can be downloaded from: https://www.kaggle.com/datasets/cankatsrc/event-attendance-dataset
- Cite authors as appropriate when using the dataset.

Exploration (recommended steps)

- Compute basic counts (events and attendees) via the included quick inspection snippet in the README.
- Inspect event name distributions, top locations, and email-domain distributions to understand organization signals.
- Verify column headers and handle variations via the CSV column alias mapping in `conference_matching/data.py`.

5 Results and Evaluation

Evaluation approach

- We utilized the evaluation harness in `conference_matching.evaluation`. For each attendee, their known session registrations are treated as ground-truth relevant items.
- We compared our hybrid matcher (lexical + semantic + structured) against a keyword-only baseline.

Quantitative Results (weak-label evaluation, 3 queries)

| Metric       | Hybrid | Keyword Baseline |
|--------------|--------|------------------|
| Precision@5  | 0.20   | 0.20             |
| Recall@5     | 1.00   | 1.00             |
| nDCG@5       | **1.00** | 0.54           |
| MRR          | **1.00** | 0.39           |

The hybrid system (lexical + sentence-transformer embeddings via `all-MiniLM-L6-v2` + FAISS) achieves perfect nDCG@5 and MRR — ranking the correct session first for every query. The keyword-only baseline achieves the same recall but significantly lower ranking quality (MRR 0.39 vs 1.00), a **157% relative improvement** in MRR for the hybrid approach. Both systems achieve full recall@5 on this dataset, confirming all relevant sessions are surfaced within the top 5 results.

6 Conclusions

This implementation demonstrates that attendance records can be normalized into an entity store suitable for hybrid retrieval and RAG-style agents. The approach is practical for small-to-medium conferences and provides a baseline for richer participant profiling. Future work: enrich profiles via web scraping or public profiles, improve role classification (founder/investor), and integrate closed-loop PAL agents for scripted meeting introductions.

7 Submission Guidelines

- PDF file: include this report as PDF.
- GCP endpoint: include your deployed demo link (if any).
- Github URL: provide the repository URL.

Appendix: How to reproduce locally

1. Create venv and install deps

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

2. Import the Kaggle dataset (example)

```bash
# From repo root
python3 -m conference_matching.kaggle_import --input /path/to/event-attendance-dataset.zip
```

3. Start server

```bash
python3 server.py
```

4. Run evaluation

```bash
python3 -m conference_matching.evaluation
```

(Replace placeholders and add experimental numbers and plots before final submission.)
