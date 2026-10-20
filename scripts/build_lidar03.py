#!/usr/bin/env python3
"""LIDAR-03 — spatial-CV-RETRAINED lidar scarp-channel classifier (assigned lane).

Lane (single paragraph, unchanged): native-resolution lidar scarp channels —
(i) slope-aware scarplet template channels (Sare & Hilley, JOSS 2018,
doi:10.21105/joss.01066; slope-aware extension AGU 2015 T31A-2838) and
(ii) Steger sub-pixel lines (IEEE TPAMI 20(2):113-125, 1998) + Frangi
multiscale Hessian measures (MICCAI 1998, LNCS 1496:130-137) on a
slope-detrended surface, aggregated to 100 m as scarp-pixel fraction,
SNR-weighted amplitude, structure-tensor orientation coherence and dominant
strike; RETRAIN UNDER SPATIAL CV; gate on DTI gain in lidar-covered holdout
blocks not confined to range fronts; float32 EPSG:32611 100 m, NaN only
outside the footprint (plus an all-finite sibling for the observed portal
checker); validate; hash/pixel-agreement vs all prior rasters.

What is NEW here (pre-registered BEFORE any number below was read)
-------------------------------------------------------------------
Every previous field in this repo's lane (LIDAR-01, LIDAR-02, H66x, H67-1)
used HAND-WEIGHTED channel combinations. The lane paragraph's "retrain under
spatial CV" step was never executed. LIDAR-03 executes it:
  * A HistGradientBoosting classifier is trained per spatial (quadrant) fold
    on VISIBLE catalogue positives vs sampled background, using ONLY lane
    channels, and predicts the held-out quadrant. The final field is trained
    on the full visible catalogue. No catalogue-distance feature is used
    (the field must generalise off-catalogue by construction).
  * UNSIGNED slope-aware template amplitude max(upface, downface) replaces
    LIDAR-02's signed antislope net: LIDAR-02's own E1 canary measured
    template_net AUC 0.301 vs SGMC off-catalogue (an ANTI-signal) while
    upface alone scored 0.743 and the veto 0.766 — normal-fault scarps face
    BOTH ways relative to local slope, so polarity subtraction destroyed
    signal. Polarity channels are still offered to the classifier as raw
    inputs; it may learn what subtraction could not.
  * Three ranked-but-never-run channels from the LIDAR-02 hypothesis table
    are computed and canary-tested: L02-B Steger sub-pixel offset density,
    L02-C strike-discontinuity (double-angle strike gradient x coherence),
    L02-D distributed-damage fraction ex_mean/(ex_max+eps).
  * RELIEF-DECONFOUNDING by within-decile ranking: the classifier probability
    is re-ranked inside relief deciles before emission, so dot density cannot
    concentrate on range fronts merely because relief correlates with every
    scarp channel (IR-74 mechanism). LIDAR-02 stratified the EMISSION only;
    re-ranking the FIELD inside strata was never tried.

Named non-fault mimic: fluvial terrace risers / irrigation canal banks
(sharp, persistent, single-sided steps). No pinned cultural-feature mask
(roads/canals/field edges) exists in this checkout — disclosed, not hidden;
the classifier's background sampling includes such terrain wherever it is
unlabelled, which is a mitigation, not a mask.

SCALE DISCLOSURE (mandatory, inherited): input is the hash-pinned mirror
``external/lidar_scarp_features_u8.tif`` — per-100 m-cell extrema of
2 m-working-resolution descriptors derived in owner CI from USGS 3DEP 1 m
tiles (706/716). Frangi/Steger here therefore run at sigma = 1-4 x 100 m
cells (100-400 m) on the slope-detrended aggregate, NOT at native 2-20 m on
raw 1 m DEM tiles (unreachable from this sandbox; official source
https://www.usgs.gov/3d-elevation-program). Native-resolution execution is
NOT measured and is never claimed.

Protocol (budget 3 experiments): E1 leakage canary (feature-alone AUC vs
catalogue and vs SGMC off-catalogue; STOP if any > 0.90) -> E2 quadrant
hide-and-recover (evaluator src/gems/metric.py, alpha 0.2 / beta 0.8 /
triangular R=300 m; catalogue-derived eligibility from visible faults only;
paired bootstrap CI vs mass-matched random) -> E3 emission + uniqueness
(surface Spearman AND final-dot 3 px overlap + density lift vs every
accessible prior raster) + format validation of both siblings.

PRE-REGISTERED GATE (all must hold to offer the download as OK TO SUBMIT):
canary pass; E2 paired-diff 95% CI lower bound > 0; >= 3 of 4 folds won vs
random; low-relief-tercile dot share >= 0.20; |rho| <= 0.90; no identical
raster; no density-comparable lift-duplicate (overlap > 0.70 AND lift > 2);
density-comparable 3 px overlap <= 0.70; validator PASS on both siblings.
Otherwise verdict = negative, bytes kept for audit, site must say NOT OK.
"""
from __future__ import annotations

