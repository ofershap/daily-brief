"""חוזה המתאמים: מקור אחד -> DayBrief אחד, בלי עיצוב ובלי שליחה."""

from __future__ import annotations

from typing import Protocol

from ..models import DayBrief


class Collector(Protocol):
    """אוסף נתונים של יום אחד ממקור אחד.

    מימוש חדש (למשל Webtop, יומן, או בית ספר אחר) מממש collect()
    ומחזיר DayBrief באותם טיפוסים. שאר הזרימה לא משתנה.
    """

    def collect(self) -> DayBrief:
        ...
