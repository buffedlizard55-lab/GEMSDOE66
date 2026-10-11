#!/usr/bin/env python3
"""Range-front stratification of the novelty holdout.

The gate for this lane is a DTI gain "that is not confined to range fronts".  A scarp
detector that simply re-discovers range-front escarpments would pass a pooled holdout while
adding nothing the catalogue lacks, because range fronts are exactly where the catalogue
already has faults.  We therefore split the held-out SGMC off-catalogue truth by **local
relief** (the 10 m-DEM-derived ``T_relief_local`` channel, a standard range-front proxy) and
report the lane field's gain over a chance-level control separately in each stratum.

Strata are defined by relief terciles computed over the truth pixels themselves, so each
stratum carries comparable truth mass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gemsdoe66.emission import emit  # noqa: E402
from gemsdoe66.features import load_stack  # noqa: E402
from gemsdoe66.grid import catalogue_mask, footprint_mask  # noqa: E402
from gemsdoe66.holdout import (  # noqa: E402
    bootstrap_ci, buffer_around, fold_masks, novelty_truth, score_emission,
)

OUT = ROOT / "evidence" / "range_front_stratification.json"
N_DOTS, MIN_SEP = 37_654, 2.82


def main() -> int:
    fp = footprint_mask()
    cat = catalogue_mask()
    exclude = buffer_around(cat, 2.0)
    nov = novelty_truth(3.0)

    stack, names, fi = load_stack()
    j = names.index("T_relief_local")
    relief = np.full(3730 * 3292, np.nan, np.float32)
    relief[fi] = np.asarray(stack[j])
    relief = relief.reshape(3730, 3292)

    lane = np.load(ROOT / "data" / "processed" / "field_lidar_lane.npy")
    lane[~fp] = -np.inf
    rng = np.random.default_rng(7)
    cand = np.flatnonzero((fp & ~exclude).ravel())
    rnd = np.zeros(fp.shape, np.float32)
    rnd.flat[cand] = rng.random(cand.size).astype(np.float32)
    rnd[~fp] = -np.inf

    # relief terciles over the truth pixels
    rv = relief[nov]
    q1, q2 = np.nanpercentile(rv, 33.3), np.nanpercentile(rv, 66.7)
    strata = {
        "low_relief (basin floor / pediment)": nov & (relief <= q1),
        "mid_relief": nov & (relief > q1) & (relief <= q2),
        "high_relief (range front)": nov & (relief > q2),
    }
    print(f"relief tercile cuts: {q1:.2f} m, {q2:.2f} m")
    for k, v in strata.items():
        print(f"  {k:38s} {int(v.sum()):,} truth px")

    res = {}
    for sname, smask in strata.items():
        vals = {"lane": [], "random": []}
        for fold, truth, excl in fold_masks(nov, 8):
            t = truth & smask
            if t.sum() < 50:
                continue
            for nm, fld in (("lane", lane), ("random", rnd)):
                dots = emit(fld, N_DOTS, fp, exclude=exclude, min_sep_px=MIN_SEP)
                vals[nm].append(score_emission(dots.astype(np.float32), t)["dti"])
        a = np.asarray(vals["lane"])
        b = np.asarray(vals["random"])
        d = a - b
        lo, hi = bootstrap_ci(d)
        res[sname] = {"n_folds": int(a.size), "lane_mean": float(a.mean()),
                      "random_mean": float(b.mean()), "gain": float(d.mean()),
                      "gain_ci95": [lo, hi], "folds_positive": int((d > 0).sum())}
        print(f"  {sname:38s} lane={a.mean():.5f} chance={b.mean():.5f} "
              f"gain={d.mean():+.5f} CI[{lo:+.5f},{hi:+.5f}] {int((d>0).sum())}/{a.size}",
              flush=True)

    gains = [v["gain"] for v in res.values()]
    verdict = "PASS" if all(g > 0 for g in gains) else "FAIL"
    print(f"\nverdict: {verdict} — gain positive in {sum(g > 0 for g in gains)}/{len(gains)} strata")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"relief_terciles_m": [float(q1), float(q2)],
                               "strata": res, "verdict": verdict}, indent=1))
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
