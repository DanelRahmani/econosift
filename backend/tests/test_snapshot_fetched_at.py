"""P3-35: endpoints that serve a stored snapshot are dated by when it was built.

``provenance.attach`` stamps each ref with the oldest ``@cached`` read, else
*now*. A response built from a file or DB row written days earlier would then
read as fetched just now, and the Navbar's "Data as of" (the oldest
``fetchedAt`` on the page) would look newer than the data. Each endpoint below
stamps ``fetchedAt`` from its snapshot's build time instead.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import date, datetime, timezone

from backend import provenance as pv

# 2026-07-15 12:00:00 UTC as a Unix epoch: 20649 days × 86400 s + 12 h.
#   20649 = days from 1970-01-01 to 2026-07-15 (date(2026,7,15) - date(1970,1,1)).
JULY_15_NOON = 20649 * 86400 + 12 * 3600
JULY_15_NOON_ISO = "2026-07-15T12:00:00Z"


def test_stamp_formats_epochs_and_naive_utc_datetimes():
    assert (date(2026, 7, 15) - date(1970, 1, 1)).days == 20649
    assert pv.stamp(JULY_15_NOON) == JULY_15_NOON_ISO
    assert pv.stamp(datetime(2026, 7, 15, 12, 0)) == JULY_15_NOON_ISO          # naive = UTC
    assert pv.stamp(datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)) == JULY_15_NOON_ISO


def test_13f_holders_are_dated_by_the_data_set_build(tmp_path, monkeypatch):
    import zipfile
    from backend.services import thirteenf_service as tf
    from tests.test_thirteenf_service import AAPL, COVERPAGE, INFOTABLE, SUBMISSION, _tsv

    z = tmp_path / "ds.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("SUBMISSION.tsv", _tsv(SUBMISSION))
        f.writestr("COVERPAGE.tsv", _tsv(COVERPAGE))
        f.writestr("INFOTABLE.tsv", _tsv(INFOTABLE))
    store = tmp_path / "13f"
    monkeypatch.setattr(tf, "_DIR", store)
    tf.write_reduced("01mar2026-31may2026", *tf.reduce_dataset(z))
    meta = store / "meta_01mar2026-31may2026.json"
    meta.write_text(json.dumps({**json.loads(meta.read_text()), "builtAt": JULY_15_NOON_ISO}))
    monkeypatch.setattr(tf, "_cusips_for", lambda t: [AAPL])
    monkeypatch.setattr(tf, "_latest_window", lambda: None)   # no newer data set published
    monkeypatch.setattr(tf, "_shares_outstanding", lambda t: None)

    out = tf._holders_sync("AAPL")

    assert out["holders"]
    assert out["provenance"]["*"]["fetchedAt"] == JULY_15_NOON_ISO


def test_insider_aggregate_is_dated_by_the_stored_data_set(tmp_path, monkeypatch):
    from backend.services import edgar_service, insider_aggregator as agg, insider_dataset as ds
    from tests.test_insider_aggregator import NONDERIV_TRANS, REPORTINGOWNER, SP500, SUBMISSION, _tsv
    import zipfile

    z = tmp_path / "2026q2_form345.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("SUBMISSION.tsv", _tsv(SUBMISSION))
        f.writestr("REPORTINGOWNER.tsv", _tsv(REPORTINGOWNER))
        f.writestr("NONDERIV_TRANS.tsv", _tsv(NONDERIV_TRANS))
    store = tmp_path / "form345"
    monkeypatch.setattr(ds, "_DIR", store)
    published = {"insider-transactions-data-sets/2026q2_form345.zip": "https://sec.example/2026q2_form345.zip"}
    monkeypatch.setattr(ds.sec_datasets, "find", lambda path, ua: published.get(path))
    monkeypatch.setattr(ds.sec_datasets, "download", lambda url, dest, ua: dest.write_bytes(z.read_bytes()))
    monkeypatch.setattr(ds, "_user_agent", lambda: "Test Person test@example.com")
    monkeypatch.setattr(edgar_service, "_edgar_ready", lambda: True)
    monkeypatch.setattr(agg.constituents, "get_constituents", lambda index: SP500)

    class Oct1(date):
        @classmethod
        def today(cls):
            return date(2026, 10, 1)
    monkeypatch.setattr(ds, "date", Oct1)
    ds.load_latest()                                   # downloads and stores 2026q2
    os.utime(store / "meta_2026q2.json", (JULY_15_NOON, JULY_15_NOON))

    out = agg.get_insider_aggregate()

    assert out["dataset"] == "2026q2"
    assert out["provenance"]["*"]["fetchedAt"] == JULY_15_NOON_ISO


def test_country_profile_is_dated_by_the_downloaded_files(tmp_path, monkeypatch):
    from backend.services import factbook_profiles_service as fps, factbook_service as fs

    countries = tmp_path / "factbook.json"
    countries.write_text(json.dumps([{"cca2": "NL", "cca3": "NLD", "name": {"common": "Netherlands"},
                                      "region": "Europe"}]), encoding="utf-8")
    os.utime(countries, (JULY_15_NOON, JULY_15_NOON))
    monkeypatch.setattr(fs, "_resolve_path", lambda: countries)

    # The CIA factbook profile was downloaded a day later: 2026-07-16 12:00 UTC.
    fb_dir = tmp_path / "fb"
    (fb_dir / "europe").mkdir(parents=True)
    profile = fb_dir / "europe" / "nl.json"
    profile.write_text(json.dumps({"Introduction": {"Background": {"text": "Kingdom."}}}), encoding="utf-8")
    os.utime(profile, (JULY_15_NOON + 86400, JULY_15_NOON + 86400))
    monkeypatch.setattr(fps, "_DATA_DIR", fb_dir)
    monkeypatch.setattr(fps, "_GEC_REGIONS", {"nl": "europe"})

    out = fs.get_country_profile("NL")

    assert out["provenance"]["*"]["fetchedAt"] == JULY_15_NOON_ISO
    intro = out["provenance"]["sections.Introduction"]
    assert {r["provider"]: r["fetchedAt"] for r in intro} == {
        "factbook": "2026-07-16T12:00:00Z", "other": JULY_15_NOON_ISO}


def test_stored_ai_summary_is_dated_by_its_generation(monkeypatch):
    from backend.routers import ai as ai_router

    class Row:  # a summary generated on 2026-07-15 at noon UTC, read back from SQLite
        summary_text, model_used, created_at = "Headline.\n- point", "gemini-2.5-flash", datetime(2026, 7, 15, 12, 0)
        grounding = None
    monkeypatch.setattr(ai_router, "_cached_lookup", lambda *a: Row)

    out = asyncio.run(ai_router.ai_macro(ai_router.MacroRequest(countries=["US"])))

    assert out["cached"] is True
    assert out["provenance"]["*"]["fetchedAt"] == JULY_15_NOON_ISO
