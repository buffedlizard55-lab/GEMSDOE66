#!/usr/bin/env python3
"""Second instrument: GLOBAL whole-trace holdout (catalogue proximity preserved).

Why a second instrument
-----------------------
``lane_run.py --stage sweep`` withholds whole fault segments *inside held 6 km blocks*,
which removes every nearby visible fault from the scoring domain.  That is the correct
hide-and-recover test of "can the field find a fault with no catalogue context", but it
deletes the one covariate that dominates the real task: the real hidden faults are
plausibly interleaved with, or continue, the given catalogue.  This instrument therefore
withholds whole INGENIOUS traces **everywhere**, keeps the rest of the catalogue visible,
emits across the whole footprint, and scores the withheld traces.

Protocol
--------
* whole traces withheld (authoritative ``record_id`` segments), 300 m buffer removed from
  the visible set;
* every catalogue-derived feature is computed from the visible set only;
* truth = withheld trace pixels that are LiDAR-covered;
* pooled DTI, alpha = 0.2, beta = 0.8, triangular kernel R = 300 m.
"""
from __future__ import annotations

import argparse
import gc
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from gems.constants import ALPHA, BETA  # noqa: E402
from gems.metric import dti_from_terms, tversky_terms  # noqa: E402
from lane_run import (H, W, BUFFER_PX, FeatureAssembler, dist_and_strike,  # noqa: E402
                     fit_predict, load_base, segment_ids_from_traces, mean_ci)
from lane_run_helper import poisson_disk_dots, weighted_disk_dots  # noqa: E402


