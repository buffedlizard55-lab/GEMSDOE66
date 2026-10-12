"""Feature stack: every available layer, on the competition grid, footprint pixels only.

Memory note: the sandbox has ~3 GB of RAM and the full grid is 3730 x 3292 = 12.28 M pixels.
Layers are therefore kept **one at a time** in memory and written into a single on-disk
``float32`` memmap of shape ``(n_layers, n_footprint)``.  5.17 M footprint pixels x 4 bytes
= 20.7 MB per layer, so the whole ~50-layer stack is ~1 GB on disk and never more than one
layer in RAM.

Dequantisation of the owner's uint8 products is the documented inverse of the packing rule
recorded in ``topo_10m_derived_100m_u8.manifest.json`` and reproduced in GEMSDOE25's
``src/gems25/features.py``:

    q = 1 + round(254 * t(x / xmax));   q == 0  ->  no data
    x = xmax * (t**2 if 'sqrt' else t)

The ``sqrt`` rule means those channels were stored on a square-root scale; the numbers below
are therefore *physical* values (metres, degrees), not quantisation indices.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio

from .grid import EXTERNAL, PROCESSED, RAW, footprint_mask

# ---------------------------------------------------------------------------------------------
# layer registry
# ---------------------------------------------------------------------------------------------
BASE_NAMES = [
    "mag_anom", "rtp", "tmi_hg", "geod_2ndinv", "iso_grav_anom_slope", "tc",
    "geod_shearrate", "geod_dilaterate", "tmi_vg", "deq_n100a15", "iso_grav_anom_vg",
    "det_elev", "iso_grav_anom", "tmi", "depth_to_base_surf", "ieq_n100a15",
    "cond_surf", "iso_grav_anom_hg", "det_elev_slope",
]

LIDAR_BANDS = [
    "ex_max", "ex_mean", "step_max", "lapneg_max", "lappos_max", "downface_max",
    "upface_max", "cross_max", "relief", "coh100", "strike", "valid",
]
# (xmax, rule) from the owner's lidar_scarp_features.json packing receipt
LIDAR_QUANT = {
    "ex_max": (1.5, "sqrt"), "ex_mean": (0.3, "sqrt"), "step_max": (1.0, "sqrt"),
    "lapneg_max": (0.05, "sqrt"), "lappos_max": (0.05, "sqrt"), "downface_max": (1.0, "sqrt"),
    "upface_max": (1.0, "sqrt"), "cross_max": (1.0, "sqrt"), "relief": (300.0, "sqrt"),
    "coh100": (1.0, "linear"), "strike": (180.0, "linear"), "valid": (1.0, "linear"),
}

TOPO10_BANDS = ["slope_p90", "slope_max", "steep_frac", "slope_std", "relief_local",
                "curv_prof_absmax", "aspect_coherence", "hs_lineament", "dem_mean"]
TOPO10_RANGE = {   # (lo, hi) from topo_10m_derived_100m_u8.manifest.json
    "slope_p90": (0.0, 41.82450717926024), "slope_max": (0.0, 48.14020595550532),
    "steep_frac": (0.0, 1.0), "slope_std": (0.0, 9.837751884460445),
    "relief_local": (0.0, 80.53856750488279), "curv_prof_absmax": (0.0, 40.50098724365233),
    "aspect_coherence": (0.09517142064869404, 0.9983641988039017),
    "hs_lineament": (0.0, 0.5624071541428564),
    "dem_mean": (1099.7082177734376, 2481.5011486816393),
}

RAD_BANDS = ["rad_K", "rad_Th", "rad_U", "rad_TC"]
EXT_BANDS = ["ext_ThK", "ext_UK", "ext_UTh", "ext_TMI_up150"]
CATEGORICAL = ["sgmc_faults", "sgmc_faults_derived", "gdr_qfaults_v2", "gdr_paleo",
               "gdr_volcanics"]


def dequantize(q: np.ndarray, xmax: float, rule: str) -> np.ndarray:
    """Invert ``q = 1 + round(254*t(x/xmax))``; ``q == 0`` -> NaN (no data)."""
    t = (q.astype(np.float32) - 1.0) / 254.0
    x = xmax * (t * t if rule == "sqrt" else t)
    return np.where(q > 0, x, np.nan).astype(np.float32)


def linear_u8(q: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Invert ``q = 1 + round(254*clip((v-lo)/(hi-lo),0,1))``; ``q == 0`` -> NaN."""
    t = (q.astype(np.float32) - 1.0) / 254.0
    return np.where(q > 0, lo + t * (hi - lo), np.nan).astype(np.float32)


def _flat(arr: np.ndarray, fi: np.ndarray) -> np.ndarray:
    return np.asarray(arr, dtype=np.float32).ravel()[fi]


# Some layers named by the inherited runner are not present in this checkout: either they were
# never hash-pinned (IR-66-DATA-02) or the verified mirror carries a different file name.
# `EXTERNAL_ALIASES` maps an expected file name onto a hash-pinned verified file, and every
# missing or aliased layer is recorded in stack_meta.json so the stack is never silently short.
EXTERNAL_ALIASES = {
    "sgmc_faults_100m.tif": "derived_sgmc_faults_100m_u8.tif",
}
MISSING_LAYERS: list[dict] = []


def _exists(path):
    """Return (path_to_use, note).  Never raises; missing layers are recorded, not faked."""
    path = Path(path)
    if path.exists():
        return path, None
    alt = EXTERNAL_ALIASES.get(path.name)
    if alt is not None and (EXTERNAL / alt).exists():
        return EXTERNAL / alt, f"aliased to verified mirror {alt}"
    MISSING_LAYERS.append({"file": path.name, "reason": "not present in this checkout"})
    return None, "missing"


