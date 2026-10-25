"""בדיקות מתאם משו״ב מול פיקסצ׳רים בדויים (אף פעם לא נתוני משפחה אמיתיים).

צורות הפיקסצ׳רים של מערכת ושיעורי-בית אומתו מול משיכה חיה קריאה-בלבד
(25.10.2026; כל הערכים מומצאים). מספור הימים לא אומת — הבדיקות מזריקות
כיול מפורש (day1_weekday="ראשון"), והמתאם נכשל סגור בלעדיו.
צורת השיחות טרם אומתה; המיפוי שלה נבדק ב-tests/test_messages_calendar_state.py.
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
        kid = map_kid(
            "דנה", _load("mashov_timetable.json"), _load("mashov_homework.json"),
            SUNDAY, day1_weekday="ראשון",
        )
        self.assertEqual(kid.name, "דנה")
        # day=1 (ראשון לפי הכיול) בלבד; הרשומה של day=2 מסוננת
        self.assertEqual([l.subject for l in kid.lessons], ["מתמטיקה", "אנגלית"])
        self.assertEqual(kid.lessons[0].time, "שיעור 1")
        self.assertEqual(kid.lessons[0].teacher, "ד״ר לוי")
        self.assertEqual(kid.lessons[0].room, "חדר 12")
        # שיעורי בית: subjectName/homework/remark; lessonDate = תאריך מתן, לא הגשה
        self.assertEqual(kid.homework[0].subject, "מתמטיקה")
        self.assertEqual(kid.homework[0].title, "עמ׳ 42 תרגילים 1-5 — להביא מחשבון")
        self.assertEqual(kid.homework[0].given, "29.10.2026")
        self.assertEqual(kid.homework[0].due, "")

    def test_day_enum_uncalibrated_fails_closed(self):
        with self.assertRaises(CollectorError) as ctx:
            map_kid("דנה", _load("mashov_timetable.json"), [], SUNDAY)
        self.assertIn("MASHOV_DAY1_IS", str(ctx.exception))

    def test_day_enum_invalid_value_fails_closed(self):
        with self.assertRaises(CollectorError) as ctx:
            map_kid("דנה", _load("mashov_timetable.json"), [], SUNDAY, day1_weekday="יום א")
        self.assertIn("אינו יום תקין", str(ctx.exception))

    def test_old_flat_shape_fails_closed(self):
        # הצורה השטוחה שנשערה לפני הכיול מול המקור — חייבת להיכשל סגור
        with self.assertRaises(CollectorError) as ctx:
            map_kid("דנה", _load("mashov_timetable_wrongshape.json"), [], SUNDAY, day1_weekday="ראשון")
        self.assertIn("timeTable/groupDetails", str(ctx.exception))

    def test_non_list_envelope_fails_closed(self):
        with self.assertRaises(CollectorError) as ctx:
            map_kid("דנה", {"timetable": []}, [], SUNDAY, day1_weekday="ראשון")
        self.assertIn("מבנה לא מוכר", str(ctx.exception))

    def test_lesson_without_subject_fails_closed(self):
        bad = [{"timeTable": {"groupId": 1, "day": 1, "lesson": 1, "roomNum": "", "weeks": 0},
                "groupDetails": {"groupId": 1, "groupName": "x", "groupTeachers": []}}]
        with self.assertRaises(CollectorError) as ctx:
            map_kid("דנה", bad, [], SUNDAY, day1_weekday="ראשון")
        self.assertIn("subjectName", str(ctx.exception))

    def test_all_rows_filtered_fails_closed(self):
        only_other_days = [
            {"timeTable": {"groupId": 9, "day": 3, "lesson": 1, "roomNum": "", "weeks": 0},
             "groupDetails": {"groupId": 9, "subjectName": "עברית", "groupTeachers": []}}
        ]
        with self.assertRaises(CollectorError) as ctx:
            map_kid("דנה", only_other_days, [], SUNDAY, day1_weekday="ראשון")
        self.assertIn("סוננו החוצה", str(ctx.exception))

    def test_empty_raw_is_legitimate(self):
        # רשימות ריקות = באמת אין נתונים (סוף שבוע, אין שיעורים) — מותר,
        # גם בלי כיול מספור ימים (אין מה לסנן)
        kid = map_kid("דנה", [], [], SUNDAY)
        self.assertEqual(kid.lessons, [])
        self.assertEqual(kid.homework, [])

    def test_homework_without_homework_field_fails_closed(self):
        bad = [{"lessonId": 1, "lessonDate": "2030-01-01T00:00:00", "subjectName": "מתמטיקה"}]
        with self.assertRaises(CollectorError) as ctx:
            map_kid("דנה", [], bad, SUNDAY)
        self.assertIn("homework", str(ctx.exception))

    def test_dedup_double_lesson(self):
        dup = [
            {"timeTable": {"groupId": 1, "day": 1, "lesson": 1, "roomNum": "א", "weeks": 0},
             "groupDetails": {"groupId": 1, "subjectName": "מתמטיקה", "groupTeachers": []}},
            {"timeTable": {"groupId": 1, "day": 1, "lesson": 1, "roomNum": "א", "weeks": 0},
             "groupDetails": {"groupId": 1, "subjectName": "מתמטיקה", "groupTeachers": []}},
        ]
        kid = map_kid("דנה", dup, [], SUNDAY, day1_weekday="ראשון")
        self.assertEqual(len(kid.lessons), 1)


if __name__ == "__main__":
    unittest.main()
