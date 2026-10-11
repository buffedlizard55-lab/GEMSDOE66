#!/usr/bin/env python3
"""Anatomy of every prior submission raster in ``registry/rasters/``.

Answers, by measurement rather than by assertion:

* how many pixels does each raster emit, and at what intensity?
* how far are the emitted pixels from the known catalogue?
* what is each raster's DTI **against the known catalogue** (a proxy, NOT a competition
  score - the organiser masks known faults, so this measures catalogue recall only)?
* how similar is each pair of rasters (rank correlation of the positive-pixel sets)?

The output feeds the duplicate/uniqueness gate required by the parallel-run protocol.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gemsdoe66.grid import footprint_mask, catalogue_mask, canonical_grid  # noqa: E402
from gemsdoe66.metric import dti_parts  # noqa: E402

REG = ROOT / "registry" / "rasters"
OUT = ROOT / "evidence" / "registry_anatomy.json"

# owner-reported live scores where one exists; everything else is unscored.
OWNER_SCORES = {
    "GEMSDOE32__h33-2-b2-zeros.tif": 0.2778,
    "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif": 0.2778,
    "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-nan.tif": 0.2778,
    "GEMSDOE28__h27-4-r1-solo-d2-8.tif": 0.2708,
    "GEMSDOE28__h36-1-rung30-blind-r1.tif": 0.2710,
    "GEMSDOE28__h38-1-hf-euler-r30-r1.tif": 0.2707,
    "GEMSDOE28__h32-1-prethin-tip-euler-d2-8.tif": 0.2649,
    "GEMSDOE33__h33d-analog-tip-stepover-r30.tif": 0.2632,
    "GEMSDOE25__dotted-h19-5-d2-8.tif": 0.2600,
    "gems25-dotted-h19-5-d2-8-20261002-e56ea318af89-zeros.tif": 0.2600,
    "gems25-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif": 0.2600,
    "GEMSDOE30__d28-poisson300m-offcat-44090.tif": 0.2600,
    "gemsdoe32-d28-ref02600-repro-44090-20261004T183200Z-426073b6-zeros.tif": 0.2600,
    "GEMSDOE27__topo-gap-closure-t-v2-on-d1-5.tif": 0.2449,
    "GEMSDOE24__h25-1-dotted-h19-5-d1-5.tif": 0.2477,
    "GEMSDOE29__wormrank-d28.tif": 0.2560,
    "19GEMSDOE__h19-5-powerlaw-budget-multiline.tif": 0.1922,
    "19GEMSDOE__h19-4-multiline-corroborated.tif": 0.1894,
    "GEMSDOE49__gate_ortho_w0.25-40k.tif": 0.2376,
    "GEMSDOE36__anderson-geothermal-pinn-38854.tif": 0.2750,
}


def read01(path: Path, fp: np.ndarray) -> np.ndarray:
    with rasterio.open(path) as src:
        a = src.read(1).astype(np.float32)
    a = np.nan_to_num(a, nan=0.0)
    a[~fp] = 0.0
    return np.clip(a, 0.0, 1.0)


def main() -> int:
    fp = footprint_mask()
    cat = catalogue_mask()
    grid = canonical_grid()
    # Euclidean distance (px) from every cell to the nearest catalogue pixel
    dist = ndimage.distance_transform_edt(~cat)

    rows = {}
    for p in sorted(REG.glob("*.tif")):
        a = read01(p, fp)
        pos = a > 0
        n_pos = int(pos.sum())
        if n_pos == 0:
            rows[p.name] = {"emitted": 0}
            continue
        score, tp, fpw, fnw, ng, S, M = dti_parts(a, cat)
        d = dist[pos]
        rows[p.name] = {
            "bytes": p.stat().st_size,
            "emitted": n_pos,
            "mass": float(a.sum()),
            "mean_intensity": float(a[pos].mean()),
            "dti_vs_catalogue": score,
            "tpw": tp, "fpw": fpw, "fnw": fnw, "M": M,
            "frac_within_1px_of_cat": float((d <= 1.0).mean()),
            "frac_within_2px_of_cat": float((d <= 2.0).mean()),
            "frac_within_3px_of_cat": float((d <= 3.0).mean()),
            "median_dist_px": float(np.median(d)),
            "mean_dist_px": float(d.mean()),
            "owner_score": OWNER_SCORES.get(p.name),
        }
        print(f"{p.name[:62]:62s} n={n_pos:>7,}  DTIcat={score:.4f}  "
              f"d<=2:{(d <= 2.0).mean():.3f}  med_d={np.median(d):6.2f}  "
              f"score={OWNER_SCORES.get(p.name)}", flush=True)

    sim = {}
    pw = ROOT / "evidence" / "registry_pairwise.json"
    if pw.exists():
        sim = json.loads(pw.read_text())

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"per_raster": rows, "pairwise": sim,
                               "grid": {"shape": list(grid.shape), "crs": grid.crs,
                                        "transform": list(grid.transform)},
                               "n_footprint": int(fp.sum()), "n_catalogue": int(cat.sum())},
                              indent=1))
    print(f"\nwrote {OUT}  ({len(rows)} rasters, {len(sim)} pairs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
