import json
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio
from affine import Affine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from lane_check import lane_check  # noqa: E402

TF = Affine(100.0, 0.0, 0.0, 0.0, -100.0, 10000.0)


def _write(path, arr, transform=TF):
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                       dtype="float32", crs="EPSG:32611", transform=transform) as dst:
        dst.write(arr.astype(np.float32), 1)
    return path


def _dots(seed, n=60, shape=(80, 80)):
    rng = np.random.default_rng(seed)
    a = np.zeros(shape, np.float32)
    idx = rng.choice(shape[0] * shape[1], n, replace=False)
    a.flat[idx] = rng.random(n) * 0.9 + 0.05
    return a


def test_identical_raster_is_flagged_and_hashes_are_reported(tmp_path):
    a = _dots(1)
    candidate = _write(tmp_path / "candidate.tif", a)
    registry = _write(tmp_path / "registry.tif", a.copy())
    rep = lane_check(candidate, [registry], stage="emitted")
    row = rep["comparisons"][0]
    assert rep["verdict"].startswith("LANE DRIFT")
    assert row["drift"] is True
    assert row["exact_duplicate"] is True
    assert row["exact_pixel_agreement"] == 1.0
    assert len(rep["candidate_sha256"]) == 64
    assert len(row["sha256"]) == 64


def test_shifted_dots_within_3px_are_flagged(tmp_path):
    a = _dots(2)
    b = np.roll(a, 2, axis=1)  # every dot moved 2 px: all within 3 px
    rep = lane_check(_write(tmp_path / "candidate.tif", a),
                     [_write(tmp_path / "registry.tif", b)], stage="emitted")
    row = rep["comparisons"][0]
    assert row["candidate_dots_within_3px"] > 0.7
    assert row["drift"] is True


def test_independent_raster_is_not_flagged(tmp_path):
    a = _dots(3)
    b = _dots(99)
    rep = lane_check(_write(tmp_path / "candidate.tif", a),
                     [_write(tmp_path / "registry.tif", b)], stage="emitted")
    assert rep["comparisons"][0]["drift"] is False
    assert rep["verdict"].startswith("no drift vs supplied registry")


def test_surface_stage_detects_high_correlation_without_dot_overlap(tmp_path):
    rng = np.random.default_rng(4)
    a = rng.random((80, 80)).astype(np.float32)
    b = (0.5 * a + 0.2).astype(np.float32)
    rep = lane_check(_write(tmp_path / "surface.tif", a),
                     [_write(tmp_path / "registry.tif", b)], stage="surface")
    row = rep["comparisons"][0]
    assert row["pearson_r"] > 0.99
    assert row["drift"] is True
    assert rep["candidate_dots"] is None
    assert row["candidate_dots_within_3px"] is None
    assert rep["stage"] == "surface"


def test_surface_stage_does_not_apply_dot_overlap(tmp_path):
    a = np.zeros((80, 80), np.float32)
    b = np.zeros((80, 80), np.float32)
    a[20, 20] = 1.0
    b[20, 24] = 1.0  # four pixels apart; surface mode is correlation/agreement only
    rep = lane_check(_write(tmp_path / "surface.tif", a),
                     [_write(tmp_path / "registry.tif", b)], stage="surface")
    row = rep["comparisons"][0]
    assert row["candidate_dots_within_3px"] is None
    assert row["drift"] is False
    assert rep["verdict"].startswith("no drift vs supplied registry")


def test_empty_candidate_is_inconclusive_and_json_safe(tmp_path):
    empty = np.zeros((80, 80), np.float32)
    rep = lane_check(_write(tmp_path / "candidate.tif", empty),
                     [_write(tmp_path / "registry.tif", _dots(6))], stage="emitted")
    assert rep["verdict"].startswith("INCONCLUSIVE")
    assert rep["comparisons"][0]["pearson_r"] is None
    json.dumps(rep, allow_nan=False)


def test_unaligned_registry_grid_is_rejected(tmp_path):
    a = _dots(7)
    candidate = _write(tmp_path / "candidate.tif", a)
    registry = _write(tmp_path / "registry.tif", a,
                      transform=Affine(100.0, 0.0, 100.0, 0.0, -100.0, 10000.0))
    with pytest.raises(ValueError, match="transform mismatch"):
        lane_check(candidate, [registry], stage="surface")


def test_no_registry_is_inconclusive():
    from lane_check import _verdict
    assert _verdict([], "surface").startswith("INCONCLUSIVE")
