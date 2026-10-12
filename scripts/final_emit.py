#!/usr/bin/env python3
"""Fit the LIDAR-01 field on the full catalogue and emit the submission raster.

Design decision (measured, not assumed)
---------------------------------------
The field uses **only catalogue-independent channels** — the 35 LiDAR-lane channels plus
the competition's 19 numerical bands.  The catalogue-derived channels (distance to the
visible network, its strike alignment, and the proximity-weighted interactions) are
excluded on purpose: with them the gradient-boosted field collapses onto a memorised copy
of the training catalogue (p99 = 2.2e-05, 0.37 % of cells above 0.5, AUC 0.4955 against
withheld traces).  Without them the same model generalises (AUC 0.6164 on withheld
traces) and top-score emission beats mass-matched random placement by ~2.4x on the
whole-trace holdout.  That is also the right inductive bias for the scored task, whose
truth is faults that are *absent* from the catalogue we were given.
"""
from __future__ import annotations

import argparse
import gc
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from lane_run import (H, W, FeatureAssembler, fit_predict, load_base)  # noqa: E402
from lane_run_helper import poisson_disk_dots, weighted_disk_dots  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=37654)
    ap.add_argument("--sep", type=float, default=2.8)
    ap.add_argument("--mode", default="topk", choices=["topk", "weighted"])
    ap.add_argument("--gamma", type=float, default=1.0)
    ap.add_argument("--max-iter", type=int, default=120)
    ap.add_argument("--score-out", default=str(ROOT / "data" / "derived" / "lane01_final_score.npy"))
    ap.add_argument("--emit", action="store_true", help="also write the GeoTIFF")
    args = ap.parse_args()

    t0 = time.time()
    log = lambda m: print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)

    footprint, fault, chans, names, lidar = load_base()
    asm = FeatureAssembler(chans, names, use_lane=True, use_official=True)

    def _sv(self, _visible):
        self._dyn = np.zeros((0, H, W), dtype=np.float32)   # no catalogue-derived channel
    FeatureAssembler.set_visible = _sv
    asm.set_visible(fault)
    log(f"channels: {len(asm.all_names)} (catalogue-independent only)")

    score, _ = fit_predict(asm, fault, footprint, footprint, seed=7,
                           max_iter=args.max_iter)
    score = np.nan_to_num(score, nan=0.0).astype(np.float32)
    np.save(args.score_out, score)
    v = score[footprint]
    log("score percentiles " + " ".join(
        f"p{q}:{np.percentile(v, q):.4g}" for q in (1, 25, 50, 75, 99, 100)))
    (Path(args.score_out).with_suffix(".meta.json")).write_text(json.dumps(
        {"channels": asm.all_names, "n_channels": len(asm.all_names),
         "catalogue_derived_channels_excluded": True}, indent=1))

    if not args.emit:
        return 0

    if args.mode == "topk":
        dots = poisson_disk_dots(score, footprint, args.budget, args.sep)
    else:
        dots = weighted_disk_dots(score, footprint, args.budget, args.sep,
                                  gamma=args.gamma, seed=4242)
    log(f"selected {int(dots.sum())} dots")
    import subprocess
    cmd = [sys.executable, str(ROOT / "scripts" / "emit_submission.py"),
           "--score", args.score_out, "--budget", str(args.budget),
           "--sep", str(args.sep)]
    cmd += ["--gamma", str(args.gamma)] if args.mode == "weighted" else []
    subprocess.run(cmd, check=True, cwd=str(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