import gc
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from gems.metric import dti  # noqa: E402
from gems.submission_writer import write_submission, sha256_file  # noqa: E402
from gems.validate_submission import validate  # noqa: E402
from gems66.lidar_channels import (  # noqa: E402
    load_lidar_stack, multiscale_line_fields, steger_lines, orientation_coherence,
)

RAW = ROOT / "data" / "raw"
LIDAR_TIF = RAW / "external" / "lidar_scarp_features_u8.tif"
SGMC_TIF = RAW / "external" / "derived_sgmc_faults_100m_u8.tif"
LABELS_TIF = RAW / "labels.tif"
SAMPLE_TIF = RAW / "sample_submission.tif"
H33_TIF = ROOT / "registry" / "rasters" / "GEMSDOE32__h33-2-b2-zeros.tif"
LIDAR02_TIF = ROOT / "docs" / "downloads" / "gems66-lidar02-sharpersist-stratified-37654dots-20261020T182135Z-zeros.tif"
EVID = ROOT / "evidence"
K_DOTS = 37654
CAT_BUFFER_PX = 2
SEED = 20261020
EVALUATOR = "src/gems/metric.py dti (alpha=0.2, beta=0.8, triangular R=300m, eps=1e-9)"


def rank01(a, mask):
    out = np.zeros(a.shape, np.float32)
    m = mask & np.isfinite(a)
    v = a[m].astype(np.float32, copy=False)
    if v.size == 0:
        return out
    order = np.argsort(v, kind="mergesort")
    ranks = np.empty(v.size, np.float32)
    ranks[order] = np.arange(v.size, dtype=np.float32)
    out[m] = ranks / np.float32(max(int(m.sum()) - 1, 1))
    return out


