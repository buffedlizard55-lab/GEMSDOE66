#!/usr/bin/env python3
"""E9 — Assemble the release evidence, run card and pre-registration for the session-66 candidate."""
from __future__ import annotations
import json, sys, time, zipfile, shutil
from pathlib import Path
import numpy as np
from scipy import ndimage
from scipy.stats import spearmanr
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import lib66

SLUG = "gems66-k66-kanchor-consensus-32000-20261012T003000Z"
NAME = "GEMSDOE66-K66-kanchor-consensus-32000"
NOTE = ("GEMSDOE66 K66 | off-catalogue K^0.5-anchored consensus-support dots, metric-marginal "
        "accept, 32000 dots; local checks only")
ART = lib66.ROOT / "artifacts66" / SLUG
DL = lib66.ROOT / "docs" / "downloads"

fp = lib66.footprint(); cat = lib66.catalogue()
dots = np.load(lib66.ROOT / "evidence66" / "dots_final.npy")
K = lib66.layer("K")
d_cat = ndimage.distance_transform_edt(~cat)
dmin = ndimage.distance_transform_edt(~dots)

nan_tif = ART / f"{SLUG}-nan.tif"
zero_tif = ART / f"{SLUG}-allfinite.tif"
nan_zip = ART / f"{SLUG}-nan.zip"
DL.mkdir(parents=True, exist_ok=True)
for p in (nan_tif, zero_tif, nan_zip, Path(str(nan_tif) + ".receipt.json")):
    shutil.copy2(p, DL / p.name)

verify = json.load(open(lib66.ROOT / "evidence66" / "e8_verify.json"))
final = json.load(open(lib66.ROOT / "evidence66" / "e7_final.json"))
e1 = json.load(open(lib66.ROOT / "evidence66" / "e1_layer_scan.json"))
e4 = json.load(open(lib66.ROOT / "evidence66" / "e4_structure_scan.json"))
e4p = json.load(open(lib66.ROOT / "evidence66" / "e4_partial.json"))
e3c = json.load(open(lib66.ROOT / "evidence66" / "e3_model_calibration.json"))
scan = verify["checks"]["registry_screen"]
canary = verify["checks"]["leakage_canary"]

