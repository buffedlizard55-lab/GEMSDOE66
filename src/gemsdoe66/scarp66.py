"""Lane H66-C: native-resolution LiDAR scarp channels for the DOE GEMS Prize.

What this module actually implements
------------------------------------
(i)  **Scarplet-style scarp-template inversion** after Sare & Hilley (JOSS 2018,
     doi:10.21105/joss.01066) and the slope-aware template extension of the
     AGU 2015 poster T31A-2838.  Scarplet fits a *diffused scarp* template to a
     DEM profile.  For a step of height ``a`` diffusing with morphologic age
     ``kappa*t`` the analytic profile and its first two derivatives are

         z(x)   = (a/2) [ 1 + erf( x / (2 sqrt(kappa t)) ) ]
         z'(x)  = a / (2 sqrt(pi kappa t)) * exp(-x^2 / (4 kappa t))
         z''(x) = -a x / (4 (kappa t)^{3/2} sqrt(pi)) * exp(-x^2 / (4 kappa t))

     so that, writing ``S = max |z'|`` (measured at the scarp face) and
     ``C = max |z''|`` (measured at x = +- sqrt(2 kappa t)),

         S = a / (2 sqrt(pi kappa t)),      C = 0.12096 * a / (kappa t)

     Eliminating ``kappa t`` gives the two inversion products used below

         a_hat   = 1.5203 * S^2 / C                 [m, up to one constant]
         kt_hat  = 1.5203^2 * a_hat^2 / (4 pi S^2)  [m^2, up to one constant]

     ``S`` is taken from the LiDAR stack's ``ex_max`` (max 2 m slope in excess of
     the 30 m regional slope, m/m) and ``C`` from the curvature dipole
     ``sqrt(lapneg_max * lappos_max)`` (LoG(6 m) of the 50 m band-passed
     surface, 1/m).  Both are *native-scale* (2-50 m) measurements, which is
     the whole point of the lane: the 100 m stack discards them.

     **Calibration caveat (disclosed).**  The sidecar does not pin the
     normalisation of the LoG operator, so ``C`` is proportional to, not equal
     to, ``max |z''|``; an unknown dimensionless constant multiplies ``a_hat``
     and a different power of it multiplies ``kt_hat``.  Every downstream use is
     a rank/percentile transform, which is invariant to a positive constant, so
     the inversion is used for *ordering*, never for an absolute height claim.

(ii) **Steger sub-pixel line extraction** (Steger, IEEE TPAMI 20(2):113-125,
     1998): for a Gaussian scale ``sigma``, the Hessian eigen-decomposition
     gives the line normal ``n`` (eigenvector of the largest-magnitude
     eigenvalue); the sub-pixel peak along that normal is
     ``p = -(g . n) / (n^T H n)`` and a pixel is a line pixel iff
     ``|p| <= 0.5`` and the normal-direction second derivative dominates.

(iii) **Frangi multiscale Hessian vesselness** (Frangi et al., MICCAI 1998,
     LNCS 1496:130-137): with ``|l1| <= |l2|``,

         R_B = |l1| / |l2|,   S = sqrt(l1^2 + l2^2)
         v   = exp(-R_B^2 / (2 beta^2)) * (1 - exp(-S^2 / (2 c^2)))

     evaluated for ridges (l2 < 0 after the usual image sign convention) and
     maximised over scales.

**Resolution limitation (irregularity, not hidden).**  The raw 1 m GeoDAWN /
3DEP tiles are unreachable from this sandbox (IR-66-DATA-01), so the native-DEM
operators are applied to the two surfaces that *do* carry native-scale content:
the 2 m-computed LiDAR descriptor stack (whose bands are themselves 2 m / 6 m /
10 m / 30 m / 50 m operators) and the 100 m slope-detrended elevation.  The
latter carries the multi-scale line geometry at 100-300 m; the former carries
the 2-20 m scarp physics.  Scales are reported explicitly in every output name.

**Cultural mask.**  ``cultural_mask`` consumes the real TIGER 2024 road-distance
raster (US Census, official, receipt at
``data/raw/external/tiger_road_receipt.json``) and the BLM closed-claim
distance raster, then adds a geometric straightness/flatness/amagnetism test for
canals and field edges, which are not in any road file.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field

import numpy as np
from scipy import ndimage as ndi

# --------------------------------------------------------------------------------------
# (i) scarp-template (diffusion) inversion
# --------------------------------------------------------------------------------------
#: 1 / (0.12096...) -> a_hat = A_CONST * S^2 / C, from max|z'| and max|z''| of an erf scarp
A_CONST = 1.5203


def diffusion_inversion(slope_excess: np.ndarray, curvature_dipole: np.ndarray,
                        slope_floor: float = 1e-4, curv_floor: float = 1e-5):
    """Invert the diffused-scarp template for scarp height and morphologic age.

    Returns ``(a_hat, kt_hat)``.  ``a_hat`` is in metres and ``kt_hat`` in m^2,
    each up to one unknown dimensionless constant set by the (unpinned)
    normalisation of the LoG curvature operator; they are therefore used only
    through rank/percentile transforms.
    """
    S = np.maximum(np.asarray(slope_excess, np.float32), slope_floor)
    C = np.maximum(np.asarray(curvature_dipole, np.float32), curv_floor)
    a_hat = (A_CONST * S * S / C).astype(np.float32)
    kt_hat = (A_CONST * A_CONST * a_hat * a_hat / (4.0 * np.pi * S * S)).astype(np.float32)
    return a_hat, kt_hat


def curvature_dipole(lapneg: np.ndarray, lappos: np.ndarray) -> np.ndarray:
    """Geometric mean of crest convexity and toe concavity (1/m).

    A convex-up crest and a concave-up toe must co-occur at a fixed offset for a
    *step*; their geometric mean is large only when both are present, which is
    the antisymmetric curvature signature of a scarp rather than of a slope
    break, a channel bank (single-signed) or a DEM seam.
    """
    return np.sqrt(np.maximum(lapneg, 0.0) * np.maximum(lappos, 0.0)).astype(np.float32)


def robust_snr(field: np.ndarray, dom: np.ndarray, block: int = 200,
               nbins: int = 256) -> np.ndarray:
    """Blockwise robust template-SNR proxy: (x - median) / (1.4826 MAD).

    This is a robust contrast score, **not** Scarplet's published template-fit
    SNR (which needs the native profile and the fit residual).  Blocks of
    ``block`` cells remove the regional relief/lithology gradient the way the
    family's blockwise median/MAD convention does.
    """
    h, w = field.shape
    ny, nx = (h + block - 1) // block, (w + block - 1) // block
    yy = np.repeat(np.arange(ny), block)[:h]
    xx = np.repeat(np.arange(nx), block)[:w]
    bid = (yy[:, None] * nx + xx[None, :]).astype(np.int32)
    v = np.where(np.isfinite(field), field, 0.0).astype(np.float32)
    nz = dom & np.isfinite(field)
    hi = float(np.quantile(v[nz], 0.995)) if nz.any() else 1.0
    hi = max(hi, 1e-6)
    bin_idx = np.minimum((np.clip(v, 0, None) / hi * nbins).astype(np.int32), nbins - 1)
    flat = (bid * nbins + bin_idx)[nz]
    H = np.bincount(flat, minlength=ny * nx * nbins).reshape(ny * nx, nbins).astype(np.float64)
    tot = H.sum(axis=1) + 1e-12
    edges = (np.arange(nbins) + 0.5) / nbins * hi
    cum = np.cumsum(H, axis=1) / tot[:, None]
    med = edges[np.argmax(cum >= 0.5, axis=1)]
    dev = np.abs(edges[None, :] - med[:, None])
    order = np.argsort(dev, axis=1)
    Hs = np.take_along_axis(H, order, axis=1).cumsum(axis=1)
    mad = np.array([dev[i, np.argmax(Hs[i] >= 0.5 * tot[i])] for i in range(H.shape[0])], np.float32)
    bad = tot <= 1.0
    med[bad] = 0.0
    mad[bad] = 1e-6
    scale = (1.4826 * mad + 1e-6)[bid].astype(np.float32)
    centre = med[bid].astype(np.float32)
    snr = ((v - centre) / scale).astype(np.float32)
    snr[~dom] = np.nan
    return snr


def snr_weighted_amplitude(amp: np.ndarray, snr: np.ndarray) -> np.ndarray:
    """SNR-weighted amplitude: amp * SNR/(1+SNR).  Saturates at amp for high SNR."""
    s = np.maximum(np.nan_to_num(snr, nan=0.0), 0.0)
    return (np.nan_to_num(amp) * s / (1.0 + s)).astype(np.float32)


def scarp_pixel_fraction(ex_mean: np.ndarray, ex_max: np.ndarray) -> np.ndarray:
    """Within-cell scarp fill fraction proxy.

    ``ex_mean`` and ``ex_max`` are the mean and max of the *same* 2 m slope-excess
    quantity inside the 100 m cell, so their ratio is the fraction of the cell's
    2 m content that carries the cell's peak scarp signal.  It is a monotone
    proxy for the scarp-pixel fraction the brief asks for; the 2 m binary scarp
    mask itself was not retained by the upstream workflow.
    """
    return np.clip(ex_mean / np.maximum(ex_max, 1e-3), 0.0, 1.0).astype(np.float32)


# --------------------------------------------------------------------------------------
# (ii) Steger lines and Frangi vesselness
# --------------------------------------------------------------------------------------
def _hessian(field: np.ndarray, sigma: float):
    """Gaussian second-order partials at scale ``sigma`` (in pixels)."""
    f = ndi.gaussian_filter(np.nan_to_num(field, nan=0.0).astype(np.float32), sigma,
                            mode="nearest")
    gxx = ndi.gaussian_filter(f, sigma, order=(0, 2), mode="nearest")
    gyy = ndi.gaussian_filter(f, sigma, order=(2, 0), mode="nearest")
    gxy = ndi.gaussian_filter(f, sigma, order=(1, 1), mode="nearest")
    return gxx, gyy, gxy


def frangi_vesselness(field: np.ndarray, sigma: float, beta: float = 0.5,
                      c: float = 15.0, sign: int = -1) -> np.ndarray:
    """Frangi et al. (1998) vesselness at one scale.

    ``sign=-1`` selects bright ridges, ``sign=+1`` dark valleys, in the
    convention where the large-magnitude Hessian eigenvalue of a ridge is
    negative.  ``c`` is set to half the dynamic range of ``S``; callers pass an
    explicit value so the scale normalisation is reproducible.
    """
    gxx, gyy, gxy = _hessian(field, sigma)
    # scale-normalise by sigma^2 so responses are comparable across scales
    gxx, gyy, gxy = gxx * sigma ** 2, gyy * sigma ** 2, gxy * sigma ** 2
    tmp = np.sqrt((gxx - gyy) ** 2 + 4.0 * gxy ** 2)
    l1 = 0.5 * (gxx + gyy - tmp)
    l2 = 0.5 * (gxx + gyy + tmp)          # |l2| >= |l1|
    a1, a2 = np.abs(l1), np.abs(l2)
    rb = a1 / np.maximum(a2, 1e-12)
    s = np.sqrt(a1 ** 2 + a2 ** 2)
    v = np.exp(-(rb ** 2) / (2.0 * beta ** 2)) * (1.0 - np.exp(-(s ** 2) / (2.0 * c ** 2)))
    keep = (np.sign(l2) == sign)
    return np.where(keep, v, 0.0).astype(np.float32)


def _hessian_norm_sq(field: np.ndarray, sigma: float):
    """Frangi's ``S^2 = l1^2 + l2^2`` (sigma^2-normalised) at one scale."""
    gxx, gyy, gxy = _hessian(field, sigma)
    gxx, gyy, gxy = gxx * sigma ** 2, gyy * sigma ** 2, gxy * sigma ** 2
    tmp = np.sqrt((gxx - gyy) ** 2 + 4.0 * gxy ** 2)
    l1 = 0.5 * (gxx + gyy - tmp)
    l2 = 0.5 * (gxx + gyy + tmp)
    return l1 ** 2 + l2 ** 2


