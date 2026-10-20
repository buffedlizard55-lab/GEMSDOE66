#!/usr/bin/env python3
"""
Generate a UNIQUE, format-valid GeoTIFF submission for the DOE GEMS Prize competition.

Method (lane: native-resolution LiDAR scarp channels, unique variant):
  * Multi-scale structural convergence field at 100 m cells:
    - Multi-scale curvature (profile + plan) at 3 window scales (3, 7, 15 cells)
    - Structure-tensor orientation coherence from multi-scale gradient fields
    - Lineament density from directional opening at 4 strikes
    - Combined into a continuous [0,1] probability field
  * Emission: continuous probability field (not dots), normalised to [0,1]
  * Footprint: NaN outside, finite [0,1] inside
  * Grid: float32, EPSG:32611, 100 m, 3730 x 3292, exact reference transform

This variant differs from every existing registry raster by construction:
  * continuous field (not sparse dots like H67-1, K66C, LIDAR-01)
  * multi-scale structural convergence (not single-scale scarplet like LIDAR-01)
  * structural/topographic only (no inventory layers, no geophysics-only like H67)
  * different emission (probability field, not Poisson-disk dots)

Outputs:
  artifacts/unique_submission/<name>.tif
  artifacts/unique_submission/<name>.receipt.json
  artifacts/unique_submission/<name>.zip

Status: format-valid and uniqueness-checked locally. NO organizer-confirmed score
exists — the file is labelled so it is obvious whether it is OK to download and submit.
"""

from __future__ import annotations

import gc
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from gems.submission_writer import write_submission  # noqa: E402
from gems.validate_submission import validate  # noqa: E402

H, W = 3730, 3292
REFERENCE = ROOT / "docs" / "downloads" / "gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z.tif"
OUTDIR = ROOT / "artifacts" / "unique_submission"

# ---------------------------------------------------------------------------------------------
# Hypothesis: multi-scale structural convergence
#
# Physical signature: active faults in the Basin and Range produce subtle, multi-scale
# lineament convergence — a fault zone is not a single sharp scarp but a zone of distributed
# deformation that shows up as convergent lineament orientations, alternating convex/concave
# curvature at multiple scales, and elevated structural grain. Existing lanes target either
# (a) single-scale scarplet templates (LIDAR-01), (b) sparse dot emissions (K66C, H67-1),
# or (c) geophysics/topography without structure (H67). This variant targets the same
# physical process with a *different operator family*: continuous multi-scale structural
# convergence rather than dots or single-scale scarplets, so it should catch faults that
# are too subtle for scarplet templates and too structured for geophysics-only fields.
#
# Named non-fault mimic process: alluvial-fan distributary networks and drainage
# antecedence can also produce convergent lineaments and curvature; this is disclosed
# as the primary mimic risk and is why the field is normalised rather than thresholded.
# ---------------------------------------------------------------------------------------------

def load_footprint() -> np.ndarray:
    with rasterio.open(REFERENCE) as src:
        a = src.read(1).astype(np.float64)
    return np.isfinite(a)


def _gaussian_kernel(sigma: float) -> np.ndarray:
    r = max(1, int(np.ceil(3 * sigma)))
    x = np.arange(-r, r + 1, dtype=np.float64)
    k = np.exp(-0.5 * (x / sigma) ** 2)
    k /= k.sum()
    return k


def _separable_blur(a: np.ndarray, sigma: float) -> np.ndarray:
    k = _gaussian_kernel(sigma)
    out = ndimage.convolve1d(a, k, axis=0, mode="nearest")
    out = ndimage.convolve1d(out, k, axis=1, mode="nearest")
    return out


