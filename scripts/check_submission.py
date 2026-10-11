#!/usr/bin/env python3
"""Re-run format checks and report diagnostics; never clear a candidate from a subset.

The local ``gemsdoe66`` comparison is diagnostic only. Release uniqueness is delegated to
``gems57`` and requires an organizer-complete indexed registry, raw final-dot thresholds,
and a separately supplied pre-placement surface. A missing index/surface fails closed.
This script NEVER grants download clearance: it runs the canonical run-card gate for
triage and returns blocked; publication requires a separate independently reviewed selector.

    python3 scripts/check_submission.py <candidate.tif> --surface field.npy
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gemsdoe66.grid import footprint_mask  # noqa: E402
from gemsdoe66.uniqueness import check_registry  # noqa: E402
from gemsdoe66.validate_submission import validate, write_receipt  # noqa: E402
from gems57.uniqueness import compare_array_to_registry  # noqa: E402
from gems.validate_submission import validate as validate_official_grid  # noqa: E402
from gems.release_gate import assess_release  # noqa: E402


def strict_registry_report(candidate: np.ndarray, footprint: np.ndarray, *, phase: str,
                           candidate_file_sha256: str | None = None) -> dict:
    """Apply the shared phase-aware gate; absence of its certified index is a stop."""
    index = ROOT / "evidence" / "registry_refreshed.json"
    if not index.is_file():
        return {
            "unique": False,
            "complete_registry_pass": False,
            "phase": phase,
            "n_compared": 0,
            "reason": "missing evidence/registry_refreshed.json; no organizer-complete index",
        }
    try:
        return compare_array_to_registry(
            candidate, index, footprint, file_sha256=candidate_file_sha256,
            phase=phase,
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {
            "unique": False,
            "complete_registry_pass": False,
            "phase": phase,
            "n_compared": 0,
            "reason": f"shared registry comparison failed closed: {exc}",
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tif")
    ap.add_argument("--mode", default=None,
                    help="inferred from the filename if omitted")
    ap.add_argument("--prune", type=float, default=2.0)
    ap.add_argument("--surface", default=None, help="the continuous field, as .npy")
    args = ap.parse_args()

    p = Path(args.tif)
    mode = args.mode or ("nan" if p.stem.endswith("-nan") else "zeros")
    fp = footprint_mask()

    val = validate(p, mode=mode, require_off_catalogue=args.prune)
    write_receipt(val, p.parent / f"checks-{p.name}.json")
    print(f"[format] ok={val['ok']}")
    for k, v in val["checks"].items():
        print(f"   {'PASS' if v else 'FAIL'}  {k}")
    print("   stats:", json.dumps(val["stats"]))

    with rasterio.open(p) as src:
        a = src.read(1)
    cand = np.nan_to_num(a, nan=0.0)

    diagnostic = check_registry(cand.astype(np.float32), ROOT / "registry" / "rasters", fp)
    (ROOT / "evidence" / f"uniqueness_{p.stem}.json").write_text(
        json.dumps(diagnostic, indent=1))
    print(f"\n[accessible-set diagnostic only] verdict={diagnostic['verdict']}  "
          f"reason={diagnostic['reason']}")
    print(f"   max |rho| = {diagnostic['max_abs_spearman_rho']:.4f}  "
          f"({diagnostic['argmax_rho']})")
    print(f"   raw max within-3px = {diagnostic['max_frac_dots_within_3px']:.4f}; "
          f"density-adjusted lift={diagnostic['max_lift_over_random']:.3f} (diagnostic only)")

    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    strict_dots = strict_registry_report(
        cand.astype(np.float32), fp, phase="emitted", candidate_file_sha256=sha)
    (ROOT / "evidence" / f"shared_uniqueness_{p.stem}-dots.json").write_text(
        json.dumps(strict_dots, indent=2))
    print(f"[shared release gate, final dots] unique={strict_dots.get('unique', False)}; "
          f"{strict_dots.get('reason', 'see report')}")

    strict_surface = {
        "unique": False,
        "complete_registry_pass": False,
        "phase": "surface",
        "reason": "no --surface field was supplied",
    }
    if args.surface:
        s = np.load(args.surface).astype(np.float32)
        if s.shape != fp.shape:
            strict_surface["reason"] = "surface shape differs from the footprint"
        elif not np.isfinite(s).all() or (s < 0).any() or (s > 1).any():
            strict_surface["reason"] = "surface must be finite and in [0,1] for the shared gate"
        else:
            s = s.copy()
            s[~fp] = 0.0
            strict_surface = strict_registry_report(
                s, fp, phase="surface",
                candidate_file_sha256=hashlib.sha256(Path(args.surface).read_bytes()).hexdigest())
        (ROOT / "evidence" / f"shared_uniqueness_{p.stem}-surface.json").write_text(
            json.dumps(strict_surface, indent=2))
        print(f"[shared release gate, pre-placement surface] "
              f"unique={strict_surface.get('unique', False)}; "
              f"{strict_surface.get('reason', 'see report')}")
    else:
        print("[shared release gate, pre-placement surface] BLOCKED: provide --surface field")

    # Legacy 'ok' and a partial raster scan are not scientific or official-grid clearance.
    # Re-read the candidate with the shared exact-grid/footprint validator. Missing reference
    # files are SKIPPED, never PASS. Even a complete machine preflight only permits a separate
    # independent selector review; this diagnostic CLI never publishes a submission.
    reference = ROOT / "data" / "bridge" / "sample_submission.tif"
    features = ROOT / "data" / "bridge" / "training_features.tif"
    official = validate_official_grid(p,
        reference_path=reference if reference.is_file() else None,
        features_path=features if features.is_file() else None)
    card = json.loads((ROOT / "docs" / "data" / "run-card.json").read_text())
    surface_sha = hashlib.sha256(Path(args.surface).read_bytes()).hexdigest() if args.surface else None
    decision = assess_release(p, card, official, strict_surface, strict_dots,
                              surface_sha256=surface_sha)
    print("\n[release decision] BLOCKED — check_submission is a diagnostic, not a selector")
    print(json.dumps(decision, indent=2))
    return 1


if __name__ == "__main__":
    sys.exit(main())
