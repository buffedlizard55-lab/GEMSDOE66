#!/usr/bin/env python3
"""LIDAR-04 — locally-normalised SNR

RENAME NOTE (2026-10-20, at merge): this session originally ran as "LIDAR-03" in
parallel with another session that independently used the same label for a
spatial-CV-retrained classifier and merged first (PR #30, verdict promote,
file gems66-lidar03-cvretrain-reliefdecile-...). To avoid overwriting that
session's record, this session was renamed LIDAR-04 everywhere except the
raster file stem gems66-lidar03-localsnr-fracpair-..., which is baked into the
GeoTIFF tags, receipts and sha256 record and is therefore kept verbatim. x scarp-fraction x crest/toe-pair scarp lane.

Lane (assigned, single paragraph): native-resolution lidar scarp channels —
(i) slope-aware scarplet template channels (Sare & Hilley, JOSS 2018,
doi:10.21105/joss.01066; slope-aware extension AGU 2015 T31A-2838) and
(ii) Steger sub-pixel lines (IEEE TPAMI 20(2):113-125, 1998) + Frangi
multiscale Hessian line measures (MICCAI 1998, LNCS 1496:130-137) on a
slope-detrended surface, aggregated to 100 m as scarp-pixel fraction,
SNR-weighted amplitude, orientation coherence and dominant strike.

What is NEW vs LIDAR-01/02 (pre-registered here, before any number below
was read; motivated by LIDAR-02's published E1 canary, evidence/
lidar02_e1_canary.json, which is prior-experiment data, not this run's):
  * The signed antislope template net (up - max(down, cross)) measured
    AUC 0.301 vs SGMC off-catalogue and 0.444 vs the catalogue in LIDAR-02
    -- an anti-signal that LIDAR-02 nevertheless weighted at 0.20.  It is
    REMOVED.  In its place: UNSIGNED single-polarity dominance
    |up-down|/(up+down+cross) (one clean step face, either facing).
  * True local-contrast SNR: step and ex divided by their ~1 km Gaussian
    background (sigma = 5 cells).  Prior "SNR-weighted amplitude" was
    step*coherence, not a signal/background ratio.  A subtle basin-floor
    scarp is locally anomalous even when its absolute step is small; raw
    amplitudes are relief-confounded (relief alone: AUC 0.774 vs the SGMC
    proxy in LIDAR-02's canary).
  * Scarp-pixel fraction proxy ex_mean/(ex_max+eps): distributed small
    steps inside the cell (damage-zone signature), the aggregate the lane
    names first.  Prior fields used extrema almost exclusively.
  * Crest/toe curvature pairing sqrt(lappos*lapneg): a diffusion-degraded
    scarp profile (the Scarplet model) has paired convex crest + concave
    toe; either curvature sign alone is generic terrain.
  * Steger sub-pixel offset-valid density (L02-B, ranked-not-run in the
    LIDAR-02 review): 5x5 density of pixels whose sub-pixel extremum falls
    inside the pixel with consistent Hessian sign, at sigma 1 and 2, on
    the detrended SNR surface.  Prior lanes used Steger *response*.
  * Frangi/Steger run on the detrended SNR surface (not detrended raw
    step), via the shared multiscale_line_fields with the IR-L04-TOOL-01
    threshold fix (Steger thresholded on its own response distribution).
Emission geometry is IDENTICAL to LIDAR-02 (K=37654, >=3 px separation,
>2 px from catalogue, relief-tercile allocation by eligible-footprint
share) so the field is the only changed variable -- a clean ablation.

Named non-fault mimic: fluvial terrace risers / irrigation canal banks.
They are also locally anomalous, single-polarity, paired-curvature steps;
nothing in this checkout (no pinned cultural-feature mask) fully removes
them.  The pairing + persistence terms only demote isolated edges.

SCALE DISCLOSURE (inherited, mandatory): input is the pinned per-100 m
extrema/means of 2 m descriptors from USGS 3DEP 1 m tiles (706/716, owner
CI).  Operators run at 100-400 m on the aggregate, NOT native 2-20 m on
raw 1 m tiles (unreachable from this sandbox: only github.com/pypi.org
egress).  Named free official source for the native version: USGS 3DEP
1 m DEM (https://www.usgs.gov/3d-elevation-program); obtainability from
here was checked and FAILS (host not reachable), so the aggregate path is
used and labelled.

PRE-REGISTERED GATE (all must pass to offer the download as OK TO SUBMIT):
  G1 canary: worst feature-alone AUC <= 0.90 (leakage stop).
  G2 holdout: E2 paired diff vs mass-matched random, 95% CI lower > 0
     (same criterion LIDAR-02 failed: +0.0144 [-0.0015, +0.0238]).
  G3 incumbent: SGMC off-catalogue pooled DTI > h33-2-b2 measured in the
     same run (LIDAR-02: candidate 0.09515 vs h33 0.09539 -- a tie).
  G4 not range-front confined: low-relief dot share >= 0.25 AND candidate
     low-tercile SGMC DTI >= mass-matched random low-tercile SGMC DTI.
  G5 uniqueness: max |surface Spearman| <= 0.90; no identical raster;
     density-comparable 3 px dot overlap <= 0.70; no raster with overlap
     > 0.70 at lift > 2.0 (raw overlap also reported, never hidden).
  G6 format: shared validator PASS on both siblings (float32 EPSG:32611
     100 m, values in [0,1], 0 NaN inside footprint; -zeros fully finite).
Field formula (fixed now): rank01( (0.25*snr + 0.20*persist_snr +
0.15*frac + 0.15*pair + 0.10*pdom + 0.10*frangi_rank +
0.05*steger_offset_rank) * (0.5 + 0.5*sqrt(step_rank*ex_rank)) ), with
snr = 0.5*rank(step/bg_step) + 0.5*rank(ex/bg_ex).
Budget: E1, E2, E3 -- 3 experiments, then stop.  Verdict negative if any
gate fails; negative results are deliverables.
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
sys.path.insert(0, str(ROOT / "scripts"))
from gems.metric import dti  # noqa: E402
from gems.submission_writer import write_submission, sha256_file  # noqa: E402
from gems.validate_submission import validate  # noqa: E402
from gems66.lidar_channels import (  # noqa: E402
    load_lidar_stack, multiscale_line_fields, steger_lines,
    orientation_coherence,
)
# Reuse, don't rebuild: the LIDAR-02 session's tested helpers, unchanged.
from build_lidar02 import (  # noqa: E402
    rank01, auc, load_grid, eligible_mask, stratified_dots, random_dots,
    read_dots, K_DOTS, SEED, EVALUATOR,
)

RAW = ROOT / "data" / "raw"
LIDAR_TIF = RAW / "external" / "lidar_scarp_features_u8.tif"
SGMC_TIF = RAW / "external" / "derived_sgmc_faults_100m_u8.tif"
LABELS_TIF = RAW / "labels.tif"
SAMPLE_TIF = RAW / "sample_submission.tif"
H33_TIF = ROOT / "registry" / "rasters" / "GEMSDOE32__h33-2-b2-zeros.tif"
LIDAR01_TIF = ROOT / "artifacts" / "lidar01" / \
    "gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z.tif"
LIDAR02_TIF = ROOT / "docs" / "downloads" / \
    "gems66-lidar02-sharpersist-stratified-37654dots-20261020T182135Z-zeros.tif"
EVID = ROOT / "evidence"
FIELD_FORMULA = ("rank01( (0.25*snr + 0.20*persist_snr + 0.15*frac + 0.15*pair"
                 " + 0.10*pdom + 0.10*frangi_rank + 0.05*steger_offset_rank)"
                 " * (0.5+0.5*sqrt(step_rank*ex_rank)) ); snr = 0.5*rank(step/bg_step)"
                 " + 0.5*rank(ex/bg_ex), bg = gaussian sigma=5 cells")


def build_channels(sgmc_off, catalogue):
    """Memory-frugal channel build with per-channel canary (free-as-you-go)."""
    footprint, _cat, _sg = load_grid()
    stack64 = load_lidar_stack(LIDAR_TIF)
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

    # --- local-contrast SNR (new): signal / ~1 km background roughness ---
    bg = ndimage.gaussian_filter(step, 5.0, mode="nearest").astype(np.float32)
    snr_step_raw = (step / (bg + np.float32(0.02))).astype(np.float32); del bg; gc.collect()
    can("snr_step", snr_step_raw); r_snr_step = rank01(snr_step_raw, valid)
    bg = ndimage.gaussian_filter(ex, 5.0, mode="nearest").astype(np.float32)
    snr_ex_raw = (ex / (bg + np.float32(0.02))).astype(np.float32); del bg; gc.collect()
    can("snr_ex", snr_ex_raw); r_snr_ex = rank01(snr_ex_raw, valid); del snr_ex_raw
    snr = (0.5 * r_snr_step + 0.5 * r_snr_ex).astype(np.float32)
    del r_snr_step, r_snr_ex; can("part_snr", snr)

    # --- persistence of the SNR surface at 300/500/900 m (geomean of ranks) ---
    persist = np.ones(step.shape, np.float32)
    for sz, nm in [(3, "persist_snr300"), (5, "persist_snr500"), (9, "persist_snr900")]:
        b = ndimage.uniform_filter(snr_step_raw, sz, mode="nearest").astype(np.float32)
        can(nm, b); persist *= np.maximum(rank01(b, valid), np.float32(1e-4)); del b; gc.collect()
    persist = rank01(persist ** np.float32(1 / 3), valid); can("part_persist_snr", persist)

    # --- scarp-pixel fraction proxy (new): distributed steps, not one extremum ---
    exm = f32("ex_mean"); can("ex_mean", exm)
    frac_raw = (exm / (ex + np.float32(0.01))).astype(np.float32); del exm; gc.collect()
    can("frac_raw", frac_raw); frac = rank01(frac_raw, valid); del frac_raw

    # --- crest/toe curvature pairing (new) ---
    lp, ln = f32("lappos_max"), f32("lapneg_max")
    can("lappos_max", lp); can("lapneg_max", ln)
    pair_raw = np.sqrt(np.maximum(lp * ln, np.float32(0))).astype(np.float32)
    del lp, ln; gc.collect()
    can("pair_raw", pair_raw); pair = rank01(pair_raw, valid); del pair_raw

    # --- unsigned single-polarity dominance (new; signed antislope REMOVED) ---
    up, down, cross = f32("upface_max"), f32("downface_max"), f32("cross_max")
    can("upface_max", up); can("downface_max", down); can("cross_max", cross)
    net = (up - np.maximum(down, cross)).astype(np.float32)
    can("template_net_removed", net); del net  # recorded to verify the anti-signal here
    pdom_raw = (np.abs(up - down) / (up + down + cross + np.float32(0.01))).astype(np.float32)
    del up, down, cross; gc.collect()
    can("pdom_raw", pdom_raw); pdom = rank01(pdom_raw, valid); del pdom_raw

    coh = f32("coh100"); can("coh100", coh); del coh
    for k in list(stack64):  # remaining raw bands: canary only
        a = f32(k); can(k, a); del a
    gc.collect()

    # --- slope-detrended SNR surface -> Frangi + Steger (shared, fixed) ---
    surf = (snr_step_raw - ndimage.gaussian_filter(snr_step_raw, 4.0, mode="nearest")).astype(np.float32)
    del snr_step_raw; gc.collect()
    surf[~valid] = np.nan
    lines = multiscale_line_fields(surf, scales=(1.0, 2.0, 4.0))
    fr = np.nan_to_num(lines.pop("frangi_max"), nan=0.0).astype(np.float32)
    can("frangi_max_snr", fr); r_fr = rank01(fr, valid); del fr
    stf = np.nan_to_num(lines.pop("steger_frac300"), nan=0.0).astype(np.float32)
    can("steger_frac300_snr_fixed", stf); del stf
    for k in list(lines):
        a = np.nan_to_num(lines.pop(k), nan=0.0).astype(np.float32); can(k, a); del a

    # --- Steger sub-pixel offset-valid density (new, L02-B) ---
    surf0 = np.nan_to_num(surf, nan=0.0).astype(np.float32)
    offdens = np.zeros(surf.shape, np.float32)
    for sg in (1.0, 2.0):
        _resp, line, _inside = steger_lines(surf0, sg, response_min=0.0)
        line &= valid
        offdens += ndimage.uniform_filter(line.astype(np.float32), 5, mode="nearest")
        del _resp, line, _inside; gc.collect()
    offdens = (offdens / np.float32(2.0)).astype(np.float32)
    can("steger_offset_density", offdens); r_off = rank01(offdens, valid); del offdens
    oc = np.nan_to_num(orientation_coherence(surf0, 2.0), nan=0.0).astype(np.float32)
    can("orient_coh_snr", oc); del oc, surf, surf0, step, ex; gc.collect()

    amp_gate = (0.5 + 0.5 * np.sqrt(np.maximum(r_step * r_ex, np.float32(0)))).astype(np.float32)
    del r_step, r_ex
    field = ((0.25 * snr + 0.20 * persist + 0.15 * frac + 0.15 * pair
              + 0.10 * pdom + 0.10 * r_fr + 0.05 * r_off) * amp_gate).astype(np.float32)
    del snr, persist, frac, pair, pdom, r_fr, r_off, amp_gate; gc.collect()
    field = rank01(field, valid)
    can("field", field)
    return field, relief, valid, footprint, canary


def main():
    EVID.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    footprint, catalogue, sgmc = load_grid()
    dist_cat_full = ndimage.distance_transform_edt(~catalogue)
    sgmc_off = sgmc & (dist_cat_full > 3)
    del dist_cat_full
    field, relief, valid, footprint, canary = build_channels(sgmc_off, catalogue)
    print(f"footprint={footprint.sum()} lidar_valid={valid.sum()} catalogue={catalogue.sum()} sgmc_off={sgmc_off.sum()}", flush=True)

    # ---------- E1 leakage canary ----------
    worst_name = max(canary, key=lambda k: max(v for v in canary[k].values()
                                               if v == v))
    worst = float(max(v for v in canary[worst_name].values() if v == v))
    e1 = {"experiment": "E1 leakage canary (feature-alone AUC; stop if > 0.90)",
          "evaluator": EVALUATOR, "channels": canary, "worst_auc": worst,
          "worst_channel": worst_name, "pass": bool(worst <= 0.90),
          "n_sgmc_offcat": int(sgmc_off.sum()), "n_channels": len(canary)}
    (EVID / "lidar04_e1_canary.json").write_text(json.dumps(e1, indent=1))
    print("E1 worst AUC", worst, worst_name, "pass", e1["pass"], flush=True)
    if not e1["pass"]:
        print("LEAKAGE STOP"); return

    # ---------- E2 spatial hide-and-recover holdout (4 quadrant blocks) ----------
    H, W = field.shape
    blocks = [(slice(0, H // 2), slice(0, W // 2)), (slice(0, H // 2), slice(W // 2, W)),
              (slice(H // 2, H), slice(0, W // 2)), (slice(H // 2, H), slice(W // 2, W))]
    elig_full, _ = eligible_mask(valid, footprint, catalogue)
    controls = [("h33", H33_TIF), ("lidar02", LIDAR02_TIF)]
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
        for tag, p in controls:
            dmask, _ = read_dots(p)
            pr = np.zeros(field.shape, np.float32); pr[dmask & block] = 1.0
            row[tag + "_dots_in_block"] = int((dmask & block).sum())
            row[tag + "_dti_asis"] = float(dti(pr, truth))
        folds.append(row)
        print("fold", fi, row["candidate_dti"], row["random_dti"], row["withheld_positives"], flush=True)
        del pred_c, pred_r, pr, dmask; gc.collect()

    def ci(vals):
        v = np.array(vals); m = float(v.mean())
        rng = np.random.default_rng(SEED)
        bs = [float(rng.choice(v, size=v.size, replace=True).mean()) for _ in range(2000)]
        return m, [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]

    cand_m, cand_ci = ci([f["candidate_dti"] for f in folds])
    rnd_m, rnd_ci = ci([f["random_dti"] for f in folds])
    diff_m, diff_ci = ci([f["candidate_dti"] - f["random_dti"] for f in folds])
    total_withheld = int(sum(f["withheld_positives"] for f in folds))
    e2 = {"experiment": "E2 quadrant hide-and-recover on catalogue (visible-only buffer; field is catalogue-free)",
          "label": "HOLDOUT-DTI", "evaluator": EVALUATOR, "folds": folds,
          "candidate_mean": cand_m, "candidate_ci95": cand_ci,
          "random_mean": rnd_m, "random_ci95": rnd_ci,
          "paired_diff_mean": diff_m, "paired_diff_ci95": diff_ci,
          "folds_won_vs_random": int(sum(1 for f in folds
                                         if f["candidate_dti"] > f["random_dti"])),
          "total_withheld_positives": total_withheld,
          "note": "Catalogue-truth holdout penalises off-catalogue designs by construction "
                  "(h33 as-is ~0.006/fold); reported for falsification, paired with the "
                  "SGMC off-catalogue pooled control in E3."}
    (EVID / "lidar04_e2_holdout.json").write_text(json.dumps(e2, indent=1))
    print("E2 candidate", cand_m, cand_ci, "random", rnd_m, rnd_ci, "diff", diff_m, diff_ci, flush=True)

    # ---------- E3 final emission ----------
    dots, sinfo = stratified_dots(field, elig_full, relief, K_DOTS)
    pred = np.zeros(field.shape, np.float32); pred[dots] = 1.0
    pred[~footprint] = 0.0
    rnd_full = random_dots(elig_full, int(dots.sum()), SEED + 99)
    preds = {"candidate": pred}
    pr = np.zeros(field.shape, np.float32); pr[rnd_full] = 1.0
    preds["random_matched"] = pr
    for tag, p in [("h33_2_b2", H33_TIF), ("lidar01", LIDAR01_TIF), ("lidar02", LIDAR02_TIF)]:
        if not p.exists():
            print("control missing", tag, p); continue
        dmask, _ = read_dots(p)
        pr = np.zeros(field.shape, np.float32); pr[dmask] = 1.0
        preds[tag] = pr
        preds[tag + "_dots_arr"] = dmask
    ctrl = {}
    for tag in ("candidate", "h33_2_b2", "lidar01", "lidar02", "random_matched"):
        if tag in preds:
            ctrl[tag] = float(dti(preds[tag], sgmc_off))
            ctrl[tag + "_dots"] = int((preds[tag] > 0).sum())
    print("SGMC control", ctrl, flush=True)
    # relief-stratified SGMC DTI (range-front confinement check), candidate + random + h33
    qs = np.percentile(relief[valid], [33.333, 66.667])
    strata_masks = [relief <= qs[0], (relief > qs[0]) & (relief <= qs[1]), relief > qs[1]]
    strata_dti = []
    for si, sm in enumerate(strata_masks):
        t = sgmc_off & sm
        row = {"stratum": si, "truth_px": int(t.sum()),
               "candidate_dots": int((dots & sm).sum())}
        for tag in ("candidate", "random_matched", "h33_2_b2"):
            if tag in preds:
                row[tag + "_dti_in_stratum_truth"] = float(dti(preds[tag], t)) if t.sum() else None
        strata_dti.append(row)
    print("strata", strata_dti, flush=True)
    for tag in list(preds):
        if tag != "candidate":
            del preds[tag]
    gc.collect()

    # uniqueness: surface spearman (pre-placement field) + final-dot overlap/lift
    rng = np.random.default_rng(SEED)
    samp_idx = rng.choice(np.where(footprint.ravel())[0], size=200000, replace=False)

    def spearman_sample(a2d):
        x = field.ravel()[samp_idx].astype(float); y = a2d.ravel()[samp_idx].astype(float)
        xr = np.argsort(np.argsort(x)); yr = np.argsort(np.argsort(y))
        return float(np.corrcoef(xr, yr)[0, 1])

    cand_ys, cand_xs = np.where(dots)
    rnd_ys, rnd_xs = np.where(rnd_full)
    reg_files = sorted((ROOT / "registry" / "rasters").glob("*.tif")) + \
        sorted((ROOT / "docs" / "downloads").glob("*.tif")) + \
        sorted((ROOT / "artifacts" / "lidar_lane").glob("*.tif")) + \
        sorted((ROOT / "artifacts" / "lidar01").glob("*.tif"))
    uniq = []
    for p in reg_files:
        if "lidar03" in p.name:
            continue
        try:
            dmask, vals = read_dots(p)
        except Exception as e:
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
        del dmask, vals, dist; gc.collect()
    ok_u = [u for u in uniq if "error" not in u]
    max_rho = max(abs(u["surface_spearman_sample200k"]) for u in ok_u)
    comparable = [u for u in ok_u if K_DOTS / 3 <= u["ref_dots"] <= K_DOTS * 3]
    max_ov_comp = max((u["dot_overlap3px"] for u in comparable), default=0.0)
    worst_comp = max(comparable, key=lambda u: u["dot_overlap3px"], default=None)
    max_ov_raw = max((u["dot_overlap3px"] for u in ok_u), default=0.0)
    dup_lift = [u for u in comparable if u["dot_overlap3px"] > 0.70 and (u["lift"] or 0) > 2.0]
    uniq_rec = {"n_compared": len(uniq), "n_readable": len(ok_u),
                "max_abs_surface_spearman": float(max_rho),
                "max_dot_overlap3px_raw": float(max_ov_raw),
                "max_dot_overlap3px_density_comparable": float(max_ov_comp),
                "worst_comparable": worst_comp, "duplicate_under_lift_rule": dup_lift,
                "any_identical": any(u.get("identical_dots") for u in ok_u),
                "per_raster": uniq}
    (EVID / "lidar04_uniqueness.json").write_text(json.dumps(uniq_rec, indent=1))
    print("uniq rho", max_rho, "ov_comp", max_ov_comp, "ov_raw", max_ov_raw,
          "dup_lift", len(dup_lift), flush=True)

    gate = {"G1_canary_pass": e1["pass"],
            "G2_holdout_diff_ci_lower_gt0": bool(diff_ci[0] > 0),
            "G3_sgmc_beats_h33": bool(ctrl.get("candidate", 0) > ctrl.get("h33_2_b2", np.inf)),
            "low_relief_dot_share": float(strata_dti[0]["candidate_dots"] / max(int(dots.sum()), 1)),
            "G4_low_share_ge_0p25_and_low_stratum_ge_random": bool(
                strata_dti[0]["candidate_dots"] / max(int(dots.sum()), 1) >= 0.25
                and (strata_dti[0].get("candidate_dti_in_stratum_truth") or 0)
                >= (strata_dti[0].get("random_matched_dti_in_stratum_truth") or np.inf)),
            "G5_max_abs_rho_le_0p90": bool(max_rho <= 0.90),
            "G5_no_identical": not uniq_rec["any_identical"],
            "G5_no_lift_duplicate": len(dup_lift) == 0,
            "G5_comparable_overlap_le_0p70": bool(max_ov_comp <= 0.70)}
    print("GATE (pre-format)", gate, flush=True)

    # write siblings (always written for audit; offered only if every gate passes)
    base = f"gems66-lidar03-localsnr-fracpair-{int(dots.sum())}dots-{ts}"
    name = base[:120]
    note = ("LIDAR-03 local-SNR x scarp-fraction x crest/toe pair, antislope-net removed,"
            " relief-stratified; GEMSDOE66 lidar03")[:140]  # historical: as executed (see rename note)
    outdir = ROOT / "docs" / "downloads"; outdir.mkdir(parents=True, exist_ok=True)
    receipts = {}
    for suffix, fill, pol in [("zeros", 0.0, "either"), ("nan", None, "nan")]:
        out = outdir / f"{base}-{suffix}.tif"
        rec = write_submission(out, pred, footprint, SAMPLE_TIF, overwrite=True,
                               name=name, note=note, outside_fill=fill)
        v = validate(out, reference_path=SAMPLE_TIF, outside_policy=pol)
        (EVID / f"lidar04_validate_{suffix}.json").write_text(json.dumps(v, indent=1, default=str))
        zpath = outdir / f"{base}-{suffix}.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(out, arcname=out.name)
        receipts[suffix] = {"file": out.name, "zip": zpath.name, "sha256": sha256_file(out),
                            "zip_sha256": sha256_file(zpath), "writer_receipt": rec,
                            "validator_passed": bool(v.get("passed")),
                            "validator": v}
        print(suffix, receipts[suffix]["sha256"][:16], "validator_passed",
              receipts[suffix]["validator_passed"], flush=True)
    gate["G6_validator_pass_both"] = all(r["validator_passed"] for r in receipts.values())
    gate["all_pass"] = all(v for k, v in gate.items() if isinstance(v, bool))
    rec_all = {"generated_utc": ts, "name": name, "note": note, "note_chars": len(note),
               "dots": int(dots.sum()), "strata_emission": sinfo, "sgmc_control": ctrl,
               "relief_strata_sgmc": strata_dti, "gate": gate, "receipts": receipts,
               "field_formula": FIELD_FORMULA,
               "inputs_sha256": {str(p.relative_to(ROOT)): sha256_file(p)
                                 for p in [LIDAR_TIF, LABELS_TIF, SAMPLE_TIF, SGMC_TIF]}}
    (EVID / "lidar04_e3_emission.json").write_text(json.dumps(rec_all, indent=1, default=str))
    print("DONE", base, "gate_all_pass", gate["all_pass"], flush=True)
    print(json.dumps({"base": base, "gate": gate}, indent=1), flush=True)


if __name__ == "__main__":
    main()
