#!/usr/bin/env python3
"""LIDAR-02-A runner: channels -> leakage canary -> blocked holdout -> gated emission.

Preregistration: registry/preregistration-lidar02.json (read it first).
Stages: channels | canary | holdout | emit | all
Inputs (hash-pinned mirrors, see registry/data_manifest.json, restored by
scripts/fetch_mirrors.py --dest data/raw):
  data/raw/labels.tif, data/raw/sample_submission.tif,
  data/raw/external/lidar_scarp_features_u8.tif, data/raw/training_features.tif (validate only)
Every score written is HOLDOUT-DTI (src/gems/metric.py).  No organiser score exists.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems.constants import ALPHA, BETA  # noqa: E402
from gems.holdout import spatial_block_holdout  # noqa: E402
from gems.metric import dti_from_terms, tversky_terms  # noqa: E402
from gems66.lidar_channels import LIDAR_BANDS, dequantise, slope_aware_scarp_template  # noqa: E402
from gems66.lidar02_channels import (  # noqa: E402
    SCALES, local_roughness, multiscale_persistence, prominence, rank01)
from lane_run_helper import poisson_disk_dots  # noqa: E402

H, W = 3730, 3292
RAW = ROOT / "data" / "raw"
DERIVED = ROOT / "data" / "derived"
EVID = ROOT / "evidence"
FULL_DOTS = 38000
SEP_TOPK = 2.8
BLOCK_PX, BUFFER_PX, HALO_PX, N_FOLDS = 60, 3, 3, 6

CHANNELS = ["ex_max", "step_max", "upface_max", "downface_max", "cross_max", "relief",
            "coh100", "template_net", "template_net_coh", "snr_amp", "template_veto",
            "lap_mag", "rough1km", "prominence", "frangi_max", "frangi_scale",
            "persist_count", "persist_gate", "field_raw", "field_new", "field_new_cov",
            "prominence_up", "field_promup", "field_promup_cov"]


def log(msg, t0=[time.time()]):  # noqa: B006 - intentional session clock
    print(f"[{time.time()-t0[0]:7.1f}s] {msg}", flush=True)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def base_masks():
    with rasterio.open(RAW / "sample_submission.tif") as s:
        footprint = np.isfinite(s.read(1))
    with rasterio.open(RAW / "labels.tif") as s:
        fault = (s.read(1) > 0) & footprint
    with rasterio.open(RAW / "external" / "lidar_scarp_features_u8.tif") as s:
        lidar = (s.read(LIDAR_BANDS.index("valid") + 1) > 0) & footprint
    return footprint, fault, lidar


def open_channels(mode="r"):
    meta = json.loads((DERIVED / "lidar02_channels.json").read_text())
    mm = np.memmap(DERIVED / "lidar02_channels.f32", dtype="float32", mode=mode,
                   shape=(len(meta["channels"]), H, W))
    return mm, meta


def chan(mm, meta, name):
    return np.array(mm[meta["channels"].index(name)], dtype=np.float32)


# --------------------------------------------------------------------------- E1
def stage_channels():
    DERIVED.mkdir(parents=True, exist_ok=True)
    footprint, fault, lidar = base_masks()
    lidar_p = RAW / "external" / "lidar_scarp_features_u8.tif"
    with rasterio.open(lidar_p) as src:
        raw = src.read()
    stack = {name: dequantise(raw[i], name) for i, name in enumerate(LIDAR_BANDS)}
    del raw
    gc.collect()
    log("dequantised 12 lidar bands")

    mm = np.memmap(DERIVED / "lidar02_channels.f32", dtype="float32", mode="w+",
                   shape=(len(CHANNELS), H, W))
    idx = {n: i for i, n in enumerate(CHANNELS)}

    def put(name, arr):
        mm[idx[name]] = np.nan_to_num(arr, nan=0.0).astype(np.float32, copy=False)

    for n in ("ex_max", "step_max", "upface_max", "downface_max", "cross_max",
              "relief", "coh100"):
        put(n, stack[n])

    tmpl = slope_aware_scarp_template(stack)
    put("template_net", tmpl["template_net"])
    put("template_net_coh", tmpl["template_net_coh"])
    put("snr_amp", tmpl["snr_amp"])
    put("template_veto", tmpl["template_veto"])
    log("slope-aware scarplet template written")

    lap_mag = (np.nan_to_num(stack["lapneg_max"], nan=0.0)
               + np.nan_to_num(stack["lappos_max"], nan=0.0)).astype(np.float32)
    put("lap_mag", lap_mag)
    rough = local_roughness(stack["lapneg_max"], stack["lappos_max"], lidar)
    put("rough1km", rough)
    prom, floor = prominence(tmpl["template_net"], rough, lidar)
    put("prominence", prom)
    prom_up, _ = prominence(stack["upface_max"], rough, lidar)
    put("prominence_up", prom_up)
    log(f"local roughness + prominence written (floor p10={floor:.6g})")

    base_field = np.nan_to_num(tmpl["template_net_coh"], nan=0.0).astype(np.float32)
    del stack, tmpl, lap_mag
    gc.collect()
    multi = multiscale_persistence(base_field, lidar, response_pct=95.0)
    put("frangi_max", multi["frangi_max"])
    put("frangi_scale", multi["frangi_scale"])
    put("persist_count", multi["persist_count"])
    put("persist_gate", multi["persist_gate"])
    log(f"multiscale Frangi/Steger written (c={multi['frangi_c_used']:.4g}, "
        f"persist>=2 cells={int((multi['persist_gate'] > 0).sum()):,})")

    elig = footprint & lidar
    r_net = rank01(base_field, elig)
    r_fr = rank01(multi["frangi_max"], elig)
    field_raw = (0.5 * r_net + 0.5 * r_fr).astype(np.float32)
    put("field_raw", field_raw)
    r_prom = rank01(prom, elig)
    field_new = (r_prom * multi["persist_gate"]).astype(np.float32)
    put("field_new", field_new)
    put("field_new_cov", (field_new + 0.01 * r_prom).astype(np.float32))
    r_promup = rank01(chan(mm, {"channels": CHANNELS}, "prominence_up"), elig)
    f_promup = (r_promup * multi["persist_gate"]).astype(np.float32)
    put("field_promup", f_promup)
    put("field_promup_cov", (f_promup + 0.01 * r_promup).astype(np.float32))
    mm.flush()
    del mm
    gc.collect()
    log("fields written")

    meta = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "channels": CHANNELS,
        "shape": [len(CHANNELS), H, W],
        "inputs": {p.name: {"sha256": sha256_file(p), "bytes": p.stat().st_size}
                   for p in (lidar_p, RAW / "labels.tif", RAW / "sample_submission.tif")},
        "scales_px": list(SCALES), "steger_response_pct": 95.0,
        "frangi_c_used": multi["frangi_c_used"],
        "steger_thresholds": multi["steger_thresholds"],
        "prominence_floor_p10": floor,
        "counts": {"footprint": int(footprint.sum()), "lidar_and_footprint": int(lidar.sum()),
                   "catalogue": int(fault.sum()),
                   "persist_gate_cells": int((multi["persist_gate"] > 0).sum())},
        "scale_disclosure": ("Steger/Frangi at sigma=1.0-4.0 x 100 m cells on the cached "
                             "100 m aggregate of 2 m descriptors; native 2-20 m operators "
                             "NOT measured (1 m DEM unreachable from this sandbox)."),
        "field_definitions": {
            "field_raw": "0.5*rank01(template_net_coh) + 0.5*rank01(frangi_max) over footprint&lidar",
            "field_new": "rank01(prominence) * (persist_count>=2); prominence = max(template_net,0)/(rough1km+p10 floor)",
            "field_new_cov": "field_new + 0.01*rank01(prominence) (max-cover objective; preregistration amendment 2)",
            "field_promup": "rank01(prominence_up) * (persist_count>=2); prominence_up = upface_max/(rough1km+p10 floor), NO veto subtraction (amendment 3 / E2b)",
            "field_promup_cov": "field_promup + 0.01*rank01(prominence_up)",
        },
    }
    (DERIVED / "lidar02_channels.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta["counts"], indent=1))
    return 0


def make_folds(fault, lidar):
    return [spatial_block_holdout(fault, lidar, BLOCK_PX, 1.0 / N_FOLDS, BUFFER_PX,
                                  seed=f, min_lidar_fraction=0.9)
            for f in range(N_FOLDS)]


def fold_domain(sp, footprint, lidar):
    held = sp["held_block"]
    dom = ndimage.binary_dilation(held, structure=np.ones((2 * HALO_PX + 1,) * 2))
    return dom & footprint & lidar


# --------------------------------------------------------------------------- canary
def stage_canary():
    from sklearn.metrics import roc_auc_score
    footprint, fault, lidar = base_masks()
    mm, meta = open_channels()
    folds = make_folds(fault, lidar)
    rng = np.random.default_rng(7)
    rows: dict[str, list[float]] = {}
    withheld = []
    for f, sp in enumerate(folds):
        truth = sp["holdout"]
        withheld.append(int(truth.sum()))
        dom = fold_domain(sp, footprint, lidar)
        bg = dom & ~sp["visible"] & ~sp["held_segment"] & ~sp["buffer_dropped"]
        bg_idx = np.flatnonzero(bg.ravel())
        if bg_idx.size > 150_000:
            bg_idx = rng.choice(bg_idx, 150_000, replace=False)
        t_idx = np.flatnonzero(truth.ravel())
        y = np.concatenate([np.ones(t_idx.size), np.zeros(bg_idx.size)])
        for name in meta["channels"]:
            v = chan(mm, meta, name).ravel()
            x = np.concatenate([v[t_idx], v[bg_idx]]).astype(np.float64)
            if np.unique(x).size < 2:
                continue
            rows.setdefault(name, []).append(float(roc_auc_score(y, x)))
            del v, x
        log(f"canary fold {f}: truth={t_idx.size} bg={bg_idx.size}")
        gc.collect()
    res = {c: {"n_folds": len(v), "auc_mean": round(float(np.mean(v)), 6),
               "auc_max": round(float(np.max(v)), 6), "flag_leakage_if_above": 0.90,
               "leakage_flag": bool(max(v) > 0.90)} for c, v in rows.items()}
    out = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "stage": "E1 leakage canary (LIDAR-02)",
           "instrument": ("per-channel AUC, withheld whole segments (8-connected proxy) vs "
                          "in-domain non-fault background subsampled to 150k, 6 spatial-block folds"),
           "withheld_positives_per_fold": withheld,
           "per_channel": res,
           "flagged": sorted([c for c, v in res.items() if v["leakage_flag"]]),
           "max_auc_observed": round(max(v["auc_max"] for v in res.values()), 6)}
    EVID.mkdir(exist_ok=True)
    (EVID / "lidar02_canary.json").write_text(json.dumps(out, indent=1))
    top = sorted(res.items(), key=lambda kv: -kv[1]["auc_mean"])[:8]
    print(json.dumps({"flagged": out["flagged"], "max_auc": out["max_auc_observed"],
                      "top8": [(k, v["auc_mean"]) for k, v in top]}, indent=1))
    return 0


# --------------------------------------------------------------------------- max-cover
_KERNEL = None


def _kernel():
    global _KERNEL
    if _KERNEL is None:
        dy, dx = np.mgrid[-2:3, -2:3]
        d = np.hypot(dy, dx)
        _KERNEL = np.clip(1.0 - d / 3.0, 0.0, None).astype(np.float32)
    return _KERNEL


def _kernel_max(dots: np.ndarray) -> np.ndarray:
    """max over dots of triangular kernel value (the cover field)."""
    k = _kernel()
    h, w = dots.shape
    padded = np.pad(dots.astype(np.float32), 2, mode="constant")
    out = np.zeros((h, w), dtype=np.float32)
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            kv = float(k[dy + 2, dx + 2])
            if kv <= 0:
                continue
            np.maximum(out, padded[2 + dy:2 + dy + h, 2 + dx:2 + dx + w] * kv, out=out)
    return out


def maxcov_dots(field, eligible, n_dots, batch=200, sep_px=2.0):
    """Batched greedy max-cover: repeatedly place dots where the not-yet-covered
    field mass inside the 300 m triangular kernel is largest (disclosed batch
    approximation to lazy greedy; min separation ``sep_px``)."""
    ys, xs = np.nonzero(eligible)
    if ys.size == 0 or n_dots <= 0:
        return np.zeros(field.shape, bool)
    r0, r1 = max(int(ys.min()) - 3, 0), min(int(ys.max()) + 4, field.shape[0])
    c0, c1 = max(int(xs.min()) - 3, 0), min(int(xs.max()) + 4, field.shape[1])
    F = np.nan_to_num(field[r0:r1, c0:c1], nan=0.0).astype(np.float32)
    E = eligible[r0:r1, c0:c1]
    F[~E] = 0.0  # objective mass only inside the eligible domain (disclosed)
    cover = np.zeros_like(F)
    dots = np.zeros(F.shape, bool)
    suppressed = ~E.copy()
    k = _kernel()
    dy, dx = np.mgrid[-2:3, -2:3]
    keep = (dy * dy + dx * dx) < float(sep_px) ** 2
    dys, dxs = dy[keep], dx[keep]
    placed = 0
    while placed < n_dots:
        gain = ndimage.convolve(F * (1.0 - cover), k, mode="constant")
        gain[suppressed] = -np.inf
        n_cand = min(gain.size, max(batch * 40, 4000))
        cand = np.argpartition(gain.ravel(), -n_cand)[-n_cand:]
        cand = cand[np.argsort(-gain.ravel()[cand], kind="stable")]
        new = np.zeros(F.shape, bool)
        got = 0
        Hc, Wc = F.shape
        for flat in cand.tolist():
            if got >= batch or placed + got >= n_dots:
                break
            y, x = divmod(int(flat), Wc)
            if suppressed[y, x] or not np.isfinite(gain[y, x]):
                continue
            new[y, x] = True
            got += 1
            yy, xx = y + dys, x + dxs
            ok = (yy >= 0) & (yy < Hc) & (xx >= 0) & (xx < Wc)
            suppressed[yy[ok], xx[ok]] = True
        if got == 0:
            break
        dots |= new
        placed += got
        cover = np.maximum(cover, _kernel_max(new))
        del gain, new
        gc.collect()
    out = np.zeros(field.shape, bool)
    out[r0:r1, c0:c1] = dots
    return out


def emit_topk(field, eligible, n_dots):
    dots = poisson_disk_dots(np.nan_to_num(field, nan=0.0).astype(np.float32),
                             eligible, n_dots, SEP_TOPK)
    pred = np.zeros((H, W), dtype=np.float32)
    pred[dots] = 1.0
    return pred


def mean_ci(arr):
    a = np.asarray(arr, dtype=float)
    m = float(a.mean())
    if a.size < 2:
        return m, None
    se = float(a.std(ddof=1) / np.sqrt(a.size))
    return m, [round(m - 1.96 * se, 6), round(m + 1.96 * se, 6)]


# --------------------------------------------------------------------------- E2
def stage_holdout():
    footprint, fault, lidar = base_masks()
    mm, meta = open_channels()
    field_raw = chan(mm, meta, "field_raw")
    field_new = chan(mm, meta, "field_new")
    field_cov = chan(mm, meta, "field_new_cov")
    relief = chan(mm, meta, "relief")
    folds = make_folds(fault, lidar)

    elig_full = footprint & lidar & ~fault
    n_elig_full = int(elig_full.sum())

    strata_base = footprint & lidar
    rv = relief[strata_base]
    q1, q2 = [float(np.percentile(rv, p)) for p in (100 / 3, 200 / 3)]
    strata = np.full((H, W), -1, dtype=np.int8)
    strata[strata_base] = np.digitize(relief[strata_base], [q1, q2]).astype(np.int8)
    stratum_names = ["low_relief_basin", "mid_relief", "high_relief_range_front"]
    del relief
    gc.collect()

    arms = ["random", "raw_topk", "new_topk", "new_maxcov"]
    per_fold = {a: [] for a in arms}
    terms = {a: [0.0, 0.0, 0.0] for a in arms}
    strat_terms = {a: {s: [0.0, 0.0, 0.0] for s in range(3)} for a in arms}
    strat_truth = {s: 0 for s in range(3)}
    dots_per_fold, withheld = [], []

    for f, sp in enumerate(folds):
        truth = sp["holdout"]
        withheld.append(int(truth.sum()))
        dom = fold_domain(sp, footprint, lidar)
        eligible = dom & ~sp["visible"] & ~sp["buffer_dropped"]
        n_dots = int(round(FULL_DOTS * int(eligible.sum()) / n_elig_full))
        dots_per_fold.append(n_dots)
        rng = np.random.default_rng(1000 + f)
        fields = {
            "random": rng.random((H, W)).astype(np.float32),
            "raw_topk": field_raw,
            "new_topk": field_new,
        }
        preds = {}
        for a in ("random", "raw_topk", "new_topk"):
            preds[a] = emit_topk(fields[a], eligible, n_dots)
        del fields["random"]
        d = maxcov_dots(field_cov, eligible, n_dots)
        p = np.zeros((H, W), dtype=np.float32)
        p[d] = 1.0
        preds["new_maxcov"] = p

        for a in arms:
            tp, fp, fn = tversky_terms(preds[a], truth)
            per_fold[a].append(dti_from_terms(tp, fp, fn, ALPHA, BETA))
            terms[a] = [terms[a][0] + tp, terms[a][1] + fp, terms[a][2] + fn]
            for s in range(3):
                ts = truth & (strata == s)
                ps = np.where(strata == s, preds[a], 0.0).astype(np.float32)
                tp2, fp2, fn2 = tversky_terms(ps, ts)
                strat_terms[a][s] = [strat_terms[a][s][0] + tp2,
                                     strat_terms[a][s][1] + fp2,
                                     strat_terms[a][s][2] + fn2]
                del ps
            log(f"fold {f} arm {a}: HOLDOUT-DTI={per_fold[a][-1]:.5f} dots={int((preds[a] > 0).sum())}")
        for s in range(3):
            strat_truth[s] += int((truth & (strata == s)).sum())
        del preds
        gc.collect()

    def summ(a):
        m, ci = mean_ci(perFold := per_fold[a])
        pooled = dti_from_terms(*terms[a], ALPHA, BETA)
        return {"label": "HOLDOUT-DTI", "per_fold": [round(x, 6) for x in perFold],
                "mean": round(m, 6), "ci95": ci, "pooled": round(pooled, 6),
                "terms_pooled": [round(x, 3) for x in terms[a]]}

    def paired(a, b):
        d = np.asarray(per_fold[a]) - np.asarray(per_fold[b])
        m, ci = mean_ci(d)
        return {"mean": round(m, 6), "ci95": ci,
                "ci_lower_gt_0": bool(ci and ci[0] > 0),
                "per_fold": [round(float(x), 6) for x in d]}

    strata_out = {}
    for s in range(3):
        strata_out[stratum_names[s]] = {
            "pooled_withheld_positives": strat_truth[s],
            "judged": bool(strat_truth[s] >= 100),
            **{a: round(dti_from_terms(*strat_terms[a][s], ALPHA, BETA), 6) for a in arms},
        }

    out = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stage": "E2 blocked holdout (LIDAR-02)",
        "evaluator": "src/gems/metric.py :: tversky_terms (alpha=0.2, beta=0.8, triangular R=300 m, eps=1e-9)",
        "holdout_spec": {
            "function": "src/gems/holdout.py spatial_block_holdout",
            "block_px": BLOCK_PX, "buffer_px": BUFFER_PX, "n_folds": N_FOLDS,
            "seeds": list(range(N_FOLDS)), "holdout_fraction": 1.0 / N_FOLDS,
            "min_lidar_fraction": 0.9,
            "segment_ids": "8-connected components (PROXY - authoritative trace IDs not in reachable manifest)",
            "domain": "held blocks dilated 300 m, intersect footprint & lidar",
            "eligibility": "domain & NOT visible-fault pixels & NOT buffer-dropped fault pixels (pixel-exact)",
            "dots_full_grid_budget": FULL_DOTS, "dots_per_fold": dots_per_fold,
            "eligible_full_grid_cells": n_elig_full,
            "withheld_positives_per_fold": withheld,
            "withheld_positives_pooled": int(sum(withheld)),
            "note": "folds are independent seed draws; held blocks may overlap across folds, so pooled terms double-count cells - pooled values are descriptive; gate also requires paired per-fold CIs",
        },
        "arms": {
            "random": "uniform random field, spacing-constrained top-K (mass-matched null)",
            "raw_topk": "field_raw (global ranks) + spacing top-K; deterministic LIDAR-01-like baseline WITHOUT its HGB and catalogue-distance features (disclosed simplification)",
            "new_topk": "field_new (LIDAR-02-A) + spacing top-K",
            "new_maxcov": "field_new_cov (= field_new + 0.01*rank01(prominence), amendment 2) + batched greedy kernel max-cover (PRIMARY)",
        },
        "results": {a: summ(a) for a in arms},
        "paired": {"new_maxcov_minus_raw_topk": paired("new_maxcov", "raw_topk"),
                   "new_maxcov_minus_random": paired("new_maxcov", "random"),
                   "new_topk_minus_raw_topk": paired("new_topk", "raw_topk"),
                   "new_maxcov_minus_new_topk": paired("new_maxcov", "new_topk")},
        "relief_strata": {
            "cuts_m_from_lidar_relief_band_over_footprint_and_lidar": [round(q1, 3), round(q2, 3)],
            "per_stratum_pooled_holdout_dti": strata_out,
        },
        "scale_disclosure": meta["scale_disclosure"],
    }
    (EVID / "lidar02_holdout.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({a: out["results"][a] for a in arms}, indent=1))
    print(json.dumps(out["paired"], indent=1))
    print(json.dumps(out["relief_strata"], indent=1))
    return 0


# --------------------------------------------------------------------------- E3
def gate_from_evidence():
    canary = json.loads((EVID / "lidar02_canary.json").read_text())
    hold = json.loads((EVID / "lidar02_holdout.json").read_text())
    r = hold["results"]
    st = hold["relief_strata"]["per_stratum_pooled_holdout_dti"]
    off_front = False
    off_detail = {}
    for name in ("low_relief_basin", "mid_relief"):
        s = st[name]
        ok = bool(s["judged"] and s["new_maxcov"] > s["random"])
        off_detail[name] = {"judged": s["judged"], "new_maxcov": s["new_maxcov"],
                            "random": s["random"], "beats_random": ok}
        off_front = off_front or ok
    checks = {
        "canary_clear": bool(not canary["flagged"]),
        "pooled_new_gt_raw": bool(r["new_maxcov"]["pooled"] > r["raw_topk"]["pooled"]),
        "paired_new_minus_raw_ci_lower_gt_0": hold["paired"]["new_maxcov_minus_raw_topk"]["ci_lower_gt_0"],
        "paired_new_minus_random_ci_lower_gt_0": hold["paired"]["new_maxcov_minus_random"]["ci_lower_gt_0"],
        "not_confined_to_range_fronts": bool(off_front),
    }
    return checks, off_detail, hold, canary


def stage_emit():
    sys.path.insert(0, str(ROOT / "src"))
    from gems.submission_writer import write_submission
    from gems.validate_submission import validate

    checks, off_detail, hold, canary = gate_from_evidence()
    log(f"gate checks (pre-uniqueness/validator): {checks}")
    if not all(checks.values()):
        out = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "stage": "E3 emission (LIDAR-02)", "gate_checks": checks,
               "off_range_front_detail": off_detail,
               "verdict": "negative - gate not met; no raster emitted for download, no slot spent"}
        (EVID / "lidar02_emission.json").write_text(json.dumps(out, indent=1))
        print(json.dumps(out, indent=1))
        return 3

    footprint, fault, lidar = base_masks()
    mm, meta = open_channels()
    field_new = chan(mm, meta, "field_new")
    field_cov = chan(mm, meta, "field_new_cov")
    eligible = footprint & lidar & ~fault
    dots = maxcov_dots(field_cov, eligible, FULL_DOTS)
    pred = np.zeros((H, W), dtype=np.float32)
    pred[dots] = 1.0
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    stem = f"gems66-lidar02-snrpersist-maxcov-{int(dots.sum())}dots-{ts}"
    note = "LIDAR-02-A local-SNR scarp prominence x cross-scale Steger persistence, kernel max-cover emission"
    assert len(note) <= 140, len(note)
    outdir = ROOT / "artifacts" / "lidar02"
    outdir.mkdir(parents=True, exist_ok=True)
    receipts = {}
    for suffix, fill in (("-nan", None), ("-zeros", 0.0)):
        p = outdir / f"{stem}{suffix}.tif"
        receipts[suffix] = write_submission(
            p, pred, footprint, RAW / "sample_submission.tif",
            name=f"{stem}{suffix}", note=note, outside_fill=fill)
        log(f"wrote {p.name} sha256={receipts[suffix]['sha256'][:16]}...")
    primary = outdir / f"{stem}-nan.tif"
    report = validate(primary, RAW / "sample_submission.tif", RAW / "training_features.tif")
    zeros = outdir / f"{stem}-zeros.tif"
    report_z = validate(zeros, RAW / "sample_submission.tif", RAW / "training_features.tif",
                         outside_policy="either")
    uniq = uniqueness(primary, field_new)
    u_ok = bool(uniq["unique_chance_corrected"] and not uniq["identical_to_any"]
                and (uniq["surface_max_abs_spearman"] is None
                     or uniq["surface_max_abs_spearman"] <= 0.90)
                and uniq["max_abs_spearman_dots"] <= 0.90)
    out = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "stage": "E3 emission (LIDAR-02)", "gate_checks": checks,
           "off_range_front_detail": off_detail,
           "name": stem, "note": note, "note_chars": len(note),
           "dots": int(dots.sum()), "receipts": receipts,
           "validator_nan_primary": report, "validator_zeros_sibling": report_z,
           "uniqueness": uniq, "uniqueness_ok": u_ok,
           "all_gates_met": bool(all(checks.values()) and report["passed"] and u_ok)}
    (EVID / "lidar02_emission.json").write_text(json.dumps(out, indent=1))
    (EVID / "lidar02_uniqueness.json").write_text(json.dumps(uniq, indent=1))
    print(json.dumps({"name": stem, "dots": int(dots.sum()),
                      "validator_passed": report["passed"], "unique_ok": u_ok,
                      "all_gates_met": out["all_gates_met"]}, indent=1))
    return 0 if out["all_gates_met"] else 4


def uniqueness(candidate_path: Path, surface: np.ndarray):
    """Registry + downloads + artifacts scan, reusing check_uniqueness_lane helpers."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "cul", ROOT / "scripts" / "check_uniqueness_lane.py")
    cul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cul)

    cand = cul.read_band1(candidate_path.resolve())
    cand_sha = sha256_file(candidate_path)
    finite = np.isfinite(cand)
    dots = np.zeros((H, W), bool)
    dots[finite] = cand[finite] > 0
    n_dots = int(dots.sum())
    st = np.ones((7, 7), bool)

    # Exclude the candidate's own staged copies (self/sibling in downloads or
    # artifacts): they are byte-identical staging of the candidate, not registry
    # comparators.  Without this, a post-release recheck compares the file to
    # itself and reports a false twin (found 2026-10-20 post-merge recheck).
    self_stem = candidate_path.name.replace("-nan.tif", "").replace("-zeros.tif", "")
    comparators = []
    for d in (ROOT / "registry" / "rasters", ROOT / "docs" / "downloads"):
        comparators += sorted(p for p in d.rglob("*.tif") if self_stem not in p.name)
    comparators += sorted(p for p in (ROOT / "artifacts").rglob("*.tif")
                          if p.resolve() != candidate_path.resolve()
                          and "lidar02" not in str(p))
    comparators += sorted(p for p in (ROOT / "artifacts66").rglob("*.tif"))
    # random-placement control (same recipe as check_uniqueness_lane / IR-73)
    rng = np.random.default_rng(2026)
    rnd = poisson_disk_dots(rng.random((H, W)).astype(np.float32), finite, n_dots, 2.8)

    rows = []
    surf_max = None
    for p in comparators:
        b = cul.read_band1(p)
        if b is None:
            continue
        bf = np.isfinite(b)
        b_dots = np.zeros((H, W), bool)
        b_dots[bf] = b[bf] > 0
        e = {"raster": str(p.relative_to(ROOT)), "sha256": sha256_file(p),
             "identical_sha256": sha256_file(p) == cand_sha,
             "dots": int(b_dots.sum())}
        e["spearman_dots"] = cul.spearman(cand, b)
        e["spearman_surface_preplacement"] = cul.spearman(surface.astype(np.float32), b)
        if e["spearman_surface_preplacement"] is not None:
            v = abs(e["spearman_surface_preplacement"])
            surf_max = v if surf_max is None else max(surf_max, v)
        if b_dots.any() and n_dots:
            dil = ndimage.binary_dilation(b_dots, structure=st)
            e["dot_overlap_within_3px"] = round(float((dots & dil).sum() / n_dots), 6)
            e["random_control_overlap"] = round(float((rnd & dil).sum() / max(int(rnd.sum()), 1)), 6)
            e["lift_over_random"] = round(e["dot_overlap_within_3px"] / max(e["random_control_overlap"], 1e-9), 3)
            e["density_ratio_comparator_over_candidate"] = round(int(b_dots.sum()) / n_dots, 3)
        rows.append(e)
        del b, b_dots
    rho = [abs(r["spearman_dots"]) for r in rows if r.get("spearman_dots") is not None]
    identical = any(r["identical_sha256"] for r in rows)
    literal = [r for r in rows if (r.get("dot_overlap_within_3px") or 0) > 0.70]
    # chance-corrected duplicate rule (IR-73): literal trip AND lift>2 AND comparable density
    corrected = [r for r in literal
                 if (r.get("lift_over_random") or 0) > 2.0
                 and 1 / 3 <= (r.get("density_ratio_comparator_over_candidate") or 0) <= 3.0]
    worst = max(rows, key=lambda r: r.get("dot_overlap_within_3px") or 0, default=None)
    return {
        "candidate": candidate_path.name, "candidate_sha256": cand_sha, "n_dots": n_dots,
        "n_comparators_compared": len(rows),
        "identical_to_any": bool(identical),
        "max_abs_spearman_dots": round(max(rho), 6) if rho else None,
        "surface_max_abs_spearman": round(surf_max, 6) if surf_max is not None else None,
        "worst_raw_overlap": ({"raster": worst["raster"],
                               "dot_overlap_within_3px": worst.get("dot_overlap_within_3px"),
                               "random_control_overlap": worst.get("random_control_overlap"),
                               "lift_over_random": worst.get("lift_over_random"),
                               "density_ratio": worst.get("density_ratio_comparator_over_candidate")}
                              if worst else None),
        "literal_rule_trips_gt_0p70": [{"raster": r["raster"],
                                        "overlap": r["dot_overlap_within_3px"],
                                        "random_control": r.get("random_control_overlap"),
                                        "lift": r.get("lift_over_random")} for r in literal],
        "unique_chance_corrected": bool(not corrected and (not rho or max(rho) <= 0.90)
                                        and (surf_max is None or surf_max <= 0.90)),
        "rule_disclosure": ("Raw >0.70 within-3px trips are reported verbatim above; the "
                            "chance-corrected verdict follows IR-73 (requires lift>2 over a "
                            "matched random placement and comparator density within 3x)."),
        "rows": rows,
    }


STAGES = {"channels": stage_channels, "canary": stage_canary,
          "holdout": stage_holdout, "emit": stage_emit}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=[*STAGES, "all"])
    args = ap.parse_args()
    if args.stage == "all":
        for fn in STAGES.values():
            rc = fn()
            if rc:
                return rc
        return 0
    return STAGES[args.stage]()


if __name__ == "__main__":
    sys.exit(main())
