"""בדיקת תאימות SKILL.md לתקן Agent Skills הפתוח (agentskills.io).

זה מבחן התאימות היחיד שאנחנו יכולים להריץ בלי בוט אמיתי: התאמה לתקן
הפורסם. אנחנו לא מכריזים על תאימות לבוט ספציפי בלי מבחן מול הבוט עצמו.
"""

import re
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "skills" / "daily-brief" / "SKILL.md"


class SkillSpecTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")

    def test_frontmatter_present(self):
        self.assertTrue(self.text.startswith("---\n"), "SKILL.md must open with YAML frontmatter")

    def _frontmatter(self):
        return self.text.split("---\n", 2)[1]

    def test_name_matches_directory(self):
        match = re.search(r"^name:\s*(\S+)\s*$", self._frontmatter(), re.M)
        self.assertIsNotNone(match, "frontmatter needs name:")
        self.assertEqual(match.group(1), "daily-brief")
        self.assertLessEqual(len(match.group(1)), 64, "spec: name <= 64 chars")

    def test_description_within_limit(self):
        match = re.search(r"^description:\s*(.+)$", self._frontmatter(), re.M)
        self.assertIsNotNone(match, "frontmatter needs description:")
        self.assertLessEqual(len(match.group(1)), 1024, "spec: description <= 1024 chars")

    def test_under_line_limit(self):
        self.assertLess(len(self.text.splitlines()), 500, "spec: SKILL.md < 500 lines")


if __name__ == "__main__":
    unittest.main()
