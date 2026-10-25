"""נקודת הכניסה: אוסף -> מעצב -> פלט (מסך או קובץ). בלי בוט בלולאה."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .formatters import format_brief


def _load_env_file(path: Path) -> None:
    """טוען KEY=VALUE פשוט מקובץ .env, בלי לדרוס משתנים שכבר קיימים."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="daily-brief",
        description="בריף בית-ספר יומי: איסוף דטרמיניסטי והודעה מעוצבת אחת.",
    )
    parser.add_argument(
        "--collector",
        choices=["demo", "mashov"],
        default="demo",
        help="מקור הנתונים (ברירת מחדל: demo, נתונים בדויים בלי התחברות)",
    )
    parser.add_argument("--demo", action="store_true", help="קיצור ל--collector demo")
    parser.add_argument("--schools", action="store_true", help="מדפיס את רשימת בתי הספר הציבורית של משו״ב (למציאת סמל)")
    parser.add_argument("--out", metavar="PATH", help="כותב את הבריף לקובץ במקום למסך")
    parser.add_argument("--env", metavar="PATH", default=".env", help="נתיב לקובץ .env (ברירת מחדל: .env)")
    args = parser.parse_args(argv)

    _load_env_file(Path(args.env))

    if args.schools:
        _print_schools()
        return

    collector_name = "demo" if args.demo else args.collector
    if collector_name == "demo":
        from .collectors import demo
        brief = demo.collect()
    else:
        from .collectors.mashov import MashovCollector
        brief = MashovCollector().collect()

    # יומן אופציונלי: BRIEF_ICS (נתיב קובץ מקומי או URL). כשל = שורת ⚠️ בבריף.
    ics_source = os.environ.get("BRIEF_ICS", "")
    if ics_source:
        from .collectors.ics import collect as collect_ics, events_on, find_conflicts
        from datetime import date as _date
        from .models import SourceStatus
        try:
            calendar_events = collect_ics(ics_source)
            brief.calendar_events = events_on(calendar_events, _date.today())
            school_events = [event for kid in brief.kids for event in kid.events]
            brief.conflicts = find_conflicts(
                school_events, calendar_events, brief.date
            )
            brief.sources.append(SourceStatus(name="יומן ICS", ok=True))
        except Exception as exc:
            brief.sources.append(SourceStatus(
                name="יומן ICS", ok=False, detail=f"{type(exc).__name__}: {exc}"
            ))

    # סמן ריצה אחרונה: הודעות חדשות מסומנות 🆕; אין "חדש" כפול בריצה חוזרת.
    from .state import load_last_success, save_success
    state_path = Path(os.environ.get("BRIEF_STATE", "out/state.json"))
    last_success = load_last_success(state_path)
    if last_success is not None:
        from datetime import datetime, timezone
        for msg in brief.messages:
            try:
                sent = datetime.fromisoformat(msg.date)
                if sent.tzinfo is None:
                    sent = sent.replace(tzinfo=timezone.utc)
                msg.is_new = sent > last_success
            except ValueError:
                msg.is_new = False  # תאריך לא מפוענח = לא מסומן חדש

    text = format_brief(brief)
    save_success(state_path)  # נכתב רק אחרי הפקה מוצלחת
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"נכתב: {args.out}", file=sys.stderr)
    else:
        print(text, end="")


def _print_schools() -> None:
    """רשימת בתי הספר היא נקודת קצה ציבורית; לא נדרשת התחברות."""
    import asyncio

    async def _run() -> None:
        try:
            from mashov import MashovClient
        except ImportError as exc:
            raise SystemExit("התקינו את תלות המשו״ב: pip install pymashov") from exc
        async with MashovClient(username="", password="", semel="", auto_login=False) as client:
            for school in await client.get_schools():
                print(f"{school.get('semel', '?')}\t{school.get('name', '?')}\t{school.get('city', '')}")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
