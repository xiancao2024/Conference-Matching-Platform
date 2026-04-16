from __future__ import annotations

import csv
import json
import os
import re
import tempfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .ontology import PHRASE_TO_CONCEPT, TOKEN_TO_CONCEPT


REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
NORMALIZED_KAGGLE_PATH = DATA_DIR / "conference_kaggle.json"
NORMALIZED_GTC_PATH = DATA_DIR / "conference_gtc.json"
KAGGLE_DATASET_ID = "cankatsrc/event-attendance-dataset"

# Wide-row profile CSV: one row per attendee (GTC-style).
GTC_PROFILE_COLUMN_ALIASES = {
    "name": {"name", "fullname", "attendeename", "participantname", "displayname"},
    "email": {"email", "attendeeemail", "contactemail", "e-mail"},
    "phone": {"phone", "attendeephone", "contactphone", "mobile"},
    "education_level": {"educationlevel", "education", "degree", "schooling"},
    "major": {"major", "fieldofstudy", "discipline"},
    "job_title": {"jobtitle", "title", "role", "position"},
    "work_experience": {"workexperience", "experience", "years", "tenure"},
    "interests": {"interests", "interest", "topics", "tags", "focusareas"},
    "agenda_items": {"agendaitems", "agenda", "sessions", "registeredsessions", "gtcsessions", "events"},
    "bio": {"bio", "biography", "resumesnippet", "profile", "about", "summary"},
}

TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9\-]+")
PERSONAL_EMAIL_DOMAINS = {"gmail", "yahoo", "hotmail", "outlook", "icloud", "aol", "protonmail"}
CANONICAL_TO_DISPLAY = {
    "ai": "artificial intelligence",
    "healthcare": "healthcare",
    "workflow": "workflow automation",
    "developer_tools": "developer tools",
    "climate": "climate",
    "energy": "energy",
    "carbon": "carbon",
    "fintech": "fintech",
    "compliance": "compliance",
    "cybersecurity": "cybersecurity",
    "community": "community",
    "networking": "networking",
    "partnerships": "partnerships",
    "pilot": "pilot programs",
    "funding": "fundraising",
    "mentorship": "mentorship",
    "customers": "customer discovery",
}
CSV_COLUMN_ALIASES = {
    "event_id": {"eventid", "event_id", "id"},
    "event_name": {"eventname", "event_name", "event", "name"},
    "location": {"location", "venue", "eventlocation"},
    "date_time": {"datetime", "dateandtime", "date_time", "date", "eventdate", "eventdatetime"},
    "attendee_name": {"attendeename", "attendee_name", "participantname", "nameattendee"},
    "attendee_email": {"attendeeemail", "attendee_email", "email", "participantemail"},
    "attendee_phone": {"attendeephone", "attendee_phone", "phone", "participantphone"},
}


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def _title_case(value: str) -> str:
    return " ".join(part.capitalize() for part in value.replace("_", " ").split())


def _tokenize(value: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(value.lower())]


def _extract_concepts(text: str) -> list[str]:
    normalized = text.lower()
    concepts: list[str] = []
    for phrase, mapped in PHRASE_TO_CONCEPT.items():
        if phrase in normalized:
            concepts.extend(mapped)
    for token in _tokenize(normalized):
        concepts.extend(TOKEN_TO_CONCEPT.get(token, []))
    return concepts


def _display_concepts(texts: list[str], limit: int = 4) -> list[str]:
    counts: Counter[str] = Counter()
    for text in texts:
        counts.update(_extract_concepts(text))
    if not counts:
        return ["community"]
    return [CANONICAL_TO_DISPLAY.get(key, _title_case(key)) for key, _ in counts.most_common(limit)]


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _find_matching_column(fieldnames: list[str], canonical_name: str) -> str | None:
    normalized_map = {_normalize_header(name): name for name in fieldnames}
    for alias in CSV_COLUMN_ALIASES[canonical_name]:
        if alias in normalized_map:
            return normalized_map[alias]
    return None


def _find_gtc_column(fieldnames: list[str], canonical_name: str) -> str | None:
    normalized_map = {_normalize_header(name): name for name in fieldnames}
    for alias in GTC_PROFILE_COLUMN_ALIASES[canonical_name]:
        if alias in normalized_map:
            return normalized_map[alias]
    return None