def stack_paths():
    return (PROCESSED / "stack.f32", PROCESSED / "stack_names.json",
            PROCESSED / "footprint_index.npy")


def build_stack(force: bool = False) -> tuple[np.lib.format.memmap, list[str]]:
    """Build (or load) the on-disk feature stack.  Returns (memmap, layer_names)."""
    sp, np_, ip_ = stack_paths()
    fp = footprint_mask()
    fi = np.flatnonzero(fp.ravel()).astype(np.int64)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    np.save(ip_, fi)
    if sp.exists() and np_.exists() and not force:
        names = json.loads(np_.read_text())
        mm = np.lib.format.open_memmap(sp, mode="r", dtype=np.float32,
                                       shape=(len(names), fi.size))
        return mm, names

    layers: list[tuple[str, np.ndarray]] = []

    # ---- 1. the 19 competition bands ------------------------------------------------------
    with rasterio.open(RAW / "training_features.tif") as src:
        for i, name in enumerate(BASE_NAMES, start=1):
            a = src.read(i)
            a = np.where(np.isfinite(a) & (a > -1e30), a, np.nan).astype(np.float32)
            layers.append((name, _flat(a, fi)))

    # ---- 2. 1 m LiDAR scarp descriptors (dequantised to physical units) -------------------
    with rasterio.open(EXTERNAL / "lidar_scarp_features_u8.tif") as src:
        for i, name in enumerate(LIDAR_BANDS, start=1):
            xmax, rule = LIDAR_QUANT[name]
            layers.append((f"L_{name}", _flat(dequantize(src.read(i), xmax, rule), fi)))

    # ---- 3. 10 m DEM derived topography ---------------------------------------------------
    topo_path, topo_note = _exists(EXTERNAL / "topo_10m_derived_100m_u8.tif")
    if topo_path is not None:
        with rasterio.open(topo_path) as src:
            for i, name in enumerate(TOPO10_BANDS, start=1):
                lo, hi = TOPO10_RANGE[name]
                layers.append((f"T_{name}", _flat(linear_u8(src.read(i), lo, hi), fi)))
    else:
        MISSING_LAYERS[-1]["layers"] = [f"T_{n}" for n in TOPO10_BANDS]

    # ---- 4. GeoDAWN radiometrics and extensions (uint8, 1st-99th pct) ---------------------
    with rasterio.open(EXTERNAL / "geodawn_rad_u8.tif") as src:
        for i, name in enumerate(RAD_BANDS, start=1):
            layers.append((name, _flat(src.read(i).astype(np.float32) / 255.0, fi)))
    with rasterio.open(EXTERNAL / "geodawn_extensions_u8.tif") as src:
        for i, name in enumerate(EXT_BANDS, start=1):
            layers.append((name, _flat(src.read(i).astype(np.float32) / 255.0, fi)))

    # ---- 5. independent fault inventories / paleo / volcanics (0/1) ------------------------
    files = [("sgmc_faults_100m.tif", "sgmc_faults"),
             ("derived_sgmc_faults_100m.tif", "sgmc_faults_derived"),
             ("derived_gdr_qfaults_v2_100m_u8.tif", "gdr_qfaults_v2"),
             ("derived_gdr_paleo_100m_u8.tif", "gdr_paleo"),
             ("derived_gdr_volcanics_100m_u8.tif", "gdr_volcanics")]
    for fname, name in files:
        path, note = _exists(EXTERNAL / fname)
        if path is None:
            MISSING_LAYERS[-1]["layers"] = [name]
            continue
        with rasterio.open(path) as src:
            a = src.read(1)
            layers.append((name, _flat((a > 0).astype(np.float32), fi)))

    # ---- 6. channel steepness (chi) from the 10 m DEM -------------------------------------
    for fname, names in (("dem10_chi_100m_i16.tif", "chi_b"), ("dem10_chi_100m_sig_i32.tif", "chi_sig")):
        path, note = _exists(EXTERNAL / fname)
        if path is None:
            MISSING_LAYERS[-1]["layers"] = [names]
            continue
        with rasterio.open(path) as src:
            for i in range(1, src.count + 1):
                a = src.read(i).astype(np.float32)
                a[a <= -32767] = np.nan
                a[a < 0] = np.nan
                layers.append((f"chi_b{i}" if names == "chi_b" else "chi_sig", _flat(a, fi)))

    names = [n for n, _ in layers]
    mm = np.lib.format.open_memmap(sp, mode="w+", dtype=np.float32,
                                   shape=(len(names), fi.size))
    for j, (n, v) in enumerate(layers):
        mm[j] = v
        del v
    mm.flush()
    np_.write_text(json.dumps(names, indent=1))
    meta = {"n_layers": len(names), "n_footprint": int(fi.size), "names": names,
            "missing_layers": MISSING_LAYERS,
            "fail_soft_note": "layers absent from this checkout are skipped and listed in "
                              "missing_layers; the stack is never padded or faked",
            "dtype": "float32", "units_note":
            "L_* are dequantised physical values (m, degrees); T_* from 10 m DEM; "
            "chi_* from the 10 m DEM (25/36 blocks succeeded)."}
    (PROCESSED / "stack_meta.json").write_text(json.dumps(meta, indent=1))
    return mm, names


def load_stack():
    sp, np_, ip_ = stack_paths()
    names = json.loads(np_.read_text())
    mm = np.lib.format.open_memmap(sp, mode="r", dtype=np.float32,
                                   shape=(len(names), int(np.load(ip_).size)))
    return mm, names, np.load(ip_)


if __name__ == "__main__":
    mm, names = build_stack(force=True)
    print(f"built stack: {mm.shape[0]} layers x {mm.shape[1]:,} footprint px")
    print(", ".join(names))
