"""H66 lane channels: physical scarplet aggregates + the cultural-feature veto.

Lane paragraph (verbatim requirement this module implements)
------------------------------------------------------------
"(i) scarplet template matching ... which returns amplitude, relative age, orientation and
SNR from a GeoTIFF DEM, extended with slope-aware scarp templates ...; (ii) Steger sub-pixel
ridge/valley lines ... and Frangi multiscale Hessian line measures ... at 2-20 m scales on a
slope-detrended surface.  Aggregate to 100 m cells as scarp-pixel fraction, SNR-weighted
amplitude, structure-tensor orientation coherence and dominant strike.  Mask roads, canals
and field edges with the existing cultural-feature mask, then retrain under spatial CV."

What is computable here, and the one deviation
----------------------------------------------
The competition grid is 100 m; the native-resolution evidence available *inside this
checkout for the whole footprint* is the owner-pinned 2 m LiDAR scarp stack
(``data/external/lidar_scarp_features_u8.tif``, 706/716 USGS 3DEP 1 m tiles, sidecar
``lidar_scarp_features.json``).  Its ``ex_*``/``step_max``/``lap*_max`` bands **are** the
cell-level aggregation of a slope-detrended, multi-scale LoG (Laplacian-of-Gaussian)
scarplet template response -- i.e. the Sare & Hilley / AGU-2015 slope-aware template family,
and the Frangi-type ridge measure -- already run at 2 m.  A Steger sub-pixel refinement and a
2-20 m Frangi scale sweep on 1 m pixels are therefore **not re-run on the full footprint**:
they are re-run here on the two committed 3 m pilot tiles (``scripts/e0_native_check.py``) to
verify that the 100 m aggregation preserves the ranking, and the full-footprint channel is
built from the pinned 2 m aggregates.  The deviation is recorded as IR-66-RES-01.

The cultural mask: no ``cultural-feature mask`` exists in this family's data (verified by
search -- ``grep -ri cultural`` over the pinned manifest and both data trees returns only a
prose mention in ``60GEMSDOE/registry/preregistration-h71.json``).  It is therefore built here
from geometry only, with no label input: roads, canals, field edges and mine benches are
*straight over long distances, constant in amplitude, in flat terrain, and invisible to
aeromagnetics*; a range-front or basin-boundary fault scarp is none of those at once.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage as ndi

from .spec66 import load_quant, read_bands, topo_band

# ----------------------------------------------------------------------------
# small robust helpers
# ----------------------------------------------------------------------------

def block_pctl(values: np.ndarray, valid: np.ndarray, block: int = 200,
               nbins: int = 256) -> tuple[np.ndarray, np.ndarray]:
    """Per-``block``-cell median and 1.4826*MAD of ``values`` over ``valid`` cells.

    Computed from per-block histograms (two ``bincount`` passes over the grid), which is
    what makes a 20 km-block robust estimate affordable on a 12.3 M-cell grid in a 3 GB
    sandbox; the resolution is one bin, and the bin width is returned in the diagnostics of
    the caller.  Blockwise standardisation is the family convention for the regional
    climate/lithology gradient (the 40 km blockwise median/MAD rule recorded for the
    chi-steepness lane); 20 km blocks are used here because the LiDAR tiles are 10 km.
    """
    h, w = values.shape
    ny, nx = (h + block - 1) // block, (w + block - 1) // block
    yy = np.repeat(np.arange(ny), block)[:h]
    xx = np.repeat(np.arange(nx), block)[:w]
    bid = (yy[:, None] * nx + xx[None, :]).astype(np.int32)
    # the lane's physical inputs are non-negative (slope excess, relief, coherence); the
    # histogram estimator is defined on [0, hi] and clips anything below it, which is also
    # what keeps a noisy synthetic test array from producing negative bin indices.
    v = np.clip(np.where(np.isfinite(values), values, 0.0), 0.0, None).astype(np.float32)
    nz = valid & np.isfinite(values)
    hi = float(np.quantile(v[nz], 0.995)) if nz.any() else 1.0
    hi = max(hi, 1e-6)
    bin_idx = np.minimum((v / hi * nbins).astype(np.int32), nbins - 1)
    flat = (bid * nbins + bin_idx)[nz]
    H = np.bincount(flat, minlength=ny * nx * nbins).reshape(ny * nx, nbins).astype(np.float64)
    tot = H.sum(axis=1) + 1e-12
    edges = (np.arange(nbins) + 0.5) / nbins * hi

    def wq(p: float) -> np.ndarray:
        cum = np.cumsum(H, axis=1) / tot[:, None]
        k = np.argmax(cum >= p, axis=1)
        return edges[k]

    med = wq(0.5)
    dev = np.abs(edges[None, :] - med[:, None])
    order = np.argsort(dev, axis=1)
    Hs = np.take_along_axis(H, order, axis=1).cumsum(axis=1)
    mad = np.array([dev[i, np.argmax(Hs[i] >= 0.5 * tot[i])] for i in range(H.shape[0])], np.float32)
    bad = tot <= 0
    med[bad] = 0.0
    mad[bad] = 1e-6
    return med[bid].astype(np.float32), (1.4826 * mad + 1e-6)[bid].astype(np.float32)


def robust_rank(x: np.ndarray, dom: np.ndarray) -> np.ndarray:
    """Empirical percentile rank of ``x`` within ``dom`` (0 outside)."""
    a = np.sort(np.asarray(x)[dom].astype(np.float32))
    if a.size < 16:
        return np.zeros(x.shape, np.float32)
    out = (np.searchsorted(a, x, side="right") / float(a.size)).astype(np.float32)
    out[~dom] = 0.0
    return np.clip(out, 0.0, 1.0)


def circ_windowed_strike(strike_deg: np.ndarray, weight: np.ndarray, size: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Windowed structure-tensor orientation: resultant length R and doubled-angle mean strike.

    Second-order (doubled-angle) statistics are used because a scarp line has no polarity;
    this is the same order parameter the family used for multi-physics strike agreement.
    """
    th = np.deg2rad(strike_deg) * 2.0
    w = np.where(np.isfinite(th) & np.isfinite(weight), weight, 0.0).astype(np.float32)
    cx = ndi.uniform_filter(np.nan_to_num(np.cos(th) * w, nan=0.0), size)
    cy = ndi.uniform_filter(np.nan_to_num(np.sin(th) * w, nan=0.0), size)
    ww = ndi.uniform_filter(w, size) + 1e-6
    R = np.hypot(cx, cy) / ww
    ang = 0.5 * np.arctan2(cy, cx)
    return R.astype(np.float32), np.rad2deg(ang).astype(np.float32), ww.astype(np.float32)


