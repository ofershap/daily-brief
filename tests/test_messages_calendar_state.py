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
from daily_brief.models import SchoolEvent, weekday_he
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
        self.events = parse_ics((FIXTURES / "family_calendar.ics").read_text(encoding="utf-8")).events

    def test_parses_dates_and_titles(self):
        by_title = {e.title: e for e in self.events}
        self.assertEqual(by_title["טיול שנתי ביום שלישי"].date, "4.11.2026")
        self.assertEqual(by_title["מפגש הורים (בדוי)"].date, "1.11.2026")

    def test_events_on_filters_to_day(self):
        on_sunday = events_on(self.events, date(2026, 11, 1))
        self.assertEqual([e.title for e in on_sunday], ["מפגש הורים (בדוי)"])

    def test_dated_source_conflict_reported(self):
        school = [SchoolEvent(title="טיול שנתי ביום שלישי", date="3.11.2026")]
        conflicts = find_conflicts(school, self.events)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].date_a, "3.11.2026")  # תאריך האירוע, לא של הבריף
        self.assertEqual(conflicts[0].date_b, "4.11.2026")
        self.assertEqual(conflicts[0].source_b, "יומן")

    def test_same_date_no_conflict(self):
        school = [SchoolEvent(title="מפגש הורים (בדוי)", date="1.11.2026")]
        self.assertEqual(find_conflicts(school, self.events), [])

    def test_undated_school_event_never_conflicts(self):
        # אין להמציא לאירוע תאריך (למשל תאריך הבריף) כדי להשוות
        school = [SchoolEvent(title="טיול שנתי ביום שלישי")]
        self.assertEqual(find_conflicts(school, self.events), [])


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


