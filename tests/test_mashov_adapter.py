"""בדיקות מתאם משו״ב מול פיקסצ׳רים בדויים (אף פעם לא נתוני משפחה אמיתיים).

הפיקסצ׳רים עוקבים אחרי הצורות האילוסטרטיביות ב-README של pymashov; המיפוי
מחכה לכיול מול חשבון אמיתי (AGENTS.md צעד 5). הבדיקות נועדו להבטיח שהמתאם
נכשל סגור עם הודעה ברורה, ולא מייצר בריף ריק בשקט.
"""

import json
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from daily_brief.collectors.mashov import CollectorError, map_kid

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SUNDAY = date(2026, 11, 1)  # יום ראשון אמיתי בלוח 2026


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class MashovAdapterTest(unittest.TestCase):
    def test_maps_representative_fixture(self):
        kid = map_kid("דנה", _load("mashov_timetable.json"), _load("mashov_homework.json"), SUNDAY)
        self.assertEqual(kid.name, "דנה")
        # יום 1 (ראשון) בלבד; יום 2 מסונן
        self.assertEqual([l.subject for l in kid.lessons], ["מתמטיקה", "אנגלית"])
        self.assertEqual(kid.lessons[0].teacher, "ד״ר לוי")
        self.assertEqual(kid.homework[0].title, "עמ׳ 42 תרגילים 1-5")
        self.assertEqual(kid.homework[0].due, "3.11.2026")

    def test_wrong_envelope_fails_closed(self):
        with self.assertRaises(CollectorError) as ctx:
            map_kid("דנה", _load("mashov_timetable_wrongshape.json"), [], SUNDAY)
        self.assertIn("מבנה לא מוכר", str(ctx.exception))

    def test_lesson_without_subject_fails_closed(self):
        bad = [{"day": 1, "lessons": [{"time": "08:00", "foo": "bar"}]}]
        with self.assertRaises(CollectorError) as ctx:
            map_kid("דנה", bad, [], SUNDAY)
        self.assertIn("בלי מקצוע מזוהה", str(ctx.exception))

    def test_all_days_filtered_fails_closed(self):
        # אם מספור הימים שונה מההנחה, לא לשדר "אין לימודים" בשקט
        only_other_days = [{"day": 3, "lessons": [{"time": "08:00", "subject": "עברית"}]}]
        with self.assertRaises(CollectorError) as ctx:
            map_kid("דנה", only_other_days, [], SUNDAY)
        self.assertIn("סוננו החוצה", str(ctx.exception))

    def test_empty_raw_is_legitimate(self):
        # רשימות ריקות = באמת אין נתונים (סוף שבוע, אין שיעורים) — מותר
        kid = map_kid("דנה", [], [], SUNDAY)
        self.assertEqual(kid.lessons, [])
        self.assertEqual(kid.homework, [])

    def test_dedup_double_lesson(self):
        dup = [{"day": 1, "lessons": [
            {"time": "08:00", "subject": "מתמטיקה"},
            {"time": "08:00", "subject": "מתמטיקה"},
        ]}]
        kid = map_kid("דנה", dup, [], SUNDAY)
        self.assertEqual(len(kid.lessons), 1)


if __name__ == "__main__":
    unittest.main()
