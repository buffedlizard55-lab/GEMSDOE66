#!/usr/bin/env python3
"""E4 — Structural scan: which *designable* statistic of a dot set best predicts the owner score?

Single- and two-variable leave-one-out linear models over structural statistics that a generator
can control (dot count, catalogue prune fraction, coverage, and mass-weighted layer means).
Selection is by LOO RMSE with n=18; treat winners as design drivers, never as scores.
"""
from __future__ import annotations
import json, sys, itertools
from pathlib import Path
import numpy as np
from scipy import ndimage
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib66

fp = lib66.footprint(); cat = lib66.catalogue()
d_cat = ndimage.distance_transform_edt(~cat)
K = lib66.layer("K"); step = lib66.layer("step_max"); valid = lib66.layer("valid")
coh = lib66.layer("coh100"); sg = lib66.layer("sgmc")
scored = lib66.distinct_scored(); names = sorted(scored)
y = np.array([scored[n] for n in names])
rows = {}
cov = np.zeros(lib66.GRID, bool)
for n in names:
    d = lib66.read_registry_dots(lib66.REG / n)
    dd = ndimage.distance_transform_edt(~d)
    cov |= (dd <= 3)
    rows[n] = {
        "n_dots": float(d.sum()),
        "frac_within_2px_cat": float((d_cat[d] <= 2).mean()),
        "mean_dist_to_cat": float(d_cat[d].mean()),
        "coverage_frac": float((dd[fp] <= 3).mean()),
        "K_mean": float(K[d].mean()), "step_mean": float(step[d].mean()),
        "valid_mean": float(valid[d].mean()), "coh_mean": float(coh[d].mean()),
        "sgmc_mean": float(sg[d].mean()), "relief_mean": float(lib66.layer("relief")[d].mean()),
        "in_lidar_frac": float((valid[d] > 0).mean()),
        "mean_Kminus_fp": float(K[d].mean() - K[fp].mean()),
    }
print("union coverage of the 18 scored rasters (within 300 m):", round(float((cov[fp]).mean()), 3))
print("union coverage of the 6 best:", end=" ")
best6 = [n for n, s in sorted(scored.items(), key=lambda kv: -kv[1])[:6]]
cov6 = np.zeros(lib66.GRID, bool)
for n in best6:
    cov6 |= (ndimage.distance_transform_edt(~lib66.read_registry_dots(lib66.REG / n)) <= 3)
print(round(float((cov6[fp]).mean()), 3))
print("K percentiles inside that union:", np.percentile(K[cov6 & fp], [25, 50, 75, 90]).round(1),
      " vs footprint:", np.percentile(K[fp], [25, 50, 75, 90]).round(1))

keys = sorted(rows[names[0]])
X = np.array([[rows[n][k] for k in keys] for n in names])
print("\nsingle-variable LOO RMSE (baseline %.5f):" % np.sqrt(np.mean((y - y.mean()) ** 2)))
base = np.sqrt(np.mean((y - y.mean()) ** 2))
res = []
for i, k in enumerate(keys):
    v = X[:, i]
    # sign-flip does not matter for a single variable; report |spearman|
    from scipy.stats import spearmanr
    rho = spearmanr(v, y).statistic
    pred = np.empty(len(y))
    for j in range(len(y)):
        tr = np.ones(len(y), bool); tr[j] = False
        A = np.vstack([v[tr], np.ones(tr.sum())]).T
        c, *_ = np.linalg.lstsq(A, y[tr], rcond=None)
        pred[j] = c[0] * v[j] + c[1]
    rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
    res.append((rmse, k, float(rho)))
    print(f"  {k:22s} rho {rho:+7.3f}  LOO RMSE {rmse:.5f}")
res.sort()
best = res[0][1]
print("\ntwo-variable models containing '%s' and one other (LOO RMSE):" % best)
i0 = keys.index(best)
combos = []
for i, k in enumerate(keys):
    if i == i0:
        continue
    A = X[:, [i0, i]]
    pred = np.empty(len(y))
    for j in range(len(y)):
        tr = np.ones(len(y), bool); tr[j] = False
        M = np.hstack([A[tr], np.ones((tr.sum(), 1))])
        c, *_ = np.linalg.lstsq(M, y[tr], rcond=None)
        pred[j] = np.hstack([A[j], [1.0]]) @ c
    rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
    combos.append((rmse, k))
combos.sort()
for rmse, k in combos[:6]:
    print(f"  {best} + {k:22s} LOO RMSE {rmse:.5f}")
out = {"evidence_class": "LOCAL structural screen vs owner-reported scores (n=18); not scores",
       "union_coverage_all18": float((cov[fp]).mean()), "union_coverage_best6": float((cov6[fp]).mean()),
       "K_percentiles_union_best6": [float(v) for v in np.percentile(K[cov6 & fp], [25, 50, 75, 90])],
       "K_percentiles_footprint": [float(v) for v in np.percentile(K[fp], [25, 50, 75, 90])],
       "per_raster": rows,
       "single_variable_loo": [{"statistic": k, "rho": r, "loo_rmse": rm} for rm, k, r in res],
       "two_variable_loo": [{"model": f"{best}+{k}", "loo_rmse": rm} for rm, k in combos]}
(lib66.ROOT / "evidence66" / "e4_structure_scan.json").write_text(json.dumps(out, indent=1))
print("\nwrote evidence66/e4_structure_scan.json")
