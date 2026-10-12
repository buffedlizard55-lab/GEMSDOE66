#!/usr/bin/env python3
"""E5 — Candidate emission designs, scored on the validated structural drivers.

Validated drivers (E1/E4, n=18 owner-reported scores):
  * fewer emitted dots scores higher (rho = -0.827; LOO RMSE 0.00875 alone)
  * higher radiometric K under the dots scores higher (rho = +0.977; partial rho +0.913)
  * two-variable LOO RMSE 0.00231 against the family's 0.02490 baseline

Design space (all candidates share the validated structure: >=2 cells from the catalogue,
min separation 2 cells, footprint only, binary dots):
  support : "global" (whole eligible footprint) or "consensus" (union of the 300 m disks of the
            6 highest-scoring registry rasters, 16.9% of the footprint)
  gamma   : prior exponent rho ~ K^gamma
  N       : dot budget (cap)
The metric-marginal greedy of E3 orders candidates; the cap sets the mass.

Outputs: evidence66/e5_designs.json + dots for the selected design.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import numpy as np
from scipy import ndimage
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib66

MIN_SEP, CAT_PRUNE, R_PX = 2, 2, 3
K7 = np.clip(1.0 - np.hypot(*np.mgrid[-R_PX:R_PX + 1, -R_PX:R_PX + 1].astype(float)) / 3.0, 0, None)


def consensus_support(names, r=3):
    cov = np.zeros(lib66.GRID, bool)
    for n in names:
        d = lib66.read_registry_dots(lib66.REG / n)
        cov |= ndimage.distance_transform_edt(~d) <= r
    return cov


def emit(rho, allowed, N_cap, verbose=True):
    rho = rho.astype(np.float32)
    nu = ndimage.convolve(rho, np.ones((7, 7), np.float32), mode="constant") * 0.577
    dF = np.exp(-0.5 * nu, dtype=np.float32)
    g0 = ndimage.convolve(rho, K7.astype(np.float32), mode="constant")
    cand = np.flatnonzero((g0 > 0).ravel() & allowed.ravel())
    order = cand[np.argsort(-g0.ravel()[cand], kind="stable")]
    H, W = lib66.GRID
    c = np.zeros(lib66.GRID, np.float32); blocked = np.zeros(lib66.GRID, bool)
    g0f, dFf = g0.ravel(), dF.ravel()
    acc = []; T = 0.0; F = 0.0
    g_assumed = 60988.0
    for posi in order:
        if len(acc) >= N_cap:
            break
        if blocked.ravel()[posi]:
            continue
        if g0f[posi] * (0.8 * g_assumed + 0.2 * F) <= 0.2 * T:
            continue
        r, cc = divmod(int(posi), W)
        rr0, rr1 = max(r - R_PX, 0), min(r + R_PX + 1, H)
        cc0, cc1 = max(cc - R_PX, 0), min(cc + R_PX + 1, W)
        sub_c = c[rr0:rr1, cc0:cc1]; sub_rho = rho[rr0:rr1, cc0:cc1]
        kk = K7[rr0 - (r - R_PX):rr1 - (r - R_PX), cc0 - (cc - R_PX):cc1 - (cc - R_PX)]
        dT = float((sub_rho * np.maximum(kk - sub_c, 0.0)).sum())
        if dT <= 0.0:
            continue
        d = float(dFf[posi])
        T += dT; F += d
        np.maximum(sub_c, kk, out=sub_c)
        blocked[max(r - MIN_SEP, 0):min(r + MIN_SEP + 1, H),
                max(cc - MIN_SEP, 0):min(cc + MIN_SEP + 1, W)] = True
        acc.append((r, cc))
    dots = np.zeros(lib66.GRID, bool)
    a = np.array(acc); dots[a[:, 0], a[:, 1]] = True
    return dots, T, F


def main() -> int:
    t0 = time.time()
    fp = lib66.footprint(); cat = lib66.catalogue()
    d_cat = ndimage.distance_transform_edt(~cat)
    K = lib66.layer("K")
    allowed = fp & (d_cat >= CAT_PRUNE) & (K > 0)
    scored = lib66.distinct_scored()
    best6 = sorted(scored, key=lambda n: -scored[n])[:6]
    cons = consensus_support(best6) & allowed
    print("consensus support fraction of footprint:", round(float(cons.sum() / fp.sum()), 4))
    designs = []
    for support_name, mask in (("global", allowed), ("consensus", cons)):
        if mask.sum() == 0:
            continue
        for gamma in (0.5, 1.0):
            for ncap in (25000, 31000, 37654):
                pos = np.where(mask, np.power(np.where(mask, K, 1.0), gamma), 0.0)
                pos = np.where(d_cat >= 1.0, pos, 0.0)
                rho = np.where(mask, pos, 0.0)
                if rho.sum() <= 0:
                    continue
                rho = rho / rho.sum() * 60988.0
                dots, T, F = emit(rho, allowed | (dots0 := np.zeros(lib66.GRID, bool)), ncap)
                dmin = ndimage.distance_transform_edt(~dots)
                row = {"support": support_name, "gamma": gamma, "N_cap": ncap,
                       "n_dots": int(dots.sum()),
                       "K_mean": float(K[dots].mean()),
                       "coverage_frac": float((dmin[fp] <= 3).mean()),
                       "frac_dots_within_2px_cat": float((d_cat[dots] <= 2).mean()),
                       "T_model": T, "F_model": F,
                       "model_dti": T / (0.2 * T + 0.8 * 60988.0 + 0.2 * F)}
                designs.append(row)
                print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()})
                np.save(lib66.ROOT / "evidence66" / f"dots_{support_name}_g{gamma}_n{ncap}.npy", dots)
    (lib66.ROOT / "evidence66" / "e5_designs.json").write_text(json.dumps(
        {"evidence_class": "MODEL/DESIGN PROXY; not a score", "designs": designs,
         "runtime_s": round(time.time() - t0, 1)}, indent=1))
    print("runtime", round(time.time() - t0, 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
