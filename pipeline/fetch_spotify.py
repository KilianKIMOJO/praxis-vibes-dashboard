"""Podcast-Kennzahlen aus Spotify for Creators über die inoffizielle Bibliothek
`spotifygraphqlconnector` (OpenPodcast). Spotify bietet keine offizielle Statistik-API.

Benötigt:  SPOTIFY_SP_DC, SPOTIFY_SP_KEY   (Cookies einer eingeloggten Sitzung)
Optional:  SPOTIFY_SHOW_URI                (sonst automatisch die erste gehostete Show)

Vorgehen
- Gesamtwiedergaben aller Plattformen (Streams + Downloads) werden jede Woche als
  Zählerstand gespeichert. Wiedergaben der Woche = Differenz zum Vorwochenstand.
- Gibt es noch keinen Vorwochenstand, wird der 7-Tage-Wert von Spotify genommen.
- Follower und Wiedergaben je Folge (gesamt) kommen als Schnappschuss dazu.

Die Antwortstrukturen sind nicht offiziell dokumentiert. Die Werte werden deshalb
tolerant gesucht und alle Rohantworten in data/raw/ abgelegt. Nach dem ersten echten
Lauf die Rohdateien prüfen und, falls nötig, die Schlüssel in KEYS anpassen.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# Schlüsselmuster je Kennzahl, in Prioritätsreihenfolge (Groß-/Kleinschreibung egal)
KEYS = {
    "plays_total": [r"^total(streams)?anddownloads$", r"^streamsanddownloads$", r"^totalplays$",
                    r"^plays$", r"^total$", r"^starts$"],
    "plays_7d": [r"^total(streams)?anddownloads$", r"^streamsanddownloads$", r"^plays$",
                 r"^totalplays$", r"^streams$", r"^starts$", r"^total$"],
    "followers": [r"^followers?(count)?$", r"^totalfollowers$", r"^followercount$"],
}


def walk_numbers(obj, path=""):
    """Liefert (pfad, schlüssel, wert) für alle Zahlen in einer JSON-Struktur."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_numbers(v, f"{path}.{k}")
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                yield f"{path}.{k}", k, v
            elif isinstance(v, str) and re.fullmatch(r"\d+", v):
                yield f"{path}.{k}", k, int(v)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_numbers(v, f"{path}[{i}]")


def pick(obj, patterns: list[str]) -> tuple[str | None, float | None]:
    found = list(walk_numbers(obj))
    for pat in patterns:
        for path, key, val in found:
            # Tages- oder Zeitreihenwerte überspringen, wir wollen Summen
            if re.search(r"daily|timeseries|\[\d+\]", path, re.I):
                continue
            if re.fullmatch(pat, key.lower().replace("_", "")):
                return path, val
    return None, None


def fetch(sp_dc: str, sp_key: str, show_uri: str | None, raw_dir: Path) -> tuple[dict, list[dict], list[str]]:
    from spotifygraphqlconnector import SpotifyGraphQLConnector  # nur in GitHub Actions installiert

    raw_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    kwargs = {"sp_dc": sp_dc, "sp_key": sp_key}
    if show_uri:
        kwargs["show_uri"] = show_uri
    c = SpotifyGraphQLConnector(**kwargs)

    def call(name, fn, *a, **kw):
        try:
            res = fn(*a, **kw)
            (raw_dir / f"spotify_{name}.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
            return res
        except Exception as e:  # noqa: BLE001 – inoffizielle API, jeder Fehler wird gemeldet
            warnings.append(f"{name}: {type(e).__name__}: {str(e)[:200]}")
            return None

    overview = call("overview", c.get_show_overview_stats)
    last7 = call("last7", c.get_show_spotify_stats, date_range_window="WINDOW_LAST_SEVEN_DAYS")
    discovery = call("discovery", c.get_show_audience_discovery)
    top = call("top_episodes", c.get_show_top_episodes)

    vals: dict = {}
    p, v = pick(overview, KEYS["plays_total"]) if overview else (None, None)
    if v is not None:
        vals["plays_total"] = v
        vals["_plays_total_path"] = p
    p, v = pick(last7, KEYS["plays_7d"]) if last7 else (None, None)
    if v is not None:
        vals["plays_7d"] = v
        vals["_plays_7d_path"] = p
    for src in (discovery, overview, last7):
        if src is None:
            continue
        p, v = pick(src, KEYS["followers"])
        if v is not None:
            vals["followers"] = v
            vals["_followers_path"] = p
            break

    # Wiedergaben je Folge (gesamt) – Liste von Objekten mit Name/URI und einer Zahl
    episodes: list[dict] = []
    if top:
        def collect(o):
            if isinstance(o, dict):
                name = o.get("name") or o.get("title") or o.get("episodeName")
                uri = o.get("uri") or o.get("episodeUri") or o.get("id")
                if name and uri:
                    _, plays = pick(o, KEYS["plays_total"] + [r"^value$", r"^count$"])
                    if plays is not None:
                        episodes.append({"uri": uri, "title": name, "plays_total": plays})
                        return
                for v in o.values():
                    collect(v)
            elif isinstance(o, list):
                for v in o:
                    collect(v)
        collect(top)
    if not vals.get("plays_total") and not vals.get("plays_7d"):
        warnings.append("Keine Wiedergaben in den Antworten gefunden – Rohdateien prüfen, KEYS anpassen.")
    return vals, episodes, warnings
