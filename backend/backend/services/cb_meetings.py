"""Central-bank meeting dates (P1-15).

``backend/backend/reference/cb_meetings.json`` is curated from each bank's own published schedule; every row
records its ``source`` URL and ``retrieved`` date. The SNB publishes its calendar as a yearly
iCal file, so for the years in ``_SNB_FEEDS`` its rows are taken from the live feed instead (a
moved assessment shows up without a code change); if the feed fails the bundled rows stand.
"""
from __future__ import annotations

import json
import logging
import pathlib
import re
from datetime import datetime

import requests

from ..cache import cached

log = logging.getLogger(__name__)

# Shipped inside the package: /app/data is the persistent volume, which a rebuilt image never updates.
_PATH = pathlib.Path(__file__).resolve().parents[1] / "reference" / "cb_meetings.json"

# Yearly SNB calendars, linked from https://www.snb.ch/en/services-events/digital-services/rss-calendar-feeds
_SNB_FEEDS = {
    "2026": "https://www.snb.ch/public/ical/calendar/en/872f3023-70ea-42a9-8c27-524da3533fb7.ics",
    "2027": "https://www.snb.ch/public/ical/calendar/en/ac3d067c-1b93-475e-9d22-56045798603d.ics",
}
_SNB_TITLE = "SNB Monetary Policy Assessment"
_ASSESSMENT = re.compile(r"Monetary policy assessment of (\d{1,2} [A-Z][a-z]+ \d{4})")


def load_bundled() -> list[dict]:
    try:
        with open(_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        log.exception("Failed to load cb_meetings.json")
        return []


def parse_snb_ics(text: str, source: str) -> list[dict]:
    """One row per monetary policy assessment, dated by the SUMMARY (several events share one)."""
    unfolded = re.sub(r"\r?\n[ \t]", "", text)
    dates: set[str] = set()
    for line in unfolded.splitlines():
        if line.startswith("SUMMARY"):
            m = _ASSESSMENT.search(line)
            if m:
                dates.add(datetime.strptime(m.group(1), "%d %B %Y").date().isoformat())
    return [{"date": d, "bank": "SNB", "country": "CH", "title": _SNB_TITLE, "source": source}
            for d in sorted(dates)]


@cached("snb_meetings_ics")
def snb_feed() -> list[dict]:
    rows: list[dict] = []
    for year, url in _SNB_FEEDS.items():
        try:
            resp = requests.get(url, timeout=20, headers={"User-Agent": "EconoSift/1.0"})
            resp.raise_for_status()
            rows += [r for r in parse_snb_ics(resp.text, url) if r["date"].startswith(year)]
        except Exception as exc:
            log.warning("SNB calendar feed %s failed: %s", url, exc)
    return rows


def get_meetings() -> list[dict]:
    """Bundled rows, with SNB rows replaced by the feed for each year the feed returned."""
    rows = load_bundled()
    feed = snb_feed()
    years = {r["date"][:4] for r in feed}
    if not years:
        return rows
    kept = [r for r in rows if not (r.get("bank") == "SNB" and r["date"][:4] in years)]
    return sorted(kept + feed, key=lambda r: (r["date"], r["bank"]))


def last_dates(rows: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for r in rows:
        if r["date"] > out.get(r["bank"], ""):
            out[r["bank"]] = r["date"]
    return out


def schedule_end(rows: list[dict]) -> str | None:
    """Date after which at least one bank's meetings are missing."""
    ends = last_dates(rows).values()
    return min(ends) if ends else None