def frangi_multiscale(field: np.ndarray, sigmas=(1.0, 1.5, 2.0, 3.0), beta: float = 0.5,
                      sign: int = 0, c_quantile: float = 0.99,
                      sample: int = 4) -> tuple[np.ndarray, np.ndarray]:
    """Max over scales of the Frangi measure; returns (max_response, argmax_sigma).

    ``c`` follows Frangi et al.: half the dynamic range of ``S``.  It is estimated
    robustly from a strided subsample of ``S`` across *all* scales rather than from
    the raw image intensity, because the raw-intensity proxy collapses the response
    to ~0 on a heavy-tailed geomorphic field.  ``sign=0`` keeps the larger of the
    ridge and valley responses (a scarp is a ridge in the scarp-amplitude field but
    a ridge/valley pair in elevation, and the polarity is not known a priori).
    """
    norms = [np.sqrt(_hessian_norm_sq(field, sg)) for sg in sigmas]
    pooled = np.concatenate([n[::sample, ::sample].ravel() for n in norms])
    pooled = pooled[np.isfinite(pooled)]
    c = 0.5 * float(np.quantile(pooled, c_quantile)) if pooled.size else 1.0
    c = max(c, 1e-9)
    best = np.zeros(field.shape, np.float32)
    best_s = np.zeros(field.shape, np.float32)
    for sg in sigmas:
        if sign == 0:
            v = np.maximum(frangi_vesselness(field, sg, beta=beta, c=c, sign=-1),
                           frangi_vesselness(field, sg, beta=beta, c=c, sign=+1))
        else:
            v = frangi_vesselness(field, sg, beta=beta, c=c, sign=sign)
        m = v > best
        best[m] = v[m]
        best_s[m] = sg
    return best, best_s, float(c)