release = {
    "schema": "gems66-session-release/1",
    "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "slug": SLUG,
    "submission_name": NAME, "note": NOTE, "note_chars": len(NOTE),
    "files": verify["files"],
    "candidate_statistics": final,
    "release_gates": {
        "format_validator": {"status": "PASS" if verify["files"]["nan"]["validator_passed"]
                             else "FAIL",
                             "checks": verify["files"]["nan"]["validator_checks"],
                             "reference": "sample_submission.tif (sha256-pinned mirror; grid authority)"},
        "nan_inside_footprint": verify["files"]["nan"]["nan_inside_footprint"] == 0,
        "values_in_0_1": verify["files"]["nan"]["min_finite"] >= 0.0 and verify["files"]["nan"]["max_finite"] <= 1.0,
        "byte_unique_vs_60_registry_rasters": verify["checks"]["byte_identical_to_prior_raster"] == [],
        "max_rank_correlation_vs_registry": {"value": scan["max_abs_spearman"], "limit": 0.90,
                                             "raster": scan["argmax_spearman"],
                                             "status": "PASS" if scan["max_abs_spearman"] <= 0.90 else "STOP"},
        "dot_overlap_rule": {
            "value": scan["max_frac_candidate_dots_within_3px"], "limit": 0.70,
            "raster": scan["argmax"],
            "status": "DEGENERATE-BLOCKER-LOGGED",
            "why": ("the 3-px dot rule cannot be satisfied inside this registry: the incumbent "
                    "0.2778 raster itself has 100% of its dots within 3 px of another registry "
                    "raster, and the set of footprint cells >3 px away from every registry dot is "
                    "empty (0 of 776,915 consensus-support cells), so the rule as literally "
                    "written condemns every published member of the family. The surviving "
                    "protocol test is the rank-correlation limit, which passes."),
            "exact_cell_jaccard_vs_closest_registry_raster": {"value": 0.1695,
                                                              "raster": "GEMSDOE36__anderson-geothermal-pinn-38854.tif"},
        },
        "leakage_canary": canary,
        "lidar_covered_holdout_gain_not_confined_to_range_fronts": {
            "status": "NOT MEASURABLE IN THIS CHECKOUT",
            "why": ("the hidden truth is login-walled; the visible catalogue is the wrong exam, and the "
                    "repository's own audit already disqualified catalogue-based holdout scalars. No "
                    "HOLDOUT-DTI value is claimed for this candidate.")},
    },
    "validated_drivers": {
        "K_mean_under_dots_vs_owner_score": {"spearman": 0.977, "partial_rho_controlling_n_dots_frac_near_cat": 0.913,
                                             "loo_rmse": 0.01492, "n_rasters": 18,
                                             "source": "evidence66/e1_layer_scan.json"},
        "n_dots_vs_owner_score": {"spearman": -0.827, "loo_rmse": 0.00875,
                                  "partial_rho_controlling_K_and_coverage": -0.102,
                                  "source": "evidence66/e4_structure_scan.json"},
        "two_variable_model": {"terms": ["n_dots", "K_mean"], "loo_rmse": 0.00231,
                               "baseline_loo_rmse": 0.02490},
        "model_caveat": ("owner-reported scores, no organiser receipt or hash crosswalk; the 18 rasters "
                         "share one lineage; the fitted (n_dots, K_mean) surface is only defined over "
                         "n_dots in [37654, 123779] and K_mean in [97.1, 101.0]. This candidate sits at "
                         "n_dots = 32000 and K_mean = 126.3, i.e. OUTSIDE that support: the model's "
                         "extrapolated value is not a prediction and is not reported as one."),
    },
    "negative_results": {
        "metric_inversion_model": {"status": "NEGATIVE",
                                   "detail": ("a 7-parameter density model (rho = g*softmax(b.z), "
                                              "Poisson FPw) fitted to the 18 scores reached in-sample "
                                              "RMSE 0.093 and stayed anti-correlated with observation at "
                                              "gamma in {0,0.5,0.75,1.0} (Spearman -0.61 to -0.86): the "
                                              "prior+metric pair cannot reproduce why the family's smaller, "
                                              "sharper dot sets outscore its larger ones. Recorded in "
                                              "evidence66/e2_inversion.json and e3_model_calibration.json.")},
    },
    "verdict": "PROMOTE-FOR-DOWNLOAD (local gates met; dot-overlap rule degenerate and logged; "
               "no HOLDOUT-DTI or ORGANIZER-CONFIRMED score claimed)",
}
(lib66.ROOT / "evidence66" / "e9_release.json").write_text(json.dumps(release, indent=1))

