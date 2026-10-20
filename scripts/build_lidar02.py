#!/usr/bin/env python3
"""LIDAR-02 — relief-stratified sharpness x persistence x polarity scarp lane.

Lane (assigned, single paragraph): native-resolution lidar scarp channels —
(i) slope-aware scarplet template channels (Sare & Hilley, JOSS 2018,
doi:10.21105/joss.01066; slope-aware extension AGU 2015 T31A-2838) and
(ii) Steger sub-pixel lines (IEEE TPAMI 20(2):113-125, 1998) + Frangi
multiscale Hessian line measures (MICCAI 1998, LNCS 1496:130-137) on a
slope-detrended surface, aggregated to 100 m as scarp-pixel fraction,
SNR-weighted amplitude, orientation coherence and dominant strike.

What is NEW vs every prior raster in this repo (pre-registered here, before
any number below was read):
  * G-01 sharpness / relative-age gate  A = ex_max/(step_max+eps) plus
    curvature asymmetry (lappos-lapneg)/(lappos+lapneg) — no prior field in
    this repo uses an amplitude/sharpness ratio (registry hypotheses G-01,
    "RANKED, NOT RUN").
  * G-02 three-scale along-strike persistence product (geometric mean of
    300/500/900 m box-mean ranks) — never combined in this repo.
  * G-03 cross-trace polarity pairing (antislope upface minus the stronger
    of downface/cross veto, from the shared slope-aware template).
  * RELIEF-STRATIFIED EMISSION: the dot budget is allocated across relief
    terciles in proportion to FOOTPRINT SHARE (truth-free), directly
    targeting IR-74 (LIDAR-01's gain reversed on the basin floor, lift
    0.34). No prior emission in this repo stratifies by relief.
Named non-fault mimic: fluvial terrace risers / canal banks (sharp,
single-sided, persistent) — suppressed, not eliminated, by the antislope
polarity term and the cross-slope veto. No pinned cultural-feature mask
(roads/canals) is reachable in this checkout; that gap is disclosed, not
papered over.

SCALE DISCLOSURE (mandatory, inherited): the pinned input
``external/lidar_scarp_features_u8.tif`` holds per-100 m-cell extrema of
2 m-working-resolution descriptors derived in owner CI from USGS 3DEP 1 m
tiles (706/716). Frangi/Steger below therefore run at sigma = 1-4 x 100 m
cells (100-400 m) on the detrended aggregate, NOT at native 2-20 m on the
1 m DEM (raw tiles unreachable from this sandbox). Every number is
labelled accordingly.

Protocol: E1 leakage canary (feature-alone AUC, stop > 0.90) -> E2 spatial
hide-and-recover holdout (pooled DTI, alpha 0.2 / beta 0.8 / 300 m
triangular kernel, evaluator src/gems/metric.py) vs mass-matched random,
the h33-2-b2 incumbent and LIDAR-01, with relief strata -> E3 emission +
uniqueness (surface rank-corr AND final-dot 3 px overlap + lift vs every
registry raster) + format validation. Download is offered only if the
gate in ``gate()`` passes; otherwise the verdict is negative and the site
must say DO NOT SUBMIT.
"""
from __future__ import annotations

import hashlib
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
from gems.metric import dti, tversky_terms, dti_from_terms  # noqa: E402
from gems.submission_writer import write_submission, sha256_file  # noqa: E402
from gems.validate_submission import validate  # noqa: E402
from gems66.lidar_channels import (  # noqa: E402
    load_lidar_stack, slope_aware_scarp_template, multiscale_line_fields,
    orientation_coherence, dominant_strike_deg,
)

RAW = ROOT / "data" / "raw"
LIDAR_TIF = RAW / "external" / "lidar_scarp_features_u8.tif"
SGMC_TIF = RAW / "external" / "derived_sgmc_faults_100m_u8.tif"
LABELS_TIF = RAW / "labels.tif"
SAMPLE_TIF = RAW / "sample_submission.tif"
H33_TIF = ROOT / "registry" / "rasters" / "GEMSDOE32__h33-2-b2-zeros.tif"
LIDAR01_TIF = ROOT / "docs" / "downloads" / "gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z.tif"
EVID = ROOT / "evidence"
K_DOTS = 37654          # matched to the h33-2-b2 / LIDAR-01 budget for comparability
CAT_BUFFER_PX = 2       # 200 m: the measured 0.2708 -> h33-2-b2 lesson (dead mass on catalogue)
MIN_SEP_PX = 3.0
SEED = 20261020
EVALUATOR = "src/gems/metric.py dti (alpha=0.2, beta=0.8, triangular R=300m, eps=1e-9)"