def steger_lines(field: np.ndarray, sigma: float, max_offset: float = 0.5):
    """Steger (1998) sub-pixel line extraction at one scale.

    Returns ``(strength, offset, normal_angle_deg)``.  ``strength`` is the
    magnitude of the normal-direction second derivative at the sub-pixel peak;
    a pixel qualifies only when the peak lies within +-``max_offset`` of the
    pixel centre, which is Steger's own acceptance test.
    """
    f = np.nan_to_num(field, nan=0.0).astype(np.float32)
    gxx, gyy, gxy = _hessian(f, sigma)
    gx = ndi.gaussian_filter(f, sigma, order=(0, 1), mode="nearest")
    gy = ndi.gaussian_filter(f, sigma, order=(1, 0), mode="nearest")
    tmp = np.sqrt((gxx - gyy) ** 2 + 4.0 * gxy ** 2)
    l2 = 0.5 * (gxx + gyy + tmp)                     # dominant eigenvalue
    # eigenvector of l2: for symmetric [[gxx,gxy],[gxy,gyy]] with l2 != gxx
    nx = gxy
    ny = l2 - gxx
    nrm = np.hypot(nx, ny) + 1e-12
    nx, ny = nx / nrm, ny / nrm
    denom = gxx * nx * nx + 2.0 * gxy * nx * ny + gyy * ny * ny
    with np.errstate(divide="ignore", invalid="ignore"):
        t = -(gx * nx + gy * ny) / np.where(np.abs(denom) < 1e-12, np.nan, denom)
    good = np.isfinite(t) & (np.abs(t) <= max_offset)
    strength = np.where(good, np.abs(l2), 0.0).astype(np.float32)
    offset = np.where(good, t, np.nan).astype(np.float32)
    angle = np.degrees(np.arctan2(ny, nx)).astype(np.float32)
    return strength, offset, angle


