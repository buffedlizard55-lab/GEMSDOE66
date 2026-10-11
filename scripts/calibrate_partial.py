#!/usr/bin/env python3
"""Second pass on the live anchor: separate real signal from nuisance.

``scripts/calibrate_live.py`` found layers whose dot-mean correlates with the owner-reported
live score at |rho| up to 0.98.  That is high enough to be suspicious.  The rasters in the
registry are *not* an independent sample: they share one lineage and the main thing that
changed between them is the **emission geometry** (how many dots, and how far the dots sit
from the known catalogue).  Any layer that happens to vary with distance-to-catalogue will
therefore inherit the score trend without being causally involved.

This script regresses out two nuisance variables that are pure emission geometry -

    (1) the fraction of emitted dots within 200 m of the known catalogue
    (2) the number of emitted dots

- and recomputes the partial Spearman correlation of every layer with the live score.
A layer is only interesting if it survives both controls.

It also reports, for reference, how strongly each layer tracks distance-to-catalogue, which
is the mechanism by which a nuisance layer can masquerade as signal.
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
from gemsdoe66.grid import catalogue_mask, footprint_mask  # noqa: E402

REG = ROOT / "registry" / "rasters"
OUT = ROOT / "evidence" / "live_anchor_partial.json"
OWNER = json.loads((ROOT / "evidence" / "live_anchor_calibration.json").read_text())

SCORES = {
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
    a = np.nan_to_num(a, nan=0.0)
    a[~fp] = 0.0
    return np.clip(a, 0.0, 1.0)


def rank(x: np.ndarray) -> np.ndarray:
    ok = np.isfinite(x)
    out = np.full(x.shape, np.nan)
    out[ok] = np.argsort(np.argsort(x[ok])).astype(float)
    return out


def partial_spearman(x, y, nuis):
    """Spearman of x vs y after linear (rank) regression of both on the nuisance columns."""
    rx, ry = rank(x), rank(y)
    m = np.isfinite(rx) & np.isfinite(ry)
    Z = np.column_stack([np.ones(m.sum())] + [rank(n)[m] for n in nuis])
    Z = np.nan_to_num(Z)
    bx, *_ = np.linalg.lstsq(Z, np.nan_to_num(rx)[m], rcond=None)
    by, *_ = np.linalg.lstsq(Z, np.nan_to_num(ry)[m], rcond=None)
    ex = np.nan_to_num(rx)[m] - Z @ bx
    ey = np.nan_to_num(ry)[m] - Z @ by
    if np.std(ex) == 0 or np.std(ey) == 0:
        return 0.0, 1.0
    rho = float(np.corrcoef(ex, ey)[0, 1])
    dof = max(1, m.sum() - 2 - Z.shape[1])
    t = rho * np.sqrt(dof / max(1e-12, 1 - rho ** 2))
    # two-sided t p-value without scipy's betainc dependency
    from math import erf, lgamma, log, exp

    def _betai(a, b, z):
        # continued-fraction incomplete beta (Numerical Recipes betacf)
        def betacf(a, b, z, itmax=200, eps=3e-12):
            qab, qap, qam = a + b, a + 1.0, a - 1.0
            c = 1.0
            d = 1.0 - qab * z / qap
            d = 1.0 / (d if abs(d) > 1e-30 else 1e-30)
            h = d
            for mm in range(1, itmax + 1):
                m2 = 2 * mm
                aa = mm * (b - mm) * z / ((qam + m2) * (a + m2))
                d = 1.0 + aa * d
                d = 1.0 / (d if abs(d) > 1e-30 else 1e-30)
                c = 1.0 + aa / (c if abs(c) > 1e-30 else 1e-30)
                h *= d * c
                aa = -(a + mm) * (qab + mm) * z / ((a + m2) * (qap + m2))
                d = 1.0 + aa * d
                d = 1.0 / (d if abs(d) > 1e-30 else 1e-30)
                c = 1.0 + aa / (c if abs(c) > 1e-30 else 1e-30)
                de = d * c
                h *= de
                if abs(de - 1.0) < eps:
                    break
            return h
        if z <= 0:
            return 0.0
        if z >= 1:
            return 1.0
        lbeta = lgamma(a) + lgamma(b) - lgamma(a + b)
        front = exp(a * log(z) + b * log(1 - z) - lbeta)
        if z < (a + 1) / (a + b + 2):
            return front * betacf(a, b, z) / a
        return 1.0 - exp(b * log(1 - z) + a * log(z) - lbeta) * betacf(b, a, 1 - z) / b

    p = _betai(0.5 * dof, 0.5, dof / (dof + t * t))
    return rho, float(min(1.0, max(0.0, p)))


def main() -> int:
    fp = footprint_mask()
    cat = catalogue_mask()
    stack, names, fi = load_stack()
    dist_cat = ndimage.distance_transform_edt(~cat)

    seen: dict[str, str] = {}
    for p in sorted(REG.glob("*.tif")):
        if p.name not in SCORES:
            continue
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        seen.setdefault(h, p.name)
    keep = sorted(seen.values())

    rows, y, nuis, labels = [], [], [], []
    for name in keep:
        a = read01(REG / name, fp)
        pos = a > 0
        if pos.sum() == 0:
            continue
        w = a[pos].astype(np.float64)
        w /= w.sum()
        idx = np.flatnonzero(pos.ravel())
        fpos = np.clip(np.searchsorted(fi, idx), 0, fi.size - 1)
        assert np.all(fi[fpos] == idx)
        stats = []
        for j in range(len(names)):
            v = np.asarray(stack[j])[fpos].astype(np.float64)
            g = np.isfinite(v)
            stats.append(float((v[g] * w[g]).sum() / max(1e-12, w[g].sum())) if g.any() else np.nan)
        rows.append(stats)
        y.append(SCORES[name])
        d = dist_cat[pos]
        nuis.append([float((d <= 2.0).mean()), float(pos.sum())])
        labels.append(name)
    X = np.asarray(rows)
    y = np.asarray(y)
    N = np.asarray(nuis)
    print(f"n = {len(labels)} distinct scored rasters; nuisance = {['frac_within_2px_cat', 'n_dots']}")

    nuis_cols = [N[:, 0], N[:, 1]]
    out = []
    for j, nm in enumerate(names):
        v = X[:, j]
        if np.isfinite(v).sum() < 8 or np.nanstd(v) == 0:
            continue
        raw = float(spearmanr(v, y).statistic)
        pr, pp = partial_spearman(v, y, nuis_cols)
        # how much does this layer just track the nuisance?
        rho_frac = float(spearmanr(v, N[:, 0]).statistic)
        rho_n = float(spearmanr(v, N[:, 1]).statistic)
        out.append({"layer": nm, "rho_raw": raw, "rho_partial": pr, "p_partial": pp,
                    "rho_vs_frac_near_catalogue": rho_frac, "rho_vs_n_dots": rho_n})
    out.sort(key=lambda r: -abs(r["rho_partial"]))

    print(f"\n{'layer':26s} {'rho_raw':>8} {'rho_part':>9} {'p_part':>8} "
          f"{'|rho| v frac':>12} {'|rho| v n':>10}")
    for r in out[:24]:
        print(f"{r['layer']:26s} {r['rho_raw']:+8.3f} {r['rho_partial']:+9.3f} "
              f"{r['p_partial']:8.3f} {r['rho_vs_frac_near_catalogue']:+12.3f} "
              f"{r['rho_vs_n_dots']:+10.3f}")

    m = len(out)
    order = np.argsort([r["p_partial"] for r in out])
    prev = 1.0
    for rank, k in enumerate(order):
        prev = min(prev, out[k]["p_partial"] * m / (rank + 1))
        out[k]["q_bh"] = float(prev)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "nuisance_controls": ["frac of dots within 200 m of the known catalogue",
                              "number of emitted dots"],
        "n": len(labels), "rasters": labels, "scores": [float(s) for s in y],
        "layers": out,
    }, indent=1))
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
