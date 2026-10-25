"""מעצב בריף בסגנון הודעת וואטסאפ בעברית: דטרמיניסטי, בלי בוט בלולאה.

הפלט הוא טקסט פשוט עם מוסכמות וואטסאפ (*מודגש*, אימוג'י, תבליטים),
כדי שההודעה תיראה טבעית כשהבוט שלכם שולח אותה כמו שהיא.
שער שלמות: מקור שנכשל או חלקי מופיע בשורת ⚠️, לא נעלם בשקט.
"""

from __future__ import annotations

from ..models import DayBrief, KidBrief

_EMOJI = ["👧", "👦", "🧒", "👶"]


def format_brief(brief: DayBrief) -> str:
    lines: list[str] = [f"🎒 *בריף בית ספר - יום {brief.weekday_he}, {brief.date}*", ""]
    for index, kid in enumerate(brief.kids):
        lines.extend(_format_kid(kid, _EMOJI[index % len(_EMOJI)]))
        lines.append("")
    if brief.messages:
        lines.append("💬 *הודעות ממורים:*")
        for msg in brief.messages:
            flag = "🆕 " if msg.is_new else ""
            attach = " 📎" if msg.has_attachment else ""
            date = f" ({msg.date})" if msg.date else ""
            sender = f"{msg.sender}: " if msg.sender else ""
            lines.append(f"· {flag}{sender}{msg.subject}{attach}{date}")
        lines.append("")
    if brief.calendar_events:
        events = " · ".join(f"{event.title} ({event.date})" for event in brief.calendar_events)
        lines.append(f"🗓 *מהיומן:* {events}")
        lines.append("")
    for conflict in brief.conflicts:
        lines.append(
            f"⚠️ *סתירה בין מקורות:* {conflict.title} - "
            f"{conflict.source_a} אומר {conflict.date_a}, {conflict.source_b} אומר {conflict.date_b}"
        )
    if brief.conflicts:
        lines.append("")
    for warning in brief.warnings:
        lines.append(f"⚠️ *בדיקת תאריכים:* {warning}")
    if brief.warnings:
        lines.append("")
    failed = [src for src in brief.sources if not src.ok]
    if failed:
        for src in failed:
            detail = f": {src.detail}" if src.detail else ""
            lines.append(f"⚠️ *מקור חסר:* {src.name}{detail}")
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
            f"{hw.subject} - {hw.title}"
            + (f" (להגשה {hw.due})" if hw.due else (f" (ניתן {hw.given})" if hw.given else ""))
            for hw in kid.homework
        )
        lines.append(f"📚 *שיעורי בית:* {homework}")
    for event in kid.events:
        note = f" - {event.note}" if event.note else ""
        date = f" ({event.date})" if event.date else ""
        lines.append(f"📣 *אירוע:* {event.title}{date}{note}")
    for note in kid.notes:
        lines.append(f"✏️ {note}")
    return lines
