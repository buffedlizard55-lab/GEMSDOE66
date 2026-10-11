"""Validate a candidate submission GeoTIFF against the official format rules.

Official rules (problem page, "Submission format"): single layer, float32, EPSG:32611,
100 m, same bounds as the training data, values in [0, 1], data outside bounds null or NaN.
The portal error "Predicted values must be in range [0, 1]" is what a file with out-of-range
values (or a large negative nodata sentinel) produces.

Checks that depend on the training rasters (exact transform, footprint) run only when a
reference file is supplied. Without it those checks are reported as SKIPPED, not PASSED.

CLI:  python -m gems.validate_submission FILE.tif [--reference data/labels.tif]
            [--features data/training_features.tif]
exit code 0 = every check PASSED (SKIPPED counts as not passed), 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from .constants import EPSG, FEATURE_NODATA_SENTINEL, PIXEL_M, SHAPE_HW


def _check(name, ok, detail, status=None):
    return {"check": name, "status": status or ("PASS" if ok else "FAIL"), "detail": detail}


def footprint_from_features(features_path: str | Path, shape_hw=None) -> np.ndarray:
    """Footprint = cells whose first feature band is finite and above the nodata sentinel."""
    import rasterio

    with rasterio.open(features_path) as src:
        band = src.read(1).astype(np.float64)
    fp = np.isfinite(band) & (band > FEATURE_NODATA_SENTINEL)
    if shape_hw is not None and fp.shape != tuple(shape_hw):
        raise ValueError(f"features shape {fp.shape} != expected {shape_hw}")
    return fp


def validate(path: str | Path, reference_path: str | Path | None = None,
             features_path: str | Path | None = None) -> dict:
    import rasterio

    path = Path(path)
    checks: list[dict] = []
    if not path.exists():
        return {"file": str(path), "passed": False, "checks": [_check("file exists", False, "missing")]}

    with rasterio.open(path) as src:
        checks.append(_check("single band", src.count == 1, f"count={src.count}"))
        checks.append(_check("dtype float32", src.dtypes[0] == "float32", f"dtype={src.dtypes[0]}"))
        checks.append(_check("CRS EPSG:32611", src.crs is not None and src.crs.to_string() == EPSG,
                             f"crs={src.crs.to_string() if src.crs else None}"))
        expected_shape = SHAPE_HW
        ref_transform = None
        if reference_path is not None:
            with rasterio.open(reference_path) as ref:
                expected_shape = (ref.height, ref.width)
                ref_transform = ref.transform
                ref_crs = ref.crs
        checks.append(_check("shape matches", (src.height, src.width) == tuple(expected_shape),
                             f"file={(src.height, src.width)} expected={tuple(expected_shape)}"))
        res_ok = abs(abs(src.res[0]) - PIXEL_M) < 1e-9 and abs(abs(src.res[1]) - PIXEL_M) < 1e-9
        checks.append(_check("resolution 100 m", res_ok, f"res={src.res}"))
        if ref_transform is not None:
            same_tf = all(abs(a - b) < 1e-6 for a, b in zip(src.transform[:6], ref_transform[:6]))
            checks.append(_check("transform matches reference", same_tf,
                                 f"file={tuple(src.transform)[:6]} ref={tuple(ref_transform)[:6]}"))
            checks.append(_check("CRS matches reference",
                                 src.crs is not None and ref_crs is not None and src.crs == ref_crs,
                                 f"file={src.crs} ref={ref_crs}"))
        else:
            checks.append(_check("transform matches reference", True,
                                 "SKIPPED: no reference raster supplied", status="SKIPPED"))
        nodata = src.nodata
        nodata_ok = nodata is None or (isinstance(nodata, float) and np.isnan(nodata))
        checks.append(_check("nodata tag is none or NaN", nodata_ok,
                             f"nodata={nodata} (a finite nodata tag is rejected conservatively)"))
        arr = src.read(1).astype(np.float64)

    finite = np.isfinite(arr)
    n_inf = int(np.isinf(arr).sum())
    checks.append(_check("no infinities", n_inf == 0, f"inf_count={n_inf}"))
    vals = arr[finite]
    if vals.size:
        vmin, vmax = float(vals.min()), float(vals.max())
    else:
        vmin = vmax = float("nan")
    checks.append(_check("values within [0, 1]", vals.size > 0 and vmin >= 0.0 and vmax <= 1.0,
                         f"min={vmin} max={vmax} finite_cells={int(finite.sum())}"))

    if features_path is not None:
        fp = footprint_from_features(features_path, expected_shape)
        nan_inside = int((~finite & fp).sum())
        checks.append(_check("no NaN inside footprint", nan_inside == 0,
                             f"nan_inside={nan_inside} footprint_cells={int(fp.sum())}"))
        outside_finite = int((finite & ~fp).sum())
        checks.append(_check("NaN-only outside footprint (finite outside footprint count)",
                             outside_finite == 0, f"finite_outside={outside_finite}",
                             status=None if outside_finite == 0 else "WARN"))
    else:
        checks.append(_check("no NaN inside footprint", True,
                             "SKIPPED: no features raster supplied", status="SKIPPED"))

    nonzero = int(np.nansum(arr > 0))
    checks.append(_check("info: emitted cells (value > 0)", True, f"emitted={nonzero}", status="INFO"))
    # Strict: a SKIPPED check is NOT a pass. Without the reference grid and the features raster the
    # file has not been validated against the official data, so it cannot clear the gate.
    failed = [c for c in checks if c["status"] == "FAIL"]
    skipped = [c for c in checks if c["status"] == "SKIPPED"]
    return {"file": str(path), "passed": not failed and not skipped, "has_failures": bool(failed),
            "checks": checks, "skipped_checks_mean_unverified": bool(skipped)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("file")
    ap.add_argument("--reference", help="labels.tif (or any file with the official grid)")
    ap.add_argument("--features", help="training features raster, for the footprint check")
    args = ap.parse_args(argv)
    report = validate(args.file, args.reference, args.features)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
