"""H67 feature stack: every layer this session is allowed to touch, with explicit provenance.

Layers
------
* 19 competition bands from ``training_features.tif`` (organiser; via hash-pinned mirror).
* 12 LiDAR scarp descriptors derived by the owner's CI from USGS 3DEP 1 m DEM tiles, supplied
  as uint8 aggregates on the 100 m grid (``lidar_scarp_features_u8.tif``).  **Scale caveat:** the
  brief asks for 2-20 m native-resolution filters; the finest reachable product is this 100 m
  aggregate, so any filter scale quoted in pixels is 100 m here and is reported as such.
* 8 GeoDAWN radiometric bands (K, Th, U, TC, Th/K, U/K, U/Th, TMI up-continued 150 m), uint8
  quantised 1st-99th percentile.
* USGS SGMC geologic-map faults rasterised to 100 m.
* GDR/INGENIOUS Quaternary fault trace centroids and GDR well/spring temperatures.

Every array returned is ``(H, W)`` float32 with NaN where undefined.  Nothing in this module
reads ``labels.tif``; catalogue-derived layers are built by the caller from an explicitly
*handed-in* visible-fault mask so the holdout can withdraw segments.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent.parent
RAW = ROOT / "data" / "raw"
PIXEL_M = 100.0
SHAPE_HW = (3730, 3292)

FEATURE_SENTINEL = -1e38

# competition band short names, in file order (verified against the raster's own descriptions)
COMPETITION_BANDS = (
    "mag_anom", "rtp", "tmi_hg", "geod_2ndinv", "iso_grav_anom_slope", "tc", "geod_shearrate",
    "geod_dilaterate", "tmi_vg", "deq_n100a15", "iso_grav_anom_vg", "det_elev", "iso_grav_anom",
    "tmi", "depth_to_base_surf", "ieq_n100a15", "cond_surf", "iso_grav_anom_hg", "det_elev_slope",
)
LIDAR_BANDS = ("ex_max", "ex_mean", "step_max", "lapneg_max", "lappos_max", "downface_max",
               "upface_max", "cross_max", "relief", "coh100", "strike", "valid")
RAD_BANDS = ("K", "Th", "U", "TC", "ThK", "UK", "UTh", "TMI_up150")


@dataclass
class Stack:
    shape: tuple[int, int]
    footprint: np.ndarray          # bool, official study area from sample_submission
    layers: dict                   # name -> (H, W) float32
    provenance: dict               # name -> source string


def _open(name: str):
    return rasterio.open(RAW / name)


def _u8_to_float(arr: np.ndarray) -> np.ndarray:
    """uint8 with 0 == nodata -> float32 with NaN at nodata, else value/255."""
    out = np.full(arr.shape, np.nan, dtype=np.float32)
    m = arr > 0
    out[m] = arr[m].astype(np.float32) / 255.0
    return out


def _grad_mag(a: np.ndarray) -> np.ndarray:
    gy, gx = np.gradient(a.astype(np.float32))
    return np.hypot(gx, gy).astype(np.float32)


def _hessian_eigen(a: np.ndarray, sigma_px: float) -> tuple[np.ndarray, np.ndarray]:
    """Eigenvalues (lam1 <= lam2) of the Gaussian-smoothed Hessian, scale-normalised."""
    s = ndimage.gaussian_filter(a.astype(np.float32), sigma_px)
    n = sigma_px ** 2
    gyy = ndimage.sobel(ndimage.sobel(s, axis=0), axis=0) / 4.0 * n
    gxx = ndimage.sobel(ndimage.sobel(s, axis=1), axis=1) / 4.0 * n
    gxy = ndimage.sobel(ndimage.sobel(s, axis=0), axis=1) / 4.0 * n
    tmp = np.sqrt(((gxx - gyy) / 2.0) ** 2 + gxy ** 2)
    return (gxx + gyy) / 2.0 - tmp, (gxx + gyy) / 2.0 + tmp


def frangi_vesselness(a: np.ndarray, sigmas_px, beta: float = 0.5, c_frac: float = 0.5,
                      dark_on_light: bool = False) -> np.ndarray:
    """Frangi et al. (MICCAI 1998, LNCS 1496:130-137) 2-D vesselness, multiscale max.

    ``sigmas_px`` are in *pixels of this grid* (100 m here) and are always reported as such.
    """
    a = a.astype(np.float32)
    finite = np.isfinite(a)
    work = np.where(finite, a, np.nanmedian(a[finite]) if finite.any() else 0.0)
    best = np.zeros(a.shape, dtype=np.float32)
    for s in sigmas_px:
        l1, l2 = _hessian_eigen(work, float(s))
        if not dark_on_light:
            l1, l2 = -l1, -l2  # bright tubular ridges
        ratio = np.divide(l1, l2, out=np.zeros_like(l1), where=np.abs(l2) > 1e-12)
        rb = np.abs(ratio)
        s2 = l1 ** 2 + l2 ** 2
        c = c_frac * float(np.nanmax(s2)) if np.isfinite(s2).any() else 1.0
        v = np.exp(-rb ** 2 / (2 * beta ** 2)) * (1.0 - np.exp(-s2 / (2 * max(c, 1e-12) ** 2)))
        v = np.where(l2 < 0, 0.0, v)
        best = np.maximum(best, v.astype(np.float32))
    return np.where(finite, best, np.nan).astype(np.float32)


def structure_tensor_fields(a: np.ndarray, sigma_px: float = 1.5) -> dict:
    """Structure-tensor coherence and dominant strike (radians, 0 = N-S line, E-W strike)."""
    s = ndimage.gaussian_filter(a.astype(np.float32), sigma_px)
    gy, gx = np.gradient(s)
    jxx = ndimage.gaussian_filter(gx * gx, sigma_px)
    jyy = ndimage.gaussian_filter(gy * gy, sigma_px)
    jxy = ndimage.gaussian_filter(gx * gy, sigma_px)
    tr = jxx + jyy
    det = jxx * jyy - jxy ** 2
    disc = np.sqrt(np.maximum(tr ** 2 / 4.0 - det, 0.0))
    l1 = tr / 2.0 + disc
    l2 = tr / 2.0 - disc
    coh = np.divide(l1 - l2, l1 + l2, out=np.zeros_like(l1), where=(l1 + l2) > 1e-12)
    theta = 0.5 * np.arctan2(2 * jxy, jxx - jyy)      # gradient direction
    strike = (theta + np.pi / 2.0)                     # line direction
    strike = np.mod(strike, np.pi)
    return {"coherence": coh.astype(np.float32), "strike_rad": strike.astype(np.float32)}


def steger_ridge_response(a: np.ndarray, sigma_px: float = 2.0) -> np.ndarray:
    """|largest Hessian eigenvalue| at one scale: the sub-pixel ridge/valley *strength* field.

    Steger (IEEE TPAMI 20(2):113-125, 1998) localises line centres by the extremum of the
    second-derivative eigen-direction; the eigenvalue magnitude is the line strength used here.
    Sub-pixel offsets are not resolvable on a 100 m aggregate, which is disclosed, not hidden.
    """
    l1, l2 = _hessian_eigen(a.astype(np.float32), sigma_px)
    return np.maximum(np.abs(l1), np.abs(l2)).astype(np.float32)


def strike_concordance(strike_a: np.ndarray, strike_b: np.ndarray) -> np.ndarray:
    """cos^2 of the angle between two undirected line orientations, in [0, 1]."""
    d = strike_a - strike_b
    return (np.cos(d) ** 2).astype(np.float32)


def _dist_m(mask: np.ndarray) -> np.ndarray:
    if not mask.any():
        return np.full(mask.shape, np.inf, dtype=np.float32)
    return (ndimage.distance_transform_edt(~mask) * PIXEL_M).astype(np.float32)


def _load_qfaults(shape_hw) -> np.ndarray:
    import csv
    m = np.zeros(shape_hw, dtype=bool)
    path = RAW / "external" / "gdr_qfaults_traces.csv"
    with path.open() as fh:
        for row in csv.DictReader(fh):
            if row.get("centroid_in_footprint") != "1":
                continue
            r, c = int(float(row["centroid_row"])), int(float(row["centroid_col"]))
            if 0 <= r < shape_hw[0] and 0 <= c < shape_hw[1]:
                m[r, c] = True
    return m


def _load_hot_springs(shape_hw, min_temp_c: float = 40.0) -> np.ndarray:
    import csv
    m = np.zeros(shape_hw, dtype=bool)
    path = RAW / "external" / "gdr_wellspring_in_footprint.csv"
    with path.open() as fh:
        for row in csv.DictReader(fh):
            try:
                t = float(row["temp_c"])
            except (TypeError, ValueError):
                continue
            if not np.isfinite(t) or t < min_temp_c:
                continue
            r, c = int(float(row["row"])), int(float(row["col"]))
            if 0 <= r < shape_hw[0] and 0 <= c < shape_hw[1]:
                m[r, c] = True
    return m


def iter_layers(visible_faults: np.ndarray | None = None,
                sigmas_px=(2.0, 4.0, 8.0, 16.0)):
    """Yield ``(name, array, provenance)`` one layer at a time.

    Streaming matters: the full stack is ~3 GB resident, which does not fit this sandbox, so
    callers write each layer straight to a disk memmap and drop it.
    """
    with _open("sample_submission.tif") as ds:
        sample = ds.read(1).astype(np.float64)
        shape = (ds.height, ds.width)
        crs = ds.crs
        transform = ds.transform
    footprint = np.isfinite(sample)
    if shape != SHAPE_HW:
        raise SystemExit(f"official grid shape {shape} != {SHAPE_HW}")
    lidar_cos = lidar_sin = None
    keep_det_elev = None
    yield "__footprint__", footprint, "sample_submission.tif finite cells (official study area)"

    with _open("training_features.tif") as ds:
        descs = ds.descriptions
        for i, name in enumerate(COMPETITION_BANDS):
            if not descs[i].startswith(name + " "):
                raise SystemExit(f"band {i+1} description {descs[i]!r} != expected {name!r}")
            b = ds.read(i + 1).astype(np.float32)
            b[b < FEATURE_SENTINEL] = np.nan
            if name == "det_elev":
                keep_det_elev = b          # needed again for the topographic line fields
            yield name, b, "organiser training_features.tif via hash-pinned mirror"

    with _open("external/lidar_scarp_features_u8.tif") as ds:
        raw = ds.read()
        valid = raw[LIDAR_BANDS.index("valid")] > 0
        for i, name in enumerate(LIDAR_BANDS):
            if ds.descriptions[i] != name:
                raise SystemExit(f"lidar band {i+1} {ds.descriptions[i]!r} != {name!r}")
            src = ("owner CI from USGS 3DEP 1 m DEM (706/716 tiles), uint8 aggregate on the "
                   "100 m grid")
            if name == "valid":
                yield "lidar_valid", valid.astype(np.float32), src
            elif name == "strike":
                # strike is an undirected orientation: keep cos/sin so wrapping is harmless
                ang = raw[i].astype(np.float32) / 255.0 * np.pi
                lidar_cos = np.where(valid, np.cos(2 * ang), np.nan).astype(np.float32)
                lidar_sin = np.where(valid, np.sin(2 * ang), np.nan).astype(np.float32)
                yield "lidar_strike_cos", lidar_cos, src
                yield "lidar_strike_sin", lidar_sin, src
            else:
                yield "lidar_" + name, _u8_to_float(raw[i]), src

    rad = np.zeros((8,) + shape, dtype=np.uint8)
    with _open("external/geodawn_rad_u8.tif") as ds:
        rad[0:4] = ds.read()
        rad_names = list(ds.descriptions)
    with _open("external/geodawn_extensions_u8.tif") as ds:
        rad[4:8] = ds.read()
        rad_names += list(ds.descriptions)
    for i, name in enumerate(RAD_BANDS):
        if rad_names[i] != name:
            raise SystemExit(f"radiometric band {i+1} {rad_names[i]!r} != {name!r}")
        yield ("rad_" + name, _u8_to_float(rad[i]),
               "USGS GeoDAWN release DOI 10.5066/P93LGLVQ, uint8 1st-99th pct")

    with _open("external/derived_sgmc_faults_100m_u8.tif") as ds:
        sgmc = ds.read(1) == 1
    yield ("sgmc_fault", sgmc.astype(np.float32),
           "USGS SGMC state geologic-map faults rasterised to 100 m (owner CI)")

    # ---- independent inventories -----------------------------------------------------------
    qf = _load_qfaults(shape)
    yield ("qfaults_centroid", qf.astype(np.float32),
           "GDR 1391 INGENIOUS Quaternary fault trace centroids (CC BY 4.0)")
    hs = _load_hot_springs(shape)
    yield ("hot_spring_40c", hs.astype(np.float32),
           "GDR 1391 well/spring points with measured temp >= 40 C (CC BY 4.0)")

    # ---- catalogue-derived layers (visible faults ONLY) ------------------------------------
    if visible_faults is None:
        visible_faults = np.zeros(shape, dtype=bool)
    vf = np.asarray(visible_faults, dtype=bool)
    yield ("d_visible_catalogue_m", _dist_m(vf),
           "distance to the VISIBLE catalogue only (holdout-safe)")

    # ---- inventory distances ---------------------------------------------------------------
    yield "d_sgmc_m", _dist_m(sgmc), "distance to all SGMC map faults"
    sgmc_off = sgmc & ~vf
    yield ("d_sgmc_off_visible_m", _dist_m(sgmc_off),
           "distance to SGMC map faults outside the VISIBLE catalogue")
    yield "d_qfaults_m", _dist_m(qf), "distance to INGENIOUS Quaternary trace centroids"
    yield "d_hot_spring_m", _dist_m(hs), "distance to GDR thermal points >= 40 C"

    # ---- topographic line / scarp fields on detrended elevation ----------------------------
    de = keep_det_elev
    fin = np.isfinite(de)
    de_filled = np.where(fin, de, np.nanmean(de[fin]) if fin.any() else 0.0).astype(np.float32)
    scale_note = ("derived here from detrended elevation on the 100 m grid; filter scales are "
                  "100 m pixels, NOT the 2-20 m native scales the brief requests")
    yield "det_elev_grad", _grad_mag(de_filled), scale_note
    yield "steger_ridge_s2", steger_ridge_response(de_filled, 2.0), scale_note
    yield "steger_ridge_s4", steger_ridge_response(de_filled, 4.0), scale_note
    yield "frangi_2to16", frangi_vesselness(de_filled, sigmas_px), scale_note
    st = structure_tensor_fields(de_filled, 1.5)
    yield "st_coherence", st["coherence"], scale_note
    yield "st_strike_rad", st["strike_rad"], scale_note + " (orientation, excluded as a raw feature)"
    if lidar_cos is not None:
        yield ("strike_concordance",
               strike_concordance(st["strike_rad"],
                                  np.arctan2(np.nan_to_num(lidar_sin),
                                             np.nan_to_num(lidar_cos)) / 2.0),
               "cos^2 angle between the 100 m structure-tensor strike and the 1 m-derived LiDAR "
               "scarp strike")
    del lidar_cos, lidar_sin, keep_det_elev, de, de_filled

    # ---- geophysical edge fields -----------------------------------------------------------
    with _open("training_features.tif") as ds:
        idx = {n: i for i, n in enumerate(COMPETITION_BANDS)}
        grad_src = {}
        for nm in ("iso_grav_anom_hg", "tmi_hg", "iso_grav_anom_vg", "tmi_vg", "tc",
                   "depth_to_base_surf", "cond_surf"):
            b = ds.read(idx[nm] + 1).astype(np.float32)
            b[b < FEATURE_SENTINEL] = np.nan
            grad_src[nm] = b
    for nm, b in grad_src.items():
        yield nm + "_grad", _grad_mag(np.nan_to_num(b, nan=0.0)), \
            "derived here: |grad| of the organiser band"
    yield ("basement_step",
           frangi_vesselness(np.nan_to_num(grad_src["depth_to_base_surf"], nan=0.0), (2.0, 4.0)),
           "Frangi line measure of depth-to-basement (cover-thickness corridor)")


#: layers that are not model features (masks / redundant angle encodings)
NON_FEATURES = {"__footprint__", "lidar_valid"}
#: layers that read the visible-catalogue set and therefore MUST be rebuilt per holdout fold
FOLD_DEPENDENT = ("d_visible_catalogue_m", "d_sgmc_off_visible_m")
