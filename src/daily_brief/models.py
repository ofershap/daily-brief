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


WEEKDAYS_HE = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
