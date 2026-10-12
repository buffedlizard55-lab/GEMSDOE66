#!/usr/bin/env python3
"""Null controls for the H67 spatially blocked holdout.

The recipe comparison in ``scripts/h67_holdout.py`` gave three feature sets an IDENTICAL
HOLDOUT-DTI (0.0178), which is only interpretable next to a placement null.  Per IR-66-GATE-01
an overlap or gain number is meaningless without the random-placement baseline for the same
truth, budget and eligible mask.  This script measures that baseline: no model, no greedy.

  NULL-1  uniform random dots over the same eligible mask
  NULL-2  uniform random dots over the whole footprint (ignores the standoff rule)
  NULL-3  a fixed 100 m lattice over the eligible mask (spacing chosen to spend the same budget)

Usage: python3 scripts/h67_null_control.py [--instruments C,N] [--budget 45000] [--folds 2]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gems import holdout as shared_holdout          # noqa: E402
from gems import metric as official_metric          # noqa: E402
import gems67.stack as h67stack                     # noqa: E402

EVALUATOR = ("src/gems/metric.py @ arena/855725e1; vectorised == literal brute force to 3.6e-15; "
             "official worked example TPw=3.00/FNw=2.00 reproduced exactly")


def _dti(pred_bool, truth):
    tp, fp, fn = official_metric.tversky_terms(pred_bool.astype(np.float32),
                                               truth.astype(np.float32))
    return official_metric.dti_from_terms(tp, fp, fn)


def lattice(shape, eligible, budget):
    """Regular lattice clipped to the eligible mask, spacing tuned to the budget."""
    lo, hi = 1, max(shape)
    while lo < hi:
        mid = (lo + hi) // 2
        m = np.zeros(shape, bool)
        m[::mid, ::mid] = True
        m &= eligible
        if m.sum() >= budget:
            lo = mid + 1
        else:
            hi = mid
    m = np.zeros(shape, bool)
    m[::max(lo, 1), ::max(lo, 1)] = True
    return m & eligible


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instruments", default="C,N")
    ap.add_argument("--folds", type=int, default=2)
    ap.add_argument("--budget", type=int, default=45000)
    ap.add_argument("--standoff-px", type=int, default=2)
    ap.add_argument("--buffer-px", type=int, default=3)
    ap.add_argument("--reps", type=int, default=10, help="Monte Carlo repetitions per random null")
    ap.add_argument("--json", default=str(ROOT / "evidence" / "h67_null_control.json"))
    args = ap.parse_args()
    t0 = time.time()
    rng = np.random.default_rng(20261012)

    with rasterio.open(h67stack.RAW / "sample_submission.tif") as ds:
        footprint = np.isfinite(ds.read(1).astype(np.float64))
    with rasterio.open(h67stack.RAW / "labels.tif") as ds:
        catalogue = ds.read(1) == 1
    with rasterio.open(h67stack.RAW / "external" / "derived_sgmc_faults_100m_u8.tif") as ds:
        sgmc = ds.read(1) == 1
    novel_pool = sgmc & (ndimage.distance_transform_edt(~catalogue) > 3)

    pools = {"N": ("N_offcatalogue_novel", novel_pool), "C": ("C_catalogue_recover", catalogue)}
    out = {"evaluator_version": EVALUATOR, "budget": args.budget, "folds": args.folds,
           "standoff_px": args.standoff_px, "reps": args.reps, "instruments": {}}

    for key in [x.strip().upper() for x in args.instruments.split(",") if x.strip()]:
        inst, pool = pools[key]
        print(f"\n=== {inst} ===", flush=True)
        acc = {}
        held_pooled = 0
        for k_i in range(args.folds):
            sp = shared_holdout.split_fault_segments(pool, holdout_fraction=1.0 / max(args.folds, 2),
                                                     buffer_px=args.buffer_px, seed=1000 + k_i)
            truth, visible = sp["holdout"], sp["visible"]
            if truth.sum() == 0:
                continue
            held_pooled += int(truth.sum())
            eligible = footprint & (ndimage.distance_transform_edt(~visible) > args.standoff_px)
            cand = {"NULL-1_random_eligible": [], "NULL-2_random_footprint": [],
                    "NULL-3_lattice_eligible": []}

            idx = np.flatnonzero(eligible.ravel())
            lat = lattice(footprint.shape, eligible, args.budget)
            cand["NULL-3_lattice_eligible"].append(
                _dti(lat, truth))
            fidx = np.flatnonzero(footprint.ravel())
            for _ in range(args.reps):
                p = np.zeros(footprint.shape, bool)
                p.ravel()[rng.choice(idx, size=min(args.budget, idx.size), replace=False)] = True
                cand["NULL-1_random_eligible"].append(
                    _dti(p, truth))
                q = np.zeros(footprint.shape, bool)
                q.ravel()[rng.choice(fidx, size=min(args.budget, fidx.size), replace=False)] = True
                cand["NULL-2_random_footprint"].append(
                    _dti(q, truth))
            print(f"  fold {k_i}: |G|={int(truth.sum()):,} eligible={int(eligible.sum()):,} "
                  f"NULL-1={np.mean(cand['NULL-1_random_eligible']):.4f} "
                  f"NULL-2={np.mean(cand['NULL-2_random_footprint']):.4f} "
                  f"NULL-3={cand['NULL-3_lattice_eligible'][0]:.4f} ({time.time()-t0:.0f}s)",
                  flush=True)
            for k_, v in cand.items():
                acc.setdefault(k_, []).extend(v)

        out["instruments"][inst] = {
            "withheld_positive_pixels_pooled": held_pooled,
            "nulls": {k_: {"mean_dti": float(np.mean(v)), "sd_dti": float(np.std(v)),
                           "min_dti": float(np.min(v)), "max_dti": float(np.max(v)),
                           "n": len(v)} for k_, v in acc.items()},
        }

    out["wall_seconds"] = round(time.time() - t0, 1)
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(out, indent=1))
    print(f"\nwrote {args.json}  ({out['wall_seconds']}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
