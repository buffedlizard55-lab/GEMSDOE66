"""Shared registry uniqueness checks distinguish continuous surfaces from emitted dots."""

import hashlib

import numpy as np
import pytest
import rasterio
from affine import Affine

from gems57.gates import lane_uniqueness_report
from gems57.uniqueness import compare_array_to_registry, summarize_registry_rows, two_phase_summary

TF = Affine(100.0, 0.0, 1000.0, 0.0, -100.0, 9000.0)
CRS = "EPSG:32611"


def _raster(path, values):
    values = np.asarray(values, np.float32)
    with rasterio.open(path, "w", driver="GTiff", height=values.shape[0], width=values.shape[1],
                       count=1, dtype="float32", crs=CRS, transform=TF) as dst:
        dst.write(values, 1)
    return path


def _index(path, *, complete=True, organizer_complete=None):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if organizer_complete is None:
        organizer_complete = complete
    rasters = [{
        "repo_first": "test/repo", "sources": [path.name], "cache_file": str(path), "sha256": digest,
    }]
    return {"complete_accessible_scan": complete,
            "organizer_registry_complete": organizer_complete,
            "registry_rasters_expected": len(rasters),
            "errors": [], "rasters": rasters}


def test_dense_continuous_surface_uses_rank_and_pixel_checks_not_dot_overlap(tmp_path):
    rng = np.random.default_rng(17)
    mine = rng.random((24, 24), dtype=np.float32)
    theirs = rng.random((24, 24), dtype=np.float32)
    registry = _raster(tmp_path / "prior.tif", theirs)
    report = compare_array_to_registry(mine, _index(registry), np.ones(mine.shape, bool), phase="surface")
    assert report["phase"] == "surface"
    assert report["overlap_applicable"] is False
    assert report["worst_dot_overlap"] is None
    assert report["my_dots"] is None
    assert report["unique"] is True
    assert report["rows"][0]["my_dots_within_3px_of_theirs"] is None
    assert report["rows"][0]["duplicate_by_overlap"] is False
    assert report["rows"][0]["my_dots_within_3px_of_theirs"] is None


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


def test_accessible_scan_without_organizer_completeness_is_not_a_pass(tmp_path):
    rng = np.random.default_rng(18)
    mine = rng.random((24, 24), dtype=np.float32)
    theirs = rng.random((24, 24), dtype=np.float32)
    registry = _raster(tmp_path / "accessible-only.tif", theirs)
    report = compare_array_to_registry(
        mine, _index(registry, complete=True, organizer_complete=False),
        np.ones(mine.shape, bool), phase="surface",
    )
    assert report["complete_accessible_scan"] is True
    assert report["organizer_registry_complete"] is False
    assert report["unique_within_accessible_scan"] is True
    assert report["unique"] is False
    assert report["stop_required"] is True
    assert "complete registry not certified" in report["verdict"]

    # A boolean claim without an expected inventory count is not a certificate.
    uncounted = _index(registry, complete=True, organizer_complete=True)
    del uncounted["registry_rasters_expected"]
    uncounted_report = compare_array_to_registry(
        mine, uncounted, np.ones(mine.shape, bool), phase="surface",
    )
    assert uncounted_report["organizer_registry_complete"] is False
    assert uncounted_report["unique"] is False


def test_shared_gate_ok_requires_full_registry_certificate(tmp_path):
    rng = np.random.default_rng(28)
    mine = rng.random((24, 24), dtype=np.float32)
    theirs = rng.random((24, 24), dtype=np.float32)
    sample = _raster(tmp_path / "sample.tif", np.zeros_like(mine))
    registry = _raster(tmp_path / "prior.tif", theirs)
    report = lane_uniqueness_report(
        mine, np.ones(mine.shape, bool), sample=sample, phase="surface",
        registry_index=_index(registry, complete=True, organizer_complete=False),
    )
    assert report["unique_within_accessible_scan"] is True
    assert report["complete_registry_pass"] is False
    assert report["ok"] is False


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


