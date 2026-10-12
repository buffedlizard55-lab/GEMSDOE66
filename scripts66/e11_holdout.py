#!/usr/bin/env python3
"""E11 - buffered whole-segment, lidar-covered holdout for the released candidate.

Protocol (frozen by the shared template, reused here rather than rebuilt)
------------------------------------------------------------------------
Instrument N (novelty): truth = SGMC fault pixels more than 300 m (3 px) from the given
catalogue, restricted to lidar-covered cells.  Truth components are grouped into 8 spatially
coherent, balanced folds; a fold's whole components are withheld together with a 3 px buffer.
Score = the organiser's DTI (alpha = 0.2, beta = 0.8, 300 m triangular kernel), computed
per fold and pooled.

Fields compared at the *same* budget rule used by the family: the released candidate
(32,000 dots), the owner-reported 0.2778 incumbent (37,654 dots, re-read from
registry/rasters), and a seeded uniform-dot chance control (32,000 dots).

Two instrument versions are reported and never mixed:
  * N-pooled   : fold mean of DTI over the whole lidar-covered novelty truth.
  * N-stratified: the frozen de-confounding, with one declared substitution -- the frozen
    version strata by T_relief_local from topo_10m_derived_100m_u8.tif, whose mirror carries
    no sha256/size pin (unobtainable here); this run strata by the lidar mirror's own
    L_relief band instead (dequantised, q = 1 + round(254*sqrt(x/300))).  Strata cut at the
    33.3rd/66.7th percentile of the stratifier **over the withheld truth pixels**, exactly as
    the frozen version does, and are re-weighted by lidar-covered footprint area.

Everything printed is labelled HOLDOUT-DTI with evaluator version, withheld-positive counts
and 95% percentile-bootstrap CIs over folds.  No number here is an organizer score.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts66"))

import lib66  # noqa: E402
from gemsdoe66.holdout import bootstrap_ci, fold_masks  # noqa: E402
from gemsdoe66.metric import _max_kernel, _max_kernel_from_points  # noqa: E402

OUT = ROOT / "evidence66" / "e11_holdout.json"
N_FOLDS = 8
EPS = 1e-9
ALPHA, BETA = 0.2, 0.8


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def dti_from_maxks(pred: np.ndarray, truth: np.ndarray) -> dict:
    """DTI of a prediction against truth, reusing the shared kernel helpers.

    TPw = sum_g max_x p(x)k(d(x,g));  FPw = sum_x p(x)(1 - max_g k);  FNw = |G| - TPw.
    """
    maxk_pred = _max_kernel(pred)
    ys, xs = np.nonzero(truth)
    tpw = float(maxk_pred[ys, xs].sum())
    maxk_truth = _max_kernel_from_points(np.stack([ys, xs], 1), pred.shape)
    fpw = float((pred * (1.0 - maxk_truth)).sum())
    fnw = float(truth.sum()) - tpw
    dti = tpw / (tpw + ALPHA * fpw + BETA * fnw + EPS)
    return {"dti": float(dti), "tpw": tpw, "fpw": fpw, "fnw": fnw,
            "n_truth": int(truth.sum()), "mass": float(pred.sum())}


def dequant_relief(q: np.ndarray) -> np.ndarray:
    """L_relief dequantisation: x = 300 * ((q-1)/254)^2, q == 0 -> nodata."""
    t = (q.astype(np.float32) - 1.0) / 254.0
    return np.where(q > 0, 300.0 * t * t, np.nan).astype(np.float32)


def main() -> int:
    t0 = time.time()
    fp = lib66.footprint()
    cat = lib66.catalogue()
    d_cat = ndimage.distance_transform_edt(~cat)

    with rasterio.open(ROOT / "data" / "raw" / "external" / "derived_sgmc_faults_100m_u8.tif") as s:
        sgmc = (s.read(1) > 0) & fp
    with rasterio.open(ROOT / "data" / "raw" / "external" / "lidar_scarp_features_u8.tif") as s:
        lid = s.read(12) > 0
        relief = dequant_relief(s.read(9))

    nov_all = sgmc & (d_cat > 3.0)
    nov = nov_all & lid

    # ---- fields -------------------------------------------------------------------------
    cand = np.load(ROOT / "evidence66" / "dots_final.npy").astype(np.float64)
    inc_path = next(p for p in sorted((ROOT / "registry" / "rasters").glob("GEMSDOE32__h33*"))
                    if p.suffix.lower() in (".tif", ".tiff"))
    inc = lib66.read_registry_dots(inc_path).astype(np.float64)
    rng = np.random.default_rng(20261012)
    free = np.flatnonzero((fp & lid).ravel())
    rnd = np.zeros(fp.shape, np.float64)
    rnd.ravel()[rng.choice(free, size=int(cand.sum()), replace=False)] = 1.0
    n_lid_fp = int((fp & lid).sum())

    fields = {"candidate": cand, "incumbent_0.2778": inc, "chance_uniform": rnd}
    scored = {}
    for name, f in fields.items():
        f = f.copy()
        f[~lid] = 0.0                      # scoring domain: lidar-covered cells only
        scored[name] = f
        print(f"{name}: dots={int(f.sum()):,} inside lidar coverage")

    # ---- instrument N, pooled over 8 folds ----------------------------------------------
    pooled = {}
    for name, f in scored.items():
        vals, counts = [], []
        for fold, truth, _excl in fold_masks(nov, N_FOLDS):
            r = dti_from_maxks(f, truth)
            vals.append(r["dti"])
            counts.append(r["n_truth"])
        v = np.asarray(vals)
        lo, hi = bootstrap_ci(v)
        pooled[name] = {"holdout_dti_mean_over_folds": float(v.mean()),
                        "ci95_bootstrap_over_folds": [lo, hi],
                        "n_folds": int(v.size),
                        "withheld_positives_total": int(sum(counts)),
                        "withheld_positives_per_fold": [int(c) for c in counts],
                        "per_fold_dti": [float(x) for x in v]}
        print(f"N-pooled  {name:20s} HOLDOUT-DTI {v.mean():.5f}  95% CI [{lo:.5f}, {hi:.5f}]"
              f"  truth px {sum(counts):,}")

    # ---- instrument N, relief-stratified (declared substitute stratifier) ---------------
    rv = relief[nov]
    q1, q2 = (float(np.nanpercentile(rv, 33.3)), float(np.nanpercentile(rv, 66.7)))
    strata = {"low_relief": nov & (relief <= q1),
              "mid_relief": nov & (relief > q1) & (relief <= q2),
              "high_relief (range front)": nov & (relief > q2)}
    # lidar-covered footprint weights per stratum (cells inside lidar coverage and footprint)
    bnd = np.digitize(np.nan_to_num(relief, nan=-1.0), [q1, q2])
    wt = {}
    for key, idx in (("low_relief", 0), ("mid_relief", 1), ("high_relief (range front)", 2)):
        wt[key] = float(((bnd == idx) & fp & lid & np.isfinite(relief)).sum()) / float(n_lid_fp)

    strat = {}
    for sname, truth_s in strata.items():
        strat[sname] = {"n_truth": int(truth_s.sum()), "weight_lidar_footprint": wt[sname],
                        "fields": {}}
        for name, f in scored.items():
            vals, counts = [], []
            for fold, truth, _excl in fold_masks(truth_s, N_FOLDS):
                r = dti_from_maxks(f, truth)
                vals.append(r["dti"])
                counts.append(r["n_truth"])
            v = np.asarray(vals)
            lo, hi = bootstrap_ci(v)
            strat[sname]["fields"][name] = {
                "holdout_dti_mean_over_folds": float(v.mean()),
                "ci95_bootstrap_over_folds": [lo, hi], "n_folds": int(v.size),
                "withheld_positives_total": int(sum(counts)),
                "per_fold_dti": [float(x) for x in v]}
            print(f"N-strat {sname:26s} {name:20s} HOLDOUT-DTI {v.mean():.5f} "
                  f"95% CI [{lo:.5f}, {hi:.5f}]  truth px {sum(counts):,}")

    # de-confounded footprint-weighted averages and paired differences
    def wavg(field):
        return float(sum(strat[s]["weight_lidar_footprint"]
                         * strat[s]["fields"][field]["holdout_dti_mean_over_folds"]
                         for s in strata))

    diffs = {}
    for a, b, key in (("candidate", "incumbent_0.2778", "candidate_minus_incumbent"),
                      ("candidate", "chance_uniform", "candidate_minus_chance_uniform")):
        per_stratum = {s: strat[s]["fields"][a]["holdout_dti_mean_over_folds"]
                       - strat[s]["fields"][b]["holdout_dti_mean_over_folds"] for s in strata}
        diffs[key] = {
            "pooled_fold_mean": pooled[a]["holdout_dti_mean_over_folds"]
            - pooled[b]["holdout_dti_mean_over_folds"],
            "relief_weighted": wavg(a) - wavg(b),
            "per_stratum": per_stratum}
    rf = "high_relief (range front)"
    diffs["candidate_minus_incumbent"]["range_front_only"] = (
        strat[rf]["fields"]["candidate"]["holdout_dti_mean_over_folds"]
        - strat[rf]["fields"]["incumbent_0.2778"]["holdout_dti_mean_over_folds"])
    diffs["candidate_minus_chance_uniform"]["range_front_only"] = (
        strat[rf]["fields"]["candidate"]["holdout_dti_mean_over_folds"]
        - strat[rf]["fields"]["chance_uniform"]["holdout_dti_mean_over_folds"])

    verdict = {
        "gate_question": "does the candidate's HOLDOUT-DTI gain exist and survive outside range fronts?",
        "pooled_gain_vs_incumbent": diffs["candidate_minus_incumbent"]["pooled_fold_mean"],
        "relief_weighted_gain_vs_incumbent": diffs["candidate_minus_incumbent"]["relief_weighted"],
        "range_front_only_gain_vs_incumbent": diffs["candidate_minus_incumbent"]["range_front_only"],
    }
    verdict["reading"] = (
        "POSITIVE if the relief-weighted and the pooled gains both exceed zero and the range-front-only "
        "gain is not the whole of it; NEGATIVE if a gain exists only on range fronts; INCONCLUSIVE if the "
        "signs disagree.  The CIs printed above are over folds and are the only uncertainty statement "
        "made here.")
    if (verdict["pooled_gain_vs_incumbent"] > 0 and verdict["relief_weighted_gain_vs_incumbent"] > 0
            and verdict["range_front_only_gain_vs_incumbent"] < verdict["pooled_gain_vs_incumbent"]):
        verdict["verdict"] = "POSITIVE-NOT-CONFINED-TO-RANGE-FRONTS"
    elif verdict["pooled_gain_vs_incumbent"] > 0 and verdict["relief_weighted_gain_vs_incumbent"] <= 0:
        verdict["verdict"] = "NEGATIVE-GAIN-CONFINED-TO-RANGE-FRONTS"
    elif verdict["pooled_gain_vs_incumbent"] <= 0:
        verdict["verdict"] = "NEGATIVE-NO-POOLED-GAIN"
    else:
        verdict["verdict"] = "INCONCLUSIVE"
    print("verdict:", verdict["verdict"])

    out = {
        "evidence_class": "HOLDOUT-DTI (local proxy instrument; NOT an organizer score)",
        "instrument": {
            "name": "buffered whole-segment hide-and-recover, lidar-covered",
            "folds": N_FOLDS, "fold_unit": "connected component of the truth mask",
            "buffer_px": 3.0, "alpha": ALPHA, "beta": BETA, "kernel": "300 m triangular",
            "truth": "SGMC fault pixels > 300 m (3 px) from the given catalogue, restricted to lidar-covered cells",
            "truth_px_total_all_folds": int(nov.sum()),
            "scoring_domain": "lidar-covered footprint cells only (prediction zeroed outside)",
            "declared_substitution": ("the frozen relief-stratified version strata by T_relief_local from "
                                      "topo_10m_derived_100m_u8.tif, whose mirror has no sha256/size pin and "
                                      "is absent; this run strata by the lidar mirror's own L_relief band"),
            "stratifier_cuts_m": [q1, q2],
            "evaluator_version": {"metric.py": sha256(ROOT / "src" / "gemsdoe66" / "metric.py"),
                                  "holdout.py": sha256(ROOT / "src" / "gemsdoe66" / "holdout.py")},
        },
        "fields": {name: {"n_dots": int(f.sum())} for name, f in scored.items()},
        "instrument_N_pooled": pooled,
        "instrument_N_stratified": strat,
        "differences_and_verdict": {**diffs, "verdict": verdict},
        "labels": ("every HOLDOUT-DTI here is a local proxy measurement with an evaluator version, "
                   "withheld-positive counts and 95% bootstrap CIs over 8 folds; no ORGANIZER-CONFIRMED "
                   "score exists for any field"),
        "runtime_s": round(time.time() - t0, 1),
    }
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {OUT} in {out['runtime_s']} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