def _gtc_row_value(row: dict[str, str], fieldnames: list[str], canonical_name: str) -> str:
    column_name = _find_gtc_column(fieldnames, canonical_name)
    return (row.get(column_name, "") if column_name else "").strip()


def _split_multi_field(value: str) -> list[str]:
    if not (value or "").strip():
        return []
    parts = re.split(r"[,;|\n]+", value)
    return [p.strip() for p in parts if p.strip()]


def _csv_match_score(fieldnames: list[str]) -> int:
    score = 0
    for canonical_name in CSV_COLUMN_ALIASES:
        if _find_matching_column(fieldnames, canonical_name):
            score += 1
    return score


def _read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader if row]


def _discover_csv_paths(source_path: Path) -> tuple[list[Path], tempfile.TemporaryDirectory[str] | None]:
    if source_path.is_file() and source_path.suffix.lower() == ".csv":
        return [source_path], None
    if source_path.is_dir():
        return sorted(source_path.rglob("*.csv")), None
    if source_path.is_file() and source_path.suffix.lower() == ".zip":
        temp_dir = tempfile.TemporaryDirectory()
        with zipfile.ZipFile(source_path) as archive:
            archive.extractall(temp_dir.name)
        return sorted(Path(temp_dir.name).rglob("*.csv")), temp_dir
    raise FileNotFoundError(f"Unsupported dataset source: {source_path}")


def load_event_attendance_rows(source_path: Path) -> tuple[list[dict[str, str]], str]:
    csv_paths, temp_dir = _discover_csv_paths(source_path)
    try:
        if not csv_paths:
            raise FileNotFoundError(f"No CSV files found under {source_path}")

        best_path: Path | None = None
        best_score = -1
        for path in csv_paths:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                fieldnames = reader.fieldnames or []
            score = _csv_match_score(fieldnames)
            if score > best_score:
                best_score = score
                best_path = path

        if best_path is None or best_score < 4:
            raise ValueError(
                "Could not find a CSV that matches the expected Event Attendance schema. "
                "Expected columns like Event ID, Event Name, Location, Date/Time, Attendee Name, Email, Phone."
            )

        rows = _read_csv_rows(best_path)
        return rows, str(best_path)
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


def _row_value(row: dict[str, str], fieldnames: list[str], canonical_name: str) -> str:
    column_name = _find_matching_column(fieldnames, canonical_name)
    return (row.get(column_name, "") if column_name else "").strip()


def _organization_from_email(email: str) -> str:
    if "@" not in email:
        return "Independent"
    domain = email.split("@", 1)[1].lower()
    label = domain.split(".", 1)[0]
    if label in PERSONAL_EMAIL_DOMAINS:
        return "Independent"
    return _title_case(label)


def _attendee_bio(name: str, organization: str, events: list[str]) -> str:
    if not events:
        return f"{name} appears in the imported attendance dataset."
    preview = ", ".join(events[:2])
    suffix = f" and {len(events) - 2} more event(s)" if len(events) > 2 else ""
    if organization == "Independent":
        return f"{name} is attending {preview}{suffix}."
    return f"{name} from {organization} is attending {preview}{suffix}."


def _event_bio(name: str, location: str, date_time: str, attendee_count: int) -> str:
    parts = [name]
    if location:
        parts.append(f"at {location}")
    if date_time:
        parts.append(f"on {date_time}")
    sentence = " ".join(parts) + "."
    return f"{sentence} Imported dataset records {attendee_count} attendee row(s) for this event."


