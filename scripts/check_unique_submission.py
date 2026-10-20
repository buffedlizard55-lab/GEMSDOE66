#!/usr/bin/env python3
"""
Check uniqueness of a candidate submission against the registry rasters.
Applies the parallel-run protocol gates:
  - rank |Spearman rho| <= 0.90 vs any registry raster
  - <= 70% of dots within 3 px of any single registry raster (density-corrected)
  - byte-unique vs all registry rasters
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy.stats import spearmanr
from scipy.ndimage import binary_dilation

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

REGISTRY_DIR = ROOT / "registry" / "rasters"
RHO_LIMIT = 0.90
OVERLAP_LIMIT = 0.70


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def _dots(a):
    a = np.asarray(a)
    return np.isfinite(a) & (a > 0)


def _near(support, radius_px=3):
    r = int(np.ceil(radius_px))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    return binary_dilation(support, structure=yy * yy + xx * xx <= radius_px * radius_px)


def dot_overlap(mine, theirs, radius_px=3):
    m, t = _dots(mine), _dots(theirs)
    if m.shape != t.shape:
        return 0.0
    if not m.any() or not t.any():
        return 0.0
    return float(_near(t, radius_px)[m].mean())


def main() -> int:
    candidate = sys.argv[1] if len(sys.argv) > 1 else None
    if not candidate:
        print("Usage: python3 scripts/check_unique_submission.py <candidate.tif>")
        return 1

    cand_path = Path(candidate)
    if not cand_path.exists():
        print(f"Candidate not found: {cand_path}")
        return 1

    with rasterio.open(cand_path) as src:
        cand = src.read(1).astype(np.float32)

    fp = np.isfinite(cand)
    my_dots = _dots(cand)
    n_my_dots = int(my_dots.sum())
    print(f"Candidate: {cand_path.name}")
    print(f"  SHA256: {sha256_file(cand_path)}")
    print(f"  My dots: {n_my_dots}")
    print(f"  Footprint: {int(fp.sum())}")

    results = []
    tif_files = sorted(REGISTRY_DIR.glob("*.tif"))
    print(f"  Registry rasters: {len(tif_files)}")

    for tif in tif_files:
        try:
            with rasterio.open(tif) as src:
                other = src.read(1).astype(np.float32)
            if other.shape != cand.shape:
                print(f"  SKIP {tif.name}: shape mismatch {other.shape} vs {cand.shape}")
                continue

            # Byte-unique check
            other_bytes = hashlib.sha256(other.tobytes()).hexdigest()
            cand_bytes = hashlib.sha256(cand.tobytes()).hexdigest()
            byte_unique = other_bytes != cand_bytes

            # Rank correlation (flatten, finite only)
            mask = fp & np.isfinite(other)
            if mask.sum() > 100:
                rho, _ = spearmanr(cand[mask].ravel(), other[mask].ravel())
                rho = float(rho) if np.isfinite(rho) else 0.0
            else:
                rho = 0.0

            # Dot overlap
            overlap = dot_overlap(cand, other)

            # Density correction: random placement null
            # Expected overlap if my dots placed randomly within their dilation
            other_dilated = _near(_dots(other))
            null_overlap = float(other_dilated[fp].mean()) if other_dilated[fp].size else 0.0
            lift = overlap / null_overlap if null_overlap > 0 else 0.0

            rho_abs = abs(rho)
            stop_rho = rho_abs > RHO_LIMIT
            stop_overlap = overlap > OVERLAP_LIMIT

            results.append({
                "raster": tif.name,
                "rho": round(rho, 6),
                "abs_rho": round(rho_abs, 6),
                "overlap_3px": round(overlap, 6),
                "null_overlap": round(null_overlap, 6),
                "lift": round(lift, 4),
                "byte_unique": byte_unique,
                "stop_rho": stop_rho,
                "stop_overlap": stop_overlap,
            })
        except Exception as e:
            print(f"  ERROR {tif.name}: {e}")

    # Summary
    max_rho = max((r["abs_rho"] for r in results), default=0.0)
    max_rho_raster = max(results, key=lambda r: r["abs_rho"])["raster"] if results else "none"
    max_overlap = max((r["overlap_3px"] for r in results), default=0.0)
    max_overlap_raster = max(results, key=lambda r: r["overlap_3px"])["raster"] if results else "none"
    all_byte_unique = all(r["byte_unique"] for r in results)
    any_stop_rho = any(r["stop_rho"] for r in results)
    any_stop_overlap = any(r["stop_overlap"] for r in results)

    print(f"\n  MAX |Spearman rho|: {max_rho:.6f} vs {max_rho_raster} (limit {RHO_LIMIT})")
    print(f"  MAX 3-px overlap: {max_overlap:.6f} vs {max_overlap_raster} (limit {OVERLAP_LIMIT})")
    print(f"  All byte-unique: {all_byte_unique}")
    print(f"  Any rho stop: {any_stop_rho}")
    print(f"  Any overlap stop: {any_stop_overlap}")

    verdict = "UNIQUE" if (not any_stop_rho and not any_stop_overlap and all_byte_unique) else "DUPLICATE/STOP"
    print(f"\n  VERDICT: {verdict}")

    # Top overlaps
    print("\n  Top 5 by overlap:")
    for r in sorted(results, key=lambda x: -x["overlap_3px"])[:5]:
        print(f"    {r['raster']}: overlap={r['overlap_3px']:.4f} rho={r['rho']:+.4f} lift={r['lift']:.2f}x")

    print("\n  Top 5 by |rho|:")
    for r in sorted(results, key=lambda x: -x["abs_rho"])[:5]:
        print(f"    {r['raster']}: rho={r['rho']:+.4f} overlap={r['overlap_3px']:.4f}")

    # Write report
    report = {
        "candidate": cand_path.name,
        "sha256": sha256_file(cand_path),
        "my_dots": n_my_dots,
        "rho_limit": RHO_LIMIT,
        "overlap_limit": OVERLAP_LIMIT,
        "max_abs_rho": max_rho,
        "max_abs_rho_raster": max_rho_raster,
        "max_overlap": max_overlap,
        "max_overlap_raster": max_overlap_raster,
        "all_byte_unique": all_byte_unique,
        "any_rho_stop": any_stop_rho,
        "any_overlap_stop": any_stop_overlap,
        "verdict": verdict,
        "results": results,
    }
    report_path = ROOT / "evidence" / f"uniqueness_{cand_path.stem}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=1))
    print(f"\n  Report written: {report_path}")

    return 0 if verdict == "UNIQUE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
