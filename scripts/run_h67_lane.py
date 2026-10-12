#!/usr/bin/env python3
"""H67 lane runner: native-resolution LiDAR scarp channels (this session).

Experiments (budget 3, per the parallel-run protocol)
-----------------------------------------------------
E1  ``canary``   leakage canary: per-fold AUC of every candidate surface (and of the raw
                 physical channels) on the 8-fold spatial hide-and-recover holdout.
                 AUC > 0.90 on any single feature means leakage until proven otherwise.
E2  ``emit N``   emit candidate N at the incumbent's budget (37,654 dots, min sep 2.82 px,
                 200 m catalogue buffer, scatter-cover blur 2.8 px), score pooled DTI on the
                 buffered 8-fold holdout against the incumbent (GEMSDOE32 h33-2-b2, 0.2778
                 per the owner's site), relief-stratify the gain, ablate the cultural mask,
                 and run the duplicate/lane-drift gate (pre-placement surface + final dots).
E3  ``finalize N``  build the submission TIFF (nan + zeros), validate, uniqueness on the
                 final bytes, evidence + run card.

All numbers are labelled HOLDOUT-DTI (proxy truth: SGMC off-catalogue faults) unless
marked otherwise.  Nothing here is ORGANIZER-CONFIRMED.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems66.h67_hypotheses import NAMES, build_surfaces, rank01  # noqa: E402
from gems66.h67_layers import load_layers, emission_domain       # noqa: E402
from gemsdoe66.emission import emit as emit_field                # noqa: E402
from gemsdoe66.grid import catalogue_mask, footprint_mask, RAW   # noqa: E402
from gemsdoe66.holdout import (buffer_around, bootstrap_ci,      # noqa: E402
                               folds_by_spatial_cluster, novelty_truth, score_emission)
from gemsdoe66.metric import dti_parts                           # noqa: E402
from gemsdoe66.uniqueness import check_registry, read01          # noqa: E402
from gemsdoe66.validate_submission import validate               # noqa: E402

EVID = ROOT / "evidence"
REG = ROOT / "registry" / "rasters"
INCUMBENT = REG / "GEMSDOE32__h33-2-b2-zeros.tif"

N_FOLDS = 8
BUFFER_PX = 3.0
N_DOTS = 37_654          # the incumbent's budget - isolates field quality
MIN_SEP = 2.82
SCATTER_SIGMA = 2.8      # family d2-8 scatter-cover convention
CAT_PRUNE_PX = 2.0

# pre-registered gate (frozen before any result was looked at)
GATE = {
    "pooled_diff_vs_incumbent_gt": 0.0,
    "paired_ci_lower_gt": 0.0,
    "strata_beating_random_min": 2,
    "canary_auc_max": 0.90,
    "rho_max": 0.90,
    "within3_max": 0.70,
}


def out(name: str, obj) -> None:
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / name
    p.write_text(json.dumps(obj, indent=1, default=float))
    print(f"wrote {p}")


def load_truth_folds() -> tuple[np.ndarray, np.ndarray]:
    truth = novelty_truth(3.0)
    folds = folds_by_spatial_cluster(truth, n_folds=N_FOLDS, n_clusters=32, seed=0)
    return truth, folds


def fold_masks_from(truth: np.ndarray, folds: np.ndarray):
    for f in range(N_FOLDS):
        t = folds == f
        if not t.any():
            continue
        yield f, t, buffer_around(t, BUFFER_PX)


# --------------------------------------------------------------------------- E1
def canary() -> None:
    t0 = time.time()
    print("loading layers...")
    L = load_layers()
    print("layers:", json.dumps(L.meta, indent=1))
    S = build_surfaces(L)
    truth, folds = load_truth_folds()
    buf_all = buffer_around(truth, BUFFER_PX)
    from sklearn.metrics import roc_auc_score

    results = {}
    bg_pool = L.fp & ~truth & ~buf_all
    for name in list(NAMES):
        surf = getattr(S, name)
        vals = []
        for f, t, buf in fold_masks_from(truth, folds):
            region = L.fp & ~buf
            pos = t
            neg = region & ~pos
            rng = np.random.default_rng(f)
            nidx = np.flatnonzero(neg.ravel())
            if nidx.size > 300_000:
                nidx = rng.choice(nidx, 300_000, replace=False)
            y = np.concatenate([np.ones(pos.sum()), np.zeros(nidx.size)])
            x = np.concatenate([surf[pos], surf.ravel()[nidx]])
            vals.append(roc_auc_score(y, np.nan_to_num(x, nan=-1e9, neginf=-1e9, posinf=1e9)))
        results[name] = {"auc_folds": [round(v, 5) for v in vals],
                         "auc_mean": round(float(np.mean(vals)), 5)}
    # raw channels (single-feature canary)
    for cname, arr in (("amp", L.amp), ("step", L.step), ("sharp", L.sharp),
                       ("coh", L.coh), ("relief", L.relief), ("h52_h", L.h52_h)):
        vals = []
        for f, t, buf in fold_masks_from(truth, folds):
            region = L.fp & ~buf
            neg = region & ~t
            rng = np.random.default_rng(f)
            nidx = np.flatnonzero(neg.ravel())
            if nidx.size > 300_000:
                nidx = rng.choice(nidx, 300_000, replace=False)
            y = np.concatenate([np.ones(t.sum()), np.zeros(nidx.size)])
            x = np.concatenate([arr[t], arr.ravel()[nidx]])
            vals.append(roc_auc_score(y, np.nan_to_num(x, nan=-1e9, neginf=-1e9, posinf=1e9)))
        results[f"channel:{cname}"] = {"auc_folds": [round(v, 5) for v in vals],
                                       "auc_mean": round(float(np.mean(vals)), 5)}
    results["meta"] = {"n_truth": int(truth.sum()), "n_folds": N_FOLDS,
                       "buffer_px": BUFFER_PX, "seconds": round(time.time() - t0, 1),
                       "gate_auc_max": GATE["canary_auc_max"]}
    out("h67_e1_canary.json", results)
    for k, v in results.items():
        if "auc_mean" in v:
            flag = "  <<< LEAK" if v["auc_mean"] > GATE["canary_auc_max"] else ""
            print(f"  {k:24s} AUC={v['auc_mean']:.4f}{flag}")


# --------------------------------------------------------------------------- E2
def registry_union_mask():
    """Boolean mask of pixels that are positive in ANY registry raster (dot union)."""
    from gemsdoe66.uniqueness import read01
    fp = footprint_mask()
    union = np.zeros(fp.shape, bool)
    for p_ in sorted(REG.glob("*.tif")):
        a = read01(p_, fp)
        union |= a > 0
        del a
    return union


def emit_candidate(name: str, complement: bool = False, tag: str = "") -> dict:
    t0 = time.time()
    print("loading layers...")
    L = load_layers()
    if name == "h52_h_rank":
        S = None
        surf = rank01(L.h52_h, emission_domain(L)).astype(np.float32)
        surf[~L.fp] = np.nan
    else:
        S = build_surfaces(L)
        surf = getattr(S, name).copy()
    truth, folds = load_truth_folds()

    # ---------------- pre-placement uniqueness (continuous surface) -------------
    print("pre-placement uniqueness scan...")
    pre = check_registry(surf.astype(np.float32), REG, fp=L.fp,
                         max_rho=GATE["rho_max"], max_within3=GATE["within3_max"])
    print(f"  pre: verdict={pre['verdict']} max|rho|={pre['max_abs_spearman_rho']:.3f} "
          f"max within3={pre['max_frac_dots_within_3px']:.3f}")

    # ---------------- emission ---------------------------------------------------
    dom = emission_domain(L)
    if complement:
        from scipy import ndimage as _ndi
        u = registry_union_mask()
        d_u = _ndi.distance_transform_edt(~u)
        eligible = dom & (d_u > 4.0)
        print(f"complement eligibility: {int(eligible.sum()):,} cells (>=4 px from every registry dot)")
        dots = emit_field(surf, N_DOTS, L.fp,
                          exclude=buffer_around(L.cat, CAT_PRUNE_PX) | ~eligible,
                          min_sep_px=MIN_SEP, scatter_sigma=SCATTER_SIGMA)
        dots &= eligible
    else:
        dots = emit_field(surf, N_DOTS, L.fp, exclude=buffer_around(L.cat, CAT_PRUNE_PX),
                          min_sep_px=MIN_SEP, scatter_sigma=SCATTER_SIGMA)
        dots &= dom
    ndots = int(dots.sum())
    print(f"emitted {ndots} dots")

    # ---------------- post-placement uniqueness (final dots) ---------------------
    dot_raster = dots.astype(np.float32)
    post = check_registry(dot_raster, REG, fp=L.fp,
                          max_rho=GATE["rho_max"], max_within3=GATE["within3_max"])
    raw_within3 = max((r["frac_candidate_dots_within_3px"] for r in post["top"]), default=0.0)
    print(f"  post: verdict={post['verdict']} raw max within3={raw_within3:.3f}")

    # ---------------- holdout scoring --------------------------------------------
    inc = read01(INCUMBENT, L.fp)
    per_fold = {}
    for f, t, _ in fold_masks_from(truth, folds):
        sc = score_emission(dot_raster, t)
        si = score_emission(inc, t)
        per_fold[f"fold{f}"] = {
            "n_truth": int(t.sum()),
            "candidate_dti": round(sc["dti"], 5), "incumbent_dti": round(si["dti"], 5),
            "diff": round(sc["dti"] - si["dti"], 5),
            "candidate_mass": round(sc["mass"], 0),
        }
    cand_pool = score_emission(dot_raster, truth)
    inc_pool = score_emission(inc, truth)
    diffs = np.array([v["diff"] for k, v in per_fold.items() if k.startswith("fold")])
    ci_lo, ci_hi = bootstrap_ci(diffs, n_boot=4000, seed=0)

    # ---------------- relief-stratified gain (the "not confined to range fronts") --
    rel = L.relief
    rv = rel[truth]
    q1, q2 = np.nanpercentile(rv, (33.3, 66.7))
    strata = {
        "low (basin/pediment)": truth & (rel <= q1),
        "mid": truth & (rel > q1) & (rel <= q2),
        "high (range front)": truth & (rel > q2),
    }
    rng = np.random.default_rng(7)
    cand_idx = np.flatnonzero((L.fp & ~buffer_around(L.cat, CAT_PRUNE_PX)).ravel())
    strata_res = {}
    for sname, smask in strata.items():
        share = smask.sum() / max(1, truth.sum())
        # candidate dots inside the stratum (no re-emission; the field already saw relief)
        sc_s = score_emission(np.where(smask | dots, dot_raster, 0.0), smask)
        # random baseline at the same dot count, same domain
        rnd = np.zeros(L.fp.shape, np.float32)
        sel = rng.choice(cand_idx, size=ndots, replace=False)
        rnd.ravel()[sel] = 1.0
        sr = score_emission(np.where(smask | (rnd > 0), rnd, 0.0), smask)
        strata_res[sname] = {"n_truth": int(smask.sum()),
                             "candidate_dti": round(sc_s["dti"], 5),
                             "random_dti": round(sr["dti"], 5),
                             "candidate_minus_random": round(sc_s["dti"] - sr["dti"], 5)}

    # ---------------- cultural-mask ablation --------------------------------------
    from gemsdoe66.emission import emit as _emit
    dom = emission_domain(L)
    dom_full = L.fp & L.valid & ~buffer_around(L.cat, CAT_PRUNE_PX)   # no road veto
    dots_noroad = _emit(surf, N_DOTS, L.fp, exclude=buffer_around(L.cat, CAT_PRUNE_PX),
                        min_sep_px=MIN_SEP, scatter_sigma=SCATTER_SIGMA) & dom_full
    abl = score_emission(dots_noroad.astype(np.float32), truth)
    road_veto_mass = int((dots_noroad & (L.road_m < 250)).sum())

    # ---------------- gate ---------------------------------------------------------
    strata_beat = sum(1 for v in strata_res.values() if v["candidate_minus_random"] > 0)
    gate = {
        "G1_pooled_diff": cand_pool["dti"] - inc_pool["dti"],
        "G1_pass": bool(cand_pool["dti"] - inc_pool["dti"] > GATE["pooled_diff_vs_incumbent_gt"]),
        "G2_ci_lower": ci_lo,
        "G2_pass": bool(ci_lo > GATE["paired_ci_lower_gt"]),
        "G3_strata_beating_random": strata_beat,
        "G3_pass": bool(strata_beat >= GATE["strata_beating_random_min"]),
        "G4_pre_rho": pre["max_abs_spearman_rho"],
        "G4_post_raw_within3": raw_within3,
        "G4_post_verdict": post["verdict"],
        "G4_pass": bool(abs(pre["max_abs_spearman_rho"]) <= GATE["rho_max"]
                        and raw_within3 <= GATE["within3_max"]
                        and post["verdict"] == "UNIQUE"),
    }
    res = {
        "candidate": name, "n_dots": ndots, "budget": N_DOTS,
        "min_sep_px": MIN_SEP, "scatter_sigma": SCATTER_SIGMA,
        "cat_prune_px": CAT_PRUNE_PX,
        "holdout": {
            "label": "HOLDOUT-DTI (proxy truth: SGMC off-catalogue >300 m; 8 spatial folds, "
                     f"3 px buffer; evaluator gemsdoe66.metric.dti; n_withheld={int(truth.sum())})",
            "pooled_candidate": round(cand_pool["dti"], 5),
            "pooled_incumbent": round(inc_pool["dti"], 5),
            "pooled_diff": round(cand_pool["dti"] - inc_pool["dti"], 5),
            "paired_ci95": [round(ci_lo, 5), round(ci_hi, 5)],
            "per_fold": per_fold,
        },
        "strata": {"tercile_cuts_m": [round(float(q1), 2), round(float(q2), 2)], **strata_res},
        "ablation_no_road_veto": {"pooled_dti": round(abl["dti"], 5),
                                  "dots_on_road_veto_zone": road_veto_mass},
        "uniqueness": {"pre_placement": {k: pre[k] for k in
                              ("verdict", "reason", "max_abs_spearman_rho", "argmax_rho",
                               "max_frac_dots_within_3px", "max_lift_over_random",
                               "argmax_lift", "n_compared", "identical_to")},
                       "post_placement": {k: post[k] for k in
                              ("verdict", "reason", "max_abs_spearman_rho", "argmax_rho",
                               "max_frac_dots_within_3px", "max_lift_over_random",
                               "argmax_lift", "n_compared", "identical_to")},
                       "raw_within3_all": max((r["frac_candidate_dots_within_3px"]
                                               for r in post["top"]), default=0.0)},
        "gate": gate,
        "seconds": round(time.time() - t0, 1),
        "surface": str(ROOT / "data/processed" / f"h67_surface_{name}.npy"),
    }
    np.save(ROOT / "data/processed" / f"h67_surface_{name}.npy", surf.astype(np.float32))
    np.save(ROOT / "data/processed" / f"h67_dots_{name}{'_complement' if complement else ''}{tag}.npy", dots)
    out(f"h67_e2_emit_{name}{'_complement' if complement else ''}{tag}.json", res)
    print(json.dumps({k: res[k] for k in ("holdout", "strata", "gate")}, indent=1))
    return res


# --------------------------------------------------------------------------- E3
def finalize(name: str) -> None:
    from gemsdoe66.submission import write_submission
    from gemsdoe66.holdout import novelty_truth as _nt
    dots = np.load(ROOT / "data/processed" / f"h67_dots_{name}.npy")
    L = load_layers()
    truth, folds = load_truth_folds()
    rng = np.random.default_rng(0)
    for mode in ("nan", "zeros"):
        p = ROOT / "artifacts" / "h67" / f"gems66-h67-{name}-37654-{mode}.tif"
        receipt = write_submission(dots.astype(np.float32), p, mode=mode)
        rep = validate(p, mode=mode, require_off_catalogue=2.0, expected_dots=N_DOTS)
        out(f"h67_e3_validate_{name}_{mode}.json",
            {"receipt": receipt, "validator": rep})
        print(f"{mode}: ok={rep['ok']} dots={rep['stats'].get('positive_pixels')}")
    # pooled holdout of the final bytes (re-read from disk)
    p = ROOT / "artifacts" / "h67" / f"gems66-h67-{name}-37654-nan.tif"
    with rasterio.open(p) as ds:
        a = ds.read(1)
    fin = score_emission(np.nan_to_num(a, nan=0.0).astype(np.float32), truth)
    out("h67_e3_final_holdout.json", {
        "label": "HOLDOUT-DTI, final bytes re-read from disk",
        "pooled_dti": round(fin["dti"], 5), "n_truth": int(truth.sum())})


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("canary")
    p = sub.add_parser("emit")
    p.add_argument("name", choices=list(NAMES) + ["h52_h_rank"])
    p.add_argument("--complement", action="store_true",
                   help="eligible only where >= 4 px from EVERY registry raster's dots")
    p.add_argument("--tag", default="")
    p2 = sub.add_parser("finalize")
    p2.add_argument("name", choices=list(NAMES) + ["h52_h_rank"])
    args = ap.parse_args()
    if args.cmd == "canary":
        canary()
    elif args.cmd == "emit":
        emit_candidate(args.name, complement=args.complement, tag=args.tag)
    else:
        finalize(args.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
