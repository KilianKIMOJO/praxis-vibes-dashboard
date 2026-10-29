"""Gemeinsame Helfer: Pfade, Kalenderwochen, Historie laden und speichern."""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = ROOT / "docs"  # GitHub Pages liest aus /docs
CONFIG = ROOT / "config"
HISTORY = DATA / "history.json"
EPISODES = DATA / "episodes.json"
STATUS = DATA / "status.json"

# Felder je Woche. "ig" = Instagram @praxis.vibes, "pod" = Podcast (Spotify for Creators).
IG_FIELDS = ["followers", "follows", "unfollows", "net", "reach", "views",
             "profile_views", "link_clicks", "link_story", "link_bio"]
POD_FIELDS = ["plays", "plays_total", "followers", "followers_net"]


def week_id(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_monday(year: int, week: int) -> date:
    return date.fromisocalendar(year, week, 1)


def parse_week_id(wid: str) -> date:
    y, w = wid.split("-W")
    return week_monday(int(y), int(w))


def last_completed_week(today: date | None = None) -> date:
    """Montag der letzten vollständig abgeschlossenen Woche (Mo–So)."""
    today = today or datetime.now(timezone.utc).date()
    this_monday = today - timedelta(days=today.weekday())
    return this_monday - timedelta(days=7)


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_history() -> dict:
    """Historie als Dict week_id -> Datensatz."""
    rows = load_json(HISTORY, [])
    return {r["week"]: r for r in rows}


def save_history(hist: dict) -> None:
    rows = sorted(hist.values(), key=lambda r: r["week"])
    save_json(HISTORY, rows)


def empty_week(wid: str) -> dict:
    mon = parse_week_id(wid)
    return {
        "week": wid,
        "start": mon.isoformat(),
        "end": (mon + timedelta(days=6)).isoformat(),
        "ig": {},
        "pod": {},
        "sources": {},
    }


def merge_week(hist: dict, wid: str, section: str, values: dict, source: str,
               overwrite: bool = True) -> None:
    """Werte einer Quelle in eine Woche schreiben. None-Werte werden ignoriert."""
    rec = hist.setdefault(wid, empty_week(wid))
    target = rec.setdefault(section, {})
    wrote = False
    for k, v in values.items():
        if v is None:
            continue
        if overwrite or k not in target:
            target[k] = v
            wrote = True
    if wrote:
        rec.setdefault("sources", {})[section] = source


def env(name: str) -> str | None:
    v = os.environ.get(name, "").strip()
    return v or None
