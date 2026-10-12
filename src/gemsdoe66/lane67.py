"""H67 lane - native-resolution LiDAR scarp channels, aggregated to the official 100 m grid.

This module implements the assigned lane for this session:

  (i)  scarplet-style scarp evidence aggregated per 100 m cell: scarp-pixel fraction,
       SNR-weighted amplitude, structure-tensor orientation coherence and dominant strike,
       taken from the hash-pinned 1 m-LiDAR-derived descriptor stack
       (``external/lidar_scarp_features_u8.tif``, 12 channels, USGS 3DEP 1 m bare-earth DEM,
       706/716 tiles, see README section 2);
  (ii) scale-persistent Steger / Frangi line evidence on the slope-detrended surface,
       using the shared implementations in :mod:`gemsdoe66.fields` (no private fork).

Documented scale deviation (inherited, not hidden)
--------------------------------------------------
The raw 1 m GeoTIFF tiles are not reachable from this sandbox (only github.com and PyPI are
allowed; prd-tnm.s3.amazonaws.com returns HTTP 000).  The lane therefore runs on the
1 m-derived per-100 m aggregate for the scarp channels (which *is* native-resolution
information, summarised per cell) and at 2-20 pixel scales on the 100 m detrended surface for
the line evidence.  That is the same deviation recorded in README section 7 item 1; it is
repeated here so no reader mistakes this for a 1 m re-run.

What is new in this module relative to the inherited ``lidar_lane`` fields
-------------------------------------------------------------------------
1. The strike channel is used as a *circular* quantity: orientation coherence and dominant
   strike are aggregated with amplitude weighting and the 2-theta axial convention.
2. A scale-persistence term (minimum normalised Frangi response across scales) is required,
   which suppresses short cultural edges that exist at one scale only.
3. The scarp-pixel fraction is computed as the fraction of a 3x3 cell neighbourhood carrying
   native-resolution scarp evidence, not as a per-cell indicator.
4. Nothing here reads an inventory layer as a feature; SGMC / catalogue / QFaults / vent
   rasters are labels or *exclusion* masks only.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter, uniform_filter

from .features import LIDAR_QUANT, dequantize, load_stack
from .fields import (fill_for_filter, frangi_line, robust_unit, structure_tensor)
from .grid import RAW, footprint_mask

EXTERNAL = RAW / "external"
LIDAR_CHANNELS = ["ex_max", "ex_mean", "step_max", "lapneg_max", "lappos_max",
                  "downface_max", "upface_max", "cross_max", "relief", "coh100",
                  "strike", "valid"]


def lidar_grids() -> dict[str, np.ndarray]:
    """Dequantised 1 m-LiDAR-derived channels on the 100 m grid (NaN where nodata)."""
    import rasterio

    out: dict[str, np.ndarray] = {}
    with rasterio.open(EXTERNAL / "lidar_scarp_features_u8.tif") as src:
        for i, name in enumerate(LIDAR_CHANNELS, start=1):
            xmax, rule = LIDAR_QUANT[name]
            out[name] = dequantize(src.read(i), xmax, rule)
    return out


def circular_stats(strike_deg: np.ndarray, weight: np.ndarray, size: int = 3):
    """Amplitude-weighted axial mean strike and coherence from a strike raster.

    ``strike_deg`` is the 1 m-derived scarp strike (degrees, 0-180 axial).  Both statistics
    use the 2-theta representation so that 0 deg and 180 deg are the same direction.
    """
    ok = np.isfinite(strike_deg) & np.isfinite(weight)
    th = np.deg2rad(np.where(ok, strike_deg, 0.0))
    w = np.where(ok, np.maximum(weight, 0.0), 0.0)
    c = w * np.cos(2.0 * th)
    s = w * np.sin(2.0 * th)
    cs = uniform_filter(c, size=size, mode="nearest")
    ss = uniform_filter(s, size=size, mode="nearest")
    ws = uniform_filter(w, size=size, mode="nearest")
    coherence = np.where(ws > 1e-9, np.hypot(cs, ss) / np.maximum(ws, 1e-9), 0.0)
    dominant = 0.5 * np.rad2deg(np.arctan2(ss, cs)) % 180.0
    return dominant.astype(np.float32), np.clip(coherence, 0.0, 1.0).astype(np.float32)


def lane_parts(size: int = 3) -> dict[str, np.ndarray]:
    """The four scarplet-lane aggregates plus supporting terms, on the 100 m grid."""
    L = lidar_grids()
    amp = np.nan_to_num(L["ex_max"], nan=0.0)
    coh = np.nan_to_num(L["coh100"], nan=0.0)
    step = np.nan_to_num(L["step_max"], nan=0.0)
    relief = np.nan_to_num(L["relief"], nan=0.0)
    valid = np.isfinite(L["valid"]) & (L["valid"] > 0)

    # (i-a) scarp-pixel fraction: share of the 3x3 neighbourhood carrying scarp evidence
    scarp_frac = uniform_filter((amp > 0).astype(np.float32), size=size, mode="nearest")

    # (i-b) SNR-weighted amplitude: amplitude weighted by the 1 m strike coherence
    snr_amp = uniform_filter(amp * coh, size=size, mode="nearest")

    # (i-c) orientation coherence and (i-d) dominant strike, amplitude-weighted, axial
    dominant, orient_coh = circular_stats(L["strike"], np.where(valid, amp * coh + 1e-6, np.nan), size)

    # supporting: cross-profile step strength and local relief of the scarp population
    step_frac = uniform_filter((step > 0).astype(np.float32), size=size, mode="nearest")
    relief_mean = uniform_filter(relief, size=size, mode="nearest")

    fp = footprint_mask()
    parts = {
        "scarp_pixel_fraction": robust_unit(scarp_frac, fp & valid),
        "snr_weighted_amplitude": robust_unit(snr_amp, fp & valid),
        "orientation_coherence": orient_coh,
        "dominant_strike_deg": np.where(valid, dominant, np.nan).astype(np.float32),
        "step_fraction": robust_unit(step_frac, fp & valid),
        "relief_mean": robust_unit(relief_mean, fp & valid),
        "valid": valid.astype(np.float32),
    }
    return parts


def persistence_parts(sigmas=(2.0, 5.0, 10.0)) -> dict[str, np.ndarray]:
    """Scale-persistent line evidence on the slope-detrended surface (shared helpers)."""
    stack, names, fi = load_stack()
    fp = footprint_mask()
    idx = {n: i for i, n in enumerate(names)}

    def grid(name: str) -> np.ndarray:
        out = np.full(fp.size, np.nan, np.float32)
        out[fi] = np.asarray(stack[idx[name]])
        return out.reshape(fp.shape)

    det = grid("det_elev")
    ok = fp & np.isfinite(det)
    z = fill_for_filter(det, ok)

    per = []
    for s in sigmas:
        r = np.maximum(frangi_line(z, sigmas=(s,), ridge=True),
                       frangi_line(-z, sigmas=(s,), ridge=True))
        per.append(robust_unit(r, ok))
    band = np.stack(per, 0)
    persistence = band.min(0)                       # must be present at every scale
    theta, coh = structure_tensor(z, sigma=6.0)
    return {"persistence": persistence.astype(np.float32),
            "tensor_coherence": robust_unit(coh, ok),
            "tensor_strike_deg": np.where(ok, np.rad2deg(theta) % 180.0, np.nan).astype(np.float32),
            "ok": ok}


def strike_concordance(strike_a: np.ndarray, strike_b: np.ndarray) -> np.ndarray:
    """Axial agreement of two strike fields: cos(2*dtheta) in [0, 1]."""
    ok = np.isfinite(strike_a) & np.isfinite(strike_b)
    d = np.abs(np.deg2rad(strike_a - strike_b))
    d = np.abs((d + np.pi / 2) % np.pi - np.pi / 2)
    return np.where(ok, np.clip(np.cos(2.0 * d), 0.0, 1.0), 0.0).astype(np.float32)


if __name__ == "__main__":                                  # pragma: no cover - diagnostic
    p = lane_parts()
    q = persistence_parts()
    concord = strike_concordance(p["dominant_strike_deg"], q["tensor_strike_deg"])
    for k, v in list(p.items()) + list(q.items()):
        f = np.isfinite(v)
        print(f"{k:24s} finite={int(f.sum()):>9d} mean={np.nanmean(v) if f.any() else float('nan'):.4f}")
    print(f"{'strike_concordance':24s} mean={concord.mean():.4f} p90={np.percentile(concord, 90):.4f}")
