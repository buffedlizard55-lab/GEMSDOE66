"""Session-66 release invariants: the bytes offered for download must satisfy every stated claim."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SLUG = json.loads((Path(__file__).resolve().parents[1] / "registry66" / "run-card-session66.json").read_text())["raster"]["file"].split("/")[-1][:-len("-nan.tif")]
DL = ROOT / "docs" / "downloads"
CARD = ROOT / "registry66" / "run-card-session66.json"
RELEASE = ROOT / "evidence66" / "e13_release.json"


def _rasterio():
    return pytest.importorskip("rasterio")


def test_run_card_and_release_agree():
    card = json.loads(CARD.read_text())
    rel = json.loads(RELEASE.read_text())
    assert card["verdict"].startswith("PROMOTE")
    assert card["promote"] is True
    assert card["raster"]["sha256"] == rel["files"]["nan"]["sha256"]
    assert card["raster"]["sibling_allfinite_sha256"] == rel["files"]["allfinite"]["sha256"]
    assert len(card["submission"]["note"]) <= 140
    assert 0 < len(card["submission"]["name"]) <= 120
    # session-66 pass 3: the frozen local holdout IS measured, with CI and withheld counts,
    # and the card must state the margin against the family's best-known design.
    hold = card["holdout_dti"]
    assert hold["label"] == "HOLDOUT-DTI"
    assert isinstance(hold["value"], float) and 0.0 < hold["value"] < 1.0
    assert hold["ci95"][0] < hold["value"] < hold["ci95"][1]
    assert hold["withheld_positive_count"] > 1000 and hold["n_folds"] == 8
    assert "evaluator_version" in hold and hold["evaluator_version"]
    assert "margin_vs_incumbent" in hold
    assert "not beat" in hold["status"] or "ties" in hold["status"]


def test_download_exists_and_hashes_match():
    card = json.loads(CARD.read_text())
    import hashlib
    for key, name in (("file", "nan"), ("sibling_allfinite", "allfinite")):
        p = ROOT / card["raster"][key]
        assert Path(p).exists(), p
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        assert h == card["raster"]["sha256" if name == "nan" else "sibling_allfinite_sha256"]
    assert (ROOT / card["raster"]["zip"]).exists()


def test_download_is_competition_format():
    _rasterio()
    import rasterio
    from gems.constants import EPSG, SHAPE_HW
    card = json.loads(CARD.read_text())
    for key in ("file", "sibling_allfinite"):
        with rasterio.open(ROOT / card["raster"][key]) as src:
            assert src.count == 1
            assert src.dtypes[0] == "float32"
            assert (src.height, src.width) == tuple(SHAPE_HW)
            assert src.crs.to_string() == EPSG
            assert abs(src.res[0] - 100.0) < 1e-9
            arr = src.read(1)
        finite = np.isfinite(arr)
        assert np.isnan(arr[finite]).sum() == 0
        vals = arr[finite]
        assert vals.min() >= 0.0 and vals.max() <= 1.0
        if key == "file":
            # only the NaN encoding carries the emitted dots; the all-finite sibling is zeros
            assert int((arr > 0).sum()) == card["statistics"]["n_dots"]


def test_nan_outside_footprint_matches_reference_grid():
    _rasterio()
    import rasterio
    ref = ROOT / "data" / "raw" / "sample_submission.tif"
    if not ref.exists():
        pytest.skip("reference raster not restored in this checkout")
    card = json.loads(CARD.read_text())
    with rasterio.open(ref) as r:
        fp = np.isfinite(r.read(1))
    with rasterio.open(ROOT / card["raster"]["file"]) as s:
        arr = s.read(1)
    assert np.isnan(arr[fp]).sum() == 0
    assert np.isfinite(arr[~fp]).sum() == 0


def test_catalogue_prune_claim_holds():
    _rasterio()
    import rasterio
    from scipy import ndimage
    labels = ROOT / "data" / "raw" / "labels.tif"
    if not labels.exists():
        pytest.skip("labels.tif not restored in this checkout")
    card = json.loads(CARD.read_text())
    with rasterio.open(labels) as s:
        cat = s.read(1) > 0
    with rasterio.open(ROOT / card["raster"]["file"]) as s:
        dots = s.read(1) > 0
    d = ndimage.distance_transform_edt(~cat)
    assert float((d[dots] <= 2).mean()) == 0.0


def test_site_advertises_the_download_and_the_how_to():
    idx = (ROOT / "docs" / "index.html").read_text()
    ex = (ROOT / "docs" / "executive-summary.html").read_text()
    assert "DOWNLOAD IS READY" in idx
    assert f"downloads/{SLUG}-nan.tif" in idx
    assert "HOLDOUT-DTI" in idx and "ties it, it does not beat it" in idx
    assert "How to submit, step by step" in ex
    assert "Predicted values must be in range [0, 1]" in ex
    assert "HOLDOUT-DTI" in ex


def test_charter_is_at_the_top_of_the_readme():
    readme = (ROOT / "README.md").read_text()
    assert "SESSION-66 STANDING CHARTER" in readme
    assert readme.index("SESSION-66 STANDING CHARTER") < 2000