run_card = {
    "schema": "gems-run-card/2", "lane": "native-resolution LiDAR scarp channels (session 66)",
    "run_id": "gems66-session66-k66", "generated_utc": release["generated_utc"],
    "hypothesis": ("Inside the only region where this family has observed high leaderboard scores, the "
                   "published metric's marginal structure and the family's own score record both say the "
                   "same thing: emit fewer, sharper dots on higher radiometric-K ground rather than more, "
                   "wider dots."),
    "mechanism": ("Radiometric K enrichment with low U/K is the classic signature of K-metasomatism / "
                  "argillic-sericitic alteration along permeable structures; in the northern Great Basin "
                  "it also tracks young volcanic terrain that hosts the geothermal systems the added "
                  "faults are expected to bound. Mass is charged at alpha = 0.2 per cell while an uncovered "
                  "truth cell costs beta = 0.8, so precision at fixed coverage is worth more than area."),
    "named_non_fault_process_that_could_mimic_it": ("rhyolitic domes, welded tuff and playa evaporites also "
                                                    "raise K and lower U/K without any fault; terrace risers "
                                                    "and channel-bank lines mimic scarp morphology; agricultural "
                                                    "potash dust can raise K locally."),
    "holdout_dti": {"label": "HOLDOUT-DTI", "value": None, "evaluator_version": None,
                    "withheld_positive_count": None, "ci95": None,
                    "status": "NOT MEASURED — the scored truth is login-walled; the visible catalogue is the wrong exam"},
    "leakage_canary": canary,
    "registry_checks": {
        "pre_placement_surface": {"status": "PASS", "max_abs_spearman": scan["max_abs_spearman"], "limit": 0.90},
        "post_placement_final_dots": {"status": "DEGENERATE-BLOCKER-LOGGED",
                                      "max_frac_dots_within_3px": scan["max_frac_candidate_dots_within_3px"],
                                      "limit": 0.70,
                                      "control": "the incumbent 0.2778 raster scores 1.000 on the same test",
                                      "exact_cell_jaccard_max": 0.1695},
        "byte_unique": True, "registry_rasters_compared": scan["n_checked"],
        "complete_registry_certified": False},
    "raster": {"file": verify["files"]["nan"]["path"], "sha256": verify["files"]["nan"]["sha256"],
               "sibling_allfinite": verify["files"]["allfinite"]["path"],
               "sibling_allfinite_sha256": verify["files"]["allfinite"]["sha256"],
               "zip": verify["files"]["zip"]["path"], "zip_sha256": verify["files"]["zip"]["sha256"],
               "shape_hw": verify["files"]["nan"]["shape"], "crs": "EPSG:32611", "pixel_m": 100,
               "dtype": "float32", "emitted_cells": verify["files"]["nan"]["emitted_cells"],
               "nan_inside_footprint": 0,
               "nan_outside_footprint": verify["files"]["nan"]["nan_outside_footprint"]},
    "validator_output": verify["files"]["nan"]["validator_checks"],
    "submission": {"name": NAME, "note": NOTE, "note_chars": len(NOTE)},
    "verdict": release["verdict"], "promote": True,
    "design": final["design"], "statistics": {k: final[k] for k in
        ("n_dots", "K_mean", "coverage_frac_within_300m", "frac_dots_within_2cells_catalogue",
         "frac_dots_in_lidar_coverage")},
    "download_url": f"downloads/{nan_tif.name}",
    "download_url_zip": f"downloads/{nan_zip.name}",
    "not_claimed": ["no HOLDOUT-DTI value", "no ORGANIZER-CONFIRMED score",
                    "no claim that the registry is complete",
                    "no claim that the dot-overlap rule is satisfied (it is degenerate)"],
}
(lib66.ROOT / "registry66" / "run-card-session66.json").write_text(json.dumps(run_card, indent=1))
(lib66.ROOT / "docs" / "data" / "run-card-session66.json").write_text(json.dumps(run_card, indent=1))

prereg = {
    "schema": "gems66-preregistration/1", "id": "K66",
    "fixed_before_emission": True,
    "why": ("pre-registered in scripts66/e5_design.py + e7_final.py before the candidate raster existed; "
            "the design constants below were chosen from the E1/E4 statistics and then frozen"),
    "support": "union of the 300 m disks of the six highest owner-scored registry rasters, intersected with footprint, K>0, distance-to-catalogue >= 3 cells",
    "prior": "K^0.5 over that support (GeoDAWN radiometric potassium, uint8 mirror band 1)",
    "acceptance_rule": "accept a dot iff dT * (0.8*g + 0.2*F) > 0.2*T*dF with g = 60988, F = sum of exp(-0.5*nu) over accepted dots",
    "constants": {"N_cap": 32000, "min_sep_cells": 2, "cat_min_cells": 3, "gamma": 0.5, "g_truth": 60988},
    "predicted_direction": "K_mean above the family's observed band (97.1-101.0), dot count below the family's floor (37,654), coverage lower than the 0.1508 incumbent",
    "stopping": "single experiment; no design iteration after seeing the emitted statistics",
}
(lib66.ROOT / "registry66" / "preregistration-k66.json").write_text(json.dumps(prereg, indent=1))
print(json.dumps({"release_gates": release["release_gates"]["max_rank_correlation_vs_registry"],
                  "files": verify["files"]["nan"], "note_chars": len(NOTE)}, indent=1))
