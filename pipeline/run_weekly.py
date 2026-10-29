"""Wöchentlicher Lauf: Daten abrufen, Historie fortschreiben, Dashboard und Mail erzeugen.

Aufrufe
  python pipeline/run_weekly.py                    # Normalfall (GitHub Actions, montags)
  python pipeline/run_weekly.py --backfill 8       # Instagram rückwirkend für 8 Wochen füllen
  python pipeline/run_weekly.py --excel "<KPI-Tracking.xlsx>" --no-fetch   # nur Excel + Aufbau
Fehlt für eine Quelle der Zugang, wird sie übersprungen und im Status vermerkt.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402
import fetch_feed  # noqa: E402
from common import (DATA, EPISODES, STATUS, env, last_completed_week, load_history,  # noqa: E402
                    load_json, merge_week, parse_week_id, save_history, save_json, week_id)

RAW = DATA / "raw"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def norm_title(t: str) -> str:
    t = re.sub(r"^#\s*\d+\s*[-–:]\s*", "", t or "")
    return re.sub(r"[^a-z0-9äöüß]", "", t.lower())[:40]


def run_feed(status: dict) -> None:
    try:
        eps = fetch_feed.fetch()
    except Exception as e:  # noqa: BLE001
        status["feed"] = {"ok": False, "checked": now_iso(), "message": f"Feed nicht erreichbar: {e}"}
        return
    old = {e["guid"]: e for e in load_json(EPISODES, [])}
    for e in eps:
        prev = old.get(e["guid"], {})
        e["plays"] = prev.get("plays", {})
        if "plays_total" in prev:
            e["plays_total"] = prev["plays_total"]
    save_json(EPISODES, eps)
    status["feed"] = {"ok": True, "checked": now_iso(), "message": f"{len(eps)} Folgen im Feed"}


def run_instagram(status: dict, hist: dict, target, backfill: int) -> None:
    from fetch_instagram import Instagram, InstagramError

    token = env("IG_ACCESS_TOKEN")
    if not token:
        status["instagram"] = {"ok": False, "checked": now_iso(),
                               "message": "Kein Zugang hinterlegt (IG_ACCESS_TOKEN). Werte kommen aus dem Excel."}
        return
    ig = Instagram(token, raw_dir=RAW)
    st = {"checked": now_iso()}
    try:
        res = ig.refresh_token()
        if res.get("expires_in"):
            exp = datetime.now(timezone.utc) + timedelta(seconds=int(res["expires_in"]))
            st["token_expires"] = exp.date().isoformat()
        if ig.token != token and os.environ.get("RUNNER_TEMP"):
            # neuer Token: der Workflow schreibt ihn ins GitHub-Secret zurück (nie ins Repo)
            Path(os.environ["RUNNER_TEMP"], "ig_token_new").write_text(ig.token)
    except InstagramError as e:
        ig.warnings.append(f"Token-Verlängerung: {e}")
    try:
        prof = ig.profile()
        st["account"] = prof.get("username")
        weeks = [target - timedelta(days=7 * i) for i in range(backfill, -1, -1)]
        for mon in weeks:
            vals = ig.week(mon, include_followers=(mon == target))
            merge_week(hist, week_id(mon), "ig", vals, "api")
        st["ok"] = True
        st["message"] = f"@{st.get('account')} · {len(weeks)} Woche(n) abgerufen"
    except InstagramError as e:
        st["ok"] = False
        st["message"] = f"Abruf fehlgeschlagen: {e}"
    if ig.warnings:
        st["warnings"] = ig.warnings
    status["instagram"] = st


def run_spotify(status: dict, hist: dict, target) -> None:
    sp_dc, sp_key = env("SPOTIFY_SP_DC"), env("SPOTIFY_SP_KEY")
    if not (sp_dc and sp_key):
        status["spotify"] = {"ok": False, "checked": now_iso(),
                             "message": "Kein Zugang hinterlegt (SPOTIFY_SP_DC/SP_KEY). Werte kommen aus dem Excel."}
        return
    try:
        import fetch_spotify
        vals, top, warnings = fetch_spotify.fetch(sp_dc, sp_key, env("SPOTIFY_SHOW_URI"), RAW)
    except Exception as e:  # noqa: BLE001
        status["spotify"] = {"ok": False, "checked": now_iso(), "message": f"Abruf fehlgeschlagen: {e}"}
        return
    wid = week_id(target)
    prev = hist.get(week_id(target - timedelta(days=7)), {}).get("pod", {})
    pod = {}
    if vals.get("plays_total") is not None:
        pod["plays_total"] = vals["plays_total"]
        if prev.get("plays_total") is not None:
            pod["plays"] = vals["plays_total"] - prev["plays_total"]
    if "plays" not in pod and vals.get("plays_7d") is not None:
        pod["plays"] = vals["plays_7d"]
    if vals.get("followers") is not None:
        pod["followers"] = vals["followers"]
        if prev.get("followers") is not None:
            pod["followers_net"] = vals["followers"] - prev["followers"]
    merge_week(hist, wid, "pod", pod, "api")

    # Wiedergaben je Folge als Wochenschnappschuss
    eps = load_json(EPISODES, [])
    by_title = {norm_title(e["title"]): e for e in eps}
    matched = 0
    for t in top:
        e = by_title.get(norm_title(t["title"]))
        if e:
            e["plays_total"] = t["plays_total"]
            e.setdefault("plays", {})[wid] = t["plays_total"]
            matched += 1
    save_json(EPISODES, eps)
    st = {"ok": bool(pod), "checked": now_iso(),
          "message": f"Wiedergaben {pod.get('plays', '–')}, Folgen zugeordnet: {matched}/{len(top)}",
          "paths": {k: v for k, v in vals.items() if k.startswith("_")}}
    if warnings:
        st["warnings"] = warnings
    status["spotify"] = st


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", help="Zielwoche, z. B. 2026-W44 (Standard: letzte abgeschlossene)")
    ap.add_argument("--backfill", type=int, default=int(os.environ.get("BACKFILL") or 0),
                    help="Instagram zusätzlich für so viele Vorwochen abrufen (max. 12)")
    ap.add_argument("--excel", help="Vorher KPI-Tracking.xlsx importieren")
    ap.add_argument("--no-fetch", action="store_true", help="Nur aufbauen, nichts abrufen")
    a = ap.parse_args()

    if a.excel:
        sys.argv = ["import_excel.py", a.excel]
        import import_excel
        import_excel.main()

    target = parse_week_id(a.week) if a.week else last_completed_week()
    status = load_json(STATUS, {})
    hist = load_history()
    if not a.no_fetch:
        run_feed(status)
        run_instagram(status, hist, target, min(max(a.backfill, 0), 12))
        run_spotify(status, hist, target)
        save_history(hist)
        status["last_run"] = now_iso()
        save_json(STATUS, status)
    build.build()
    for k in ("feed", "instagram", "spotify"):
        if k in status:
            print(f"{k:10s} {'OK ' if status[k].get('ok') else '—  '} {status[k].get('message')}")


if __name__ == "__main__":
    main()
