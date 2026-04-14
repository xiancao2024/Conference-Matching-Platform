# GatherBlock Conference Matching Platform

This repository now runs on real imported attendance data only. The supported source is the Kaggle Event Attendance dataset:

- `cankatsrc/event-attendance-dataset`
- https://www.kaggle.com/datasets/cankatsrc/event-attendance-dataset

The app normalizes that dataset into conference attendees and session/resource records, then runs a hybrid retrieval pipeline over those imported entities.

## What the project includes

- A Kaggle attendance importer that reads a downloaded `.zip`, `.csv`, or extracted directory.
- A normalized conference schema written to `data/conference_kaggle.json`.
- A Python hybrid matching engine with lexical, semantic, and structured scoring.
- A browser demo with guided queries over imported attendees and sessions.
- A weak-label evaluation harness built from real attendance links.
- Automated tests that exercise the real-data schema path.

## Data flow

1. Download the Kaggle dataset manually or through `kagglehub`.
2. Normalize the raw attendance rows into the app schema.
3. Start the local server.
4. Query imported attendees and sessions through the web UI.

Core loader: [data.py](/Users/xiancao/Downloads/2026NLP/NLP_Rag/Conference-Matching-Platform/repo/conference_matching/data.py)  
Importer entrypoint: [kaggle_import.py](/Users/xiancao/Downloads/2026NLP/NLP_Rag/Conference-Matching-Platform/repo/conference_matching/kaggle_import.py)  
Matcher: [engine.py](/Users/xiancao/Downloads/2026NLP/NLP_Rag/Conference-Matching-Platform/repo/conference_matching/engine.py)

## Import the real dataset

If you downloaded the Kaggle zip manually:

```bash
python3 -m conference_matching.kaggle_import --input /path/to/event-attendance-dataset.zip
```

If you already extracted the dataset:

```bash
python3 -m conference_matching.kaggle_import --input /path/to/extracted-folder
```

If you want to use `kagglehub` directly:

```bash
pip install kagglehub
python3 -m conference_matching.kaggle_import
```

The importer writes the normalized JSON to `data/conference_kaggle.json` by default.

If you prefer to write or use a different path, set `CONFERENCE_DATA_PATH` when running the server or any CLI that reads the dataset.

Examples

```bash
# Import from a downloaded zip or extracted folder (writes data/conference_kaggle.json)
python3 -m conference_matching.kaggle_import --input /path/to/event-attendance-dataset.zip

# Import using the bundled default Kaggle id (requires kagglehub)
pip install kagglehub
python3 -m conference_matching.kaggle_import

# Run the server using a specific normalized file
CONFERENCE_DATA_PATH=/full/path/to/conference_kaggle.json python3 server.py
```

Quick inspection

If `data/conference_kaggle.json` is present you can view basic counts quickly without opening the whole file:

```bash
# print conference event and attendee counts (run from repo root)
python3 - <<'PY'
import json
with open('data/conference_kaggle.json', 'r', encoding='utf-8') as f:
	o = json.load(f)
conf = o.get('conference', {})
print('events:', conf.get('event_count'))
print('attendees:', conf.get('attendee_count'))
PY
```

## Run locally

Start the demo server after importing the dataset:

```bash
python3 server.py
```

Then open:

```text
http://127.0.0.1:8000
```

For a remote VM such as GCP, bind the server externally:

```bash
HOST=0.0.0.0 PORT=8000 python3 server.py
```

Or use the helper script:

```bash
./scripts/gcp_start.sh
```

If you want to point the app at a specific normalized JSON instead of `data/conference_kaggle.json`:

```bash
CONFERENCE_DATA_PATH=/path/to/conference_kaggle.json python3 server.py
```

## Run on GCP

If your GCP VM is already created, the simplest deployment path is:

1. SSH into the VM.
2. Clone or copy this repo onto the VM.
3. Create the virtual environment and install `kagglehub` if you want the VM to download the dataset directly.
4. Import the dataset.
5. Start the app on `0.0.0.0`.
6. Open the VM firewall for the app port, or use SSH port forwarding.

Example commands on the VM:

```bash
cd ~/Conference-Matching-Platform
python3 -m venv .venv
.venv/bin/python -m pip install kagglehub
.venv/bin/python -m conference_matching.kaggle_import
HOST=0.0.0.0 PORT=8000 .venv/bin/python server.py
```

If you already imported the dataset locally and copied `data/conference_kaggle.json` to the VM, you can skip the Kaggle download and just run:

```bash
HOST=0.0.0.0 PORT=8000 CONFERENCE_DATA_PATH=/full/path/to/conference_kaggle.json .venv/bin/python server.py
```

To reach the app from your laptop, either:

- open a GCP firewall rule for TCP `8000`, then visit `http://VM_EXTERNAL_IP:8000`
- or use SSH port forwarding and keep the app private:

```bash
gcloud compute ssh YOUR_INSTANCE_NAME --zone YOUR_ZONE -- -L 8000:localhost:8000
```

Then open `http://127.0.0.1:8000` on your laptop.

## Evaluation

The evaluation module now uses weak labels derived from the real attendance data:

- each imported attendee becomes a query
- that attendee's known event sessions become the relevant set
- hybrid retrieval is compared against a keyword baseline

Run it with:

```bash
python3 -m conference_matching.evaluation
```

## Tests

Run the tests with:

```bash
python3 -m unittest discover -s tests
```

## Important limitation

The Kaggle dataset is an attendance dataset, not a full GatherBlock profile database. It provides event rows and attendee contact fields, but it does not provide rich role labels such as founder/investor, nor explicit asks/offers. The app therefore derives some search fields heuristically from event names, locations, and attendance history.

## File layout

- [conference_matching/data.py](/Users/xiancao/Downloads/2026NLP/NLP_Rag/Conference-Matching-Platform/repo/conference_matching/data.py): import and dataset loading
- [conference_matching/kaggle_import.py](/Users/xiancao/Downloads/2026NLP/NLP_Rag/Conference-Matching-Platform/repo/conference_matching/kaggle_import.py): Kaggle normalization CLI
- [conference_matching/engine.py](/Users/xiancao/Downloads/2026NLP/NLP_Rag/Conference-Matching-Platform/repo/conference_matching/engine.py): matching and ranking
- [conference_matching/evaluation.py](/Users/xiancao/Downloads/2026NLP/NLP_Rag/Conference-Matching-Platform/repo/conference_matching/evaluation.py): weak-label evaluation
- [conference_matching/server.py](/Users/xiancao/Downloads/2026NLP/NLP_Rag/Conference-Matching-Platform/repo/conference_matching/server.py): local API and static file serving
- [static/index.html](/Users/xiancao/Downloads/2026NLP/NLP_Rag/Conference-Matching-Platform/repo/static/index.html): web UI
