"""Locate and download the SEC's structured data-set files (Form 13F, insider
transactions, ...).

From mid-2026 the SEC publishes new files under
``/files/datastandardsinnovation/data/``; older ones stay under
``/files/structureddata/data/``. Both are probed, newest location first.
"""
from __future__ import annotations

from pathlib import Path

import requests

_ROOTS = ("https://www.sec.gov/files/datastandardsinnovation/data/",
          "https://www.sec.gov/files/structureddata/data/")


def find(path: str, ua: str) -> str | None:
    """URL of a published file such as ``form-13f-data-sets/<name>.zip``, or
    None if it is not published. Network errors propagate."""
    for root in _ROOTS:
        r = requests.head(root + path, headers={"User-Agent": ua}, timeout=20, allow_redirects=True)
        if r.status_code == 200:
            return root + path
    return None


def download(url: str, dest: Path, ua: str) -> None:
    with requests.get(url, headers={"User-Agent": ua}, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