def auc(score, pos, mask):
    m = mask & np.isfinite(score)
    s, y = score[m].astype(np.float32, copy=False), pos[m]
    n1, n0 = int(y.sum()), int((~y).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    r = np.empty(s.size, np.float64); r[order] = np.arange(1, s.size + 1)
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def load_grid():
    with rasterio.open(SAMPLE_TIF) as s:
        footprint = np.isfinite(s.read(1).astype(np.float64))
    with rasterio.open(LABELS_TIF) as s:
        catalogue = (s.read(1) > 0) & footprint
    with rasterio.open(SGMC_TIF) as s:
        sgmc = (s.read(1) > 0) & footprint
    return footprint, catalogue, sgmc


def build_feature_stack(sgmc_off, catalogue):
    """Return (feat_names, X list of rank01 float32 maps, relief, valid, footprint, canary)."""
    footprint, _c, _s = load_grid()
    st = load_lidar_stack(LIDAR_TIF)
    valid = np.isfinite(st["valid"]) & (np.nan_to_num(st["valid"]) > 0) & footprint

    def f32(name):
        a = np.nan_to_num(st.pop(name), nan=0.0).astype(np.float32); gc.collect(); return a

    canary, feats, names = {}, [], []

    def add(name, arr):
        canary[name] = {"auc_vs_catalogue": auc(arr, catalogue, valid),
                        "auc_vs_sgmc_offcat": auc(arr, sgmc_off, valid)}
        names.append(name); feats.append(rank01(arr, valid))

    relief = f32("relief"); step = f32("step_max"); ex = f32("ex_max"); exm = f32("ex_mean")
    lp = f32("lappos_max"); ln = f32("lapneg_max")
    up = f32("upface_max"); down = f32("downface_max"); cross = f32("cross_max")
    coh = f32("coh100"); strike = f32("strike"); del st["valid"]; gc.collect()

    add("step_max", step); add("ex_max", ex); add("ex_mean", exm)
    add("lappos_max", lp); add("lapneg_max", ln); add("coh100", coh); add("relief", relief)
    add("tmpl_amp_unsigned", np.maximum(up, down))
    add("tmpl_upface", up); add("tmpl_downface", down); add("tmpl_cross", cross)
    add("snr_amp", step * coh)
    add("sharp_ratio", ex / (step + np.float32(0.05)))
    add("curv_asym", (lp - ln) / (lp + ln + np.float32(1e-6)))
    add("damage_frac_L02D", exm / (ex + np.float32(0.01)))
    del ex, exm, lp, ln, up, down, cross; gc.collect()

    persist = np.ones(step.shape, np.float32)
    for sz in (3, 5, 9):
        b = ndimage.uniform_filter(step, sz, mode="nearest").astype(np.float32)
        persist *= np.maximum(rank01(b, valid), np.float32(1e-4)); del b
    add("persist_geomean", persist ** np.float32(1 / 3)); del persist; gc.collect()

    # L02-C strike discontinuity: gradient of double-angle strike vectors, x coherence
    th = np.deg2rad(2.0 * strike.astype(np.float64))
    cx = ndimage.gaussian_filter(np.cos(th), 2.0, mode="nearest")
    sx = ndimage.gaussian_filter(np.sin(th), 2.0, mode="nearest"); del th
    g = np.sqrt(ndimage.sobel(cx, 0) ** 2 + ndimage.sobel(cx, 1) ** 2
                + ndimage.sobel(sx, 0) ** 2 + ndimage.sobel(sx, 1) ** 2).astype(np.float32)
    del cx, sx; g *= coh
    add("strike_disc_L02C", g); del g, strike, coh; gc.collect()

    detr = (step - ndimage.gaussian_filter(step, 4.0, mode="nearest")).astype(np.float32)
    del step; detr[~valid] = np.nan; gc.collect()
    lines = multiscale_line_fields(detr, scales=(1.0, 2.0, 4.0))
    add("frangi_max", np.nan_to_num(lines.pop("frangi_max"), nan=0.0).astype(np.float32))
    add("steger_frac300", np.nan_to_num(lines.pop("steger_frac300"), nan=0.0).astype(np.float32))
    for k in list(lines):
        a = np.nan_to_num(lines.pop(k), nan=0.0).astype(np.float32)
        canary[k] = {"auc_vs_catalogue": auc(a, catalogue, valid),
                     "auc_vs_sgmc_offcat": auc(a, sgmc_off, valid)}; del a
    # L02-B Steger sub-pixel offset density at sigma=2
    resp, _line, inside = steger_lines(np.nan_to_num(detr, nan=0.0), 2.0)
    thr = float(np.percentile(resp[valid], 95))
    dens = ndimage.uniform_filter((inside & (resp > thr) & valid).astype(np.float32), 5,
                                  mode="nearest")
    del resp, _line, inside
    add("steger_offset_density_L02B", dens); del dens
    oc = np.nan_to_num(orientation_coherence(np.nan_to_num(detr, nan=0.0), 2.0), nan=0.0).astype(np.float32)
    add("tensor_coherence", oc); del oc, detr; gc.collect()
    return names, feats, relief, valid, footprint, canary


def train_predict(feats, train_mask, catalogue, valid, dist_cat):
    from sklearn.ensemble import HistGradientBoostingClassifier
    rng = np.random.default_rng(SEED)
    pos = np.where(train_mask & catalogue & valid)
    neg_pool = np.where(train_mask & valid & (dist_cat > CAT_BUFFER_PX))
    npos = min(int(pos[0].size), 60000)
    pi = rng.choice(pos[0].size, size=npos, replace=False)
    ni = rng.choice(neg_pool[0].size, size=min(5 * npos, neg_pool[0].size), replace=False)
    ys = np.concatenate([pos[0][pi], neg_pool[0][ni]]); xs = np.concatenate([pos[1][pi], neg_pool[1][ni]])
    y = np.concatenate([np.ones(npos, np.int8), np.zeros(ni.size, np.int8)])
    X = np.column_stack([f[ys, xs] for f in feats]).astype(np.float32)
    clf = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.06, max_leaf_nodes=31,
                                         min_samples_leaf=100, random_state=SEED)
    clf.fit(X, y); del X, y; gc.collect()
    H, W = valid.shape
    proba = np.zeros((H, W), np.float32)
    for r0 in range(0, H, 256):
        r1 = min(H, r0 + 256)
        Xb = np.column_stack([f[r0:r1].ravel() for f in feats]).astype(np.float32)
        proba[r0:r1] = clf.predict_proba(Xb)[:, 1].astype(np.float32).reshape(r1 - r0, W)
        del Xb
    return proba, {"n_pos": int(npos), "n_neg": int(ni.size)}


