#!/usr/bin/env python3
"""Experiment 2: emission-surface candidates built from the fields measured in experiment 1.

No new supervised fits are needed - every candidate here is a combination of

* ``incumbent_blur``: the family's best-scoring raster (owner-reported 0.2778) treated as a
  *prior surface* by blurring its dot set, which estimates where that field's belief mass
  lies between its emitted dots;
* ``lidar_lane``: the lane field (multiscale Steger/Frangi/structure-tensor measures on the
  slope-detrended surface plus the 1 m-LiDAR-derived scarp descriptors);
* ``catalogue_habitat``: a supervised fit to the given catalogue.

The scientific question is whether adding an *independent* channel - the 1 m lidar scarp
evidence that the INGENIOUS mappers actually used (Giddens et al., Stanford Geothermal
Workshop 2025: "LiDAR and hillshades were utilized to identify the extent and location of
Quaternary faults") - to the family's existing prior produces a better ranking than either
alone.

Same pre-registered envelope as experiment 1: 37,654 dots, minimum separation 2.82 px,
zero dots within 200 m of the known catalogue, pooled DTI (alpha 0.2, beta 0.8, 300 m).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gemsdoe66.emission import emit  # noqa: E402
from gemsdoe66.grid import catalogue_mask, footprint_mask  # noqa: E402
from gemsdoe66.holdout import (  # noqa: E402
    bootstrap_ci, buffer_around, fold_masks, novelty_truth, score_emission,
)

OUT = ROOT / "evidence" / "experiment2_emission.json"
N_DOTS = 37_654
MIN_SEP = 2.82
CAT_PRUNE_PX = 2.0


def read01(path: Path, fp: np.ndarray) -> np.ndarray:
    with rasterio.open(path) as src:
        a = src.read(1).astype(np.float32)
    a = np.nan_to_num(a, nan=0.0)
    a[~fp] = 0.0
    return np.clip(a, 0.0, 1.0)


def rank01(a: np.ndarray, fp: np.ndarray) -> np.ndarray:
    v = np.where(fp & np.isfinite(a), a, np.nan)
    flat = v.ravel()
    ok = np.isfinite(flat)
    out = np.zeros(flat.size, np.float32)
    order = np.argsort(flat[ok], kind="stable")
    ranks = np.empty(ok.sum(), np.float32)
    ranks[order] = np.arange(ok.sum(), dtype=np.float32)
    out[ok] = ranks / max(1.0, ok.sum() - 1)
    return out.reshape(a.shape)


def main() -> int:
    t0 = time.time()
    fp = footprint_mask()
    cat = catalogue_mask()
    emit_exclude = buffer_around(cat, CAT_PRUNE_PX)

    inc = read01(ROOT / "registry" / "rasters" / "GEMSDOE32__h33-2-b2-zeros.tif", fp)
    inc_dots = inc > 0
    # prior surface: density of the incumbent's belief mass, blurred at the dot spacing
    prior = ndimage.gaussian_filter(inc_dots.astype(np.float32), 2.0, mode="constant")

    from gemsdoe66.fields import lidar_lane_field
    lane, _ = lidar_lane_field()
    lane = np.where(np.isfinite(lane), lane, 0.0).astype(np.float32)

    hab = np.load(ROOT / "data" / "processed" / "field_global_cat.npy")
    hab = np.where(np.isfinite(hab), hab, 0.0).astype(np.float32)

    r_prior = rank01(prior, fp)
    r_lane = rank01(lane, fp)
    r_hab = rank01(hab, fp)

    cands = {
        "incumbent_dots": None,                                    # verbatim control
        "prior_blur": r_prior,
        "lidar_lane": r_lane,
        "catalogue_habitat": r_hab,
        "fusion_prior50_lane50": 0.50 * r_prior + 0.50 * r_lane,
        "fusion_prior60_lane40": 0.60 * r_prior + 0.40 * r_lane,
        "fusion_prior40_lane60": 0.40 * r_prior + 0.60 * r_lane,
        "fusion_prior50_lane30_hab20": 0.50 * r_prior + 0.30 * r_lane + 0.20 * r_hab,
        "product_prior_lane": np.sqrt(np.maximum(r_prior, 0) * np.maximum(r_lane, 0)),
    }

    nov = novelty_truth(3.0)
    results = {k: {"N": [], "C": []} for k in cands}
    detail = []

    for instrument, truth_src in (("N", nov), ("C", cat)):
        for fold, truth, excl in fold_masks(truth_src, 8):
            visible = truth_src & ~excl
            for name, field in cands.items():
                if name == "incumbent_dots":
                    dots = inc_dots
                else:
                    f2 = field.astype(np.float32).copy()
                    f2[~fp] = -np.inf
                    dots = emit(f2, N_DOTS, fp, exclude=emit_exclude, min_sep_px=MIN_SEP)
                pred = dots.astype(np.float32)
                s = score_emission(pred, truth)
                ln = score_emission(pred, truth, mask_from_fp=visible)
                results[name][instrument].append(s["dti"])
                detail.append({"instrument": instrument, "fold": fold, "field": name,
                               "n_dots": int(dots.sum()), "dti": s["dti"],
                               "tpw": s["tpw"], "n_truth": s["n_truth"],
                               "lenient_dti": ln["dti"]})
            print(f"[{instrument}{fold}] " + "  ".join(
                f"{k[:14]}={results[k][instrument][-1]:.4f}" for k in cands), flush=True)

    base = np.asarray(results["incumbent_dots"]["N"])
    summary = {}
    for name in cands:
        aN = np.asarray(results[name]["N"])
        aC = np.asarray(results[name]["C"])
        d = aN - base
        lo, hi = bootstrap_ci(d)
        summary[name] = {"novelty_mean": float(aN.mean()),
                         "novelty_folds": [float(x) for x in aN],
                         "catalogue_mean": float(aC.mean()),
                         "catalogue_folds": [float(x) for x in aC],
                         "delta_vs_incumbent_mean": float(d.mean()),
                         "delta_ci95": [lo, hi],
                         "folds_positive": int((d > 0).sum()), "n_folds": int(d.size)}
    print(f"\n{'candidate':30s} {'novelty':>8} {'catalogue':>10} {'delta':>9} {'CI95':>19} folds+")
    for k in cands:
        s = summary[k]
        print(f"{k:30s} {s['novelty_mean']:8.5f} {s['catalogue_mean']:10.5f} "
              f"{s['delta_vs_incumbent_mean']:+9.5f} "
              f"[{s['delta_ci95'][0]:+.4f},{s['delta_ci95'][1]:+.4f}] "
              f"{s['folds_positive']}/{s['n_folds']}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "design": {"n_dots": N_DOTS, "min_sep_px": MIN_SEP,
                   "catalogue_prune_px": CAT_PRUNE_PX,
                   "metric": "pooled distance-weighted Tversky, alpha=0.2, beta=0.8, R=300 m",
                   "folds": "8 spatially coherent balanced folds by connected component, "
                            "300 m buffer removed from training only"},
        "summary": summary, "detail": detail,
        "runtime_s": round(time.time() - t0, 1)}, indent=1))
    print(f"\nwrote {OUT} ({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
