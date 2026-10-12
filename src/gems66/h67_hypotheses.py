"""H67 candidate hypothesis surfaces - native-resolution LiDAR scarp channels.

Five candidates, each a full-grid float32 surface (higher = more likely to be a fault
scarp that the public catalogue misses).  None of them uses fault-inventory layers as
features (leakage discipline of ``gemsdoe66.fields``); the only non-geophysical input is
the *geometry* of the given catalogue (a distance prior), which the organiser provides
and the incumbent family already uses in its emission geometry.

Physical signatures targeted (layer sources in parentheses)
-----------------------------------------------------------
H67-A flank_scgate     catalogue-flank habitat x scarp-channel gate (step, coherence,
                       dip-sense persistence).  Sibling/stepover faults live 200-800 m
                       from the mapped trace; the gate keeps only places where a native
                       1 m-resolution slope-break with coherent dip sense actually exists.
H67-B young_scarp      young-scarp band: scarplet amplitude with a 10 vs 50 m slope
                       break (height 0.3-3 m), crest-toe sharpness, coherence, in
                       gentle relief - the "easiest to miss" band of the recent
                       normal-fault population.
H67-C persistence      along-strike scarp persistence: fraction of a 2 km / 5 km
                       along-strike corridor carrying scarp amplitude above the p90,
                       times corridor amplitude.  Fault scarps persist over km scales;
                       isolated steps (channels, mines, cuts) do not.
H67-D bimodal_x        strike bimodality: two coherent scarp directions >= 20 deg apart
                       within 5 km (X-junctions, relay/stepover zones) carrying
                       slope-break amplitude.
H67-E mag_offset       scarp x aeromagnetic offset coupling: slope-break amplitude where
                       the smoothed TMI gradient crosses the scarp strike near 90 deg -
                       the signature of a fault that displaced a magnetic body.

Controls that every surface carries: lidar coverage domain, TIGER-road veto, BLM-claim
soft penalty, zero dots within 200 m of the catalogue (applied at emission).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage as ndi

from .h67_layers import Layers, emission_domain

N_BINS = 36          # doubled-angle bins over 180 deg
CORR_KM = (2.0, 5.0) # persistence corridor half-lengths


def rank01(x: np.ndarray, dom: np.ndarray) -> np.ndarray:
    """Empirical percentile rank of ``x`` over ``dom``; 0 elsewhere."""
    a = np.sort(x[dom & np.isfinite(x)].astype(np.float32))
    if a.size < 16:
        return np.zeros(x.shape, np.float32)
    out = np.searchsorted(a, x, side="right").astype(np.float32) / a.size
    out[~(dom & np.isfinite(x))] = 0.0
    return out


def _wmean(x: np.ndarray, w: np.ndarray, size: int) -> tuple[np.ndarray, np.ndarray]:
    """Weighted windowed mean of scalar ``x`` with weights ``w`` (both NaN-safe)."""
    xx = np.nan_to_num(x, nan=0.0) * np.nan_to_num(w, nan=0.0)
    ww = np.nan_to_num(w, nan=0.0)
    s = ndi.uniform_filter(xx, size)
    sw = ndi.uniform_filter(ww, size)
    with np.errstate(invalid="ignore", divide="ignore"):
        m = s / np.maximum(sw, 1e-6)
    m[sw < 1e-6] = np.nan
    return m, sw


def facing_persistence(L: Layers, dom: np.ndarray, km: float = 3.0) -> np.ndarray:
    """Mean dip-sense along a ~``km`` corridor (strike-agnostic disc proxy).

    ``|mean(facing * step)| / mean(step)``: a scarp whose dip sense is coherent over
    kilometres (a fault's hanging wall) scores 1; random or opposing steps score 0.
    """
    size = int(km * 10) | 1
    m, sw = _wmean(L.facing, L.step, size)
    s2, _ = _wmean(np.ones_like(L.step), L.step, size)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.abs(m) / np.maximum(s2, 1e-3)
    out[~dom | ~np.isfinite(out) | (sw < 1e-6)] = np.nan
    return out.astype(np.float32)


def corridor_stats(L: Layers, dom: np.ndarray) -> dict:
    """Along-strike corridor statistics via directional walks on the strike field.

    At each pixel we walk +/- ``km`` along the local strike in 100 m steps and record the
    mean scarp amplitude and the fraction of corridor samples above the domain p90.
    Returns a dict of ``(mean_amp, frac_above)`` arrays keyed by corridor half-length.
    Memory: int32 index arrays and float32 accumulators only.
    """
    th = np.deg2rad(np.nan_to_num(L.strike, nan=0.0)).astype(np.float32)
    dx = np.cos(th).astype(np.float32)
    dy = (-np.sin(th)).astype(np.float32)   # raster y grows south
    amp = np.where(dom & np.isfinite(L.amp), L.amp, np.nan)
    a = amp[dom & np.isfinite(amp)]
    thr = float(np.nanpercentile(a, 90)) if a.size else np.nan
    H, W = dom.shape
    rows = np.tile(np.arange(H, dtype=np.int32)[:, None], (1, W))
    cols = np.tile(np.arange(W, dtype=np.int32)[None, :], (H, 1))
    out = {}
    H, W = dom.shape
    for km in CORR_KM:
        steps = int(km * 10)
        sums = np.zeros((2, H, W), np.float32)
        cnts = np.zeros((2, H, W), np.float32)
        abv = np.zeros((2, H, W), np.float32)
        for s in range(1, steps + 1):
            r1 = np.clip((rows + np.round(dy * s)).astype(np.int32), 0, H - 1)
            c1 = np.clip((cols + np.round(dx * s)).astype(np.int32), 0, W - 1)
            r0 = np.clip((rows - np.round(dy * s)).astype(np.int32), 0, H - 1)
            c0 = np.clip((cols - np.round(dx * s)).astype(np.int32), 0, W - 1)
            v1 = amp[r1, c1]
            v0 = amp[r0, c0]
            f1 = np.isfinite(v1)
            f0 = np.isfinite(v0)
            sums[0] += np.where(f1, v1, 0.0)
            sums[1] += np.where(f0, v0, 0.0)
            cnts[0] += f1.astype(np.float32)
            cnts[1] += f0.astype(np.float32)
            abv[0] += (f1 & (v1 > thr)).astype(np.float32)
            abv[1] += (f0 & (v0 > thr)).astype(np.float32)
            del v1, v0, f1, f0, r1, c1, r0, c0
        total = cnts[0] + cnts[1]
        with np.errstate(invalid="ignore", divide="ignore"):
            mean_amp = (sums[0] + sums[1]) / np.maximum(total, 1.0)
            frac_above = (abv[0] + abv[1]) / np.maximum(total, 1.0)
        mean_amp[total < 0.5 * steps] = np.nan
        frac_above[total < 0.5 * steps] = np.nan
        mean_amp[~dom] = np.nan
        frac_above[~dom] = np.nan
        out[km] = (mean_amp, frac_above)
        del sums, cnts, abv, total
    return out


def _bimodality(L: Layers, dom: np.ndarray, km: float = 5.0) -> np.ndarray:
    """1 - dominant doubled-angle share within a ``km`` disc, with a peak-separation test.

    Memory-safe: a single (N,) top-1/top-2 running update per bin pass; no (36, N) array.
    """
    size = int(km * 10) | 1
    shape = dom.shape
    th2 = (np.deg2rad(np.nan_to_num(L.strike, nan=0.0)) * 2.0).astype(np.float32).ravel()
    w = np.where(dom & np.isfinite(L.step), L.step, 0.0).astype(np.float32).ravel()
    ww = ndi.uniform_filter(w.reshape(shape), size).ravel()
    top1_v = np.zeros(L.fp.size, np.float32)
    top2_v = np.zeros(L.fp.size, np.float32)
    top1_i = np.zeros(L.fp.size, np.int8)
    top2_i = np.zeros(L.fp.size, np.int8)
    for b in range(N_BINS):
        lo = 2 * np.pi * b / N_BINS
        hi = 2 * np.pi * (b + 1) / N_BINS
        m = ((th2 >= lo) & (th2 < hi)).astype(np.float32) * w
        binw = ndi.uniform_filter(m, size)
        share = (binw / np.maximum(ww, 1e-9)).astype(np.float32)
        better = share > top1_v
        mid = ~better & (share > top2_v)
        top2_v = np.where(better, top1_v, np.where(mid, share, top2_v))
        top2_i = np.where(better, top1_i, np.where(mid, b, top2_i))
        top1_v = np.where(better, share, top1_v)
        top1_i = np.where(better, b, top1_i)
        del m, binw, share
    dd = (top1_i.astype(np.int32) - top2_i.astype(np.int32) + N_BINS) % N_BINS
    dd = np.minimum(dd, N_BINS - dd)
    sep_deg = dd * (180.0 / N_BINS)
    bim = np.where((top1_v < 0.55) & (top2_v > 0.12) & (sep_deg >= 20.0),
                   (1.0 - top1_v), 0.0)
    bim = bim.reshape(shape)
    bim[~dom | (ww.reshape(shape) < 1e-6)] = np.nan
    return bim.astype(np.float32)


@dataclass
class Surfaces:
    dom: np.ndarray
    flank_scgate: np.ndarray
    young_scarp: np.ndarray
    persistence: np.ndarray
    bimodal_x: np.ndarray
    mag_offset: np.ndarray
    meta: dict


def build_surfaces(L: Layers, claim_soft_m: float = 250.0) -> Surfaces:
    dom = emission_domain(L)
    claim_pen = 0.5 * (L.claim_m < claim_soft_m).astype(np.float32)

    fp_p = facing_persistence(L, dom, 3.0)

    # -- H67-A: catalogue-flank habitat x scarp-channel gate ---------------------
    dcat = L.dcat_px
    flank = np.zeros(L.fp.shape, np.float32)
    ring = dom & (dcat >= 2.0) & (dcat <= 8.0)
    flank[ring] = np.exp(-(dcat[ring] - 2.0) / 5.0)
    # rank INSIDE the ring only; outside the ring the prior is exactly zero
    r_flank = rank01(flank, ring)
    r_flank[~ring] = 0.0
    r_step = rank01(L.step, dom)
    r_coh = rank01(L.coh, dom)
    r_face = rank01(fp_p, dom)
    A = (r_flank * r_step * r_coh * r_face * (1.0 - claim_pen)).astype(np.float32)
    A[~dom] = np.nan

    # -- H67-B: young-scarp band --------------------------------------------------
    rel_hi = float(np.nanpercentile(L.relief[dom & np.isfinite(L.relief)], 75))
    band = ((L.height >= 0.3) & (L.height <= 3.0) & (L.relief <= rel_hi)).astype(np.float32)
    # robust SNR of the amplitude (block-free: global robust z on the quiet majority)
    quiet = dom & np.isfinite(L.amp) & (L.amp <= np.nanpercentile(L.amp[dom & np.isfinite(L.amp)], 50))
    med = float(np.nanmedian(L.amp[quiet])) if quiet.any() else 0.0
    mad = 1.4826 * float(np.nanmedian(np.abs(L.amp[quiet] - med))) if quiet.any() else 1.0
    snr = np.clip((L.amp - med) / max(2.0 * mad, 1e-6), 0.0, None).astype(np.float32)
    r_amp_snr = rank01(snr, dom)
    r_sharp = rank01(L.sharp, dom)
    B = (r_amp_snr * r_sharp * r_coh * band * r_face * (1.0 - claim_pen)).astype(np.float32)
    B[~dom] = np.nan

    # -- H67-C: along-strike persistence ------------------------------------------
    corr = corridor_stats(L, dom)
    m2, f2 = corr[2.0]
    m5, f5 = corr[5.0]
    persist = np.minimum(f2, f5)
    r_pers = rank01(persist, dom)
    r_ml = rank01(np.minimum(np.nan_to_num(m2, nan=0.0), np.nan_to_num(m5, nan=0.0)), dom)
    C = (r_pers * r_ml * r_coh * (1.0 - claim_pen)).astype(np.float32)
    C[~dom] = np.nan

    # -- H67-D: strike bimodality ---------------------------------------------------
    bim = _bimodality(L, dom, 5.0)
    r_bim = rank01(bim, dom)
    D = (r_bim * r_step * r_face * (1.0 - claim_pen)).astype(np.float32)
    D[~dom] = np.nan

    # -- H67-E: magnetic-offset coupling --------------------------------------------
    from scipy.ndimage import gaussian_filter
    tmi_sm = gaussian_filter(np.nan_to_num(L.tmi, nan=0.0), 6.0, mode="nearest")
    gy, gx = np.gradient(tmi_sm)
    az = np.arctan2(-gy, gx)                       # azimuth of steepest ascent
    th_r = np.deg2rad(np.nan_to_num(L.strike, nan=0.0))
    cross_term = np.abs(np.sin(az - th_r))          # 1 when gradient crosses the scarp
    r_g = rank01(np.hypot(gx, gy), dom)
    E = (r_step * r_g * cross_term * r_face * (1.0 - claim_pen)).astype(np.float32)
    E[~dom] = np.nan

    meta = {"dom_cells": int(dom.sum()), "relief_p75_m": rel_hi,
            "amp_p50_m_m": float(np.nanmedian(L.amp[dom & np.isfinite(L.amp)])) if dom.any() else None,
            "claim_soft_m": claim_soft_m}
    return Surfaces(dom=dom, flank_scgate=A, young_scarp=B, persistence=C,
                    bimodal_x=D, mag_offset=E, meta=meta)


NAMES = ("flank_scgate", "young_scarp", "persistence", "bimodal_x", "mag_offset")
