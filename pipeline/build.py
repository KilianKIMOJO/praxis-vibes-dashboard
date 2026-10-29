"""Erzeugt aus der Historie die Dashboard-Daten (docs/data.js) und die KPI-Mail
(docs/mail.json für Power Automate, docs/mail.html als Vorschau).

Zeitraum der Mail: die letzten zwei abgeschlossenen Wochen (Mo–So).
Vergleich: die zwei Wochen davor und der Schnitt der zwölf Wochen davor.
"""
from __future__ import annotations

import html
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (CONFIG, EPISODES, SITE, STATUS, last_completed_week, load_history,  # noqa: E402
                    load_json, parse_week_id, save_json, week_id)

FLOW = {  # Kennzahlen, die je Woche summiert werden
    ("pod", "plays"), ("pod", "followers_net"),
    ("ig", "reach"), ("ig", "views"), ("ig", "profile_views"), ("ig", "link_clicks"),
    ("ig", "follows"), ("ig", "unfollows"), ("ig", "net"), ("ig", "posts"),
}
LABELS = {
    ("pod", "plays"): "Podcast-Wiedergaben",
    ("ig", "reach"): "Instagram erreichte Konten",
    ("ig", "followers"): "Instagram-Follower",
    ("ig", "net"): "Instagram-Follower netto",
    ("pod", "followers_net"): "Spotify-Follower netto",
    ("pod", "followers"): "Spotify-Follower",
    ("ig", "views"): "Instagram-Views",
    ("ig", "profile_views"): "Profilaufrufe",
    ("ig", "link_clicks"): "Link-Klicks",
}
MONTHS = ["Jan", "Feb", "März", "Apr", "Mai", "Juni", "Juli", "Aug", "Sep", "Okt", "Nov", "Dez"]


# ── Formatierung (deutsch) ──────────────────────────────────────────────────
def fnum(v, digits=0) -> str:
    if v is None:
        return "–"
    s = f"{v:,.{digits}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fpct(p) -> str:
    if p is None:
        return "–"
    sign = "+" if p > 0 else ("−" if p < 0 else "±")
    return f"{sign}{fnum(abs(p) * 100)} %"


def fdate(d: date) -> str:
    return f"{d.day}. {MONTHS[d.month - 1]}"


def kw(wid: str) -> int:
    return int(wid.split("-W")[1])


# ── Kennzahlen ──────────────────────────────────────────────────────────────
def weeks_back(end: date, n: int, offset: int = 0) -> list[str]:
    """n Wochen-IDs, endend offset Wochen vor end (älteste zuerst)."""
    return [week_id(end - timedelta(days=7 * (offset + i))) for i in range(n - 1, -1, -1)]


def total(hist, wids, sec, key):
    vals = [hist.get(w, {}).get(sec, {}).get(key) for w in wids]
    have = [v for v in vals if v is not None]
    if not have:
        return None, 0
    return sum(have), len(have)


def latest(hist, wids, sec, key):
    for w in reversed(wids):
        v = hist.get(w, {}).get(sec, {}).get(key)
        if v is not None:
            return v, w
    return None, None


def change(cur, ref):
    if cur is None or ref in (None, 0):
        return None
    return cur / ref - 1


def kpi(hist, sec, key, period, prev, base) -> dict:
    if (sec, key) in FLOW:
        cur, n = total(hist, period, sec, key)
        p, pn = total(hist, prev, sec, key)
        b, bn = total(hist, base, sec, key)
        avg2 = (b / bn * len(period)) if bn >= 4 else None
        return {
            "label": LABELS.get((sec, key), key), "value": cur,
            "complete": n == len(period), "weeks_with_data": n,
            "prev": p if pn == len(prev) else None,
            "vs_prev": change(cur, p) if (pn == len(prev) and n == len(period)) else None,
            "avg12": avg2, "vs_avg12": change(cur, avg2) if n == len(period) else None,
        }
    cur, cw = latest(hist, period, sec, key)
    p, _ = latest(hist, prev + period[:0], sec, key)
    return {"label": LABELS.get((sec, key), key), "value": cur, "as_of": cw,
            "prev": p, "delta": (cur - p) if cur is not None and p is not None else None}


def target_status(value, target):
    if value is None or not target:
        return None
    ratio = value / target
    level = "gut" if ratio >= 1 else ("knapp" if ratio >= 0.85 else "unter Ziel")
    return {"target": target, "ratio": ratio, "level": level}


