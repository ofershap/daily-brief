"""מתאם יומן: קורא קובץ ICS מקומי או URL ציבורי, בספרייה סטנדרטית בלבד.

הצלבת מקורות: אירוע בית ספר שמופיע גם ביומן אבל בתאריך אחר מדווח כסתירה
מתוארכת בין מקורות (ראו find_conflicts). זו ההשוואה הזולה והדטרמיניסטית;
אין כאן התחברות ליומן גוגל — מי שרוצה מייצא ICS ציבורי/מקומי.

גבולות מוצהרים (במכוונה לא מנקה-יומן מלא):
- RRULE נתמך רק בצורות DAILY/WEEKLY עם INTERVAL/COUNT/UNTIL/BYDAY, ו-EXDATE.
  כל חזרה אחרת (MONTHLY/YEARLY/BYSETPOS/...) או RDATE — מוצג המועד הראשון
  ונרשמת אזהרת "חלקי" מפורשת; אף אירוע לא נשמט בשקט.
- DTSTART עם Z (UTC) מומר ל-Asia/Jerusalem דרך zoneinfo; אם ההמרה לא
  אפשרית — נשמר התאריך הגולמי ונרשמת אזהרה, כדי שלא "יזוז" בשקט.
- DTSTART עם TZID: התאריך נלקח כפי שכתוב (זה התאריך באזור-הזמן של האירוע).
- אירוע בלי DTSTART לא נשמט בשקט — נרשמת אזהרה.
"""

from __future__ import annotations

import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from ..models import CalendarEvent, SchoolEvent, SourceConflict

LOCAL_TZ = "Asia/Jerusalem"

_WEEKDAY_TOKEN = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
_SUPPORTED_RRULE_KEYS = {"FREQ", "INTERVAL", "COUNT", "UNTIL", "BYDAY", "WKST"}


@dataclass
class IcsResult:
    events: list[CalendarEvent] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _unfold(text: str) -> list[str]:
    """שורות ICS ארוכות נמשכות בשורה הבאה עם רווח/טאב מוביל."""
    lines: list[str] = []
    for line in text.splitlines():
        if line[:1] in (" ", "\t") and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


def _split_prop(line: str) -> tuple[str, dict[str, str], str]:
    """'DTSTART;TZID=Asia/Jerusalem:20261101T090000' -> ('DTSTART', {'TZID': ...}, '...')"""
    head, _, value = line.partition(":")
    parts = head.split(";")
    params: dict[str, str] = {}
    for part in parts[1:]:
        key, _, val = part.partition("=")
        params[key.strip().upper()] = val.strip()
    return parts[0].strip().upper(), params, value


def _parse_ics_datetime(raw: str, params: dict[str, str], warnings: list[str], title: str) -> str:
    """מחזיר DD.MM.YYYY. מטפל ב-VALUE=DATE, ב-UTC (Z) עם המרה מוצהרת, וב-TZID."""
    value = raw.strip()
    if len(value) >= 8 and value[:8].isdigit():
        year, month, day = int(value[0:4]), int(value[4:6]), int(value[6:8])
        if "T" in value and value.endswith("Z"):
            # UTC אמיתי: ממירים ל-Asia/Jerusalem כדי שהתאריך לא "יזוז" בשקט
            try:
                from zoneinfo import ZoneInfo
                naive = datetime.strptime(value, "%Y%m%dT%H%M%SZ")
                local = naive.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo(LOCAL_TZ))
                return f"{local.day}.{local.month}.{local.year}"
            except Exception:
                warnings.append(
                    f'אירוע "{title}": שעת UTC ({value}) לא הומרה לאזור המקומי — '
                    "התאריך עלול לזוז ביום. הוצג כפי שכתוב."
                )
                return f"{day}.{month}.{year}"
        # floating או TZID: התאריך כפי שכתוב הוא התאריך באזור של האירוע
        return f"{day}.{month}.{year}"
    warnings.append(f'אירוע "{title}": DTSTART לא מזוהה ({value!r}) — הוצג גולמי.')
    return value


def _parse_rrule(raw: str) -> dict[str, str]:
    rule: dict[str, str] = {}
    for part in raw.split(";"):
        key, _, val = part.partition("=")
        rule[key.strip().upper()] = val.strip().upper()
    return rule


def _date_from_ics(raw: str) -> date | None:
    raw = raw.strip()
    if len(raw) >= 8 and raw[:8].isdigit():
        return date(int(raw[0:4]), int(raw[4:6]), int(raw[6:8]))
    return None


