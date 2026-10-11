"""Write a submission GeoTIFF that matches the organiser's published format.

Requirements, quoted from
https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/

* "the same projected coordinate reference system as the training data ... EPSG 32611"
* "the same resolution as the training data (100m)"
* "the same bounds as the training data, and data outside the bounds is null or nan"
* "a single layer with datatype of 32-bit float (``float32``) with values between 0 and 1"

The portal rejects a file with ``Predicted values must be in range [0, 1]`` if any *finite*
value falls outside that interval.  NaN outside the footprint is required, not merely
permitted, so the writer sets ``nodata`` to NaN as well as writing NaN values.

Two outside modes are supported and both are validated:

``nan``   - NaN outside the footprint (what the page asks for).
``zeros`` - 0 outside the footprint (accepted by the portal; a family of prior submissions
            shipped in this mode, and it is kept only for A/B comparison).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio

from .grid import (EXPECTED_CRS, EXPECTED_SHAPE, EXPECTED_TRANSFORM, RAW,
                   canonical_grid, footprint_mask)

DTYPE = "float32"


def to_submission_array(values: np.ndarray, mode: str = "nan",
                        footprint: np.ndarray | None = None) -> np.ndarray:
    """Clip to [0, 1], force float32, and null outside the footprint."""
    fp = footprint_mask() if footprint is None else footprint
    a = np.asarray(values, dtype=np.float64)
    a = np.where(np.isfinite(a), a, 0.0)
    a = np.clip(a, 0.0, 1.0)
    out = a.astype(np.float32)
    if mode == "nan":
        out = out.copy()
        out[~fp] = np.nan
    else:
        out[~fp] = 0.0
    return out


def write_submission(values: np.ndarray, path, mode: str = "nan",
                     compress: str = "deflate") -> dict:
    """Write ``values`` as a submission GeoTIFF.  Returns a receipt dictionary."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    grid = canonical_grid()
    fp = footprint_mask()
    arr = to_submission_array(values, mode=mode, footprint=fp)
    if arr.shape != EXPECTED_SHAPE:
        raise ValueError(f"shape {arr.shape} != {EXPECTED_SHAPE}")

    profile = dict(
        driver="GTiff",
        height=grid.height,
        width=grid.width,
        count=1,
        dtype=DTYPE,
        crs=EXPECTED_CRS,
        transform=rasterio.transform.Affine(*EXPECTED_TRANSFORM),
        nodata=float("nan") if mode == "nan" else 0.0,
        compress=compress,
        predictor=3 if compress in ("deflate", "lzw") else 1,
        tiled=False,
    )
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr, 1)
        dst.set_band_description(1, "fault probability")

    b = path.read_bytes()
    receipt = {
        "path": str(path),
        "filename": path.name,
        "size_bytes": len(b),
        "sha256": hashlib.sha256(b).hexdigest(),
        "mode": mode,
        "dtype": DTYPE,
        "crs": EXPECTED_CRS,
        "shape": list(EXPECTED_SHAPE),
        "transform": list(EXPECTED_TRANSFORM),
    }
    return receipt


def read_back(path) -> np.ndarray:
    """Re-open a written file and return the array (used by the validator)."""
    with rasterio.open(path) as src:
        return src.read(1)
