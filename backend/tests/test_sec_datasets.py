"""SEC data-set files moved: new ones are published under
/files/datastandardsinnovation/data/, older ones stay under
/files/structureddata/data/ (seen October 2026)."""
from __future__ import annotations

from types import SimpleNamespace

from backend.services import sec_datasets


def _head(existing):
    calls = []

    def head(url, **kw):
        calls.append(url)
        return SimpleNamespace(status_code=200 if url in existing else 404)
    return head, calls


def test_find_prefers_the_new_location(monkeypatch):
    new = "https://www.sec.gov/files/datastandardsinnovation/data/form-13f-data-sets/x.zip"
    head, calls = _head({new})
    monkeypatch.setattr(sec_datasets.requests, "head", head)
    assert sec_datasets.find("form-13f-data-sets/x.zip", "UA") == new
    assert calls == [new]


def test_find_falls_back_to_the_old_location(monkeypatch):
    old = "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/x.zip"
    head, calls = _head({old})
    monkeypatch.setattr(sec_datasets.requests, "head", head)
    assert sec_datasets.find("form-13f-data-sets/x.zip", "UA") == old
    assert len(calls) == 2


def test_find_returns_none_when_unpublished(monkeypatch):
    head, _ = _head(set())
    monkeypatch.setattr(sec_datasets.requests, "head", head)
    assert sec_datasets.find("form-13f-data-sets/x.zip", "UA") is None
