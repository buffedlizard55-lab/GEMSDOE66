#!/usr/bin/env python3
"""Lane-drift check between a candidate raster and registry rasters.

Rules from the brief: correlation with a registry raster > 0.90, OR more than 70% of the
candidate's dots lying within 3 px of one registry raster's dots, means lane drift -> log as
a duplicate and stop.

Dots = cells with value > 0 (sparse emission). Correlation = Pearson r over cells that are
finite in both rasters. Distances use pixel indices (3 px = 300 m at 100 m).

Usage: python scripts/lane_check.py candidate.tif registry1.tif [registry2.tif ...] [--json out.json]
Exit code: 0 = no drift, 2 = drift flagged (duplicate, stop), 3 = inconclusive, 1 = error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems.submission_writer import sha256_file  # noqa: E402

CORR_LIMIT = 0.90
DOT_OVERLAP_LIMIT = 0.70
DOT_RADIUS_PX = 3.0


def _read(path):
    import rasterio
    with rasterio.open(path) as src:
        return src.read(1).astype(np.float64)


def pearson_on_common(a: np.ndarray, b: np.ndarray) -> float:
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 2:
        return float("nan")
    x, y = a[m], b[m]
    if x.std() == 0 or y.std() == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def dot_fraction_near(dots_a: np.ndarray, dots_b: np.ndarray, radius: float = DOT_RADIUS_PX) -> float:
    """Fraction of dots_a with a dot_b within radius pixels."""
    from scipy.spatial import cKDTree
    if len(dots_a) == 0:
        return float("nan")
    if len(dots_b) == 0:
        return 0.0
    d, _ = cKDTree(dots_b).query(dots_a, k=1)
    return float(np.mean(d <= radius))


def lane_check(candidate: str | Path, registry: list[str | Path]) -> dict:
    a = _read(candidate)
    dots_a = np.argwhere(np.nan_to_num(a, nan=0.0) > 0)
    rows = []
    for r in registry:
        b = _read(r)
        dots_b = np.argwhere(np.nan_to_num(b, nan=0.0) > 0)
        corr = pearson_on_common(a, b)
        frac = dot_fraction_near(dots_a, dots_b)
        drift = (np.isfinite(corr) and corr > CORR_LIMIT) or (np.isfinite(frac) and frac > DOT_OVERLAP_LIMIT)
        rows.append({"registry": Path(r).name, "sha256": sha256_file(r), "pearson_r": corr,
                     "dots_registry": int(len(dots_b)), "candidate_dots_within_3px": frac,
                     "drift": bool(drift)})
    return {"candidate": Path(candidate).name, "candidate_sha256": sha256_file(candidate),
            "candidate_dots": int(len(dots_a)), "limits": {"pearson_r": CORR_LIMIT,
            "dots_within_3px": DOT_OVERLAP_LIMIT}, "comparisons": rows, "verdict": _verdict(rows)}


def _verdict(rows) -> str:
    if any(r["drift"] for r in rows):
        return "LANE DRIFT - log duplicate and stop"
    if any(not np.isfinite(r["pearson_r"]) or not np.isfinite(r["candidate_dots_within_3px"]) for r in rows):
        return "INCONCLUSIVE - empty or constant raster; not a pass"
    return "no drift vs supplied registry rasters"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("candidate")
    ap.add_argument("registry", nargs="+")
    ap.add_argument("--json", help="write the report to this path")
    args = ap.parse_args(argv)
    try:
        rep = lane_check(args.candidate, args.registry)
    except Exception as exc:  # noqa: BLE001 - report any read failure as exit 1
        print(f"error: {exc}", file=sys.stderr)
        return 1
    text = json.dumps(rep, indent=2)
    print(text)
    if args.json:
        Path(args.json).write_text(text)
    if rep["verdict"].startswith("LANE DRIFT"):
        return 2
    if rep["verdict"].startswith("INCONCLUSIVE"):
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