def test_cached_negative_correlation_flag_is_recomputed_and_surface_overlap_ignored():
    row = {
        "sha256": "a" * 64,
        "spearman_full_footprint": -0.95,
        "duplicate_by_rho": False,  # stale signed-only flag from an older audit
        "my_dots_within_3px_of_theirs": 0.99,
        "duplicate_by_overlap": True,  # not an applicable rule for a dense surface
        "identical_bytes": False,
        "identical_decoded_predictions": False,
    }
    report = summarize_registry_rows(
        [row], registry_rasters_expected=1, complete_accessible_scan=True,
        source_errors=[], candidate_meta={"my_dots": 900, "candidate_rank_variation": True},
        scope="synthetic unit test", phase="surface",
    )
    assert report["rows"][0]["duplicate_by_rho"] is True
    assert report["rows"][0]["duplicate_by_overlap"] is False
    assert report["my_dots"] is None
    assert report["worst_dot_overlap"] is None
    assert report["unique"] is False


def test_cached_emitted_overlap_is_recomputed_and_malformed_values_fail_closed():
    row = {
        "sha256": "b" * 64,
        "spearman_full_footprint": 0.2,
        "duplicate_by_rho": False,
        "my_dots_within_3px_of_theirs": 0.8,
        "duplicate_by_overlap": False,  # stale cached threshold flag
        "identical_bytes": False,
        "identical_decoded_predictions": False,
    }
    result = summarize_registry_rows(
        [row], registry_rasters_expected=1, complete_accessible_scan=True,
        source_errors=[], candidate_meta={"my_dots": 100, "candidate_rank_variation": True},
        scope="synthetic unit test", phase="emitted",
    )
    assert result["rows"][0]["duplicate_by_overlap"] is True
    assert result["unique"] is False

    malformed = dict(row, my_dots_within_3px_of_theirs=1.2)
    blocked = summarize_registry_rows(
        [malformed], registry_rasters_expected=1, complete_accessible_scan=True,
        source_errors=[], candidate_meta={"my_dots": 100, "candidate_rank_variation": True},
        scope="synthetic unit test", phase="emitted",
    )
    assert blocked["complete_accessible_scan"] is False
    assert blocked["unique"] is False
    assert "malformed uniqueness measurement" in blocked["rows"][0]["error"]


def test_two_phase_summary_handles_surface_null_overlap_and_absolute_rho():
    report = two_phase_summary(
        [{"submission":"inverse", "their_dots":10,
          "spearman_full_footprint":-0.95,
          "my_dots_within_3px_of_theirs":None,
          "their_dots_within_3px_of_mine":None,
          "identical_bytes":False,
          "identical_decoded_predictions":False}],
        footprint_cells=576, expected_rasters=1, phase="surface",
        organizer_registry_complete=True,
    )
    assert report["literal_reading"]["rho_firings"] == 1
    assert report["literal_reading"]["worst_abs_spearman_full_footprint"] > 0.90
    assert report["literal_reading"]["forward_overlap_firings"] == 0
    assert report["unique"] is False
    assert report["stop_required"] is True


def test_two_phase_summary_does_not_clear_a_clean_partial_registry():
    report = two_phase_summary(
        [{"submission":"only-accessible", "their_dots":5,
          "spearman_full_footprint":0.2,
          "my_dots_within_3px_of_theirs":0.1,
          "their_dots_within_3px_of_mine":0.1,
          "jaccard_dot_sets":0.05,
          "identical_bytes":False,
          "identical_decoded_predictions":False}],
        footprint_cells=576, expected_rasters=1, phase="emitted",
        organizer_registry_complete=False,
    )
    assert report["complete_accessible_scan"] is True
    assert report["organizer_registry_complete"] is False
    assert report["unique_within_accessible_scan"] is True
    assert report["unique"] is False
    assert report["stop_required"] is True


def test_unknown_phase_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="phase must be"):
        compare_array_to_registry(np.ones((2, 2)), [], np.ones((2, 2), bool), phase="soft")