def _occurs_on(event: CalendarEvent, target: date) -> bool:
    """האם האירוע (כולל חזרה נתמכת) מתרחש ב-target. דטרמיניסטי ומוגבל."""
    start = _parse_dmy(event.date)
    if start is None:
        return False
    if target == start:
        return target.isoformat() not in event.exdates
    if not event.rrule:
        return False
    rule = _parse_rrule(event.rrule)
    freq = rule.get("FREQ")
    if freq not in ("DAILY", "WEEKLY"):
        return False  # צורה לא נתמכת — כבר אווזהר בפרסור; לא מנחשים
    interval = int(rule.get("INTERVAL", "1") or "1")
    if interval < 1:
        return False
    until = _date_from_ics(rule.get("UNTIL", ""))
    if until and target > until:
        return False
    if target < start:
        return False

    matches = False
    if freq == "DAILY":
        matches = (target - start).days % interval == 0
    else:  # WEEKLY
        byday = rule.get("BYDAY")
        if byday:
            days = {_WEEKDAY_TOKEN[t] for t in byday.split(",") if t in _WEEKDAY_TOKEN}
        else:
            days = {start.weekday()}
        matches = target.weekday() in days and _weeks_between(start, target) % interval == 0
    if not matches:
        return False
    # COUNT: סופרים מועדים מתחילת החזרה עד target (כולל)
    count = rule.get("COUNT")
    if count and count.isdigit():
        occurrences = 0
        day = start
        while day <= target:
            if _occurs_on_simple(start, rule, interval, day):
                occurrences += 1
            day += timedelta(days=1)
        if occurrences > int(count):
            return False
    return target.isoformat() not in event.exdates


def _weeks_between(start: date, target: date) -> int:
    return (target - start).days // 7


def _occurs_on_simple(start: date, rule: dict[str, str], interval: int, day: date) -> bool:
    if day < start:
        return False
    freq = rule.get("FREQ")
    if freq == "DAILY":
        return (day - start).days % interval == 0
    byday = rule.get("BYDAY")
    if byday:
        days = {_WEEKDAY_TOKEN[t] for t in byday.split(",") if t in _WEEKDAY_TOKEN}
    else:
        days = {start.weekday()}
    return day.weekday() in days and _weeks_between(start, day) % interval == 0


def _parse_dmy(value: str) -> date | None:
    try:
        day, month, year = (int(part) for part in value.split("."))
        return date(year, month, day)
    except (ValueError, AttributeError):
        return None


def parse_ics(text: str) -> IcsResult:
    result = IcsResult()
    current: dict[str, tuple[dict[str, str], str]] | None = None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT" and current is not None:
            summary = current.get("SUMMARY", ({}, ""))[1].strip()
            dtstart_params, dtstart_raw = current.get("DTSTART", ({}, ""))
            if summary and dtstart_raw:
                rrule_params, rrule_raw = current.get("RRULE", ({}, ""))
                exdate_raws = [v for k, (p, v) in current.items() if k == "EXDATE" or k.startswith("EXDATE#")]
                event_date = _parse_ics_datetime(dtstart_raw, dtstart_params, result.warnings, summary)
                rrule = rrule_raw.strip()
                if rrule:
                    rule = _parse_rrule(rrule)
                    unsupported = set(rule) - _SUPPORTED_RRULE_KEYS
                    if rule.get("FREQ") not in ("DAILY", "WEEKLY") or unsupported:
                        result.warnings.append(
                            f'אירוע "{summary}": חזרה בתבנית לא נתמכת ({rrule[:80]}) — '
                            "מוצג המועד הראשון בלבד; מועדים חוזרים לא יופיעו."
                        )
                        rrule = ""  # לא לחשב מועדים של תבנית לא נתמכת
                exdates: set[str] = set()
                for raw_ex in exdate_raws:
                    for piece in raw_ex.split(","):
                        parsed = _date_from_ics(piece)
                        if parsed:
                            exdates.add(parsed.isoformat())
                if current.get("RDATE"):
                    result.warnings.append(
                        f'אירוע "{summary}": RDATE לא נתמך — מועדים נוספים עלולים להיחסר.'
                    )
                result.events.append(CalendarEvent(
                    title=summary, date=event_date, rrule=rrule, exdates=tuple(sorted(exdates)),
                ))
            elif summary:
                result.warnings.append(f'אירוע "{summary}" בלי DTSTART — לא הוצג (לא נשמט בשקט).')
            current = None
        elif current is not None and ":" in line:
            key, params, value = _split_prop(line)
            if key == "EXDATE" and "EXDATE" in current:
                # ייתכנו כמה שורות EXDATE — שומרים הכל ברשימה דרך מפתח מסודר
                index = 2
                while f"EXDATE#{index}" in current:
                    index += 1
                current[f"EXDATE#{index}"] = (params, value)
            else:
                current[key] = (params, value)
    # איסוף EXDATE#n לתוך הבנייה למעלה מתבצע דרך הסינון בלולאת הבנייה
    return result


def collect(source: str) -> IcsResult:
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
    """אזהרה כשיום השבוע שרשום בכותרת סותר את התאריך המחושב."""
    notes: list[str] = []
    for event in events:
        if not event.date:
            continue
        for name in WEEKDAY_NAMES:
            if f"יום {name}" in event.title:
                actual = weekday_he_fn(event.date)
                if actual and actual != name:
                    notes.append(
                        f"בכותרת '{event.title}' כתוב יום {name}, "
                        f"אבל {event.date} יוצא יום {actual}"
                    )
    return notes


def events_on(events: list[CalendarEvent], day: date) -> list[CalendarEvent]:
    return [event for event in events if _occurs_on(event, day)]
