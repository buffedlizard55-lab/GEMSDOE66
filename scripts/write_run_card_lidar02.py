#!/usr/bin/env python3
"""Assemble the LIDAR-02 run card from evidence/*.json (single source of truth).

Writes docs/data/run-card-lidar02-maxcov.json and the mirror registry/run_card_lidar02_maxcov.json.
If (and only if) E3 reported all gates met, also stages the release files into
docs/downloads/ and records the release block the site renders.  Run AFTER
scripts/run_lidar02b.py emit.  Never hand-edit the outputs.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVID = ROOT / "evidence"
DOCS_DATA = ROOT / "docs" / "data"
DL = ROOT / "docs" / "downloads"
ART = ROOT / "artifacts" / "lidar02"


def load(name):
    p = EVID / name
    return json.loads(p.read_text()) if p.exists() else None


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    can1, can2 = load("lidar02_canary.json"), load("lidar02b_canary.json")
    e2, e2b = load("lidar02_holdout.json"), load("lidar02b_holdout.json")
    emi = load("lidar02b_emission.json")
    if e2b is None or emi is None:
        print("E2b holdout/emission evidence missing - run run_lidar02b.py first", file=sys.stderr)
        return 2
    promote = bool(emi.get("all_gates_met"))
    release = {"offered_for_download": False}
    raster = {"exists": False}
    if promote:
        stem = emi["name"]
        src_nan, src_zero = ART / f"{stem}-nan.tif", ART / f"{stem}-zeros.tif"
        DL.mkdir(parents=True, exist_ok=True)
        for src in (src_nan, src_zero):
            shutil.copy2(src, DL / src.name)
            rcpt = Path(str(src) + ".receipt.json")
            if rcpt.exists():
                shutil.copy2(rcpt, DL / rcpt.name)
        zpath = DL / f"{stem}-nan.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(DL / src_nan.name, arcname=src_nan.name)
        manifest = {"name": stem, "tif": src_nan.name, "zeros_tif": src_zero.name,
                    "zip": zpath.name, "sha256": sha256_file(DL / src_nan.name),
                    "sha256_zeros": sha256_file(DL / src_zero.name),
                    "sha256_zip": sha256_file(zpath), "dots": emi["dots"],
                    "note": emi["note"], "generator": "scripts/run_lidar02b.py emit",
                    "validator_passed": emi["validator_nan_primary"]["passed"]}
        (DL / f"{stem}.manifest.json").write_text(json.dumps(manifest, indent=1))
        release = {"offered_for_download": True, "tif": src_nan.name,
                   "zeros_tif": src_zero.name, "zip": zpath.name,
                   "manifest": f"{stem}.manifest.json", "sha256": manifest["sha256"],
                   "sha256_zeros": manifest["sha256_zeros"], "dots": emi["dots"]}
        raster = {"exists": True, "file": f"docs/downloads/{src_nan.name}",
                  "sha256": manifest["sha256"], "dots": emi["dots"],
                  "dtype": "float32", "crs": "EPSG:32611", "shape_hw": [3730, 3292],
                  "values": "binary dots 1.0 on 0.0; NaN only outside footprint (-nan) / all-finite sibling (-zeros)"}

    vr = (emi.get("validator_nan_primary") or {})
    vchecks = vr.get("checks") or []
    n_pass = sum(1 for c in vchecks if c["status"] == "PASS")
    n_fail = sum(1 for c in vchecks if c["status"] == "FAIL")
    n_skip = sum(1 for c in vchecks if c["status"] == "SKIPPED")
    uniq = emi.get("uniqueness") or {}

    card = {
        "schema": "gems-run-card/1",
        "run_id": "lidar02-2026-10-20",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo": "buffedlizard55-lab/GEMSDOE66",
        "branch": "arena/c73a2700-gemsdoe66",
        "lane": "native-resolution lidar scarp channels (executed at 100-400 m on the cached 100 m aggregate of 2 m descriptors - native 2-20 m NOT measured, 1 m DEM unreachable from sandbox)",
        "hypothesis": ("LIDAR-02-A: local-SNR scarp prominence (slope-aware antislope template amplitude / "
                       "1 km local roughness) x cross-scale signed Steger persistence, emitted by kernel "
                       "max-cover, beats the global raw scarp field at equal budget on lidar-covered blocked "
                       "holdout, with gain not confined to range fronts. E2 FALSIFIED the veto-subtracted "
                       "field; E2b (preregistration amendment 3) tested the two surviving mechanisms: "
                       "no-veto prominence and max-cover emission on the raw field."),
        "mechanism": ("Detectability ranking (amplitude relative to local roughness) should promote low-relief "
                      "basin/piedmont scarps that global amplitude ranking starves (IR-74); cross-scale "
                      "persistence should reject single-scale cultural edges; max-cover emission matches the "
                      "DTI marginal-credit structure (alpha=0.2, 300 m kernel)."),
        "named_non_fault_mimic": ("Fluvial terrace riser / alluvial-fan head incision. Secondary: landslide "
                                  "headscarps, paleo-shorelines, canal banks, road cuts and field edges (no "
                                  "TIGER cultural mask reachable - IR-LIDAR02-CULT-01)."),
        "preregistration": "registry/preregistration-lidar02.json (3 amendments, each timestamped before the run it affected)",
        "holdout_dti": {
            "label": "HOLDOUT-DTI",
            "evaluator_version": "src/gems/metric.py :: tversky_terms (alpha=0.2, beta=0.8, triangular R=300 m, eps=1e-9)",
            "withheld_positives_pooled": e2b["holdout_spec"]["withheld_positives_pooled"],
            "withheld_positives_per_fold": e2b["holdout_spec"]["withheld_positives_per_fold"],
            "n_folds": 6,
            "segment_id_source": "8-connected components (PROXY, disclosed)",
            "arms_e2b": e2b["results"],
            "paired_e2b": e2b["paired"],
            "candidate_arm_by_preregistered_rule": emi.get("candidate_arm"),
            "arms_e2_falsified_field": (e2 or {}).get("results"),
            "paired_e2": (e2 or {}).get("paired"),
            "relief_strata_e2b": e2b["relief_strata"],
            "adaptivity_disclosure": e2b.get("adaptivity_disclosure"),
            "organizer_score": None,
            "organizer_score_label": "no ORGANIZER-CONFIRMED score exists; nothing was uploaded",
        },
        "leakage_canary": {
            "threshold_auc": 0.90,
            "max_auc_E1_channels": (can1 or {}).get("max_auc_observed"),
            "max_auc_E2b_channels": (can2 or {}).get("max_auc_observed"),
            "flagged": sorted(set((can1 or {}).get("flagged", []) + (can2 or {}).get("flagged", []))),
        },
        "gate_checks": emi.get("gate_checks"),
        "registry_checks": {
            "n_comparators": uniq.get("n_comparators_compared"),
            "identical_to_any": uniq.get("identical_to_any"),
            "max_abs_spearman_dots": uniq.get("max_abs_spearman_dots"),
            "surface_max_abs_spearman": uniq.get("surface_max_abs_spearman"),
            "worst_raw_overlap": uniq.get("worst_raw_overlap"),
            "literal_rule_trips_gt_0p70": uniq.get("literal_rule_trips_gt_0p70"),
            "unique_chance_corrected": uniq.get("unique_chance_corrected"),
            "evidence": "evidence/lidar02b_uniqueness.json",
        } if uniq else {"status": "not run (gate failed before emission)"},
        "raster": raster,
        "release": release,
        "validator": {
            "summary": (f"{n_pass} PASS / {n_fail} FAIL / {n_skip} SKIPPED" if vchecks else "not run (gate failed)"),
            "passed": vr.get("passed"),
            "checks": vchecks,
            "zeros_sibling_passed": (emi.get("validator_zeros_sibling") or {}).get("passed"),
        },
        "submission": {
            "name": emi.get("name"),
            "note": emi.get("note"),
            "note_chars": emi.get("note_chars"),
            "slots_used": 0,
            "uploaded": False,
        },
        "budget": {"experiments_used": 3, "experiments": ["E1 channels+canary", "E2 LIDAR-02-A holdout (falsified)", "E2b amendment-3 holdout"],
                   "wall_clock_note": "session 2026-10-20; see review doc"},
        "open_irregularities": ["IR-LIDAR02-CULT-01", "IR-LIDAR02-SCALE-01", "IR-LIDAR02-SITE-01", "IR-LIDAR02-SEG-01"],
        "promote": promote,
        "promotion_decision": "promote" if promote else "negative",
        "verdict": ("promote - all preregistered gates met (see gate_checks); download offered, slot NOT spent by this session"
                    if promote else
                    "negative - preregistered gate not met; no download offered, no slot spent"),
        "evidence_files": ["evidence/lidar02_canary.json", "evidence/lidar02_holdout.json",
                           "evidence/lidar02b_canary.json", "evidence/lidar02b_holdout.json",
                           "evidence/lidar02b_emission.json", "evidence/lidar02b_uniqueness.json"],
    }
    DOCS_DATA.mkdir(parents=True, exist_ok=True)
    (DOCS_DATA / "run-card-lidar02-maxcov.json").write_text(json.dumps(card, indent=1))
    (ROOT / "registry" / "run_card_lidar02_maxcov.json").write_text(json.dumps(card, indent=1))
    print(json.dumps({"promote": promote, "verdict": card["verdict"],
                      "release": release}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