def rank01(a: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Percentile rank in [0,1] over finite cells in mask; 0 elsewhere. float32-frugal."""
    out = np.zeros(a.shape, np.float32)
    m = mask & np.isfinite(a)
    v = a[m].astype(np.float32, copy=False)
    if v.size == 0:
        return out
    order = np.argsort(v, kind="mergesort")
    ranks = np.empty(v.size, np.float32)
    ranks[order] = np.arange(v.size, dtype=np.float32)
    del order, v
    out[m] = ranks / np.float32(max(int(m.sum()) - 1, 1))
    return out


def auc(score: np.ndarray, pos: np.ndarray, mask: np.ndarray) -> float:
    m = mask & np.isfinite(score)
    s, y = score[m].astype(np.float32, copy=False), pos[m]
    n1, n0 = int(y.sum()), int((~y).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    r = np.empty(s.size, np.float64); r[order] = np.arange(1, s.size + 1)
    out = float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))
    del order, r, s, y
    return out


def load_grid():
    with rasterio.open(SAMPLE_TIF) as s:
        sample = s.read(1).astype(np.float64)
    footprint = np.isfinite(sample)
    with rasterio.open(LABELS_TIF) as s:
        catalogue = (s.read(1) > 0) & footprint
    with rasterio.open(SGMC_TIF) as s:
        sgmc = (s.read(1) > 0) & footprint
    return footprint, catalogue, sgmc


def build_channels(sgmc_off, catalogue):
    """Memory-frugal (3 GB sandbox): rank + canary each channel, then free it.

    Returns (field, relief, valid, footprint, canary_dict, parts_for_canary).
    Field formula is identical to the pre-registered one in the module docstring.
    """
    import gc
    footprint, _cat, _sg = load_grid()
    stack64 = load_lidar_stack(LIDAR_TIF)   # template code returns float64; cast+free per band
    valid = np.isfinite(stack64["valid"]) & (np.nan_to_num(stack64["valid"]) > 0) & footprint
    def f32(name):
        a = np.nan_to_num(stack64.pop(name), nan=0.0).astype(np.float32)
        gc.collect(); return a
    canary = {}
    def can(name, arr):
        canary[name] = {"auc_vs_sgmc_offcat": auc(arr, sgmc_off, valid),
                        "auc_vs_catalogue": auc(arr, catalogue, valid)}
    relief = f32("relief"); can("relief", relief)
    step = f32("step_max"); can("step_max", step)
    ex = f32("ex_max"); can("ex_max", ex)
    r_step, r_ex = rank01(step, valid), rank01(ex, valid)
    sharp_raw = (ex / (step + np.float32(0.05))).astype(np.float32); del ex; gc.collect()
    can("sharp_ratio", sharp_raw); r_sharp = rank01(sharp_raw, valid); del sharp_raw
    lp, ln = f32("lappos_max"), f32("lapneg_max")
    asym = ((lp - ln) / (lp + ln + np.float32(1e-6))).astype(np.float32); del lp, ln; gc.collect()
    can("curv_asym", asym); r_asym = rank01(asym, valid); del asym
    sharp = (0.5 * r_sharp + 0.5 * r_asym).astype(np.float32); del r_sharp, r_asym
    can("part_sharp", sharp)
    # persistence product of box-mean ranks (300/500/900 m)
    persist = np.ones(step.shape, np.float32)
    for sz, nm in [(3, "persist300"), (5, "persist500"), (9, "persist900")]:
        b = ndimage.uniform_filter(step, sz, mode="nearest").astype(np.float32)
        can(nm, b); persist *= np.maximum(rank01(b, valid), np.float32(1e-4)); del b; gc.collect()
    persist = rank01(persist ** np.float32(1 / 3), valid); can("part_persist", persist)
    # slope-aware scarplet template (shared code) on the remaining bands
    mini = {k: stack64[k] for k in ("upface_max", "downface_max", "cross_max")}
    mini["step_max"] = step.astype(np.float64); mini["coh100"] = stack64["coh100"]
    tmpl = slope_aware_scarp_template(mini); del mini
    net = np.nan_to_num(tmpl.pop("template_net"), nan=0.0).astype(np.float32)
    can("template_net", net); polarity = rank01(net, valid); del net
    can("part_polarity", polarity)
    for k in list(tmpl):
        a = np.nan_to_num(tmpl.pop(k), nan=0.0).astype(np.float32); can(k, a); del a
    coh = f32("coh100"); can("coh100", coh); r_coh = rank01(coh, valid); del coh
    exm = f32("ex_mean"); can("ex_mean", exm); del exm
    for k in list(stack64):  # remaining raw bands: canary only
        a = f32(k); can(k, a); del a
    gc.collect()
    # slope-detrended surface -> Frangi + Steger (shared multiscale code)
    detr = (step - ndimage.gaussian_filter(step, 4.0, mode="nearest")).astype(np.float32)
    del step; gc.collect()
    detr[~valid] = np.nan
    lines = multiscale_line_fields(detr, scales=(1.0, 2.0, 4.0))
    fr = np.nan_to_num(lines.pop("frangi_max"), nan=0.0).astype(np.float32)
    can("frangi_max", fr); r_fr = rank01(fr, valid); del fr
    stg = np.nan_to_num(lines.pop("steger_frac300"), nan=0.0).astype(np.float32)
    can("steger_frac300", stg); r_stg = rank01(stg, valid); del stg
    for k in list(lines):
        a = np.nan_to_num(lines.pop(k), nan=0.0).astype(np.float32); can(k, a); del a
    oc = np.nan_to_num(orientation_coherence(np.nan_to_num(detr, nan=0.0), 2.0), nan=0.0).astype(np.float32)
    can("orient_coh", oc); del oc, detr; gc.collect()
    amp_gate = (0.5 + 0.5 * np.sqrt(np.maximum(r_step * r_ex, np.float32(0)))).astype(np.float32)
    del r_step, r_ex
    field = ((0.25 * sharp + 0.25 * persist + 0.20 * polarity
              + 0.15 * r_fr + 0.10 * r_coh + 0.05 * r_stg) * amp_gate).astype(np.float32)
    del sharp, persist, polarity, r_fr, r_coh, r_stg, amp_gate; gc.collect()
    field = rank01(field, valid)
    can("field", field)
    return field, relief, valid, footprint, canary


def eligible_mask(valid, footprint, catalogue_visible):
    dist_cat = ndimage.distance_transform_edt(~catalogue_visible)
    return valid & footprint & (dist_cat > CAT_BUFFER_PX), dist_cat


def greedy_dots(field, elig, k, rng_tiebreak=True):
    """Top-k by field with >= MIN_SEP_PX Euclidean separation (disk r=2 blocked)."""
    ys, xs = np.where(elig)
    vals = field[ys, xs].astype(np.float64)
    if rng_tiebreak:
        vals = vals + np.random.default_rng(SEED).random(vals.size) * 1e-9
    order = np.argsort(-vals, kind="mergesort")
    blocked = np.zeros(field.shape, bool)
    dots = np.zeros(field.shape, bool)
    H, W = field.shape
    n = 0
    disk = [(dy, dx) for dy in range(-2, 3) for dx in range(-2, 3) if dy * dy + dx * dx < 9]
    for idx in order:
        if n >= k:
            break
        y, x = int(ys[idx]), int(xs[idx])
        if blocked[y, x]:
            continue
        dots[y, x] = True; n += 1
        for dy, dx in disk:
            yy, xx = y + dy, x + dx
            if 0 <= yy < H and 0 <= xx < W:
                blocked[yy, xx] = True
    return dots, n


def stratified_dots(field, elig, relief, k):
    """Allocate k across relief terciles by eligible-footprint share (truth-free)."""
    qs = np.percentile(relief[elig], [33.333, 66.667])
    strata = [elig & (relief <= qs[0]), elig & (relief > qs[0]) & (relief <= qs[1]),
              elig & (relief > qs[1])]
    shares = np.array([s.sum() for s in strata], float); shares /= shares.sum()
    ks = np.floor(shares * k).astype(int); ks[np.argmax(shares)] += k - ks.sum()
    dots = np.zeros(field.shape, bool); placed = []
    # global separation: place stratum by stratum, respecting already-placed dots
    blocked_from = np.zeros(field.shape, bool)
    for s_mask, kk in zip(strata, ks):
        d, n = greedy_dots(field, s_mask & ~blocked_from, int(kk))
        dots |= d; placed.append(int(n))
        blocked_from |= ndimage.binary_dilation(d, structure=np.ones((5, 5), bool))
    return dots, {"relief_tercile_cuts_m": [float(q) for q in qs],
                  "strata_eligible_share": [float(s) for s in shares],
                  "strata_k": [int(x) for x in ks], "strata_placed": placed}


def random_dots(elig, k, seed):
    ys, xs = np.where(elig)
    rng = np.random.default_rng(seed)
    pick = rng.choice(ys.size, size=min(k * 3, ys.size), replace=False)
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
    del dist_cat_full
    field, relief, valid, footprint, canary = build_channels(sgmc_off, catalogue)
    print(f"footprint={footprint.sum()} lidar_valid={valid.sum()} catalogue={catalogue.sum()} sgmc_off={sgmc_off.sum()}", flush=True)

    # ---------- E1 leakage canary (computed inside build_channels, free-as-you-go) ----------
    worst = max(max(v.values()) for v in canary.values())
    e1 = {"experiment": "E1 leakage canary (feature-alone AUC; stop if > 0.90)",
          "evaluator": EVALUATOR, "channels": canary, "worst_auc": float(worst),
          "pass": bool(worst <= 0.90), "n_sgmc_offcat": int(sgmc_off.sum())}
    (EVID / "lidar02_e1_canary.json").write_text(json.dumps(e1, indent=1))
    print("E1 worst AUC", worst, "pass", e1["pass"])
    if not e1["pass"]:
        print("LEAKAGE STOP"); return

    # ---------- E2 spatial hide-and-recover holdout (4 quadrant blocks) ----------
    H, W = field.shape
    blocks = [(slice(0, H // 2), slice(0, W // 2)), (slice(0, H // 2), slice(W // 2, W)),
              (slice(H // 2, H), slice(0, W // 2)), (slice(H // 2, H), slice(W // 2, W))]
    elig_full, _ = eligible_mask(valid, footprint, catalogue)
    folds = []
    for fi, (rs, cs) in enumerate(blocks):
        block = np.zeros(field.shape, bool); block[rs, cs] = True
        truth = catalogue & block & valid
        visible_cat = catalogue & ~block
        elig_b, _ = eligible_mask(valid, footprint, visible_cat)
        elig_b &= block
        k_fold = max(int(round(K_DOTS * elig_b.sum() / max(elig_full.sum(), 1))), 1)
        cand, sinfo = stratified_dots(field, elig_b, relief, k_fold)
        rnd = random_dots(elig_b, int(cand.sum()), SEED + fi)
        pred_c = np.zeros(field.shape, np.float32); pred_c[cand] = 1.0
        pred_r = np.zeros(field.shape, np.float32); pred_r[rnd] = 1.0
        row = {"fold": fi, "withheld_positives": int(truth.sum()), "k_fold": int(cand.sum()),
               "candidate_dti": float(dti(pred_c, truth)), "random_dti": float(dti(pred_r, truth)),
               "strata": sinfo}
        for tag, p in [("h33", H33_TIF), ("lidar01", LIDAR01_TIF)]:
            dmask, _ = read_dots(p)
            pr = np.zeros(field.shape, np.float32); pr[dmask & block] = 1.0
            row[tag + "_dots_in_block"] = int((dmask & block).sum())
            row[tag + "_dti_asis"] = float(dti(pr, truth))
        folds.append(row); print("fold", fi, row["candidate_dti"], row["random_dti"], row["withheld_positives"])
    def ci(vals):
        v = np.array(vals); m = float(v.mean())
        rng = np.random.default_rng(SEED)
        bs = [float(rng.choice(v, size=v.size, replace=True).mean()) for _ in range(2000)]
        return m, [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
    cand_m, cand_ci = ci([f["candidate_dti"] for f in folds])
    rnd_m, rnd_ci = ci([f["random_dti"] for f in folds])
    diffs = [f["candidate_dti"] - f["random_dti"] for f in folds]
    diff_m, diff_ci = ci(diffs)
    total_withheld = int(sum(f["withheld_positives"] for f in folds))
    e2 = {"experiment": "E2 quadrant hide-and-recover on catalogue (visible-only buffer; field is catalogue-free)",
          "label": "HOLDOUT-DTI", "evaluator": EVALUATOR, "folds": folds,
          "candidate_mean": cand_m, "candidate_ci95": cand_ci,
          "random_mean": rnd_m, "random_ci95": rnd_ci,
          "paired_diff_mean": diff_m, "paired_diff_ci95": diff_ci,
          "total_withheld_positives": total_withheld,
          "note": "Catalogue-truth holdout measures recovery of withheld mapped segments; it cannot certify discovery of unmapped faults. SGMC pooled control in E3 record."}
    (EVID / "lidar02_e2_holdout.json").write_text(json.dumps(e2, indent=1))
    print("E2 candidate", cand_m, cand_ci, "random", rnd_m, rnd_ci, "diff", diff_m, diff_ci)

    # ---------- E3 final emission ----------
    dots, sinfo = stratified_dots(field, elig_full, relief, K_DOTS)
    pred = np.zeros(field.shape, np.float32); pred[dots] = 1.0
    pred[~footprint] = 0.0
    # SGMC off-catalogue pooled control (reported, not optimised)
    ctrl = {"candidate": float(dti(pred, sgmc_off))}
    for tag, p in [("h33_2_b2", H33_TIF), ("lidar01", LIDAR01_TIF)]:
        dmask, _ = read_dots(p)
        pr = np.zeros(field.shape, np.float32); pr[dmask] = 1.0
        ctrl[tag] = float(dti(pr, sgmc_off)); ctrl[tag + "_dots"] = int(dmask.sum())
    rnd_full = random_dots(elig_full, int(dots.sum()), SEED + 99)
    pr = np.zeros(field.shape, np.float32); pr[rnd_full] = 1.0
    ctrl["random_matched"] = float(dti(pr, sgmc_off))
    # relief-stratified kernel credit vs SGMC truth (range-front confinement check)
    qs = np.percentile(relief[valid], [33.333, 66.667])
    strata_masks = [relief <= qs[0], (relief > qs[0]) & (relief <= qs[1]), relief > qs[1]]
    strata_dti = []
    for si, sm in enumerate(strata_masks):
        t = sgmc_off & sm
        strata_dti.append({"stratum": si, "truth_px": int(t.sum()),
                           "candidate_dots": int((dots & sm).sum()),
                           "candidate_dti_in_stratum_truth": float(dti(pred, t)) if t.sum() else None})
    print("SGMC control", ctrl); print("strata", strata_dti)

    # uniqueness: surface spearman (sample) + final-dot overlap + lift, vs registry + downloads
    rng = np.random.default_rng(SEED)
    samp_idx = rng.choice(np.where(footprint.ravel())[0], size=200000, replace=False)
    def spearman_sample(a2d):
        x = field.ravel()[samp_idx].astype(float); y = a2d.ravel()[samp_idx].astype(float)
        xr = np.argsort(np.argsort(x)); yr = np.argsort(np.argsort(y))
        return float(np.corrcoef(xr, yr)[0, 1])
    cand_ys, cand_xs = np.where(dots)
    uniq = []
    reg_files = sorted((ROOT / "registry" / "rasters").glob("*.tif")) + \
        sorted((ROOT / "docs" / "downloads").glob("*.tif")) + \
        sorted((ROOT / "artifacts" / "lidar_lane").glob("*.tif"))
    rnd_ys, rnd_xs = np.where(rnd_full)
    for p in reg_files:
        try:
            dmask, vals = read_dots(p)
        except Exception as e:  # unreadable registry member: record, never skip silently
            uniq.append({"file": p.name, "error": str(e)}); continue
        if dmask.shape != dots.shape:
            uniq.append({"file": p.name, "error": f"shape {dmask.shape}"}); continue
        dist = ndimage.distance_transform_edt(~dmask)
        ov = float((dist[cand_ys, cand_xs] <= 3).mean()) if cand_ys.size else 0.0
        ov_r = float((dist[rnd_ys, rnd_xs] <= 3).mean()) if rnd_ys.size else 0.0
        uniq.append({"file": p.name, "ref_dots": int(dmask.sum()),
                     "surface_spearman_sample200k": spearman_sample(vals),
                     "dot_overlap3px": ov, "random_overlap3px": ov_r,
                     "lift": float(ov / ov_r) if ov_r > 0 else None,
                     "identical_dots": bool((dmask == dots).all()),
                     "sha256": sha256_file(p)})
    ok_u = [u for u in uniq if "error" not in u]
    max_rho = max(abs(u["surface_spearman_sample200k"]) for u in ok_u)
    comparable = [u for u in ok_u if K_DOTS / 3 <= u["ref_dots"] <= K_DOTS * 3]
    max_ov_comp = max((u["dot_overlap3px"] for u in comparable), default=0.0)
    worst_comp = max(comparable, key=lambda u: u["dot_overlap3px"], default=None)
    max_ov_raw = max((u["dot_overlap3px"] for u in ok_u), default=0.0)
    dup_lift = [u for u in comparable if u["dot_overlap3px"] > 0.70 and (u["lift"] or 0) > 2.0]
    uniq_rec = {"n_compared": len(uniq), "n_readable": len(ok_u), "max_abs_surface_spearman": float(max_rho),
                "max_dot_overlap3px_raw": float(max_ov_raw),
                "max_dot_overlap3px_density_comparable": float(max_ov_comp),
                "worst_comparable": worst_comp, "duplicate_under_lift_rule": dup_lift,
                "any_identical": any(u.get("identical_dots") for u in ok_u), "per_raster": uniq}
    (EVID / "lidar02_uniqueness.json").write_text(json.dumps(uniq_rec, indent=1))
    print("uniq rho", max_rho, "ov_comp", max_ov_comp, "ov_raw", max_ov_raw, "dup_lift", len(dup_lift))

    # gate (pre-registered in docstring): canary pass; holdout diff CI > 0 vs random;
    # dots present in all 3 relief strata with low-stratum share >= 25% (not range-front
    # confined by construction); uniqueness: |rho|<=0.90, no identity, no lift-duplicate,
    # comparable-density overlap <= 0.70.
    low_share = strata_dti[0]["candidate_dots"] / max(int(dots.sum()), 1)
    gate = {"canary_pass": e1["pass"], "holdout_diff_ci_lower_gt0": bool(diff_ci[0] > 0),
            "low_relief_dot_share": float(low_share), "low_relief_share_ge_0p25": bool(low_share >= 0.25),
            "max_abs_rho_le_0p90": bool(max_rho <= 0.90), "no_identical": not uniq_rec["any_identical"],
            "no_lift_duplicate": len(dup_lift) == 0,
            "comparable_overlap_le_0p70": bool(max_ov_comp <= 0.70)}
    gate["all_pass"] = all(v for k, v in gate.items() if isinstance(v, bool))
    print("GATE", gate)

    # write siblings (always write for audit; site offers download only if gate passes)
    base = f"gems66-lidar02-sharpersist-stratified-{int(dots.sum())}dots-{ts}"
    name = base[:120]
    note = "LIDAR-02 sharpness x persistence x antislope polarity, relief-stratified emission; GEMSDOE66 run card lidar02"[:140]
    outdir = ROOT / "docs" / "downloads"; outdir.mkdir(parents=True, exist_ok=True)
    receipts = {}
    for suffix, fill, pol in [("zeros", 0.0, "either"), ("nan", None, "nan")]:
        out = outdir / f"{base}-{suffix}.tif"
        rec = write_submission(out, pred, footprint, SAMPLE_TIF, overwrite=True,
                               name=name, note=note, outside_fill=fill)
        v = validate(out, reference_path=SAMPLE_TIF, outside_policy=pol)
        zpath = outdir / f"{base}-{suffix}.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(out, arcname=out.name)
        receipts[suffix] = {"file": out.name, "zip": zpath.name, "sha256": sha256_file(out),
                            "zip_sha256": sha256_file(zpath), "writer_receipt": rec,
                            "validator": v}
        print(suffix, receipts[suffix]["sha256"][:16], v.get("verdict") or v.get("status") or str(v)[:200])
    rec_all = {"generated_utc": ts, "name": name, "note": note, "note_chars": len(note),
               "dots": int(dots.sum()), "strata_emission": sinfo, "sgmc_control": ctrl,
               "relief_strata_sgmc": strata_dti, "gate": gate, "receipts": receipts,
               "field_formula": "rank01( (0.25*sharp + 0.25*persist + 0.20*polarity + 0.15*frangi_rank + 0.10*coh_rank + 0.05*steger_rank) * (0.5+0.5*sqrt(step_rank*ex_rank)) )",
               "inputs_sha256": {str(p.relative_to(ROOT)): sha256_file(p) for p in [LIDAR_TIF, LABELS_TIF, SAMPLE_TIF, SGMC_TIF]}}
    (EVID / "lidar02_e3_emission.json").write_text(json.dumps(rec_all, indent=1, default=str))
    print("DONE", base, "gate_all_pass", gate["all_pass"])


if __name__ == "__main__":
    main()
