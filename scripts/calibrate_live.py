#!/usr/bin/env python3
"""Live-score anchoring: which *physical* property of an emitted dot set explains score?

Why this exists
---------------
Every purely local instrument in this project family has the same defect: its truth is the
known catalogue, while the hidden test set is by construction *off* the catalogue.  A proxy
built on that truth rewards covering the catalogue and therefore cannot reward a genuinely
new fault (GEMSDOE32 registered this as IR-32-PROXY-01, and measured that the headline
proxy ranks live scores at only rho = +0.14).

This script takes the opposite route.  It uses the only ground signal that actually exists
for this family - the **owner-reported live leaderboard scores** on 20 previously submitted
rasters - and asks a purely statistical question:

    for each physical layer L, does the mean value of L under a raster's emitted dots
    correlate with that raster's live score, across rasters?

A layer that survives this test is a layer the organiser's hidden faults demonstrably live
on.  It is then the layer a new field should be built around.

Caveats that are stated, not hidden:

* n is ~14-20 distinct rasters (identical duplicates are collapsed by content digest).
* Owner-reported scores are **not organiser receipts** (no hash-to-score crosswalk exists).
* With n this small, a single correlation is weak evidence.  We therefore report the
  permutation p-value, the Benjamini-Hochberg adjusted q, and a leave-one-out prediction
  error, and we treat the result as a *prior for which lane to work in*, never as a score.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gemsdoe66.features import load_stack  # noqa: E402
from gemsdoe66.grid import footprint_mask, catalogue_mask  # noqa: E402

REG = ROOT / "registry" / "rasters"
OUT = ROOT / "evidence" / "live_anchor_calibration.json"

OWNER_SCORES = {
    "GEMSDOE32__h33-2-b2-zeros.tif": 0.2778,
    "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif": 0.2778,
    "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-nan.tif": 0.2778,
    "GEMSDOE36__anderson-geothermal-pinn-38854.tif": 0.2750,
    "GEMSDOE28__h36-1-rung30-blind-r1.tif": 0.2710,
    "GEMSDOE28__h27-4-r1-solo-d2-8.tif": 0.2708,
    "GEMSDOE28__h38-1-hf-euler-r30-r1.tif": 0.2707,
    "GEMSDOE28__h32-1-prethin-tip-euler-d2-8.tif": 0.2649,
    "GEMSDOE33__h33d-analog-tip-stepover-r30.tif": 0.2632,
    "GEMSDOE25__dotted-h19-5-d2-8.tif": 0.2600,
    "gems25-dotted-h19-5-d2-8-20261002-e56ea318af89-zeros.tif": 0.2600,
    "gems25-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif": 0.2600,
    "GEMSDOE30__d28-poisson300m-offcat-44090.tif": 0.2600,
    "gemsdoe32-d28-ref02600-repro-44090-20261004T183200Z-426073b6-zeros.tif": 0.2600,
    "GEMSDOE29__wormrank-d28.tif": 0.2560,
    "GEMSDOE24__h25-1-dotted-h19-5-d1-5.tif": 0.2477,
    "GEMSDOE27__topo-gap-closure-t-v2-on-d1-5.tif": 0.2449,
    "GEMSDOE49__gate_ortho_w0.25-40k.tif": 0.2376,
    "19GEMSDOE__h19-5-powerlaw-budget-multiline.tif": 0.1922,
    "19GEMSDOE__h19-4-multiline-corroborated.tif": 0.1894,
}


def read01(path: Path, fp: np.ndarray) -> np.ndarray:
    with rasterio.open(path) as src:
        a = src.read(1).astype(np.float32)
    a = np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)
    a[~fp] = 0.0
    return np.clip(a, 0.0, 1.0)


def main() -> int:
    fp = footprint_mask()
    cat = catalogue_mask()
    stack, names, fi = load_stack()
    nlayers = len(names)
    nfp = fi.size
    dist_cat = ndimage.distance_transform_edt(~cat)

    # ---- collapse byte-identical duplicates, keeping one row per distinct raster -----------
    seen: dict[str, str] = {}
    for p in sorted(REG.glob("*.tif")):
        if p.name not in OWNER_SCORES:
            continue
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        if h not in seen:
            seen[h] = p.name
    keep = sorted(seen.values())
    print(f"{len(keep)} distinct scored rasters (from {len(OWNER_SCORES)} scored filenames)")

    # ---- per-raster statistics -------------------------------------------------------------
    rows, y, labels = [], [], []
    for name in keep:
        a = read01(REG / name, fp)
        pos = a > 0
        n = int(pos.sum())
        if n == 0:
            continue
        w = a[pos].astype(np.float64)
        w = w / w.sum()
        idx = np.flatnonzero(pos.ravel())          # flat index in the full grid
        # map full-grid flat index -> footprint-vector position
        fpos = np.searchsorted(fi, idx)
        fpos = np.clip(fpos, 0, nfp - 1)
        assert np.all(fi[fpos] == idx), "footprint index mapping failed"
        stats = []
        for j in range(nlayers):
            v = np.asarray(stack[j])[fpos].astype(np.float64)
            good = np.isfinite(v)
            stats.append(float(np.sum(v[good] * w[good]) / max(1e-12, w[good].sum()))
                         if good.any() else np.nan)
        rows.append(stats)
        y.append(OWNER_SCORES[name])
        labels.append(name)
    X = np.asarray(rows, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    print(f"design matrix: {X.shape}")

    # footprint mean of every layer, for enrichment normalisation
    fp_mean = np.empty(nlayers)
    for j in range(nlayers):
        v = np.asarray(stack[j]).astype(np.float64)
        v = v[np.isfinite(v)]
        fp_mean[j] = v.mean() if v.size else np.nan

    # ---- rank correlations, permutation p, BH q --------------------------------------------
    res = []
    rng = np.random.default_rng(0)
    for j, nm in enumerate(names):
        v = X[:, j]
        ok = np.isfinite(v)
        if ok.sum() < 6 or np.nanstd(v[ok]) == 0:
            continue
        rho = float(spearmanr(v[ok], y[ok]).statistic)
        # enrichment version (mean at dots / footprint mean)
        enr = np.where(fp_mean[j] != 0, v / fp_mean[j], np.nan)
        rho_e = float(spearmanr(enr[ok], y[ok]).statistic) if np.isfinite(enr[ok]).all() else np.nan
        # permutation null on the raw statistic
        null = np.empty(2000)
        yy = y[ok]
        for b in range(2000):
            null[b] = spearmanr(v[ok], rng.permutation(yy)).statistic
        p = float((np.abs(null) >= abs(rho) - 1e-12).mean())
        res.append({"layer": nm, "rho": rho, "rho_enrichment": rho_e,
                    "p_perm": p, "mean_at_dots": float(np.nanmean(v[ok])),
                    "footprint_mean": float(fp_mean[j])})
    res.sort(key=lambda r: -abs(r["rho"]))
    # Benjamini-Hochberg
    m = len(res)
    order = np.argsort([r["p_perm"] for r in res])
    prev = 1.0
    for rank, k in enumerate(order):
        val = res[k]["p_perm"] * m / (rank + 1)
        prev = min(prev, val)
        res[k]["q_bh"] = float(prev)

    print(f"\n{'layer':26s} {'rho':>7} {'p':>7} {'q_BH':>7} {'rho_enr':>8}")
    for r in res[:20]:
        print(f"{r['layer']:26s} {r['rho']:+7.3f} {r['p_perm']:7.3f} {r['q_bh']:7.3f} "
              f"{r['rho_enrichment']:+8.3f}")

    # ---- leave-one-out prediction with the single best layer --------------------------------
    def loo(j):
        v = X[:, j].copy()
        med = np.nanmedian(v)
        v[~np.isfinite(v)] = med
        pred = np.empty(len(y))
        for i in range(len(y)):
            tr = np.ones(len(y), bool); tr[i] = False
            A = np.vstack([v[tr], np.ones(tr.sum())]).T
            coef, *_ = np.linalg.lstsq(A, y[tr], rcond=None)
            pred[i] = coef[0] * v[i] + coef[1]
        return float(np.sqrt(np.mean((pred - y) ** 2))), pred

    best = [r["layer"] for r in res[:6]]
    loo_out = {}
    for nm in best:
        j = names.index(nm)
        rmse, pred = loo(j)
        loo_out[nm] = {"loo_rmse": rmse, "pred": [float(p) for p in pred]}
    base_rmse = float(np.sqrt(np.mean((y - y.mean()) ** 2)))
    print(f"\nbaseline (predict the mean) LOO RMSE = {base_rmse:.4f}")
    for nm, d in loo_out.items():
        print(f"  {nm:26s} LOO RMSE = {d['loo_rmse']:.4f}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "method": "spearman rank correlation of layer-mean-under-emitted-dots vs "
                  "owner-reported live DTI, across distinct scored rasters",
        "n_rasters": len(labels), "rasters": labels, "scores": [float(s) for s in y],
        "baseline_loo_rmse": base_rmse,
        "layers": res, "loo_single_layer": loo_out,
        "caveat": "owner-reported scores, not organiser receipts; n is small; "
                  "used to choose a lane, never as a score",
    }, indent=1))
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
