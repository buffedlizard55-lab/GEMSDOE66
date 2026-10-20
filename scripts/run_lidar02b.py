#!/usr/bin/env python3
"""LIDAR-02 E2b (final experiment; preregistration amendment 3, written before this ran).

Same folds, eligibility, budgets, evaluator and gate as E2.  New promup channels are
canaried here before any arm is scored.  Reuses scripts/run_lidar02.py machinery by import.
Stages: holdout | emit
"""
from __future__ import annotations

import argparse
import gc
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_lidar02 as R  # noqa: E402
from gems.constants import ALPHA, BETA  # noqa: E402
from gems.metric import dti_from_terms, tversky_terms  # noqa: E402

H, W = R.H, R.W
ARMS = ["random", "raw_topk", "raw_maxcov", "promup_topk", "promup_maxcov"]
CANDIDATES = ["promup_maxcov", "raw_maxcov"]
NEW_CHANNELS = ["prominence_up", "field_promup", "field_promup_cov"]


def canary_new(folds, footprint, lidar, mm, meta):
    from sklearn.metrics import roc_auc_score
    rng = np.random.default_rng(7)
    rows: dict[str, list[float]] = {}
    for f, sp in enumerate(folds):
        truth = sp["holdout"]
        dom = R.fold_domain(sp, footprint, lidar)
        bg = dom & ~sp["visible"] & ~sp["held_segment"] & ~sp["buffer_dropped"]
        bg_idx = np.flatnonzero(bg.ravel())
        if bg_idx.size > 150_000:
            bg_idx = rng.choice(bg_idx, 150_000, replace=False)
        t_idx = np.flatnonzero(truth.ravel())
        y = np.concatenate([np.ones(t_idx.size), np.zeros(bg_idx.size)])
        for name in NEW_CHANNELS:
            v = R.chan(mm, meta, name).ravel()
            x = np.concatenate([v[t_idx], v[bg_idx]]).astype(np.float64)
            if np.unique(x).size >= 2:
                rows.setdefault(name, []).append(float(roc_auc_score(y, x)))
            del v, x
        R.log(f"E2b canary fold {f}")
        gc.collect()
    res = {c: {"n_folds": len(v), "auc_mean": round(float(np.mean(v)), 6),
               "auc_max": round(float(np.max(v)), 6), "flag_leakage_if_above": 0.90,
               "leakage_flag": bool(max(v) > 0.90)} for c, v in rows.items()}
    out = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "stage": "E2b leakage canary for amendment-3 channels (LIDAR-02)",
           "instrument": "identical to evidence/lidar02_canary.json (same folds, same bg recipe/seed)",
           "per_channel": res,
           "flagged": sorted([c for c, v in res.items() if v["leakage_flag"]]),
           "max_auc_observed": round(max(v["auc_max"] for v in res.values()), 6)}
    (R.EVID / "lidar02b_canary.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return out


def stage_holdout():
    footprint, fault, lidar = R.base_masks()
    mm, meta = R.open_channels()
    folds = R.make_folds(fault, lidar)
    canary_new(folds, footprint, lidar, mm, meta)

    field_raw = R.chan(mm, meta, "field_raw")
    field_promup = R.chan(mm, meta, "field_promup")
    field_promup_cov = R.chan(mm, meta, "field_promup_cov")
    relief = R.chan(mm, meta, "relief")

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

    per_fold = {a: [] for a in ARMS}
    terms = {a: [0.0, 0.0, 0.0] for a in ARMS}
    strat_terms = {a: {s: [0.0, 0.0, 0.0] for s in range(3)} for a in ARMS}
    credit_tp = {a: {s: 0.0 for s in range(3)} for a in ARMS}
    strat_truth = {s: 0 for s in range(3)}
    dots_per_fold, withheld, placed = [], [], {a: [] for a in ARMS}

    for f, sp in enumerate(folds):
        truth = sp["holdout"]
        withheld.append(int(truth.sum()))
        dom = R.fold_domain(sp, footprint, lidar)
        eligible = dom & ~sp["visible"] & ~sp["buffer_dropped"]
        n_dots = int(round(R.FULL_DOTS * int(eligible.sum()) / n_elig_full))
        dots_per_fold.append(n_dots)
        rng = np.random.default_rng(1000 + f)
        preds = {
            "random": R.emit_topk(rng.random((H, W)).astype(np.float32), eligible, n_dots),
            "raw_topk": R.emit_topk(field_raw, eligible, n_dots),
            "promup_topk": R.emit_topk(field_promup, eligible, n_dots),
        }
        for a, fld in (("raw_maxcov", field_raw), ("promup_maxcov", field_promup_cov)):
            d = R.maxcov_dots(fld, eligible, n_dots)
            p = np.zeros((H, W), dtype=np.float32)
            p[d] = 1.0
            preds[a] = p
        for a in ARMS:
            placed[a].append(int((preds[a] > 0).sum()))
            tp, fp, fn = tversky_terms(preds[a], truth)
            per_fold[a].append(dti_from_terms(tp, fp, fn, ALPHA, BETA))
            terms[a] = [terms[a][0] + tp, terms[a][1] + fp, terms[a][2] + fn]
            for s in range(3):
                ts = truth & (strata == s)
                ps = np.where(strata == s, preds[a], 0.0).astype(np.float32)
                tp2, fp2, fn2 = tversky_terms(ps, ts)
                strat_terms[a][s] = [strat_terms[a][s][0] + tp2, strat_terms[a][s][1] + fp2,
                                     strat_terms[a][s][2] + fn2]
                del ps
                tp3, _, _ = tversky_terms(preds[a], ts)  # full pred: kernel credit diagnostic
                credit_tp[a][s] += tp3
            R.log(f"E2b fold {f} arm {a}: HOLDOUT-DTI={per_fold[a][-1]:.5f} dots={placed[a][-1]}")
        for s in range(3):
            strat_truth[s] += int((truth & (strata == s)).sum())
        del preds
        gc.collect()

    def summ(a):
        m, ci = R.mean_ci(per_fold[a])
        return {"label": "HOLDOUT-DTI", "per_fold": [round(x, 6) for x in per_fold[a]],
                "mean": round(m, 6), "ci95": ci,
                "pooled": round(dti_from_terms(*terms[a], ALPHA, BETA), 6),
                "terms_pooled": [round(x, 3) for x in terms[a]],
                "dots_placed_per_fold": placed[a]}

    def paired(a, b):
        d = np.asarray(per_fold[a]) - np.asarray(per_fold[b])
        m, ci = R.mean_ci(d)
        return {"mean": round(m, 6), "ci95": ci, "ci_lower_gt_0": bool(ci and ci[0] > 0),
                "per_fold": [round(float(x), 6) for x in d]}

    strata_out, credit_out = {}, {}
    for s in range(3):
        strata_out[stratum_names[s]] = {
            "pooled_withheld_positives": strat_truth[s], "judged": bool(strat_truth[s] >= 100),
            **{a: round(dti_from_terms(*strat_terms[a][s], ALPHA, BETA), 6) for a in ARMS}}
        base = credit_tp["random"][s] / max(strat_truth[s], 1)
        credit_out[stratum_names[s]] = {
            "diagnostic_only_not_a_gate": True,
            "kernel_credit_per_truth_pixel": {a: round(credit_tp[a][s] / max(strat_truth[s], 1), 6) for a in ARMS},
            "lift_vs_random": {a: round((credit_tp[a][s] / max(strat_truth[s], 1)) / base, 4) if base > 0 else None for a in ARMS}}

    out = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stage": "E2b blocked holdout (LIDAR-02, preregistration amendment 3)",
        "adaptivity_disclosure": ("E2b arms were motivated by E2 diagnostics (evidence/lidar02_holdout.json) "
                                  "and the E1 canary; folds/budgets/gate are identical to E2 but the holdout "
                                  "is no longer untouched - read as exploratory-confirmatory."),
        "evaluator": "src/gems/metric.py :: tversky_terms (alpha=0.2, beta=0.8, triangular R=300 m, eps=1e-9)",
        "holdout_spec": {"identical_to_E2": True, "dots_per_fold": dots_per_fold,
                         "withheld_positives_per_fold": withheld,
                         "withheld_positives_pooled": int(sum(withheld)),
                         "eligible_full_grid_cells": n_elig_full},
        "arms": {
            "random": "uniform random field, spacing top-K (mass-matched null)",
            "raw_topk": "field_raw + spacing top-K (E2 reference, identical recipe)",
            "raw_maxcov": "field_raw + batched greedy kernel max-cover (diagnostic candidate)",
            "promup_topk": "field_promup (no-veto prominence x persistence) + spacing top-K",
            "promup_maxcov": "field_promup_cov + batched greedy kernel max-cover (primary candidate)",
        },
        "candidate_selection_rule_preregistered": "higher pooled DTI among {promup_maxcov, raw_maxcov}; all original gate conditions vs raw_topk/random must hold; CIs unadjusted for the 2-candidate selection (disclosed)",
        "results": {a: summ(a) for a in ARMS},
        "paired": {f"{a}_minus_raw_topk": paired(a, "raw_topk") for a in CANDIDATES} | {
            f"{a}_minus_random": paired(a, "random") for a in CANDIDATES} | {
            "promup_maxcov_minus_promup_topk": paired("promup_maxcov", "promup_topk"),
            "raw_maxcov_minus_raw_topk_dup": paired("raw_maxcov", "raw_topk")},
        "relief_strata": {"cuts_m": [round(q1, 3), round(q2, 3)],
                          "per_stratum_pooled_holdout_dti": strata_out,
                          "kernel_credit_lift_diagnostic": credit_out},
        "scale_disclosure": meta["scale_disclosure"],
    }
    (R.EVID / "lidar02b_holdout.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({a: out["results"][a] for a in ARMS}, indent=1))
    print(json.dumps(out["paired"], indent=1))
    print(json.dumps(out["relief_strata"], indent=1))
    return 0


def gate_e2b():
    can1 = json.loads((R.EVID / "lidar02_canary.json").read_text())
    can2 = json.loads((R.EVID / "lidar02b_canary.json").read_text())
    hold = json.loads((R.EVID / "lidar02b_holdout.json").read_text())
    r = hold["results"]
    cand = max(CANDIDATES, key=lambda a: r[a]["pooled"])
    st = hold["relief_strata"]["per_stratum_pooled_holdout_dti"]
    off_detail, off = {}, False
    for name in ("low_relief_basin", "mid_relief"):
        s = st[name]
        ok = bool(s["judged"] and s[cand] > s["random"])
        off_detail[name] = {"judged": s["judged"], "candidate": s[cand], "random": s["random"],
                            "beats_random": ok}
        off = off or ok
    checks = {
        "canary_clear_E1_and_E2b": bool(not can1["flagged"] and not can2["flagged"]),
        "pooled_candidate_gt_raw_topk": bool(r[cand]["pooled"] > r["raw_topk"]["pooled"]),
        "paired_candidate_minus_raw_topk_ci_lower_gt_0": hold["paired"][f"{cand}_minus_raw_topk"]["ci_lower_gt_0"],
        "paired_candidate_minus_random_ci_lower_gt_0": hold["paired"][f"{cand}_minus_random"]["ci_lower_gt_0"],
        "not_confined_to_range_fronts": bool(off),
    }
    return cand, checks, off_detail, hold


def stage_emit():
    from gems.submission_writer import write_submission
    from gems.validate_submission import validate
    cand, checks, off_detail, hold = gate_e2b()
    R.log(f"E2b candidate by preregistered rule: {cand}; gate: {checks}")
    base = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "stage": "E3 gated emission (LIDAR-02, via E2b)", "candidate_arm": cand,
            "gate_checks": checks, "off_range_front_detail": off_detail}
    if not all(checks.values()):
        base["verdict"] = "negative - gate not met; no raster offered for download, no slot spent"
        (R.EVID / "lidar02b_emission.json").write_text(json.dumps(base, indent=1))
        print(json.dumps(base, indent=1))
        return 3

    footprint, fault, lidar = R.base_masks()
    mm, meta = R.open_channels()
    field_name = "field_promup_cov" if cand == "promup_maxcov" else "field_raw"
    surface = R.chan(mm, meta, "field_promup" if cand == "promup_maxcov" else "field_raw")
    fld = R.chan(mm, meta, field_name)
    eligible = footprint & lidar & ~fault
    dots = R.maxcov_dots(fld, eligible, R.FULL_DOTS)
    pred = np.zeros((H, W), dtype=np.float32)
    pred[dots] = 1.0
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    tag = "promup-persist" if cand == "promup_maxcov" else "rawscarp"
    stem = f"gems66-lidar02-{tag}-maxcov-{int(dots.sum())}dots-{ts}"
    note = ("LIDAR-02 no-veto local-SNR scarp prominence x Steger persistence, kernel max-cover"
            if cand == "promup_maxcov" else
            "LIDAR-02 lidar scarp field (template+Frangi ranks), kernel max-cover emission")
    assert len(note) <= 140, len(note)
    outdir = ROOT / "artifacts" / "lidar02"
    outdir.mkdir(parents=True, exist_ok=True)
    receipts = {}
    for suffix, fill in (("-nan", None), ("-zeros", 0.0)):
        p = outdir / f"{stem}{suffix}.tif"
        receipts[suffix] = write_submission(p, pred, footprint, R.RAW / "sample_submission.tif",
                                            name=f"{stem}{suffix}", note=note, outside_fill=fill)
        R.log(f"wrote {p.name} sha256={receipts[suffix]['sha256'][:16]}...")
    primary = outdir / f"{stem}-nan.tif"
    report = validate(primary, R.RAW / "sample_submission.tif", R.RAW / "training_features.tif")
    report_z = validate(outdir / f"{stem}-zeros.tif", R.RAW / "sample_submission.tif",
                         R.RAW / "training_features.tif", outside_policy="either")
    uniq = R.uniqueness(primary, surface)
    u_ok = bool(uniq["unique_chance_corrected"] and not uniq["identical_to_any"]
                and (uniq["surface_max_abs_spearman"] is None or uniq["surface_max_abs_spearman"] <= 0.90)
                and uniq["max_abs_spearman_dots"] <= 0.90)
    base.update({"name": stem, "note": note, "note_chars": len(note), "dots": int(dots.sum()),
                 "field_used_for_placement": field_name, "receipts": receipts,
                 "validator_nan_primary": report, "validator_zeros_sibling": report_z,
                 "uniqueness": uniq, "uniqueness_ok": u_ok,
                 "all_gates_met": bool(all(checks.values()) and report["passed"] and u_ok)})
    (R.EVID / "lidar02b_emission.json").write_text(json.dumps(base, indent=1))
    (R.EVID / "lidar02b_uniqueness.json").write_text(json.dumps(uniq, indent=1))
    print(json.dumps({"name": stem, "dots": int(dots.sum()), "validator_passed": report["passed"],
                      "unique_ok": u_ok, "all_gates_met": base["all_gates_met"]}, indent=1))
    return 0 if base["all_gates_met"] else 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["holdout", "emit"])
    a = ap.parse_args()
    return stage_holdout() if a.stage == "holdout" else stage_emit()


if __name__ == "__main__":
    sys.exit(main())