# ----------------------------------------------------------------------------
@dataclass
class Channels:
    """Physical scarplet channels on the 100 m grid.  All NaN off-LiDAR."""
    amp: np.ndarray          # ex_max, m/m -- scarplet amplitude (slope excess)
    step: np.ndarray         # step_max, m/m -- 10-vs-50 m slope break
    height_m: np.ndarray     # step_max * 10 m -- implied scarplet height (assumption A1)
    frac: np.ndarray         # ex_mean/ex_max -- scarp-pixel (fill) fraction within the cell
    snr: np.ndarray          # amp / blockwise background of amp (robust, unitless)
    amp_snr: np.ndarray      # SNR-weighted amplitude, m/m
    rel_age: np.ndarray      # cross / mean(downface,upface) -- Sare & Hilley relative age
    facing: np.ndarray       # (down-up)/(down+up), -1..1 -- asymmetric (dip-sense) step
    sharp: np.ndarray        # sqrt(crest convexity * toe concavity), 1/m
    coh_cell: np.ndarray     # coh100 from the stack, 0..1
    strike: np.ndarray       # dominant strike, deg (0..180)
    relief_m: np.ndarray     # cell relief, m
    lid: np.ndarray          # fraction of valid lidar samples, 0..1
    covered: np.ndarray      # bool: lidar-covered footprint cell (lid >= 0.5)


