"""P1-15: central-bank meeting dates — sourced bundle, SNB iCal feed, expiry guard. No network."""
from __future__ import annotations

import datetime


def test_every_bundled_row_names_its_source_and_retrieval_date():
    from backend.services import cb_meetings
    rows = cb_meetings.load_bundled()
    assert rows
    for r in rows:
        assert r["source"].startswith("https://"), r
        datetime.date.fromisoformat(r["retrieved"])


def test_schedule_does_not_run_out_within_60_days():
    """Fails 60 days before any bank's last bundled meeting: time to add the next year."""
    from backend.services import cb_meetings
    horizon = datetime.date.today() + datetime.timedelta(days=60)
    for bank, last in cb_meetings.last_dates(cb_meetings.load_bundled()).items():
        assert datetime.date.fromisoformat(last) >= horizon, (
            f"{bank} schedule ends {last}: add the next year's dates to backend/backend/reference/cb_meetings.json")


_SNB_ICS = (
    "BEGIN:VCALENDAR\r\n"
    "BEGIN:VEVENT\r\n"
    "DTSTART;TZID=Europe/Zurich:20270301T071500\r\n"
    "SUMMARY:Monetary policy assessment of 18 March 2027 (press release)\r\n"
    "END:VEVENT\r\n"
    "BEGIN:VEVENT\r\n"
    "DTSTART;TZID=Europe/Zurich:20270318T093000\r\n"
    "SUMMARY:Monetary policy assessment of 18 March 2027 (introductory remarks\\,\r\n"
    "  news conference)\r\n"
    "END:VEVENT\r\n"
    "BEGIN:VEVENT\r\n"
    "DTSTART;TZID=Europe/Zurich:20270624T093000\r\n"
    "SUMMARY:Monetary policy assessm\r\n"
    " ent of 24 June 2027 (press release)\r\n"
    "END:VEVENT\r\n"
    "BEGIN:VEVENT\r\n"
    "DTSTART;TZID=Europe/Zurich:20270107T093000\r\n"
    "SUMMARY:Preliminary data on 2026 annual result\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)


def test_parse_snb_ics_takes_the_assessment_date_from_the_summary():
    """The 18 March entries (one dated 1 March, the announcement) collapse to one 2027-03-18 row;
    a folded SUMMARY line still parses (24 June); the annual-result event is ignored."""
    from backend.services import cb_meetings
    rows = cb_meetings.parse_snb_ics(_SNB_ICS, "https://snb.example/2027.ics")
    assert [r["date"] for r in rows] == ["2027-03-18", "2027-06-24"]
    assert rows[0]["bank"] == "SNB" and rows[0]["country"] == "CH"
    assert rows[0]["source"] == "https://snb.example/2027.ics"


def test_feed_replaces_bundled_snb_rows_for_the_years_it_covers(monkeypatch):
    from backend.services import cb_meetings
    bundled = [
        {"date": "2027-03-18", "bank": "SNB", "country": "CH", "title": "t", "source": "b", "retrieved": "x"},
        {"date": "2027-06-17", "bank": "SNB", "country": "CH", "title": "t", "source": "b", "retrieved": "x"},
        {"date": "2026-12-10", "bank": "SNB", "country": "CH", "title": "t", "source": "b", "retrieved": "x"},
        {"date": "2027-01-27", "bank": "Fed", "country": "US", "title": "t", "source": "b", "retrieved": "x"},
    ]
    monkeypatch.setattr(cb_meetings, "load_bundled", lambda: bundled)
    monkeypatch.setattr(cb_meetings, "snb_feed", lambda: [
        {"date": "2027-03-18", "bank": "SNB", "country": "CH", "title": "t", "source": "feed"},
        {"date": "2027-06-24", "bank": "SNB", "country": "CH", "title": "t", "source": "feed"},
    ])
    got = {(r["bank"], r["date"]): r["source"] for r in cb_meetings.get_meetings()}
    # 2027 SNB comes from the feed (17 June moved to 24 June); 2026 SNB and the Fed stay bundled.
    assert got == {("SNB", "2027-03-18"): "feed", ("SNB", "2027-06-24"): "feed",
                   ("SNB", "2026-12-10"): "b", ("Fed", "2027-01-27"): "b"}


def test_feed_failure_keeps_the_bundled_rows(monkeypatch):
    from backend.services import cb_meetings
    bundled = [{"date": "2027-03-18", "bank": "SNB", "country": "CH", "title": "t", "source": "b",
                "retrieved": "x"}]
    monkeypatch.setattr(cb_meetings, "load_bundled", lambda: bundled)
    monkeypatch.setattr(cb_meetings, "snb_feed", lambda: [])
    assert cb_meetings.get_meetings() == bundled


def test_schedule_end_is_the_earliest_last_date_across_banks():
    from backend.services import cb_meetings
    rows = [{"date": "2027-12-08", "bank": "Fed"}, {"date": "2027-12-16", "bank": "ECB"},
            {"date": "2027-06-01", "bank": "Fed"}]
    assert cb_meetings.schedule_end(rows) == "2027-12-08"
    assert cb_meetings.schedule_end([]) is None


def test_reference_files_ship_inside_the_package_not_the_data_volume():
    # docker-compose mounts the persistent sqlite_data volume over /app/data, so a JSON kept there is
    # frozen at the volume's first creation (live: the June cb_meetings.json survived every rebuild),
    # and the desktop build bundles only the package. Both files must load from the package.
    import pathlib
    from backend.services import atlas_service, cb_meetings
    pkg = pathlib.Path(cb_meetings.__file__).resolve().parents[1]
    assert cb_meetings._PATH.is_relative_to(pkg) and cb_meetings._PATH.exists()
    assert len(atlas_service._country_universe()) > 100
    assert (pkg / "reference" / "country_universe.json").exists()
