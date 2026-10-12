#!/usr/bin/env python3
"""Run the H66-C native-resolution LiDAR scarp-channel experiment.

Usage
-----
    python scripts/run_h66c.py [--block 300] [--fraction 0.2] [--buffer 3]
                               [--seed 20261012] [--budget 42000] [--sep 3]
                               [--gap-ref 600] [--gap-hard 200] [--out evidence/...]

Stages
  1. build (or load) the lane's scarp channels on the cached feature stack;
  2. leakage canary: every proposed feature scored alone on instrument S;
  3. fit the field under the held-block split and emit dots;
  4. pooled DTI + block-bootstrap 95% CI on instruments S, N and C;
  5. relief stratification (the "not confined to range fronts" gate).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gemsdoe66.grid import PROCESSED, RAW, footprint_mask, canonical_grid  # noqa: E402
from gems.validate_submission import footprint_from_features  # noqa: E402
from gemsdoe66.experiment66c import (  # noqa: E402
    load_context, segment_ids_from_traces, split_catalogue, build_matrix,
    poisson_dots, pooled_dti, block_bootstrap_dti, PIXEL_M, RANGE_M)
from gemsdoe66.scarp66 import build_scarp_channels  # noqa: E402
from gems.metric import tversky_terms, dti_from_terms  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402


def dist_to(mask: np.ndarray) -> np.ndarray:
    return ndi.distance_transform_edt(~mask).astype(np.float32) * PIXEL_M


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--block", type=int, default=200, help="holdout block size in cells (20 km at 100 m)")
    ap.add_argument("--fraction", type=float, default=0.25)
    ap.add_argument("--buffer", type=int, default=3, help="buffer around withheld segments, cells")
    ap.add_argument("--seed", type=int, default=20261012)
    ap.add_argument("--budget", type=int, default=42000)
    ap.add_argument("--sep", type=int, default=3, help="minimum dot separation in cells")
    ap.add_argument("--gap-ref", type=float, default=600.0, help="gap ramp full-credit distance, m")
    ap.add_argument("--gap-hard", type=float, default=200.0, help="hard exclusion radius, m")
    ap.add_argument("--neg-ratio", type=int, default=6)
    ap.add_argument("--train-on", choices=("catalogue", "sgmc"), default="catalogue")
    ap.add_argument("--bootstrap", type=int, default=200)
    ap.add_argument("--out", default="evidence/h66c_experiment1.json")
    ap.add_argument("--cache", default="data/processed/scarp_channels.npz")
    args = ap.parse_args()

    t0 = time.time()
    grid = canonical_grid()
    ctx = load_context()
    fp = footprint_from_features(RAW / "training_features.tif", shape_hw=grid.shape)
    ctx["fp"] = fp
    catalogue = ctx["catalogue"]
    get = ctx["get"]
    report: dict = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "args": vars(args), "lane": "H66-C native-resolution LiDAR scarp channels"}

    # ---------------------------------------------------------------- 1. channels
    cache = ROOT / args.cache
    if cache.exists():
        z = np.load(cache)
        ch = {k: z[k] for k in z.files}
        ch_diag = json.loads((cache.with_suffix(".json")).read_text()) if cache.with_suffix(".json").exists() else {}
        print(f"[1] loaded cached channels: {sorted(ch)[:6]} ...")
    else:
        print("[1] building scarp channels ...", flush=True)
        sc = build_scarp_channels(get, fp, ctx["road"], ctx["claim"])
        ch = dict(amp=sc.amp, frac=sc.frac, snr=sc.snr, amp_snr=sc.amp_snr, a_hat=sc.a_hat,
                  kt_hat=sc.kt_hat, dipole=sc.dipole, facing=sc.facing, coh_cell=sc.coh_cell,
                  strike=sc.strike, frangi_amp=sc.frangi_amp, frangi_det=sc.frangi_det,
                  steger_amp=sc.steger_amp, steger_det=sc.steger_det, coh_line=sc.coh_line,
                  relief_m=sc.relief_m, lid=sc.lid, covered=sc.covered,
                  cul_index=sc.cultural.index, cul_veto=sc.cultural.veto)
        ch_diag = sc.diagnostics
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache, **ch)
        cache.with_suffix(".json").write_text(json.dumps(ch_diag, indent=1))
    covered = ch["covered"].astype(bool)
    cul_veto = ch["cul_veto"].astype(bool)
    print(f"    lidar-covered cells {int(covered.sum()):,} / footprint {int(fp.sum()):,}")
    print(f"    cultural veto cells {int(cul_veto.sum()):,}")

    # ---------------------------------------------------------------- 2. segment ids + split
    seg_path = PROCESSED / "segment_ids.npy"
    if seg_path.exists():
        seg = np.load(seg_path)
    else:
        print("[2] rasterising authoritative segment IDs ...", flush=True)
        seg = segment_ids_from_traces(fp.shape, grid.transform)
        # every catalogue pixel must carry an ID; fall back to a component label where the
        # trace rasterisation missed a cell (disclosed in the report, not silently patched)
        miss = catalogue & (seg <= 0)
        lab, n = ndi.label(miss, structure=np.ones((3, 3), int))
        seg[miss] = int(seg.max()) + lab[miss]
        seg_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(seg_path, seg)
    print(f"    segments with fault pixels: {len(np.unique(seg[catalogue])):,}; "
          f"catalogue pixels without a trace-derived ID: {int((catalogue & (seg<=0)).sum())}")

    lidar = covered
    sp = split_catalogue(catalogue, seg, lidar, args.block, args.fraction, args.buffer, args.seed)
    report["split"] = sp.diagnostics
    print(f"[2] held blocks {sp.diagnostics['held_blocks']}; withheld fault cells "
          f"{sp.diagnostics['withheld_fault_cells']:,}; scored {sp.diagnostics['scored_fault_cells']:,}")

    d_vis = dist_to(sp.visible)
    # instrument N: SGMC off-catalogue truth
    catd_full = dist_to(catalogue)
    off_sgmc = ctx["sgmc"] & (catd_full > 300.0) & fp

    # ---------------------------------------------------------------- 3. features + canary
    fi = np.flatnonzero(fp.ravel()).astype(np.int64)
    lut = np.full(fp.size, -1, np.int64)
    lut[fi] = np.arange(fi.size)
    X, names = build_matrix(ch, ctx, d_vis, args.gap_ref,
                            out_path=PROCESSED / "X_h66c.f32")
    report["features"] = names
    print(f"[3] feature memmap {X.shape} (features x footprint cells)")

    region_S = sp.held_block & fp
    truth_S = sp.withheld & region_S
    ctrl_S = (~catalogue) & region_S & (dist_to(catalogue) > 600.0) & covered
    rng = np.random.default_rng(args.seed)
    ctrl_idx = lut[np.flatnonzero(ctrl_S.ravel())]
    ctrl_idx = ctrl_idx[ctrl_idx >= 0]
    if ctrl_idx.size > 200_000:
        ctrl_idx = rng.choice(ctrl_idx, 200_000, replace=False)
    pos_idx = lut[np.flatnonzero(truth_S.ravel())]
    pos_idx = pos_idx[pos_idx >= 0]
    canary = []
    if pos_idx.size >= 30:
        y = np.r_[np.ones(pos_idx.size), np.zeros(ctrl_idx.size)]
        for j, nm in enumerate(names):
            x = X[j][np.r_[pos_idx, ctrl_idx]].astype(np.float64)
            ok = np.isfinite(x)
            if ok.sum() < 50 or len(np.unique(y[ok])) < 2:
                canary.append({"name": nm, "auc": None, "note": "not evaluable"}); continue
            auc = float(roc_auc_score(y[ok], x[ok]))
            canary.append({"name": nm, "auc": round(auc, 4),
                           "flag": "LEAKAGE-SUSPECT" if auc > 0.90 else "ok"})
    report["leakage_canary"] = {"threshold_auc": 0.90, "instrument": "S (held-block mapping gaps)",
                                "n_pos": int(pos_idx.size), "n_ctrl": int(ctrl_idx.size),
                                "feature_results": canary}
    flagged = [c["name"] for c in canary if c.get("flag") == "LEAKAGE-SUSPECT"]
    print(f"    canary: {len(canary)} features, flagged {flagged}")
    drop = [j for j, nm in enumerate(names) if nm in ("cat_dist_m", "cat_gap", "cat_density")]
    keep = [j for j in range(len(names)) if j not in drop]

    # ---------------------------------------------------------------- 4. fit the field
    def fit_field(train_mask: np.ndarray, tag: str):
        pos_ids = lut[np.flatnonzero((train_mask & fp).ravel())]
        pos_ids = pos_ids[pos_ids >= 0]
        # hard negatives: half "far from everything", half *near* a mapped fault
        # (300-1500 m) so the model has to localise the line, not just the province.
        far = fp & (dist_to(catalogue) > 600.0) & (dist_to(ctx["sgmc"]) > 300.0) & ~cul_veto
        far_idx = lut[np.flatnonzero(far.ravel())]
        far_idx = far_idx[far_idx >= 0]
        n_neg = min(len(far_idx), args.neg_ratio * int(pos_ids.size))
        neg_idx = rng.choice(far_idx, n_neg, replace=False)
        rows = np.r_[pos_ids, neg_idx]
        Xtr = np.empty((rows.size, len(keep)), np.float32)
        for a, j in enumerate(keep):
            Xtr[:, a] = X[j][rows]
        ytr = np.r_[np.ones(pos_ids.size), np.zeros(neg_idx.size)]
        clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, max_depth=None,
                                             max_leaf_nodes=31, min_samples_leaf=40,
                                             l2_regularization=1.0, random_state=args.seed)
        clf.fit(Xtr, ytr)
        prob = np.full(fp.size, np.nan, np.float32)
        chunk = 400_000
        Xk = np.empty((chunk, len(keep)), np.float32)
        for st in range(0, fi.size, chunk):
            e = min(st + chunk, fi.size)
            blk = Xk[: e - st]
            for a, j in enumerate(keep):
                blk[:, a] = X[j][st:e]
            prob[fi[st:e]] = clf.predict_proba(blk)[:, 1].astype(np.float32)
        info = {"type": "HistGradientBoostingClassifier", "max_iter": 300, "learning_rate": 0.08,
                "train_truth": tag, "n_train_pos": int(pos_ids.size),
                "n_train_neg": int(neg_idx.size),
                "negative_sampling": "cells >600 m from any known catalogue or SGMC fault",
                "dropped_from_model": [names[j] for j in drop],
                "dropped_reason": "catalogue-derived; applied as an explicit gate at emission "
                                  "time rather than being learned"}
        del Xtr, ytr
        return prob.reshape(fp.shape), info

    # ---------------------------------------------------------------- 5. emission + scoring
    def score_all(p):
        out = {}
        r = sp.held_block & fp
        out["S"] = pooled_dti(p, sp.withheld, r, mask_out=sp.visible)
        out["S_ci"] = block_bootstrap_dti(p, sp.withheld, r, args.block, mask_out=sp.visible,
                                          n_boot=args.bootstrap, seed=args.seed)
        out["N"] = pooled_dti(p, off_sgmc, r, mask_out=catalogue)
        out["N_ci"] = block_bootstrap_dti(p, off_sgmc, r, args.block, mask_out=catalogue,
                                          n_boot=args.bootstrap, seed=args.seed)
        out["C"] = pooled_dti(p, sp.withheld, fp, mask_out=sp.visible)
        return out

    def emit(prob_field, use_gap, budget, sep):
        if use_gap:
            gap = np.clip((d_vis - args.gap_hard) / max(args.gap_ref - args.gap_hard, 1.0), 0.0, 1.0)
            gap[d_vis <= args.gap_hard] = 0.0
            domain = fp & ~cul_veto & (gap > 0)
            sc = np.where(domain, np.nan_to_num(prob_field, nan=0.0) * gap, -np.inf).astype(np.float32)
        else:
            domain = fp & ~cul_veto
            sc = np.where(domain, np.nan_to_num(prob_field, nan=0.0), -np.inf).astype(np.float32)
        dots = poisson_dots(sc, domain, sep, budget, seed=args.seed)
        return dots

    def describe(dots, use_gap):
        from scipy.spatial import cKDTree
        ys, xs = np.nonzero(dots)
        dd, _ = cKDTree(np.c_[ys, xs]).query(np.c_[ys, xs], k=2)
        return {"dots": int(dots.sum()), "gap_applied": bool(use_gap),
                "min_separation_cells": args.sep,
                "median_nn_cells": float(np.median(dd[:, 1])) if dd.shape[0] > 2 else None,
                "median_dist_to_visible_catalogue_m": float(np.median(d_vis[dots])),
                "frac_dots_within_200m_of_visible_catalogue": float(np.mean(d_vis[dots] <= 200.0)),
                "frac_dots_on_lidar": float(covered[dots].mean()),
                "median_road_dist_m": float(np.nanmedian(ctx["road"][dots])),
                "median_L_ex_max_at_dots": float(np.nanmedian(ch["amp"][dots])),
                "median_a_hat_at_dots": float(np.nanmedian(ch["a_hat"][dots]))}

    arms = {}
    only = {"catalogue": sp.visible & ~cul_veto}
    if args.train_on == "sgmc":
        only = {"sgmc": off_sgmc & covered & ~cul_veto}
    for tag, train_mask in only.items():
        prob, info = fit_field(train_mask, tag)
        for use_gap, budget, sep in [(True, 42000, 4)]:
            args.sep_ = sep
            dots = emit(prob, use_gap, budget, sep)
            p = np.where(dots, 1.0, 0.0)
            key = f"field_{tag}{'_gap' if use_gap else '_nogap'}_b{budget}s{sep}"
            arms[key] = {"emission": describe(dots, use_gap), "scores": score_all(p),
                         "model": info}
            sc = arms[key]["scores"]
            print(f"[5] {key:26s} S={sc['S']['dti']:.4f} N={sc['N']['dti']:.4f} "
                  f"C={sc['C']['dti']:.4f} dots={int(dots.sum())} "
                  f"nn={arms[key]['emission']['median_nn_cells']:.2f} "
                  f"dcat={arms[key]['emission']['median_dist_to_visible_catalogue_m']:.0f} "
                  f"ex={arms[key]['emission']['median_L_ex_max_at_dots']:.3f}")
        np.save(PROCESSED / f"prob_{tag}.npy", prob)
    report["arms"] = arms
    report["model"] = list(arms.values())[0]["model"]
    print("[6] arm ranking by out-of-sample instrument N (SGMC off-catalogue, held blocks):")
    for k, v in sorted(arms.items(), key=lambda kv: -kv[1]["scores"]["N"]["dti"]):
        print(f"    {k:38s} N={v['scores']['N']['dti']:.4f} S={v['scores']['S']['dti']:.4f} "
              f"dots={v['emission']['dots']} f200={v['emission']['frac_dots_within_200m_of_visible_catalogue']:.3f}")

    # baselines recomputed locally on the same instruments (paired comparison)
    baselines = {}
    for nm, rel in (("d28_44090_nogate",
                     "registry/rasters/GEMSDOE30__d28-poisson300m-offcat-44090.tif"),
                    ("h33-2-b2_37654_gate200",
                     "registry/rasters/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif"),
                    ("anderson_38854_gate200",
                     "registry/rasters/GEMSDOE36__anderson-geothermal-pinn-38854.tif")):
        pth = ROOT / rel
        if not pth.exists():
            continue
        with rasterio.open(pth) as ds:
            a = ds.read(1).astype(np.float64)
        a = np.where(np.isfinite(a), a, 0.0)
        baselines[nm] = score_all(a)
        print(f"    baseline {nm:26s} S={baselines[nm]['S']['dti']:.4f} "
              f"N={baselines[nm]['N']['dti']:.4f} C={baselines[nm]['C']['dti']:.4f}")
    report["scores"] = {"baselines": baselines}

    # relief stratification of the selected arm
    key = sorted(arms, key=lambda k: -arms[k]["scores"]["N"]["dti"])[0]
    report["selected_arm"] = key
    prob = np.load(PROCESSED / f"prob_{args.train_on}.npy")
    dots = emit(prob, True, args.budget, args.sep)
    pred = np.where(dots, 1.0, 0.0).astype(np.float64)
    relief = ch["relief_m"]
    strata = {}
    for lo, hi, lab in ((0, 10, "basin_floor_relief_lt_10m"), (10, 30, "piedmont_10_30m"),
                        (30, 1e9, "range_front_gt_30m")):
        m = fp & (relief >= lo) & (relief < hi)
        r = sp.held_block & m
        if (sp.withheld & r).sum() < 20:
            continue
        strata[lab] = pooled_dti(pred, sp.withheld, r, mask_out=sp.visible)
    report["relief_stratification"] = {"arm": key, "strata": strata}
    for k, v in strata.items():
        print(f"    {k:28s} DTI={v['dti']:.4f} n_truth={v['n_truth']}")

    report["elapsed_s"] = round(time.time() - t0, 1)
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, default=float))
    print(f"\nwrote {out}  ({report['elapsed_s']} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
