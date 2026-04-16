from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from conference_matching.data import (
    load_event_attendance_rows,
    normalize_event_attendance_rows,
    normalize_gtc_profile_rows,
)


class KaggleDataImportTest(unittest.TestCase):
    def test_normalize_event_attendance_rows_creates_attendees_and_events(self) -> None:
        rows = [
            {
                "Event ID": "101",
                "Event Name": "AI Founder Breakfast",
                "Location": "Boston",
                "Date & Time": "2026-09-18 09:00",
                "Attendee Name": "Ava Stone",
                "Attendee Email": "ava@northstar.ai",
                "Attendee Phone": "555-1111",
            },
            {
                "Event ID": "101",
                "Event Name": "AI Founder Breakfast",
                "Location": "Boston",
                "Date & Time": "2026-09-18 09:00",
                "Attendee Name": "Leo Hart",
                "Attendee Email": "leo@example.com",
                "Attendee Phone": "555-2222",
            },
        ]
        dataset = normalize_event_attendance_rows(rows, "in-memory")

        self.assertEqual(dataset["conference"]["event_count"], 1)
        self.assertEqual(dataset["conference"]["attendee_count"], 2)
        self.assertEqual(len(dataset["entities"]), 3)
        self.assertTrue(any(item["entity_type"] == "resource" for item in dataset["entities"]))
        self.assertTrue(any(item["entity_type"] == "attendee" for item in dataset["entities"]))

    def test_load_event_attendance_rows_supports_csv_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "event_attendance.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "Event ID",
                        "Event Name",
                        "Location",
                        "Date & Time",
                        "Attendee Name",
                        "Attendee Email",
                        "Attendee Phone",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "Event ID": "42",
                        "Event Name": "Climate Networking",
                        "Location": "Cambridge",
                        "Date & Time": "2026-09-18 13:00",
                        "Attendee Name": "Maya Chen",
                        "Attendee Email": "maya@lumengrid.com",
                        "Attendee Phone": "555-3333",
                    }
                )

            rows, source_label = load_event_attendance_rows(csv_path)
            self.assertEqual(len(rows), 1)
            self.assertIn("event_attendance.csv", source_label)

    def test_normalize_gtc_profile_rows_one_row_per_attendee(self) -> None:
        rows = [
            {
                "Name": "Test User",
                "Email": "test@example.com",
                "Education Level": "MS",
                "Major": "CS",
                "Job Title": "Software Engineer",
                "Work Experience": "5 years",
                "Interests": "LLMs; Robotics",
                "Agenda Items": "CUDA Lab | Keynote",
                "Bio/Resume Snippet": "Builds GPU kernels for training.",
            }
        ]
        dataset = normalize_gtc_profile_rows(rows, "in-memory")
        self.assertEqual(dataset["conference"]["source_type"], "gtc-wide-row")
        self.assertEqual(dataset["conference"]["attendee_count"], 1)
        self.assertEqual(dataset["conference"]["event_count"], 1)
        attendees = [e for e in dataset["entities"] if e["entity_type"] == "attendee"]
        sessions = [e for e in dataset["entities"] if e["entity_type"] == "resource"]
        self.assertEqual(len(attendees), 1)
        self.assertEqual(len(sessions), 0)
        self.assertEqual(attendees[0]["title"], "Software Engineer")
        self.assertIn("CUDA Lab", attendees[0]["source_events"])


if __name__ == "__main__":
    unittest.main()