def relief_decile_rank(proba, relief, valid):
    out = np.zeros(proba.shape, np.float32)
    qs = np.percentile(relief[valid], np.linspace(0, 100, 11))
    for i in range(10):
        m = valid & (relief >= qs[i]) & (relief <= qs[i + 1] if i == 9 else relief < qs[i + 1])
        if m.sum() > 1:
            out[m] = rank01(proba, m)[m]
    return out


def eligible_mask(valid, footprint, catalogue_visible):
    dist = ndimage.distance_transform_edt(~catalogue_visible)
    return valid & footprint & (dist > CAT_BUFFER_PX)


def greedy_dots(field, elig, k):
    ys, xs = np.where(elig)
    vals = field[ys, xs].astype(np.float64) + np.random.default_rng(SEED).random(ys.size) * 1e-9
    order = np.argsort(-vals, kind="mergesort")
    blocked = np.zeros(field.shape, bool); dots = np.zeros(field.shape, bool)
    H, W = field.shape; n = 0
    disk = [(dy, dx) for dy in range(-2, 3) for dx in range(-2, 3) if dy * dy + dx * dx < 9]
    for idx in order:
        if n >= k: break
        y, x = int(ys[idx]), int(xs[idx])
        if blocked[y, x]: continue
        dots[y, x] = True; n += 1
        for dy, dx in disk:
            yy, xx = y + dy, x + dx
            if 0 <= yy < H and 0 <= xx < W: blocked[yy, xx] = True
    return dots


def random_dots(elig, k, seed):
    ys, xs = np.where(elig)
    pick = np.random.default_rng(seed).choice(ys.size, size=min(k * 3, ys.size), replace=False)
    blocked = np.zeros(elig.shape, bool); dots = np.zeros(elig.shape, bool)
    H, W = elig.shape; n = 0
    disk = [(dy, dx) for dy in range(-2, 3) for dx in range(-2, 3) if dy * dy + dx * dx < 9]
    for idx in pick:
        if n >= k: break
        y, x = int(ys[idx]), int(xs[idx])
        if blocked[y, x]: continue
        dots[y, x] = True; n += 1
        for dy, dx in disk:
            yy, xx = y + dy, x + dx
            if 0 <= yy < H and 0 <= xx < W: blocked[yy, xx] = True
    return dots


def read_dots(path):
    with rasterio.open(path) as s:
        a = s.read(1).astype(np.float64)
    return np.isfinite(a) & (a > 0), np.where(np.isfinite(a), a, 0.0)


