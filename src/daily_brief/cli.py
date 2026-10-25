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

    text = format_brief(brief)
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
