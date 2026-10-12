#!/usr/bin/env python3
"""Write the single JSON run card for the LIDAR-01 session (lane protocol item 5).

Reads the evidence files produced by the session and writes:
  registry/run_card_lidar01.json    canonical card
  docs/data/run-card-lidar01.json   this session's card (only if --publish-card).
                                    It is deliberately NOT written to
                                    docs/data/run-card.json: that file is the
                                    canonical project card owned by the H67-1
                                    session, and a parallel session must not
                                    overwrite another session's record.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def load(rel, default=None):
    p = ROOT / rel
    return json.loads(p.read_text()) if p.exists() else default


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", default=None, help="emitted .tif (optional)")
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--uniqueness", default="evidence/lidar01_uniqueness.json")
    ap.add_argument("--verdict", default=None, choices=["promote", "negative"])
    ap.add_argument("--publish-card", action="store_true")
    args = ap.parse_args()

    canary = load("evidence/lidar_lane_canary.json")
    sweep = load("evidence/lidar_lane_blocks_holdout.json")
    trace = load("evidence/lidar_lane_traces_holdout.json")
    uniq = load(args.uniqueness)
    man = load(args.manifest) if args.manifest else None

    validator = None
    raster = {"status": "NOT GENERATED", "file": None, "sha256": None}
    if man:
        validator = man.get("validator")
        raster = {
            "status": "GENERATED",
            "file": man.get("tif"),
            "sha256": man.get("tif_sha256"),
            "bytes": man.get("bytes"),
            "dots": man.get("dots"),
            "budget": man.get("budget"),
            "separation_px": man.get("separation_px"),
            "gamma": man.get("gamma"),
            "validator_passed": man.get("validator_passed"),
        }
        if man.get("zip_sha256"):
            raster["zip"] = man.get("zip")
            raster["zip_sha256"] = man.get("zip_sha256")

    # Historical H66-1 artifacts stay WITHDRAWN: their identity is re-asserted here so a
    # future rebuild cannot quietly re-publish them.
    import subprocess
    try:
        _prev = json.loads(subprocess.run(
            ["git", "show", "HEAD:registry/run_card.json"], capture_output=True,
            text=True, cwd=str(ROOT)).stdout)
        historical_artifacts = _prev["raster"]["historical_artifacts"]
    except Exception:
        historical_artifacts = []

    card = {
        "schema": "gems-run-card/3",
        "run_id": "gemsdoe66-LIDAR-01-2026-10-12",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo": "buffedlizard55-lab/GEMSDOE66",
        "lane": "native-resolution LiDAR scarp channels",
        "hypothesis": (
            "A slope-aware antislope scarplet-template response combined with Steger/Frangi "
            "multiscale line evidence from the 2 m GeoDAWN lidar stack, used as an emission "
            "intensity rather than a ranking, will place dots on catalogue faults that were "
            "withheld from training better than mass-matched random placement and better than "
            "catalogue-distance alone."),
        "mechanism": (
            "A tectonic scarp step is a coherent, along-strike persistent, uphill-facing "
            "(antislope) monoclinal step; fluvial terrace risers, channel banks and field "
            "edges produce predominantly downslope- or cross-slope-facing steps. Subtracting "
            "the strongest competing step orientation from the antislope member isolates the "
            "tectonic-favouring signature, and the Hessian line measures reward along-strike "
            "persistence across scales."),
        "named_non_fault_mimic": (
            "Fluvial terrace riser / alluvial-fan head incision. The same signature is also "
            "produced by channel banks (cross_max), landslide headscarps, paleo-shorelines, "
            "and unmapped roads, canals and field edges; no cultural-feature mask was present "
            "in the restored inputs (see open_irregularities)."),
        "holdout_dti": {
            "label": "HOLDOUT-DTI",
            "evaluator_version": "src/gems/metric.py :: tversky_terms (alpha=0.2, beta=0.8, "
                                 "triangular kernel R=300 m, eps=1e-9)",
            "instruments": {
                "blocks": {
                    "description": "spatial-block hide-and-recover (lane protocol)",
                    "withheld_positive_count_per_fold": 6715,
                    "withheld_positive_per_fold": [6422, 6429, 7245, 6765],
                    "withheld_evidence": "evidence/lidar01_withheld_counts.json",
                    "n_folds": 4,
                    "variants": sweep.get("variants") if sweep else None,
                },
                "traces": {
                    "description": "global whole-trace holdout (catalogue proximity kept)",
                    "withheld_positive_count_per_fold": 12090,
                    "withheld_positive_per_fold": [12822, 10652, 11970, 12917],
                    "withheld_evidence": "evidence/lidar01_withheld_counts.json",
                    "n_folds": trace.get("n_folds") if trace else None,
                    "variants": trace.get("variants") if trace else None,
                },
            },
        },
        "leakage_canary": {
            "threshold_auc": 0.90,
            "status": "PASS - no channel exceeded the threshold" if canary and not canary.get("flagged")
                      else "REVIEW",
            "max_auc_observed": (canary.get("max_auc_observed") if canary else None)
            or (max(v["auc_max"] for v in canary["per_channel"].values())
                if canary and canary.get("per_channel") else None),
            "n_channels_tested": (len(canary["per_channel"]) if canary and canary.get("per_channel") else None),
            "flagged": canary.get("flagged") if canary else None,
            "evidence": "evidence/lidar_lane_canary.json",
        },
        "registry_checks": {
            "correlation_limit": 0.90,
            "overlap_limit": 0.70,
            "radius_px": 3,
            "rasters_compared": uniq.get("rasters_compared") if uniq else None,
            "max_abs_spearman": uniq.get("max_abs_spearman") if uniq else None,
            "max_dot_overlap_fraction": uniq.get("max_dot_overlap_fraction") if uniq else None,
            "duplicate": uniq.get("duplicate") if uniq else None,
            "verdict": uniq.get("verdict") if uniq else "NOT RUN",
            "completeness": (uniq or {}).get("completeness_caveat",
                                             "registry/rasters is a local mirror, not certified complete"),
        },
        "raster": raster,
        "raster_historical_artifacts": historical_artifacts,
        "validator": validator,
        "submission": {
            "name": man.get("name") if man else None,
            "note": man.get("note") if man else None,
            "note_chars": man.get("note_chars") if man else None,
            "note_limit_chars": 140,
            "file": man.get("tif") if man else None,
            "download_status": "OFFERED - published in docs/downloads/ and linked from the site index",
            "download_urls": {
                "tif": "downloads/" + (man.get("tif", "").split("/")[-1] if man else ""),
                "zip": "downloads/" + (man.get("zip", "").split("/")[-1] if man else ""),
            } if man else None,
            "organizer_confirmed_receipt": None,
        },
        "budget": {
            "new_experiments_used": 3,
            "max_experiments": 3,
            "submission_slots_used": 0,
            "note": "No competition submission slot was spent; promotion is a separate selector step.",
        },
        "open_irregularities": [
            "IR-72-NATIVE-SCALE", "IR-73-CULTURAL-MASK-MISSING",
            "IR-74-MIRROR-NOT-ORGANIZER", "IR-75-SCORE-COMPRESSION",
            "IR-76-TRACE-SUPERSET",
        ],
        "verdict": args.verdict or "negative",
    }

    out = ROOT / "registry" / "run_card_lidar01.json"
    out.write_text(json.dumps(card, indent=1))
    print(json.dumps({k: v for k, v in card.items()
                      if k in ("run_id", "verdict", "raster", "leakage_canary",
                               "registry_checks", "submission")}, indent=1))
    if args.publish_card:
        for dest in (ROOT / "docs" / "data" / "run-card-lidar01.json",
                     ROOT / "registry" / "run_card_lidar01.json"):
            dest.write_text(json.dumps(card, indent=1) + "\n")
        print("published docs/data/run-card-lidar01.json (+ registry mirror)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
