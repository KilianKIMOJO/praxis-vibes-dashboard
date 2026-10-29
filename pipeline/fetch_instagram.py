"""Instagram-Kennzahlen über die offizielle Instagram Graph API (Instagram Login).

Benötigt:  IG_ACCESS_TOKEN  (langlebiger Token, 60 Tage gültig)
Optional:  IG_API_VERSION   (Standard v23.0)

Je Woche (Mo 00:00 bis Mo 00:00, Europe/Berlin) werden abgefragt:
reach, views, profile_views, profile_links_taps, follows_and_unfollows.
Der Follower-Stand ist der Wert zum Zeitpunkt des Abrufs (Montagmorgen = Wochenende).
Die API hält Kennzahlen nur rund 90 Tage vor, daher speichern wir wöchentlich.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")
HOST = "https://graph.instagram.com"


class InstagramError(RuntimeError):
    pass


def _get(url: str, params: dict) -> dict:
    full = url + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(full, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            msg = json.loads(body).get("error", {}).get("message", body)
        except json.JSONDecodeError:
            msg = body
        raise InstagramError(f"HTTP {e.code}: {msg[:300]}") from None


def _ts(d: date) -> int:
    return int(datetime.combine(d, time(0, 0), BERLIN).timestamp())


class Instagram:
    def __init__(self, token: str, version: str | None = None, raw_dir: Path | None = None):
        self.token = token
        self.base = f"{HOST}/{version or os.environ.get('IG_API_VERSION') or 'v23.0'}"
        self.raw_dir = raw_dir
        self.user_id = None
        self.warnings: list[str] = []

    def _raw(self, name: str, obj) -> None:
        if self.raw_dir:
            self.raw_dir.mkdir(parents=True, exist_ok=True)
            (self.raw_dir / f"ig_{name}.json").write_text(json.dumps(obj, indent=2), encoding="utf-8")

    def refresh_token(self) -> dict:
        """Verlängert den Token um 60 Tage. Gibt {access_token, expires_in} zurück."""
        res = _get(f"{HOST}/refresh_access_token",
                   {"grant_type": "ig_refresh_token", "access_token": self.token})
        if res.get("access_token"):
            self.token = res["access_token"]
        return res

    def profile(self) -> dict:
        res = _get(f"{self.base}/me", {"fields": "user_id,username,followers_count,media_count",
                                       "access_token": self.token})
        self._raw("profile", res)
        self.user_id = res.get("user_id") or res.get("id")
        return res

    def _metric(self, metric: str, since: date, until: date, breakdown: str | None = None) -> dict | None:
        params = {"metric": metric, "period": "day", "metric_type": "total_value",
                  "since": _ts(since), "until": _ts(until), "access_token": self.token}
        if breakdown:
            params["breakdown"] = breakdown
        try:
            res = _get(f"{self.base}/{self.user_id}/insights", params)
        except InstagramError as e:
            self.warnings.append(f"{metric}: {e}")
            return None
        self._raw(f"{metric}_{since.isoformat()}", res)
        data = res.get("data") or []
        return data[0].get("total_value") if data else None

    @staticmethod
    def _breakdown(tv: dict | None) -> dict:
        out = {}
        for b in (tv or {}).get("breakdowns", []):
            for r in b.get("results", []):
                key = "/".join(r.get("dimension_values", []))
                out[key] = r.get("value")
        return out

    @staticmethod
    def _total(tv: dict | None) -> int | None:
        if not tv:
            return None
        if tv.get("value") is not None:
            return tv["value"]
        vals = [r.get("value") or 0 for b in tv.get("breakdowns", []) for r in b.get("results", [])]
        return sum(vals) if vals else None

    def posts_between(self, since: date, until: date) -> int | None:
        try:
            res = _get(f"{self.base}/{self.user_id}/media",
                       {"fields": "id,timestamp,media_type", "limit": 50, "access_token": self.token})
        except InstagramError as e:
            self.warnings.append(f"media: {e}")
            return None
        n = 0
        for m in res.get("data", []):
            ts = datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z").astimezone(BERLIN).date()
            if since <= ts < until:
                n += 1
        return n

    def week(self, monday: date, include_followers: bool = True) -> dict:
        """Kennzahlen einer Woche. include_followers=False für zurückliegende Wochen."""
        if self.user_id is None:
            prof = self.profile()
        else:
            prof = {}
        nxt = monday + timedelta(days=7)
        reach_tv = self._metric("reach", monday, nxt, breakdown="follow_type")
        fu = self._breakdown(self._metric("follows_and_unfollows", monday, nxt, breakdown="follow_type"))
        follows = fu.get("FOLLOWER")
        unfollows = fu.get("NON_FOLLOWER")
        reach_split = self._breakdown(reach_tv)
        out = {
            "reach": self._total(reach_tv),
            "reach_nonfollower": reach_split.get("NON_FOLLOWER"),
            "views": self._total(self._metric("views", monday, nxt)),
            "profile_views": self._total(self._metric("profile_views", monday, nxt)),
            "link_clicks": self._total(self._metric("profile_links_taps", monday, nxt)),
            "follows": follows,
            "unfollows": unfollows,
            "net": (follows - unfollows) if follows is not None and unfollows is not None else None,
            "posts": self.posts_between(monday, nxt),
        }
        if include_followers and prof.get("followers_count") is not None:
            out["followers"] = prof["followers_count"]
        return out


if __name__ == "__main__":
    tok = os.environ.get("IG_ACCESS_TOKEN")
    if not tok:
        raise SystemExit("IG_ACCESS_TOKEN fehlt")
    ig = Instagram(tok)
    print(ig.profile())
    from common import last_completed_week
    print(ig.week(last_completed_week()))
    print("Warnungen:", ig.warnings)