def build_channels(ext_dir, footprint: np.ndarray, lid_min: float = 0.5) -> Channels:
    """Decode the stack band-by-band and release each raw band as soon as it is consumed.

    The sandbox has 3 GB of RAM and the grid is 12.3 M cells, so holding all twelve
    float32 bands at once (588 MB) plus the derived channels would thrash.  A 3 GB-safe
    peak is ~5 live arrays.
    """
    from pathlib import Path
    import rasterio
    ext = Path(ext_dir)
    quant = load_quant(ext / "lidar_scarp_features_u8.tif")
    names = ("ex_max", "ex_mean", "step_max", "lapneg_max", "lappos_max", "downface_max",
             "upface_max", "cross_max", "relief", "coh100", "strike", "valid")
    ds = rasterio.open(ext / "lidar_scarp_features_u8.tif")
    def rd(name: str) -> np.ndarray:
        return quant[name].decode(ds.read(names.index(name) + 1))
    amp, mean = rd("ex_max"), rd("ex_mean")
    step, cross, dface, uface = rd("step_max"), rd("cross_max"), rd("downface_max"), rd("upface_max")
    lneg, lpos, relief = rd("lapneg_max"), rd("lappos_max"), rd("relief")
    coh, strike, lid = rd("coh100"), rd("strike"), rd("valid")
    ds.close()
    dom = footprint & np.isfinite(amp) & (lid >= lid_min)

    # (1) scarp-pixel fraction inside the cell: mean/max of the same quantity.
    with np.errstate(invalid="ignore", divide="ignore"):
        frac = np.clip(mean / np.maximum(amp, 1e-3), 0.0, 1.0).astype(np.float32)
    # (2) SNR-weighted amplitude: background = robust MAD of amp on the non-scarped majority.
    quiet = dom & (frac < np.nanquantile(frac[dom], 0.5))
    med, mad = block_pctl(np.nan_to_num(amp, nan=0.0), quiet)
    snr = np.clip((amp - med) / (2.0 * mad), 0.0, None).astype(np.float32)   # robust z of amp
    amp_snr = (np.nan_to_num(amp) * snr / (1.0 + snr)).astype(np.float32)
    # (3) relative age (young scarp = steep face relative to the adjacent surfaces)
    with np.errstate(invalid="ignore", divide="ignore"):
        rel_age = (cross / (0.5 * (dface + uface) + 1e-3)).astype(np.float32)
        facing = ((dface - uface) / (dface + uface + 1e-3)).astype(np.float32)
    sharp = np.sqrt(np.maximum(lneg, 0) * np.maximum(lpos, 0)).astype(np.float32)
    height_m = (np.nan_to_num(step) * 10.0).astype(np.float32)               # assumption A1
    for a in (frac, snr, amp_snr, rel_age, facing, sharp, height_m):
        a[~dom] = np.nan
    return Channels(amp=amp, step=step, height_m=height_m, frac=frac, snr=snr, amp_snr=amp_snr,
                     rel_age=rel_age, facing=facing, sharp=sharp, coh_cell=coh, strike=strike,
                     relief_m=relief, lid=lid, covered=dom)


# ----------------------------------------------------------------------------
@dataclass
class Cultural:
    index: np.ndarray        # 0..1 anthropogenic-lineament index (higher = more cultural)
    mask: np.ndarray         # bool, True = veto (roads / canals / field edges / mine benches)
    diagnostics: dict