def normalize_event_attendance_rows(rows: list[dict[str, str]], source_label: str) -> dict[str, Any]:
    if not rows:
        raise ValueError("The attendance dataset is empty.")

    fieldnames = list(rows[0].keys())
    attendee_groups: dict[str, dict[str, Any]] = {}
    event_groups: dict[str, dict[str, Any]] = {}
    event_theme_texts: defaultdict[str, list[str]] = defaultdict(list)

    for row in rows:
        event_name = _row_value(row, fieldnames, "event_name") or "Unnamed Event"
        event_id = _row_value(row, fieldnames, "event_id") or event_name
        location = _row_value(row, fieldnames, "location")
        date_time = _row_value(row, fieldnames, "date_time")
        attendee_name = _row_value(row, fieldnames, "attendee_name") or "Unknown Attendee"
        attendee_email = _row_value(row, fieldnames, "attendee_email")
        attendee_phone = _row_value(row, fieldnames, "attendee_phone")

        event_key = _slugify(event_id)
        event_record = event_groups.setdefault(
            event_key,
            {
                "event_name": event_name,
                "location": location,
                "date_time": date_time,
                "raw_row_count": 0,
            },
        )
        event_record["raw_row_count"] += 1
        event_theme_texts[event_key].append(" ".join(part for part in [event_name, location] if part))

        attendee_key = _slugify(attendee_email or attendee_name)
        attendee_record = attendee_groups.setdefault(
            attendee_key,
            {
                "name": attendee_name,
                "email": attendee_email,
                "phone": attendee_phone,
                "events": [],
                "event_theme_texts": [],
            },
        )
        attendee_record["events"].append(event_name)
        attendee_record["event_theme_texts"].append(" ".join(part for part in [event_name, location] if part))

    entities: list[dict[str, Any]] = []
    all_theme_texts: list[str] = []

    for attendee_key, attendee in attendee_groups.items():
        organization = _organization_from_email(attendee["email"])
        sectors = _display_concepts(attendee["event_theme_texts"])
        tags = sorted(set(attendee["events"]))[:4]
        all_theme_texts.extend(attendee["event_theme_texts"])
        entities.append(
            {
                "id": f"attendee-{attendee_key}",
                "entity_type": "attendee",
                "name": attendee["name"],
                "role": "participant",
                "title": "Conference Attendee",
                "organization": organization,
                "sectors": sectors,
                "stage": ["all"],
                "goals": ["Find relevant people at the event", "Join useful event conversations"],
                "asks": ["Relevant introductions", "Networking opportunities"],
                "offers": ["Peer conversation", "Shared event context"],
                "tags": tags,
                "bio": _attendee_bio(attendee["name"], organization, attendee["events"]),
                "contact_email": attendee["email"],
                "contact_phone": attendee["phone"],
                "source_events": sorted(set(attendee["events"])),
            }
        )

    for event_key, event in event_groups.items():
        sectors = _display_concepts(event_theme_texts[event_key])
        all_theme_texts.extend(event_theme_texts[event_key])
        entities.append(
            {
                "id": f"event-{event_key}",
                "entity_type": "resource",
                "name": event["event_name"],
                "role": "session",
                "title": "Imported Event Session",
                "organization": event["location"] or "Event Venue",
                "sectors": sectors,
                "stage": ["all"],
                "goals": [f"Bring together attendees interested in {event['event_name']}"],
                "asks": ["Attendees who want to join this event"],
                "offers": [value for value in [event["location"], event["date_time"], "Shared event context"] if value],
                "tags": sectors,
                "bio": _event_bio(event["event_name"], event["location"], event["date_time"], event["raw_row_count"]),
                "attendee_count": event["raw_row_count"],
            }
        )

    top_tracks = _display_concepts(all_theme_texts, limit=5)
    conference = {
        "id": "kaggle-event-attendance",
        "name": "Kaggle Event Attendance Dataset",
        "location": "Imported from event attendance records",
        "date": "",
        "theme": "Conference matching over imported attendance rows",
        "description": (
            "Normalized from the Kaggle Event Attendance Dataset. "
            "Attendee roles and richer matchmaking fields are heuristically derived from event attendance records."
        ),
        "tracks": top_tracks,
        "source_type": "kaggle-normalized",
        "source_dataset": KAGGLE_DATASET_ID,
        "source_label": source_label,
        "event_count": len(event_groups),
        "attendee_count": len(attendee_groups),
        "raw_row_count": len(rows),
    }
    return {"conference": conference, "entities": entities}


