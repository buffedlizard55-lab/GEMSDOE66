"""LIDAR-02 release gates (session 2026-10-20, branch arena/c73a2700-gemsdoe66).

These tests encode the *rules* the release must satisfy, read from the session's
own run card, so a later rebuild cannot quietly promote, relabel or de-disclose
the artifact: exactly one banner state, every figure labelled HOLDOUT-DTI, the
falsified E2 field still on the record, the IR-73 raw-overlap trip still
disclosed, and - if promoted - bytes on disk that re-validate line by line.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
CARD = DOCS / "data" / "run-card-lidar02.json"
MIRROR = ROOT / "registry" / "run_card_lidar02.json"


@pytest.fixture(scope="module")
def card():
    return json.loads(CARD.read_text())


def test_run_card_published_and_mirrored(card):
    assert MIRROR.exists()
    mirror = json.loads(MIRROR.read_text())
    assert mirror["verdict"] == card["verdict"]
    assert mirror["promote"] == card["promote"]


def test_every_number_is_labelled_and_no_organizer_score(card):
    assert card["holdout_dti"]["label"] == "HOLDOUT-DTI"
    assert card["holdout_dti"]["organizer_score"] is None
    assert card["submission"]["slots_used"] == 0
    assert card["submission"]["uploaded"] is False
    for arm, res in card["holdout_dti"]["arms_e2b"].items():
        assert res["label"] == "HOLDOUT-DTI", arm
        assert res["ci95"] and len(res["ci95"]) == 2, arm
    assert card["holdout_dti"]["withheld_positives_pooled"] > 0


def test_canary_clear_and_falsified_field_still_on_record(card):
    assert card["leakage_canary"]["max_auc_E1_channels"] <= 0.90
    assert card["leakage_canary"]["max_auc_E2b_channels"] <= 0.90
    # E2's falsified LIDAR-02-A field must remain in the card, below random.
    e2 = card["holdout_dti"]["arms_e2_falsified_field"]
    assert e2["new_maxcov"]["pooled"] < e2["random"]["pooled"]
    assert "FALSIFIED" in card["hypothesis"]


def test_gate_verdict_consistent_with_checks(card):
    if card["promote"]:
        assert all(card["gate_checks"].values())
        rc = card["registry_checks"]
        assert rc["identical_to_any"] is False
        assert rc["max_abs_spearman_dots"] <= 0.90
        assert rc["surface_max_abs_spearman"] <= 0.90
        assert card["validator"]["passed"] is True
        assert "0 FAIL" in card["validator"]["summary"]
        assert "0 SKIPPED" in card["validator"]["summary"]
    else:
        assert not all(card["gate_checks"].values())


def test_ir73_raw_trip_is_disclosed_not_hidden(card):
    trips = card["registry_checks"]["literal_rule_trips_gt_0p70"]
    assert trips, "the raw within-3px trip vs the 311k-dot raster must stay on record"
    for t in trips:
        assert t["random_control"] is not None and t["lift"] is not None


def test_site_shows_exactly_one_banner_state(card):
    index = (DOCS / "index.html").read_text()
    if card["promote"]:
        assert "DOWNLOAD READY" in index and "OK TO SUBMIT" in index
        assert card["release"]["tif"] in index
        assert "IR-73" in index  # raw-overlap disclosure beside the button
        assert "0.0012" in index or "thin" in index.lower()  # thin stratum margin disclosed
    else:
        assert "NOT OFFERED" in index
        assert "lidar02" not in "\n".join(
            line for line in index.splitlines() if ".tif" in line and "href" in line)


@pytest.mark.skipif(not CARD.exists(), reason="run card absent")
def test_downloaded_bytes_match_card_and_revalidate(card):
    if not card["promote"]:
        # fail closed: no lidar02 raster may sit in the download path
        assert not list((DOCS / "downloads").glob("*lidar02*.tif"))
        return
    rasterio = pytest.importorskip("rasterio")
    import numpy as np

    rel = card["release"]
    p = DOCS / "downloads" / rel["tif"]
    assert p.is_file() and (DOCS / "downloads" / rel["zip"]).is_file()
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    assert sha == rel["sha256"] == card["raster"]["sha256"]
    with rasterio.open(p) as src:
        assert src.count == 1 and src.dtypes[0] == "float32"
        assert src.crs is not None and src.crs.to_epsg() == 32611
        assert (src.height, src.width) == (3730, 3292)
        assert src.res == (100.0, 100.0)
        a = src.read(1)
    finite = np.isfinite(a)
    inside = a[finite]
    assert inside.min() >= 0.0 and inside.max() <= 1.0  # the portal's [0, 1] rule
    assert int((inside > 0).sum()) == rel["dots"] == 38000
    # all-finite sibling: same dots, no NaN anywhere
    with rasterio.open(DOCS / "downloads" / rel["zeros_tif"]) as src:
        z = src.read(1)
    assert not np.isnan(z).any()
    assert bool(((z > 0) == (np.nan_to_num(a) > 0)).all())
    assert len(card["submission"]["note"]) <= 140
