"""סמן ריצה אחרונה מוצלחת: אידמפוטנטות וסימון "חדש" להודעות.

קובץ JSON מקומי (ברירת מחדל out/state.json). נכתב רק אחרי הפקה מוצלחת.
הודעות שתאריכן אחרי הריצה האחרונה המוצלחת מסומנות 🆕; ריצה חוזרת על אותם
נתונים לא מייצרת "חדש" כפול. קובץ המצב נשאר אצל המשתמש.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def load_last_success(path: Path) -> datetime | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return datetime.fromisoformat(raw["last_success"])
    except (OSError, ValueError, KeyError):
        return None


def save_success(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"last_success": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False),
        encoding="utf-8",
    )
