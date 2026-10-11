"""Relief-matched holdout: does the lane beat the incumbent once the TRUTH's own relief
bias is removed?

Motivation
----------
The novelty truth (SGMC faults >300 m from the given catalogue) is not distributed like the
terrain: it is 59.3 % range front and 1.5 % basin floor, while the footprint is 25.2 % range
front and 25.6 % basin.  Mapped faults are concentrated on range fronts because scarps are
visible there, not because faults are.

Any candidate that also concentrates on range fronts therefore scores well for a reason that
has nothing to do with detector skill: it matches the *prior of the truth*.  The pooled
instrument cannot separate "better detector" from "better matched to where faults are easy to
map", and the pooled lane-vs-incumbent gap is measured under exactly that confound.

Instrument
----------
Split the footprint into three local-relief strata (basin / mid / range front) at the
footprint's own tercile boundaries.  Inside each fold:

  * allocate the 37,654-pixel budget across strata **in proportion to the stratum's share of
    the footprint** (so the candidate cannot buy score by moving mass to the stratum where
    the truth is densest),
  * emit the top pixels of the candidate field within each stratum,
  * score each stratum with the same pooled DTI (alpha 0.2, beta 0.8, 300 m kernel),
  * average the three strata with **footprint** weights.

The result is a macro-average across terrain classes: every class contributes in proportion
to how much of the board it occupies, not in proportion to how many faults happen to be
mapped in it.  It is also the number that answers the question we actually care about for a
hidden truth set, whose relief distribution is much closer to the footprint's than to SGMC's.

Both pooled (confounded) and relief-matched (de-confounded) numbers are reported side by
side, because the gap between them is the size of the confound.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gemsdoe66.features import load_stack                      # noqa: E402
from gemsdoe66.grid import footprint_mask                      # noqa: E402
from gemsdoe66.holdout import (bootstrap_ci, buffer_around,  # noqa: E402
                               fold_masks, novelty_truth, score_emission)
from gemsdoe66.grid import catalogue_mask                    # noqa: E402

N_FOLDS = 8
N_DOTS = 37_654
MIN_SEP = 2.82
CAT_PRUNE_PX = 2.0
from gemsdoe66.emission import emit as emit_field              # noqa: E402

INCUMBENT = "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif"
LANE = "gems66-lidar_lane-37654dots-20261011T214803Z-a08aa21d30ba-nan.tif"
STRATA = ("basin", "mid", "range_front")


def relief_strata():
    """Three relief classes at the footprint's own tercile boundaries."""
    fp = footprint_mask()
    stack, names, fi = load_stack()
    rel = np.full(3730 * 3292, np.nan, np.float32)
    rel[fi] = np.asarray(stack[names.index("T_relief_local")])
    rel = rel.reshape(3730, 3292)
    v = rel[fp & np.isfinite(rel)]
    lo, hi = float(np.percentile(v, 25)), float(np.percentile(v, 75))
    s = np.digitize(rel, [lo, hi]).astype(np.int8)   # 0 basin, 1 mid, 2 range front
    s[~np.isfinite(rel)] = -1
    return s, fp, float(lo), float(hi)


def emit_stratified(field, allowed, strata, budget):
    """Top-``budget`` pixels of ``field`` inside ``allowed``, budget split across the three
    relief strata in proportion to each stratum's share of ``allowed``."""
    out = np.zeros(field.shape, np.float32)
    for s in range(3):
        m = allowed & (strata == s)
        n = int(m.sum())
        if n == 0:
            continue
        share = int(round(budget * n / int(allowed.sum())))
        if share <= 0:
            continue
        idx = np.flatnonzero(m.ravel())
        vals = field.ravel()[idx]
        k = min(share, idx.size)
        if k <= 0:
            continue
        take = idx[np.argpartition(vals, -k)[-k:]]
        out.ravel()[take] = 1.0
    return out


