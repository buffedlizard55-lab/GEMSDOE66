#!/usr/bin/env python3
"""E3 — K-anchored, metric-marginal dot emission.

Design (pre-registered in registry66/preregistration-k66.json):
  * prior        rho(x) = g * K^gamma / sum(K^gamma) over cells that are inside the footprint and
                 outside a 1-cell catalogue buffer.  rho = 0 on the catalogue itself, because the
                 scored truth is stated to be *outside* the public USGS database.
  * objective    the published DTI, not a proxy.  A dot at x is accepted only when the exact
                 first-order condition of DTI holds while the running totals T (credit earned)
                 and F (unpenalised mass) are updated:
                     dT * (0.8 g + 0.2 F) > 0.2 T dF
  * structure    min separation 2 cells (200 m, the validated d2 family), >= 2 cells from the
                 catalogue (validated B=2 prune), footprint-only.
  * gamma        fault-density exponent; gamma=0 is the uniform null, gamma=1 the anchored prior.

Outputs: evidence66/e3_emission_gamma{gamma}.json + the accepted dot coordinates.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib66  # noqa: E402

MIN_SEP_PX = 2
CAT_PRUNE_PX = 2
G_TRUTH = 60988.0        # operating truth-mass scale = visible catalogue size (stated assumption)
E1K_SCALE = 0.5          # E[1-K] = exp(-E1K_SCALE * expected truth cells in the 300 m disk)


def kernel7() -> np.ndarray:
    yy, xx = np.mgrid[-3:4, -3:4]
    k = np.clip(1.0 - np.hypot(yy, xx) / 3.0, 0.0, None)
    return k


def run(gamma: float, verbose: bool = True):
    t0 = time.time()
    fp = lib66.footprint()
    cat = lib66.catalogue()
    K = lib66.layer("K").astype(np.float32)
    d_cat = ndimage.distance_transform_edt(~cat).astype(np.float32)

    allowed = fp & (d_cat >= CAT_PRUNE_PX) & (K > 0)
    # prior
    pos = np.where(allowed, K, 0.0).astype(np.float64)
    if gamma != 1.0:
        pos = np.where(allowed, np.power(np.where(allowed, K, 1.0), gamma), 0.0)
    # catalogue pixels are excluded from the truth field itself (1-cell buffer for digitising slop)
    pos = np.where(d_cat >= 1.0, pos, 0.0)
    rho = G_TRUTH * pos / pos.sum()
    if verbose:
        print(f"gamma={gamma}  prior support cells {int((rho>0).sum())}  sum rho {rho.sum():.0f}")

    k7 = kernel7()
    # expected truth cells inside the 300 m disk (analytic disk area / 7x7 box area = 0.577)
    nu = ndimage.convolve(rho.astype(np.float32), np.ones((7, 7), np.float32), mode="constant") * 0.577
    dF = np.exp(-E1K_SCALE * nu, dtype=np.float32)          # E[1-K] at a dot placed on x
    g0 = ndimage.convolve(rho.astype(np.float32), k7.astype(np.float32), mode="constant")  # dT upper bound

    cand = np.flatnonzero((np.asarray(g0) > 0).ravel() & allowed.ravel())
    order = cand[np.argsort(-np.asarray(g0).ravel()[cand], kind="stable")]
    if verbose:
        print(f"  candidates {order.size}  ({time.time()-t0:.1f}s)")

    c = np.zeros(lib66.GRID, np.float32)     # current credit field
    blocked = np.zeros(lib66.GRID, bool)     # min-separation bookkeeping
    dFf = dF.ravel(); g0f = np.asarray(g0).ravel(); rhof = rho.astype(np.float32).ravel()
    kflat = k7.ravel()
    H, W = lib66.GRID
    accepted = []
    T = 0.0
    F = 0.0
    r_px = 3
    idx_cache = np.arange(-r_px, r_px + 1)
    for posi in order:
        if blocked.ravel()[posi]:
            continue
        if g0f[posi] * (0.8 * G_TRUTH + 0.2 * F) <= 0.2 * T:
            continue                      # conservative skip: dT<=g0 and dF<=1
        r, cc = divmod(int(posi), W)
        r0, r1 = r - r_px, r + r_px + 1
        c0, c1 = cc - r_px, cc + r_px + 1
        # clip windows at the array edge (a dot near the border simply sees a smaller window)
        rr0, rr1 = max(r0, 0), min(r1, H)
        cc0, cc1 = max(c0, 0), min(c1, W)
        sub_c = c[rr0:rr1, cc0:cc1]
        sub_rho = rho[rr0:rr1, cc0:cc1]
        kk = k7[rr0 - r0:rr1 - r0, cc0 - c0:cc1 - c0]
        new = np.maximum(kk - sub_c, 0.0)
        dT = float((sub_rho * new).sum())
        if dT <= 0.0:
            continue
        d = float(dFf[posi])
        if dT * (0.8 * G_TRUTH + 0.2 * F) > 0.2 * T * d:
            T += dT
            F += d
            np.maximum(sub_c, kk, out=sub_c)
            r2 = MIN_SEP_PX
            br0, br1 = max(r - r2, 0), min(r + r2 + 1, H)
            bc0, bc1 = max(cc - r2, 0), min(cc + r2 + 1, W)
            blocked[br0:br1, bc0:bc1] = True
            accepted.append((int(r), int(cc)))

    dt = time.time() - t0
    dti = T / (0.2 * T + 0.8 * G_TRUTH + 0.2 * F) if T > 0 else 0.0
    dots = np.zeros(lib66.GRID, bool)
    if accepted:
        a = np.array(accepted)
        dots[a[:, 0], a[:, 1]] = True
    kmean = float(K[dots].mean()) if dots.any() else float("nan")
    cover = float((ndimage.distance_transform_edt(~dots)[fp] <= 3).mean())
    out = {
        "gamma": gamma, "min_sep_px": MIN_SEP_PX, "cat_prune_px": CAT_PRUNE_PX,
        "g_truth_assumed": G_TRUTH, "e1k_scale": E1K_SCALE,
        "n_dots": int(dots.sum()), "T_model": T, "F_model": F, "model_dti": dti,
        "k_mean_at_dots": kmean, "footprint_mean_K": float(K[fp].mean()),
        "coverage_within_300m_frac_of_footprint": cover,
        "frac_dots_within_2px_catalogue": float((d_cat[dots] <= 2).mean()) if dots.any() else None,
        "runtime_s": round(dt, 1),
        "evidence_class": "MODEL PROXY (rho~K^gamma, assumed g); not a score",
    }
    if verbose:
        print(json.dumps(out, indent=1))
    return dots, out


if __name__ == "__main__":
    gammas = [float(x) for x in sys.argv[1:]] or [0.0, 0.5, 1.0]
    for g in gammas:
        dots, info = run(g)
        np.save(lib66.ROOT / "evidence66" / f"dots_gamma{g}.npy", dots)
        (lib66.ROOT / "evidence66" / f"e3_emission_gamma{g}.json").write_text(json.dumps(info, indent=1))
