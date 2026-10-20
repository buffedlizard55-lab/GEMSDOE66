"""LIDAR-02-A fields: local-SNR scarp prominence x cross-scale signed persistence.

This module only *adds* fields on top of :mod:`gems66.lidar_channels` (whose
dequantisation, slope-aware scarplet template and Hessian primitives are reused
unchanged).  Two quantities are new relative to everything measured in this
repository before 2026-10-20 (see docs/review/2026-10-20-lidar02-hypotheses.md):

``local_roughness``
    A ~1 km-support robust background roughness: the Gaussian-smoothed
    (sigma = 5 cells = 500 m) magnitude of the summed crest/toe laplacian
    extrema.  ``channels66``/``scarp66`` compute a 40 km-blockwise MAD z-score
    of amplitude; the denominator here is local, so detectability is judged
    against the terrain the scarp actually sits in.

``prominence``
    Antislope template net amplitude divided by that local roughness (plus a
    small percentile floor).  Unitless contrast; used through ranks only.

``persistence_count`` / ``persistence_gate``
    Per-scale Steger (1998) signed line masks on the coherence-weighted
    template field; a cell is persistent when a same-sign (bright/ridge) line
    is present at >= 2 scales.  ``multiscale_line_fields`` in the shared
    module ORs scales together and thresholds Steger by a Frangi percentile;
    here each scale is thresholded on its own response distribution and the
    count is kept, because the count is the cultural-edge discriminator.

Frangi vesselness is recomputed here only to fix one measured defect: with the
shared module's fixed ``c = 15`` on a [0, 1]-ish field the Hessian norm is
orders of magnitude below ``c`` and the response collapses toward
``S^2 / (2 c^2)`` (the same degeneracy H66-C recorded).  ``c`` is estimated
from the pooled Hessian-norm distribution instead; the eigenvalues and
derivative machinery are imported unchanged from the shared module.

Scale disclosure (mandatory, repeated): sigma values are in 100 m cells
(100-400 m).  The native 2-20 m operators require the 1 m/2 m DEM, which is
not reachable from this environment.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from .lidar_channels import _eig2, _gaussian_derivatives

SCALES = (1.0, 1.5, 2.0, 3.0, 4.0)


def local_roughness(lapneg: np.ndarray, lappos: np.ndarray, valid: np.ndarray,
                    sigma_px: float = 5.0) -> np.ndarray:
    """Gaussian-smoothed laplacian-extrema magnitude over ``valid`` cells.

    NaNs (no lidar) are excluded by smoothing the value and the validity
    weight separately and dividing (normalised convolution), so a cell next
    to a coverage gap is not assigned a spuriously low roughness.
    """
    mag = np.nan_to_num(lapneg, nan=0.0) + np.nan_to_num(lappos, nan=0.0)
    w = valid.astype(np.float64)
    num = ndimage.gaussian_filter(mag * w, sigma_px, mode="nearest")
    den = ndimage.gaussian_filter(w, sigma_px, mode="nearest")
    out = np.where(den > 1e-9, num / np.maximum(den, 1e-9), 0.0)
    return out.astype(np.float32)


def prominence(template_net: np.ndarray, roughness: np.ndarray,
               valid: np.ndarray, floor_pct: float = 10.0) -> tuple[np.ndarray, float]:
    """Antislope net amplitude / local roughness.  Returns (field, floor_used)."""
    net = np.maximum(np.nan_to_num(template_net, nan=0.0), 0.0)
    r = roughness[valid]
    floor = float(np.percentile(r, floor_pct)) if r.size else 0.0
    out = net / (roughness.astype(np.float64) + floor + 1e-12)
    out = np.where(valid, out, 0.0)
    return out.astype(np.float32), floor


def _hessian_norm_p99(field: np.ndarray, scales=SCALES) -> float:
    """Robust scale for Frangi's ``c`` from the pooled Hessian norm.

    Estimated on four 512x512 windows (grid corners + centre) to bound cost;
    the windows are fixed and documented, and only a percentile is taken.
    """
    f = np.nan_to_num(field, nan=0.0)
    h, w = f.shape
    wins = [(0, 0), (0, w - 512), (h - 512, 0), (h // 2 - 256, w // 2 - 256)]
    vals = []
    for (r0, c0) in wins:
        win = f[r0:r0 + 512, c0:c0 + 512]
        for s in scales:
            _, _, lxx, lxy, lyy = _gaussian_derivatives(win, s)
            l1, l2 = _eig2(lxx, lxy, lyy)
            vals.append(np.sqrt(l1 * l1 + l2 * l2).ravel())
    return float(np.percentile(np.concatenate(vals), 99.0))


def _per_scale(field: np.ndarray, sigma: float, valid: np.ndarray, c: float,
               beta: float = 0.5, response_pct: float = 97.5):
    """Frangi vesselness and Steger bright-line mask sharing one derivative set."""
    f = np.nan_to_num(field, nan=0.0)
    gx, gy, lxx, lxy, lyy = _gaussian_derivatives(f, sigma)
    l1, l2 = _eig2(lxx, lxy, lyy)
    with np.errstate(divide="ignore", invalid="ignore"):
        rb = np.abs(l1) / np.maximum(np.abs(l2), 1e-30)
        s = np.sqrt(l1 * l1 + l2 * l2)
    fr = np.exp(-(rb ** 2) / (2.0 * beta ** 2)) * (1.0 - np.exp(-(s ** 2) / (2.0 * c ** 2)))
    fr = np.where((np.abs(l2) > 0) & valid, fr, 0.0).astype(np.float32)

    det = lxx * lyy - lxy * lxy
    safe = np.abs(det) > 1e-30
    det_s = np.where(safe, det, 1.0)
    ox = np.where(safe, -(lyy * gx - lxy * gy) / det_s, np.inf)
    oy = np.where(safe, -(lxx * gy - lxy * gx) / det_s, np.inf)
    inside = (np.abs(ox) < 0.5) & (np.abs(oy) < 0.5)
    resp = np.abs(l2)
    thr = float(np.percentile(resp[valid], response_pct)) if valid.any() else np.inf
    line = inside & (l2 < 0) & (resp > thr) & valid
    return fr, line, thr


def multiscale_persistence(field: np.ndarray, valid: np.ndarray, scales=SCALES,
                           response_pct: float = 97.5):
    """Frangi max/arg-scale + Steger per-scale line count over ``scales``."""
    c = max(_hessian_norm_p99(field, scales) / 2.0, 1e-12)
    best_fr = np.zeros(field.shape, dtype=np.float32)
    best_scale = np.zeros(field.shape, dtype=np.float32)
    count = np.zeros(field.shape, dtype=np.int16)
    thresholds = {}
    for s in scales:
        fr, line, thr = _per_scale(field, s, valid, c, response_pct=response_pct)
        thresholds[str(s)] = thr
        take = fr > best_fr
        best_fr = np.where(take, fr, best_fr)
        best_scale = np.where(take, np.float32(s), best_scale)
        # 1 px correspondence tolerance: a Steger line's pixel position migrates
        # with sigma, so cross-scale persistence is counted after 3x3 dilation
        # (preregistration amendment, 2026-10-20, before any holdout number).
        line = ndimage.binary_dilation(line, structure=np.ones((3, 3), bool)) & valid
        count += line.astype(np.int16)
        del fr, line, take
    return {
        "frangi_max": best_fr,
        "frangi_scale": best_scale,
        "persist_count": count.astype(np.float32),
        "persist_gate": (count >= 2).astype(np.float32),
        "frangi_c_used": c,
        "steger_thresholds": thresholds,
    }


def rank01(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Percentile rank in [0, 1] of ``values`` over ``mask`` cells (0 outside)."""
    out = np.zeros(values.shape, dtype=np.float32)
    idx = np.flatnonzero(mask.ravel())
    if idx.size == 0:
        return out
    v = np.nan_to_num(values.ravel()[idx].astype(np.float64), nan=0.0)
    order = np.argsort(v, kind="stable")
    ranks = np.empty(idx.size, dtype=np.float64)
    ranks[order] = np.arange(idx.size, dtype=np.float64)
    # average ranks for ties
    sv = v[order]
    same = np.r_[False, sv[1:] == sv[:-1]]
    if same.any():
        # group boundaries in sorted order
        bounds = np.flatnonzero(~same)
        ends = np.r_[bounds[1:], idx.size]
        avg = (bounds + ends - 1) / 2.0
        sorted_ranks = np.repeat(avg, ends - bounds)
        ranks[order] = sorted_ranks
    out.ravel()[idx] = (ranks / max(idx.size - 1, 1)).astype(np.float32)
    return out
