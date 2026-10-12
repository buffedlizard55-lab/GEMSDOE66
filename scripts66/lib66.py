"""Shared, auditable helpers for the GEMSDOE66 session-66 experiments.

Data sources are the sha256-pinned owner mirrors (registry/data_manifest.json), restored with
scripts/fetch_mirrors.py. Nothing here contacts drivendata.org. Every array is on the exact
official grid asserted from sample_submission.tif (3730 x 3292, EPSG:32611, 100 m).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
REG = ROOT / "registry" / "rasters"
GRID = (3730, 3292)
TRANSFORM = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)


def _read(path):
    with rasterio.open(path) as src:
        a = src.read(1).astype(np.float64)
        assert (src.height, src.width) == GRID, f"{path} shape {(src.height, src.width)}"
        assert tuple(round(v, 6) for v in src.transform[:6]) == tuple(round(v, 6) for v in TRANSFORM)
    return a


def footprint() -> np.ndarray:
    """Official coverage mask: finite cells of the organiser sample_submission raster."""
    with rasterio.open(RAW / "sample_submission.tif") as src:
        return np.isfinite(src.read(1).astype(np.float32))


def catalogue() -> np.ndarray:
    """Visible USGS-derived catalogue truth (labels.tif > 0, 60,988 pixels)."""
    return _read(RAW / "labels.tif") > 0


def layer(name: str) -> np.ndarray:
    """Named uint8 mirror layer; 0 is the mirror's nodata code (verified against the tag)."""
    src_map = {
        "K": ("external/geodawn_rad_u8.tif", 1), "Th": ("external/geodawn_rad_u8.tif", 2),
        "U": ("external/geodawn_rad_u8.tif", 3), "TC": ("external/geodawn_rad_u8.tif", 4),
        "ThK": ("external/geodawn_extensions_u8.tif", 1), "UK": ("external/geodawn_extensions_u8.tif", 2),
        "UTh": ("external/geodawn_extensions_u8.tif", 3), "TMI": ("external/geodawn_extensions_u8.tif", 4),
        "sgmc": ("external/derived_sgmc_faults_100m_u8.tif", 1),
    }
    lidar = ["ex_max", "ex_mean", "step_max", "lapneg_max", "lappos_max", "downface_max",
             "upface_max", "cross_max", "relief", "coh100", "strike", "valid"]
    if name in src_map:
        p, b = src_map[name]
        return _read(RAW / p) if b == 1 else _read_band(RAW / p, b)
    if name in lidar:
        return _read_band(RAW / "external/lidar_scarp_features_u8.tif", lidar.index(name) + 1)
    raise KeyError(name)


def _read_band(path, b):
    with rasterio.open(path) as src:
        a = src.read(b).astype(np.float64)
        assert (src.height, src.width) == GRID
    return a


def read_registry_dots(path) -> np.ndarray:
    """Boolean dot mask of a registry raster within the footprint (NaN/zeros outside)."""
    fp = footprint()
    with rasterio.open(path) as src:
        a = np.nan_to_num(src.read(1).astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    assert a.shape == GRID
    return (a > 0) & fp


def credit_field(dots: np.ndarray, range_px: float = 3.0) -> np.ndarray:
    """c(x) = max over dots of the 300 m triangular kernel; exact for a monotone kernel."""
    d = ndimage.distance_transform_edt(~dots)
    return np.clip(1.0 - d / range_px, 0.0, None)


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def owner_scores() -> dict:
    """Owner-reported live scores, imported from scripts/calibrate_live.py (single source)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("cal", ROOT / "scripts" / "calibrate_live.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return dict(mod.OWNER_SCORES)


def distinct_scored(registry: Path = REG) -> dict:
    """name -> owner score, collapsing byte-identical duplicates (as calibrate_live.py does)."""
    scores = owner_scores()
    seen: dict[str, str] = {}
    for p in sorted(registry.glob("*.tif")):
        if p.name not in scores:
            continue
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        seen.setdefault(h, p.name)
    return {n: scores[n] for n in sorted(seen.values())}


def dti_terms(pred: np.ndarray, gt: np.ndarray, range_px: float = 3.0):
    """Exact published-metric terms for a probability raster vs a binary truth mask."""
    from gems.metric import tversky_terms
    return tversky_terms(pred, gt, pixel_m=100.0, range_m=range_px * 100.0)
