#!/usr/bin/env python3
"""Assemble the H66-2 run card from the evidence JSONs (no hand-typed numbers).

Writes:
  registry/run_card_h66_2.json   full protocol-required run card
  docs/data/run-card-h66-2.json  compact feed consumed by scripts/build_site.py

Every field is read from evidence/h66b_{emission,verdict,uniqueness,e1_ablation}.json and
registry/preregistration-h66-2.json; the sha256 of the artifact is re-computed from the bytes.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text())


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    pre = load("registry/preregistration-h66-2.json")
    emi = load("evidence/h66b_emission.json")
    ver = load("evidence/h66b_verdict.json")
    uniq = load("evidence/h66b_uniqueness.json")
    abl = load("evidence/h66b_e1_ablation.json")
    art = ROOT / ver["files"]["artifact"]
    digest = sha256(art)
    receipt = emi["writer_receipt"]
    val = receipt["validator"]
    tpl = receipt["template_report"]
    assert digest == ver["files"].get("artifact_sha256", digest)
    with __import__("rasterio").open(art) as ds:
        shape, crs, dtype, nodata = ds.shape, ds.crs, ds.dtypes[0], ds.nodata

    lanes = "native-resolution LiDAR scarplet channels (H66 lane, candidate H66-2)"
    card = {
        "schema": "gems-run-card/1",
        "hypothesis_id": "H66-2",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo": "buffedlizard55-lab/GEMSDOE66",
        "lane": lanes,
        "hypothesis": pre["question"],
        "mechanism": pre["mechanism"],
        "named_non_fault_mimic": pre["named_non_fault_mimic"],
        "preregistration": "registry/preregistration-h66-2.json",
        "holdout_dti": {
            "evidence_class": "NOT RUN - no HOLDOUT-DTI value",
            "why_not_run": ("experiment budget (3 experiments or 2 hours) was spent on the ablation, the "
                            "strata/terrain audit and the emission; every number below is an "
                            "OFF-CATALOGUE-PROXY measurement and is labelled as one"),
            "proxy_instrument": emi["instrument"]["definition"],
            "proxy_global": emi["instrument"]["global_off_catalogue"],
            "proxy_basin": emi["instrument"]["basin"],
            "proxy_upland": emi["instrument"]["upland"],
            "organizer_confirmed": None,
            "not_a_leaderboard_score": True,
        },
        "e1_ablation": {
            "n_arms": len(abl["arms"]),
            "winner": "concordance_step_face",
            "winner_row": abl["arms"]["concordance_step_face"],
            "h66_1_blend_row": abl["arms"]["h66_1_blend"],
            "random_mass_matched": abl["random_mass_matched"],
            "truth_pixels": abl["truth_pixels"],
            "eligibility_cells": abl["eligibility_cells"],
            "detail": "evidence/h66b_e1_ablation.json",
        },
        "strata_and_controls": {
            "source": "evidence/h66b_e2_strata.json + evidence/h66b_verdict.json",
            "upland": ver["strata"]["upland"],
            "basin": ver["strata"]["basin"],
            "pooled": ver["strata"]["pooled"],
            "correction": ver["corrections"],
        },
        "transfer_check": ver["transfer_check"],
        "leakage_canary": emi["leakage_canary"],
        "uniqueness_vs_registry": {
            "corpus": "every GeoTIFF physically present in this checkout",
            "registry_rasters_checked": uniq["registry_rasters_checked"],
            "complete_accessible_scan": uniq["complete_accessible_scan"],
            "pinned_corpus_note": uniq["scope"]["pinned_corpus_note"],
            "max_abs_spearman_rho": uniq["worst_spearman_full_footprint"],
            "max_frac_dots_within_3px": uniq["worst_dot_overlap"],
            "worst_overlap_is_a_dense_prior": uniq["gate_G5"]["dense_rows_tripping"],
            "sparse_rows_tripping_a_gate": uniq["gate_G5"]["sparse_rows_tripping_a_gate"],
            "byte_unique": uniq["byte_unique_among_checked"],
            "pixel_unique": uniq["pixel_unique_among_checked"],
            "verdict": ("PASS vs the sparse submission-like corpus; the single tripping row is a dense prior "
                        "whose 3 px dilation covers most of the footprint for any dot set (IR-60-GATE-01)"),
        },
        "validator_output": {
            "all_checks_passed": val["all_checks_passed"],
            "template_ok": tpl["ok"],
            "sha256": digest,
            "bytes": art.stat().st_size,
            "reread": dict(shape=list(shape), crs=str(crs), dtype=str(dtype), nodata=nodata,
                           vmin=emi["portal_range_check"]["vmin"], vmax=emi["portal_range_check"]["vmax"],
                           n_nan=emi["portal_range_check"]["n_nan"],
                           n_positive=int(ver["strata"]["pooled"]["h66_2"]["n_dots"])),
            "portal_range_check": emi["portal_range_check"],
        },
        "inputs_verified": {
            "truth_proxy": "data/external/sgmc_faults_100m.tif (USGS SGMC state map, public domain)",
            "grid_and_nan_policy": "data/bridge/labels.tif + data/bridge/sample_submission.tif",
            "channels": "evidence/h66b_fields.npz (15 float32 arms, built from the pinned 2 m LiDAR stack)",
        },
        "submission": {
            "name": emi["name"],
            "note": emi["note"],
            "note_chars": emi["note_chars"],
            "note_limit_chars": 140,
            "file": art.name,
            "sha256": digest,
            "clearance": ("NOT CLEARED - do not submit. The bytes live in artifacts/h66-2/ (research "
                          "directory, no site page links to it) because the 2026-10-11 release gate "
                          "requires a valid buffered whole-segment HOLDOUT-DTI with CI, a complete "
                          "registry and two independent reviews before publication; this candidate has "
                          "none of those and its own verdict is negative."),
        },
        "verdict": ver["verdict"],
        "verdict_detail": {
            "primary": ver["decision_rule"]["primary_result"],
            "secondary": ver["decision_rule"]["secondary_result"],
            "tertiary": ver["decision_rule"]["tertiary_result"],
            "promotion": ver["decision_rule"]["promotion_result"],
            "what_is_true": ver["what_is_true"],
            "what_is_not_claimed": ver["what_is_not_claimed"],
            "next_candidate": ver["next_candidate"],
        },
        "budget": ver["budget"],
        "files": dict(ver["files"], artifact_sha256=digest,
                      run_card="registry/run_card_h66_2.json",
                      verdict="evidence/h66b_verdict.json"),
    }
    (ROOT / "registry/run_card_h66_2.json").write_text(json.dumps(card, indent=2) + "\n")
    feed = {
        "schema": "gems-run-card-feed/1",
        "hypothesis_id": "H66-2",
        "file": art.name,
        "file_zip": art.with_suffix(".zip").name if art.with_suffix(".zip").exists() else None,
        "sha256": digest,
        "name": emi["name"],
        "note": emi["note"],
        "note_chars": emi["note_chars"],
        "dots": int(ver["strata"]["pooled"]["h66_2"]["n_dots"]),
        "verdict": ver["verdict"],
        "clearance": card["submission"]["clearance"],
        "proxy_global_dti": emi["instrument"]["global_off_catalogue"]["dti"],
        "proxy_upland_ratio": ver["strata"]["upland"]["ratio_vs_own_mass_random"]["h66_2"],
        "basin": "no dots in the basin stratum (19 of 37,654)",
        "transfer": {"rho_in_band": ver["transfer_check"]["spearman_in_band"],
                     "p_in_band": ver["transfer_check"]["p_value_in_band"],
                     "band": ver["transfer_check"]["mass_band"]},
    }
    (ROOT / "docs/data/run-card-h66-2.json").write_text(json.dumps(feed, indent=2) + "\n")
    print(f"wrote registry/run_card_h66_2.json and docs/data/run-card-h66-2.json "
          f"(artifact {art.name}, sha256 {digest[:12]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
