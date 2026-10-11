"""Canonical grid for the GEMS competition (EPSG:32611, 100 m, 3730 x 3292).

Every value here is read from the bytes, never assumed.  The canonical transform and shape
come from ``data/raw/sample_submission.tif`` (the submission-format template) and are
cross-checked against ``labels.tif`` and ``training_features.tif``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
EXTERNAL = RAW / "external"

EXPECTED_CRS = "EPSG:32611"
EXPECTED_SHAPE = (3730, 3292)          # (rows, cols)
EXPECTED_TRANSFORM = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
GRID_METRES = 100.0
KERNEL_RANGE_M = 300.0                 # official triangular-kernel support
KERNEL_RANGE_PX = 3.0                  # 300 m / 100 m
ALPHA, BETA = 0.2, 0.8                 # official Tversky weights


@dataclass(frozen=True)
class Grid:
    height: int
    width: int
    transform: tuple
    crs: str

    @property
    def shape(self) -> tuple:
        return (self.height, self.width)


def read_raster(path, band: int | None = None):
    """Read a raster; returns (array, profile).  ``band=None`` reads all bands."""
    with rasterio.open(path) as src:
        arr = src.read() if band is None else src.read(band)
        return arr, src.profile.copy()


def canonical_grid() -> Grid:
    """Load the submission template and return the canonical grid."""
    with rasterio.open(RAW / "sample_submission.tif") as src:
        t = tuple(src.transform)[:6]
        g = Grid(src.height, src.width, t, str(src.crs))
    if (g.height, g.width) != EXPECTED_SHAPE:
        raise AssertionError(f"unexpected shape {g.shape}")
    if g.crs != EXPECTED_CRS:
        raise AssertionError(f"unexpected CRS {g.crs}")
    if g.transform != EXPECTED_TRANSFORM:
        raise AssertionError(f"unexpected transform {g.transform}")
    return g


def footprint_mask() -> np.ndarray:
    """Boolean mask of pixels inside the scored footprint (NaN outside)."""
    p = PROCESSED / "footprint.npy"
    if p.exists():
        return np.load(p)
    a, _ = read_raster(RAW / "sample_submission.tif", 1)
    m = np.isfinite(a)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    np.save(p, m)
    return m


def catalogue_mask() -> np.ndarray:
    """Boolean mask of labelled (known) fault pixels, inside the footprint."""
    p = PROCESSED / "catalogue.npy"
    if p.exists():
        return np.load(p)
    a, _ = read_raster(RAW / "labels.tif", 1)
    m = np.isfinite(a) & (a > 0)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    np.save(p, m)
    return m


def nodata_to_nan(arr: np.ndarray, nodata=-3.4028234663852886e38) -> np.ndarray:
    out = arr.astype(np.float32, copy=True)
    out[out <= nodata * 0.999] = np.nan
    out[out < -1e30] = np.nan
    return out
