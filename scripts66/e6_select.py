#!/usr/bin/env python3
"""E6 — Hedged design variants + pre-registered selection + registry uniqueness screen.

Hedge rule: keep the incumbent's coverage, tilt the *density* toward K.  After the metric-marginal
K-preferential pass, add dots at the highest-K cells of the still-uncovered consensus support until
coverage >= the incumbent's or the dot budget is spent.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import numpy as np
from scipy import ndimage
from scipy.stats import spearmanr
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib66
from e5_design import consensus_support, emit, MIN_SEP, CAT_PRUNE, R_PX

OUT = lib66.ROOT / "evidence66"


def add_coverage_dots(dots, mask, K, budget, coverage_target, fp, chunk=200):
    """Greedily add dots on the highest-K uncovered cells of *mask* (blocked-mask bookkeeping).

    A full-grid Euclidean distance transform is recomputed only every ``chunk`` insertions, so the
    loop costs a few seconds rather than one transform per dot.
    """
    d = dots.copy()
    dmin = ndimage.distance_transform_edt(~d)
    H, W = lib66.GRID
    st = np.ones((2 * MIN_SEP + 1, 2 * MIN_SEP + 1), bool)
    added = 0
    while d.sum() < budget:
        cov = float((dmin[fp] <= 3).mean())
        if cov >= coverage_target:
            break
        blocked = ndimage.binary_dilation(d, structure=st)
        cand = mask & ~blocked & (dmin > R_PX)
        if not cand.any():
            break
        vals = np.where(cand, K, -1.0)
        order = np.argsort(-vals.ravel(), kind="stable")[:chunk]
        order = [int(i) for i in order if vals.ravel()[i] > 0]
        if not order:
            break
        for flat in order:
            r, c = divmod(flat, W)
            if blocked[r, c] or d.sum() >= budget:
                continue
            d[r, c] = True
            added += 1
            blocked[max(r - MIN_SEP, 0):min(r + MIN_SEP + 1, H),
                    max(c - MIN_SEP, 0):min(c + MIN_SEP + 1, W)] = True
        dmin = ndimage.distance_transform_edt(~d)
    print(f"   coverage hedge added {added} dots -> coverage "
          f"{float((dmin[fp] <= 3).mean()):.4f}", flush=True)
    return d


def screen_unique(dots):
    out = []
    for p in sorted(lib66.REG.glob("*.tif")):
        try:
            o = lib66.read_registry_dots(p)
        except Exception:
            continue
        if o.sum() == 0:
            continue
        dmin = ndimage.distance_transform_edt(~o)
        frac = float((dmin[dots] <= 3).mean())
        d2 = ndimage.distance_transform_edt(~dots)
        frac_rev = float((d2[o] <= 3).mean())
        a = dots.astype(np.float32).ravel(); b = o.astype(np.float32).ravel()
        rho = float(spearmanr(a, b).statistic)
        out.append({"raster": p.name, "frac_of_candidate_dots_within_3px": frac,
                    "frac_of_registry_dots_within_3px": frac_rev, "spearman_full_footprint": rho})
    out.sort(key=lambda r: -r["frac_of_candidate_dots_within_3px"])
    return out


def main() -> int:
    t0 = time.time()
    fp = lib66.footprint(); cat = lib66.catalogue()
    d_cat = ndimage.distance_transform_edt(~cat)
    K = lib66.layer("K")
    allowed = fp & (d_cat >= CAT_PRUNE) & (K > 0)
    scored = lib66.distinct_scored()
    best6 = sorted(scored, key=lambda n: -scored[n])[:6]
    cons = consensus_support(best6) & allowed
    n_incumbent = 37654
    cov_incumbent = 0.1508
    print(f"consensus support {cons.sum()} cells ({cons.sum()/fp.sum():.4f} of footprint)", flush=True)

    variants = {}
    # A: K-preferential density inside the consensus support, then a coverage hedge
    for gamma, budget in ((0.35, 31000), (0.5, 31000), (0.5, 37654)):
        pos = np.where(cons, np.power(np.where(cons, K, 1.0), gamma), 0.0)
        pos = np.where(d_cat >= 1.0, pos, 0.0)
        rho = pos / pos.sum() * 60988.0
        dots, T, F = emit(rho, allowed, budget)
        hedged = add_coverage_dots(dots, cons, K, n_incumbent, cov_incumbent, fp)
        key = f"consensus_g{gamma}_n{budget}_hedged"
        variants[key] = hedged
        print(f"{key}: {int(hedged.sum())} dots, K {K[hedged].mean():.1f}, "
              f"cov {(ndimage.distance_transform_edt(~hedged)[fp] <= 3).mean():.4f}")
    # B: incumbent-structure control (global uniform prior, no cap change) -- sanity reference
    pos = np.where(allowed, 1.0, 0.0)
    rho = pos / pos.sum() * 60988.0
    dots, T, F = emit(rho, allowed, 40000)
    variants["control_uniform_40k"] = dots

    rows = {}
    for k, d in variants.items():
        dmin = ndimage.distance_transform_edt(~d)
        rows[k] = {"n_dots": int(d.sum()), "K_mean": float(K[d].mean()),
                   "coverage_frac": float((dmin[fp] <= 3).mean()),
                   "frac_dots_within_2px_cat": float((d_cat[d] <= 2).mean())}
        np.save(OUT / f"dots_{k}.npy", d)
        print(k, {kk: round(vv, 4) for kk, vv in rows[k].items()})

    # ---- pre-registered selection rule ------------------------------------------------
    rule = ("maximise K_mean subject to n_dots <= 37654 and coverage >= 0.13 and "
            "0 dots within 2 cells of the catalogue and consensus-support membership")
    eligible = {k: v for k, v in rows.items()
                if v["n_dots"] <= n_incumbent and v["coverage_frac"] >= 0.13
                and v["frac_dots_within_2px_cat"] == 0.0}
    pick = max(eligible, key=lambda k: eligible[k]["K_mean"]) if eligible else None
    print("\nrule:", rule)
    print("eligible:", sorted(eligible), "-> pick:", pick)
    if pick:
        u = screen_unique(variants[pick])
        print("top registry overlaps for the pick:")
        for r in u[:8]:
            print(f"   {r['frac_of_candidate_dots_within_3px']:.4f}  rho {r['spearman_full_footprint']:+.4f}  {r['raster'][:52]}")
        (OUT / "e6_screen.json").write_text(json.dumps(
            {"pick": pick, "rule": rule, "variants": rows, "registry_screen": u,
             "evidence_class": "LOCAL checks; not scores"}, indent=1))
    (OUT / "e6_variants.json").write_text(json.dumps(
        {"rule": rule, "variants": rows, "pick": pick, "runtime_s": round(time.time() - t0, 1)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
