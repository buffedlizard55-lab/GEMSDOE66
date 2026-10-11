#!/usr/bin/env python3
"""Emit the run card required by the parallel-run protocol.

One JSON object, built from the evidence files rather than by hand:

    hypothesis; mechanism; the named non-fault process that could mimic it; holdout DTI + CI;
    correlation/overlap vs registry; raster sha256; validator output; submission name +
    note (<= 140 chars); verdict promote / negative.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def load(p):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return {}


def main() -> int:
    dl = sorted((ROOT / "docs" / "downloads").glob("*.manifest.json"))
    if not dl:
        print("no submission manifest found")
        return 1
    man = load(dl[-1])
    slug = man["slug"]
    checks = load(ROOT / "docs" / "downloads" / f"checks-{slug}-nan.tif.json")
    uniq_dots = load(next(iter((ROOT / "evidence").glob(f"uniqueness_{slug}-nan.json")), ""))
    uniq_surf = load(next(iter((ROOT / "evidence").glob("uniqueness_surface_*.json")), ""))
    e1 = load(ROOT / "evidence" / "experiment1_parsed.json")
    e3 = load(ROOT / "evidence" / "experiment3_controls.json")
    rf = load(ROOT / "evidence" / "range_front_stratification.json")
    rg = load(ROOT / "evidence" / "relief_gate.json")
    sb = load(ROOT / "evidence" / f"submission_{slug}.json")

    lane = e1.get("lidar_lane", {}).get("N", [])
    inc = e1.get("incumbent", {}).get("N", [])
    chance = e3.get("chance", {})

    note = (f"GEMSDOE66 lane: Frangi/Steger/structure-tensor scarp field from 1 m GeoDAWN "
            f"lidar, {man.get('n_dots', 0):,} dots, 0 within 200 m of the catalogue.")
    assert len(note) <= 140, len(note)

    gate_met = (
        lane and inc and chance
        and (sum(lane) / len(lane)) > (sum(inc) / len(inc))
        and chance.get("lane_minus_random", {}).get("ci95", [1, -1])[0] > 0
        and checks.get("ok") is True
        and uniq_dots.get("verdict") == "UNIQUE"
    )
    card = {
        "lane": "native-resolution lidar scarp channels (scarplet / Steger / Frangi)",
        "hypothesis": (
            "Faults the USGS Quaternary catalogue lacks are, in the GeoDAWN region, faults "
            "whose scarps are visible in 1 m lidar but are averaged away at 100 m; therefore a "
            "multiscale line/structure-tensor field built on the 1 m-LiDAR-derived scarp "
            "descriptors and the slope-detrended elevation should rank off-catalogue fault "
            "pixels higher than the geophysical-habitat fields the project family has used, "
            "and higher than chance."),
        "mechanism": (
            "Frangi multiscale vesselness (both polarities) + Steger sub-pixel line "
            "localisation + structure-tensor orientation coherence and dominant strike, at "
            "2-20 pixel scales on the 100 m detrended elevation, fused with 1 m-LiDAR scarp "
            "amplitude x coherence and a strike-concordance gate, then masked against flat / "
            "very steep cultural ground. Emitted as 37,654 dots at >= 2.82 px separation with "
            "every dot within 200 m of the known catalogue deleted."),
        "non_fault_process_that_could_mimic_it": (
            "Fluvial terrace risers, alluvial-fan incisement edges, landslide head scarps, "
            "and - most importantly on flat ground - road cuts, canal banks and field "
            "boundaries all produce lineated 1 m scarps with high Hessian response. The "
            "strike-concordance term and the relief/slope cultural mask are the controls; the "
            "measured result is that the control is incomplete on basin floors, where the "
            "field's gain over chance is -0.003 (4/8 folds)."),
        "holdout": {
            "evaluator_version": "gemsdoe66.metric.dti (verified to 1e-9 against a brute-force "
                                 "transcription of the organiser's equations)",
            "instrument": "novelty - SGMC fault pixels > 300 m from the given catalogue",
            "n_withheld_positives_per_fold": "~7,700 (8 spatially coherent balanced folds by "
                                             "connected component; 300 m buffer, training only)",
            "metric": "pooled distance-weighted Tversky, alpha=0.2, beta=0.8, R=300 m",
            "matched_envelope": "37,654 dots, min separation 2.82 px, 0 dots within 200 m of "
                                "the catalogue, identical for every field",
            "lidar_lane_dti": round(sum(lane) / len(lane), 5) if lane else None,
            "lidar_lane_ci95": chance.get("lidar_lane", {}).get("ci95"),
            "incumbent_0.2778_raster_dti": round(sum(inc) / len(inc), 5) if inc else None,
            "incumbent_ci95": chance.get("incumbent_prior", {}).get("ci95"),
            "chance_level_dti": chance.get("random", {}).get("mean"),
            "chance_ci95": chance.get("random", {}).get("ci95"),
            "lane_minus_chance": chance.get("lane_minus_random", {}).get("mean"),
            "lane_minus_chance_ci95": chance.get("lane_minus_random", {}).get("ci95"),
            "lane_minus_chance_folds_positive":
                chance.get("lane_minus_random", {}).get("folds_positive"),
            "lane_vs_incumbent": (round(sum(lane) / len(lane) - sum(inc) / len(inc), 5)
                                  if lane and inc else None),
            "range_front_stratification": rf.get("strata"),
            "range_front_verdict": rf.get("verdict"),
            "relief_gate_measured_not_shipped": rg.get("gates"),
        },
        "correlation_overlap_vs_registry": {
            "n_registry_rasters_compared": uniq_dots.get("n_compared")
            or sb.get("uniqueness", {}).get("n_compared"),
            "max_abs_spearman_rho_dots": uniq_dots.get("max_abs_spearman_rho")
            or sb.get("uniqueness", {}).get("max_abs_spearman_rho"),
            "argmax_rho_dots": uniq_dots.get("argmax_rho")
            or sb.get("uniqueness", {}).get("argmax_rho"),
            "max_abs_spearman_rho_surface": uniq_surf.get("max_abs_spearman_rho"),
            "argmax_rho_surface": uniq_surf.get("argmax_rho"),
            "max_frac_dots_within_3px": uniq_dots.get("max_frac_dots_within_3px")
            or sb.get("uniqueness", {}).get("max_frac_dots_within_3px"),
            "max_lift_over_random": uniq_dots.get("max_lift_over_random"),
            "verdict": uniq_dots.get("verdict") or sb.get("uniqueness", {}).get("verdict"),
            "thresholds": {"max_rho": 0.90, "max_within3": 0.70, "min_lift": 1.5},
        },
        "raster": {
            "filename": f"{slug}-nan.tif",
            "sha256": checks.get("sha256"),
            "size_bytes": checks.get("size_bytes"),
            "zeros_variant_sha256": load(
                ROOT / "docs" / "downloads" / f"checks-{slug}-zeros.tif.json").get("sha256"),
        },
        "validator_output": {
            "no_nan_inside_footprint": checks.get("checks", {}).get("in_footprint_zero_nan"),
            "values_in_0_1": checks.get("checks", {}).get("in_footprint_range_0_1"),
            "crs_shape_transform_match": all([
                checks.get("checks", {}).get("crs_epsg_32611"),
                checks.get("checks", {}).get("dimensions_3730x3292"),
                checks.get("checks", {}).get("transform_matches_template")]),
            "nan_only_outside_footprint": checks.get("checks", {}).get("outside_footprint_nan"),
            "dtype_float32_single_band": all([
                checks.get("checks", {}).get("dtype_float32"),
                checks.get("checks", {}).get("single_band")]),
            "all_checks": checks.get("checks"),
            "ok": checks.get("ok"),
        },
        "submission": {
            "name": slug,
            "note_140chars": note,
            "note_length": len(note),
        },
        "verdict": "promote" if gate_met else "negative",
        "verdict_basis": (
            "gate = lane beats the incumbent's raster on the novelty holdout AND the "
            "lane-minus-chance 95% CI excludes zero AND the format validator passes on the "
            "bytes AND the duplicate gate returns UNIQUE"),
        "not_claimed": (
            "no organiser score exists for this or any artifact here; the holdout truth is "
            "SGMC, not the expert panel's hidden set; promotion here means 'meets the local "
            "gate', not 'will score X'"),
    }
    out = ROOT / "evidence" / f"run_card_{slug}.json"
    out.write_text(json.dumps(card, indent=1))
    (ROOT / "docs" / "data").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs" / "data" / "run_card.json").write_text(json.dumps(card, indent=1))
    print(json.dumps({k: card[k] for k in
                      ("lane", "verdict", "submission", "raster")}, indent=1))
    print("\nholdout:", json.dumps(card["holdout"], indent=1)[:1400])
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
