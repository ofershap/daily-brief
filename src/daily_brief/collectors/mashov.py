"""מתאם משו״ב: אוסף מערכת ושיעורי בית דרך ספריית pymashov הפתוחה.

מקורות וגבולות ידע (מאומת מול הקוד הפתוח של pymashov):
- pymashov קוראת נקודות קצה ומחזירה JSON גולמי בלי מיפוי שדות
  (ראו mashov/client.py בריפו t0mer/pymashov): get_timetable ->
  GET /api/students/{id}/timetable, get_homework ->
  GET /api/students/{id}/homework. שמות השדות בתוך התשובה אינם מתועדים;
  הדוגמאות ב-README של pymashov מסומנות שם כ"אילוסטרטיביות בלבד".
- לכן המתאם כאן נכשל-סגור: מבנה לא מוכר, מפתחות חסרים ברשומות שקיימות,
  או כשל התחברות — כולם זורקים CollectorError עם הודעה ברורה, ולא מייצרים
  בריף "בריא" ריק. מבנה התשובה מאומת מול פיקסצ׳רים בדויים ב-tests/, ומחכה
  לכיול מול חשבון אמיתי (AGENTS.md, צעד 5).
- אין פרמטרי עמוד ב-get_timetable/get_homework של pymashov (בשונה
  מ-get_conversations עם skip/take), ולכן אין טיפול בעמודים כאן; אם יתברר
  שהתשובות נחתכות, זה יתגלה בכיול החי ויתועד.
- שימוש אחראי: סשן אחד לכל הילדים, קצב בקשות נמוך, רק החשבון שלך או של
  ילדך. הנתונים הם מידע אישי על קטינים.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import date

from ..models import WEEKDAYS_HE, DayBrief, Homework, KidBrief, Lesson

REQUIRED_ENV = ("MASHOV_USERNAME", "MASHOV_PASSWORD", "MASHOV_SEMEL", "MASHOV_KIDS")

# מפתחות מקובלים לפי דוגמאות ה-README של pymashov (אילוסטרטיביות!).
_TIMETABLE_DAY_KEYS = ("day",)
_TIMETABLE_LESSONS_KEYS = ("lessons",)
_LESSON_TIME_KEYS = ("time", "hour", "startTime")
_LESSON_SUBJECT_KEYS = ("subject", "subjectName", "name")
_LESSON_TEACHER_KEYS = ("teacher", "teacherName")
_HOMEWORK_SUBJECT_KEYS = ("subject", "subjectName")
_HOMEWORK_TITLE_KEYS = ("description", "title", "homework")
_HOMEWORK_DUE_KEYS = ("dueDate", "due", "date")


class CollectorError(SystemExit):
    """כשל איסוף ברור — תמיד נכשל סגור, אף פעם לא בריף ריק בשקט."""


def _fail(message: str) -> None:
    raise CollectorError(f"מתאם משו״ב נעצר: {message}")


def _require_list(data, what: str) -> list:
    if not isinstance(data, list):
        _fail(
            f"{what} חזר במבנה לא מוכר ({type(data).__name__} במקום list). "
            "ככל הנראה משו״ב שינו את התשובה — דרוש כיול (AGENTS.md צעד 5)."
        )
    return data


def _first_key(raw: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = raw.get(key)
        if value:
            return str(value)
    return ""


class MashovCollector:
    """collect() סינכרוני מבחוץ; בפנים סשן async אחד לכל הילדים."""

    def collect(self) -> DayBrief:
        missing = [key for key in REQUIRED_ENV if not os.environ.get(key)]
        if missing:
            _fail(
                "חסרים משתני סביבה: " + ", ".join(missing) +
                ". העתיקו .env.example ל-.env ומלאו, או הגדירו אותם ידנית."
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
            _fail(f"רשומת ילד לא תקינה ב-MASHOV_KIDS: {item!r} (צפוי שם=מזהה)")
        pairs[name.strip()] = student_id.strip()
    if not pairs:
        _fail("MASHOV_KIDS ריק: צפוי פורמט שם=מזהה, מופרד בפסיקים")
    return pairs


async def _collect_all(kids: dict[str, str]) -> DayBrief:
    try:
        from mashov import MashovClient  # pymashov; מותקן רק כשצריך
    except ImportError as exc:
        raise CollectorError("מתאם משו״ב נעצר: התקינו את התלות: pip install pymashov") from exc

    today = date.today()
    try:
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
                kid_briefs.append(map_kid(name, timetable, homework, today))
                kid = kid_briefs[-1]
                print(
                    f"נאסף ל{name}: {len(kid.lessons)} שיעורים, "
                    f"{len(kid.homework)} שיעורי בית.",
                    file=sys.stderr,
                )
    except CollectorError:
        raise
    except Exception as exc:  # התחברות/רשת/שינוי API — נכשל סגור עם סיבה
        _fail(f"{type(exc).__name__}: {exc}. בדקו פרטי התחברות, ואם תקינים — כיול (AGENTS.md צעד 5).")
    return DayBrief(
        date=f"{today.day}.{today.month}.{today.year}",
        weekday_he=WEEKDAYS_HE[today.weekday()],
        kids=kid_briefs,
    )


def map_kid(name: str, timetable, homework, today: date) -> KidBrief:
    """ממפה JSON גולמי לטיפוסים המשותפים. נכשל סגור על מבנה לא מוכר."""
    timetable_rows = _require_list(timetable, f"מערכת של {name}")
    homework_rows = _require_list(homework, f"שיעורי בית של {name}")

    lessons: list[Lesson] = []
    # צורה לפי דוגמאות pymashov: רשימת ימים, כל יום עם 'day' ו-'lessons'.
    # מספור הימים לא מתועד; ההנחה ראשון=1..שבת=7, והכיול החי יאמת.
    mashov_today = (today.weekday() + 2) % 7 or 7
    skipped_days = 0
    for day in timetable_rows:
        if not isinstance(day, dict) or "lessons" not in day:
            _fail(f"רשומת יום לא מוכרת במערכת של {name}: {str(day)[:120]}")
        day_num = day.get("day")
        if day_num is not None and day_num != mashov_today:
            skipped_days += 1
            continue  # מסננים ליום הנוכחי; בלי מספר יום ניקח הכל
        for raw in day.get("lessons") or []:
            if not isinstance(raw, dict):
                _fail(f"רשומת שיעור לא מוכרת אצל {name}: {str(raw)[:120]}")
            subject = _first_key(raw, _LESSON_SUBJECT_KEYS)
            if not subject:
                _fail(f"שיעור בלי מקצוע מזוהה אצל {name}: {str(raw)[:120]}")
            lessons.append(Lesson(
                time=_first_key(raw, _LESSON_TIME_KEYS),
                subject=subject,
                teacher=_first_key(raw, _LESSON_TEACHER_KEYS),
                room=str(raw.get("room", "")),
            ))
    if timetable_rows and not lessons and skipped_days == len(timetable_rows):
        # ייתכן שמספור הימים שונה מן ההנחה — לא לשדר "אין לימודים" בשקט.
        _fail(
            f"כל ימי המערכת של {name} סוננו החוצה ({skipped_days} ימים). "
            "ככל הנראה מספור הימים שונה מההנחה ראשון=1 — דרוש כיול."
        )

    homework_items: list[Homework] = []
    for hw in homework_rows:
        if not isinstance(hw, dict):
            _fail(f"רשומת שיעורי בית לא מוכרת אצל {name}: {str(hw)[:120]}")
        title = _first_key(hw, _HOMEWORK_TITLE_KEYS)
        if not title:
            _fail(f"שיעורי בית בלי תיאור מזוהה אצל {name}: {str(hw)[:120]}")
        homework_items.append(Homework(
            subject=_first_key(hw, _HOMEWORK_SUBJECT_KEYS),
            title=title,
            due=_first_key(hw, _HOMEWORK_DUE_KEYS),
        ))
    if homework_rows and not homework_items:
        _fail(f"שיעורי הבית של {name} לא מופו (מבנה לא מוכר) — דרוש כיול.")

    return KidBrief(name=name, lessons=dedup_lessons(lessons), homework=homework_items)


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
