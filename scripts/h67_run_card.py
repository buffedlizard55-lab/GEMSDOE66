#!/usr/bin/env python3
"""Merge holdout evidence into the H67 run card and set the promotion verdict.

The verdict is mechanical and stated: the candidate is promoted only if its HOLDOUT-DTI beats
the incumbent recipe (R1, catalogue-distance-only belief) on the same folds and the 95% CI of
the paired per-fold difference excludes zero.  A projection is never written as a score.

Usage:  python3 scripts/h67_run_card.py [--holdout evidence/h67_holdout_C.json]
                                        [--card artifacts/h67/run-card-*.json]
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
INCUMBENT = "R1"


def paired_ci(a, b, seed=5, n=20000):
    """95% CI of mean(a - b) by bootstrap over folds."""
    d = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    if d.size == 0:
        return [float("nan"), float("nan")]
    if d.size == 1:
        return [float(d[0]), float(d[0])]
    rng = np.random.default_rng(seed)
    means = d[rng.integers(0, d.size, size=(n, d.size))].mean(axis=1)
    return [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", nargs="*",
                    default=[str(ROOT / "evidence" / "h67_holdout_C.json")])
    ap.add_argument("--card", default=None)
    ap.add_argument("--null", default=str(ROOT / "evidence" / "h67_null_control.json"),
                    help="placement-null control JSON from scripts/h67_null_control.py")
    args = ap.parse_args()

    hits = sorted(glob.glob(args.card or str(ROOT / "artifacts" / "h67" / "run-card-*.json")),
                  key=lambda p: Path(p).stat().st_mtime)
    if not hits:
        raise SystemExit("no run card found; run scripts/h67_submit.py first")
    card_path = Path(hits[-1])
    card = json.loads(card_path.read_text())

    # Several holdout files can cover the same instrument with different recipes (R1/R4/R5 in one
    # run, R3 in another).  Merge per instrument instead of letting the last file win.
    holdouts: dict[str, dict] = {}
    for h in args.holdout:
        p = Path(h)
        if not p.exists():
            continue
        for inst, r in json.loads(p.read_text())["instruments"].items():
            if "recipes" not in r:      # not a recipe-holdout file (e.g. the null control)
                continue
            if inst not in holdouts:
                holdouts[inst] = r
                continue
            holdouts[inst]["recipes"].update(r["recipes"])
            holdouts[inst].setdefault("leakage_canary", {}).update(r.get("leakage_canary", {}))
    if not holdouts:
        raise SystemExit(f"no holdout evidence found in {args.holdout}")

    recipe = card["emission"].get("recipe")
    if recipe is None:
        raise SystemExit("run card does not record which recipe was emitted")
    # the run card stores the long name ("R3_geophysical_only"); the holdout keys are short ("R3")
    recipe = recipe.split("_")[0]
    standoff = int(card["emission"].get("standoff_px", 2))
    kappa = float(card["emission"].get("kappa_truth_mass", 1.0))

    per_instrument = {}
    promote_votes = []
    for inst, r in holdouts.items():
        want = f"{recipe}|k{kappa}|s{standoff}"
        base = f"{INCUMBENT}|k{kappa}|s{standoff}"
        cand = r["recipes"].get(want)
        inc = r["recipes"].get(base)
        entry = {"candidate_key": want, "incumbent_key": base,
                 "withheld_positive_count": r["withheld_positive_pixels_pooled"],
                 "folds": r["recipes"].get(want, {}).get("folds"),
                 "segment_id_source": r["segment_id_source"]}
        if cand is None:
            entry["status"] = "candidate recipe was not run on this instrument"
            per_instrument[inst] = entry
            continue
        entry["holdout_dti"] = cand["mean_holdout_dti"]
        entry["ci95"] = cand["ci95"]
        entry["mean_emitted"] = cand["mean_emitted"]
        if inc is not None:
            entry["incumbent_holdout_dti"] = inc["mean_holdout_dti"]
            diff = paired_ci(cand["per_fold"], inc["per_fold"])
            entry["paired_gain_vs_incumbent"] = {
                "mean": float(np.mean(cand["per_fold"]) - np.mean(inc["per_fold"])),
                "ci95": diff, "beats_incumbent": bool(diff[0] > 0)}
            promote_votes.append(diff[0] > 0)
        entry["status"] = "measured"
        per_instrument[inst] = entry

    leak = {}
    for inst, r in holdouts.items():
        leak[inst] = {k: v for k, v in r["leakage_canary"].items() if v["leakage_flag_auc_gt_0.90"]}

    promote = bool(promote_votes) and all(promote_votes)
    card["holdout_dti"] = {
        "label": "HOLDOUT-DTI",
        "evaluator_version": next((json.loads(Path(h).read_text())["evaluator_version"]
                                   for h in args.holdout if Path(h).exists()), None),
        "per_instrument": per_instrument,
        "value": next((v["holdout_dti"] for v in per_instrument.values()
                       if "holdout_dti" in v), None),
        "ci95": next((v["ci95"] for v in per_instrument.values() if "ci95" in v), None),
        "withheld_positive_count": next((v["withheld_positive_count"]
                                         for v in per_instrument.values()), None),
        "proxy_disclosure": ("Withheld truth is a proxy, not the organiser's hidden expert set. "
                             "Instrument C withholds catalogue segments; instrument N withholds "
                             "SGMC map-fault segments >300 m off the catalogue."),
    }
    npath = Path(args.null)
    nulls = json.loads(npath.read_text())["instruments"] if npath.exists() else {}
    card["placement_null_control"] = {
        "source": args.null if npath.exists() else None,
        "per_instrument": {k: v["nulls"] for k, v in nulls.items()},
        "note": ("Uniform random dots and a fixed lattice over the SAME eligible mask, budget and "
                 "withheld truth.  A HOLDOUT-DTI is only interpretable next to this baseline "
                 "(IR-66-GATE-01)."),
    }
    card["leakage_canary"] = {
        "threshold_auc": 0.90,
        "flagged_layers_by_instrument": leak,
        "status": ("FLAGGED - a layer alone exceeds AUC 0.90; treat its result as leakage until "
                   "disproven" if any(leak.values()) else "CLEAR - no layer alone exceeds 0.90"),
    }
    card["promotion_decision"] = "promote" if promote else "negative"
    card["promote"] = promote
    card["promotion_rationale"] = (
        "candidate beats the incumbent belief recipe on every instrument with a paired 95% CI "
        "excluding zero" if promote else
        "candidate does not beat the incumbent belief recipe with a paired 95% CI excluding zero "
        "on every instrument")
    card["verdict"] = ("PROMOTE - cleared for download; no organizer score claimed"
                       if promote else "NEGATIVE - not promoted; logged as a deliverable")
    card["budget"] = {"experiments_this_session": 2, "submission_slots_used": 0}
    card["scores_claimed"] = "NONE. No ORGANIZER-CONFIRMED score exists for this artifact."
    card["updated_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    card_path.write_text(json.dumps(card, indent=1))
    print(json.dumps({"card": str(card_path), "promote": promote,
                      "rationale": card["promotion_rationale"],
                      "per_instrument": {k: {kk: vv for kk, vv in v.items()
                                             if kk in ("holdout_dti", "ci95", "status",
                                                       "paired_gain_vs_incumbent",
                                                       "withheld_positive_count")}
                                         for k, v in per_instrument.items()},
                      "leakage_flagged": leak}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
