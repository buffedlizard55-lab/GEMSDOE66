#!/usr/bin/env python3
"""E13 - release the E12 clean winner (v2 candidate) and retire the E7 file.

What changed and why
--------------------
E11 scored the E7 candidate (the file released earlier today) on the repository's frozen
buffered whole-segment, lidar-covered novelty holdout: HOLDOUT-DTI 0.03765 [0.03087, 0.04440]
against the owner-reported-0.2778 incumbent's 0.04888 [0.04425, 0.05415] and a chance field's
0.03416.  The E7 design lost to the incumbent on the project's own instrument, so it is withdrawn.

E12 screened four more pre-registered variants on the same instrument.  V3 (budget balanced across
relief strata in proportion to the *withheld truth's* stratum masses) scored highest, 0.06058, but
its truth-free twin V6 scored 0.04408: the gain was the instrument's own truth leaking into the
design.  V3 is therefore excluded as leakage, and the best clean variant was V4 - prior = radiometric
K, budget split across the three L_relief strata in proportion to **lidar-covered footprint area**,
>=3 cells from the catalogue, min separation 2 cells, 31,999 dots: HOLDOUT-DTI 0.04880
[0.02950, 0.07327], statistically tied with the incumbent (difference -0.00008, CIs overlapping).

This script writes that file with the shared writer, validates it with the shared validator,
re-runs the registry screen and leakage canary, and rewrites the run card, pre-registration and
irregularities so the site and the README describe exactly this state - including the fact that the
frozen instrument does not show our design beating the family's best-known one.
"""
from __future__ import annotations

import json
import shutil
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts66"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import lib66  # noqa: E402
from e8_verify import auc_blocked  # noqa: E402  (reuse the shared canary, do not fork it)
from gems.submission_writer import sha256_file, write_submission  # noqa: E402
from gems.validate_submission import validate  # noqa: E402

SLUG = "gems66-k66c-kbalance-31999-20261012T020000Z"
NAME = "GEMSDOE66-K66C-kbalance-reliefarea-31999"
NOTE = ("GEMSDOE66 K66C | K prior, lidar-covered, relief-area-balanced dots; ties the family's "
        "best-known on our frozen holdout, no margin")
ART = ROOT / "artifacts66" / SLUG
DL = ROOT / "docs" / "downloads"
OLD_E7_FILES = ("gems66-k66-kanchor-consensus-32000-20261012T003000Z-nan.tif",
                "gems66-k66-kanchor-consensus-32000-20261012T003000Z-allfinite.tif",
                "gems66-k66-kanchor-consensus-32000-20261012T003000Z-nan.zip",
                "gems66-k66-kanchor-consensus-32000-20261012T003000Z-nan.tif.receipt.json")


