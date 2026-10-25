"""מודל הנתונים המשותף לבריף היומי.

כל מתאם (מקור) ממלא את אותם טיפוסים, כך שהמעצב ושאר הזרימה לא תלויים
במקור הספציפי. זה החלק הדטרמיניסטי: בלי בוט, בלי שיקול דעת.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Lesson:
    time: str          # "08:00"
    subject: str
    teacher: str = ""
    room: str = ""


@dataclass
class Homework:
    subject: str
    title: str
    due: str = ""      # "3.11" או ""


@dataclass
class SchoolEvent:
    title: str
    note: str = ""


@dataclass
class SchoolMessage:
    sender: str
    subject: str
    date: str = ""
    has_attachment: bool = False
    is_new: bool = False


@dataclass
class CalendarEvent:
    title: str
    date: str          # DD.MM.YYYY
    source: str = "יומן"


@dataclass
class SourceConflict:
    title: str
    date_a: str
    source_a: str
    date_b: str
    source_b: str


@dataclass
class SourceStatus:
    name: str
    ok: bool
    detail: str = ""   # סיבת כשל/חלקיות, בעברית קצרה


@dataclass
class KidBrief:
    name: str
    lessons: list[Lesson] = field(default_factory=list)
    homework: list[Homework] = field(default_factory=list)
    events: list[SchoolEvent] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class DayBrief:
    date: str          # "1.11.2026"
    weekday_he: str    # "ראשון"
    kids: list[KidBrief] = field(default_factory=list)
    messages: list[SchoolMessage] = field(default_factory=list)
    calendar_events: list[CalendarEvent] = field(default_factory=list)
    conflicts: list[SourceConflict] = field(default_factory=list)
    sources: list[SourceStatus] = field(default_factory=list)


WEEKDAYS_HE = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