def _gtc_profile_bio(
    name: str,
    bio: str,
    education: str,
    major: str,
    job: str,
    work_exp: str,
    interests_cell: str,
    agendas: list[str],
) -> str:
    chunks: list[str] = []
    if bio:
        chunks.append(bio)
    meta_bits = [
        f"Education: {education}" if education else "",
        f"Major: {major}" if major else "",
        f"Role: {job}" if job else "",
        f"Experience: {work_exp}" if work_exp else "",
    ]
    meta = ". ".join(b for b in meta_bits if b)
    if meta:
        chunks.append(meta + ".")
    if interests_cell:
        chunks.append(f"Interests: {interests_cell}")
    if agendas:
        tail = ", ".join(agendas[:8])
        if len(agendas) > 8:
            tail += f", +{len(agendas) - 8} more"
        chunks.append(f"Registered GTC sessions: {tail}.")
    return " ".join(chunks) if chunks else f"{name} (GTC profile import)."


def normalize_gtc_profile_rows(rows: list[dict[str, str]], source_label: str) -> dict[str, Any]:
    """Normalize wide CSV rows: one row per attendee with interests and agenda session titles."""
    if not rows:
        raise ValueError("The profile dataset is empty.")

    fieldnames = list(rows[0].keys())
    if _find_gtc_column(fieldnames, "name") is None:
        raise ValueError(
            "Wide-row GTC CSV must include a Name column. "
            "Supported headers include: Name, Email, Education Level, Major, Job Title, "
            "Work Experience, Interests, Agenda Items, Bio."
        )

    attendee_groups: dict[str, dict[str, Any]] = {}

    for idx, row in enumerate(rows):
        name = _gtc_row_value(row, fieldnames, "name")
        if not name:
            continue
        email = _gtc_row_value(row, fieldnames, "email")
        phone = _gtc_row_value(row, fieldnames, "phone")
        education = _gtc_row_value(row, fieldnames, "education_level")
        major = _gtc_row_value(row, fieldnames, "major")
        job = _gtc_row_value(row, fieldnames, "job_title")
        work_exp = _gtc_row_value(row, fieldnames, "work_experience")
        interests_cell = _gtc_row_value(row, fieldnames, "interests")
        agenda_cell = _gtc_row_value(row, fieldnames, "agenda_items")
        bio_cell = _gtc_row_value(row, fieldnames, "bio")

        agendas = _split_multi_field(agenda_cell)
        base_key = _slugify(email) if email else _slugify(name)
        attendee_key = base_key
        n = 0
        while attendee_key in attendee_groups:
            n += 1
            attendee_key = f"{base_key}-{n}"

        synthetic_email = email or f"{attendee_key}@profiles.gtc.local"

        theme_parts = [interests_cell, major, job, work_exp] + agendas
        attendee_groups[attendee_key] = {
            "name": name,
            "email": synthetic_email,
            "phone": phone,
            "education": education,
            "major": major,
            "job": job,
            "work_exp": work_exp,
            "interests_cell": interests_cell,
            "agendas": agendas,
            "bio_cell": bio_cell,
            "event_theme_texts": [" ".join(t for t in theme_parts if t)],
        }

    entities: list[dict[str, Any]] = []
    all_theme_texts: list[str] = []

    for attendee_key, attendee in attendee_groups.items():
        organization = _organization_from_email(attendee["email"])
        sector_inputs = attendee["event_theme_texts"] + attendee["agendas"] + [attendee["interests_cell"]]
        sectors = _display_concepts(sector_inputs)
        tags = (attendee["agendas"] + _split_multi_field(attendee["interests_cell"]))[:10]
        full_bio = _gtc_profile_bio(
            attendee["name"],
            attendee["bio_cell"],
            attendee["education"],
            attendee["major"],
            attendee["job"],
            attendee["work_exp"],
            attendee["interests_cell"],
            attendee["agendas"],
        )
        all_theme_texts.extend(sector_inputs)
        entities.append(
            {
                "id": f"attendee-{attendee_key}",
                "entity_type": "attendee",
                "name": attendee["name"],
                "role": "participant",
                "title": attendee["job"] or "Conference Attendee",
                "organization": organization,
                "sectors": sectors,
                "stage": ["all"],
                "goals": ["Meet peers at GTC sessions", "Explore registered agenda topics"],
                "asks": _split_multi_field(attendee["interests_cell"])[:6]
                or ["Relevant introductions at GTC"],
                "offers": [x for x in [attendee["major"], attendee["education"]] if x]
                or ["Peer conversation", "Shared GTC context"],
                "tags": tags or sectors[:4],
                "bio": full_bio,
                "contact_email": attendee["email"],
                "contact_phone": attendee["phone"],
                "source_events": sorted(set(attendee["agendas"])),
                "education_level": attendee["education"],
                "major": attendee["major"],
                "work_experience": attendee["work_exp"],
            }
        )

    top_tracks = _display_concepts(all_theme_texts, limit=5)
    conference = {
        "id": "gtc-profile-wide-row",
        "name": "NVIDIA GTC (single conference)",
        "location": "Synthetic / organizer-collected profiles",
        "date": "",
        "theme": "Attendee interests, resumes, and registered agenda items",
        "description": (
            "One conference (GTC). One row per attendee: education, major, job, interests, "
            "registered agenda titles (text only), and bio. Matching is people-only; agenda text "
            "is embedded in each profile for search."
        ),
        "tracks": top_tracks,
        "source_type": "gtc-wide-row",
        "source_dataset": "local-gtc-profile-csv",
        "source_label": source_label,
        "event_count": 1,
        "attendee_count": len(attendee_groups),
        "raw_row_count": len(rows),
    }
    return {"conference": conference, "entities": entities}