def main() -> None:
    t0 = time.time()
    strata, fp, lo, hi = relief_strata()
    truth_all = novelty_truth()

    share_fp = [float((fp & (strata == s)).sum()) / float(fp.sum()) for s in range(3)]
    share_tr = [float((truth_all & (strata == s)).sum()) / float(truth_all.sum())
                for s in range(3)]
    print("local relief: basin <= %.2f m, range front >= %.2f m" % (lo, hi))
    print("stratum share of FOOTPRINT : " + "  ".join(
        "%s %.1f%%" % (n, 100 * v) for n, v in zip(STRATA, share_fp)))
    print("stratum share of TRUTH     : " + "  ".join(
        "%s %.1f%%" % (n, 100 * v) for n, v in zip(STRATA, share_tr)))
    print("  -> the truth is %.1fx enriched in range fronts and %.1fx depleted in basins"
          % (share_tr[2] / share_fp[2], share_fp[0] / max(share_tr[0], 1e-9)))

    with rasterio.open(ROOT / "docs" / "downloads" / LANE) as src:
        lane = np.clip(np.nan_to_num(src.read(1).astype(np.float32)), 0, 1)
    lane[~fp] = 0
    with rasterio.open(ROOT / "registry" / "rasters" / INCUMBENT) as src:
        inc = np.clip(np.nan_to_num(src.read(1).astype(np.float32)), 0, 1)
    inc[~fp] = 0

    rng = np.random.default_rng(20261011)
    rand = rng.random(lane.shape, dtype=np.float32)
    rand[~fp] = 0

    cat = catalogue_mask()
    cat_prune = buffer_around(cat, CAT_PRUNE_PX)

    pooled = {k: [] for k in ("lane", "inc", "rand")}
    matched = {k: [] for k in ("lane", "inc", "rand")}
    per_stratum = {k: {n: [] for n in STRATA} for k in ("lane", "inc", "rand")}

    for f, truth, excl in fold_masks(truth_all, N_FOLDS):
        # Emission exclusion is the 200 m catalogue prune ONLY.  The held-out fold's own
        # 300 m buffer is a *training* exclusion; applying it to emission would delete the
        # neighbourhood of the truth and force TP_w to zero (IR-66-BUG-01, re-fixed here).
        allowed = fp & ~cat_prune
        n_tr = int(truth.sum())
        if n_tr < 50:
            continue
        rec = {}
        for key, fld in (("lane", lane), ("inc", inc), ("rand", rand)):
            fld_e = np.where(np.isfinite(fld), fld, 0.0).astype(np.float32)
            fld_e = fld_e.copy()
            fld_e[~fp] = -np.inf
            pooled[key].append(
                score_emission(emit_field(fld_e, N_DOTS, fp, exclude=~allowed,
                                          min_sep_px=MIN_SEP), truth)["dti"])
            strat_pred = emit_stratified(fld_e, allowed, strata, N_DOTS)
            rec[key] = strat_pred
            parts = []
            for s in range(3):
                tm = truth & (strata == s)
                if int(tm.sum()) < 20:
                    parts.append(np.nan)
                    continue
                sub = strat_pred.copy()
                sub[strata != s] = 0.0
                parts.append(score_emission(sub, tm)["dti"])
            for n, v in zip(STRATA, parts):
                per_stratum[key][n].append(v)
            ok = [(share_fp[s], parts[s]) for s in range(3) if np.isfinite(parts[s])]
            w = sum(a for a, _ in ok)
            matched[key].append(float(sum(a * b for a, b in ok) / w))
        print("  fold %d: pooled lane %.5f inc %.5f | matched lane %.5f inc %.5f rand %.5f"
              % (f, pooled["lane"][-1], pooled["inc"][-1],
                 matched["lane"][-1], matched["inc"][-1], matched["rand"][-1]))

    def summarise(d, key):
        v = np.array([x for x in d[key] if np.isfinite(x)])
        lo_, hi_ = bootstrap_ci(v)
        return {"mean": float(v.mean()), "ci95": [lo_, hi_], "n_folds": int(v.size)}

    res = {"instrument": "HOLDOUT-DTI, novelty (SGMC off-catalogue), 8 blocked folds, "
                         "37,654 dots, alpha 0.2 beta 0.8, 300 m kernel",
           "relief_thresholds_m": {"basin_le": lo, "range_front_ge": hi},
           "stratum_share_footprint": dict(zip(STRATA, share_fp)),
           "stratum_share_truth": dict(zip(STRATA, share_tr)),
           "pooled_confounded": {k: summarise(pooled, k) for k in pooled},
           "relief_matched": {k: summarise(matched, k) for k in matched},
           "per_stratum": {k: {n: summarise(per_stratum[k], n) for n in STRATA}
                           for k in per_stratum}}
    for tag, d in (("pooled", pooled), ("matched", matched)):
        for a, b in (("lane", "inc"), ("lane", "rand")):
            dif = np.array(d[a]) - np.array(d[b])
            lo_, hi_ = bootstrap_ci(dif)
            res.setdefault("gains_" + tag, {})["%s_minus_%s" % (a, b)] = {
                "mean": float(dif.mean()), "ci95": [lo_, hi_],
                "folds_positive": int((dif > 0).sum()), "n_folds": int(dif.size)}

    print("\n%-22s %9s %9s %9s" % ("instrument", "lane", "incumbent", "random"))
    for tag, d in (("pooled (confounded)", pooled), ("relief-matched", matched)):
        print("%-22s %9.5f %9.5f %9.5f"
              % (tag, np.mean(d["lane"]), np.mean(d["inc"]), np.mean(d["rand"])))
    print()
    for tag in ("pooled", "matched"):
        for k, v in res["gains_" + tag].items():
            print("  %-8s %-16s %+.5f  CI95 [%+.5f, %+.5f]  %d/%d folds"
                  % (tag, k, v["mean"], v["ci95"][0], v["ci95"][1],
                     v["folds_positive"], v["n_folds"]))
    print("\nper-stratum DTI (footprint-weighted average = relief-matched score):")
    print("  %-12s %9s %9s %9s %9s" % ("stratum", "share_fp", "lane", "incumbent", "random"))
    for s, n in enumerate(STRATA):
        print("  %-12s %8.1f%% %9.5f %9.5f %9.5f"
              % (n, 100 * share_fp[s],
                 np.nanmean(per_stratum["lane"][n]), np.nanmean(per_stratum["inc"][n]),
                 np.nanmean(per_stratum["rand"][n])))

    gm = res["gains_matched"]["lane_minus_inc"]
    gp = res["gains_pooled"]["lane_minus_inc"]
    res["verdict"] = ("lane still wins once the relief confound is removed"
                      if gm["ci95"][0] > 0 else
                      "lane advantage does NOT survive relief matching")
    res["confound_size"] = float(gp["mean"] - gm["mean"])
    print("\n  confound size (pooled gap - matched gap) = %+.5f" % res["confound_size"])
    print("  VERDICT: %s   [%.0f s]" % (res["verdict"], time.time() - t0))

    out = ROOT / "evidence" / "relief_matched.json"
    out.write_text(json.dumps(res, indent=2))
    print("  wrote %s" % out)


if __name__ == "__main__":
    main()
