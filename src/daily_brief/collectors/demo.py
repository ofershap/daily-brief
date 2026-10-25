"""מתאם דמו: נתונים בדויים לחלוטין, בלי התחברות ובלי תלות.

משמש לבדיקת ניסיון (dry-run) לפני מבחן חיה, ולדוגמה ב-README.
כל שם, בית ספר ופרט כאן הם בדויים.
"""

from __future__ import annotations

from ..models import (
    CalendarEvent,
    DayBrief,
    Homework,
    KidBrief,
    Lesson,
    SchoolEvent,
    SchoolMessage,
    SourceConflict,
    SourceStatus,
)


def collect() -> DayBrief:
    return DayBrief(
        date="1.11.2026",
        weekday_he="ראשון",
        kids=[
            KidBrief(
                name="נועה",
                lessons=[
                    Lesson(time="08:00", subject="מתמטיקה", teacher="רוני"),
                    Lesson(time="09:00", subject="אנגלית"),
                    Lesson(time="10:00", subject="ספורט"),
                ],
                homework=[Homework(subject="מתמטיקה", title="עמ׳ 42 תרגילים 1-5", due="3.11")],
                events=[SchoolEvent(title="טיול שנתי", note="להביא אישור הורה חתום", date="3.11.2026")],
            ),
            KidBrief(
                name="עמית",
                lessons=[
                    Lesson(time="08:00", subject="עברית"),
                    Lesson(time="09:00", subject="מדעים", room="מעבדה 2"),
                ],
                homework=[],
                notes=["מחר חינוך גופני - להביא בגדי ספורט"],
            ),
        ],
        messages=[
            SchoolMessage(sender="המורה שרה", subject="אישור הורה לטיול - נא להחזיר חתום", date="31.10.2026", is_new=True),
            SchoolMessage(sender="מזכירות", subject="טופס הצטרפות לחוג מדעים", date="30.10.2026", has_attachment=True),
        ],
        calendar_events=[
            CalendarEvent(title="טיול שנתי", date="4.11.2026", source="יומן משפחתי"),
        ],
        conflicts=[
            SourceConflict(
                title="טיול שנתי",
                date_a="3.11.2026", source_a="משו״ב",
                date_b="4.11.2026", source_b="יומן משפחתי",
            )
        ],
        sources=[
            SourceStatus(name="משו״ב (דמו)", ok=True),
            SourceStatus(name="יומן משפחתי (דמו)", ok=True),
        ],
    )
