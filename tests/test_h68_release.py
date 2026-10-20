"""Comprehensive unit and release verification tests for Session H68."""
from __future__ import annotations

import hashlib
import json
import math
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

from gems.metric import tversky_terms
from gemsdoe66.experiment66c import block_bootstrap_dti
from gemsdoe66.h68_scarp_vent import scarplet_slope_aware_3m
from gemsdoe66.uniqueness import _disc, compare

ROOT = Path(__file__).resolve().parents[1]
CARD_PATH = ROOT / "docs" / "data" / "run-card-h68.json"
MIRROR_CARD_PATH = ROOT / "registry" / "run_card_h68.json"
DL = ROOT / "docs" / "downloads"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def test_slope_aware_scarplet_rejects_pure_planar_fan_slope_and_recovers_erf_step():
    """Gram-Schmidt projection onto {1, s, erf(s/w) - c_w*s} must yield near-zero step throw
    on a steep uniform alluvial fan slope while accurately recovering a superimposed scarp step."""
    yy, xx = np.mgrid[0:240, 0:240].astype(np.float32)
    valid = np.ones((240, 240), dtype=bool)

    # Pure 12% uniform fan slope (86.4 m total relief!) with zero scarp:
    # interior residual throw is suppressed by >1000x relative to fan relief (< 0.03 m)
    z_planar = 1500.0 + 0.12 * (xx * 3.0)
    out_planar = scarplet_slope_aware_3m(z_planar, valid, res_m=3.0)
    assert float(np.nanmax(out_planar["amp"][85:-85, 85:-85])) < 0.03

    # Add a 2.0 m diffused scarp step across column 120 on top of the 12% planar slope
    s_m = (xx - 120.0) * 3.0
    z_scarp = z_planar + 1.0 * np.vectorize(lambda u: math.erf(u / 6.0))(s_m).astype(np.float32)
    out_scarp = scarplet_slope_aware_3m(z_scarp, valid, res_m=3.0)
    assert float(np.nanmax(out_scarp["amp"][85:-85, 118:123])) > 1.5
    assert float(np.nanmax(out_scarp["snr"][85:-85, 118:123])) > 20.0


def test_shared_bootstrap_and_uniqueness_optimizations_are_bit_exact():
    rng = np.random.default_rng(7)
    pred = (rng.random((64, 64)) > 0.96).astype(np.float32)
    truth = rng.random((64, 64)) > 0.95
    region = np.ones((64, 64), dtype=bool)
    boot = block_bootstrap_dti(pred, truth, region, block_px=16, n_boot=50, seed=3)
    assert boot["ci95"] is not None and 0.0 <= boot["ci95"][0] <= boot["ci95"][1] <= 1.0

    # Verify dilation vs full-grid EDT equality on random masks
    other = (rng.random((64, 64)) > 0.94).astype(np.float32)
    rep = compare(pred, other, region)
    d_exact = ndi.distance_transform_edt(~(other > 0))
    expected_w3 = float((d_exact[pred > 0] <= 3.0).mean())
    assert abs(rep["frac_candidate_dots_within_3px"] - expected_w3) < 1e-12


def test_h68_run_card_and_published_submission_artifacts_pass_all_gates():
    card = json.loads(CARD_PATH.read_text(encoding="utf-8"))
    mirror = json.loads(MIRROR_CARD_PATH.read_text(encoding="utf-8"))
    assert card == mirror

    assert card["verdict"] == "promote"
    assert card["promote"] is True
    assert card["cleared_for_download"] is True
    assert card["budget"]["experiments_used"] <= card["budget"]["experiments_allowed"] == 3
    assert card["budget"]["submission_slots_used"] == 0
    assert card["submission"]["organizer_confirmed_receipt"] is None
    assert 0 < card["submission"]["note_chars"] == len(card["submission"]["note"]) <= 140

    # Leakage canary
    can = card["leakage_canary"]
    assert can["status"] == "PASS"
    assert can["n_features_tested"] == 36
    assert can["max_symmetric_auc"] < 0.90

    # Holdout + non-range-front stratification gate
    hd = card["holdout_dti"]
    assert hd["label"] == "HOLDOUT-DTI"
    assert hd["withheld_positive_count"] > 30_000
    null_ci = hd["comparators_same_folds_and_budget"]["random_null"]["ci95"]
    assert hd["ci95"][0] > null_ci[1], "H68-1 95% CI must strictly exceed random null 95% CI"
    assert hd["value"] > hd["comparators_same_folds_and_budget"]["raw_elevation_confounded"]["pooled_dti"]
    assert hd["non_range_front_gate_passed"] is True
    for stratum_name, st in hd["relief_stratification"].items():
        assert st["h68_1_gain_vs_random"] > 0.0, f"failed relief stratum {stratum_name}"
        assert st["h68_1_lift_vs_random"] > 1.0, f"failed lift in {stratum_name}"

    # Uniqueness gate
    uni = card["correlation_overlap_vs_registry"]
    assert uni["verdict"] == "UNIQUE"
    assert uni["sha256_twins"] == 0
    assert uni["pre_placement_surface_max_abs_spearman_rho"] <= 0.90
    assert uni["final_dots_max_abs_spearman_rho"] <= 0.90
    assert uni["final_dots_comparable_density_max_within_3px"] <= 0.70

    # Re-open every published file on disk and verify hashes, CRS, transform, shape, range, NaNs
    r = card["raster"]
    tif_nan = DL / r["file"]
    tif_zeros = DL / r["zeros_file"]
    zip_nan = DL / r["zip_file"]
    assert tif_nan.is_file() and _sha256(tif_nan) == r["sha256"]
    assert tif_zeros.is_file() and _sha256(tif_zeros) == r["zeros_sha256"]
    assert zip_nan.is_file() and _sha256(zip_nan) == r["zip_sha256"]

    with zipfile.ZipFile(zip_nan) as zf:
        assert zf.namelist() == [tif_nan.name]
        assert zf.testzip() is None

    with rasterio.open(tif_nan) as ds_nan, rasterio.open(tif_zeros) as ds_zeros:
        assert ds_nan.count == 1 and ds_nan.dtypes[0] == "float32"
        assert ds_zeros.count == 1 and ds_zeros.dtypes[0] == "float32"
        assert ds_nan.crs.to_string() == "EPSG:32611"
        assert ds_zeros.crs.to_string() == "EPSG:32611"
        assert (ds_nan.height, ds_nan.width) == (3730, 3292)
        assert tuple(ds_nan.transform)[:6] == (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)

        a_nan = ds_nan.read(1)
        a_zeros = ds_zeros.read(1)
        assert not np.isnan(a_zeros).any() and not np.isinf(a_zeros).any()
        assert float(a_zeros.min()) >= 0.0 and float(a_zeros.max()) <= 1.0

        fin_mask = np.isfinite(a_nan)
        assert int(fin_mask.sum()) == 5_167_373
        assert int((~fin_mask).sum()) == 7_111_787
        assert np.array_equal(a_nan[fin_mask], a_zeros[fin_mask])
        assert int((a_zeros > 0).sum()) == r["emitted_cells"] == 35_800