def make_folds(fault, lidar, n_folds, seed0=500):
    seg = segment_ids_from_traces(fault)
    ids = np.unique(seg[fault])
    ids = ids[ids > 0]
    folds = []
    for f in range(n_folds):
        rng = np.random.default_rng(seed0 + f)
        k = max(1, int(round(len(ids) / n_folds)))
        held = rng.choice(ids, size=k, replace=False)
        held_segment = fault & np.isin(seg, held)
        buffer_zone = (ndimage.distance_transform_edt(~held_segment) <= BUFFER_PX
                       if held_segment.any() else np.zeros_like(fault))
        visible = fault & ~held_segment & ~buffer_zone
        folds.append({
            "visible": visible,
            "held_segment": held_segment,
            "truth": held_segment & lidar,
            "buffer": buffer_zone,
            "held_ids": sorted(int(x) for x in held),
        })
    return seg, folds


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=4)
    ap.add_argument("--budget", type=int, default=37654)
    ap.add_argument("--sep", type=float, default=2.8)
    ap.add_argument("--variants", default="random,distance,lane_nocat")
    ap.add_argument("--instrument", default="traces", choices=["traces", "blocks"])
    ap.add_argument("--folds-blocks", type=int, default=4)
    ap.add_argument("--max-iter", type=int, default=120)
    args = ap.parse_args()
    t0 = time.time()
    log = lambda m: print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)

    footprint, fault, chans, names, lidar = load_base()
    log(f"footprint {int(footprint.sum())} fault {int(fault.sum())} lidar {int(lidar.sum())}")
    if args.instrument == "traces":
        _, folds = make_folds(fault, lidar, args.folds)
        dom_fn = lambda sp: footprint
    else:
        from lane_run import make_folds as block_folds, fold_domain
        _, bfs = block_folds(fault, lidar)
        bfs = bfs[:args.folds]
        folds = []
        for sp in bfs:
            _, dom = fold_domain(sp, footprint, lidar)
            folds.append({"visible": sp["visible"], "held_segment": sp["held_segment"],
                          "truth": sp["holdout"], "buffer": sp["buffer_dropped"],
                          "domain": dom, "train_ok": footprint & ~dom & ~sp["held_segment"]
                          & ~sp["buffer_dropped"]})
        dom_fn = lambda sp: sp["domain"]
    log(f"{len(folds)} folds ({args.instrument}); withheld positives/fold ~"
        f"{int(np.mean([f['truth'].sum() for f in folds]))}")

    want = [v.strip() for v in args.variants.split(",")]
    results = {}
    cache = ROOT / "data" / "derived" / "trace_scores"
    cache.mkdir(parents=True, exist_ok=True)

    for vname in want:
        per_fold = {"topk": [], "weighted": []}
        agg = {"topk": {"tp": 0., "fp": 0., "fn": 0.},
               "weighted": {"tp": 0., "fp": 0., "fn": 0.}}
        dots = {"topk": [], "weighted": []}
        for f, sp in enumerate(folds):
            cf = cache / f"{vname}_t{f}.npy"
            if vname == "lane_nocat":
                # drop every catalogue-derived channel: distance to the visible network,
                # its strike alignment and the proximity-weighted interactions.  With them
                # in the model the field collapses onto a memorised copy of the visible
                # catalogue (measured: p99 = 2.2e-05, 0.37 % of cells at p > 0.5, AUC 0.50
                # on withheld traces).  Without them it generalises (AUC 0.62, fold 0).
                _orig = FeatureAssembler.set_visible

                def _sv(self, visible, _o=_orig):
                    _o(self, visible)
                    self._dyn = np.zeros((0, H, W), dtype=np.float32)
                FeatureAssembler.set_visible = _sv
            if cf.exists():
                score = np.load(cf)
            else:
                train_ok = sp.get("train_ok") or (footprint & ~sp["held_segment"] & ~sp["buffer"])
                if vname == "random":
                    rng = np.random.default_rng(3000 + f)
                    score = rng.random((H, W)).astype(np.float32)
                elif vname == "distance":
                    d, _ = dist_and_strike(sp["visible"])
                    score = np.exp(-d / 5.0).astype(np.float32)
                else:
                    asm = FeatureAssembler(chans, names, use_lane=True, use_official=True)
                    asm.set_visible(sp["visible"])
                    score, _ = fit_predict(asm, sp["visible"], train_ok,
                                           sp.get("domain") or footprint,
                                           seed=31 + f, max_iter=args.max_iter)
                    FeatureAssembler.set_visible = _orig
                    score = np.nan_to_num(score, nan=0.0).astype(np.float32)
                    del asm
                    gc.collect()
                np.save(cf, score)
                globals().pop("_orig", None)
            truth = sp["truth"]
            dom = dom_fn(sp)
            budget_f = max(1, int(round(args.budget * dom.sum() / max(footprint.sum(), 1))))
            for mode in ("topk", "weighted"):
                if vname == "random" and mode == "weighted":
                    pred = np.zeros((H, W), dtype=np.float32)
                    d = poisson_disk_dots(score, dom, budget_f, args.sep)
                    pred[d] = 1.0
                    n = int(d.sum())
                elif mode == "topk":
                    d = poisson_disk_dots(score, dom, budget_f, args.sep)
                    pred = np.zeros((H, W), dtype=np.float32)
                    pred[d] = 1.0
                    n = int(d.sum())
                else:
                    d = weighted_disk_dots(score, dom, budget_f, args.sep,
                                           gamma=1.0, seed=5150 + f)
                    pred = np.zeros((H, W), dtype=np.float32)
                    pred[d] = 1.0
                    n = int(d.sum())
                tp, fp, fn = tversky_terms(pred, truth)
                dv = dti_from_terms(tp, fp, fn, ALPHA, BETA)
                per_fold[mode].append(float(dv))
                dots[mode].append(n)
                agg[mode]["tp"] += tp; agg[mode]["fp"] += fp; agg[mode]["fn"] += fn
                del pred, d
                gc.collect()
            log(f"{vname} fold {f}: truth={int(truth.sum())} "
                f"topk={per_fold['topk'][-1]:.5f} weighted={per_fold['weighted'][-1]:.5f}")
            del score
            gc.collect()
        for mode in ("topk", "weighted"):
            m, ci = mean_ci(per_fold[mode])
            pooled = dti_from_terms(agg[mode]["tp"], agg[mode]["fp"], agg[mode]["fn"],
                                    ALPHA, BETA)
            results[f"{vname}|{mode}"] = {
                "label": "HOLDOUT-DTI",
                "per_fold": [round(float(x), 6) for x in per_fold[mode]],
                "mean": round(m, 6), "ci95": ci, "pooled": round(float(pooled), 6),
                "dots": dots[mode], "budget_full_grid": args.budget,
                "dots_per_fold": dots[mode], "separation_px": args.sep}
            log(f"{vname}|{mode}: mean={m:.5f} ci={ci} pooled={pooled:.5f}")
    out = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "stage": "trace-holdout",
           "protocol": ("global whole-trace holdout: whole INGENIOUS traces withheld "
                        "everywhere, 300 m buffer removed from the visible catalogue, "
                        "features derived from visible faults only, truth = withheld "
                        "trace pixels inside LiDAR coverage, emission across the whole "
                        "footprint, pooled DTI alpha=0.2 beta=0.8 R=300 m"),
           "evaluator": "src/gems/metric.py :: tversky_terms / dti_from_terms",
           "instrument": args.instrument, "n_folds": len(folds), "variants": results}
    (ROOT / "evidence" / f"lidar_lane_{args.instrument}_holdout.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: {"mean": v["mean"], "ci95": v["ci95"], "pooled": v["pooled"]}
                      for k, v in results.items()}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
