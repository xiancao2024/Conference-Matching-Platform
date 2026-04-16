#!/usr/bin/env python3
"""
Generate a GTC-style wide CSV (one row per attendee) without any API calls.

Use this for local samples and large (e.g. 10k) synthetic datasets at zero API cost.
For import:  python3 -m conference_matching.gtc_import --input <this.csv>

API / Gemini (optional, not implemented here):
  - Calling Gemini or OpenAI for 10k rows is billed per token/request; free tiers exist but have limits.
  - A Gemini API key works only if you add a separate script that calls Google AI Studio / Vertex
    (this file stays offline-friendly).

Examples:
  python3 scripts/generate_gtc_wide_csv.py --rows 50 --output data/gtc_local_sample.csv
  python3 scripts/generate_gtc_wide_csv.py --rows 10000 --output data/gtc_generated_10k.csv
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

FIRST = [
    "Ava", "Leo", "Maya", "Noah", "Priya", "Chen", "Diego", "Emma", "Fatima", "Gavin",
    "Hana", "Ivan", "Jules", "Ken", "Lina", "Mateo", "Nina", "Omar", "Quinn", "Ravi",
]
LAST = [
    "Chen", "Park", "Singh", "Garcia", "Khan", "Nguyen", "Patel", "Kim", "Silva", "Brown",
    "Davis", "Evans", "Foster", "Green", "Hughes", "Iyer", "Jones", "Kelly", "Lopez", "Moore",
]
EDU = ["BS", "MS", "PhD", "MBA"]
MAJOR = ["CS", "EE", "Math", "Physics", "Data Science", "Robotics", "HCI"]
JOB = [
    "Software Engineer",
    "Research Scientist",
    "Founder",
    "Student",
    "ML Engineer",
    "Product Manager",
    "Solutions Architect",
]
EXP = [
    "1–2 years",
    "3–5 years",
    "6–10 years",
    "10+ years",
    "Graduate student",
]
INTEREST_POOL = [
    "LLMs",
    "Robotics",
    "CUDA",
    "Autonomous Vehicles",
    "Healthcare AI",
    "Edge AI",
    "Computer Vision",
    "Simulation",
    "Digital Twins",
    "Networking",
]
AGENDA_POOL = [
    "NVIDIA CEO Keynote",
    "Generative AI Theater: LLM Inference",
    "CUDA Developer Lab",
    "Robotics & Edge AI Session",
    "Jetson Developer Meetup",
    "Deep Learning Training Workshop",
    "Healthcare AI Roundtable",
    "Networking Reception",
    "Autonomous Vehicle Tech Talk",
    "Omniverse & Simulation Lab",
]


def _pick_interests(rng: random.Random, k: int) -> str:
    items = rng.sample(INTEREST_POOL, k=min(k, len(INTEREST_POOL)))
    return "; ".join(items)


def _pick_agendas(rng: random.Random, k: int) -> str:
    k = max(1, min(k, len(AGENDA_POOL)))
    items = rng.sample(AGENDA_POOL, k=k)
    return " | ".join(items)


def _bio_snippet(rng: random.Random, major: str, job: str, interests: str) -> str:
    templates = [
        f"Interested in {major.lower()} applications and {interests.split(';')[0].strip()}.",
        f"{job} focused on shipping ML systems; passionate about {interests.split(';')[0].strip()}.",
        f"Building prototypes at the intersection of {major} and applied AI.",
    ]
    return rng.choice(templates)


def generate_rows(n: int, rng: random.Random) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for i in range(n):
        first = rng.choice(FIRST)
        last = rng.choice(LAST)
        name = f"{first} {last}"
        email = f"{first.lower()}.{last.lower()}.{i}@gtc-synth.example"
        edu = rng.choice(EDU)
        major = rng.choice(MAJOR)
        job = rng.choice(JOB)
        exp = rng.choice(EXP)
        ni = rng.randint(2, 4)
        na = rng.randint(1, 4)
        interests = _pick_interests(rng, ni)
        agendas = _pick_agendas(rng, na)
        bio = _bio_snippet(rng, major, job, interests)
        rows.append(
            {
                "Name": name,
                "Email": email,
                "Education Level": edu,
                "Major": major,
                "Job Title": job,
                "Work Experience": exp,
                "Interests": interests,
                "Agenda Items": agendas,
                "Bio/Resume Snippet": bio,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic GTC wide-row CSV (no API).")
    parser.add_argument("--rows", type=int, default=50, help="Number of attendee rows (default 50).")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/gtc_local_sample.csv"),
        help="Output CSV path (default: data/gtc_local_sample.csv).",
    )
    args = parser.parse_args()
    if args.rows < 1:
        raise SystemExit("--rows must be >= 1")

    rng = random.Random(args.seed)
    rows = generate_rows(args.rows, rng)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {args.output.resolve()}")


if __name__ == "__main__":
    main()
