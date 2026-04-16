# GatherBlock Conference Matching Platform

Did you actually network effectively at your last conference, or just attend sessions?

This app simulates a **GTC networking copilot**: you ask "who should I meet?" and it returns ranked attendee matches with clear reasons (interest fit, role fit, and activity overlap).

The current product is optimized for a **single-conference, people-only** workflow (GTC-style profiles).

Input is a **wide CSV with one row per attendee** (name, role/title, education, interests, agenda registrations, bio). The app normalizes that CSV into `data/conference_gtc.json`, then ranks attendees with a hybrid retrieval engine.

## What the project includes

- GTC wide-row CSV generator for local testing (`scripts/generate_gtc_wide_csv.py`)
- GTC profile importer (`conference_matching.gtc_import`)
- Hybrid matcher (lexical + concept + optional embedding + structured boosts)
- People-first web UI (activity overlap + rationale)
- Optional Ollama one-line explanation (`llm_reason`) for top matches
- Docker image for VM deployment

## Data flow

1. Prepare a wide-row GTC CSV (real or synthetic).
2. Import CSV into normalized JSON (`data/conference_gtc.json`).
3. Start server / container.
4. Ask natural-language "who should I meet" queries in the UI.

## Prepare data

### Option A: Generate a local sample

```bash
python3 scripts/generate_gtc_wide_csv.py --rows 50 --output data/gtc_local_sample.csv
python3 -m conference_matching.gtc_import --input data/gtc_local_sample.csv --output data/conference_gtc.json
```

### Option B: Generate a larger dataset (e.g. 10k)

```bash
python3 scripts/generate_gtc_wide_csv.py --rows 10000 --output data/gtc_generated_10k.csv
python3 -m conference_matching.gtc_import --input data/gtc_generated_10k.csv --output data/conference_gtc.json
```

### Option C: Import your own wide-row CSV

```bash
python3 -m conference_matching.gtc_import --input /path/to/your_gtc_profiles.csv --output data/conference_gtc.json
```

## Run locally

```bash
CONFERENCE_DATA_PATH=data/conference_gtc.json python3 server.py
```

Open: `http://127.0.0.1:8000`

## Run with Docker

### Quick Docker run (most common path)

If you already have `data/conference_gtc.json`, run:

```bash
docker rm -f conference-matching 2>/dev/null || true
docker build -t conference-matching .
docker run -d --name conference-matching \
  -p 8000:8000 \
  -v "$HOME/Conference-Matching-Platform/data:/app/data" \
  -e CONFERENCE_DATA_PATH=/app/data/conference_gtc.json \
  conference-matching
docker logs -f conference-matching
```

Open: `http://127.0.0.1:8000` (or `http://<VM_EXTERNAL_IP>:8000` on a VM)

### Docker run, step by step

Build image:

```bash
docker build -t conference-matching .
```

Run container (recommended: mount full `data/` so embeddings can be reused):

```bash
docker rm -f conference-matching 2>/dev/null || true
docker run -d --name conference-matching \
  -p 8000:8000 \
  -v "$HOME/Conference-Matching-Platform/data:/app/data" \
  -e CONFERENCE_DATA_PATH=/app/data/conference_gtc.json \
  conference-matching
```

Watch logs:

```bash
docker logs -f conference-matching
```

Stop/remove:

```bash
docker rm -f conference-matching
```

## Embedding behavior (important)

- Embeddings are saved as:
  - `data/embeddings.npy`
  - `data/faiss.index`
- On restart, the app **reuses embeddings** if row count matches current entities.
- Re-embedding happens only if:
  - files are missing/corrupted, or
  - dataset size changes.
- Do **not** delete `embeddings.npy` / `faiss.index` if you want fast restarts.

Useful env vars:

- `CONFERENCE_EMBED_MAX_ENTITIES` (default `20000`): upper bound for on-the-fly embedding.
- `CONFERENCE_EMBED_SHOW_PROGRESS` (default `1`): show progress bar for large builds.

If you never want runtime embedding fallback, set:

```bash
-e CONFERENCE_EMBED_MAX_ENTITIES=0
```

## VM deployment checklist

1. Pull latest code on VM.
2. Ensure `data/conference_gtc.json` exists.
3. Build and run container with mounted `data/`.
4. Open firewall for TCP `8000`.
5. Access via `http://<VM_EXTERNAL_IP>:8000` (HTTP, not HTTPS).

Quick restart commands on VM:

```bash
cd ~/Conference-Matching-Platform
git pull origin main
docker rm -f conference-matching 2>/dev/null || true
docker build -t conference-matching .
docker run -d --name conference-matching \
  -p 8000:8000 \
  -v "$HOME/Conference-Matching-Platform/data:/app/data" \
  -e CONFERENCE_DATA_PATH=/app/data/conference_gtc.json \
  conference-matching
docker logs -f conference-matching
```

## UI behavior updates

- Ranking cards now prioritize **Activity overlap** using attendee `source_events`.
- Duplicate rationale bullets were removed; each bullet conveys distinct information.
- LLM rationale label is now `Why connect with this person`.
- Response header is product-style and avoids repeating the user's exact question.

## Tests

```bash
python3 -m unittest discover -s tests
```

If needed:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

## File layout

- `conference_matching/data.py`: loaders and normalization logic
- `conference_matching/gtc_import.py`: wide-row GTC import CLI
- `conference_matching/engine.py`: indexing, scoring, ranking, payload fields
- `conference_matching/llm.py`: optional Ollama reasoning
- `conference_matching/server.py`: API + static hosting
- `scripts/generate_gtc_wide_csv.py`: synthetic GTC CSV generation
- `static/index.html`: UI shell
- `static/app.js`: query UX and result rendering