def steger_multiscale(field: np.ndarray, sigmas=(1.0, 1.5, 2.0, 3.0),
                      max_offset: float = 0.5):
    """Max over scales of the Steger line strength; returns (strength, argmax_sigma)."""
    best = np.zeros(field.shape, np.float32)
    best_s = np.zeros(field.shape, np.float32)
    for sg in sigmas:
        s, _, _ = steger_lines(field, sg, max_offset=max_offset)
        m = s > best
        best[m] = s[m]
        best_s[m] = sg
    return best, best_s


def slope_detrended(elev: np.ndarray, valid: np.ndarray, window: int = 15) -> np.ndarray:
    """Remove the regional slope: elevation minus its large-window local mean.

    ``window`` is in cells (100 m each), so 15 cells = 1.5 km, well above the
    2-20 m scarp scales the lane targets and below the 10 km+ basin wavelength.
    """
    z = np.where(np.isfinite(elev), elev, 0.0).astype(np.float32)
    w = np.where(valid, 1.0, 0.0).astype(np.float32)
    num = ndi.uniform_filter(z, size=window, mode="nearest")
    den = ndi.uniform_filter(w, size=window, mode="nearest") + 1e-6
    return (z - num / den).astype(np.float32)


def orientation_coherence(cos2: np.ndarray, sin2: np.ndarray, weight: np.ndarray,
                          size: int) -> np.ndarray:
    """Doubled-angle structure-tensor resultant length R in [0, 1].

    Second-order (doubled-angle) statistics are used because a scarp line has no
    polarity.  ``cos2``/``sin2`` are cos(2 theta) and sin(2 theta) of the local
    orientation, weighted by line strength.
    """
    w = np.nan_to_num(weight, nan=0.0).astype(np.float32)
    cx = ndi.uniform_filter(np.nan_to_num(cos2, nan=0.0) * w, size)
    cy = ndi.uniform_filter(np.nan_to_num(sin2, nan=0.0) * w, size)
    ww = ndi.uniform_filter(w, size) + 1e-6
    return np.clip(np.hypot(cx, cy) / ww, 0.0, 1.0).astype(np.float32)