def main():
    EVID.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    footprint, catalogue, sgmc = load_grid()
    dist_cat_full = ndimage.distance_transform_edt(~catalogue)
    sgmc_off = sgmc & (dist_cat_full > 3)

    names, feats, relief, valid, footprint, canary = build_feature_stack(sgmc_off, catalogue)
    print(f"features={len(names)} footprint={int(footprint.sum())} valid={int(valid.sum())} "
          f"catalogue={int(catalogue.sum())} sgmc_off={int(sgmc_off.sum())}", flush=True)

    # ---------- E1 leakage canary ----------
    worst_name = max(canary, key=lambda k: max(canary[k].values()))
    worst = float(max(canary[worst_name].values()))
    e1 = {"experiment": "LIDAR-03 E1 leakage canary (feature-alone AUC; stop if > 0.90)",
          "evaluator": EVALUATOR, "channels": canary, "worst_auc": worst,
          "worst_channel": worst_name, "pass": bool(worst <= 0.90),
          "n_sgmc_offcat": int(sgmc_off.sum())}
    (EVID / "lidar03_e1_canary.json").write_text(json.dumps(e1, indent=1))
    print("E1 worst AUC", worst, worst_name, "pass", e1["pass"], flush=True)
    if not e1["pass"]:
        print("LEAKAGE STOP"); return

    # ---------- E2 quadrant hide-and-recover with per-fold retraining ----------
    H, W = valid.shape
    blocks = [(slice(0, H // 2), slice(0, W // 2)), (slice(0, H // 2), slice(W // 2, W)),
              (slice(H // 2, H), slice(0, W // 2)), (slice(H // 2, H), slice(W // 2, W))]
    elig_full = eligible_mask(valid, footprint, catalogue)
    folds, oof = [], np.zeros(valid.shape, np.float32)
    for fi, (rs, cs) in enumerate(blocks):
        block = np.zeros(valid.shape, bool); block[rs, cs] = True
        truth = catalogue & block & valid
        proba, tinfo = train_predict(feats, ~block, catalogue, valid, dist_cat_full)
        oof[block] = proba[block]
        field_f = relief_decile_rank(proba, relief, valid); del proba; gc.collect()
        elig_b = eligible_mask(valid, footprint, catalogue & ~block) & block
        k_fold = max(int(round(K_DOTS * elig_b.sum() / max(int(elig_full.sum()), 1))), 1)
        cand = greedy_dots(field_f, elig_b, k_fold); del field_f
        rnd = random_dots(elig_b, int(cand.sum()), SEED + fi)
        pc = np.zeros(valid.shape, np.float32); pc[cand] = 1.0
        pr = np.zeros(valid.shape, np.float32); pr[rnd] = 1.0
        row = {"fold": fi, "withheld_positives": int(truth.sum()), "k_fold": int(cand.sum()),
               "candidate_dti": float(dti(pc, truth)), "random_dti": float(dti(pr, truth)),
               "train": tinfo}
        folds.append(row); print("fold", fi, row, flush=True)
        del pc, pr, cand, rnd; gc.collect()

    def ci(vals):
        v = np.array(vals); rng = np.random.default_rng(SEED)
        bs = [float(rng.choice(v, size=v.size, replace=True).mean()) for _ in range(2000)]
        return float(v.mean()), [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
    cand_m, cand_ci = ci([f["candidate_dti"] for f in folds])
    rnd_m, rnd_ci = ci([f["random_dti"] for f in folds])
    diff_m, diff_ci = ci([f["candidate_dti"] - f["random_dti"] for f in folds])
    oof_auc = auc(oof, catalogue, valid); del oof
    e2 = {"experiment": "LIDAR-03 E2 quadrant hide-and-recover, classifier RETRAINED per fold on visible catalogue only; eligibility buffer from visible catalogue only",
          "label": "HOLDOUT-DTI", "evaluator": EVALUATOR, "folds": folds,
          "candidate_mean": cand_m, "candidate_ci95": cand_ci,
          "random_mean": rnd_m, "random_ci95": rnd_ci,
          "paired_diff_mean": diff_m, "paired_diff_ci95": diff_ci,
          "folds_won": int(sum(f["candidate_dti"] > f["random_dti"] for f in folds)),
          "total_withheld_positives": int(sum(f["withheld_positives"] for f in folds)),
          "oof_proba_auc_vs_catalogue": float(oof_auc),
          "feature_names": names,
          "note": "Catalogue-truth holdout measures recovery of withheld MAPPED segments; it cannot certify discovery of unmapped faults. Reported for falsification per protocol."}
    (EVID / "lidar03_e2_holdout.json").write_text(json.dumps(e2, indent=1))
    print("E2 candidate", cand_m, cand_ci, "random", rnd_m, rnd_ci, "diff", diff_m, diff_ci, "OOF AUC", oof_auc, flush=True)

    # ---------- E3 final emission ----------
    proba, tinfo_full = train_predict(feats, np.ones(valid.shape, bool), catalogue, valid, dist_cat_full)
    for f in feats: del f
    del feats; gc.collect()
    field = relief_decile_rank(proba, relief, valid); del proba; gc.collect()
    dots = greedy_dots(field, elig_full, K_DOTS)
    pred = np.zeros(valid.shape, np.float32); pred[dots] = 1.0; pred[~footprint] = 0.0
    ctrl = {"candidate": float(dti(pred, sgmc_off))}
    for tag, p in [("h33_2_b2", H33_TIF), ("lidar02", LIDAR02_TIF)]:
        if p.exists():
            dm, _ = read_dots(p); pr2 = np.zeros(valid.shape, np.float32); pr2[dm] = 1.0
            ctrl[tag] = float(dti(pr2, sgmc_off)); ctrl[tag + "_dots"] = int(dm.sum()); del pr2, dm
    rnd_full = random_dots(elig_full, int(dots.sum()), SEED + 99)
    pr2 = np.zeros(valid.shape, np.float32); pr2[rnd_full] = 1.0
    ctrl["random_matched"] = float(dti(pr2, sgmc_off)); del pr2
    qs = np.percentile(relief[valid], [33.333, 66.667])
    strata = [relief <= qs[0], (relief > qs[0]) & (relief <= qs[1]), relief > qs[1]]
    low_share = float((dots & strata[0]).sum() / max(int(dots.sum()), 1))
    print("SGMC control", ctrl, "low_relief_share", low_share, flush=True)

    rng = np.random.default_rng(SEED)
    samp = rng.choice(np.where(footprint.ravel())[0], size=100000, replace=False)
    xf = field.ravel()[samp].astype(float); xr = np.argsort(np.argsort(xf))
    cand_ys, cand_xs = np.where(dots); rnd_ys, rnd_xs = np.where(rnd_full)
    reg_files = (sorted((ROOT / "registry" / "rasters").glob("*.tif"))
                 + sorted((ROOT / "docs" / "downloads").glob("*.tif"))
                 + sorted((ROOT / "artifacts").rglob("*.tif"))
                 + sorted((ROOT / "artifacts66").rglob("*.tif")))
    uniq = []
    for p in reg_files:
        try: dm, vals = read_dots(p)
        except Exception as e: uniq.append({"file": p.name, "error": str(e)}); continue
        if dm.shape != dots.shape: uniq.append({"file": p.name, "error": f"shape {dm.shape}"}); continue
        y = vals.ravel()[samp].astype(float); yr = np.argsort(np.argsort(y))
        rho = float(np.corrcoef(xr, yr)[0, 1]) if y.std() > 0 else 0.0
        dist = ndimage.distance_transform_edt(~dm)
        ov = float((dist[cand_ys, cand_xs] <= 3).mean()); ovr = float((dist[rnd_ys, rnd_xs] <= 3).mean())
        uniq.append({"file": p.name, "ref_dots": int(dm.sum()), "surface_spearman_sample100k": rho,
                     "dot_overlap3px": ov, "random_overlap3px": ovr,
                     "lift": float(ov / ovr) if ovr > 0 else None,
                     "identical_dots": bool((dm == dots).all()), "sha256": sha256_file(p)})
        del dm, vals
    ok = [u for u in uniq if "error" not in u]
    max_rho = float(max(abs(u["surface_spearman_sample100k"]) for u in ok))
    comp = [u for u in ok if K_DOTS / 3 <= u["ref_dots"] <= K_DOTS * 3]
    max_ov_comp = float(max((u["dot_overlap3px"] for u in comp), default=0.0))
    worst_comp = max(comp, key=lambda u: u["dot_overlap3px"], default=None)
    dup = [u for u in comp if u["dot_overlap3px"] > 0.70 and (u["lift"] or 0) > 2.0]
    uniq_rec = {"n_compared": len(uniq), "n_readable": len(ok), "max_abs_surface_spearman": max_rho,
                "max_dot_overlap3px_raw": float(max((u["dot_overlap3px"] for u in ok), default=0.0)),
                "max_dot_overlap3px_density_comparable": max_ov_comp, "worst_comparable": worst_comp,
                "duplicate_under_lift_rule": dup, "any_identical": any(u["identical_dots"] for u in ok),
                "per_raster": uniq}
    (EVID / "lidar03_uniqueness.json").write_text(json.dumps(uniq_rec, indent=1))
    print("uniq rho", max_rho, "ov_comp", max_ov_comp, "dup", len(dup), flush=True)

    gate = {"canary_pass": e1["pass"], "holdout_diff_ci_lower_gt0": bool(diff_ci[0] > 0),
            "folds_won_ge3": bool(e2["folds_won"] >= 3),
            "low_relief_dot_share": low_share, "low_relief_share_ge_0p20": bool(low_share >= 0.20),
            "max_abs_rho_le_0p90": bool(max_rho <= 0.90), "no_identical": not uniq_rec["any_identical"],
            "no_lift_duplicate": len(dup) == 0, "comparable_overlap_le_0p70": bool(max_ov_comp <= 0.70)}
    gate["all_pass_pre_format"] = all(v for v in gate.values() if isinstance(v, bool))
    print("GATE(pre-format)", gate, flush=True)

    base = f"gems66-lidar03-cvretrain-reliefdecile-{int(dots.sum())}dots-{ts}"
    name, note = base[:120], "LIDAR-03 spatial-CV retrained scarp/Steger/Frangi classifier, relief-decile ranked; GEMSDOE66 run card lidar03"[:140]
    outdir = ROOT / "artifacts" / "lidar03"; outdir.mkdir(parents=True, exist_ok=True)
    receipts = {}
    for suffix, fill, pol in [("zeros", 0.0, "either"), ("nan", None, "nan")]:
        out = outdir / f"{base}-{suffix}.tif"
        rec = write_submission(out, pred, footprint, SAMPLE_TIF, overwrite=True,
                               name=name, note=note, outside_fill=fill)
        # Full footprint checks need the pinned training-features raster; without it the
        # fail-closed validator returns passed=False with SKIPPED footprint checks
        # (measured on the first LIDAR-03 run - see evidence/lidar03_validate_*.json vs
        # evidence/lidar03_validate_*_full.json). Pass it whenever it has been restored.
        feats = RAW / "training_features.tif"
        v = validate(out, reference_path=SAMPLE_TIF,
                     features_path=feats if feats.exists() else None, outside_policy=pol)
        zpath = outdir / f"{base}-{suffix}.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z: z.write(out, arcname=out.name)
        receipts[suffix] = {"file": out.name, "zip": zpath.name, "sha256": sha256_file(out),
                            "zip_sha256": sha256_file(zpath),
                            "validator_passed": bool(v.get("passed")), "validator": v,
                            "writer_receipt": rec}
        (EVID / f"lidar03_validate_{suffix}.json").write_text(json.dumps(v, indent=1, default=str))
        print(suffix, receipts[suffix]["sha256"][:16], "validator_passed", receipts[suffix]["validator_passed"], flush=True)
    gate["validator_pass_both"] = all(r["validator_passed"] for r in receipts.values())
    gate["all_pass"] = bool(gate["all_pass_pre_format"] and gate["validator_pass_both"])
    rec_all = {"generated_utc": ts, "name": name, "note": note, "note_chars": len(note),
               "dots": int(dots.sum()), "train_full": tinfo_full, "sgmc_control": ctrl,
               "low_relief_dot_share": low_share, "gate": gate, "receipts": receipts,
               "inputs_sha256": {str(p.relative_to(ROOT)): sha256_file(p)
                                 for p in [LIDAR_TIF, LABELS_TIF, SAMPLE_TIF, SGMC_TIF]}}
    (EVID / "lidar03_e3_emission.json").write_text(json.dumps(rec_all, indent=1, default=str))
    print("DONE", base, "gate_all_pass", gate["all_pass"], flush=True)


if __name__ == "__main__":
    main()
