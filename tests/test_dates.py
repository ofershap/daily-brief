"""רגרסיות תאריכים: יום שבוע מחושב מול לוח אמיתי, חוצי שנה/חודש,
וטיפול מפורש ביום-שבוע מיושן שרשום בכותרת."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from daily_brief.collectors.ics import stale_weekday_notes
from daily_brief.models import SchoolEvent, weekday_he


class WeekdayHeTest(unittest.TestCase):
    def test_known_dates(self):
        self.assertEqual(weekday_he("1.11.2026"), "ראשון")
        self.assertEqual(weekday_he("3.11.2026"), "שלישי")
        self.assertEqual(weekday_he("4.11.2026"), "רביעי")

    def test_cross_month_boundary(self):
        self.assertEqual(weekday_he("31.10.2026"), "שבת")
        self.assertEqual(weekday_he("30.11.2026"), "שני")
        self.assertEqual(weekday_he("1.12.2026"), "שלישי")

    def test_cross_year_boundary(self):
        self.assertEqual(weekday_he("31.12.2026"), "חמישי")
        self.assertEqual(weekday_he("1.1.2027"), "שישי")

    def test_invalid_returns_empty(self):
        self.assertEqual(weekday_he(""), "")
        self.assertEqual(weekday_he("32.13.2026"), "")
        self.assertEqual(weekday_he("לא תאריך"), "")


class StaleWeekdayTest(unittest.TestCase):
    def test_stale_embedded_weekday_flagged(self):
        # "ביום שלישי" על 4.11.2026 (רביעי) — סתירה מדווחת, לא תוקנה בשקט
        events = [SchoolEvent(title="טיול שנתי ביום שלישי", date="4.11.2026")]
        notes = stale_weekday_notes(events, weekday_he)
        self.assertEqual(len(notes), 1)
        self.assertIn("יום שלישי", notes[0])
        self.assertIn("יום רביעי", notes[0])

    def test_consistent_weekday_not_flagged(self):
        events = [SchoolEvent(title="טיול שנתי ביום שלישי", date="3.11.2026")]
        self.assertEqual(stale_weekday_notes(events, weekday_he), [])

    def test_undated_event_not_flagged(self):
        events = [SchoolEvent(title="טיול שנתי ביום שלישי")]
        self.assertEqual(stale_weekday_notes(events, weekday_he), [])

    def test_no_weekday_in_title_not_flagged(self):
        events = [SchoolEvent(title="טיול שנתי", date="4.11.2026")]
        self.assertEqual(stale_weekday_notes(events, weekday_he), [])


if __name__ == "__main__":
    unittest.main()