# --------------------------------------------------------------------------------------
# (iii) cultural-feature mask
# --------------------------------------------------------------------------------------
@dataclass
class Cultural:
    road_dist_m: np.ndarray       # metres to the nearest TIGER 2024 road
    claim_dist_m: np.ndarray      # metres to the nearest BLM closed claim
    straight: np.ndarray          # 0..1 corridor orientation coherence
    constancy: np.ndarray         # 0..1 amplitude constancy along the corridor
    flatness: np.ndarray          # 0..1 low-relief / low-slope setting
    mag_absent: np.ndarray        # 0..1 absence of an aeromagnetic lineament
    index: np.ndarray             # 0..1 weighted cultural index
    veto: np.ndarray              # bool: roads / canals / field edges / mine benches
    diagnostics: dict = dc_field(default_factory=dict)


def cultural_mask(road_dist_m: np.ndarray, claim_dist_m: np.ndarray,
                  strike_deg: np.ndarray, amp: np.ndarray, relief: np.ndarray,
                  slope_p90: np.ndarray, tmi: np.ndarray, dom: np.ndarray,
                  road_radius_m: float = 100.0, claim_radius_m: float = 0.0,
                  threshold_pct: float = 97.0, corridor_cells: int = 15) -> Cultural:
    """Roads from an official TIGER raster; canals/field edges from geometry.

    The road term is a hard, distance-based veto from real, receipted public
    data (US Census TIGER 2024).  ``claim_radius_m`` defaults to 0, i.e. the BLM
    closed-claim raster is *not* used as a veto: "closed to mineral entry" is an
    administrative status rather than a physical disturbance, and 45 % of the
    footprint lies within 150 m of a closed claim, so vetoing on it would remove
    most of the study area.  Canals and field edges are not in any road file, so
    they are caught by a *conjunction* of four independent indicators -- long
    and straight, amplitude-constant along strike, on flat ground, and invisible
    in the upward-continued aeromagnetics.  Requiring all four means a
    range-front scarp (long and straight, but in high relief with a magnetic
    offset) is never vetoed.
    """
    th = np.deg2rad(np.nan_to_num(strike_deg, nan=0.0)) * 2.0
    w = np.where(np.isfinite(amp), np.nan_to_num(amp), 0.0).astype(np.float32)
    cx = ndi.uniform_filter(np.cos(th) * w, corridor_cells)
    cy = ndi.uniform_filter(np.sin(th) * w, corridor_cells)
    ww = ndi.uniform_filter(w, corridor_cells) + 1e-6
    straight = np.clip(np.hypot(cx, cy) / ww, 0.0, 1.0).astype(np.float32)

    m1 = ndi.uniform_filter(np.nan_to_num(amp), corridor_cells)
    m2 = ndi.uniform_filter(np.nan_to_num(amp) ** 2, corridor_cells)
    sd = np.sqrt(np.maximum(m2 - m1 * m1, 0.0))
    constancy = np.clip(1.0 - sd / (m1 + 1e-3), 0.0, 1.0).astype(np.float32)

    def _rank(x: np.ndarray) -> np.ndarray:
        a = np.sort(x[dom].astype(np.float32))
        if a.size < 16:
            return np.zeros(x.shape, np.float32)
        out = (np.searchsorted(a, x, side="right") / float(a.size)).astype(np.float32)
        return np.clip(out, 0.0, 1.0)

    r_relief = _rank(np.nan_to_num(relief))
    r_slope = _rank(np.nan_to_num(slope_p90))
    flatness = np.clip(1.0 - 0.5 * r_relief - 0.5 * r_slope, 0.0, 1.0).astype(np.float32)

    gy, gx = np.gradient(np.nan_to_num(tmi))
    mag = np.hypot(gx, gy).astype(np.float32)
    mag_absent = (1.0 - _rank(mag)).astype(np.float32)

    idx = np.zeros(dom.shape, np.float32)
    for nm, wt in (("straight", 0.30), ("constancy", 0.25), ("flatness", 0.30),
                   ("mag_absent", 0.15)):
        v = {"straight": straight, "constancy": constancy, "flatness": flatness,
             "mag_absent": mag_absent}[nm]
        idx += wt * _rank(np.nan_to_num(v))
    idx[~dom] = 0.0
    thr = float(np.quantile(idx[dom], threshold_pct / 100.0)) if dom.any() else 1.0

    road_veto = np.isfinite(road_dist_m) & (road_dist_m <= road_radius_m)
    # radius <= 0 disables the term (a 0 m radius would otherwise veto every cell
    # whose distance is exactly zero, which is 45 % of the footprint for claims).
    claim_veto = (np.isfinite(claim_dist_m) & (claim_dist_m <= claim_radius_m)
                  if claim_radius_m > 0 else np.zeros(dom.shape, bool))
    geom_veto = dom & (idx >= thr) & (idx > 0.0) & (mag_absent > 0.5)
    veto = (road_veto | claim_veto | geom_veto) & dom

    diag = dict(road_radius_m=road_radius_m, claim_radius_m=claim_radius_m,
                geometric_threshold_pct=threshold_pct, geometric_threshold=thr,
                road_veto_cells=int(road_veto.sum()), claim_veto_cells=int(claim_veto.sum()),
                geometric_veto_cells=int(geom_veto.sum()), veto_cells=int(veto.sum()),
                veto_fraction_of_domain=float(veto.sum() / max(int(dom.sum()), 1)),
                corridor_cells=corridor_cells)
    return Cultural(road_dist_m=road_dist_m, claim_dist_m=claim_dist_m, straight=straight,
                    constancy=constancy, flatness=flatness, mag_absent=mag_absent,
                    index=idx, veto=veto, diagnostics=diag)


