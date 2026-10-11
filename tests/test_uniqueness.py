"""Shared registry uniqueness checks distinguish continuous surfaces from emitted dots."""

import hashlib

import numpy as np
import pytest
import rasterio
from affine import Affine

from gems57.uniqueness import compare_array_to_registry

TF = Affine(100.0, 0.0, 1000.0, 0.0, -100.0, 9000.0)
CRS = "EPSG:32611"


def _raster(path, values):
    values = np.asarray(values, np.float32)
    with rasterio.open(path, "w", driver="GTiff", height=values.shape[0], width=values.shape[1],
                       count=1, dtype="float32", crs=CRS, transform=TF) as dst:
        dst.write(values, 1)
    return path


def _index(path, *, complete=True):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"complete_accessible_scan": complete, "errors": [], "rasters": [{
        "repo_first": "test/repo", "sources": [path.name], "cache_file": str(path), "sha256": digest,
    }]}


def test_dense_continuous_surface_uses_rank_and_pixel_checks_not_dot_overlap(tmp_path):
    rng = np.random.default_rng(17)
    mine = rng.random((24, 24), dtype=np.float32)
    theirs = rng.random((24, 24), dtype=np.float32)
    registry = _raster(tmp_path / "prior.tif", theirs)
    report = compare_array_to_registry(mine, _index(registry), np.ones(mine.shape, bool), phase="surface")
    assert report["phase"] == "surface"
    assert report["overlap_applicable"] is False
    assert report["worst_dot_overlap"] is None
    assert report["unique"] is True
    assert report["rows"][0]["my_dots_within_3px_of_theirs"] is None
    assert report["rows"][0]["duplicate_by_overlap"] is False


def test_emitted_phase_applies_three_pixel_dot_overlap(tmp_path):
    mine = np.zeros((24, 24), np.float32)
    theirs = np.zeros_like(mine)
    mine[5:20:2, 5:20:2] = 1.0
    theirs[5:20:2, 6:21:2] = 1.0
    registry = _raster(tmp_path / "prior-dots.tif", theirs)
    report = compare_array_to_registry(mine, _index(registry), np.ones(mine.shape, bool), phase="emitted")
    assert report["phase"] == "emitted"
    assert report["overlap_applicable"] is True
    assert report["worst_dot_overlap"] > 0.70
    assert report["unique"] is False


def test_absolute_high_rank_correlation_stops_surface_phase(tmp_path):
    rng = np.random.default_rng(19)
    mine = rng.random((24, 24), dtype=np.float32)
    registry = _raster(tmp_path / "inverse.tif", 1.0 - mine)
    report = compare_array_to_registry(mine, _index(registry), np.ones(mine.shape, bool), phase="surface")
    assert report["worst_spearman_full_footprint"] < -0.99
    assert report["worst_abs_spearman_full_footprint"] > 0.99
    assert report["rows"][0]["duplicate_by_rho"] is True
    assert report["unique"] is False


def test_exact_decoded_pixels_and_incomplete_registry_fail_closed(tmp_path):
    rng = np.random.default_rng(23)
    mine = rng.random((24, 24), dtype=np.float32)
    registry = _raster(tmp_path / "same.tif", mine)
    exact = compare_array_to_registry(mine, _index(registry), np.ones(mine.shape, bool), phase="surface")
    assert exact["pixel_unique_among_checked"] is False
    assert exact["rows"][0]["identical_decoded_predictions"] is True
    assert exact["unique"] is False
    partial = compare_array_to_registry(mine, _index(registry, complete=False), np.ones(mine.shape, bool), phase="surface")
    assert partial["complete_accessible_scan"] is False
    assert partial["unique"] is False
    assert partial["stop_required"] is True


def test_unknown_phase_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="phase must be"):
        compare_array_to_registry(np.ones((2, 2)), [], np.ones((2, 2), bool), phase="soft")
