"""מעצב בריף בסגנון הודעת וואטסאפ בעברית: דטרמיניסטי, בלי בוט בלולאה.

הפלט הוא טקסט פשוט עם מוסכמות וואטסאפ (*מודגש*, אימוג'י, תבליטים),
כדי שההודעה תיראה טבעית כשהבוט שלכם שולח אותה כמו שהיא.
"""

from __future__ import annotations

from ..models import DayBrief, KidBrief

_EMOJI = ["👧", "👦", "🧒", "👶"]


def format_brief(brief: DayBrief) -> str:
    lines: list[str] = [f"🎒 *בריף בית ספר — יום {brief.weekday_he}, {brief.date}*", ""]
    for index, kid in enumerate(brief.kids):
        lines.extend(_format_kid(kid, _EMOJI[index % len(_EMOJI)]))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _format_kid(kid: KidBrief, emoji: str) -> list[str]:
    lines = [f"{emoji} *{kid.name}*"]
    if kid.lessons:
        lessons = " · ".join(
            f"{lesson.time} {lesson.subject}"
            + (f" ({lesson.teacher})" if lesson.teacher else "")
            for lesson in kid.lessons
        )
        lines.append(f"🕐 *מערכת:* {lessons}")
    if kid.homework:
        homework = " · ".join(
            f"{hw.subject} — {hw.title}" + (f" (להגשה {hw.due})" if hw.due else "")
            for hw in kid.homework
        )
        lines.append(f"📚 *שיעורי בית:* {homework}")
    for event in kid.events:
        note = f" — {event.note}" if event.note else ""
        lines.append(f"📣 *אירוע:* {event.title}{note}")
    for note in kid.notes:
        lines.append(f"✏️ {note}")
    return lines
