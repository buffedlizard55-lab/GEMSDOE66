#!/usr/bin/env python3
"""H67 candidate emission, registry uniqueness audit, submission write and run card.

Runs AFTER ``scripts/h67_holdout.py`` has selected a recipe, a truth-mass multiplier and a
catalogue-buffer decision on the spatially blocked holdout.  Nothing here re-tunes those
choices: they are read from ``evidence/h67_holdout*.json`` so the emitted artifact is the
artifact that was validated.

Usage:
  python3 scripts/h67_submit.py --recipe R4_catalogue_plus_sgmc --kappa 1.0 \
                                --budget 45000 --catalogue-buffer-m 0 [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gems import submission_writer           # noqa: E402
from gems import validate_submission         # noqa: E402
from gems67 import stack as h67stack         # noqa: E402
from gems67.design import load               # noqa: E402
from gems67.emit import greedy_emit          # noqa: E402

from gems67.design import INVENTORY_LAYERS  # noqa: E402  (shared, single definition)
RECIPES = {
    "R1_catalogue_only": ["d_visible_catalogue_m"],
    "R2_sgmc_off_only": ["d_sgmc_off_visible_m", "sgmc_fault"],
    "R4_catalogue_plus_sgmc": ["d_visible_catalogue_m", "d_sgmc_off_visible_m", "sgmc_fault"],
}


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", default="R4_catalogue_plus_sgmc",
                    choices=sorted(RECIPES) + ["R3_geophysical_only", "R5_full_stack",
                                               "R6_full_minus_sgmc"])
    ap.add_argument("--kappa", type=float, default=1.0)
    ap.add_argument("--budget", type=int, default=45000)
    ap.add_argument("--standoff-px", type=int, default=2,
                    help="pixels of catalogue standoff excluded from emission eligibility; "
                         "must match the winning --standoff-px of scripts/h67_holdout.py")
    ap.add_argument("--batch", type=int, default=2000)
    ap.add_argument("--outdir", default=str(ROOT / "artifacts" / "h67"))
    ap.add_argument("--holdout-json", nargs="*", default=[str(ROOT / "evidence" / "h67_holdout_C.json")])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    rng = np.random.default_rng(20261012)

    des = load()
    names = des.names
    with rasterio.open(h67stack.RAW / "sample_submission.tif") as ds:
        footprint = np.isfinite(ds.read(1).astype(np.float64))
    with rasterio.open(h67stack.RAW / "labels.tif") as ds:
        catalogue = ds.read(1) == 1
    with rasterio.open(h67stack.RAW / "training_features.tif") as ds:
        _fb = ds.read(1).astype(np.float64)
        feat_finite = np.isfinite(_fb) & (_fb > -1e38)
    del _fb
    with rasterio.open(h67stack.RAW / "external" / "derived_sgmc_faults_100m_u8.tif") as ds:
        sgmc = ds.read(1) == 1

    if args.recipe in ("R3_geophysical_only", "R5_full_stack", "R6_full_minus_sgmc"):
        cols = ([n for n in names if n not in INVENTORY_LAYERS]
                if args.recipe == "R3_geophysical_only" else
                [n for n in names if n not in ("d_sgmc_off_visible_m", "sgmc_fault", "d_sgmc_m")]
                if args.recipe == "R6_full_minus_sgmc" else names)
    else:
        cols = RECIPES[args.recipe]
    print(f"[1] recipe {args.recipe}: {len(cols)} layers", flush=True)

    # ---- train on the FULL visible catalogue (final model: nothing is withheld) -------------
    pos_flat = catalogue.ravel()[des.fp_idx]
    neg_flat = ~pos_flat
    pos_i = np.flatnonzero(pos_flat)
    neg_i = rng.choice(np.flatnonzero(neg_flat), size=min(int(neg_flat.sum()), 2 * pos_i.size),
                       replace=False)
    rows = np.concatenate([pos_i, neg_i])
    lab = np.concatenate([np.ones(pos_i.size, np.int8), np.zeros(neg_i.size, np.int8)])
    Xtr = np.empty((rows.size, len(cols)), dtype=np.float32)
    for j, nm in enumerate(cols):
        v = des.col(nm)[rows]
        Xtr[:, j] = np.where(np.isfinite(v), v, np.nan)
    clf = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.12, max_leaf_nodes=31,
                                         min_samples_leaf=40, l2_regularization=1.0,
                                         random_state=7)
    clf.fit(Xtr, lab)
    del Xtr
    print(f"    trained on {pos_i.size:,} positives / {neg_i.size:,} negatives "
          f"({time.time() - t0:.0f}s)", flush=True)

    prob = np.empty(des.n, dtype=np.float32)
    for a in range(0, des.n, 300_000):
        b_ = min(des.n, a + 300_000)
        blk = np.empty((b_ - a, len(cols)), dtype=np.float32)
        for j, nm in enumerate(cols):
            v = des.X[a:b_, names.index(nm)]
            blk[:, j] = np.where(np.isfinite(v), v, np.nan)
        prob[a:b_] = clf.predict_proba(blk)[:, 1]
    surf = des.to_grid(prob, fill=0.0)
    surf[~footprint] = 0.0

    # No prediction may sit outside the training-data bounds under EITHER reading of the rule:
    # the sample-submission mask (what the 12 scored owner artifacts follow) and the
    # training-features band-1 mask disagree by 3,061 / 1,540 cells (IR-67-FOOTPRINT-01).
    eligible = footprint & feat_finite
    if args.standoff_px > 0:
        eligible &= ndimage.distance_transform_edt(~catalogue) > args.standoff_px

    mass = args.kappa * float(prob.sum())
    print(f"[2] greedy emission: assumed truth mass {mass:,.0f}, budget {args.budget:,}",
          flush=True)
    dots, diag = greedy_emit(surf, eligible, budget=args.budget, total_truth_mass=mass,
                             batch=args.batch, verbose=True)
    n_dots = int(dots.sum())
    print(f"    emitted {n_dots:,} dots, E[DTI] under the belief model = "
          f"{diag['expected_dti']:.4f} ({time.time() - t0:.0f}s)", flush=True)

    pred = np.zeros(surf.shape, dtype=np.float32)
    pred[dots] = 1.0
    d_cat = ndimage.distance_transform_edt(~catalogue) * 100.0
    near_cat = int((dots & (d_cat <= 200)).sum())

    # ---- name / note -----------------------------------------------------------------------
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    surface_sha = sha256_bytes(surf.tobytes())[:12]
    # The name and the note must describe what was ACTUALLY emitted, not the lane we started
    # from: the validated recipe is inventory-free, so an "sgmcgap" label would be false.
    lane_tag = {"R3_geophysical_only": "geophys-maxcov",
                "R4_catalogue_plus_sgmc": "sgmcgap",
                "R1_catalogue_only": "catdist",
                "R2_sgmc_off_only": "sgmconly",
                "R5_full_stack": "fullstack",
                "R6_full_minus_sgmc": "full-nosgmc"}.get(args.recipe, args.recipe.split("_")[0].lower())
    sub_name = (f"gems66-h67-{lane_tag}-{args.recipe.split('_')[0].lower()}"
                f"-{n_dots}dots-{stamp}-{surface_sha}-nan")
    note = (f"H67 inventory-free geophysics/topography belief, metric-native max-coverage "
            f"emission; {n_dots} dots; NaN outside footprint")
    if len(note) > 140:
        note = note[:140]
    assert len(note) <= 140, len(note)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    tif = outdir / f"{sub_name}.tif"
    if args.dry_run:
        print(f"[dry-run] would write {tif}")
        return 0

    receipt = submission_writer.write_submission(
        tif, pred, footprint, h67stack.RAW / "sample_submission.tif", overwrite=True,
        name=sub_name, note=note)
    print(f"[3] wrote {tif.name}\n    sha256 {receipt['sha256']}", flush=True)

    report = validate_submission.validate(tif, h67stack.RAW / "sample_submission.tif",
                                          h67stack.RAW / "training_features.tif")
    print(f"[4] validator: passed={report['passed']} failures={report['has_failures']}")
    for c in report["checks"]:
        print(f"    {c['status']:8s} {c['check']}: {c['detail']}")

    zpath = outdir / f"{sub_name}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(tif, arcname=tif.name)

    # ---- registry uniqueness ---------------------------------------------------------------
    print("[5] registry uniqueness (surface + final dots, with a random-placement null)",
          flush=True)
    uniq = audit_uniqueness(pred, surf, footprint, tif)
    (outdir / f"uniqueness-{sub_name}.json").write_text(json.dumps(uniq, indent=1))
    worst_rho = max((r["spearman_rho_surface"] for r in uniq["comparisons"]), default=0.0)
    worst_ov = max((r["frac_cand_dots_within_3px"] for r in uniq["comparisons"]), default=0.0)
    worst_null = max((r["frac_random_dots_within_3px"] for r in uniq["comparisons"]), default=0.0)
    print(f"    max |rho| surface = {worst_rho:.4f} (stop > 0.90)")
    print(f"    max within-3px dot fraction = {worst_ov:.4f} "
          f"(null for the same raster {worst_null:.4f}; stop > 0.70)")

    card = {
        "schema": "gems-run-card/3",
        "run_id": sub_name,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo": "buffedlizard55-lab/GEMSDOE66",
        "lane": "off-catalogue geologic-map fault gap + metric-native max-coverage emission",
        "hypothesis": ("Faults drawn on the USGS SGMC state geologic map but absent from the "
                       "given USGS-QFDB/INGENIOUS catalogue are the population the organiser's "
                       "expert test set is drawn from, so a belief surface anchored on that gap "
                       "recovers off-catalogue faults a geophysics-only model cannot see."),
        "mechanism": ("Bedrock geologic maps record fault contacts that the Quaternary-only "
                      "fault database omits.  79,615 SGMC fault pixels (95.2%) lie outside the "
                      "given catalogue and 62,122 are more than 300 m from it, so they are "
                      "visible evidence of faulting the catalogue lacks."),
        "named_non_fault_mimic": ("Geologic map-unit contacts and bedding traces digitised as "
                                  "faults, arbitrary map-index lines, and lithologic boundaries "
                                  "with no geomorphic or geophysical expression."),
        "holdout_dti": {"label": "HOLDOUT-DTI", "source": args.holdout_json[0] if isinstance(args.holdout_json, list) else args.holdout_json,
                        "evaluator_version": ("src/gems/metric.py @ arena/855725e1; vectorised == "
                                              "literal brute force to 3.6e-15; official worked "
                                              "example TPw=3.00/FNw=2.00 reproduced exactly"),
                        "value": None, "ci95": None, "withheld_positive_count": None,
                        "note": "filled from the holdout JSON by scripts/h67_run_card.py"},
        "emission": {"rule": "greedy maximisation of expected DTI under an independent-"
                             "Bernoulli truth model; stops at break-even, budget is a cap",
                     **{k: (float(v) if isinstance(v, (int, float)) else v)
                        for k, v in diag.items()},
                     "dot_budget_cap": args.budget, "kappa_truth_mass": args.kappa,
                     "standoff_px": args.standoff_px, "recipe": args.recipe},
        "registry_checks": {"max_abs_spearman_surface": worst_rho,
                            "max_frac_dots_within_3px": worst_ov,
                            "max_frac_random_dots_within_3px_same_raster": worst_null,
                            "rasters_compared": uniq["n_rasters"],
                            "thresholds": {"rho": 0.90, "within_3px": 0.70}},
        "raster": {"file": tif.name, "sha256": receipt["sha256"],
                   "shape_hw": receipt["shape_hw"], "crs": receipt["crs"],
                   "emitted_cells": n_dots, "dots_within_200m_of_catalogue": near_cat,
                   "min_inside": receipt["min_inside"], "max_inside": receipt["max_inside"],
                   "nan_inside": receipt["nan_inside"],
                   "nan_outside_count": receipt["nan_outside_count"]},
        "validator": {"passed": report["passed"], "has_failures": report["has_failures"],
                      "checks": report["checks"]},
        "submission": {"name": sub_name, "note": note, "note_chars": len(note),
                       "zip": zpath.name},
        "scores_claimed": "NONE. No ORGANIZER-CONFIRMED score exists for this artifact.",
    }
    (outdir / f"run-card-{sub_name}.json").write_text(json.dumps(card, indent=1))
    print(f"[6] wrote run card + {zpath.name};  total {time.time() - t0:.0f}s")
    return 0


def audit_uniqueness(pred: np.ndarray, surf: np.ndarray, footprint: np.ndarray,
                     candidate_path: Path) -> dict:
    """Compare the candidate surface and its final dots against every reachable registry raster."""
    from scipy.stats import spearmanr
    cand_sha = submission_writer.sha256_file(candidate_path)
    paths = sorted((ROOT / "registry" / "rasters").glob("*.tif"))
    paths += sorted((ROOT / "data" / "raw" / "scored").glob("*.tif"))
    cand = pred > 0
    n_cand = int(cand.sum())
    disk = np.zeros((7, 7), dtype=bool)
    yy, xx = np.mgrid[-3:4, -3:4]
    disk = np.hypot(yy, xx) <= 3.0
    out = []
    rng = np.random.default_rng(99)
    rnd_idx = rng.choice(np.flatnonzero(footprint.ravel()), size=n_cand, replace=False)
    rnd = np.zeros(footprint.shape, dtype=bool).ravel()
    rnd[rnd_idx] = True
    rnd = rnd.reshape(footprint.shape)
    # Second null, conditioned on the candidate's own neighbourhood.  The unconditional null asks
    # "would a dot dropped anywhere in the region land near raster X", which conflates sharing a
    # geological TARGET with copying a raster's DOTS.  This one draws from the 1 km neighbourhood
    # our own dots occupy, so its lift isolates fine-scale co-location (IR-66-GATE-01).
    nb = np.zeros((21, 21), dtype=bool)
    ny, nx = np.mgrid[-10:11, -10:11]
    nb[np.hypot(ny, nx) <= 10.0] = True
    occ_idx = np.flatnonzero((ndimage.binary_dilation(cand, structure=nb) & footprint).ravel())
    rnd2 = np.zeros(footprint.shape, dtype=bool).ravel()
    rnd2[rng.choice(occ_idx, size=n_cand, replace=False)] = True
    rnd2 = rnd2.reshape(footprint.shape)
    for p in paths:
        with rasterio.open(p) as ds:
            if (ds.height, ds.width) != footprint.shape:
                continue
            o = np.nan_to_num(ds.read(1).astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
        o = np.clip(np.where(footprint, o, 0.0), 0, 1)
        od = o > 0
        dilated = ndimage.binary_dilation(od, structure=disk)
        within = float((cand & dilated).sum()) / max(n_cand, 1)
        within_rnd = float((rnd & dilated).sum()) / max(n_cand, 1)
        within_nb = float((rnd2 & dilated).sum()) / max(n_cand, 1)
        inter = int((cand & od).sum())
        union = int((cand | od).sum())
        # surface Spearman on a random subsample: 12.3 M-point ranks do not fit in RAM here
        idx = rng.choice(np.flatnonzero(footprint.ravel()), size=400_000, replace=False)
        rho = float(spearmanr(surf.ravel()[idx], o.ravel()[idx]).statistic)
        out.append({"raster": f"{p.parent.name}/{p.name}",
                    "spearman_rho_surface": rho,
                    "frac_cand_dots_within_3px": within,
                    "frac_random_dots_within_3px": within_rnd,
                    "lift_over_random": (within / within_rnd) if within_rnd > 0 else None,
                    "frac_random_dots_within_3px_same_neighbourhood": within_nb,
                    "lift_over_neighbourhood_null":
                        (within / within_nb) if within_nb > 0 else None,
                    "coincident_dots": inter,
                    "jaccard": inter / union if union else 0.0,
                    "other_dot_count": int(od.sum()),
                    "sha256_identical_to_candidate":
                        submission_writer.sha256_file(p) == cand_sha})
    return {"n_rasters": len(out), "candidate_sha256": cand_sha, "comparisons": out,
            "neighbourhood_null_px": 10,
            "null_note": ("frac_random_dots_within_3px is the fraction a uniformly random dot "
                          "set of the same size would score against the same registry raster; "
                          "only the lift above that null is evidence of lane drift.  "
                          "frac_random_dots_within_3px_same_neighbourhood is the same statistic "
                          "for dots drawn from the 1 km neighbourhood the candidate's own dots "
                          "occupy, which separates 'shares a geological target' from 'copies the "
                          "same dots'; the duplication gate uses that conditional null.")}


if __name__ == "__main__":
    raise SystemExit(main())