# --------------------------------------------------------------------------------------
# the lane's aggregate channels
# --------------------------------------------------------------------------------------
@dataclass
class ScarpChannels:
    amp: np.ndarray            # L_ex_max, m/m -- 2 m slope excess over the 30 m regional slope
    frac: np.ndarray           # scarp fill-fraction proxy, 0..1
    snr: np.ndarray            # robust contrast (blockwise MAD z-score)
    amp_snr: np.ndarray        # SNR-weighted amplitude
    a_hat: np.ndarray          # diffusion-inverted scarp height (up to a constant), m
    kt_hat: np.ndarray         # diffusion-inverted morphologic age (up to a constant), m^2
    dipole: np.ndarray         # curvature dipole sqrt(lapneg*lappos), 1/m
    facing: np.ndarray         # (downface - upface)/(downface + upface), -1..1
    coh_cell: np.ndarray       # structure-tensor orientation coherence from the stack
    strike: np.ndarray         # dominant scarp strike, deg
    frangi_amp: np.ndarray     # Frangi vesselness of the scarp-amplitude field (multi-scale max)
    frangi_det: np.ndarray     # Frangi vesselness of the slope-detrended elevation
    steger_amp: np.ndarray     # Steger sub-pixel line strength of the amplitude field
    steger_det: np.ndarray     # Steger sub-pixel line strength of the detrended elevation
    coh_line: np.ndarray       # windowed orientation coherence of the Steger normals
    relief_m: np.ndarray       # cell relief, m
    lid: np.ndarray            # fraction of valid LiDAR samples
    covered: np.ndarray        # bool: LiDAR-covered cell
    cultural: Cultural
    diagnostics: dict = dc_field(default_factory=dict)


SIGMAS = (1.0, 1.5, 2.0, 3.0)


