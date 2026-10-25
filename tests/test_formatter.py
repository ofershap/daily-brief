"""בדיקות המעצב על נתוני הדמו הבדויים בלבד."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from daily_brief.collectors import demo
from daily_brief.formatters import format_brief


class FormatterTest(unittest.TestCase):
    def setUp(self):
        self.text = format_brief(demo.collect())

    def test_header_has_date_and_weekday(self):
        self.assertIn("יום ראשון, 1.11.2026", self.text)
        self.assertTrue(self.text.startswith("🎒 *בריף בית ספר"))

    def test_all_kids_present(self):
        self.assertIn("*דנה*", self.text)
        self.assertIn("*איתמר*", self.text)

    def test_lessons_and_homework_lines(self):
        self.assertIn("🕐 *מערכת:*", self.text)
        self.assertIn("08:00 מתמטיקה (ד״ר לוי)", self.text)
        self.assertIn("📚 *שיעורי בית:* מתמטיקה - עמ׳ 42 תרגילים 1-5 (להגשה 3.11)", self.text)

    def test_events_and_notes(self):
        self.assertIn("📣 *אירוע:* טיול שנתי (3.11.2026) - להביא אישור הורה חתום", self.text)
        self.assertIn("✏️ מחר חינוך גופני", self.text)

    def test_whatsapp_bold_markers_kept_literal(self):
        # הבוט שולח כמו שזה; הכוכביות הן עיצוב וואטסאפ, לא להמיר.
        self.assertIn("*מערכת:*", self.text)


if __name__ == "__main__":
    unittest.main()