class IcsAcceptanceTest(unittest.TestCase):
    """קבלת ICS: חזרות, אזורי זמן, EXDATE, כל-היום, שורות מקופלות —
    שום דבר לא נשמט או מוזז בשקט; לא-נתמך = אזהרת חלקיות מפורשת."""

    def test_weekly_recurrence_with_count(self):
        ics = "\r\n".join([
            "BEGIN:VCALENDAR", "VERSION:2.0", "BEGIN:VEVENT",
            "UID:x1@t", "DTSTART;VALUE=DATE:20261104",  # רביעי 4.11
            "SUMMARY:שיעור נגינה (בדוי)",
            "RRULE:FREQ=WEEKLY;COUNT=3",
            "END:VEVENT", "END:VCALENDAR",
        ])
        events = parse_ics(ics).events
        # 3 מועדים: 4.11, 11.11, 18.11 — ולא 25.11
        self.assertEqual([e.title for e in events_on(events, date(2026, 11, 11))], ["שיעור נגינה (בדוי)"])
        self.assertEqual([e.title for e in events_on(events, date(2026, 11, 18))], ["שיעור נגינה (בדוי)"])
        self.assertEqual(events_on(events, date(2026, 11, 25)), [])
        self.assertEqual(events_on(events, date(2026, 11, 12)), [])

    def test_weekly_byday_and_interval(self):
        ics = "\r\n".join([
            "BEGIN:VCALENDAR", "BEGIN:VEVENT",
            "UID:x2@t", "DTSTART;VALUE=DATE:20261102",  # שני 2.11
            "SUMMARY:אימון (בדוי)", "RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,WE",
            "END:VEVENT", "END:VCALENDAR",
        ])
        events = parse_ics(ics).events
        self.assertTrue(events_on(events, date(2026, 11, 2)))    # שני שבוע 0
        self.assertTrue(events_on(events, date(2026, 11, 4)))    # רביעי שבוע 0
        self.assertEqual(events_on(events, date(2026, 11, 9)), [])   # שבוע 1 — מדולג
        self.assertTrue(events_on(events, date(2026, 11, 16)))   # שבוע 2

    def test_exdate_excludes_occurrence(self):
        ics = "\r\n".join([
            "BEGIN:VCALENDAR", "BEGIN:VEVENT",
            "UID:x3@t", "DTSTART;VALUE=DATE:20261104",
            "SUMMARY:חוג (בדוי)", "RRULE:FREQ=WEEKLY;COUNT=3",
            "EXDATE;VALUE=DATE:20261111",
            "END:VEVENT", "END:VCALENDAR",
        ])
        events = parse_ics(ics).events
        self.assertEqual(events_on(events, date(2026, 11, 11)), [])  # הוחרג
        self.assertTrue(events_on(events, date(2026, 11, 18)))

    def test_utc_datetime_not_silently_shifted(self):
        # 22:30 UTC ב-1.11 = 00:30 ב-2.11 בארץ (UTC+2 בשאון חורף)
        ics = "\r\n".join([
            "BEGIN:VCALENDAR", "BEGIN:VEVENT",
            "UID:x4@t", "DTSTART:20261101T223000Z",
            "SUMMARY:שידור חי (בדוי)",
            "END:VEVENT", "END:VCALENDAR",
        ])
        events = parse_ics(ics).events
        self.assertEqual(events[0].date, "2.11.2026")

    def test_tzid_datetime_keeps_written_date(self):
        ics = "\r\n".join([
            "BEGIN:VCALENDAR", "BEGIN:VEVENT",
            "UID:x5@t", "DTSTART;TZID=Asia/Jerusalem:20261101T090000",
            "SUMMARY:בוקר (בדוי)",
            "END:VEVENT", "END:VCALENDAR",
        ])
        events = parse_ics(ics).events
        self.assertEqual(events[0].date, "1.11.2026")

    def test_unsupported_recurrence_warns_and_shows_first_only(self):
        ics = "\r\n".join([
            "BEGIN:VCALENDAR", "BEGIN:VEVENT",
            "UID:x6@t", "DTSTART;VALUE=DATE:20261104",
            "SUMMARY:יום הולדת (בדוי)", "RRULE:FREQ=YEARLY",
            "END:VEVENT", "END:VCALENDAR",
        ])
        result = parse_ics(ics)
        self.assertEqual(result.events[0].date, "4.11.2026")
        self.assertTrue(any("לא נתמכת" in w for w in result.warnings))
        self.assertEqual(events_on(result.events, date(2027, 11, 4)), [])

    def test_event_without_dtstart_warns_not_dropped(self):
        ics = "\r\n".join([
            "BEGIN:VCALENDAR", "BEGIN:VEVENT",
            "UID:x7@t", "SUMMARY:ללא תאריך (בדוי)",
            "END:VEVENT", "END:VCALENDAR",
        ])
        result = parse_ics(ics)
        self.assertEqual(result.events, [])
        self.assertTrue(any("בלי DTSTART" in w for w in result.warnings))

    def test_folded_summary_line(self):
        ics = "\r\n".join([
            "BEGIN:VCALENDAR", "BEGIN:VEVENT",
            "UID:x8@t", "DTSTART;VALUE=DATE:20261104",
            "SUMMARY:כותרת ארוכה מאוד שנמשכת",
            " בשורה הבאה (בדוי)",
            "END:VEVENT", "END:VCALENDAR",
        ])
        result = parse_ics(ics)
        self.assertEqual(result.events[0].title, "כותרת ארוכה מאוד שנמשכתבשורה הבאה (בדוי)")

    def test_rdate_warns(self):
        ics = "\r\n".join([
            "BEGIN:VCALENDAR", "BEGIN:VEVENT",
            "UID:x9@t", "DTSTART;VALUE=DATE:20261104",
            "SUMMARY:מיוחד (בדוי)", "RDATE;VALUE=DATE:20261204",
            "END:VEVENT", "END:VCALENDAR",
        ])
        result = parse_ics(ics)
        self.assertTrue(any("RDATE" in w for w in result.warnings))

    def test_until_bounds_recurrence(self):
        ics = "\r\n".join([
            "BEGIN:VCALENDAR", "BEGIN:VEVENT",
            "UID:x10@t", "DTSTART;VALUE=DATE:20261104",
            "SUMMARY:סידרה (בדוי)", "RRULE:FREQ=DAILY;UNTIL=20261106",
            "END:VEVENT", "END:VCALENDAR",
        ])
        events = parse_ics(ics).events
        self.assertTrue(events_on(events, date(2026, 11, 6)))
        self.assertEqual(events_on(events, date(2026, 11, 7)), [])
