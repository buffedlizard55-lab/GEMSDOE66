#!/usr/bin/env python3
"""E1 — Which observable layer explains the owner-reported score, once emission geometry is removed?

Reproduces scripts/calibrate_live.py and scripts/calibrate_partial.py on the sha256-pinned
*uint8 mirror* layers (the 59-layer CI stack is not in this checkout), then adds the 12 lidar
scarp-descriptor bands.  Nuisance controls are the same two used by calibrate_partial.py:
fraction of dots within 200 m of the known catalogue, and number of emitted dots.

Output: evidence66/e1_layer_scan.json  (every number inside is a LOCAL correlation vs
owner-reported scores, never an organiser score).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib66  # noqa: E402

OUT = lib66.ROOT / "evidence66" / "e1_layer_scan.json"
LAYERS = ["K", "Th", "U", "TC", "ThK", "UK", "UTh", "TMI", "sgmc",
          "ex_max", "ex_mean", "step_max", "lapneg_max", "lappos_max",
          "downface_max", "upface_max", "cross_max", "relief", "coh100", "strike", "valid"]


def rankdata(x):
    return np.argsort(np.argsort(x))


def partial_spearman(x, y, controls):
    """Spearman between x and y after regressing both on the rank-transformed controls."""
    rx, ry = rankdata(x).astype(float), rankdata(y).astype(float)
    A = np.column_stack([rankdata(c).astype(float) for c in controls] + [np.ones(len(x))])
    bx, *_ = np.linalg.lstsq(A, rx, rcond=None)
    by, *_ = np.linalg.lstsq(A, ry, rcond=None)
    return float(spearmanr(rx - A @ bx, ry - A @ by).statistic)


def main() -> int:
    t0 = time.time()
    fp = lib66.footprint()
    cat = lib66.catalogue()
    dist_cat = ndimage.distance_transform_edt(~cat)
    scored = lib66.distinct_scored()

    dots, y, names = {}, [], []
    for name, score in scored.items():
        d = lib66.read_registry_dots(lib66.REG / name)
        dots[name] = d
        y.append(score)
        names.append(name)
    y = np.asarray(y, dtype=float)

    ndots = np.array([float(dots[n].sum()) for n in names])
    frac_near = np.array([float((dist_cat[dots[n]] <= 2).mean()) for n in names])
    w = {n: dots[n].sum() for n in names}

    rows = []
    rng = np.random.default_rng(0)
    for lay in LAYERS:
        a = lib66.layer(lay)
        means = np.array([float(a[dots[n]].mean()) for n in names])
        ok = np.isfinite(means)
        rho = float(spearmanr(means[ok], y[ok]).statistic)
        null = np.array([spearmanr(means[ok], rng.permutation(y[ok])).statistic for _ in range(2000)])
        p = float((np.abs(null) >= abs(rho) - 1e-12).mean())
        rho_p = partial_spearman(means[ok], y[ok], [frac_near[ok], ndots[ok]])
        # LOO linear prediction error of the score from this layer alone
        v = means.copy(); v[~np.isfinite(v)] = np.nanmedian(v)
        pred = np.empty(len(y))
        for i in range(len(y)):
            tr = np.ones(len(y), bool); tr[i] = False
            A = np.vstack([v[tr], np.ones(tr.sum())]).T
            c, *_ = np.linalg.lstsq(A, y[tr], rcond=None)
            pred[i] = c[0] * v[i] + c[1]
        rows.append({"layer": lay, "mean_at_dots": [float(m) for m in means],
                     "footprint_mean": float(a[fp].mean()), "rho_raw": rho, "p_perm": p,
                     "rho_partial_two_controls": rho_p,
                     "rho_vs_frac_near_catalogue": float(spearmanr(means, frac_near).statistic),
                     "rho_vs_n_dots": float(spearmanr(means, ndots).statistic),
                     "loo_rmse_score_from_layer": float(np.sqrt(np.mean((pred - y) ** 2)))})
    rows.sort(key=lambda r: -abs(r["rho_partial_two_controls"]))
    base = float(np.sqrt(np.mean((y - y.mean()) ** 2)))

    out = {
        "evidence_class": "LOCAL-CORRELATION-vs-OWNER-REPORTED-SCORES; not an organiser score",
        "method": ("Spearman of layer mean under a raster's mass-weighted dots vs the raster's "
                   "owner-reported live score, over distinct scored registry rasters; partial "
                   "version removes the ranks of (frac of dots within 200 m of catalogue, n dots)"),
        "n_rasters": len(names), "rasters": names, "scores": [float(v) for v in y],
        "n_dots": [int(v) for v in ndots], "frac_dots_within_200m_of_catalogue": [float(v) for v in frac_near],
        "baseline_loo_rmse_predict_mean": base,
        "layers": rows,
        "caveats": ["owner-reported scores are not organiser receipts and no hash-to-score crosswalk exists",
                    "the rasters share one lineage, so a layer can track a hidden shared cause",
                    "n = 18; use as a lane prior, never as a score"],
        "runtime_s": round(time.time() - t0, 1),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))
    print(f"{'layer':14s} {'rho_raw':>8} {'rho_part':>9} {'loo_rmse':>9} {'mean_at_dots':>13} {'fp_mean':>8}")
    for r in rows:
        print(f"{r['layer']:14s} {r['rho_raw']:+8.3f} {r['rho_partial_two_controls']:+9.3f} "
              f"{r['loo_rmse_score_from_layer']:9.5f} {np.mean(r['mean_at_dots']):13.2f} {r['footprint_mean']:8.2f}")
    print(f"baseline (predict the mean) LOO RMSE = {base:.5f}")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
