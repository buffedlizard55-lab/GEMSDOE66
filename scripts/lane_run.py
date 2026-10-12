#!/usr/bin/env python3
"""LIDAR-01 lane runner: leakage canary, spatial-block hide-and-recover holdout, emission.

Stages
------
  canary   per-channel AUC of every candidate feature against withheld whole segments
           (leakage canary; AUC > 0.90 = leakage until proven otherwise)
  sweep    train + emit + pooled DTI for the lane field and the named baselines
  final    fit on the full catalogue and write the score field used for emission

Memory design: the 60-channel stack over 3730x3292 cells is ~2.9 GB, more than the
sandbox RAM, so features are assembled **strip by strip** (STRIP_ROWS rows at a time)
and never materialised as a whole.

Every number written to ``evidence/`` is labelled HOLDOUT-DTI or is an explicit control.
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
from scipy import ndimage
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from gems.constants import ALPHA, BETA  # noqa: E402
from gems.holdout import spatial_block_holdout  # noqa: E402
from gems.metric import dti_from_terms, tversky_terms  # noqa: E402
from lane_run_helper import weighted_disk_dots  # noqa: E402

H, W = 3730, 3292
N_FOLDS = 6
BLOCK_PX = 60           # 6 km spatial blocks
BUFFER_PX = 3           # 300 m buffer around withheld segments
HALO_PX = 3             # 300 m kernel halo around the held blocks (score domain)
STRIP_ROWS = 250        # rows per feature-assembly strip

LANE_CHANNELS = [
    "lid_ex_max", "lid_ex_mean", "lid_step_max", "lid_lapneg_max", "lid_lappos_max",
    "lid_downface_max", "lid_upface_max", "lid_cross_max", "lid_relief", "lid_coh100",
    "lid_strike", "lid_valid",
    "template_antislope", "template_veto", "template_net", "template_net_coh",
    "snr_amp", "antislope_ratio",
    "net_frangi_max", "net_frangi_scale", "net_steger_line", "net_steger_frac300",
    "amp_frangi_max", "amp_frangi_scale", "amp_steger_line", "amp_steger_frac300",
    "coh_recomputed",
    "topo_slope_p90", "topo_slope_max", "topo_steep_frac", "topo_slope_std",
    "topo_relief_local", "topo_curv_prof_absmax", "topo_aspect_coherence",
    "topo_hs_lineament", "topo_dem_mean",
]
OFFICIAL_BANDS = ["det_elev", "det_elev_slope", "iso_grav_anom", "iso_grav_anom_slope",
                  "iso_grav_anom_hg", "iso_grav_anom_vg", "mag_anom", "rtp", "tmi",
                  "tmi_hg", "tmi_vg", "tc", "geod_2ndinv", "geod_shearrate",
                  "geod_dilaterate", "depth_to_base_surf", "cond_surf",
                  "deq_n100a15", "ieq_n100a15"]
DYN_NAMES = ["d_visible", "strike_align", "snr_amp_x_prox", "netcoh_x_prox"]


# --------------------------------------------------------------------------- inputs
def load_base():
    d = ROOT / "data"
    with rasterio.open(d / "sample_submission.tif") as s:
        sample = s.read(1)
    footprint = np.isfinite(sample)
    with rasterio.open(d / "labels.tif") as s:
        labels = s.read(1)
    fault = (labels > 0) & footprint
    meta = json.loads((d / "derived" / "lidar_lane_channels.json").read_text())
    chans = np.memmap(d / "derived" / "lidar_lane_channels.f32", dtype="float32",
                      mode="r", shape=tuple(meta["output"]["shape"]))
    names = list(meta["output"]["channels"])
    lidar = np.array(chans[names.index("lidar_cover")]) > 0.5
    return footprint, fault, chans, names, lidar


def official_feature_names():
    with rasterio.open(ROOT / "data" / "training_features.tif") as s:
        return [str(x).split(" - ")[0] for x in s.descriptions]


# --------------------------------------------------------------------------- geometry
def dist_and_strike(mask):
    """Distance in cells to the nearest True cell, and the local strike of that mask."""
    dist = ndimage.distance_transform_edt(~mask).astype(np.float32)
    gx = ndimage.sobel(dist, axis=1, mode="nearest")
    gy = ndimage.sobel(dist, axis=0, mode="nearest")
    amp = np.hypot(gx, gy) + 1e-9
    nx, ny = gx / amp, gy / amp                      # unit normal, points away from trace
    strike = np.degrees(np.mod(np.arctan2(-nx, ny) + np.pi / 2.0, np.pi))
    return dist, strike.astype(np.float32)


def strike_alignment(cell_strike_deg, fault_strike_deg):
    """|cos(2 dtheta)|: 1 when two strikes are parallel mod 180 deg, 0 at 45 deg."""
    dth = np.radians(cell_strike_deg - fault_strike_deg)
    return np.abs(np.cos(2.0 * dth)).astype(np.float32)


def segment_ids_from_traces(fault):
    """Authoritative whole-fault segment IDs.

    Each fault cell takes the INGENIOUS trace ``record_id`` of the nearest trace vertex in
    ``data/trace_segments_utm11.csv`` (public INGENIOUS Quaternary-fault database, GDR
    submission 1391).  This replaces the 8-connected-component proxy with real whole-trace
    identities, so a held fault is never split across the visible/holdout boundary.
    """
    import pandas as pd
    d = pd.read_csv(ROOT / "data" / "trace_segments_utm11.csv")
    tx0, ty0, dx = 243350.0, 4508550.0, 100.0
    col = np.floor((d[["x0", "x1"]].values.ravel() - tx0) / dx).astype(np.int64)
    row = np.floor((ty0 - d[["y0", "y1"]].values.ravel()) / dx).astype(np.int64)
    rid = np.repeat(d["record_id"].values, 2)
    ok = (col >= 0) & (col < W) & (row >= 0) & (row < H)
    seg_src = np.zeros((H, W), dtype=np.int32)
    seg_src[row[ok], col[ok]] = rid[ok] + 1
    ind = ndimage.distance_transform_edt(seg_src == 0, return_distances=False,
                                         return_indices=True)
    seg = seg_src[tuple(ind)].astype(np.int64)
    seg[~fault] = 0
    return seg


# --------------------------------------------------------------------------- features
class FeatureAssembler:
    """Assembles the model matrix strip by strip from the cached channels."""

    def __init__(self, chans, names, use_lane=True, use_official=True):
        self.chans, self.names = chans, names
        self.lane_idx = [names.index(c) for c in LANE_CHANNELS if c in names]
        self.lane_names = [c for c in LANE_CHANNELS if c in names]
        self.off_names = list(OFFICIAL_BANDS) if use_official else []
        self.use_lane = use_lane
        self.all_names = (self.lane_names if use_lane else []) + \
                         ([f"off_{n}" for n in self.off_names]) + DYN_NAMES
        self.off_order = None
        self.off_mm = None
        if self.off_names:
            all_names = official_feature_names()
            self.off_order = [all_names.index(n) for n in self.off_names]
            self.off_mm = np.memmap(ROOT / "data" / "derived" / "official_bands.f32",
                                    dtype="float32", mode="r",
                                    shape=(len(all_names) if False else 19, H, W))
        self._dyn = None          # (4, H, W) float32 set by set_visible()

    def set_visible(self, visible):
        dist, fstrike = dist_and_strike(visible)
        strike = np.array(self.chans[self.names.index("lid_strike")], dtype=np.float32)
        snr = np.array(self.chans[self.names.index("snr_amp")], dtype=np.float32)
        netcoh = np.array(self.chans[self.names.index("template_net_coh")], dtype=np.float32)
        prox = np.exp(-dist / 5.0).astype(np.float32)
        self._dyn = np.stack([dist, strike_alignment(strike, fstrike),
                              (snr * prox).astype(np.float32),
                              (netcoh * prox).astype(np.float32)]).astype(np.float32)
        del strike, snr, netcoh, prox, fstrike
        gc.collect()

    def rows(self, r0, r1):
        """Feature matrix (n_cells, n_features) for rows [r0, r1)."""
        blocks = []
        n = (r1 - r0) * W
        if self.use_lane:
            b = np.array(self.chans[self.lane_idx, r0:r1, :], dtype=np.float32)
            blocks.append(b.reshape(len(self.lane_idx), n))
            del b
        if self.off_order:
            blocks.append(np.array(self.off_mm[self.off_order, r0:r1, :], dtype=np.float32)
                          .reshape(len(self.off_order), n))
        ndyn = self._dyn.shape[0]
        if ndyn:
            blocks.append(self._dyn[:, r0:r1, :].reshape(ndyn, n))
        X = np.empty((n, sum(b.shape[0] for b in blocks)), dtype=np.float32)
        c = 0
        for b in blocks:
            X[:, c:c + b.shape[0]] = b.T
            c += b.shape[0]
        del blocks
        return X


# --------------------------------------------------------------------------- modelling
def fit_predict(asm: FeatureAssembler, visible, train_ok, predict_mask, seed=0,
                neg_per_pos=4, max_neg=150_000, max_iter=150, regularised=True):
    """HistGradientBoosting on sampled rows; dense prediction over ``predict_mask``."""
    n_pos = int((visible & train_ok).sum())
    rng = np.random.default_rng(seed)
    neg_pool = (train_ok & ~visible)
    neg_idx = np.flatnonzero(neg_pool.ravel())
    rng.shuffle(neg_idx)
    n_neg = int(min(neg_idx.size, max(1, min(max_neg, neg_per_pos * max(n_pos, 1)))))
    sel_neg = np.zeros(H * W, bool)
    sel_neg[neg_idx[:n_neg]] = True
    del neg_idx
    sel_neg = sel_neg.reshape(H, W)
    Xs, ys = [], []
    for r0 in range(0, H, STRIP_ROWS):
        r1 = min(r0 + STRIP_ROWS, H)
        rows = (visible & train_ok)[r0:r1] | sel_neg[r0:r1]
        if not rows.any():
            continue
        X = asm.rows(r0, r1)
        y = np.zeros(X.shape[0], dtype=np.int8)
        y[(visible & train_ok)[r0:r1].ravel()] = 1
        take = rows.ravel()
        Xs.append(X[take])
        ys.append(y[take])
        del X, y
        gc.collect()
    Xtr = np.vstack(Xs)
    ytr = np.concatenate(ys)
    del Xs, ys, sel_neg
    gc.collect()
    # Regularisation matters: with ~1.2 % positives and 58 continuous channels an
    # unregularised HGB drives the training positives to p ~ 1 and everything else to
    # p ~ 0, so the "field" degenerates into a memorised copy of the training catalogue
    # and carries no information about withheld faults (measured: p99 = 2.2e-05,
    # 0.37 % of cells at p > 0.5).  The regularised settings keep a usable, monotone
    # intensity over the whole footprint.
    if regularised:
        clf = HistGradientBoostingClassifier(
            max_iter=max_iter, learning_rate=0.05, max_leaf_nodes=8,
            min_samples_leaf=500, l2_regularization=5.0, max_bins=128,
            class_weight="balanced", early_stopping=False, random_state=seed)
    else:
        clf = HistGradientBoostingClassifier(max_iter=max_iter, learning_rate=0.08,
                                             max_leaf_nodes=31, min_samples_leaf=40,
                                             l2_regularization=1.0, random_state=seed)
    clf.fit(Xtr, ytr)
    del Xtr, ytr
    gc.collect()
    out = np.full(H * W, np.nan, dtype=np.float32)
    for r0 in range(0, H, STRIP_ROWS):
        r1 = min(r0 + STRIP_ROWS, H)
        if not predict_mask[r0:r1].any():
            continue
        X = asm.rows(r0, r1)
        p = clf.predict_proba(X)[:, 1]
        m = predict_mask[r0:r1].ravel()
        out[r0 * W:r1 * W][m] = p[m]
        del X, p
        gc.collect()
    return out.reshape(H, W), clf


# --------------------------------------------------------------------------- emission
def poisson_disk_dots(score, eligible, n_dots, min_sep_px):
    """Greedy spacing-constrained selection over a score field.

    Walks cells in descending score and accepts one only if no accepted dot lies within
    ``min_sep_px`` cells.  Motivation: with alpha = 0.2 an extra dot of unit mass raises
    DTI iff its kernel credit exceeds alpha * DTI (docs/research/metric-derivation.md),
    i.e. inside ~284 m of truth that no existing dot already covers.  Dots closer together
    than that spend mass (each unit costs alpha in the denominator) without buying credit.
    """
    mask = eligible & np.isfinite(score)
    ys, xs = np.nonzero(mask)
    if ys.size == 0 or n_dots <= 0:
        return np.zeros(score.shape, bool)
    order = np.argsort(-score[ys, xs], kind="stable")
    ys, xs = ys[order], xs[order]
    r = int(np.ceil(min_sep_px))
    dy, dx = np.mgrid[-r:r + 1, -r:r + 1]
    keep = (dy * dy + dx * dx) < float(min_sep_px) ** 2
    dys, dxs = dy[keep], dx[keep]
    suppressed = np.zeros((H, W), bool)
    cy, cx = [], []
    for y, x in zip(ys.tolist(), xs.tolist()):
        if len(cy) >= n_dots:
            break
        if suppressed[y, x]:
            continue
        cy.append(y)
        cx.append(x)
        yy = y + dys
        xx = x + dxs
        ok = (yy >= 0) & (yy < H) & (xx >= 0) & (xx < W)
        suppressed[yy[ok], xx[ok]] = True
    out = np.zeros((H, W), bool)
    if cy:
        out[np.asarray(cy, dtype=np.int64), np.asarray(cx, dtype=np.int64)] = True
    return out


def emit(score, eligible, n_dots, min_sep_px):
    dots = poisson_disk_dots(score, eligible, n_dots, min_sep_px)
    pred = np.zeros((H, W), dtype=np.float32)
    pred[dots] = 1.0
    return pred, int(dots.sum())


def score_fold(pred, truth):
    tp, fp, fn = tversky_terms(pred, truth)
    return {"tp": tp, "fp": fp, "fn": fn, "dti": dti_from_terms(tp, fp, fn, ALPHA, BETA)}


# --------------------------------------------------------------------------- folds
def make_folds(fault, lidar, seed0=0):
    seg = segment_ids_from_traces(fault)
    folds = [spatial_block_holdout(fault, lidar, BLOCK_PX, 1.0 / N_FOLDS, BUFFER_PX,
                                   seed0 + f, min_lidar_fraction=0.9, segment_ids=seg)
             for f in range(N_FOLDS)]
    return seg, folds


def fold_domain(sp, footprint, lidar):
    held = sp["held_block"]
    dom = ndimage.binary_dilation(held, structure=np.ones((2 * HALO_PX + 1,) * 2))
    return held, dom & footprint & lidar


def mean_ci(arr):
    a = np.asarray(arr, dtype=float)
    if a.size == 0:
        return float("nan"), None
    m = float(a.mean())
    if a.size < 2:
        return m, None
    se = float(a.std(ddof=1) / np.sqrt(a.size))
    return m, [round(m - 1.96 * se, 6), round(m + 1.96 * se, 6)]


# --------------------------------------------------------------------------- stages
def stage_canary(args, footprint, fault, lidar, chans, names, folds, log):
    asm = FeatureAssembler(chans, names, use_lane=True, use_official=True)
    rows: dict[str, list[float]] = {}
    for f, sp in enumerate(folds):
        _, dom = fold_domain(sp, footprint, lidar)
        truth = sp["holdout"]
        if int(truth.sum()) < 20:
            continue
        asm.set_visible(sp["visible"])
        bg = dom & ~sp["visible"] & ~sp["held_segment"] & footprint
        y = np.concatenate([np.ones(int(truth.sum())), np.zeros(int(bg.sum()))])
        # pull each channel from its strip (strip==whole grid here, one channel at a time)
        for cname in asm.all_names:
            v = _channel(asm, chans, names, cname)
            x = np.nan_to_num(np.concatenate([v[truth], v[bg]]).astype(np.float64))
            if np.unique(x).size < 2:
                continue
            rows.setdefault(cname, []).append(float(roc_auc_score(y, x)))
            del v, x
            gc.collect()
        log(f"canary fold {f}: truth={int(truth.sum())} bg={int(bg.sum())}")
    res = {c: {"n_folds": len(v), "auc_mean": round(float(np.mean(v)), 6),
               "auc_max": round(float(np.max(v)), 6), "flag_leakage_if_above": 0.90,
               "leakage_flag": bool(max(v) > 0.90)} for c, v in rows.items()}
    out = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "stage": "canary",
           "instrument": ("leakage canary: per-channel AUC, withheld whole INGENIOUS trace "
                          "segments vs in-domain non-fault background, 8 spatial-block folds"),
           "per_channel": res,
           "flagged": sorted([c for c, v in res.items() if v["leakage_flag"]]),
           "max_auc_observed": round(max(v["auc_max"] for v in res.values()), 6)}
    (ROOT / "evidence" / "lidar_lane_canary.json").write_text(json.dumps(out, indent=1))
    top = sorted(res.items(), key=lambda kv: -kv[1]["auc_mean"])[:10]
    print(json.dumps({"flagged": out["flagged"], "max_auc": out["max_auc_observed"],
                      "top10": [(k, v["auc_mean"]) for k, v in top]}, indent=1))
    return 0


def _channel(asm, chans, names, cname):
    j = asm.all_names.index(cname)
    if cname.startswith("off_"):
        mm = np.memmap(ROOT / "data" / "derived" / "official_bands.f32", dtype="float32",
                       mode="r", shape=(19, H, W))
        return np.array(mm[official_feature_names().index(cname[4:])], dtype=np.float32)
    if cname in DYN_NAMES:
        return asm._dyn[DYN_NAMES.index(cname)]
    return np.array(chans[names.index(cname)], dtype=np.float32)


def stage_sweep(args, footprint, fault, lidar, chans, names, folds, log):
    """Fit once per fold per variant, cache the score, then sweep emission settings."""
    cache_dir = ROOT / "data" / "derived" / "scores"
    cache_dir.mkdir(parents=True, exist_ok=True)
    all_variants = {
        "random_lidar": dict(kind="random"),
        "distance_only": dict(kind="dist"),
        "lane_full": dict(kind="model", use_lane=True, use_official=True),
        "official_only": dict(kind="model", use_lane=False, use_official=True),
        "lane_channels_only": dict(kind="model", use_lane=True, use_official=False),
    }
    want = [v for v in (args.variants.split(",") if args.variants else all_variants)]
    variants = {k: all_variants[k] for k in want if k in all_variants}
    budgets = [int(b) for b in (args.budgets.split(",") if args.budgets else [args.budget])]
    seps = [float(x) for x in (args.seps.split(",") if args.seps else [args.sep])]
    gammas = [float(g) for g in (args.gammas.split(",") if args.gammas else [args.gamma])]
    emit_cfg = [(b, sp, g) for g in gammas for b in budgets for sp in seps]
    results = {}
    for vname, cfg in variants.items():
        # ---- pass 1: obtain (or reuse) the score field for every fold
        scores = []
        for f, sp in enumerate(folds):
            _, dom = fold_domain(sp, footprint, lidar)
            cache = cache_dir / f"{vname}_f{f}.npy"
            if cache.exists():
                scores.append(np.load(cache))
                continue
            if cfg["kind"] == "random":
                rng = np.random.default_rng(1000 + f)
                sc = rng.random((H, W)).astype(np.float32)
            elif cfg["kind"] == "dist":
                d, _ = dist_and_strike(sp["visible"])
                sc = (-d).astype(np.float32)
            else:
                train_ok = footprint & ~dom & ~sp["held_segment"] & ~sp["buffer_dropped"]
                asm = FeatureAssembler(chans, names, use_lane=cfg["use_lane"],
                                       use_official=cfg["use_official"])
                asm.set_visible(sp["visible"])
                sc, _ = fit_predict(asm, sp["visible"], train_ok, dom, seed=7 + f)
                sc = np.nan_to_num(sc, nan=0.0).astype(np.float32)
                del asm
                gc.collect()
            np.save(cache, sc)
            scores.append(sc)
            log(f"{vname} fold {f}: score field ready")
        # ---- pass 2: evaluate every emission setting on the cached scores
        for budget, sep, gamma in emit_cfg:
            per_fold, dots_all = [], []
            agg = {"tp": 0.0, "fp": 0.0, "fn": 0.0}
            for f, sp in enumerate(folds):
                _, dom = fold_domain(sp, footprint, lidar)
                truth = sp["holdout"]
                if int(truth.sum()) < 20:
                    continue
                budget_f = max(1, int(round(budget * dom.sum() / max(footprint.sum(), 1))))
                if gamma is not None and gamma >= 0 and vname != "random_lidar":
                    pred = np.zeros((H, W), dtype=np.float32)
                    d = weighted_disk_dots(scores[f], dom, budget_f, sep,
                                           gamma=gamma, seed=4242 + f)
                    pred[d] = 1.0
                    ndots = int(d.sum())
                else:
                    pred, ndots = emit(scores[f], dom, budget_f, sep)
                s = score_fold(pred, truth)
                per_fold.append(float(s["dti"]))
                dots_all.append(ndots)
                agg["tp"] += s["tp"]; agg["fp"] += s["fp"]; agg["fn"] += s["fn"]
                del pred
                gc.collect()
            m, ci = mean_ci(per_fold)
            pooled = dti_from_terms(agg["tp"], agg["fp"], agg["fn"], ALPHA, BETA)
            key = f"{vname}|budget={budget}|sep={sep}|gamma={gamma}"
            results[key] = {"label": "HOLDOUT-DTI",
                            "per_fold": [round(float(x), 6) for x in per_fold],
                            "mean": round(m, 6), "ci95": ci,
                            "pooled": round(float(pooled), 6),
                            "dots_per_fold": dots_all,
                            "budget_full_grid": budget, "separation_px": sep,
                            "gamma": gamma}
            log(f"{key}: mean={m:.5f} ci={ci} pooled={pooled:.5f}")
        del scores
        gc.collect()
    out = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "stage": "sweep",
           "protocol": ("spatial-block hide-and-recover: whole INGENIOUS trace segments held "
                        "(authoritative record_id segments), 300 m buffer, lidar-covered "
                        "6 km blocks, truth = withheld segments inside held blocks, score "
                        "domain = held blocks + 300 m halo intersected with the footprint "
                        "and lidar coverage, budget scaled to fold domain area, "
                        "DTI alpha=0.2 beta=0.8 R=300 m"),
           "evaluator": "src/gems/metric.py :: tversky_terms / dti_from_terms",
           "n_folds": len(folds), "variants": results}
    spath = ROOT / "evidence" / "lidar_lane_sweep.json"
    if spath.exists():
        prev = json.loads(spath.read_text())
        prev.get("variants", {}).update(results)
        prev["generated_utc"] = out["generated_utc"]
        out = prev
    spath.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: {"mean": v["mean"], "ci95": v["ci95"], "pooled": v["pooled"]}
                      for k, v in results.items()}, indent=1))
    return 0


def stage_final(args, footprint, fault, lidar, chans, names, log):
    asm = FeatureAssembler(chans, names, use_lane=True, use_official=True)
    asm.set_visible(fault)
    log(f"channels: {len(asm.all_names)}")
    score, _ = fit_predict(asm, fault, footprint, footprint, seed=7)
    score = np.nan_to_num(score, nan=0.0).astype(np.float32)
    np.save(ROOT / "data" / "derived" / "lane_score.npy", score)
    (ROOT / "data" / "derived" / "lane_score.meta.json").write_text(json.dumps(
        {"channels": asm.all_names}, indent=1))
    log(f"score written; footprint cells={int(footprint.sum())}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["canary", "sweep", "final"])
    ap.add_argument("--budget", type=int, default=37654)
    ap.add_argument("--sep", type=float, default=2.8)
    ap.add_argument("--budgets", default=None, help="comma separated dot budgets to sweep")
    ap.add_argument("--seps", default=None, help="comma separated separations (cells) to sweep")
    ap.add_argument("--gammas", default=None, help="comma separated intensity exponents")
    ap.add_argument("--gamma", type=float, default=None)
    ap.add_argument("--variants", default=None,
                    help="comma separated subset of: " + ", ".join(
                        ["random_lidar", "distance_only", "lane_full",
                         "official_only", "lane_channels_only"]))
    args = ap.parse_args()
    t0 = time.time()
    log = lambda m: print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)
    footprint, fault, chans, names, lidar = load_base()
    log(f"footprint {int(footprint.sum())} fault {int(fault.sum())} lidar {int(lidar.sum())}")
    if args.stage == "final":
        return stage_final(args, footprint, fault, lidar, chans, names, log)
    seg, folds = make_folds(fault, lidar)
    log(f"folds built; segments={folds[0]['n_segments']} src={folds[0]['segment_id_source']}")
    if args.stage == "canary":
        return stage_canary(args, footprint, fault, lidar, chans, names, folds, log)
    return stage_sweep(args, footprint, fault, lidar, chans, names, folds, log)


if __name__ == "__main__":
    sys.exit(main())
