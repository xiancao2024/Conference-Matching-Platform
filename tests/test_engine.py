from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from conference_matching.data import normalize_event_attendance_rows, write_normalized_dataset
from conference_matching.engine import build_default_matcher
from conference_matching.evaluation import evaluate


class ConferenceMatcherTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        dataset = normalize_event_attendance_rows(
            [
                {
                    "Event ID": "101",
                    "Event Name": "Health AI Meetup",
                    "Location": "Boston",
                    "Date & Time": "2026-09-18 18:00",
                    "Attendee Name": "Ava Stone",
                    "Attendee Email": "ava@northstar.ai",
                    "Attendee Phone": "555-1111",
                },
                {
                    "Event ID": "102",
                    "Event Name": "Climate Investor Breakfast",
                    "Location": "Cambridge",
                    "Date & Time": "2026-09-19 09:00",
                    "Attendee Name": "Maya Chen",
                    "Attendee Email": "maya@lumengrid.com",
                    "Attendee Phone": "555-2222",
                },
                {
                    "Event ID": "102",
                    "Event Name": "Climate Investor Breakfast",
                    "Location": "Cambridge",
                    "Date & Time": "2026-09-19 09:00",
                    "Attendee Name": "Nadia Torres",
                    "Attendee Email": "nadia@gridworks.com",
                    "Attendee Phone": "555-3333",
                },
            ],
            "test-fixture",
        )
        cls.dataset_path = Path(cls.temp_dir.name) / "conference_kaggle.json"
        write_normalized_dataset(dataset, cls.dataset_path)
        cls.original_data_path = os.environ.get("CONFERENCE_DATA_PATH")
        os.environ["CONFERENCE_DATA_PATH"] = str(cls.dataset_path)
        cls.matcher = build_default_matcher()

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.original_data_path is None:
            os.environ.pop("CONFERENCE_DATA_PATH", None)
        else:
            os.environ["CONFERENCE_DATA_PATH"] = cls.original_data_path
        cls.temp_dir.cleanup()

    def test_session_query_prioritizes_matching_imported_event(self) -> None:
        result = self.matcher.match(
            {
                "role": "participant",
                "stage": "all",
                "target_roles": ["session"],
                "looking_for": ["sessions"],
                "sectors": ["healthcare", "artificial intelligence"],
                "asks": ["Health AI Meetup"],
                "notes": "I want the session related to the Health AI Meetup in Boston.",
            }
        )
        self.assertEqual(result["matches"][0]["role"], "session")
        self.assertEqual(result["matches"][0]["name"], "Health AI Meetup")

    def test_peer_query_can_surface_related_attendee(self) -> None:
        result = self.matcher.match(
            {
                "role": "participant",
                "stage": "all",
                "target_roles": ["participant"],
                "looking_for": ["peers"],
                "sectors": ["climate"],
                "asks": ["Climate Investor Breakfast"],
                "notes": "Find attendees connected to the Climate Investor Breakfast.",
            }
        )
        self.assertEqual(result["matches"][0]["entity_type"], "attendee")
        self.assertIn(result["matches"][0]["name"], {"Maya Chen", "Nadia Torres"})

    def test_result_explanations_are_human_readable(self) -> None:
        result = self.matcher.match(
            {
                "role": "participant",
                "stage": "all",
                "target_roles": ["session"],
                "looking_for": ["sessions"],
                "sectors": ["community"],
                "asks": ["relevant event sessions"],
                "offers": ["shared event context"],
            }
        )
        explanation = result["matches"][0]["explanation"]
        self.assertGreaterEqual(len(explanation), 1)
        self.assertTrue(any("match" in line.lower() or "fit" in line.lower() for line in explanation))

    def test_evaluation_returns_real_data_metrics(self) -> None:
        payload = evaluate()
        self.assertGreater(payload["query_count"], 0)
        self.assertIn("hybrid", payload["summary"])
        self.assertIn("keyword", payload["summary"])
        self.assertTrue(all(0.0 <= row["mrr"] <= 1.0 for row in payload["rows"]))


if __name__ == "__main__":
    unittest.main()
