"""מתאם יומן: קורא קובץ ICS מקומי או URL ציבורי, בספרייה סטנדרטית בלבד.

הצלבת מקורות: אירוע בית ספר שמופיע גם ביומן אבל בתאריך אחר מדווח כסתירה
מתוארכת בין מקורות (ראו find_conflicts). זו ההשוואה הזולה והדטרמיניסטית;
אין כאן התחברות ליומן גוגל — מי שרוצה מייצא ICS ציבורי/מקומי.
"""

from __future__ import annotations

import urllib.request
from datetime import date

from ..models import CalendarEvent, SchoolEvent, SourceConflict


def _unfold(text: str) -> list[str]:
    """שורות ICS ארוכות נמשכות בשורה הבאה עם רווח/טאב מוביל."""
    lines: list[str] = []
    for line in text.splitlines():
        if line[:1] in (" ", "\t") and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


def parse_ics(text: str) -> list[CalendarEvent]:
    events: list[CalendarEvent] = []
    current: dict[str, str] | None = None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT" and current is not None:
            summary = current.get("SUMMARY", "").strip()
            dtstart = current.get("DTSTART", "")
            if summary and dtstart:
                events.append(CalendarEvent(title=summary, date=_ics_date(dtstart)))
            current = None
        elif current is not None and ":" in line:
            key, _, value = line.partition(":")
            key = key.split(";")[0]  # DTSTART;VALUE=DATE:20261103
            current[key] = value
    return events


def _ics_date(dtstart: str) -> str:
    """20261103 או 20261103T090000 -> 3.11.2026. לא מזוהה -> מוחזר גולמי."""
    raw = dtstart.strip()[:8]
    if len(raw) == 8 and raw.isdigit():
        return f"{int(raw[6:8])}.{int(raw[4:6])}.{raw[0:4]}"
    return dtstart.strip()


def collect(source: str) -> list[CalendarEvent]:
    """source: נתיב קובץ מקומי או http(s) URL. נכשל סגור עם סיבה."""
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source, timeout=15) as resp:  # noqa: S310 - URL שהמשתמש הגדיר
            text = resp.read().decode("utf-8")
    else:
        with open(source, encoding="utf-8") as fh:
            text = fh.read()
    return parse_ics(text)


def find_conflicts(
    school_events: list[SchoolEvent], calendar_events: list[CalendarEvent]
) -> list[SourceConflict]:
    """אותו אירוע עם תאריך ידוע, תאריך שונה בין משו״ב ליומן = סתירה מתוארכת.

    משווים את תאריך האירוע עצמו, אף פעם לא תאריך הבריף. אירוע בלי תאריך
    במקור לא משתתף בהשוואה — לא ממציאים לו תאריך.
    """
    conflicts: list[SourceConflict] = []
    by_title = {event.title.strip(): event for event in calendar_events}
    for event in school_events:
        if not event.date:
            continue
        match = by_title.get(event.title.strip())
        if match and match.date != event.date:
            conflicts.append(SourceConflict(
                title=event.title,
                date_a=event.date, source_a="משו״ב",
                date_b=match.date, source_b=match.source,
            ))
    return conflicts


WEEKDAY_NAMES = {name: index for index, name in enumerate(
    ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
)}


def stale_weekday_notes(events, weekday_he_fn) -> list[str]:
    """אזהרה כשיום השבוע שרשום בכותרת סותר את התאריך המחושב.

    למשל "טיול ביום שלישי" על תאריך שיוצא רביעי — סימן לתאריך מיושן
    במקור. מדווח, לא מתקן בשקט.
    """
    notes: list[str] = []
    for event in events:
        if not event.date:
            continue
        for name in WEEKDAY_NAMES:
            if f"יום {name}" in event.title:
                actual = weekday_he_fn(event.date)
                if actual and actual != name:
                    notes.append(
                        f'בכותרת "{event.title}" כתוב יום {name}, '
                        f"אבל {event.date} יוצא יום {actual}"
                    )
    return notes


def events_on(events: list[CalendarEvent], day: date) -> list[CalendarEvent]:
    target = f"{day.day}.{day.month}.{day.year}"
    return [event for event in events if event.date == target]
