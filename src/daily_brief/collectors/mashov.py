"""מתאם משו״ב: אוסף מערכת, שיעורי בית וכותרות הודעות דרך pymashov הפתוחה.

מקורות וגבולות ידע:
- נקודות הקצה מאומתות מול הקוד הפתוח של pymashov (mashov/client.py בריפו
  t0mer/pymashov): get_timetable -> GET /api/students/{id}/timetable,
  get_homework -> GET /api/students/{id}/homework, get_conversations(skip,take).
  pymashov מחזירה JSON גולמי בלי מיפוי שדות.
- צורות התשובה של מערכת ושיעורי-בית אומתו מול משיכה חיה קריאה-בלבד
  (25.10.2026, דרך סשן קיים מאושר; הערכים בפיקסצ׳רים מומצאים כולם):
  מערכת = רשימה שטוחה של רשומות {"timeTable": {...}, "groupDetails": {...}};
  שיעורי בית = רשימה שטוחה עם lessonId/lessonDate/lesson/homework/remark/
  subjectName. lessonDate הוא תאריך מתן השיעור — אינו מועד הגשה, ולא ממופה
  ככזה. מספור הימים (day) לא אומת ולכן לא מנוהל לפי הנחה: סינון ליום הנוכחי
  פעיל רק אחרי כיול והגדרת MASHOV_DAY1_IS (ראו .env.example).
- צורת השיחות (conversations) טרם אומתה מול המקור; המיפוי כאן מבוסס צורה
  משוערת ונכשל סגור אם המבנה האמיתי שונה.
- לא נצפה מטא-מידע עימוד ברשימות מערכת/שיעורי-בית; זה אינו הוכחה שהרשימה
  מלאה. אם יתגלה חיתוך, יתועד בכיול החי.
- המתאם נכשל-סגור: מבנה לא מוכר, מפתחות חסרים, או כשל התחברות — CollectorError
  עם הודעה ברורה, ולא בריף "בריא" ריק.
- שימוש אחראי: סשן אחד לכל הילדים, קצב בקשות נמוך, רק החשבון שלך או של
  ילדך. הנתונים הם מידע אישי על קטינים.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import date, datetime

from ..models import WEEKDAYS_HE, DayBrief, Homework, KidBrief, Lesson, SchoolMessage, SourceStatus

REQUIRED_ENV = ("MASHOV_USERNAME", "MASHOV_PASSWORD", "MASHOV_SEMEL", "MASHOV_KIDS")

# שיחות דואר: צורה משוערת בלבד (לא אומתה מול המקור) — נכשל סגור על סטייה.
_MSG_SENDER_KEYS = ("sender", "from", "senderName")
_MSG_SUBJECT_KEYS = ("subject", "title")
_MSG_DATE_KEYS = ("date", "sentDate", "sendDate")
_MSG_ATTACH_KEYS = ("hasAttachments", "hasAttachment", "attachments")


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


def _require_dict(value, what: str) -> dict:
    if not isinstance(value, dict):
        _fail(f"{what} במבנה לא מוכר: {str(value)[:120]}")
    return value


def _first_key(raw: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = raw.get(key)
        if value:
            return str(value)
    return ""


def _format_given(raw) -> str:
    """lessonDate ('2030-01-01T00:00:00') -> '1.1.2030'. לא מועד הגשה!"""
    if not raw:
        return ""
    text = str(raw)
    try:
        parsed = datetime.fromisoformat(text)
        return f"{parsed.day}.{parsed.month}.{parsed.year}"
    except ValueError:
        return text


def _mashov_day_number(today: date, day1_weekday: str) -> int:
    """ממיר תאריך למספר היום של משו״ב, לפי כיול: איזה יום בשבוע הוא day=1."""
    day1_index = WEEKDAYS_HE.index(day1_weekday)
    return ((today.weekday() - day1_index) % 7) + 1


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
        day1_weekday = os.environ.get("MASHOV_DAY1_IS", "").strip()
        return asyncio.run(_collect_all(kids, day1_weekday))


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


async def _collect_all(kids: dict[str, str], day1_weekday: str) -> DayBrief:
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
                kid_briefs.append(map_kid(name, timetable, homework, today, day1_weekday))
                kid = kid_briefs[-1]
                print(
                    f"נאסף ל{name}: {len(kid.lessons)} שיעורים, "
                    f"{len(kid.homework)} שיעורי בית.",
                    file=sys.stderr,
                )
            # הודעות מורים: get_conversations עם skip/take (הפרמטרים היחידים
            # המתועדים ב-pymashov). קבצים מצורפים: מסומנים בלבד, לא מורדים.
            take = int(os.environ.get("MASHOV_MESSAGES_TAKE", "10"))
            conversations = await client.get_conversations(skip=0, take=take)
            messages = map_messages(conversations)
    except CollectorError:
        raise
    except Exception as exc:  # התחברות/רשת/שינוי API — נכשל סגור עם סיבה
        _fail(f"{type(exc).__name__}: {exc}. בדקו פרטי התחברות, ואם תקינים — כיול (AGENTS.md צעד 5).")
    return DayBrief(
        date=f"{today.day}.{today.month}.{today.year}",
        weekday_he=WEEKDAYS_HE[today.weekday()],
        kids=kid_briefs,
        messages=messages,
        sources=[SourceStatus(name="משו״ב", ok=True)],
    )


def map_kid(name: str, timetable, homework, today: date, day1_weekday: str = "") -> KidBrief:
    """ממפה JSON גולמי לטיפוסים המשותפים. נכשל סגור על מבנה לא מוכר.

    day1_weekday: איזה יום בשבוע מייצג day=1 במשו״ב (למשל "ראשון"), כפי
    שאומת בכיול חי. בלי כיול לא מסננים לפי הנחה — נכשל סגור.
    """
    timetable_rows = _require_list(timetable, f"מערכת של {name}")
    homework_rows = _require_list(homework, f"שיעורי בית של {name}")

    if timetable_rows:
        if not day1_weekday:
            _fail(
                "מספור הימים במערכת (day) טרם אומת מול חשבון אמיתי, ולא מניחים אותו. "
                "כיילו לפי AGENTS.md צעד 5 והגדירו MASHOV_DAY1_IS (למשל 'ראשון')."
            )
        if day1_weekday not in WEEKDAYS_HE:
            _fail(f"MASHOV_DAY1_IS={day1_weekday!r} אינו יום תקין ({'/'.join(WEEKDAYS_HE)}).")
    mashov_today = _mashov_day_number(today, day1_weekday) if day1_weekday else None

    lessons: list[Lesson] = []
    skipped_days = 0
    for item in timetable_rows:
        _require_dict(item, f"רשומת מערכת של {name}")
        tt = item.get("timeTable")
        gd = item.get("groupDetails")
        if not isinstance(tt, dict) or not isinstance(gd, dict):
            _fail(
                f"רשומת מערכת בלי timeTable/groupDetails אצל {name}: {str(item)[:120]}. "
                "הצורה המאומתת היא רשומות מקוננות — ככל הנראה דרוש כיול."
            )
        day_num = tt.get("day")
        if mashov_today is not None and day_num != mashov_today:
            skipped_days += 1
            continue
        subject = gd.get("subjectName")
        if not subject:
            _fail(f"שיעור בלי subjectName אצל {name}: {str(item)[:120]}")
        lesson_no = tt.get("lesson")
        if not isinstance(lesson_no, int):
            _fail(f"שיעור בלי מספר שיעור (lesson) אצל {name}: {str(item)[:120]}")
        teachers = gd.get("groupTeachers") or []
        if not isinstance(teachers, list):
            _fail(f"groupTeachers במבנה לא מוכר אצל {name}: {str(item)[:120]}")
        teacher = ", ".join(
            str(t.get("teacherName")) for t in teachers
            if isinstance(t, dict) and t.get("teacherName")
        )
        lessons.append(Lesson(
            time=f"שיעור {lesson_no}",
            subject=str(subject),
            teacher=teacher,
            room=str(tt.get("roomNum") or ""),
        ))
    if timetable_rows and not lessons and skipped_days == len(timetable_rows):
        # ייתכן שהכיול שגוי — לא לשדר "אין לימודים" בשקט.
        _fail(
            f"כל רשומות המערכת של {name} סוננו החוצה ({skipped_days} רשומות). "
            "ככל הנראה MASHOV_DAY1_IS לא תקין — כיילו מחדש."
        )

    homework_items: list[Homework] = []
    for hw in homework_rows:
        _require_dict(hw, f"רשומת שיעורי בית של {name}")
        title = hw.get("homework")
        if not title:
            _fail(f"שיעורי בית בלי שדה homework אצל {name}: {str(hw)[:120]}")
        remark = hw.get("remark")
        if remark:
            title = f"{title} — {remark}"
        homework_items.append(Homework(
            subject=str(hw.get("subjectName") or ""),
            title=str(title),
            due="",  # מועד הגשה אינו מתועד במקור — לא ממפים lessonDate לכאן
            given=_format_given(hw.get("lessonDate")),
        ))

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


def map_messages(conversations) -> list[SchoolMessage]:
    """ממפה שיחות דואר משו״ב להודעות. צורה משוערת — נכשל סגור על סטייה."""
    rows = _require_list(conversations, "שיחות משו״ב")
    messages: list[SchoolMessage] = []
    for raw in rows:
        _require_dict(raw, "רשומת שיחה")
        subject = _first_key(raw, _MSG_SUBJECT_KEYS)
        if not subject:
            _fail(f"שיחה בלי נושא מזוהה: {str(raw)[:120]}")
        attachments = raw.get("attachments")
        has_attachment = any(bool(raw.get(k)) for k in _MSG_ATTACH_KEYS) or (
            isinstance(attachments, list) and len(attachments) > 0
        )
        messages.append(SchoolMessage(
            sender=_first_key(raw, _MSG_SENDER_KEYS),
            subject=subject,
            date=_first_key(raw, _MSG_DATE_KEYS),
            has_attachment=has_attachment,
        ))
    if rows and not messages:
        _fail("שיחות משו״ב לא מופו (מבנה לא מוכר) — דרוש כיול.")
    return messages
