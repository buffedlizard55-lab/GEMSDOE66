"""Fail-closed site checks: the download verdict on the page must equal a fresh recomputation.

The previous version of this file hard-coded "nothing is ever downloadable", which was the
correct posture for the session that wrote it.  This session's contract is different and is
still fail-closed: a download is published **iff** every named gate passes on the bytes that
are actually in ``docs/downloads/``, re-checked from disk at build time.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np
import pytest
import rasterio

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "h67"   # this lane's pages; docs/*.html belong to build_site.py
DL = ROOT / "docs" / "downloads"   # shared with the other lanes; only our own prefix is ours
ART = ROOT / "artifacts" / "h67"
REFERENCE = ROOT / "data" / "raw" / "sample_submission.tif"
FEATURES = ROOT / "data" / "raw" / "training_features.tif"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

GO = "DOWNLOAD READY"
NO_CARD = "Download status: NOT AVAILABLE"
NOT_CLEARED = "Download status: NOT CLEARED"


@pytest.fixture(scope="session")
def build():
    import build_site_h67
    build_site_h67.main()
    return build_site_h67


def _links(path: Path):
    class _L(HTMLParser):
        def __init__(self):
            super().__init__()
            self.hrefs = []

        def handle_starttag(self, tag, attrs):
            if tag == "a":
                href = dict(attrs).get("href")
                if href:
                    self.hrefs.append(href)

    p = _L()
    p.feed(path.read_text(encoding="utf-8"))
    return p.hrefs


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def test_all_nav_pages_exist_and_are_well_formed(build):
    for href, _label in build.NAV:
        path = DOCS / href
        assert path.exists(), href
        text = path.read_text(encoding="utf-8")
        assert text.startswith("<!doctype html>")
        assert text.count("<main>") == 1 and text.count("</main>") == 1
        assert not re.search(r">\s*None\s*<", text), href
        HTMLParser().feed(text)


def test_exactly_one_download_verdict_is_shown(build):
    text = (DOCS / "index.html").read_text(encoding="utf-8")
    states = [s for s in (GO, NO_CARD, NOT_CLEARED) if s in text]
    assert len(states) == 1, f"index shows {states}; it must show exactly one verdict"


def test_published_verdict_matches_a_fresh_recomputation(build):
    card_path = build.newest(str(ART / "run-card-*.json"))
    assessment = build.assess(card_path)
    text = (DOCS / "index.html").read_text(encoding="utf-8")
    if assessment["cleared"]:
        assert GO in text
        assert (DL / assessment["raster"]["path"].name).exists()
        assert (DL / assessment["raster"]["zip"].name).exists()
    else:
        assert GO not in text
        assert sorted(p.name for p in DL.iterdir()) == ["README.md"]
        for href, _ in build.NAV:
            for link in _links(DOCS / href):
                assert not urlsplit(link).path.lower().endswith((".tif", ".tiff", ".zip")), \
                    f"{href} links a submission file while nothing is cleared"


@pytest.mark.skipif(not REFERENCE.exists(), reason="competition mirror not fetched")
def test_if_cleared_the_published_bytes_are_a_valid_submission(build):
    card_path = build.newest(str(ART / "run-card-*.json"))
    assessment = build.assess(card_path)
    if not assessment["cleared"]:
        pytest.skip("no cleared candidate; the fail-closed test above covers this state")
    tif = DL / assessment["raster"]["path"].name
    index_text = (DOCS / "index.html").read_text(encoding="utf-8")
    exe_text = (DOCS / "executive-summary.html").read_text(encoding="utf-8")

    # the hash printed on the page must be the hash of the published file
    assert assessment["raster"]["sha256"] in index_text
    assert assessment["raster"]["sha256"] in exe_text
    assert _sha256(tif) == assessment["raster"]["sha256"]

    with rasterio.open(tif) as ds:
        assert ds.count == 1 and ds.dtypes[0] == "float32"
        assert ds.crs.to_string() == "EPSG:32611"
        assert abs(abs(ds.res[0]) - 100.0) < 1e-9 and abs(abs(ds.res[1]) - 100.0) < 1e-9
        arr = ds.read(1).astype(np.float64)
        shape, transform, crs = (ds.height, ds.width), tuple(ds.transform)[:6], ds.crs
    with rasterio.open(REFERENCE) as ref:
        assert shape == (ref.height, ref.width)
        assert all(abs(a - b) < 1e-6 for a, b in zip(transform, tuple(ref.transform)[:6]))
        assert crs == ref.crs
    with rasterio.open(FEATURES) as feats:
        band = feats.read(1).astype(np.float64)
        feat_fp = np.isfinite(band) & (band > -1e38)
    finite = np.isfinite(arr)
    vals = arr[finite]
    assert vals.size and vals.min() >= 0.0 and vals.max() <= 1.0, "must satisfy the portal's range rule"
    # IR-67-FOOTPRINT-01: the organiser's sample submission is the authoritative mask -- every one
    # of the 12 owner artifacts the organiser scored is finite on exactly its 5,167,373 cells.  The
    # features band-1 mask disagrees by 3,061 / 1,540 cells, so it is asserted as a cross-check.
    with rasterio.open(REFERENCE) as ref:
        fp = np.isfinite(ref.read(1).astype(np.float64))
    assert int((~finite & fp).sum()) == 0, "NaN inside the reference footprint"
    assert int((finite & ~fp).sum()) == 0, "finite value outside the reference footprint"
    assert int(fp.sum()) == 5_167_373 and int(feat_fp.sum()) == 5_165_852
    assert int((fp & ~feat_fp).sum()) == 3_061 and int((feat_fp & ~fp).sum()) == 1_540
    # and no prediction may sit outside the training-data bounds under either reading
    assert int(((arr > 0) & ~feat_fp).sum()) == 0, "a dot lies outside the features bounds"

    card = assessment["card"]
    note = card["submission"]["note"]
    assert 0 < len(note) <= 140
    assert note in exe_text
    assert card["submission"]["name"] in exe_text


def test_no_organizer_confirmed_numeric_score_is_claimed(build):
    for href, _ in build.NAV:
        text = (DOCS / href).read_text(encoding="utf-8")
        assert not re.search(r"ORGANIZER-CONFIRMED\W+0\.\d", text), href
        assert "ORGANIZER-CONFIRMED" in text or href not in ("results.html", "index.html")


def test_all_local_links_resolve(build):
    seen = {href for href, _ in build.NAV}
    for href in sorted(seen):
        path = DOCS / href
        for link in _links(path):
            parsed = urlsplit(link)
            if parsed.scheme or link.startswith("#"):
                continue
            assert (path.parent / parsed.path).resolve().exists(), f"{href}: broken link {link}"


def test_executive_summary_explains_the_submission_steps(build):
    text = (DOCS / "executive-summary.html").read_text(encoding="utf-8")
    for needle in ("float32", "EPSG:32611", "100 m", "[0, 1]",
                   "Predicted values must be in range [0, 1]",
                   "three feedback submissions per week", "New submission"):
        assert needle in text, needle


def test_hypotheses_are_ranked_with_every_required_review_field(build):
    d = json.loads((ROOT / "docs" / "data" / "h67_hypotheses.json").read_text())
    assert [h["rank"] for h in d["items"]] == list(range(1, len(d["items"]) + 1))
    required = ("name", "layers", "signature", "why_off_catalogue", "named_mimic",
                "differs_from_repo", "cost", "status")
    for h in d["items"]:
        for field in required:
            assert h.get(field), f"rank {h['rank']} missing {field}"
    page = (DOCS / "hypotheses.html").read_text(encoding="utf-8")
    for h in d["items"]:
        assert h["name"] in page
