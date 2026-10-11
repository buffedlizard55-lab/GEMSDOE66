"""Mechanical release guard tests. Synthetic metadata is not competition evidence."""
from copy import deepcopy
from pathlib import Path

from gems.release_gate import assess_release
from gems.submission_writer import sha256_file


def _fixtures(tmp_path):
    path = tmp_path / "unique-synthetic.tif"
    path.write_bytes(b"synthetic bytes; not a submission")
    digest = sha256_file(path)
    surface_digest = "a" * 64
    required = ("single band", "dtype float32", "CRS EPSG:32611", "shape matches",
                "resolution 100 m", "transform matches reference", "CRS matches reference",
                "values within [0, 1]", "no NaN inside footprint", "NaN-only outside footprint",
                "features grid shape matches", "features transform matches reference grid",
                "features CRS matches reference grid")
    validator = {"passed": True, "skipped_checks_mean_unverified": False, "file": str(path),
                 "sha256": digest, "checks": [{"check": k, "status": "PASS"} for k in required]}
    card = {
        "promote": True, "promotion_decision": "promote",
        "raster": {"file": path.name, "sha256": digest, "surface_sha256": surface_digest},
        "submission": {"file": path.name, "name": "UNIQUE-SYNTHETIC", "note": "Synthetic gate test only"},
        "holdout_dti": {"label": "HOLDOUT-DTI", "value": .2, "ci95": [.15, .25],
                        "withheld_positive_count": 100, "evaluator_version": "synthetic",
                        "gain_vs_frozen_best": {"value": .03, "ci95": [.01, .04]},
                        "off_range_front_gain": {"value": .02, "ci95": [.005, .04]}},
        "leakage_canary": {"status": "PASS", "feature_results": [{"name": "synthetic", "auc": .6}]},
        "independent_reviews": {"status": "PASS", "completed": 2, "reviewer_ids": ["A", "B"]},
        "input_provenance": {"official_grid_verified": True, "native_1m_dem_verified": True,
                             "cultural_mask_verified": True},
        "budget": {"new_experiments_used": 1, "submission_slots_used": 0},
    }
    audit = {"unique": True, "organizer_registry_complete": True,
             "complete_accessible_scan": True, "stop_required": False,
             "registry_rasters_expected": 2, "registry_rasters_checked": 2,
             "missing_or_invalid": 0, "source_errors": [], "duplicate_count": 0,
             "byte_unique_among_checked": True, "pixel_unique_among_checked": True,
             "worst_abs_spearman_full_footprint": .3}
    surface = dict(audit, phase="surface", candidate_file_sha256=surface_digest)
    dots = dict(audit, phase="emitted", candidate_file_sha256=digest,
                worst_dot_overlap=.2)
    return path, card, validator, surface, dots, surface_digest


def _assess(bundle):
    return assess_release(*bundle[:5], surface_sha256=bundle[5])


def test_synthetic_all_documentary_checks_only_clear_for_human_review(tmp_path):
    rep = _assess(_fixtures(tmp_path))
    assert rep["cleared_for_review"] is True
    assert rep["download_allowed"] is False  # never auto-publish


def test_current_card_blocks_even_if_every_format_check_passed(tmp_path):
    import json
    root = Path(__file__).resolve().parents[1]
    path, _, validator, surface, dots, sh = _fixtures(tmp_path)
    card = json.loads((root / "docs/data/run-card.json").read_text())
    rep = assess_release(path, card, validator, surface, dots, sh)
    assert not rep["cleared_for_review"]
    assert any("selector" in r for r in rep["blockers"])
    assert any("HOLDOUT-DTI" in r for r in rep["blockers"])


def test_scientific_and_input_gates_fail_closed(tmp_path):
    for change in (
        lambda b: b[1]["holdout_dti"].update(gain_vs_frozen_best={"value": .01, "ci95": [-.02, .04]}),
        lambda b: b[1]["holdout_dti"].update(off_range_front_gain=None),
        lambda b: b[1]["leakage_canary"]["feature_results"][0].update(auc=.91),
        lambda b: b[1]["independent_reviews"].update(reviewer_ids=["A", "A"]),
        lambda b: b[1]["input_provenance"].update(native_1m_dem_verified=False),
        lambda b: b[1]["budget"].update(new_experiments_used=4),
    ):
        b = list(deepcopy(_fixtures(tmp_path)))
        change(b)
        assert not _assess(b)["cleared_for_review"]


def test_raster_and_registry_checks_fail_closed(tmp_path):
    for change in (
        lambda b: b[2].update(sha256="b" * 64),
        lambda b: b[2]["checks"].pop(),  # outside-footprint validation absent
        lambda b: b[3].update(organizer_registry_complete=False),
        lambda b: b[3].update(worst_abs_spearman_full_footprint=.91),
        lambda b: b[4].update(worst_dot_overlap=.71),
        lambda b: b[4].update(candidate_file_sha256="b" * 64),
        lambda b: b[4].update(stop_required=True),
        lambda b: b.__setitem__(5, "b" * 64),
    ):
        b = list(deepcopy(_fixtures(tmp_path)))
        change(b)
        assert not _assess(b)["cleared_for_review"]