def cultural_mask(ch: Channels, dom: np.ndarray, ext_dir, threshold_pct: float = 97.0,
                  size_km: float = 1.5, mag_lo: float = 0.5) -> Cultural:
    """Straight, amplitude-constant, flat-terrain, magnetically-invisible lineaments.

    Four independent indicators, each a percentile of the LiDAR-covered population, and a
    *conjunction* (all four must fire) so that a range-front scarp -- long and straight but
    in high relief with a magnetic offset -- is never vetoed.
    """
    from pathlib import Path
    ext = Path(ext_dir)
    # (a) long-corridor orientation coherence -> straightness
    R, ang, _ = circ_windowed_strike(np.nan_to_num(ch.strike), np.nan_to_num(ch.amp_snr), size_km * 10)
    straight = R
    # (b) amplitude constancy along the corridor: 1 - CV of amp inside the window
    win = int(size_km * 10) | 1
    m1 = ndi.uniform_filter(np.nan_to_num(ch.amp), win)
    m2 = ndi.uniform_filter(np.nan_to_num(ch.amp) ** 2, win)
    sd = np.sqrt(np.maximum(m2 - m1 * m1, 0.0))
    with np.errstate(invalid="ignore", divide="ignore"):
        const = np.clip(1.0 - sd / (m1 + 1e-3), 0.0, 1.0).astype(np.float32)
    const[~dom] = np.nan
    # (c) flat setting: low lidar relief AND low 10 m-derived local slope percentile
    relief_rank = robust_rank(np.nan_to_num(ch.relief_m), dom)
    slope_p90 = topo_band(ext / "topo_10m_derived_100m_u8.tif", "slope_p90")
    flat = np.clip(1.0 - 0.5 * relief_rank - 0.5 * slope_p90, 0.0, 1.0).astype(np.float32)
    # (d) no aeromagnetic lineament: gradient of the upward-continued TMI (percentile units)
    tmi = topo_band(ext / "geodawn_extensions_u8.tif", "TMI_up150")
    gy, gx = np.gradient(tmi)
    mag = np.hypot(gx, gy).astype(np.float32)
    mag[~np.isfinite(mag)] = 0.0
    mag_rank = robust_rank(mag, dom)

    parts = {"straight": straight, "constancy": const, "flat": flat, "mag_absent": 1.0 - mag_rank}
    idx = np.zeros(dom.shape, np.float32)
    for nm, wgt in (("straight", 0.35), ("constancy", 0.25), ("flat", 0.25), ("mag_absent", 0.15)):
        v = parts[nm]
        v = np.where(np.isfinite(v), v, 0.0)
        idx += wgt * robust_rank(v, dom)
    idx[~dom] = 0.0
    thr = float(np.quantile(idx[dom], threshold_pct / 100.0))
    veto = dom & (idx >= thr) & (idx > 0.0) & (mag_rank < mag_lo)
    diag = dict(threshold_pct=threshold_pct, threshold=thr, veto_cells=int(veto.sum()),
                veto_fraction_of_covered=float(veto.sum() / max(dom.sum(), 1)),
                indicator_pctl={nm: [round(float(np.nanquantile(np.where(dom, v, np.nan), q / 100.0)), 4)
                            for q in (50, 90, 97, 99)]
                               for nm, v in parts.items()})
    return Cultural(index=idx, mask=veto, diagnostics=diag)


# ----------------------------------------------------------------------------
def scarplet_score(ch: Channels, cul: Cultural, dom: np.ndarray) -> tuple[np.ndarray, dict]:
    """The lane's scarplet-concordance field: rank average of the four named aggregates.

    score = 0.35*rank(SNR-weighted amplitude) + 0.25*rank(scarp-pixel fraction)
          + 0.25*rank(structure-tensor coherence) + 0.15*rank(relative age),
    multiplied by (1 - cultural) as a hard veto.  No fault label enters this function.
    """
    r_amp = robust_rank(np.nan_to_num(ch.amp_snr), dom)
    r_frac = robust_rank(np.nan_to_num(ch.frac), dom)
    r_coh = robust_rank(np.nan_to_num(ch.coh_cell), dom)
    r_age = robust_rank(np.nan_to_num(ch.rel_age), dom)
    raw = 0.35 * r_amp + 0.25 * r_frac + 0.25 * r_coh + 0.15 * r_age
    kept = (~cul.mask) & dom
    s = np.where(kept, raw, 0.0).astype(np.float32)
    s[~dom] = 0.0
    info = dict(rank_components=dict(amp_snr=float(np.mean(r_amp[dom])), frac=float(np.mean(r_frac[dom])),
                                     coh=float(np.mean(r_coh[dom])), rel_age=float(np.mean(r_age[dom]))),
                n_scored=int(((s > 0) & dom).sum()), vetoed_score_mass=float(raw[cul.mask].sum()),
                total_score_mass_kept=float(s.sum()))
    return s, info