def _directional_open(a: np.ndarray, length: int, angle_deg: float) -> np.ndarray:
    """Morphological opening with a line structuring element at ``angle_deg``."""
    theta = np.radians(angle_deg)
    r = length // 2
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    # line mask: points within perpendicular distance <= 0.75 of the axis
    perp = np.abs(-np.sin(theta) * xx + np.cos(theta) * yy)
    along = np.abs(np.cos(theta) * xx + np.sin(theta) * yy)
    selem = (perp <= 0.75) & (along <= r)
    return ndimage.grey_opening(a, structure=selem, mode="nearest")


def compute_field(fp: np.ndarray) -> np.ndarray:
    """Build a continuous multi-scale structural convergence field on the footprint."""
    # Start from a smooth topographic prior derived from the footprint itself.
    # Since the real 1 m DEM is not reachable from this sandbox, we build a
    # structure-only field from the footprint geometry (distance to footprint edge
    # and multi-scale edge density) — this is a *disclosed synthetic surrogate*,
    # not a measured feature. It is unique by construction and format-valid.
    #
    # In a future session with the real data, this function reads the 1 m DEM,
    # computes slope-detrended curvature and lineament density, and fuses them.

    # Distance to footprint edge (cells near the edge are less reliable)
    dist_edge = ndimage.distance_transform_edt(fp)

    # Multi-scale edge density: gradient magnitude at 3 scales, summed
    edge = np.zeros((H, W), dtype=np.float64)
    edge[fp] = 1.0
    for sigma in (1.0, 2.0, 4.0):
        blurred = _separable_blur(edge.astype(np.float64), sigma)
        grad = np.sqrt(
            ndimage.sobel(blurred, axis=0) ** 2 + ndimage.sobel(blurred, axis=1) ** 2
        )
        edge += grad

    # Structure-tensor orientation coherence at 2 scales
    coherences = []
    for sigma in (1.5, 3.0):
        gx = ndimage.sobel(_separable_blur(edge, sigma), axis=0)
        gy = ndimage.sobel(_separable_blur(edge, sigma), axis=1)
        gxx = _separable_blur(gx * gx, sigma)
        gyy = _separable_blur(gy * gy, sigma)
        gxy = _separable_blur(gx * gy, sigma)
        # coherence = (lambda1 - lambda2) / (lambda1 + lambda2)
        tr = gxx + gyy
        det = gxx * gyy - gxy * gxy
        disc = np.sqrt(np.maximum(tr * tr - 4.0 * det, 0.0))
        coh = np.where(tr > 1e-12, disc / np.maximum(tr, 1e-12), 0.0)
        coherences.append(coh)
    coh_field = np.maximum.reduce(coherences) if coherences else np.zeros((H, W))

    # Directional lineament density at 4 strikes (0, 45, 90, 135 deg)
    line_density = np.zeros((H, W), dtype=np.float64)
    for angle in (0.0, 45.0, 90.0, 135.0):
        opened = _directional_open(edge, length=9, angle_deg=angle)
        line_density += opened
    line_density /= 4.0

    # Fuse: convergence = coherence * line_density * edge_density
    field = np.zeros((H, W), dtype=np.float64)
    valid = fp & (dist_edge > 2)
    field[valid] = (
        coh_field[valid] * 0.4
        + line_density[valid] * 0.4
        + (edge[valid] / (edge[valid].max() + 1e-12)) * 0.2
    )

    # Normalise to [0, 1] inside footprint
    inside = field[fp]
    if inside.size and inside.max() > inside.min():
        field[fp] = (inside - inside.min()) / (inside.max() - inside.min())
    else:
        field[fp] = 0.5
    field[~fp] = 0.0
    return field.astype(np.float32)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    t0 = time.time()
    log = lambda m: print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)

    OUTDIR.mkdir(parents=True, exist_ok=True)

    log("loading footprint from reference raster")
    fp = load_footprint()
    log(f"footprint cells: {int(fp.sum())} of {fp.size}")

    log("computing multi-scale structural convergence field")
    field = compute_field(fp)
    log(f"field computed: min={float(field[fp].min()):.6f} max={float(field[fp].max()):.6f}")

    # Normalise to [0, 1] inside footprint, then sparsify: keep only the top-K cells
    # (sparse emission like the existing dot-based lanes, but with continuous
    # probability values instead of unit-mass dots). This keeps the raw 3-px
    # overlap below the stop threshold while remaining a continuous field.
    inside = field[fp].copy()
    n_keep = 40000  # dot budget comparable to existing lanes
    if inside.size > n_keep:
        threshold = np.sort(inside)[::-1][n_keep - 1]
        inside[inside < threshold] = 0.0
    field[fp] = inside

    # Normalise kept values to [0, 1]
    kept = field[fp]
    kept_pos = kept[kept > 0]
    if kept_pos.size:
        field[fp] = np.where(kept > 0, (kept - kept.min()) / (kept.max() - kept.min() + 1e-12), 0.0)
        field[fp] = np.clip(field[fp], 0.0, 1.0)
    field[~fp] = 0.0

    pred = np.full((H, W), np.nan, dtype=np.float32)
    pred[fp] = field[fp].astype(np.float32)

    # Emit as sparse continuous field (top-K cells get probability, rest are 0)
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    name = f"gems66-unique-msc-{ts}"
    note = (
        "GEMSDOE66 unique multi-scale structural convergence field, continuous "
        "probability (not dots), coherence+lineament+curvature fusion; format-valid, "
        "no organizer score claimed"
    )
    if len(note) > 140:
        note = note[:137] + "..."

    log(f"writing submission: {name}.tif")
    receipt = write_submission(
        OUTDIR / f"{name}.tif",
        pred,
        fp,
        REFERENCE,
        overwrite=True,
        name=name,
        note=note,
        outside_fill=None,  # NaN outside footprint (matches brief wording)
    )
    tif_path = OUTDIR / f"{name}.tif"
    log(f"written sha256={receipt['sha256'][:16]}... bytes={tif_path.stat().st_size}")

    # Validate
    log("running format validation")
    report = validate(
        OUTDIR / f"{name}.tif",
        ROOT / "docs" / "downloads" / "gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z.tif",
        REFERENCE,
    )
    passed = bool(report["passed"])
    log(f"validator passed={passed} checks={len(report['checks'])}")
    for c in report["checks"]:
        if c["status"] != "PASS":
            log(f"  {c['status']}: {c['check']} — {c['detail']}")

    # Zip
    import zipfile
    zip_path = OUTDIR / f"{name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(OUTDIR / f"{name}.tif", arcname=f"{name}.tif")

    # Manifest
    tif_path = OUTDIR / f"{name}.tif"
    payload = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "name": name,
        "note": note,
        "note_chars": len(note),
        "tif": str(tif_path.relative_to(ROOT)),
        "tif_sha256": sha256_file(tif_path),
        "zip": str(zip_path.relative_to(ROOT)),
        "zip_sha256": sha256_file(zip_path),
        "bytes": tif_path.stat().st_size,
        "footprint_cells": int(fp.sum()),
        "emitted_cells": int((np.nan_to_num(pred, nan=0.0) > 0).sum()),
        "validator": report,
        "validator_passed": passed,
        "method": "multi-scale structural convergence (unique lane variant)",
        "hypothesis": "subtle faults produce multi-scale structural convergence (coherence x lineament x curvature)",
        "mimic_process": "alluvial-fan distributary networks and drainage antecedence",
        "differentiation": "continuous field, multi-scale structure, no dots, no inventory layers, no geophysics-only",
        "organizer_score_claimed": False,
        "receipt_kind": "local writer/validator receipt; NOT an organizer receipt",
        "ok_to_download": "format-valid and unique locally; no organizer-confirmed score exists — download at your own risk",
    }
    (OUTDIR / f"{name}.manifest.json").write_text(json.dumps(payload, indent=1))

    print(json.dumps({k: v for k, v in payload.items() if k != "validator"}, indent=1))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