def import_gtc_profile_csv(input_path: Path, output_path: Path | None = None) -> Path:
    """Read a wide-row GTC profile CSV and write normalized JSON (default: data/conference_gtc.json)."""
    rows = _read_csv_rows(input_path)
    normalized = normalize_gtc_profile_rows(rows, str(input_path))
    target = output_path or NORMALIZED_GTC_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    return write_normalized_dataset(normalized, target)


def write_normalized_dataset(dataset: dict[str, Any], output_path: Path | None = None) -> Path:
    target_path = output_path or NORMALIZED_KAGGLE_PATH
    with target_path.open("w", encoding="utf-8") as handle:
        json.dump(dataset, handle, indent=2)
    return target_path


def maybe_download_kaggle_dataset(dataset_id: str = KAGGLE_DATASET_ID) -> Path:
    try:
        import kagglehub  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "kagglehub is not installed. Install it first or use a manually downloaded Kaggle zip/csv."
        ) from exc
    return Path(kagglehub.dataset_download(dataset_id))


def import_kaggle_dataset(input_path: Path | None = None, dataset_id: str = KAGGLE_DATASET_ID) -> Path:
    source_path = input_path or maybe_download_kaggle_dataset(dataset_id)
    rows, source_label = load_event_attendance_rows(source_path)
    normalized = normalize_event_attendance_rows(rows, source_label)
    return write_normalized_dataset(normalized)


def load_dataset(source: str | None = None) -> dict[str, Any]:
    resolved_source = (source or os.environ.get("CONFERENCE_DATA_SOURCE", "kaggle")).lower()
    explicit_path = os.environ.get("CONFERENCE_DATA_PATH")
    if explicit_path:
        path = Path(explicit_path)
        if not path.exists():
            raise FileNotFoundError(f"Configured CONFERENCE_DATA_PATH does not exist: {path}")
        return _load_json(path)
    if resolved_source not in {"auto", "normalized", "kaggle"}:
        raise ValueError(
            "Only imported Kaggle data is supported. "
            "Use CONFERENCE_DATA_SOURCE=kaggle or provide CONFERENCE_DATA_PATH."
        )
    if NORMALIZED_KAGGLE_PATH.exists():
        return _load_json(NORMALIZED_KAGGLE_PATH)
    raise FileNotFoundError(
        f"{NORMALIZED_KAGGLE_PATH} does not exist yet. "
        "Import the Kaggle dataset first with `python3 -m conference_matching.kaggle_import --input <zip-or-csv>`."
    )


def conference_metadata(source: str | None = None) -> dict[str, Any]:
    return load_dataset(source)["conference"]


def conference_entities(source: str | None = None) -> list[dict[str, Any]]:
    return load_dataset(source)["entities"]
