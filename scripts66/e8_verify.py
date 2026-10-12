#!/usr/bin/env python3
"""E8 — Write the candidate GeoTIFFs and run every release check available locally.

Checks: official-grid format validation (src/gems/validate_submission.py) against
sample_submission.tif; byte-hash identity against every prior raster; registry uniqueness
(Spearman and 3-px dot overlap, both directions, against all 60 registry rasters); a
spatially-blocked leakage canary for the layer the design is built on; and a NaN/range audit.
"""
from __future__ import annotations
import hashlib, json, sys, zipfile
from pathlib import Path
import numpy as np
import rasterio
from scipy import ndimage
from scipy.stats import spearmanr
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import lib66
from gems.submission_writer import write_submission, sha256_file
from gems.validate_submission import validate

SLUG = "gems66-k66-kanchor-consensus-32000-20261012T003000Z"
SUBMISSION_NAME = "GEMSDOE66-K66-kanchor-consensus-32000"
NOTE = ("GEMSDOE66 K66 | off-catalogue K^0.5-anchored consensus-support dots, metric-marginal "
        "accept, 32000 dots; local checks only")
OUTDIR = lib66.ROOT / "artifacts66" / SLUG


def auc_blocked(feature, truth, block=64, n_blocks=12, seed=0):
    """AUC of a feature for a binary truth, on held-out spatial blocks (block size in cells)."""
    rng = np.random.default_rng(seed)
    bid = (np.arange(lib66.GRID[0])[:, None] // block) * (lib66.GRID[1] // block + 1) + \
          (np.arange(lib66.GRID[1])[None, :] // block)
    ids = np.unique(bid[truth | (feature > 0)])
    held = rng.choice(ids, size=min(n_blocks, ids.size), replace=False)
    m = np.isin(bid, held) & (feature > 0)
    y = truth[m]; s = feature[m]
    if y.sum() == 0 or y.sum() == y.size:
        return None
    order = np.argsort(s)
    ranks = np.empty_like(order, float)
    ranks[order] = np.arange(1, s.size + 1)
    # average ranks for ties
    uniq, inv, cnt = np.unique(s, return_inverse=True, return_counts=True)
    csum = np.cumsum(cnt)
    avg = (csum - cnt / 2.0)
    ranks = avg[inv]
    n1 = int(y.sum()); n0 = int(y.size - n1)
    return float((ranks[y].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def main() -> int:
    fp = lib66.footprint(); cat = lib66.catalogue()
    dots = np.load(lib66.ROOT / "evidence66" / "dots_final.npy")
    pred = np.zeros(lib66.GRID, np.float32)
    pred[dots] = 1.0
    OUTDIR.mkdir(parents=True, exist_ok=True)
    ref = lib66.RAW / "sample_submission.tif"
    nan_path = OUTDIR / f"{SLUG}-nan.tif"
    rec_nan = write_submission(nan_path, pred, fp, ref, overwrite=True, name=SUBMISSION_NAME, note=NOTE)
    zeros_path = OUTDIR / f"{SLUG}-allfinite.tif"
    rec_zero = write_submission(zeros_path, np.zeros_like(pred), fp, ref, overwrite=True,
                               name=SUBMISSION_NAME, note=NOTE)
    # all-finite (zeros outside) sibling, as some families ship both encodings
    arr = np.nan_to_num(pred, nan=0.0).astype(np.float32)
    with rasterio.open(ref) as s:
        prof = s.profile.copy()
    prof.update(dtype="float32", count=1, nodata=None, compress="deflate")
    with rasterio.open(zeros_path, "w", **prof) as dst:
        dst.write(arr, 1)
        dst.update_tags(GEMS_NAME=SUBMISSION_NAME, GEMS_NOTE=NOTE, GEMS_GENERATOR="scripts66/e8_verify.py")
    rec_zero = {**rec_zero, "sha256": sha256_file(zeros_path), "encoding": "zero outside footprint"}
    rec_nan["encoding"] = "NaN outside footprint"

    report = {"slug": SLUG, "submission_name": SUBMISSION_NAME, "note": NOTE,
              "note_chars": len(NOTE), "files": {}, "checks": {}}
    for tag, p, rec in (("nan", nan_path, rec_nan), ("allfinite", zeros_path, rec_zero)):
        v_ref = validate(p, reference_path=str(ref))
        with rasterio.open(p) as src:
            a = src.read(1)
        finite = np.isfinite(a)
        report["files"][tag] = {
            "path": str(p.relative_to(lib66.ROOT)), "sha256": rec["sha256"],
            "bytes": p.stat().st_size, "dtype": str(a.dtype), "shape": list(a.shape),
            "min_finite": float(np.nanmin(a[finite])), "max_finite": float(np.nanmax(a[finite])),
            "nan_inside_footprint": int(np.isnan(a[fp]).sum()),
            "nan_outside_footprint": int(np.isnan(a[~fp]).sum()),
            "finite_outside_footprint": int(finite[~fp].sum()),
            "emitted_cells": int((a[fp] > 0).sum()),
            "validator_passed": bool(v_ref["passed"]),
            "validator_checks": {c["check"]: c["status"] for c in v_ref["checks"]},
        }
    zpath = OUTDIR / f"{SLUG}-nan.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(nan_path, arcname=nan_path.name)
    report["files"]["zip"] = {"path": str(zpath.relative_to(lib66.ROOT)), "sha256": sha256_file(zpath),
                              "contains": nan_path.name}

    # ---- byte identity against every prior raster ---------------------------------------
    mine = sha256_file(nan_path); mine_z = sha256_file(zeros_path)
    ident = []
    for p in sorted(lib66.REG.glob("*.tif")):
        h = sha256_file(p)
        if h in (mine, mine_z):
            ident.append(p.name)
    report["checks"]["byte_identical_to_prior_raster"] = ident

    # ---- registry uniqueness screen ------------------------------------------------------
    rows = []
    for p in sorted(lib66.REG.glob("*.tif")):
        try:
            o = lib66.read_registry_dots(p)
        except Exception as exc:  # pragma: no cover
            rows.append({"raster": p.name, "error": str(exc)}); continue
        if o.sum() == 0:
            continue
        dm = ndimage.distance_transform_edt(~o)
        frac = float((dm[dots] <= 3).mean())
        d2 = ndimage.distance_transform_edt(~dots)
        frac_rev = float((d2[o] <= 3).mean())
        rho = float(spearmanr(dots.astype(np.float32).ravel(), o.astype(np.float32).ravel()).statistic)
        rows.append({"raster": p.name, "frac_candidate_dots_within_3px": frac,
                     "frac_registry_dots_within_3px": frac_rev, "spearman": rho})
    rows.sort(key=lambda r: -r.get("frac_candidate_dots_within_3px", 0))
    report["checks"]["registry_screen"] = {
        "n_checked": len(rows),
        "max_frac_candidate_dots_within_3px": rows[0]["frac_candidate_dots_within_3px"] if rows else None,
        "argmax": rows[0]["raster"] if rows else None,
        "max_abs_spearman": max(abs(r.get("spearman", 0.0)) for r in rows) if rows else None,
        "argmax_spearman": max(rows, key=lambda r: abs(r.get("spearman", 0.0)))["raster"] if rows else None,
        "thresholds": {"frac_within_3px": 0.70, "abs_spearman": 0.90},
        "top10": rows[:10],
    }
    rid = report["checks"]["registry_screen"]
    rid["pass"] = bool(rows and rid["max_frac_candidate_dots_within_3px"] <= 0.70
                       and abs(rid["max_abs_spearman"]) <= 0.90)

    # ---- leakage canary ------------------------------------------------------------------
    K = lib66.layer("K").astype(np.float32)
    canary = {"layer": "K (GeoDAWN radiometric potassium, mirror band)",
              "truth": "visible catalogue (labels.tif > 0, 60,988 cells)",
              "block_px": 64, "held_blocks": 12,
              "auc_blocked_K_vs_catalogue": auc_blocked(np.where(fp, K, 0.0), cat),
              "auc_full_footprint_K_vs_catalogue": auc_blocked(np.where(fp, K, 0.0), cat, n_blocks=0),
              "threshold": 0.90}
    canary["verdict"] = ("LEAKAGE FLAG: K alone separates catalogue faults above 0.90 on held-out "
                         "blocks; treat any catalogue-based gain as leaky")
    if canary["auc_blocked_K_vs_catalogue"] is not None and canary["auc_blocked_K_vs_catalogue"] < 0.90:
        canary["verdict"] = "pass (<0.90): K does not re-find the catalogue faults on held-out blocks"
    report["checks"]["leakage_canary"] = canary

    (lib66.ROOT / "evidence66" / "e8_verify.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
