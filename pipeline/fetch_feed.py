"""Liest den öffentlichen RSS-Feed von Praxis Vibes: Folgen, Datum, Länge."""
from __future__ import annotations

import re
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

FEED_URL = "https://anchor.fm/s/da67fbf8/podcast/rss"
ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"


def duration_min(raw: str | None) -> int | None:
    if not raw:
        return None
    parts = [int(p) for p in raw.split(":") if p.isdigit()]
    if not parts:
        return None
    secs = 0
    for p in parts:
        secs = secs * 60 + p
    if len(parts) == 1:  # nur Sekunden angegeben
        return round(secs / 60)
    return round(secs / 60)


def fetch(url: str = FEED_URL) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "praxis-vibes-dashboard/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        root = ET.fromstring(r.read())
    out = []
    for item in root.find("channel").findall("item"):
        title = (item.findtext("title") or "").strip()
        m = re.match(r"#\s*(\d+)", title)
        pub = parsedate_to_datetime(item.findtext("pubDate"))
        out.append({
            "number": int(m.group(1)) if m else None,
            "title": re.sub(r"^#\s*\d+\s*[-–:]\s*", "", title),
            "date": pub.date().isoformat(),
            "duration_min": duration_min(item.findtext(ITUNES + "duration")),
            "link": (item.findtext("link") or "").strip(),
            "guid": (item.findtext("guid") or "").strip(),
        })
    out.sort(key=lambda e: e["date"], reverse=True)
    return out


if __name__ == "__main__":
    for e in fetch()[:5]:
        print(e)
