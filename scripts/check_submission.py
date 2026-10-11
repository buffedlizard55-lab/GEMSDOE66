#!/usr/bin/env python3
"""Re-run the format validator and the density-aware duplicate gate on a written GeoTIFF.

Also reports the *surface* duplicate check (the candidate field against every registry
raster), which the parallel-run protocol asks for "on the surface before placement AND on
the final dots".

    python3 scripts/check_submission.py docs/downloads/<file>-nan.tif [--surface field.npy]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gemsdoe66.grid import footprint_mask  # noqa: E402
from gemsdoe66.uniqueness import check_registry, read01  # noqa: E402
from gemsdoe66.validate_submission import validate, write_receipt  # noqa: E402


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

    gate = check_registry(cand.astype(np.float32), ROOT / "registry" / "rasters", fp)
    (ROOT / "evidence" / f"uniqueness_{p.stem}.json").write_text(json.dumps(gate, indent=1))
    print(f"\n[duplicate gate, dots] verdict={gate['verdict']}  reason={gate['reason']}")
    print(f"   max |rho| = {gate['max_abs_spearman_rho']:.4f}  ({gate['argmax_rho']})")
    print(f"   max within-3px = {gate['max_frac_dots_within_3px']:.4f}")
    print(f"   max lift over random = {gate['max_lift_over_random']:.3f}  ({gate['argmax_lift']})")
    print("   top 5 by lift:")
    for r in gate["top_by_lift"]:
        print(f"     {r['registry_file'][:52]:52s} w3={r['frac_candidate_dots_within_3px']:.3f} "
              f"null={r['null_within_3px_random_placement']:.3f} lift={r['lift_over_random']:.2f} "
              f"n_other={r['n_other']}")

    if args.surface:
        s = np.load(args.surface)
        gs = check_registry(s.astype(np.float32), ROOT / "registry" / "rasters", fp)
        (ROOT / "evidence" / f"uniqueness_surface_{p.stem}.json").write_text(
            json.dumps(gs, indent=1))
        print(f"\n[duplicate gate, surface] verdict={gs['verdict']}  reason={gs['reason']}")
        print(f"   max |rho| = {gs['max_abs_spearman_rho']:.4f}  ({gs['argmax_rho']})")
    return 0 if val["ok"] and gate["verdict"] == "UNIQUE" else 1


if __name__ == "__main__":
    sys.exit(main())
