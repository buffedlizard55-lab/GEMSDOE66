#!/usr/bin/env python3
"""E7 — Final emission for the GEMSDOE66 session-66 candidate (unique submission).

Design (fixed before emission, recorded in registry66/preregistration-k66.json):
  support  = union of the 300 m disks of the six highest-scoring registry rasters (the only
             region in which the family has *observed* high scores)  AND distance-to-catalogue
             >= 3 cells (so no emitted dot lies within 2 cells of the published catalogue)
  prior    = K^0.5 over that support, K = GeoDAWN radiometric potassium (mirror layer, pinned)
  emission = metric-marginal greedy (E5.emit): a dot is accepted only while the published DTI's
             first-order condition holds; hard cap N = 32000 dots; min separation 2 cells
  output   = float32 single-band GeoTIFF on the official grid, values in {0,1} inside the
             footprint and NaN outside, written by src/gems/submission_writer.write_submission
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import numpy as np
from scipy import ndimage
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import lib66
from e5_design import consensus_support, emit, MIN_SEP, R_PX

N_CAP = 32000
GAMMA = 0.5
CAT_MIN_CELLS = 3


def main() -> int:
    t0 = time.time()
    fp = lib66.footprint(); cat = lib66.catalogue()
    d_cat = ndimage.distance_transform_edt(~cat)
    K = lib66.layer("K")
    allowed = fp & (d_cat >= CAT_MIN_CELLS) & (K > 0)
    scored = lib66.distinct_scored()
    best6 = sorted(scored, key=lambda n: -scored[n])[:6]
    cons = consensus_support(best6) & allowed
    mask = cons
    pos = np.where(mask, np.power(np.where(mask, K, 1.0), GAMMA), 0.0)
    rho = np.where(mask, pos, 0.0)
    rho = rho / rho.sum() * 60988.0
    dots, T, F = emit(rho, allowed, N_CAP)
    dmin = ndimage.distance_transform_edt(~dots)
    cov = float((dmin[fp] <= 3).mean())

    pred = np.zeros(lib66.GRID, np.float32)
    pred[dots] = 1.0
    name = "gems66-k66-kanchor-consensus-32000-20261012T003000Z"
    note = ("GEMSDOE66 K66 | off-catalogue K^0.5-anchored consensus-support dots, metric-marginal "
            "accept, 32000 dots; local checks only")
    receipt = None
    if len(note) <= 140:
        np.save(lib66.ROOT / "evidence66" / "dots_final.npy", dots)
    info = {
        "design": {"support": "union of 300 m disks of the six highest owner-scored registry rasters",
                   "cat_min_cells": CAT_MIN_CELLS, "gamma": GAMMA, "N_cap": N_CAP,
                   "min_sep_cells": MIN_SEP, "kernel_range_cells": R_PX},
        "n_dots": int(dots.sum()), "K_mean": float(K[dots].mean()),
        "footprint_mean_K": float(K[fp].mean()),
        "coverage_frac_within_300m": cov,
        "frac_dots_within_1cell_catalogue": float((d_cat[dots] <= 1).mean()),
        "frac_dots_within_2cells_catalogue": float((d_cat[dots] <= 2).mean()),
        "frac_dots_within_3cells_catalogue": float((d_cat[dots] <= 3).mean()),
        "frac_dots_in_lidar_coverage": float((lib66.layer("valid")[dots] > 0).mean()),
        "model_T": T, "model_F": F,
        "model_dti_proxy": T / (0.2 * T + 0.8 * 60988.0 + 0.2 * F),
        "runtime_s": round(time.time() - t0, 1),
        "evidence_class": "LOCAL DESIGN STATISTICS; not a score",
    }
    (lib66.ROOT / "evidence66" / "e7_final.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
