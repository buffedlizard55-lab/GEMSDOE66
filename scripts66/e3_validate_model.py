#!/usr/bin/env python3
"""Model validation: does prior+published-metric reproduce the 18 owner-reported scores?

T_j = sum_x rho(x) c_j(x)   with rho = g * prior / sum(prior)   (units: expected truth cells)
F_j = sum_{x in dots_j} exp(-0.5 * nu(x)),  nu = expected truth cells in the 300 m disk
DTI_j = T_j / (0.2 T_j + 0.8 g + 0.2 F_j)

Also scores each emitted candidate under the identical model, so the candidate-vs-incumbent
comparison is apples-to-apples (and is labelled a MODEL PROXY, never a score).
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
from scipy import ndimage
from scipy.stats import spearmanr
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib66

G = 60988.0
SCALE = 60000.0
fp = lib66.footprint()
idx = np.flatnonzero(fp.ravel())
cat = lib66.catalogue()
K = lib66.layer("K").astype(np.float32)
d_cat = ndimage.distance_transform_edt(~cat).astype(np.float32)
allowed = fp & (d_cat >= 2) & (K > 0)
scored = lib66.distinct_scored()
names = sorted(scored)
y = np.array([scored[n] for n in names])
credit = np.load(lib66.ROOT / "evidence66" / "cache_credit_u16.npy")
cands = {p.stem: np.load(p) for p in sorted((lib66.ROOT / "evidence66").glob("dots_gamma*.npy"))}
out = {}
for gamma in (0.0, 0.5, 0.75, 1.0):
    pos = np.where(allowed, np.power(np.where(allowed, K, 1.0), gamma) if gamma else 1.0, 0.0)
    pos = np.where(d_cat >= 1.0, pos, 0.0)
    rho = (G * pos / pos.sum()).astype(np.float32)
    nu = ndimage.convolve(rho, np.ones((7, 7), np.float32), mode="constant") * 0.577
    dF = np.exp(-0.5 * nu, dtype=np.float32)
    wv = rho.ravel()[idx]
    T = np.array([float((wv * (credit[i] / SCALE)).sum()) for i in range(len(names))])

    def score_dots(dots):
        flat = np.flatnonzero(dots.ravel())
        p = np.clip(np.searchsorted(idx, flat), 0, idx.size - 1)
        assert np.all(idx[p] == flat)
        F = float(dF.ravel()[idx[p]].sum())
        c = lib66.credit_field(dots)
        t = float((rho.ravel()[idx] * c.ravel()[idx]).sum())
        return t, F, t / (0.2 * t + 0.8 * G + 0.2 * F)

    F = []
    for n in names:
        _, f, _ = score_dots(lib66.read_registry_dots(lib66.REG / n))
        F.append(f)
    F = np.array(F)
    dti = T / (0.2 * T + 0.8 * G + 0.2 * F)
    rho_s = float(spearmanr(dti, y).statistic)
    rmse = float(np.sqrt(np.mean((dti - y) ** 2)))
    print(f"\ngamma={gamma}: spearman(model,observed)={rho_s:+.3f} modelRMSE={rmse:.5f} (baseline {np.sqrt(np.mean((y-y.mean())**2)):.5f})")
    for n, o, m, t, f in zip(names, y, dti, T, F):
        print(f"   obs {o:.4f} model {m:.4f}  T {t:9.0f} F {f:8.0f}  {n[:50]}")
    if f"dots_gamma{gamma}" in cands:
        t, f, m = score_dots(cands[f"dots_gamma{gamma}"])
        print(f"   >>> CANDIDATE gamma={gamma}: dots {int(cands[f'dots_gamma{gamma}'].sum())} T {t:.0f} F {f:.0f} modelDTI {m:.4f}")
        out[f"candidate_gamma{gamma}"] = {"T": t, "F": f, "model_dti": m}
    out[f"gamma{gamma}"] = {"spearman": rho_s, "rmse": rmse, "model": [float(v) for v in dti],
                            "T": [float(v) for v in T], "F": [float(v) for v in F]}
out["names"] = names
out["observed"] = [float(v) for v in y]
(lib66.ROOT / "evidence66" / "e3_model_calibration.json").write_text(json.dumps(out, indent=1))
