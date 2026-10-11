#!/usr/bin/env python3
"""Relief gate: does removing mass from ground where a scarp cannot survive help?

Measured in ``check_range_fronts.py``: the lane field's gain over chance is +0.033 on
high-relief range fronts (8/8 folds), +0.015 on mid relief (7/8) and **-0.003 on basin
floors** (4/8).  That is not a defect of the detector, it is the physics: a tectonic scarp
does not survive aggradation on an active basin floor, so there is nothing for a scarp
channel to see there - while every emitted pixel still costs alpha = 0.2.

The engineering consequence is the one thing the metric rewards: **do not spend mass where
the method cannot work**.  This script measures four relief gates and reports the pooled
novelty DTI of each at the identical 37,654-dot budget.
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

OUT = ROOT / "evidence" / "relief_gate.json"
N_DOTS, MIN_SEP = 37_654, 2.82


def main() -> int:
    fp = footprint_mask()
    cat = catalogue_mask()
    cat_ex = buffer_around(cat, 2.0)
    nov = novelty_truth(3.0)

    stack, names, fi = load_stack()
    j = names.index("T_relief_local")
    relief = np.full(3730 * 3292, np.nan, np.float32)
    relief[fi] = np.asarray(stack[j])
    relief = relief.reshape(3730, 3292)
    rv = relief[fp & np.isfinite(relief)]
    cuts = {p: float(np.percentile(rv, p)) for p in (10, 20, 33, 50)}
    print("footprint relief percentiles (m):",
          {k: round(v, 2) for k, v in cuts.items()})

    lane = np.load(ROOT / "data" / "processed" / "field_lidar_lane.npy")
    lane[~fp] = -np.inf

    gates = {
        "none": np.ones(fp.shape, bool),
        "relief>p10": ~np.isfinite(relief) | (relief > cuts[10]),
        "relief>p20": ~np.isfinite(relief) | (relief > cuts[20]),
        "relief>p33": ~np.isfinite(relief) | (relief > cuts[33]),
        "relief>p50": ~np.isfinite(relief) | (relief > cuts[50]),
    }
    res = {}
    for gname, keep in gates.items():
        excl = cat_ex | (~keep & fp)
        vals = []
        for fold, truth, ectx in fold_masks(nov, 8):
            dots = emit(lane, N_DOTS, fp, exclude=excl, min_sep_px=MIN_SEP)
            vals.append(score_emission(dots.astype(np.float32), truth)["dti"])
        a = np.asarray(vals)
        lo, hi = bootstrap_ci(a)
        res[gname] = {"mean": float(a.mean()), "ci95": [lo, hi],
                      "folds": [float(x) for x in a],
                      "excluded_px": int((cat_ex | (~keep & fp)).sum())}
        print(f"  {gname:12s} mean={a.mean():.5f} CI[{lo:+.5f},{hi:+.5f}]  "
              f"excluded={res[gname]['excluded_px']:,} px", flush=True)

    best = max(res, key=lambda k: res[k]["mean"])
    print(f"\nbest gate: {best} ({res[best]['mean']:.5f}) vs none ({res['none']['mean']:.5f})")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"n_dots": N_DOTS, "min_sep_px": MIN_SEP,
                               "footprint_relief_percentiles_m": cuts,
                               "gates": res, "best": best}, indent=1))
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
