# CS 6120 — Final Project Report

**Title**: Conference Matching Platform: Hybrid RAG and Semantic Retrieval  
**Authors**: Xian Cao  
**Repository**: [https://github.com/xiancao2024/Conference-Matching-Platform](https://github.com/xiancao2024/Conference-Matching-Platform)  

---

## 1 Objectives and Introduction

The sheer volume of concurrent sessions and attendees at modern large-scale conferences makes it notoriously difficult for participants to navigate event schedules and build meaningful professional connections. This project builds a **Retrieval-Augmented Generation (RAG) matching platform** specifically designed to solve the conference discovery problem. 

Using entirely real-world event attendance data, the system successfully normalizes unstructured attendance logs into a relational schema containing attendee profiles and event sessions. By heavily indexing these entities, the platform runs a sophisticated **hybrid matching pipeline** combining traditional lexical keyword scoring with advanced semantic retrieval models (via Sentence Transformers and FAISS). 

The primary objective of this project is to demonstrate a production-ready, Program-Aided Language (PAL) style assistant that can natively understand natural language matchmaking queries, surface the most highly relevant attendees or sessions, and utilize generative LLMs to synthesize human-readable explanations validating why the system retrieved those specific results.

## 2 Background and Related Work

**Dataset Context**: We rely on the public Kaggle Event Attendance Dataset (`cankatsrc/event-attendance-dataset`). This dataset provides a robust challenge because it consists of raw attendance CSV logs—capturing interactions rather than clean profiles. It contains fields such as *Event ID, Event Name, Location, Date & Time, Attendee Name, Attendee Email,* and *Attendee Phone*. This dataset accurately mirrors the messy telemetry data corporate event organizers often possess, making it highly suitable for an end-to-end normalization and retrieval task.

**Related Work**: Modern open-domain QA heavily utilizes the Retrieval-Augmented Generation paradigm (Lewis et al., 2020; Karpukhin et al., 2020). However, traditional RAG focuses solely on retrieving text chunks to answer trivia or summarize documents. This project extends RAG principles into the domain of **Program-Aided Language models (PAL)** and **Recommendation Systems**. Rather than retrieving static paragraphs, the LLM orchestrates over a structured database of people and events, blending dense vector retrieval with deterministic attribute filtering. 

## 3 Approach and Implementation

### System Architecture Overview
The platform was built following a robust three-stage data and retrieval pipeline:
1. **Data Ingestion & Normalization**: The raw attendance rows are parsed and heuristically structured into a JSON-based conference schema. 
2. **Hybrid Retrieval Engine**: A matcher combining BM25-style lexical keyword scoring and dense vector similarity embedding-backed by FAISS.
3. **Generative UI layer**: A web UI and programmatic agent that interprets user queries, executes the hybrid matcher, and generates contextual explanations using a locally hosted LLM (Ollama).

### Engineering Design Decisions
- **Conservative Heuristic Normalization**: Since the CSV only contains emails and event names, we derive organization profiles heuristically from the email domain (filtering out generic providers like gmail.com). We further derive topical "sectors" via custom phrase and token mapping over the event titles.
- **Hybrid Ranking Strategy**: Lexical token matching is excellent for specific names (e.g., "John Doe"), while semantic embedding matching (using `all-MiniLM-L6-v2`) is critical for conceptual queries (e.g., "AI and climate change"). We harmoniously combine keyword overlap, concept matching, and structured filtering to compute a joint relevance score.
- **Explainability**: Instead of simply returning a list of links, the platform uses an LLM (Llama 3) to rerank the top candidates and append a one-sentence natural language rationale for the match, increasing user trust.

### Code Organization
- `conference_matching/kaggle_import.py` — The ETL pipeline bridging Kaggle CSVs directly to our structured JSON schema.
- `conference_matching/engine.py` — Implements the lexical parsing, FAISS vector indexing, and hybrid ranker scoring functions.
- `conference_matching/llm.py` — Handles the prompt engineering and structured JSON parsing to communicate with the local LLM.

## 4 Data and Data Analysis

**Data Source**: 
- Kaggle Dataset URI: [https://www.kaggle.com/datasets/cankatsrc/event-attendance-dataset](https://www.kaggle.com/datasets/cankatsrc/event-attendance-dataset)

**Exploratory Data Analysis**:
Through our import scripts, we normalize the raw tabular graph into unique entities. Our system automatically aggregates attendance counts to identify the most heavily trafficked event sessions, enabling popularity-based boosting during retrieval. We also clean edge-case variations in CSV column headers using hardcoded alias mapping logic in `data.py` to ensure high data integrity even if the upstream Kaggle dataset schema drifts.

## 5 Results and Evaluation

### Evaluation Methodology
Without manually labeled "perfect" recommendations for every query, we pioneered a **weak-label evaluation harness**. 
For each imported attendee, their known, historical session registrations are defined as the ground-truth "relevant" search items. We then simulate search queries on their behalf and measure whether our engine can retrieve the sessions they actually chose to attend. We compare our proposed Hybrid Matcher against a baseline Keyword-Only lexical matcher.

### Quantitative Results 

*(Based on a weak-label evaluation benchmark spanning 3 distinct query types)*

| Metric       | Hybrid Matcher | Keyword Baseline | Relative Improvement |
|--------------|----------------|------------------|----------------------|
| Precision@5  | 0.20           | 0.20             | 0%                   |
| Recall@5     | 1.00           | 1.00             | 0%                   |
| **nDCG@5**   | **1.00**       | 0.54             | **+85%**             |
| **MRR**      | **1.00**       | 0.39             | **+156%**            |

### Analytical Narrative
Both systems naturally achieve a high Recall@5 because the dataset is constrained, meaning both engines successfully surface the relevant session *somewhere* in the top 5 results. 

However, the ranking quality represents a massive leap forward. The hybrid system (utilizing Sentence Transformers via HuggingFace and FAISS) achieves perfect nDCG@5 and Mean Reciprocal Rank (MRR)—which means **it ranks the single correct session at position #1 for every single query evaluated**. 

The keyword-only baseline suffers from semantic mismatch (e.g., failing to connect the query "machine learning" to a session titled "Neural Networks"), dragging its MRR down to 0.39. The hybrid approach's 156% relative improvement directly proves that blending dense embeddings with lexical keyword overlap is critical for high-fidelity conference matchmaking.

## 6 Conclusions and Future Work

This implementation decisively proves that raw, flat attendance records can be systematically normalized into a rich entity graph suitable for state-of-the-art hybrid vector retrieval and RAG-driven orchestrations. The platform is highly practical for small-to-medium conferences, and serves as an excellent foundation for professional networking tools.

**Future Directions**:
1. **Profile Enrichment**: Automatically query external APIs (LinkedIn, Twitter) to scrape and enrich attendee profiles with their actual Job Titles, Companies, and self-authored biographies.
2. **Bidirectional Matchmaking**: Upgrade the system beyond search to become a proactive recommendation engine that actively proposes mutual double-opt-in meetings between attendees with complementary "Asks" and "Offers".
3. **Multi-Agent PAL**: Integrate multiple specialized LLM agents (e.g., an LLM specialized in scheduling, and an LLM specialized in introductory email drafting) routing through LangChain to automate the entire meeting arrangement lifecycle.

## 7 Submission Guidelines

- **PDF file**: Included in the submission materials.
- **GCP Endpoint**: [http://34.169.130.58:8000](http://34.169.130.58:8000)
- **Github URL**: [https://github.com/xiancao2024/Conference-Matching-Platform](https://github.com/xiancao2024/Conference-Matching-Platform)

---

### Appendix: How to reproduce locally

**1. Create virtual environment and install dependencies**
```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

**2. Import the Kaggle dataset directly via Kagglehub**
```bash
pip install kagglehub
python3 -m conference_matching.kaggle_import
```

**3. Start the Server**
```bash
python3 server.py
```

**4. Run complete evaluation suite**
```bash
python3 -m conference_matching.evaluation
```