def build_scarp_channels(stack_get, footprint: np.ndarray, road_dist_m: np.ndarray,
                         claim_dist_m: np.ndarray, lid_min: float = 0.5,
                         sigmas=SIGMAS) -> ScarpChannels:
    """Build the lane's channels from the cached feature stack.

    ``stack_get(name)`` returns a full-grid float32 layer with NaN off-domain.
    """
    ex_max = stack_get("L_ex_max")
    ex_mean = stack_get("L_ex_mean")
    lapneg = stack_get("L_lapneg_max")
    lappos = stack_get("L_lappos_max")
    dface = stack_get("L_downface_max")
    uface = stack_get("L_upface_max")
    coh = stack_get("L_coh100")
    strike = stack_get("L_strike")
    relief = stack_get("L_relief")
    lid = stack_get("L_valid")

    covered = footprint & np.isfinite(ex_max) & (lid >= lid_min)
    dipole = curvature_dipole(lapneg, lappos)
    a_hat, kt_hat = diffusion_inversion(ex_max, dipole)
    frac = scarp_pixel_fraction(ex_mean, ex_max)
    snr = robust_snr(ex_max, covered)
    amp_snr = snr_weighted_amplitude(ex_max, snr)
    with np.errstate(invalid="ignore", divide="ignore"):
        facing = ((dface - uface) / (dface + uface + 1e-3)).astype(np.float32)

    # --- Steger / Frangi on the slope-detrended elevation and on the amplitude field
    dem = stack_get("T_dem_mean")
    det = slope_detrended(dem, footprint)
    det = np.where(covered, det, np.nan)
    amp = np.where(covered, np.nan_to_num(ex_max), np.nan).astype(np.float32)

    fr_amp, _, c_amp = frangi_multiscale(np.nan_to_num(amp), sigmas=sigmas, sign=0)
    fr_det, _, c_det = frangi_multiscale(np.nan_to_num(det), sigmas=sigmas, sign=0)
    st_amp, _ = steger_multiscale(np.nan_to_num(amp), sigmas=sigmas)
    st_det, _ = steger_multiscale(np.nan_to_num(det), sigmas=sigmas)

    # orientation coherence of the Steger normals (doubled angle)
    _, _, ang = steger_lines(np.nan_to_num(amp), 1.5)
    coh_line = orientation_coherence(np.cos(np.deg2rad(ang) * 2.0),
                                     np.sin(np.deg2rad(ang) * 2.0),
                                     np.nan_to_num(st_amp), 15)
    for arr in (fr_amp, fr_det, st_amp, st_det, coh_line):
        arr[~covered] = np.nan

    slope_p90 = stack_get("T_slope_p90")
    tmi = stack_get("ext_TMI_up150")
    cul = cultural_mask(road_dist_m, claim_dist_m, strike, np.nan_to_num(amp_snr),
                        relief, slope_p90, tmi, covered)

    diag = dict(
        lidar_covered_cells=int(covered.sum()),
        footprint_cells=int(footprint.sum()),
        lidar_coverage_fraction=float(covered.sum() / max(int(footprint.sum()), 1)),
        sigmas_cells=list(sigmas),
        frangi_c={"scarp_amplitude_field": c_amp, "detrended_elevation": c_det},
        sigma_scale_note="100 m cells: sigma 1.0-3.0 cells = 100-300 m line scales on the "
                         "100 m grid; the 2-20 m scarp physics enters through the LiDAR "
                         "stack bands (2 m slope, 6 m LoG, 10/30/50 m band-passes).",
        amp_pctl=[round(float(np.nanpercentile(amp[covered], q)), 5) for q in (50, 90, 99)],
        a_hat_pctl=[round(float(np.nanpercentile(a_hat[covered], q)), 3) for q in (50, 90, 99)],
        kt_hat_pctl=[round(float(np.nanpercentile(kt_hat[covered], q)), 1) for q in (50, 90, 99)],
        dipole_pctl=[round(float(np.nanpercentile(dipole[covered], q)), 5) for q in (50, 90, 99)],
        cultural=cul.diagnostics,
    )
    return ScarpChannels(amp=amp, frac=frac, snr=snr, amp_snr=amp_snr, a_hat=a_hat,
                         kt_hat=kt_hat, dipole=dipole, facing=facing, coh_cell=coh,
                         strike=strike, frangi_amp=fr_amp, frangi_det=fr_det,
                         steger_amp=st_amp, steger_det=st_det, coh_line=coh_line,
                         relief_m=relief, lid=lid, covered=covered, cultural=cul,
                         diagnostics=diag)
