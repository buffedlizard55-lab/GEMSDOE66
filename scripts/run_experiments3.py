#!/usr/bin/env python3
"""Experiment 3: chance level, the surface duplicate check, and the mass sweep.

Two things experiment 1 could not answer on its own:

1. **Is 0.07 DTI actually better than chance?**  The metric charges 0.2 per emitted pixel, so
   a *random* sparse dot set already earns a non-zero score against a small truth set.  We
   measure that baseline directly with the identical budget and geometry.
2. **Does the lane field beat the incumbent because of the field or because of the budget?**
   We sweep the emitted mass for the lane field and for the incumbent's own prior surface.

Also runs the *surface* duplicate gate the parallel-run protocol asks for ("on the surface
before placement AND on the final dots").
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
from gemsdoe66.uniqueness import check_registry  # noqa: E402

OUT = ROOT / "evidence" / "experiment3_controls.json"
MIN_SEP = 2.82
MASSES = [20_000, 30_000, 37_654, 45_000, 60_000]


def read01(path: Path, fp: np.ndarray) -> np.ndarray:
    with rasterio.open(path) as src:
        a = src.read(1).astype(np.float32)
    a = np.nan_to_num(a, nan=0.0)
    a[~fp] = 0.0
    return np.clip(a, 0.0, 1.0)


def main() -> int:
    t0 = time.time()
    fp = footprint_mask()
    cat = catalogue_mask()
    exclude = buffer_around(cat, 2.0)
    nov = novelty_truth(3.0)

    from gemsdoe66.fields import lidar_lane_field
    lane, parts = lidar_lane_field()
    lane = np.where(np.isfinite(lane), lane, 0.0).astype(np.float32)
    np.save(ROOT / "data" / "processed" / "field_lidar_lane.npy", lane)
    print("saved the lane field")

    rng = np.random.default_rng(7)
    cand = np.flatnonzero((fp & ~exclude).ravel())
    rnd = np.zeros(fp.shape, np.float32)
    rnd.flat[cand] = rng.random(cand.size).astype(np.float32)

    inc = read01(ROOT / "registry" / "rasters" / "GEMSDOE32__h33-2-b2-zeros.tif", fp)
    prior = ndimage.gaussian_filter((inc > 0).astype(np.float32), 2.0, mode="constant")

    out = {"chance": {}, "mass_sweep": {}, "surface_gate": None}

    # ---- 1. chance level on the novelty instrument ---------------------------------------
    lane_f = lane.copy(); lane_f[~fp] = -np.inf
    rnd_f = rnd.copy(); rnd_f[~fp] = -np.inf
    prior_f = prior.copy(); prior_f[~fp] = -np.inf
    acc = {"random": [], "lidar_lane": [], "incumbent_prior": []}
    for fold, truth, excl in fold_masks(nov, 8):
        for name, fld in (("random", rnd_f), ("lidar_lane", lane_f),
                          ("incumbent_prior", prior_f)):
            dots = emit(fld, 37_654, fp, exclude=exclude, min_sep_px=MIN_SEP)
            acc[name].append(score_emission(dots.astype(np.float32), truth)["dti"])
        print(f"  fold {fold}: random={acc['random'][-1]:.5f} "
              f"lane={acc['lidar_lane'][-1]:.5f} prior={acc['incumbent_prior'][-1]:.5f}",
              flush=True)
    for k, v in acc.items():
        a = np.asarray(v)
        lo, hi = bootstrap_ci(a)
        out["chance"][k] = {"mean": float(a.mean()), "ci95": [lo, hi],
                            "folds": [float(x) for x in a]}
    d = np.asarray(acc["lidar_lane"]) - np.asarray(acc["random"])
    lo, hi = bootstrap_ci(d)
    out["chance"]["lane_minus_random"] = {"mean": float(d.mean()), "ci95": [lo, hi],
                                          "folds_positive": int((d > 0).sum())}
    print(f"lane - random: {d.mean():+.5f} CI95 [{lo:+.5f},{hi:+.5f}] "
          f"{int((d>0).sum())}/8 folds")

    # ---- 2. mass sweep --------------------------------------------------------------------
    for n in MASSES:
        row = {}
        for name, fld in (("lidar_lane", lane_f), ("incumbent_prior", prior_f)):
            vals = []
            for fold, truth, excl in fold_masks(nov, 8):
                dots = emit(fld, n, fp, exclude=exclude, min_sep_px=MIN_SEP)
                vals.append(score_emission(dots.astype(np.float32), truth)["dti"])
            a = np.asarray(vals)
            lo, hi = bootstrap_ci(a)
            row[name] = {"mean": float(a.mean()), "ci95": [lo, hi]}
        out["mass_sweep"][str(n)] = row
        print(f"  n={n:6,}: lane={row['lidar_lane']['mean']:.5f} "
              f"prior={row['incumbent_prior']['mean']:.5f}", flush=True)

    # ---- 3. surface duplicate gate --------------------------------------------------------
    gate = check_registry(lane, ROOT / "registry" / "rasters", fp)
    out["surface_gate"] = {k: gate[k] for k in
                           ("verdict", "reason", "max_abs_spearman_rho", "argmax_rho",
                            "max_frac_dots_within_3px", "max_lift_over_random",
                            "argmax_lift", "n_compared")}
    print(f"\n[surface gate] {gate['verdict']}: {gate['reason']}")
    print(f"   max |rho| = {gate['max_abs_spearman_rho']:.4f} ({gate['argmax_rho']})")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"design": {
        "instrument": "novelty (SGMC off-catalogue), 8 blocked folds",
        "min_sep_px": MIN_SEP, "catalogue_prune_px": 2.0,
        "metric": "pooled distance-weighted Tversky alpha=0.2 beta=0.8 R=300 m"},
        **out, "runtime_s": round(time.time() - t0, 1)}, indent=1))
    print(f"\nwrote {OUT} ({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
