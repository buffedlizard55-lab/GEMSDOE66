"""Independent validator for a submission GeoTIFF.

Run this on the bytes that will be uploaded.  Every check is re-derived from the organiser's
published format rules by re-opening the file from disk - nothing is trusted from the
in-memory array that produced it.

Checks
------
1.  single band
2.  dtype is float32
3.  shape is 3730 x 3292
4.  CRS is EPSG:32611
5.  geotransform equals the template's
6.  no NaN / inf / sentinel inside the footprint
7.  every finite value inside the footprint is within [0, 1]  <- the portal's rejection rule
8.  outside the footprint is NaN (``nan`` mode) or 0 (``zeros`` mode)
9.  (optional) no positive pixel within ``max_dist_px`` of a known catalogue fault
10. (optional) the emitted positive-pixel count equals a declared budget
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio

from .grid import (EXPECTED_CRS, EXPECTED_SHAPE, EXPECTED_TRANSFORM, RAW,
                   catalogue_mask, footprint_mask)

SENTINELS = (-3.4028234663852886e38, -9999.0, -32768.0, -1.0e30)


def validate(path, mode: str = "nan", require_off_catalogue: float | None = None,
             expected_dots: int | None = None, tol_dots: int = 0) -> dict:
    path = Path(path)
    fp = footprint_mask()
    cat = catalogue_mask()
    checks: dict[str, bool] = {}

    with rasterio.open(path) as src:
        if src.count != 1:
            return {"ok": False, "checks": {"single_band": False},
                    "detail": f"band count {src.count}"}
        a = src.read(1)
        checks["single_band"] = True
        checks["dtype_float32"] = (src.dtypes[0] == "float32")
        checks["dimensions_3730x3292"] = (src.height, src.width) == EXPECTED_SHAPE
        checks["crs_epsg_32611"] = str(src.crs).upper() == EXPECTED_CRS.upper()
        t = tuple(src.transform)[:6]
        checks["transform_matches_template"] = all(
            abs(float(x) - float(y)) < 1e-6 for x, y in zip(t, EXPECTED_TRANSFORM))

    if a.shape != EXPECTED_SHAPE:
        return {"ok": False, "checks": checks, "detail": f"array shape {a.shape}"}

    inside = a[fp]
    checks["in_footprint_zero_nan"] = bool(not np.isnan(inside).any())
    checks["in_footprint_zero_inf"] = bool(not np.isinf(inside).any())
    checks["in_footprint_no_sentinel"] = bool(
        not any(np.any(np.isclose(inside, s, rtol=0, atol=1e-6)) for s in SENTINELS))
    finite = inside[np.isfinite(inside)]
    checks["in_footprint_range_0_1"] = bool(finite.size > 0 and finite.min() >= 0.0
                                            and finite.max() <= 1.0)
    checks["in_footprint_has_positive"] = bool((finite > 0).any())

    outside = a[~fp]
    if mode == "nan":
        checks["outside_footprint_nan"] = bool(np.isnan(outside).all())
    else:
        checks["outside_footprint_zero"] = bool(
            np.all(np.isnan(outside) | (outside == 0.0)))

    stats = {
        "in_footprint_pixels": int(fp.sum()),
        "in_footprint_finite": int(np.isfinite(inside).sum()),
        "in_footprint_min": float(finite.min()) if finite.size else None,
        "in_footprint_max": float(finite.max()) if finite.size else None,
        "in_footprint_mean": float(finite.mean()) if finite.size else None,
        "positive_pixels": int((np.nan_to_num(a, nan=0.0)[fp] > 0).sum()),
        "outside_footprint_pixels": int((~fp).sum()),
    }

    if require_off_catalogue is not None:
        from scipy import ndimage
        d = ndimage.distance_transform_edt(~cat)
        pos = np.nan_to_num(a, nan=0.0) > 0
        n_on = int((d[pos] <= require_off_catalogue).sum())
        checks[f"zero_positive_within_{require_off_catalogue}px_of_catalogue"] = (n_on == 0)
        stats["positive_within_catalogue_buffer"] = n_on

    if expected_dots is not None:
        got = int((np.nan_to_num(a, nan=0.0)[fp] > 0).sum())
        checks["emitted_count_matches_budget"] = bool(abs(got - expected_dots) <= tol_dots)
        stats["emitted_count"] = got
        stats["expected_count"] = int(expected_dots)

    ok = all(bool(v) for v in checks.values())
    return {"ok": ok, "checks": checks, "stats": stats, "filename": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path)}


def _sha256(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def write_receipt(result: dict, out_path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=1))


if __name__ == "__main__":
    import sys
    mode = sys.argv[2] if len(sys.argv) > 2 else "nan"
    r = validate(sys.argv[1], mode=mode)
    print(json.dumps(r, indent=1))
    sys.exit(0 if r["ok"] else 1)