def hints(hist, k, period, base, episodes, status) -> list[str]:
    out = []
    for key, name in (("plays", "Podcast-Wiedergaben"), ("reach", "Instagram-Reichweite")):
        x = k[key]
        ref, word = (x["vs_prev"], "zur Vorperiode") if x["vs_prev"] is not None else (x["vs_avg12"], "zum 12-Wochen-Schnitt")
        if ref is not None and abs(ref) >= 0.15:
            out.append(f"{name} {'deutlich über' if ref > 0 else 'deutlich unter'} dem Vergleich: {fpct(ref)} {word}.")
    # Beste Woche der letzten 12 Wochen
    sec_key = {"plays": ("pod", "plays"), "reach": ("ig", "reach")}
    for key, (sec, mk) in sec_key.items():
        series = [(w, hist.get(w, {}).get(sec, {}).get(mk)) for w in base + period]
        series = [(w, v) for w, v in series if v is not None]
        if len(series) >= 6:
            best = max(series, key=lambda t: t[1])
            if best[0] in period:
                out.append(f"KW {kw(best[0])} war die stärkste Woche der letzten drei Monate bei "
                           f"{'den Wiedergaben' if key == 'plays' else 'der Reichweite'} ({fnum(best[1])}).")
    # Follower-Dynamik Instagram: letzte 4 Wochen vs. 8 davor
    nets = [hist.get(w, {}).get("ig", {}).get("net") for w in base + period]
    nets = [v for v in nets if v is not None]
    if len(nets) >= 10:
        a, b = sum(nets[-4:]) / 4, sum(nets[:-4]) / len(nets[:-4])
        if b > 0 and a < b * 0.6:
            out.append(f"Instagram wächst langsamer: zuletzt Ø {fnum(a)} neue Follower pro Woche, davor Ø {fnum(b)}.")
        elif b > 0 and a > b * 1.4:
            out.append(f"Instagram wächst schneller: zuletzt Ø {fnum(a)} neue Follower pro Woche, davor Ø {fnum(b)}.")
    # Datenqualität
    for sec, mk, name in (("ig", "views", "Views"), ("pod", "plays", "Wiedergaben")):
        for i in range(1, len(period)):
            a = hist.get(period[i], {}).get(sec, {}).get(mk)
            b = hist.get(period[i - 1], {}).get(sec, {}).get(mk)
            if a is not None and a == b:
                out.append(f"Datencheck: {name} in KW {kw(period[i])} exakt gleich wie KW {kw(period[i-1])} – bitte prüfen.")
    tok = (status.get("instagram") or {}).get("token_expires")
    if tok and date.fromisoformat(tok) - date.today() < timedelta(days=14):
        out.append(f"Instagram-Zugang läuft am {fdate(date.fromisoformat(tok))} ab – Token erneuern.")
    return out


