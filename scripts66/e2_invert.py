#!/usr/bin/env python3
"""E2 — Invert the published DTI for a fault-density field, calibrated on owner-reported scores.

Model (all terms on the official 100 m grid, kernel R = 300 m = 3 cells, alpha = 0.2, beta = 0.8):

    truth density   rho(x) = g * w(x),  w propto exp(sum_k b_k z_k(x)),  w = 0 on catalogue pixels
    credit          c_j(x) = max over dots of raster j of k(d),  exact via EDT
    TPw(j)          T_j    = sum_x rho(x) c_j(x)
    FPw(j)          F_j    = sum_{x in dots_j} exp(-phi * nu(x)),   nu(x) = sum_{|y-x|<=3} rho(y)
    DTI(j)                 = T_j / (0.2 T_j + 0.8 g + 0.2 F_j)

theta = (g, b_K, b_step, b_dcat, b_valid, b_sgmc, phi) is fitted to the 18 distinct owner-reported
scores and validated leave-one-out.  A model that reproduces the observed ordering is a
*calibrated instrument*; it is not an organiser measurement.

Outputs: evidence66/e2_inversion.json, evidence66/cache_credit_u16.npy
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.optimize import least_squares

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib66  # noqa: E402

CACHE = lib66.ROOT / "evidence66" / "cache_credit_u16.npy"
OUT = lib66.ROOT / "evidence66" / "e2_inversion.json"
SCALE = 60000.0  # uint16 quantisation of the credit field


def build_design():
    fp = lib66.footprint()
    cat = lib66.catalogue()
    idx = np.flatnonzero(fp.ravel())
    d_cat = ndimage.distance_transform_edt(~cat).astype(np.float32)[fp]
    fields = {
        "K": lib66.layer("K").astype(np.float32)[fp],
        "step": lib66.layer("step_max").astype(np.float32)[fp],
        "valid": lib66.layer("valid").astype(np.float32)[fp],
        "sgmc": lib66.layer("sgmc").astype(np.float32)[fp],
        "dcat": d_cat / 10.0,
        "cat": cat.astype(np.float32)[fp],
    }
    z = {}
    for k in ("K", "step", "dcat"):
        v = fields[k]
        z[k] = (v - v.mean()) / v.std()
    z["valid"] = fields["valid"] / 255.0
    z["sgmc"] = fields["sgmc"]
    return fp, cat, idx, z


def credit_fields(fp, idx, names):
    cache = {}
    if CACHE.exists():
        arr = np.load(CACHE)
        if arr.shape == (len(names), idx.size):
            cache = {n: arr[i] for i, n in enumerate(names)}
            print(f"credit cache hit: {CACHE}")
    todo = [n for n in names if n not in cache]
    for n in todo:
        t0 = time.time()
        dots = lib66.read_registry_dots(lib66.REG / n)
        d = ndimage.distance_transform_edt(~dots)
        c = np.clip(1.0 - d / 3.0, 0.0, 1.0).astype(np.float32)[fp]
        cache[n] = np.rint(c * SCALE).astype(np.uint16).ravel()
        print(f"  credit {n[:46]:46s} {time.time()-t0:5.1f}s")
    stacked = np.stack([cache[n] for n in names])
    np.save(CACHE, stacked)
    return stacked


def predict(theta, z, credit_u16, dot_local, n_names):
    g = theta[0]
    b = theta[1:6]
    phi = theta[6]
    logw = b[0]*z["K"] + b[1]*z["step"] + b[2]*z["dcat"] + b[3]*z["valid"] + b[4]*z["sgmc"]
    logw = logw - logw.max()
    w = np.exp(logw)
    w[z["cat"] > 0] = 0.0
    Z = w.sum()
    wn = w / Z
    rho = g * wn
    # nu(x) = expected truth cells within the 300 m disk (box 7x7 scaled to the disk area)
    nu = ndimage.uniform_filter(rho.reshape(1, -1).shape and rho, size=7, mode="constant") * (282743.34 / 490000.0)
    # uniform_filter on a 1-D vector would mix rows; do it on the 2-D footprint-free grid instead
    return g, wn, rho, nu, phi, Z


def predict_scores(theta, z2d, credit_u16, dot_idx, fp):
    """Everything in 2-D grid space so that neighbourhoods are physical."""
    g = float(theta[0]); b = np.asarray(theta[1:6], float); phi = float(theta[6])
    logw = (b[0]*z2d["K"] + b[1]*z2d["step"] + b[2]*z2d["dcat"] + b[3]*z2d["valid"] + b[4]*z2d["sgmc"])
    logw = logw - logw.max()
    w = np.where(fp, np.exp(logw), 0.0)
    w[z2d["cat"] > 0] = 0.0
    wn = w / w.sum()
    rho = (g * wn).astype(np.float32)
    # expected truth cells inside the 300 m disk = disk-area-weighted local sum of rho
    box = ndimage.uniform_filter(rho, size=7, mode="constant") * 49.0
    nu = box * (282743.34 / 490000.0)
    wv = wn[fp]
    T = np.array([g * float((wv * (c / SCALE)).sum()) for c in credit_u16])
    lam = nu[fp]
    F = np.array([float(np.exp(-phi * lam[i]).sum()) for i in dot_idx])
    dti = T / (0.2 * T + 0.8 * g + 0.2 * F)
    return dti, {"T": T, "F": F, "g": g, "wn": wn, "rho": rho, "nu": nu}


def main() -> int:
    t0 = time.time()
    fp, cat, idx, z = build_design()
    scored = lib66.distinct_scored()
    names = sorted(scored)
    y = np.array([scored[n] for n in names])
    print(f"{len(names)} distinct scored rasters; footprint {idx.size}")

    credit = credit_fields(fp, idx, names)
    # 2-D versions of the design fields for neighbourhood maths
    z2d = {}
    full = {}
    for k, src in (("K", "K"), ("step", "step_max"), ("valid", "valid"), ("sgmc", "sgmc")):
        a = lib66.layer(src).astype(np.float32)
        full[k] = a
    d_cat2d = ndimage.distance_transform_edt(~cat).astype(np.float32)
    z2d["K"] = np.zeros(lib66.GRID, np.float32); z2d["K"][fp] = (full["K"][fp] - full["K"][fp].mean()) / full["K"][fp].std()
    z2d["step"] = np.zeros(lib66.GRID, np.float32); z2d["step"][fp] = (full["step"][fp] - full["step"][fp].mean()) / full["step"][fp].std()
    z2d["valid"] = (full["valid"] / 255.0).astype(np.float32)
    z2d["sgmc"] = full["sgmc"].astype(np.float32)
    z2d["dcat"] = np.zeros(lib66.GRID, np.float32); z2d["dcat"][fp] = (d_cat2d[fp] - d_cat2d[fp].mean()) / d_cat2d[fp].std()
    z2d["cat"] = cat.astype(np.float32)

    # map full-grid flat indices -> footprint-vector positions (verified, as calibrate_live.py does)
    def to_fp(flat):
        pos = np.searchsorted(idx, flat)
        pos = np.clip(pos, 0, idx.size - 1)
        assert np.all(idx[pos] == flat), "footprint index mapping failed"
        return pos

    dot_idx = []
    for n in names:
        d = lib66.read_registry_dots(lib66.REG / n)
        dot_idx.append(to_fp(np.flatnonzero(d.ravel())))
        print(f"  dots {n[:46]:46s} {d.sum():7d}")

    def resid(theta):
        dti, _ = predict_scores(theta, z2d, credit, dot_idx, fp)
        return dti - y

    theta0 = np.array([60000.0, 0.2, 0.0, 0.0, 0.0, 0.0, 0.5])
    lo = np.array([5000.0, -3.0, -3.0, -3.0, -3.0, -3.0, 0.02])
    hi = np.array([600000.0, 3.0, 3.0, 3.0, 3.0, 3.0, 20.0])
    fit = least_squares(resid, theta0, bounds=(lo, hi), xtol=1e-10, ftol=1e-10)
    theta = fit.x
    dti, info = predict_scores(theta, z2d, credit, dot_idx, fp)
    rmse = float(np.sqrt(np.mean((dti - y) ** 2)))
    print("\nfitted theta", dict(zip(["g", "bK", "bstep", "bdcat", "bvalid", "bsgmc", "phi"], theta.round(4))))
    print("RMSE (in-sample) %.5f" % rmse)

    # leave-one-out
    pred = np.empty(len(y))
    for i in range(len(y)):
        keep = np.ones(len(y), bool); keep[i] = False
        yk = y[keep]
        def r2(t):
            d, _ = predict_scores(t, z2d, credit, dot_idx, fp)
            return d[keep] - yk
        f = least_squares(r2, theta, bounds=(lo, hi), xtol=1e-9, ftol=1e-9)
        d, _ = predict_scores(f.x, z2d, credit, dot_idx, fp)
        pred[i] = d[i]
    loo = float(np.sqrt(np.mean((pred - y) ** 2)))
    base = float(np.sqrt(np.mean((y - y.mean()) ** 2)))
    print("LOO RMSE (model) %.5f  vs baseline %.5f  vs K-anchor 0.01492" % (loo, base))

    out = {
        "evidence_class": "MODEL-FIT to owner-reported scores; projections are not organiser scores",
        "model": {"kernel_range_m": 300, "alpha": 0.2, "beta": 0.8,
                  "rho": "g * softmax(b.z) with rho=0 on catalogue pixels",
                  "credit": "c_j(x)=max_dot k(d) exact via Euclidean distance transform",
                  "FPw": "sum over dots of exp(-phi * expected truth cells in the 300 m disk)"},
        "theta_names": ["g", "b_K", "b_step", "b_dcat", "b_valid", "b_sgmc", "phi"],
        "theta": [float(v) for v in theta], "rmse_in_sample": rmse, "loo_rmse": loo,
        "baseline_loo_rmse": base, "k_anchor_loo_rmse": 0.01492,
        "observed_scores": [float(v) for v in y], "predicted_scores": [float(v) for v in dti],
        "loo_predicted_scores": [float(v) for v in pred],
        "rasters": names, "runtime_s": round(time.time() - t0, 1),
        "caveats": ["n=18 non-independent rasters from one lineage",
                    "owner-reported scores, no organiser receipt or hash crosswalk",
                    "Poisson/exp(-phi nu) is an approximation of E[1-K] absorbed by phi"],
    }
    OUT.write_text(json.dumps(out, indent=1))
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
