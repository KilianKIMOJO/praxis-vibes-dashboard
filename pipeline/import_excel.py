"""Importiert die Wochenwerte aus KPI-Tracking.xlsx, Blatt "Praxis Vibes".

Das Blatt ist in Wochenblöcken aufgebaut: Zeile 1 trägt "KWnn" am Blockanfang,
darunter stehen Bezeichnungen mit dem Wert jeweils eine Zelle rechts daneben.
Zeilen 3–6: Instagram-Konto. Ab Zeile 8: Posts, Spotify- und Website-Blöcke.

Aufruf:  python3 -I pipeline/import_excel.py "<Pfad>/KPI-Tracking.xlsx"
Kommt ohne Zusatzpakete aus (liest das xlsx-XML direkt).
"""
from __future__ import annotations

import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_history, merge_week, save_history, week_id, week_monday  # noqa: E402

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
SHEET = "Praxis Vibes"
FIRST_YEAR = 2025  # erste Spalte KW31 gehört zu 2025


def col_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n


def read_sheet(path: Path) -> dict[tuple[int, int], object]:
    z = zipfile.ZipFile(path)
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            ss.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    target = None
    for s in wb.find("m:sheets", NS):
        if s.get("name") == SHEET:
            t = rels[s.get(f"{{{NS['r']}}}id")]
            target = "xl/" + t.lstrip("/").replace("xl/", "")
    if not target:
        raise SystemExit(f'Blatt "{SHEET}" nicht gefunden')
    cells: dict[tuple[int, int], object] = {}
    for row in ET.fromstring(z.read(target)).findall(".//m:sheetData/m:row", NS):
        r = int(row.get("r"))
        for c in row.findall("m:c", NS):
            v = c.find("m:v", NS)
            if v is None or v.text is None:
                continue
            val: object = ss[int(v.text)] if c.get("t") == "s" else v.text
            if c.get("t") != "s":
                try:
                    f = float(val)
                    val = int(f) if f.is_integer() else f
                except ValueError:
                    pass
            if isinstance(val, str):
                val = val.strip()
                if not val:
                    continue
            cells[(r, col_index(c.get("r")))] = val
    return cells


def norm(label: str) -> str:
    return re.sub(r"[^a-zäöü+\-]", "", label.lower())


IG_LABELS = {
    "follower": "followers",
    "neu": "follows",
    "verloren": "unfollows",
    "abgesprungen": "unfollows",
    "net+-": "net",
    "aufrufe": "views",
    "views": "views",
    "profilaufrufe": "profile_views",
    "linkaufrufe": "link_clicks",
    "linkclicks": "link_clicks",
    "erreichtekonten": "reach",
}
SPOTIFY_LABELS = {"wiedergaben": "plays", "listens": "plays",
                  "followernet": "followers_net", "follower,net": "followers_net"}
WEB_LABELS = {"überstory": "link_story", "storylink": "link_story",
              "überbio": "link_bio", "biolink": "link_bio"}


def num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def parse(cells) -> list[dict]:
    max_col = max(c for _, c in cells)
    headers = sorted((c, v) for (r, c), v in cells.items()
                     if r == 1 and isinstance(v, str) and v.upper().startswith("KW"))
    weeks = []
    year, prev = FIRST_YEAR, None
    for i, (start, label) in enumerate(headers):
        end = headers[i + 1][0] - 1 if i + 1 < len(headers) else max_col
        nums = [int(x) for x in re.findall(r"\d+", label)]
        kw = nums[-1]
        if prev is not None and kw < prev:
            year += 1
        prev = kw
        ig, pod = {}, {}
        # Instagram-Konto: Zeilen 3–6
        for r in range(3, 7):
            for c in range(start, end + 1):
                lab = cells.get((r, c))
                if isinstance(lab, str) and norm(lab) in IG_LABELS:
                    key = IG_LABELS[norm(lab)]
                    val = num(cells.get((r, c + 1)))
                    if val is not None and key not in ig:
                        ig[key] = val
        # Spotify- und Website-Blöcke: Spalte mit Kopf "Spotify" bzw. "Website Clicks" in Zeile 8
        for c in range(start, end + 1):
            head = cells.get((8, c))
            if not isinstance(head, str):
                continue
            h = norm(head)
            if h == "spotify":
                for r in range(9, 12):
                    lab = cells.get((r, c))
                    if isinstance(lab, str) and norm(lab) in SPOTIFY_LABELS:
                        val = num(cells.get((r, c + 1)))
                        if val is not None:
                            pod[SPOTIFY_LABELS[norm(lab)]] = val
                for r in range(12, 18):  # alte Website-Felder unter dem Spotify-Block (KW16)
                    lab = cells.get((r, c))
                    if isinstance(lab, str) and norm(lab) in WEB_LABELS:
                        val = num(cells.get((r, c + 1)))
                        if val is not None:
                            ig[WEB_LABELS[norm(lab)]] = val
            elif h == "websiteclicks":
                for r in range(9, 12):
                    lab = cells.get((r, c))
                    if isinstance(lab, str) and norm(lab) in WEB_LABELS:
                        val = num(cells.get((r, c + 1)))
                        if val is not None:
                            ig[WEB_LABELS[norm(lab)]] = val
        wid = week_id(week_monday(year, kw))
        weeks.append({"week": wid, "label": label, "range": len(nums) > 1, "ig": ig, "pod": pod})
    return weeks


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    path = Path(sys.argv[1])
    weeks = parse(read_sheet(path))
    hist = load_history()
    for w in weeks:
        if w["range"]:
            # Sammelspalte (z. B. "KW33-37"): nur den Follower-Stand übernehmen
            w["ig"] = {k: v for k, v in w["ig"].items() if k == "followers"}
            w["pod"] = {}
        # Excel überschreibt keine Werte, die schon per API abgerufen wurden
        for section in ("ig", "pod"):
            src = hist.get(w["week"], {}).get("sources", {}).get(section)
            merge_week(hist, w["week"], section, w[section], "excel",
                       overwrite=src in (None, "excel"))
    save_history(hist)
    print(f"{len(weeks)} Wochenblöcke gelesen, {len(hist)} Wochen in der Historie.")
    for w in weeks[-4:]:
        print(" ", w["label"], "→", w["week"], w["ig"], w["pod"])


if __name__ == "__main__":
    main()
