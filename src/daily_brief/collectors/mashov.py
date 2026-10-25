"""מתאם משו״ב: אוסף מערכת ושיעורי בית דרך ספריית pymashov הפתוחה.

הערות שימוש אחראי (גם ב-README):
- pymashov היא ספרייה לא-רשמית שמדברת עם אותו API שהאתר של משו״ב משתמש בו;
  ה-API לא מתועד ויכול להשתנות בלי התראה.
- שמות השדות בתשובות משו״ב אינם מתועדים. המיפוי כאן סובלני (get עם ברירות
  מחדל) ונועד לכיול חד-פעמי מול החשבון שלכם — ראו AGENTS.md, צעד 5.
- סשן אחד לכל הילדים: התחברות אחת בלבד בכל הרצה, כדי לא להציף את המערכת
  בהתחברויות (ריבוי התחברויות עלול להיראות כמו התקפה).
- רק החשבון שלכם או של ילדכם. הנתונים הם מידע אישי על קטינים.
"""

from __future__ import annotations

import asyncio
import os
from datetime import date

from ..models import WEEKDAYS_HE, DayBrief, Homework, KidBrief, Lesson
from .base import Collector  # noqa: F401  (ממש את החוזה)

REQUIRED_ENV = ("MASHOV_USERNAME", "MASHOV_PASSWORD", "MASHOV_SEMEL", "MASHOV_KIDS")


class MashovCollector:
    """collect() סינכרוני מבחוץ; בפנים סשן async אחד לכל הילדים."""

    def collect(self) -> DayBrief:
        missing = [key for key in REQUIRED_ENV if not os.environ.get(key)]
        if missing:
            raise SystemExit(
                "חסרים משתני סביבה: " + ", ".join(missing) +
                "\nהעתיקו .env.example ל-.env ומלאו, או הגדירו אותם ידנית."
            )
        kids = _parse_kids(os.environ["MASHOV_KIDS"])
        return asyncio.run(_collect_all(kids))


def _parse_kids(raw: str) -> dict[str, str]:
    """'דנה=123456,איתמר=123457' -> {'דנה': '123456', 'איתמר': '123457'}"""
    pairs = {}
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        name, sep, student_id = item.partition("=")
        if not sep:
            raise SystemExit(f"רשומת ילד לא תקינה ב-MASHOV_KIDS: {item!r} (צפוי שם=מזהה)")
        pairs[name.strip()] = student_id.strip()
    if not pairs:
        raise SystemExit("MASHOV_KIDS ריק: צפוי פורמט שם=מזהה, מופרד בפסיקים")
    return pairs


async def _collect_all(kids: dict[str, str]) -> DayBrief:
    try:
        from mashov import MashovClient  # pymashov; מותקן רק כשצריך
    except ImportError as exc:
        raise SystemExit("התקינו את תלות המשו״ב: pip install pymashov") from exc

    today = date.today()
    async with MashovClient(
        username=os.environ["MASHOV_USERNAME"],
        password=os.environ["MASHOV_PASSWORD"],
        semel=os.environ["MASHOV_SEMEL"],
        year=os.environ.get("MASHOV_YEAR", "2026"),
    ) as client:
        # התחברות אחת (auto_login בקריאה הראשונה) משמשת את כל הילדים.
        kid_briefs = []
        for name, student_id in kids.items():
            timetable = await client.get_timetable(student_id)
            homework = await client.get_homework(student_id)
            kid_briefs.append(_map_kid(name, timetable, homework, today))
    return DayBrief(
        date=f"{today.day}.{today.month}.{today.year}",
        weekday_he=WEEKDAYS_HE[today.weekday()],
        kids=kid_briefs,
    )


def _map_kid(name: str, timetable, homework, today: date) -> KidBrief:
    """ממפה JSON גולמי של משו״ב לטיפוסים המשותפים, בסובלנות לשמות שדות."""
    lessons: list[Lesson] = []
    # צורה מתועדת בדוגמאות pymashov: רשימת ימים, כל יום עם 'day' ו-'lessons'.
    # מספור הימים במשו״ב לא מתועד; ההנחה ראשון=1..שבת=7, והכיול החי (צעד 5) יאמת.
    mashov_today = (today.weekday() + 2) % 7 or 7
    for day in timetable or []:
        day_num = day.get("day") if isinstance(day, dict) else None
        if day_num is not None and day_num != mashov_today:
            continue  # מסננים ליום הנוכחי; בלי מספר יום ניקח הכל
        for raw in (day.get("lessons", []) if isinstance(day, dict) else []):
            lessons.append(Lesson(
                time=str(raw.get("time", "")),
                subject=str(raw.get("subject", "")),
                teacher=str(raw.get("teacher", "")),
                room=str(raw.get("room", "")),
            ))
    homework_items = [
        Homework(
            subject=str(hw.get("subject", "")),
            title=str(hw.get("description", hw.get("title", ""))),
            due=str(hw.get("dueDate", "")),
        )
        for hw in (homework or [])
        if isinstance(hw, dict)
    ]
    return KidBrief(name=name, lessons=lessons, homework=homework_items)


# דה-דופליקציה: אם אותו שיעור חוזר (למשל שעור כפול), נשאיר רשומה אחת לזמן+מקצוע.
def dedup_lessons(lessons: list[Lesson]) -> list[Lesson]:
    seen: set[tuple[str, str]] = set()
    out = []
    for lesson in lessons:
        key = (lesson.time, lesson.subject)
        if key not in seen:
            seen.add(key)
            out.append(lesson)
    return out
