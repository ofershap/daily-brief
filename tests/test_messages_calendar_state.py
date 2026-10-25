"""בדיקות הודעות/יומן/סמן-ריצה/טעינת env — פיקסצ׳רים בדויים בלבד."""

import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from daily_brief.collectors.ics import events_on, find_conflicts, parse_ics
from daily_brief.collectors.mashov import CollectorError, map_messages
from daily_brief.cli import _load_env_file
from daily_brief.models import SchoolEvent
from daily_brief.state import load_last_success, save_success

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class MessagesTest(unittest.TestCase):
    def test_maps_conversations_fixture(self):
        messages = map_messages(json.loads((FIXTURES / "mashov_conversations.json").read_text(encoding="utf-8")))
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].sender, "המורה שרה")
        self.assertEqual(messages[0].subject, "להביא אישור לטיול עד מחר")
        self.assertFalse(messages[0].has_attachment)
        self.assertTrue(messages[1].has_attachment)

    def test_conversation_without_subject_fails_closed(self):
        with self.assertRaises(CollectorError):
            map_messages([{"sender": "מזכירות"}])

    def test_conversations_wrong_envelope_fails_closed(self):
        with self.assertRaises(CollectorError):
            map_messages({"conversations": []})


class CalendarTest(unittest.TestCase):
    def setUp(self):
        self.events = parse_ics((FIXTURES / "family_calendar.ics").read_text(encoding="utf-8"))

    def test_parses_dates_and_titles(self):
        by_title = {e.title: e for e in self.events}
        self.assertEqual(by_title["טיול שנתי ביום שלישי"].date, "4.11.2026")
        self.assertEqual(by_title["מפגש הורים (בדוי)"].date, "1.11.2026")

    def test_events_on_filters_to_day(self):
        on_sunday = events_on(self.events, date(2026, 11, 1))
        self.assertEqual([e.title for e in on_sunday], ["מפגש הורים (בדוי)"])

    def test_dated_source_conflict_reported(self):
        school = [SchoolEvent(title="טיול שנתי ביום שלישי")]
        conflicts = find_conflicts(school, self.events, "1.11.2026")
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].date_b, "4.11.2026")
        self.assertEqual(conflicts[0].source_b, "יומן")

    def test_same_date_no_conflict(self):
        school = [SchoolEvent(title="מפגש הורים (בדוי)")]
        self.assertEqual(find_conflicts(school, self.events, "1.11.2026"), [])


class StateTest(unittest.TestCase):
    def test_cursor_roundtrip_and_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            self.assertIsNone(load_last_success(path))
            save_success(path)
            loaded = load_last_success(path)
            self.assertIsNotNone(loaded)
            self.assertLess((datetime.now(timezone.utc) - loaded).total_seconds(), 60)

    def test_corrupt_state_treated_as_first_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text("not json", encoding="utf-8")
            self.assertIsNone(load_last_success(path))


class EnvLoadTest(unittest.TestCase):
    def test_env_file_loads_without_clobbering(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "# הערה\nMASHOV_SEMEL=999999\nMASHOV_YEAR=2027\n\nnot-a-pair\n",
                encoding="utf-8",
            )
            os.environ.pop("MASHOV_SEMEL", None)
            os.environ["MASHOV_YEAR"] = "2026"  # קיים מראש — לא נדרס
            _load_env_file(env_path)
            self.assertEqual(os.environ.get("MASHOV_SEMEL"), "999999")
            self.assertEqual(os.environ.get("MASHOV_YEAR"), "2026")

    def test_missing_env_file_is_noop(self):
        _load_env_file(Path("/nonexistent/.env"))  # לא זורק


if __name__ == "__main__":
    unittest.main()