def build(today: date | None = None) -> dict:
    hist = load_history()
    status = load_json(STATUS, {})
    episodes = load_json(EPISODES, [])
    goals = load_json(CONFIG / "ziele.json", {})
    end = last_completed_week(today)
    period = weeks_back(end, 2)
    prev = weeks_back(end, 2, offset=2)
    base = weeks_back(end, 12, offset=2)
    p_start, p_end = parse_week_id(period[0]), parse_week_id(period[-1]) + timedelta(days=6)

    k = {
        "plays": kpi(hist, "pod", "plays", period, prev, base),
        "reach": kpi(hist, "ig", "reach", period, prev, base),
        "ig_followers": kpi(hist, "ig", "followers", period, prev, base),
        "ig_net": kpi(hist, "ig", "net", period, prev, base),
        "pod_followers_net": kpi(hist, "pod", "followers_net", period, prev, base),
        "pod_followers": kpi(hist, "pod", "followers", period, prev, base),
        "views": kpi(hist, "ig", "views", period, prev, base),
        "profile_views": kpi(hist, "ig", "profile_views", period, prev, base),
        "link_clicks": kpi(hist, "ig", "link_clicks", period, prev, base),
    }
    k["plays"]["goal"] = target_status(k["plays"]["value"], goals.get("pod_plays_14d"))
    k["reach"]["goal"] = target_status(k["reach"]["value"], goals.get("ig_reach_14d"))
    fg = (goals.get("ig_followers") or {}).get("wert")
    k["ig_followers"]["goal"] = target_status(k["ig_followers"]["value"], fg)
    if k["plays"]["value"] and k["reach"]["value"]:
        k["plays_per_1000_reach"] = k["plays"]["value"] / k["reach"]["value"] * 1000

    new_eps = [e for e in episodes if p_start.isoformat() <= e["date"] <= p_end.isoformat()]
    h = hints(hist, k, period, base, episodes, status)

    data = {
        "generated": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "period": {"weeks": period, "start": p_start.isoformat(), "end": p_end.isoformat(),
                   "label": f"KW {kw(period[0])}–{kw(period[-1])}"},
        "kpis": k,
        "hints": h,
        "goals": goals,
        "weeks": sorted(hist.values(), key=lambda r: r["week"]),
        "episodes": episodes,
        "new_episodes": new_eps,
        "status": status,
    }
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "data.js").write_text(
        "// automatisch erzeugt von pipeline/build.py – nicht von Hand ändern\nwindow.PV_DATA = "
        + json.dumps(data, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
    mail = render_mail(data)
    save_json(SITE / "mail.json", mail)
    (SITE / "mail.html").write_text(mail["html"], encoding="utf-8")
    return data


# ── Mail ────────────────────────────────────────────────────────────────────
INK, MUTED, LINE, BG = "#1d2321", "#5f6b68", "#e3ece9", "#f4f8f7"
POD, IG, UP, DOWN = "#00897b", "#e0663a", "#1e7a46", "#b3261e"


def delta_html(p, word="") -> str:
    if p is None:
        return f'<span style="color:{MUTED}">kein Vergleich</span>'
    color = UP if p > 0 else (DOWN if p < 0 else MUTED)
    arrow = "▲" if p > 0 else ("▼" if p < 0 else "■")
    return f'<span style="color:{color};font-weight:700">{arrow} {fpct(p)}</span> <span style="color:{MUTED}">{word}</span>'


def north_cell(title, x, color) -> str:
    if x["vs_prev"] is not None:
        d = delta_html(x["vs_prev"], "zur Vorperiode")
    else:
        d = delta_html(x["vs_avg12"], "zum 12-Wochen-Schnitt")
    goal = ""
    if x.get("goal"):
        g = x["goal"]
        goal = (f'<div style="margin-top:6px;font-size:13px;color:{MUTED}">Ziel {fnum(g["target"])} · '
                f'{fnum(g["ratio"] * 100)} % erreicht ({g["level"]})</div>')
    note = "" if x["complete"] else f'<div style="font-size:12px;color:{DOWN}">nur {x["weeks_with_data"]} von 2 Wochen mit Daten</div>'
    return (f'<td width="50%" valign="top" style="padding:16px;background:#ffffff;border:1px solid {LINE};border-top:4px solid {color};border-radius:8px">'
            f'<div style="font-size:12px;letter-spacing:1px;text-transform:uppercase;color:{MUTED}">{title}</div>'
            f'<div style="font-size:34px;font-weight:700;color:{INK};line-height:1.2;margin:4px 0">{fnum(x["value"])}</div>'
            f'<div style="font-size:14px">{d}</div>{goal}{note}</td>')


def render_mail(d: dict) -> dict:
    k, per = d["kpis"], d["period"]
    s, e = date.fromisoformat(per["start"]), date.fromisoformat(per["end"])
    url = d["goals"].get("dashboard_url") or "#"

    def short(x):
        p = x["vs_prev"] if x.get("vs_prev") is not None else x.get("vs_avg12")
        return fpct(p) if p is not None else "–"
    subject = (f"Praxis Vibes · {per['label']} · Wiedergaben {short(k['plays'])} · "
               f"Reichweite {short(k['reach'])}")

    rows = []
    def row(label, value, sub):
        rows.append(f'<tr><td style="padding:9px 0;border-bottom:1px solid {LINE};color:{INK}">{label}</td>'
                    f'<td align="right" style="padding:9px 0;border-bottom:1px solid {LINE};font-weight:700;color:{INK}">{value}</td>'
                    f'<td align="right" style="padding:9px 0 9px 12px;border-bottom:1px solid {LINE};font-size:13px;color:{MUTED}">{sub}</td></tr>')
    f = k["ig_followers"]
    row("Instagram-Follower", fnum(f["value"]),
        f"netto {'+' if (k['ig_net']['value'] or 0) >= 0 else ''}{fnum(k['ig_net']['value'])} in 14 Tagen")
    pf = k["pod_followers"]
    pfn = k["pod_followers_net"]["value"]
    row("Spotify-Follower", fnum(pf["value"]) if pf["value"] is not None else "–",
        f"netto {'+' if (pfn or 0) >= 0 else ''}{fnum(pfn)} in 14 Tagen")
    for key in ("views", "profile_views", "link_clicks"):
        x = k[key]
        p = x["vs_prev"] if x["vs_prev"] is not None else x["vs_avg12"]
        row(x["label"], fnum(x["value"]), (fpct(p) + (" zur Vorperiode" if x["vs_prev"] is not None else " zum Ø")) if p is not None else "")
    if k.get("plays_per_1000_reach"):
        row("Wiedergaben je 1.000 erreichte Konten", fnum(k["plays_per_1000_reach"], 1), "Brücke Instagram → Podcast")

    eps = "".join(
        f'<li style="margin:4px 0"><b>#{ep["number"]}</b> {html.escape(ep["title"])} '
        f'<span style="color:{MUTED}">· {fdate(date.fromisoformat(ep["date"]))}'
        f'{" · " + str(ep["duration_min"]) + " Min." if ep.get("duration_min") else ""}</span></li>'
        for ep in d["new_episodes"]) or f'<li style="color:{MUTED}">Keine neue Folge in diesem Zeitraum.</li>'
    hint_html = "".join(f'<li style="margin:6px 0">{html.escape(t)}</li>' for t in d["hints"][:4]) \
        or f'<li style="color:{MUTED}">Keine Auffälligkeiten.</li>'
    sources = []
    for name, key in (("Instagram", "instagram"), ("Spotify", "spotify")):
        st = d["status"].get(key) or {}
        sources.append(f"{name}: {'automatisch' if st.get('ok') else 'Excel/manuell'}")

    body = f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(subject)}</title></head>
<body style="margin:0;padding:0;background:{BG};font-family:Segoe UI,Helvetica,Arial,sans-serif;color:{INK}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG}"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%">
<tr><td style="padding:0 4px 16px">
  <div style="font-size:13px;letter-spacing:2px;text-transform:uppercase;color:{POD};font-weight:700">Praxis Vibes · Reichweite</div>
  <div style="font-size:24px;font-weight:700;margin-top:4px">KPIs {per['label']}</div>
  <div style="font-size:14px;color:{MUTED}">{fdate(s)} bis {fdate(e)} {e.year}</div>
</td></tr>
<tr><td><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
  {north_cell("Podcast-Wiedergaben", k["plays"], POD)}
  <td width="12" style="font-size:0">&nbsp;</td>
  {north_cell("Instagram erreichte Konten", k["reach"], IG)}
</tr></table></td></tr>
<tr><td style="height:12px"></td></tr>
<tr><td style="padding:20px 16px;background:#ffffff;border:1px solid {LINE};border-radius:8px;margin-top:12px">
  <div style="font-size:12px;letter-spacing:1px;text-transform:uppercase;color:{MUTED};margin-bottom:4px">Treiber · 14 Tage</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:15px">{''.join(rows)}</table>
</td></tr>
<tr><td style="height:12px"></td></tr>
<tr><td style="padding:16px;background:#ffffff;border:1px solid {LINE};border-radius:8px">
  <div style="font-size:12px;letter-spacing:1px;text-transform:uppercase;color:{MUTED}">Neue Folgen</div>
  <ul style="padding-left:18px;margin:8px 0 0;font-size:15px">{eps}</ul>
</td></tr>
<tr><td style="height:12px"></td></tr>
<tr><td style="padding:16px;background:#ffffff;border:1px solid {LINE};border-radius:8px">
  <div style="font-size:12px;letter-spacing:1px;text-transform:uppercase;color:{MUTED}">Was auffällt</div>
  <ul style="padding-left:18px;margin:8px 0 0;font-size:15px">{hint_html}</ul>
</td></tr>
<tr><td align="center" style="padding:22px 0 8px">
  <a href="{html.escape(url)}" style="display:inline-block;background:{POD};color:#ffffff;text-decoration:none;font-weight:700;padding:12px 22px;border-radius:999px">Zum Dashboard</a>
</td></tr>
<tr><td align="center" style="font-size:12px;color:{MUTED};padding:6px 0 0">
  Automatisch erstellt · Datenquellen: {' · '.join(sources)}
</td></tr>
</table></td></tr></table></body></html>"""
    return {"subject": subject, "html": body, "period": per, "generated": d["generated"]}


if __name__ == "__main__":
    d = build()
    print("Zeitraum:", d["period"]["label"])
    for key in ("plays", "reach"):
        x = d["kpis"][key]
        print(f"  {x['label']}: {x['value']}  Vorperiode {x['prev']}  Ø12×2 {x['avg12']}")
    print("Hinweise:", *d["hints"], sep="\n  ")
