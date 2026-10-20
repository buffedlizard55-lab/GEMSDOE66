"""LIDAR-03 release checks: the promoted candidate's bytes, card and site banner agree.

Fail-closed style, mirroring tests/test_lidar01_release.py: sha256s are recomputed from
disk, the run card must keep its verdict + labelled holdout numbers, and the site must
show the OK banner next to the downloads with the no-organizer-score disclaimer.
"""
import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
STEM = "gems66-lidar03-cvretrain-reliefdecile-37654dots-20261020T190152Z"
CARD = json.loads((DOCS / "data" / "run-card-lidar03.json").read_text())


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_run_card_verdict_and_labels():
    assert CARD["verdict"] == "promote"
    hd = CARD["holdout_dti"]
    assert hd["label"] == "HOLDOUT-DTI"
    assert hd["paired_diff_ci95"][0] > 0
    assert hd["total_withheld_positives"] == 48465
    assert CARD["submission"]["organizer_confirmed_receipt"] is None
    assert CARD["submission"]["slots_used"] == 0
    assert len(CARD["submission"]["note"]) <= 140
    assert CARD["leakage_canary"]["worst_auc"] <= 0.90
    u = CARD["uniqueness_vs_registry"]
    assert u["max_abs_surface_spearman_sample100k"] <= 0.90
    assert u["max_dot_overlap3px_density_comparable"] <= 0.70
    assert u["any_identical"] is False


def test_published_bytes_match_card_and_are_format_clean():
    for suffix in ("zeros", "nan"):
        tif = DOCS / "downloads" / f"{STEM}-{suffix}.tif"
        assert tif.is_file()
        assert _sha(tif) == CARD["raster"][suffix]["sha256"]
        with zipfile.ZipFile(DOCS / "downloads" / f"{STEM}-{suffix}.zip") as z:
            assert z.namelist() == [f"{STEM}-{suffix}.tif"]
            assert z.testzip() is None
        with rasterio.open(tif) as src:
            assert src.count == 1 and src.dtypes[0] == "float32"
            assert src.crs.to_epsg() == 32611
            assert (src.height, src.width) == (3730, 3292)
            assert src.nodata is None
            arr = src.read(1)
        fin = arr[np.isfinite(arr)]
        assert fin.min() >= 0.0 and fin.max() <= 1.0
        assert int((arr > 0).sum()) == 37654
        if suffix == "zeros":
            assert not np.isnan(arr).any()  # immune to the portal [0, 1] rejection
        # audit copy is byte-identical to the published copy
        assert _sha(ROOT / "artifacts" / "lidar03" / f"{STEM}-{suffix}.tif") == _sha(tif)


def test_site_banner_is_unambiguous_and_disclosed():
    for page in ("index.html", "executive-summary.html"):
        flat = " ".join((DOCS / page).read_text(encoding="utf-8").split())
        assert "LIDAR-03" in flat and "OK TO DOWNLOAD AND SUBMIT" in flat, page
        assert f"downloads/{STEM}-zeros.tif" in flat, page
        assert "HOLDOUT-DTI" in flat and "95% CI" in flat, page
        assert "ORGANIZER-CONFIRMED" in flat, page
        # LIDAR-02's negative verdict and LIDAR-01's withdrawal stay printed
        assert "NOT OK TO SUBMIT" in flat, page
        assert "0.921018" in flat, page
        # portal rejection mode addressed where downloads are offered
        assert "Predicted values must be in range [0, 1]" in flat, page


def test_no_merge_conflict_markers_anywhere_in_site_or_builder():
    for path in list(DOCS.glob("*.html")) + [ROOT / "scripts" / "build_site.py"]:
        text = path.read_text(encoding="utf-8")
        assert "<<<<<<<" not in text and ">>>>>>>" not in text, str(path)
