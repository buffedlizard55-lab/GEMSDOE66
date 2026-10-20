"""Tests for the LIDAR-03 dual-product (1 m + 3 m) Scarplet + Steger/Frangi + TIGER road/canal mask + spatial-CV submission."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np
import pytest
import rasterio

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DL = DOCS / "downloads"
ART = ROOT / "artifacts" / "lidar05"
EVID = ROOT / "evidence"
CARD = DOCS / "data" / "run-card-lidar05.json"
STEM = "gems66-lidar03-dual-scarp-steger-frangi-tiger-cv-20261020T193000Z-6036addc"


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def test_lidar03_run_card_and_evidence_files_exist_and_agree():
    assert CARD.is_file()
    rc = json.loads(CARD.read_text(encoding="utf-8"))
    e1 = json.loads((EVID / "lidar05_e1_canary_and_pilot.json").read_text(encoding="utf-8"))
    e2 = json.loads((EVID / "lidar05_e2_holdout.json").read_text(encoding="utf-8"))
    e3 = json.loads((EVID / "lidar05_e3_validation_and_uniqueness.json").read_text(encoding="utf-8"))

    assert rc["run_id"] == STEM
    assert rc["promote"] is True
    assert rc["promotion_decision"] == "promote"
    assert rc["verdict"] == "promote"
    assert rc["budget"]["new_experiments_used"] == 3
    assert rc["budget"]["limit"] == 3
    assert rc["budget"]["submission_slots_used"] == 0

    # Submission name & <=140-char note
    sub = rc["submission"]
    assert sub["name"] == f"{STEM}-nan"
    assert 0 < len(sub["note"]) == sub["note_chars"] <= 140
    assert sub["note"] == e3["submission"]["note"]

    # Leakage canary (E1): 71 features tested, max AUC <= 0.90, 0 flagged
    can = rc["leakage_canary"]
    assert can["status"] == "PASS"
    assert can["n_features_tested"] == 71
    assert can["max_feature_auc"] <= 0.90
    assert can["n_flagged"] == 0
    assert can == e1["leakage_canary"]

    # 3 m pilot DEM verification (E1)
    pil = rc["pilot_3m_verification"]
    for tile_name in ("x40y427_3m.tif", "x42y425_3m.tif"):
        t = pil["tiles"][tile_name]
        assert t["spearman_frangi3m_vs_h52_h"] > 0.90
        assert t["spearman_steger3m_vs_h52_h"] > 0.80
        assert t["spearman_frangi3m_vs_lidar1m_step"] > 0.85

    # 4-fold spatial-CV holdout & relief-tercile gate (E2)
    hd = rc["holdout_dti"]
    assert hd["label"] == "HOLDOUT-DTI"
    assert hd["withheld_positive_count"] == 27379
    assert hd["value"] == pytest.approx(0.21392, abs=1e-5)
    assert hd["ci95"][0] > hd["random_baseline_ci95"][1]
    assert hd["paired_gain_over_random"]["folds_won"] == 4
    assert hd["paired_gain_over_Random"]["ci95"][0] > 0 if "paired_gain_over_Random" in hd else hd["paired_gain_over_random"]["ci95"][0] > 0
    assert hd["paired_gain_over_geophys_baseline"]["folds_won"] == 4
    assert hd["paired_gain_over_geophys_baseline"]["ci95"][0] > 0

    rel_s = hd["relief_stratification"]
    assert rel_s["all_three_strata_beat_random"] is True
    assert rel_s["not_confined_to_range_fronts"] is True
    low = rel_s["strata"]["low_relief_basin_le_13p7m"]
    assert low["lidar03_lift_over_random"] > 1.35
    assert low["lidar03_gain_over_baseline"] > 0.05

    # Pre- and post-placement uniqueness across all 60 registry rasters (E3)
    reg = rc["registry_checks"]
    assert reg["pre_placement_surface"]["verdict"] == "UNIQUE"
    assert reg["pre_placement_surface"]["max_abs_spearman_rho"] <= 0.90
    assert reg["pre_placement_surface"]["n_compared"] == 60
    post = reg["post_placement_dots"]
    assert post["verdict_gemsdoe66"] == "UNIQUE"
    assert post["max_abs_spearman_rho"] <= 0.90
    assert post["max_euclidean_3px_overlap_all_60"] <= 0.70


def test_lidar03_rasters_and_zips_match_hashes_and_grid_contract():
    rc = json.loads(CARD.read_text(encoding="utf-8"))
    r = rc["raster"]

    for suf, sha_key, zsha_key in (
        ("nan", "sha256", "nan_zip_sha256"),
        ("zeros", "zeros_sha256", "zeros_zip_sha256"),
    ):
        art_tif = ART / f"{STEM}-{suf}.tif"
        dl_tif = DL / f"{STEM}-{suf}.tif"
        dl_zip = DL / f"{STEM}-{suf}.zip"
        assert art_tif.is_file() and dl_tif.is_file() and dl_zip.is_file()
        assert _sha256(art_tif) == r[sha_key]
        assert _sha256(dl_tif) == r[sha_key]
        assert _sha256(dl_zip) == r[zsha_key]
        with zipfile.ZipFile(dl_zip) as zf:
            assert zf.namelist() == [f"{STEM}-{suf}.tif"]
            assert zf.testzip() is None

        with rasterio.open(dl_tif) as ds:
            assert ds.count == 1
            assert ds.dtypes[0] == "float32"
            assert ds.crs.to_string() == "EPSG:32611"
            assert (ds.height, ds.width) == (3730, 3292)
            assert abs(abs(ds.res[0]) - 100.0) < 1e-9 and abs(abs(ds.res[1]) - 100.0) < 1e-9
            arr = ds.read(1)
            finite = np.isfinite(arr)
            vals = arr[finite]
            assert vals.min() >= 0.0 and vals.max() <= 1.0
            assert int((arr[finite] > 0).sum()) == 24000
            if suf == "nan":
                assert int(finite.sum()) == 5_167_373
            else:
                assert int(finite.sum()) == 3730 * 3292


def test_lidar03_banner_is_prominent_on_index_and_executive_summary():
    rc = json.loads(CARD.read_text(encoding="utf-8"))
    for page_name in ("index.html", "executive-summary.html"):
        html = (DOCS / page_name).read_text(encoding="utf-8")
        assert "LIDAR-05 / DUAL-SCARP (2026-10-20): NEW UNIQUE GEOTIFF GENERATED" in html
        assert "OK TO DOWNLOAD AND SUBMIT (WITH SCIENTIFIC DISCLOSURES)" in html
        assert f"downloads/{STEM}-nan.tif" in html
        assert f"downloads/{STEM}-zeros.tif" in html
        assert rc["raster"]["sha256"] in html
        assert rc["submission"]["note"] in html
        assert "0.21392" in html
        assert "0.6951" in html
