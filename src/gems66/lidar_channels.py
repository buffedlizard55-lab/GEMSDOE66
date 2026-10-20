"""Native-resolution LiDAR scarp channels (lane LIDAR-01).

What this module computes
-------------------------
(i)  A **slope-aware scarplet template response** following the scarp-template idea of
     Sare & Hilley (JOSS 2018, doi:10.21105/joss.01066) extended with the slope-aware
     templates described in the AGU 2015 poster T31A-2838 (Surprise Valley test): a
     tectonic scarp step is a *monoclinal step whose free face is coherent along strike*,
     and the diagnostic member of the family is the **antislope (uphill-facing) member**,
     because fluvial terrace risers, channel banks and landslide headscarps predominantly
     produce downslope- or cross-slope-facing steps.

(ii) **Steger sub-pixel ridge/valley lines** (Steger, IEEE TPAMI 20(2):113-125, 1998) and
     **Frangi multiscale Hessian line measures** (Frangi et al., MICCAI 1998,
     LNCS 1496:130-137) on the slope-detrended (band-passed) scarp field.

     SCALE DISCLOSURE (mandatory): the requested 2-20 m scales require the 1 m/2 m
     bare-earth DEM itself.  Only the cached 100 m aggregate
     ``external/lidar_scarp_features_u8.tif`` is reachable in this environment (its bands
     are *extrema of 2 m descriptors* inside each 100 m cell, so it retains
     sub-cell scarp information, but not sub-cell geometry).  The operators below are
     therefore evaluated at sigma = 1.0-4.0 **100 m cells** (100-400 m), the finest
     representable range, and every result carrying them is labelled as such.
     The native 2-20 m version of this operator is NOT measured here.

(iii) Aggregation to 100 m cells of the four quantities named in the lane:
     scarp-pixel fraction, SNR-weighted amplitude, structure-tensor orientation
     coherence and dominant strike.

Dequantisation
--------------
``lidar_scarp_features_u8.tif`` stores ``q = 1 + round(254 * t(clip(x/xmax,0,1)))`` with
``t`` in {sqrt, linear} and ``0 = no lidar`` (see ``external/lidar_scarp_features.json``).
Inverting: ``x = xmax * u**2`` for sqrt bands and ``x = xmax * u`` for linear bands with
``u = (q-1)/254``.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy import ndimage

# --- band order / quantisation of external/lidar_scarp_features_u8.tif -------------
LIDAR_BANDS = [
    "ex_max", "ex_mean", "step_max", "lapneg_max", "lappos_max", "downface_max",
    "upface_max", "cross_max", "relief", "coh100", "strike", "valid",
]
LIDAR_SCALE = {  # (xmax, transform)
    "ex_max": (1.5, "sqrt"), "ex_mean": (0.3, "sqrt"), "step_max": (1.0, "sqrt"),
    "lapneg_max": (0.05, "sqrt"), "lappos_max": (0.05, "sqrt"),
    "downface_max": (1.0, "sqrt"), "upface_max": (1.0, "sqrt"),
    "cross_max": (1.0, "sqrt"), "relief": (300.0, "sqrt"),
    "coh100": (1.0, "linear"), "strike": (180.0, "linear"), "valid": (1.0, "linear"),
}
TOPO_BANDS = [
    "slope_p90", "slope_max", "steep_frac", "slope_std", "relief_local",
    "curv_prof_absmax", "aspect_coherence", "hs_lineament", "dem_mean",
]


def dequantise(band_u8: np.ndarray, name: str) -> np.ndarray:
    """Invert the documented uint8 quantisation.  0 (nodata) becomes NaN."""
    q = band_u8.astype(np.float64)
    xmax, how = LIDAR_SCALE[name]
    u = (q - 1.0) / 254.0
    out = xmax * (u * u if how == "sqrt" else u)
    out[q == 0] = np.nan
    return out


def dequantise_topo(band_u8: np.ndarray, lo: float, hi: float) -> np.ndarray:
    q = band_u8.astype(np.float64)
    out = lo + (q - 1.0) / 254.0 * (hi - lo)
    out[q == 0] = np.nan
    return out


def load_lidar_stack(path: str | Path) -> dict[str, np.ndarray]:
    import rasterio
    with rasterio.open(path) as src:
        raw = src.read()
    return {name: dequantise(raw[i], name) for i, name in enumerate(LIDAR_BANDS)}


def load_topo_stack(path: str | Path, manifest_path: str | Path) -> dict[str, np.ndarray]:
    import rasterio
    spec = json.loads(Path(manifest_path).read_text())
    with rasterio.open(path) as src:
        raw = src.read()
    out = {}
    for b in spec["bands"]:
        i = b["index"] - 1
        out[b["band_name"]] = dequantise_topo(raw[i], b["lo"], b["hi"])
    return out


# --- Hessian machinery -------------------------------------------------------------
def _gaussian_derivatives(img: np.ndarray, sigma: float):
    """Return (Lx, Ly, Lxx, Lxy, Lyy) of ``img`` at scale ``sigma`` (NaNs excluded)."""
    work = np.where(np.isfinite(img), img, 0.0)
    gx = ndimage.gaussian_filter(work, sigma, order=[0, 1], mode="nearest")
    gy = ndimage.gaussian_filter(work, sigma, order=[1, 0], mode="nearest")
    lxx = ndimage.gaussian_filter(work, sigma, order=[0, 2], mode="nearest")
    lyy = ndimage.gaussian_filter(work, sigma, order=[2, 0], mode="nearest")
    lxy = ndimage.gaussian_filter(work, sigma, order=[1, 1], mode="nearest")
    return gx, gy, lxx, lxy, lyy


def _eig2(lxx, lxy, lyy):
    """Eigenvalues of the symmetric 2x2 Hessian; l1 is the smaller in |.|."""
    tr = lxx + lyy
    det = lxx * lyy - lxy * lxy
    disc = np.sqrt(np.maximum(tr * tr / 4.0 - det, 0.0))
    a = tr / 2.0 + disc
    b = tr / 2.0 - disc
    # order so that |l1| <= |l2|
    swap = np.abs(a) > np.abs(b)
    l1 = np.where(swap, b, a)
    l2 = np.where(swap, a, b)
    return l1, l2


def frangi_vesselness(img: np.ndarray, sigma: float, beta: float = 0.5,
                      c: float = 15.0, bright: bool = True) -> np.ndarray:
    """Frangi et al. (1998) vesselness for ridge (bright=True) or valley (bright=False) lines.

    V = exp(-Rb^2 / 2 beta^2) * (1 - exp(-S^2 / 2 c^2)) with
    Rb = |l1| / |l2|  (blobness) and S = sqrt(l1^2 + l2^2) (structureness).
    """
    _, _, lxx, lxy, lyy = _gaussian_derivatives(img, sigma)
    l1, l2 = _eig2(lxx, lxy, lyy)
    sign = -1.0 if bright else 1.0
    good = (np.sign(l2) == sign) & (np.abs(l2) > 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        rb = np.abs(l1) / np.maximum(np.abs(l2), 1e-30)
        s = np.sqrt(l1 * l1 + l2 * l2)
    v = np.exp(-(rb ** 2) / (2.0 * beta ** 2)) * (1.0 - np.exp(-(s ** 2) / (2.0 * c ** 2)))
    return np.where(good, v, 0.0)


def steger_lines(img: np.ndarray, sigma: float, response_min: float = 0.0,
                 bright: bool = True):
    """Steger (1998) sub-pixel line extraction.

    Returns ``(response, line_mask, subpixel_valid)``.  A pixel is a line pixel when the
    sub-pixel extremum of the directional derivative along the Hessian normal falls inside
    the pixel (|offset| < 0.5 in both axes) and the normal curvature has the requested sign.
    """
    gx, gy, lxx, lxy, lyy = _gaussian_derivatives(img, sigma)
    det = lxx * lyy - lxy * lxy
    safe = np.abs(det) > 1e-30
    det_s = np.where(safe, det, 1.0)
    ox = np.where(safe, -(lyy * gx - lxy * gy) / det_s, np.inf)
    oy = np.where(safe, -(lxx * gy - lxy * gx) / det_s, np.inf)
    inside = (np.abs(ox) < 0.5) & (np.abs(oy) < 0.5)
    l1, l2 = _eig2(lxx, lxy, lyy)
    sign_ok = np.sign(l2) == (-1.0 if bright else 1.0)
    resp = np.abs(l2)
    line = inside & sign_ok & (resp > response_min) & np.isfinite(img)
    return resp, line, inside


def orientation_coherence(img: np.ndarray, sigma: float, rho: float = 2.0) -> np.ndarray:
    """Structure-tensor coherence (Jaehne / Bigun) at scale ``sigma``.

    Coherence = ((Jxx-Jyy)^2 + 4 Jxy^2)^0.5 / (Jxx + Jyy), in [0, 1]; 1 = perfectly
    oriented (a straight ridge or valley), 0 = isotropic.
    """
    work = np.where(np.isfinite(img), img, 0.0)
    jxx = ndimage.gaussian_filter(work * work if False else work, sigma, order=[0, 1], mode="nearest")
    jyy = ndimage.gaussian_filter(work, sigma, order=[1, 0], mode="nearest")
    jxx = ndimage.gaussian_filter(jxx * jxx, rho, mode="nearest")
    jyy = ndimage.gaussian_filter(jyy * jyy, rho, mode="nearest")
    jxy = ndimage.gaussian_filter(
        ndimage.gaussian_filter(work, sigma, order=[0, 1], mode="nearest")
        * ndimage.gaussian_filter(work, sigma, order=[1, 0], mode="nearest"), rho, mode="nearest")
    tr = jxx + jyy
    return np.where(tr > 0, np.sqrt((jxx - jyy) ** 2 + 4.0 * jxy ** 2) / np.maximum(tr, 1e-30), 0.0)


def dominant_strike_deg(img: np.ndarray, sigma: float, rho: float = 2.0) -> np.ndarray:
    """Dominant line strike in degrees (0-180, measured from east, mod 180)."""
    work = np.where(np.isfinite(img), img, 0.0)
    gx = ndimage.gaussian_filter(work, sigma, order=[0, 1], mode="nearest")
    gy = ndimage.gaussian_filter(work, sigma, order=[1, 0], mode="nearest")
    jxx = ndimage.gaussian_filter(gx * gx, rho, mode="nearest")
    jyy = ndimage.gaussian_filter(gy * gy, rho, mode="nearest")
    jxy = ndimage.gaussian_filter(gx * gy, rho, mode="nearest")
    # lines run perpendicular to the dominant gradient direction
    ang = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy) + np.pi / 2.0
    return np.degrees(np.mod(ang, np.pi))


# --- slope-aware scarplet template -------------------------------------------------
def slope_aware_scarp_template(stack: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Return the slope-aware scarplet template channels.

    ``template_antislope`` is the response of an uphill-facing (antislope) step template:
    the part of the band-passed step that faces *against* the regional slope.  ``veto`` is
    the strongest competing step orientation (downslope-facing or cross-slope), which is
    what fluvial terrace risers, channel banks and field edges produce.  The signed
    ``template_net`` is the slope-aware fit residual used downstream.
    """
    up = np.nan_to_num(stack["upface_max"], nan=0.0)
    down = np.nan_to_num(stack["downface_max"], nan=0.0)
    cross = np.nan_to_num(stack["cross_max"], nan=0.0)
    step = np.nan_to_num(stack["step_max"], nan=0.0)
    coh = np.nan_to_num(stack["coh100"], nan=0.0)
    veto = np.maximum(down, cross)
    net = up - veto
    snr_amp = step * coh                      # SNR-weighted amplitude
    return {
        "template_antislope": up,
        "template_veto": veto,
        "template_net": net,
        "template_net_coh": np.maximum(net, 0.0) * coh,
        "snr_amp": snr_amp,
        "antislope_ratio": np.where(veto > 1e-9, up / np.maximum(veto, 1e-9), np.nan),
    }