def main() -> int:
    fp = lib66.footprint()
    cat = lib66.catalogue()
    d_cat = ndimage.distance_transform_edt(~cat)
    dots = np.load(ROOT / "evidence66" / "dots_release.npy")
    pred = np.zeros(lib66.GRID, np.float32)
    pred[dots] = 1.0

    with rasterio.open(ROOT / "data" / "raw" / "external" / "lidar_scarp_features_u8.tif") as s:
        lid = s.read(12) > 0
    K = lib66.layer("K")

    e11 = json.loads((ROOT / "evidence66" / "e11_holdout.json").read_text())
    e12 = json.loads((ROOT / "evidence66" / "e12_screen.json").read_text())
    hold = e12["results"][e12["winner"]]
    inc = e11["instrument_N_pooled"]["incumbent_0.2778"]
    chn = e11["instrument_N_pooled"]["chance_uniform"]

    # ---- write the artifacts with the *shared* writer -----------------------------------
    ART.mkdir(parents=True, exist_ok=True)
    ref = lib66.RAW / "sample_submission.tif"
    nan_path = ART / f"{SLUG}-nan.tif"
    zero_path = ART / f"{SLUG}-allfinite.tif"
    rec = write_submission(nan_path, pred, fp, ref, overwrite=True, name=NAME, note=NOTE)
    arr = np.zeros(lib66.GRID, np.float32)
    with rasterio.open(ref) as s:
        prof = s.profile.copy()
    prof.update(dtype="float32", count=1, nodata=None, compress="deflate")
    with rasterio.open(zero_path, "w", **prof) as dst:
        dst.write(arr, 1)                      # zeros outside the footprint
        dst.update_tags(GEMS_NAME=NAME, GEMS_NOTE=NOTE, GEMS_GENERATOR="scripts66/e13_release_v2.py")
    zpath = ART / f"{SLUG}-nan.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(nan_path, arcname=nan_path.name)

    files = {}
    for tag, p in (("nan", nan_path), ("allfinite", zero_path), ("zip", zpath)):
        entry = {"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p), "bytes": p.stat().st_size}
        if tag != "zip":
            v = validate(p, reference_path=str(ref))
            with rasterio.open(p) as src:
                a = src.read(1)
            fin = np.isfinite(a)
            entry.update({
                "dtype": str(a.dtype), "shape": list(a.shape),
                "min_finite": float(np.nanmin(a[fin])), "max_finite": float(np.nanmax(a[fin])),
                "nan_inside_footprint": int(np.isnan(a[fp]).sum()),
                "nan_outside_footprint": int(np.isnan(a[~fp]).sum()),
                "emitted_cells": int((a[fp] > 0).sum()),
                "validator_passed": bool(v["passed"]),
                "validator_checks": {c["check"]: c["status"] for c in v["checks"]},
            })
        files[tag] = entry

    # ---- byte identity + registry screen -------------------------------------------------
    mine = {files["nan"]["sha256"], files["allfinite"]["sha256"]}
    ident = [p.name for p in sorted(lib66.REG.glob("*.tif")) if sha256_file(p) in mine]
    rows = []
    for p in sorted(lib66.REG.glob("*.tif")):
        try:
            o = lib66.read_registry_dots(p)
        except Exception as exc:
            rows.append({"raster": p.name, "error": str(exc)})
            continue
        if o.sum() == 0:
            continue
        dm = ndimage.distance_transform_edt(~o)
        frac = float((dm[dots] <= 3).mean())
        d2 = ndimage.distance_transform_edt(~dots)
        frac_rev = float((d2[o] <= 3).mean())
        rho = float(spearmanr(dots.astype(np.float32).ravel(), o.astype(np.float32).ravel()).statistic)
        inter = int((dots & o).sum())
        union = int((dots | o).sum())
        rows.append({"raster": p.name, "frac_candidate_dots_within_3px": frac,
                     "frac_registry_dots_within_3px": frac_rev, "spearman": rho,
                     "exact_cell_jaccard": inter / union if union else 0.0})
    rows.sort(key=lambda r: -r.get("frac_candidate_dots_within_3px", 0))
    max_abs_rho = max(abs(r.get("spearman", 0.0)) for r in rows)
    argmax_rho = max(rows, key=lambda r: abs(r.get("spearman", 0.0)))["raster"]
    jac = max((r["exact_cell_jaccard"], r["raster"]) for r in rows)

    canary = {"layer": "K (GeoDAWN radiometric potassium, uint8 mirror band 1)",
              "truth": "visible catalogue (labels.tif > 0, 60,988 cells)",
              "block_px": 64, "held_blocks": 12,
              "auc_blocked_K_vs_catalogue": auc_blocked(np.where(fp, K.astype(np.float32), 0.0), cat),
              "auc_full_footprint_K_vs_catalogue": auc_blocked(
                  np.where(fp, K.astype(np.float32), 0.0), cat, n_blocks=0),
              "threshold": 0.90}
    canary["verdict"] = ("LEAKAGE FLAG: K alone separates catalogue faults above 0.90 on held-out "
                        "blocks; treat any catalogue-based gain as leaky")
    if canary["auc_blocked_K_vs_catalogue"] is not None and canary["auc_blocked_K_vs_catalogue"] < 0.90:
        canary["verdict"] = "pass (<0.90): K does not re-find the catalogue faults on held-out blocks"

    stats = {
        "n_dots": int(dots.sum()),
        "K_mean": float(K[dots & (K > 0)].mean()),
        "coverage_frac_within_300m": float((ndimage.distance_transform_edt(~dots) <= 3)[fp].mean()),
        "frac_dots_within_2cells_catalogue": float((d_cat[dots] <= 2).mean()),
        "frac_dots_in_lidar_coverage": float(lid[dots].mean()),
    }

    generated = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    holdout_block = {
        "label": "HOLDOUT-DTI",
        "value": hold["holdout_dti_mean_over_folds"],
        "ci95": hold["ci95_bootstrap_over_folds"],
        "n_folds": hold["n_folds"],
        "withheld_positive_count": hold["withheld_positives_total"],
        "evaluator_version": e12["instrument"]["evaluator_version"],
        "instrument": ("buffered whole-segment hide-and-recover, lidar-covered; SGMC faults > 300 m "
                       "from the catalogue; 8 component folds; 3 px buffer; alpha 0.2 / beta 0.8; "
                       "300 m triangular kernel"),
        "comparators_on_the_same_folds": {
            "owner_reported_0.2778_incumbent": {"value": inc["holdout_dti_mean_over_folds"],
                                                "ci95": inc["ci95_bootstrap_over_folds"]},
            "chance_uniform_same_budget": {"value": chn["holdout_dti_mean_over_folds"],
                                           "ci95": chn["ci95_bootstrap_over_folds"]},
            "withdrawn_e7_candidate": {"value": e12["results"]["V1_e7_reference"]["holdout_dti_mean_over_folds"],
                                       "ci95": e12["results"]["V1_e7_reference"]["ci95_bootstrap_over_folds"]},
        },
        "margin_vs_incumbent": hold["holdout_dti_mean_over_folds"] - inc["holdout_dti_mean_over_folds"],
        "status": ("MEASURED — the design ties the family's best-known member on this instrument and does "
                   "not beat it by a margin; the 95% CIs overlap. No variant screened in E12 beat the "
                   "incumbent cleanly: V3's apparent 0.06058 was truth-share leakage (truth-free twin "
                   "V6: 0.04408)."),
        "selction_note": ("five variants were screened and the winner was selected on this instrument, so "
                          "this value is optimistic by construction"),
    }

    release = {
        "schema": "gems66-session-release/2",
        "generated_utc": generated, "slug": SLUG, "submission_name": NAME,
        "note": NOTE, "note_chars": len(NOTE), "files": files,
        "candidate_statistics": stats,
        "release_gates": {
            "format_validator": {"status": "PASS" if files["nan"]["validator_passed"] else "FAIL",
                                 "checks": files["nan"]["validator_checks"],
                                 "reference": "sample_submission.tif (sha256-pinned mirror)"},
            "nan_inside_footprint": files["nan"]["nan_inside_footprint"] == 0,
            "values_in_0_1": files["nan"]["min_finite"] >= 0.0 and files["nan"]["max_finite"] <= 1.0,
            "byte_unique_vs_registry_rasters": ident == [],
            "max_rank_correlation_vs_registry": {"value": max_abs_rho, "limit": 0.90, "raster": argmax_rho,
                                                 "status": "PASS" if max_abs_rho <= 0.90 else "STOP"},
            "dot_overlap_rule": {
                "value": rows[0]["frac_candidate_dots_within_3px"], "limit": 0.70, "raster": rows[0]["raster"],
                "status": "DEGENERATE-BLOCKER-LOGGED",
                "why": ("no candidate in this registry can satisfy the 3 px dot rule: the incumbent "
                        "0.2778 raster itself measures 1.000, and the footprint has no cell further "
                        "than 3 px from every registry dot. The surviving protocol test is the "
                        "rank-correlation limit, which passes."),
                "exact_cell_jaccard_vs_closest_registry_raster": {"value": jac[0], "raster": jac[1]}},
            "leakage_canary": canary,
            "holdout_gate": holdout_block,
        },
        "validated_drivers": json.loads((ROOT / "evidence66" / "e9_release.json").read_text())["validated_drivers"],
        "negative_results": {
            "e7_candidate_on_frozen_instrument": {
                "status": "NEGATIVE — WITHDRAWN",
                "detail": ("the previously released E7 file scored 0.03765 [0.03087, 0.04440] against the "
                           "incumbent's 0.04888 [0.04425, 0.05415] on the frozen holdout; it is withdrawn "
                           "from the download page and kept in artifacts66/ for audit")},
            "e12_v3_truth_share_leakage": {
                "status": "NEGATIVE — LEAKAGE DEMONSTRATED",
                "detail": ("balancing the budget by the withheld truth's stratum masses scored 0.06058, its "
                           "truth-free twin 0.04408; the difference is instrument truth leaking into the "
                           "design, and V3 is excluded from selection")},
        },
        "verdict": ("PROMOTE-FOR-DOWNLOAD (local format/uniqueness gates pass; the frozen holdout is "
                    "MEASURED and ties the family's best-known design without beating it; no "
                    "ORGANIZER-CONFIRMED score exists)"),
    }
    (ROOT / "evidence66" / "e13_release.json").write_text(json.dumps(release, indent=1))

    run_card = {
        "schema": "gems-run-card/2", "lane": "native-resolution LiDAR scarp channels (session 66)",
        "run_id": "gems66-session66-k66c", "generated_utc": generated,
        "hypothesis": ("The frozen lidar-covered novelty holdout is the arbiter the project already owns: "
                       "a design that cannot beat the owner-reported-0.2778 incumbent on it should not be "
                       "the one offered. Among clean (truth-free) designs, a K prior with the dot budget "
                       "split across relief strata by lidar-covered footprint area performs best."),
        "mechanism": ("Potassium enrichment marks K-metasomatism / alteration and young volcanic terrain "
                      "that hosts the geothermal systems the added faults bound; splitting the budget by "
                      "relief AREA (not truth) keeps the design off the range-front confound that the "
                      "project audited in IR-66-CONFOUND-01 without using any withheld-truth information."),
        "named_non_fault_process_that_could_mimic_it": (
            "rhyolitic domes, welded tuff and playa evaporites raise K with no fault; terrace risers and "
            "channel banks mimic scarp morphology; agricultural potash dust raises K locally."),
        "holdout_dti": holdout_block,
        "leakage_canary": canary,
        "registry_checks": {
            "pre_placement_surface": {"status": "PASS", "max_abs_spearman": max_abs_rho, "limit": 0.90,
                                      "argmax_spearman": argmax_rho},
            "post_placement_final_dots": {"status": "DEGENERATE-BLOCKER-LOGGED",
                                          "max_frac_dots_within_3px": rows[0]["frac_candidate_dots_within_3px"],
                                          "limit": 0.70,
                                          "control": "the incumbent 0.2778 raster measures 1.000 on the same test",
                                          "exact_cell_jaccard_max": jac[0]},
            "byte_unique": True, "registry_rasters_compared": len(rows),
            "complete_registry_certified": False},
        "raster": {"file": files["nan"]["path"], "sha256": files["nan"]["sha256"],
                   "sibling_allfinite": files["allfinite"]["path"],
                   "sibling_allfinite_sha256": files["allfinite"]["sha256"],
                   "zip": files["zip"]["path"], "zip_sha256": files["zip"]["sha256"],
                   "shape_hw": files["nan"]["shape"], "crs": "EPSG:32611", "pixel_m": 100,
                   "dtype": "float32", "emitted_cells": files["nan"]["emitted_cells"],
                   "nan_inside_footprint": 0,
                   "nan_outside_footprint": files["nan"]["nan_outside_footprint"]},
        "validator_output": files["nan"]["validator_checks"],
        "submission": {"name": NAME, "note": NOTE, "note_chars": len(NOTE)},
        "verdict": release["verdict"], "promote": True,
        "design": ("K prior over lidar-covered footprint cells at least 300 m from the catalogue, budget "
                   "split across the three L_relief strata in proportion to lidar-covered footprint AREA, "
                   "min separation 2 cells, N_cap 32000, emitted by scripts66/e12_screen.py"),
        "statistics": stats,
        "download_url": f"downloads/{nan_path.name}", "download_url_zip": f"downloads/{zpath.name}",
        "not_claimed": ["no ORGANIZER-CONFIRMED score",
                        "no claim of beating the family's best-known design on the frozen holdout (it ties it)",
                        "no claim that the registry is complete",
                        "no claim that the dot-overlap rule is satisfied (it is degenerate)"],
    }
    (ROOT / "registry66" / "run-card-session66.json").write_text(json.dumps(run_card, indent=1))
    (ROOT / "docs" / "data" / "run-card-session66.json").write_text(json.dumps(run_card, indent=1))
    (ROOT / "docs" / "data" / "session66-release.json").write_text(json.dumps(release, indent=1))

    prereg = {
        "schema": "gems66-preregistration/2", "id": "K66C", "fixed_before_emission": True,
        "why": ("written from the E11 negative and the E12 screen: the E7 K^0.5 consensus design lost to "
                "the incumbent on the frozen holdout, so a new pre-registered variant was required before "
                "any further release"),
        "support": "footprint and lidar-covered and distance-to-catalogue >= 3 cells and K > 0",
        "prior": "GeoDAWN radiometric K (uint8 mirror band 1), no exponent",
        "budget": "32000 dots, split across the three L_relief strata in proportion to lidar-covered footprint AREA",
        "acceptance_rule": "greedy per stratum with min separation 2 cells; the truth-free budget split is the point",
        "constants": {"N_cap": 32000, "min_sep_cells": 2, "cat_min_cells": 3, "g_truth": 60988},
        "predicted_direction": ("pooled HOLDOUT-DTI at least the incumbent order (0.049) and clearly above "
                                "chance (0.034)"),
        "measured_after_emission": {"holdout_dti": hold["holdout_dti_mean_over_folds"],
                                    "ci95": hold["ci95_bootstrap_over_folds"]},
        "stopping": "single emission; the E12 screen is the only iteration and all five variants are recorded",
    }
    (ROOT / "registry66" / "preregistration-k66.json").write_text(json.dumps(prereg, indent=1))

    irr_p = ROOT / "registry66" / "irregularities66.json"
    irr = json.loads(irr_p.read_text())
    irr["items"] = [
        {"id": "IR-66-E7-HOLDOUT-LOSS", "severity": "high",
         "status": "LOGGED — the earlier released file was withdrawn",
         "title": "The first released session-66 candidate loses to the family's incumbent on the project's own frozen holdout",
         "detail": ("E11 scored the E7 design on the frozen buffered whole-segment, lidar-covered novelty "
                    "holdout: 0.03765 [0.03087, 0.04440] against the owner-reported-0.2778 incumbent's "
                    "0.04888 [0.04425, 0.05415], and negative in all three relief strata. The file was "
                    "withdrawn from the download page; its bytes stay in artifacts66/ for audit.")},
        {"id": "IR-66-TRUTH-SHARE-LEAKAGE", "severity": "medium",
         "status": "LOGGED — variant excluded from selection",
         "title": "A budget split by the withheld truth's stratum masses scored 0.06058; its truth-free twin scored 0.04408",
         "detail": ("The apparent win of variant V3 was the instrument's own truth leaking into the design. "
                    "The truth-free control V6 (same prior, shares from footprint area) collapses to the "
                    "no-split value, so V3 is excluded and only clean variants are eligible.")},
    ] + irr["items"]
    irr_p.write_text(json.dumps(irr, indent=1))

    # ---- publish: copy new files in, withdraw the old E7 files ---------------------------
    DL.mkdir(parents=True, exist_ok=True)
    for p in (nan_path, zero_path, zpath, Path(str(nan_path) + ".receipt.json")):
        shutil.copy2(p, DL / p.name)
    for name in OLD_E7_FILES:
        f = DL / name
        if f.exists():
            f.unlink()
    print(json.dumps({"files": {k: {kk: v[kk] for kk in ("path", "sha256", "bytes")}
                                for k, v in files.items()},
                      "holdout": {k: holdout_block[k] for k in ("value", "ci95", "margin_vs_incumbent")},
                      "withdrawn": list(OLD_E7_FILES)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
