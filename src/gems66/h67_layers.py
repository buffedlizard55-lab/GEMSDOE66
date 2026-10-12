"""H67 (this session) layer loading: native-resolution LiDAR-derived scarp stack.

Every byte is a hash-pinned owner mirror of a USGS product (see
``registry/data_manifest.json`` and the receipts under ``data/raw/external/``).
Provenance chain, verified this session:

* ``external/lidar_scarp_features_u8.tif``  - 12-band, 2 m-working-resolution scarp
  descriptors aggregated to the 100 m competition grid, computed by the owner's CI from
  706/716 USGS 3DEP 1 m bare-earth DEM tiles (EarthMRI 2020).  Quantisation receipt:
  ``lidar_scarp_features.json`` (q = 1 + round(254 t(x/xmax)), 0 = no lidar).
* ``gems48/h52_scarp3m_100m.tif`` - companion 7-band scarp-height/attitude product from
  697/700 of the same 1 m tiles (int16, nodata -32768).
* ``confounds/tiger_road_distance_m.tif``, ``confounds/blm_closed_claim_distance_m.tif`` -
  the existing cultural-feature distance layers (roads; BLM closed claims = field edges /
  old mining), GEMSDOE24 audit_sources.
* training bands (TMI, tmi_vg, det_elev, det_elev_slope) from ``training_features.tif``.

All layers are returned on the canonical 3730 x 3292 grid in physical units (metres,
metres/m, degrees, metres distance).  Nothing in this module touches fault labels.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import rasterio

from .spec66 import load_quant
from gemsdoe66.grid import RAW, catalogue_mask, footprint_mask

EXT = RAW / "external"
G48 = RAW / "gems48"
CONF = RAW / "confounds"

QXMAX = {  # from the pinned sidecar (verified identical to features.py LIDAR_QUANT)
    "ex_max": (1.5, "sqrt"), "ex_mean": (0.3, "sqrt"), "step_max": (1.0, "sqrt"),
    "lapneg_max": (0.05, "sqrt"), "lappos_max": (0.05, "sqrt"),
    "downface_max": (1.0, "sqrt"), "upface_max": (1.0, "sqrt"),
    "cross_max": (1.0, "sqrt"), "relief": (300.0, "sqrt"),
    "coh100": (1.0, "linear"), "strike": (180.0, "linear"), "valid": (1.0, "linear"),
}


def _dequant(q: np.ndarray, xmax: float, kind: str) -> np.ndarray:
    out = np.full(q.shape, np.nan, np.float32)
    ok = q > 0
    t = (q[ok].astype(np.float32) - 1.0) / 254.0
    r = t * t if kind == "sqrt" else t
    out[ok] = xmax * r
    return out


def _read(path: Path, band: int = 1) -> np.ndarray:
    with rasterio.open(path) as ds:
        a = ds.read(band)
    return a


def _pctl01(a: np.ndarray, fp: np.ndarray, lo: float = 1.0, hi: float = 99.0) -> np.ndarray:
    v = a[fp & np.isfinite(a)]
    if v.size == 0:
        return np.zeros(a.shape, np.float32)
    p0, p1 = np.percentile(v, (lo, hi))
    out = (a - p0) / max(1e-12, p1 - p0)
    out = np.clip(out, 0.0, 1.0).astype(np.float32)
    out[~np.isfinite(out)] = 0.0
    return out


@dataclass
class Layers:
    fp: np.ndarray
    cat: np.ndarray
    dcat_px: np.ndarray            # distance transform to the given catalogue, px
    valid: np.ndarray              # bool: valid lidar samples in cell (>= 0.5)
    amp: np.ndarray                # ex_max, m/m
    step: np.ndarray               # step_max, m/m
    height: np.ndarray             # step * 10 m  (assumption A1, documented)
    lneg: np.ndarray               # crest convexity, 1/m
    lpos: np.ndarray               # base concavity, 1/m
    dface: np.ndarray
    uface: np.ndarray
    cross: np.ndarray
    sharp: np.ndarray              # sqrt(lneg * lpos)
    facing: np.ndarray             # (dface - uface) / (dface + uface)
    coh: np.ndarray                # structure-tensor coherence at 100 m, 0..1
    strike: np.ndarray             # degrees 0..180
    relief: np.ndarray             # local relief, m
    tmi: np.ndarray                # 0..1 percentile units
    tmi_vg: np.ndarray             # 0..1
    up150: np.ndarray              # TMI continued to 150 m, 0..1
    uk: np.ndarray
    thk: np.ndarray
    road_m: np.ndarray             # distance to nearest TIGER road, m
    claim_m: np.ndarray            # distance to nearest BLM closed claim, m
    h52_h: np.ndarray              # h52 scarp-height estimate (native 1 m tiles), raw int16/10
    h52_face: np.ndarray           # h52 facing at peak (deg * 0.01 scale as stored)
    h52_coh: np.ndarray            # h52 cover 0..1 (proxy for template fit support)
    meta: dict = field(default_factory=dict)


def load_layers() -> Layers:
    fp = footprint_mask()
    cat = catalogue_mask()
    from scipy import ndimage
    dcat = ndimage.distance_transform_edt(~cat).astype(np.float32)

    # ---- 1 m-derived 12-band scarp stack --------------------------------------
    quant = load_quant(EXT / "lidar_scarp_features_u8.tif")
    bands = {}
    with rasterio.open(EXT / "lidar_scarp_features_u8.tif") as ds:
        names = ds.descriptions or []
        for i, n in enumerate(names, start=1):
            bands[n] = quant[n].decode(ds.read(i))
    amp, step = bands["ex_max"], bands["step_max"]
    lneg, lpos = bands["lapneg_max"], bands["lappos_max"]
    dface, uface, cross = bands["downface_max"], bands["upface_max"], bands["cross_max"]
    relief, coh, strike, valid = bands["relief"], bands["coh100"], bands["strike"], bands["valid"]
    with np.errstate(invalid="ignore", divide="ignore"):
        facing = ((dface - uface) / (dface + uface + 1e-3)).astype(np.float32)
        sharp = np.sqrt(np.maximum(lneg, 0.0) * np.maximum(lpos, 0.0)).astype(np.float32)
    height = (np.nan_to_num(step, nan=0.0) * 10.0).astype(np.float32)
    dom = fp & np.isfinite(amp)
    for a in (facing, sharp, height):
        a[~np.isfinite(a)] = np.nan
    valid_bool = valid >= 0.5

    # ---- h52 native 1 m-tile scarp-height product ------------------------------
    with rasterio.open(G48 / "h52_scarp3m_100m.tif") as ds:
        h52 = {n: ds.read(i) for i, n in enumerate(ds.descriptions or (), start=1)}
    nod = h52["cover"] == -32768
    h52_h = np.where(nod, np.nan, h52["h_all"].astype(np.float32) / 10.0)
    h52_face = np.where(nod, np.nan, h52["facing_at"].astype(np.float32) / 100.0)
    h52_coh = np.where(nod, 0.0, h52["cover"].astype(np.float32) / 100.0)

    # ---- geophysics (competition bands, percentile-normalised) -----------------
    with rasterio.open(RAW / "training_features.tif") as ds:
        tmi_raw = ds.read(14)          # TMI
        tmi_vg_raw = ds.read(9)        # TMI vertical gradient
    tmi = _pctl01(np.where(np.isfinite(tmi_raw) & (tmi_raw > -1e30), tmi_raw, np.nan), fp)
    tmi_vg = _pctl01(np.where(np.isfinite(tmi_vg_raw) & (tmi_vg_raw > -1e30), tmi_vg_raw, np.nan), fp)
    with rasterio.open(EXT / "geodawn_extensions_u8.tif") as ds:
        ext_bands = {n: ds.read(i) for i, n in enumerate(ds.descriptions or (), start=1)}
    up150 = (ext_bands["TMI_up150"].astype(np.float32) / 255.0)
    with rasterio.open(EXT / "geodawn_rad_u8.tif") as ds:
        rad_bands = {n: ds.read(i) for i, n in enumerate(ds.descriptions or (), start=1)}
    uk = (rad_bands["UK"] if "UK" in rad_bands else ext_bands["UK"]).astype(np.float32) / 255.0
    thk = (rad_bands["ThK"] if "ThK" in rad_bands else ext_bands["ThK"]).astype(np.float32) / 255.0
    # extend u8 layers: 0 outside the radiometric flight area -> mark NaN-ish by fp only
    up150[~fp] = 0.0

    # ---- cultural-feature mask (existing layers) --------------------------------
    # NaN = outside the layer's coverage window -> treat as "far" (no veto).
    road = _read(CONF / "tiger_road_distance_m.tif").astype(np.float32)
    claim = _read(CONF / "blm_closed_claim_distance_m.tif").astype(np.float32)
    road = np.where(np.isfinite(road), road, 1e6)
    claim = np.where(np.isfinite(claim), claim, 1e6)

    meta = {
        "lidar_coverage_frac": float((valid_bool & fp).sum() / max(1, fp.sum())),
        "road_m_range": [float(road.min()), float(road.max())],
        "claim_m_range": [float(claim.min()), float(claim.max())],
        "h52_cover_cells": int((h52_coh > 0).sum()),
    }
    return Layers(fp=fp, cat=cat, dcat_px=dcat, valid=valid_bool,
                  amp=amp, step=step, height=height, lneg=lneg, lpos=lpos,
                  dface=dface, uface=uface, cross=cross, sharp=sharp, facing=facing,
                  coh=coh, strike=strike, relief=relief, tmi=tmi, tmi_vg=tmi_vg,
                  up150=up150, uk=uk, thk=thk, road_m=road, claim_m=claim,
                  h52_h=h52_h, h52_face=h52_face, h52_coh=h52_coh, meta=meta)


def emission_domain(L: Layers, road_veto_m: float = 250.0) -> np.ndarray:
    """Where dots may be placed: footprint, lidar-covered, off the catalogue, off roads.

    The catalogue 200 m buffer matches the incumbent's zero-on-catalogue geometry;
    the road veto is the cultural-feature mask required by the lane brief.
    """
    from gemsdoe66.holdout import buffer_around
    return (L.fp & L.valid & ~buffer_around(L.cat, 2.0) & (L.road_m >= road_veto_m))
