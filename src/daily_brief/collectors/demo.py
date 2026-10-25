"""מתאם דמו: נתונים בדויים לחלוטין, בלי התחברות ובלי תלות.

משמש לבדיקת ניסיון (dry-run) לפני מבחן חיה, ולדוגמה ב-README.
כל שם, בית ספר ופרט כאן הם בדויים.
"""

from __future__ import annotations

from ..models import DayBrief, Homework, KidBrief, Lesson, SchoolEvent


def collect() -> DayBrief:
    return DayBrief(
        date="1.11.2026",
        weekday_he="ראשון",
        kids=[
            KidBrief(
                name="דנה",
                lessons=[
                    Lesson(time="08:00", subject="מתמטיקה", teacher="ד״ר לוי"),
                    Lesson(time="09:00", subject="אנגלית"),
                    Lesson(time="10:00", subject="ספורט"),
                ],
                homework=[Homework(subject="מתמטיקה", title="עמ׳ 42 תרגילים 1-5", due="3.11")],
                events=[SchoolEvent(title="טיול שנתי ביום שלישי", note="להביא אישור הורה חתום")],
            ),
            KidBrief(
                name="איתמר",
                lessons=[
                    Lesson(time="08:00", subject="עברית"),
                    Lesson(time="09:00", subject="מדעים", room="מעבדה 2"),
                ],
                homework=[],
                notes=["מחר חינוך גופני — להביא בגדי ספורט"],
            ),
        ],
    )