def multiscale_line_fields(field: np.ndarray, scales=(1.0, 1.5, 2.0, 3.0, 4.0),
                           response_pct: float = 95.0) -> dict[str, np.ndarray]:
    """Frangi + Steger over several scales; returns per-scale max and the arg-scale.

    Memory-frugal: only the running maxima, the accumulated line count and the
    arg-scale map are kept (one float32 array each), never the whole scale stack.

    Fixed 2026-10-20 (IR-L04-TOOL-01): the Steger response threshold was taken
    as a percentile of the running *Frangi vesselness* maximum and then applied
    to the Steger Hessian response ``|l2|`` -- a unit mismatch (dimensionless
    vesselness in ~[0, 1] vs curvature units of the input surface) that made
    ``steger_frac300``'s operating point arbitrary.  The threshold is now the
    ``response_pct`` percentile of the Steger response itself at the same
    scale.  Frangi outputs are unchanged; Steger outputs of pre-fix runs
    (LIDAR-01/02) are not reproducible from this version and their
    ``steger_frac300`` values should be read with that caveat.
    """
    n = field.shape[0] * field.shape[1]
    best_fr = np.zeros(field.shape, dtype=np.float32)
    best_scale = np.zeros(field.shape, dtype=np.float32)
    line_sum = np.zeros(field.shape, dtype=np.float32)
    nan = ~(np.isfinite(field) if field.dtype.kind == "f" else np.ones(field.shape, bool))
    f = np.where(nan, 0.0, field).astype(np.float32)
    n_scale = 0
    for s in scales:
        fr = frangi_vesselness(f, s).astype(np.float32)
        fr[nan] = 0.0
        take = fr > best_fr
        best_fr = np.where(take, fr, best_fr)
        best_scale = np.where(take, np.float32(s), best_scale)
        del fr, take
        resp, line, _ = steger_lines(f, s, response_min=0.0)
        thr = float(np.percentile(resp[~nan], response_pct)) if (~nan).any() else np.inf
        line &= (resp > thr)
        del resp
        line &= ~nan
        line_sum += line.astype(np.float32)
        del line
        n_scale += 1
    # scarp-pixel fraction: per-scale line hits averaged, then smoothed over a
    # 3x3 (300 m) neighbourhood so a 100 m cell reports its neighbourhood's share.
    frac = ndimage.uniform_filter(line_sum / float(n_scale), 3, mode="nearest")
    return {
        "frangi_max": best_fr,
        "frangi_scale": best_scale,
        "steger_line": (line_sum > 0).astype(np.float32),
        "steger_frac300": frac.astype(np.float32),
        "frangi_nscale": np.full(field.shape, float(n_scale), dtype=np.float32),
    }
