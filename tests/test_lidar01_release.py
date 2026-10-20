"""Strict protocol release gate for the LIDAR-01 audit artifact.

The governing run card defines a literal stop at >70% candidate-dot overlap within 3 px.
Chance correction is diagnostic only and cannot waive that requirement.
"""
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import rasterio
import pytest
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
NAME = "gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z"


def test_literal_overlap_stop_is_recorded_as_negative():
    evidence = json.loads((ROOT / "evidence/lidar01_uniqueness.json").read_text())
    assert evidence["duplicate_literal_rule"] is True
    assert evidence["verdict_literal_rule"] == "DUPLICATE - STOP"
    assert evidence["max_dot_overlap_fraction"] > 0.70
    assert evidence["max_abs_spearman"] < 0.90
    # Passing one uniqueness criterion does not cancel failure of the other.
    card = json.loads((DOCS / "data/run-card-lidar01.json").read_text())
    assert card["registry_checks"]["duplicate"] is True
    assert card["verdict"] == "negative"
    assert card["submission"]["download_status"].startswith("WITHDRAWN")


def test_both_documented_three_pixel_kernels_exceed_the_stop_threshold():
    candidate = ROOT / "artifacts/lidar01" / f"{NAME}.tif"
    comparator = ROOT / "registry/rasters/gems61-lane-buried-step-gravinversion-hgm-r3-k400k-b2zeros.tif"
    with rasterio.open(candidate) as ds:
        dots = ds.read(1) > 0
    with rasterio.open(comparator) as ds:
        other = ds.read(1) > 0
    count = int(dots.sum())
    square = ndimage.binary_dilation(other, structure=np.ones((7, 7), dtype=bool))
    square_overlap = float((dots & square).sum() / count)
    euclidean_overlap = float((dots & (ndimage.distance_transform_edt(~other) <= 3)).sum() / count)
    assert square_overlap == pytest.approx(0.9210176873638923, abs=1e-12)
    assert euclidean_overlap == pytest.approx(0.8481967387262973, abs=1e-12)
    assert square_overlap > 0.70 and euclidean_overlap > 0.70


def test_candidate_is_audit_only_and_hash_matches_record():
    raster = ROOT / "artifacts/lidar01" / f"{NAME}.tif"
    assert raster.is_file()
    digest = hashlib.sha256(raster.read_bytes()).hexdigest()
    evidence = json.loads((ROOT / "evidence/lidar01_uniqueness.json").read_text())
    assert digest == evidence["candidate_sha256"]
    assert digest == json.loads((DOCS / "data/run-card-lidar01.json").read_text())["raster"]["sha256"]
    assert not (DOCS / "downloads" / f"{NAME}.tif").exists()
    assert not (DOCS / "downloads" / f"{NAME}.zip").exists()


def test_public_release_pointer_is_not_cleared_or_downloadable():
    release = json.loads((DOCS / "downloads/current_release.json").read_text())
    assert release["cleared"] is False
    assert release["tif"] == ""
    assert release["zip"] == ""
    assert release["audit_candidate"].endswith(f"artifacts/lidar01/{NAME}.tif")
    assert release["audit_sha256"] == json.loads((ROOT / "evidence/lidar01_uniqueness.json").read_text())["candidate_sha256"]


def test_generated_site_explicitly_says_do_not_download_or_submit():
    for name in ("index.html", "executive-summary.html"):
        text = (DOCS / name).read_text(encoding="utf-8")
        assert "NOT CLEARED" in text
        assert "DO NOT DOWNLOAD" in text or "Do not download" in text
        assert "0.921018" in text
    for page in DOCS.glob("*.html"):
        text = page.read_text(encoding="utf-8")
        assert not re.search(r'href="[^"]*' + re.escape(NAME) + r'\.(?:tif|zip)', text)


def test_historical_scores_are_not_presented_as_organizer_confirmed():
    card = json.loads((DOCS / "data/run-card-lidar01.json").read_text())
    assert card["submission"]["organizer_confirmed_receipt"] is None
    assert card["budget"]["submission_slots_used"] == 0
    assert card["holdout_dti"]["label"] == "HOLDOUT-DTI"
