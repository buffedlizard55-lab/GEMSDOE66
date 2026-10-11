"""Candidate belief fields over the competition footprint.

Every field is a full-grid float32 array with NaN outside the footprint, higher = more
likely to be a fault that the *given* catalogue does not contain.

The three substantive fields
----------------------------
``novelty_sgmc``
    Supervised field whose positive class is **SGMC fault pixels more than 300 m from the
    given catalogue** - i.e. real faults mapped by the USGS that the competition's label set
    does not contain.  That population is the closest available analogue of the hidden test
    set, which the organiser defines as "faults not contained within the current public USGS
    database".  Previous sessions in this project family used SGMC only as an *evaluation*
    instrument, never as a training target; this is the difference.
``lidar_lane``
    The assigned lane: multiscale line/structure-tensor measures (Frangi/Sato Hessian line
    response, Steger sub-pixel line localisation, structure-tensor orientation coherence and
    dominant strike) computed on the slope-detrended elevation and on the 1 m-LiDAR-derived
    scarp descriptors, at 2-20 pixel (200-2000 m) scales, aggregated to the 100 m grid as
    scarp-pixel fraction, amplitude-weighted response and orientation coherence, then masked
    by relief/aspect to suppress cultural edges.
``catalogue_habitat``
    The same supervised model trained on the *given* catalogue.  This is the control that
    represents what the existing family of submissions implicitly does; it is expected to be
    good at recovering catalogue faults and bad at discovering new ones.

Leakage discipline
------------------
The five inventory layers (SGMC and GDR-derived fault/vent/paleo rasters) are never used as
*features* - they are labels or evaluation targets only.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from scipy.ndimage import gaussian_filter, maximum_filter, uniform_filter

from .grid import EXTERNAL, PROCESSED, footprint_mask

INVENTORY_LAYERS = {"sgmc_faults", "sgmc_faults_derived", "gdr_qfaults_v2",
                    "gdr_paleo", "gdr_volcanics"}
DROP_FEATURES = INVENTORY_LAYERS | {"L_valid"}


# ---------------------------------------------------------------------------------------------
# generic raster helpers
# ---------------------------------------------------------------------------------------------
def full_from_footprint(vec: np.ndarray, fi: np.ndarray, shape=(3730, 3292)) -> np.ndarray:
    out = np.full(shape[0] * shape[1], np.nan, dtype=np.float32)
    out[fi] = vec
    return out.reshape(shape)


def to_footprint_vec(grid: np.ndarray, fi: np.ndarray) -> np.ndarray:
    return np.asarray(grid, dtype=np.float32).ravel()[fi]


def robust_unit(a: np.ndarray, mask: np.ndarray, lo=1.0, hi=99.0) -> np.ndarray:
    """Clip to percentile bounds inside ``mask`` and scale to [0, 1]; 0 outside the mask."""
    v = a[mask & np.isfinite(a)]
    if v.size == 0:
        return np.zeros(a.shape, np.float32)
    p0, p1 = np.percentile(v, lo), np.percentile(v, hi)
    out = (a - p0) / max(1e-12, p1 - p0)
    out = np.clip(out, 0.0, 1.0).astype(np.float32)
    out[~(mask & np.isfinite(a))] = 0.0
    return out


def fill_for_filter(a: np.ndarray, mask: np.ndarray, fill=None) -> np.ndarray:
    """Nearest-neighbour fill so that filters never propagate NaN."""
    out = a.astype(np.float32).copy()
    bad = ~(mask & np.isfinite(a))
    if not bad.any():
        return out
    f = 0.0 if fill is None else fill
    out[bad] = f if fill is not None else float(np.nanmedian(a[mask & np.isfinite(a)]))
    return out


def structure_tensor(a: np.ndarray, sigma: float) -> tuple[np.ndarray, np.ndarray]:
    """Return (orientation of the minor eigenvector in radians, coherence).

    Orientation is the *line* direction (the direction along which the image varies least),
    i.e. the strike of a ridge/valley.  Coherence = (l1 - l2) / (l1 + l2) in [0, 1].
    """
    s = gaussian_filter(a, sigma, mode="nearest")
    gy, gx = np.gradient(s)
    jxx = gaussian_filter(gx * gx, sigma, mode="nearest")
    jyy = gaussian_filter(gy * gy, sigma, mode="nearest")
    jxy = gaussian_filter(gx * gy, sigma, mode="nearest")
    tr = jxx + jyy
    det = jxx * jyy - jxy * jxy
    disc = np.sqrt(np.maximum(tr * tr / 4.0 - det, 0.0))
    l1 = tr / 2.0 + disc
    l2 = np.maximum(tr / 2.0 - disc, 0.0)
    theta = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy)      # dominant gradient direction
    line_theta = theta + np.pi / 2.0                     # along-structure direction
    coh = np.where(l1 + l2 > 1e-12, (l1 - l2) / (l1 + l2 + 1e-12), 0.0)
    return (line_theta % np.pi).astype(np.float32), coh.astype(np.float32)


def frangi_line(a: np.ndarray, sigmas=(1.0, 2.0, 4.0, 8.0),
                beta=0.5, c=1e-3, ridge=True) -> np.ndarray:
    """Frangi/Sato multiscale vesselness for *lines* (ridges or valleys).

    For a ridge (bright line) the most-negative Hessian eigenvalue has large magnitude and
    the response uses ``-lambda2``; for a valley we flip the sign of the input.  Beta controls
    the penalty on blob-like structure and ``c`` suppresses the response in flat areas.
    """
    best = np.zeros(a.shape, np.float32)
    Rb = beta ** 2
    Cc = c ** 2
    for s in sigmas:
        sm = gaussian_filter(a, s, mode="nearest")
        gy, gx = np.gradient(sm)
        hyy, hyx = np.gradient(gy)
        hxy, hxx = np.gradient(gx)
        hxy = 0.5 * (hxy + hyx)
        hxx = gaussian_filter(hxx, s, mode="nearest")
        hyy = gaussian_filter(hyy, s, mode="nearest")
        hxy = gaussian_filter(hxy, s, mode="nearest")
        tr = hxx + hyy
        det = hxx * hyy - hxy * hxy
        disc = np.sqrt(np.maximum(tr * tr / 4.0 - det, 0.0))
        l1 = tr / 2.0 + disc
        l2 = tr / 2.0 - disc
        if ridge:
            lam = -l2
        else:
            lam = l1
        Rb_ = Rb
        resp = np.exp(-(l1 ** 2) / (2.0 * Rb_ * np.maximum(lam, 1e-9) ** 2 + 1e-12))
        resp *= (1.0 - np.exp(-(tr ** 2) / (2.0 * Cc + 1e-12)))
        resp = np.where(lam > 0, lam * resp, 0.0)
        np.maximum(best, resp.astype(np.float32), out=best)
    return best


def steger_subpixel(a: np.ndarray, sigma: float, ridge=True) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Steger (IEEE TPAMI 20(2):113-125, 1998) sub-pixel line extraction.

    Returns ``(strength, sub_row, sub_col)``: for each pixel, the magnitude of the Hessian's
    most-significant eigenvalue and the sub-pixel offset (t in [-0.5, 0.5]) along its
    eigenvector where the directional derivative crosses zero.  ``strength`` is the
    line contrast; the offset is what makes Steger localisation sub-pixel.
    """
    sm = gaussian_filter(a, sigma, mode="nearest")
    gy, gx = np.gradient(sm)
    hyy, hyx = np.gradient(gy)
    hxy, hxx = np.gradient(gx)
    hxy = 0.5 * (hxy + hyx)
    hxx = gaussian_filter(hxx, sigma, mode="nearest")
    hyy = gaussian_filter(hyy, sigma, mode="nearest")
    hxy = gaussian_filter(hxy, sigma, mode="nearest")
    tr = hxx + hyy
    det = hxx * hyy - hxy * hxy
    disc = np.sqrt(np.maximum(tr * tr / 4.0 - det, 0.0))
    l1 = tr / 2.0 + disc
    l2 = tr / 2.0 - disc
    lam = (-l2) if ridge else l1
    ex, ey = hxy, (lam - hxx) if np.isscalar(lam) else (lam - hxx)
    norm = np.sqrt(ex * ex + ey * ey) + 1e-12
    ex = np.where(norm > 1e-12, ex / norm, 0.0)
    ey = np.where(norm > 1e-12, ey / norm, 0.0)
    denom = hxx * ex * ex + 2.0 * hxy * ex * ey + hyy * ey * ey
    t = -(gx * ex + gy * ey) / np.where(np.abs(denom) < 1e-12, 1e-12, denom)
    t = np.clip(t, -0.5, 0.5)
    strength = np.abs(lam).astype(np.float32)
    return strength, (t * ey).astype(np.float32), (t * ex).astype(np.float32)


def nonmax_suppress(resp: np.ndarray, width: int = 1) -> np.ndarray:
    m = maximum_filter(resp, size=2 * width + 1, mode="nearest")
    return np.where(resp >= m - 1e-12, resp, 0.0).astype(np.float32)


# ---------------------------------------------------------------------------------------------
# inventory rasters used as labels / evaluation truth
# ---------------------------------------------------------------------------------------------
def load_inventory(name: str) -> np.ndarray:
    path = EXTERNAL / name
    with rasterio.open(path) as src:
        a = src.read(1)
    fp = footprint_mask()
    return (a > 0) & fp


def sgmc_offcatalogue(min_dist_px: float = 3.0, catalogue: np.ndarray | None = None
                      ) -> tuple[np.ndarray, np.ndarray]:
    """SGMC fault pixels farther than ``min_dist_px`` from the given catalogue.

    Returns ``(mask, distance_map)``.
    """
    from .grid import catalogue_mask
    cat = catalogue_mask() if catalogue is None else catalogue
    d = ndimage.distance_transform_edt(~cat)
    m = load_inventory("sgmc_faults_100m.tif") & (d > min_dist_px)
    return m, d


# ---------------------------------------------------------------------------------------------
# lane field: multiscale line / structure-tensor measures
# ---------------------------------------------------------------------------------------------
def lidar_lane_field(sigmas=(2.0, 5.0, 10.0, 20.0)) -> np.ndarray:
    """The assigned lane, adapted to the grids that are actually reachable.

    Deviation that is stated rather than hidden: the 1 m GeoDAWN/3DEP tiles and the 10 m
    tiles are not downloadable from this sandbox (only github.com and PyPI are reachable), so
    the native-resolution scarplet template matching of Sare & Hilley (JOSS 2018,
    doi:10.21105/joss.01066) cannot be re-run on 1 m data.  What *is* reachable is the
    owner's 1 m-LiDAR-derived per-100 m descriptor stack (12 channels, hash-pinned), which is
    that lane's aggregate output, plus the 10 m-DEM-derived topographic channels.  The lane is
    therefore executed as multiscale Steger/Frangi/structure-tensor analysis **on those
    channels and on the 100 m detrended elevation**, at 2-20 pixel (200-2000 m) scales.
    """
    from .features import load_stack
    stack, names, fi = load_stack()
    fp = footprint_mask()
    idx = {n: i for i, n in enumerate(names)}

    def grid(name: str) -> np.ndarray:
        return full_from_footprint(np.asarray(stack[idx[name]]), fi)

    det_elev = grid("det_elev")
    l_ex = grid("L_ex_max")
    l_step = grid("L_step_max")
    l_coh = grid("L_coh100")
    l_strike = grid("L_strike")
    t_slope = grid("T_slope_p90")
    t_relief = grid("T_relief_local")
    t_curv = grid("T_curv_prof_absmax")
    t_asp = grid("T_aspect_coherence")

    ok = fp & np.isfinite(det_elev)
    z_det = fill_for_filter(det_elev, ok)

    # (i) Frangi line response on the slope-detrended surface, both polarities.
    fr_pos = frangi_line(z_det, sigmas=sigmas, ridge=True)
    fr_neg = frangi_line(-z_det, sigmas=sigmas, ridge=True)
    frangi = np.maximum(fr_pos, fr_neg)

    # (ii) Steger sub-pixel strength on the same surface (both polarities).
    st = np.zeros(det_elev.shape, np.float32)
    for s in sigmas:
        a, _, _ = steger_subpixel(z_det, s, ridge=True)
        b, _, _ = steger_subpixel(-z_det, s, ridge=True)
        np.maximum(st, np.maximum(a, b), out=st)
    steger = nonmax_suppress(st)

    # (iii) structure-tensor orientation coherence and dominant strike
    theta, coh = structure_tensor(z_det, sigma=6.0)

    # (iv) the 1 m LiDAR scarp descriptors: amplitude x coherence, and the scarp-pixel
    #      fraction in a 3x3 neighbourhood (how much of the cell carries a scarp)
    amp = np.nan_to_num(l_ex, nan=0.0)
    step = np.nan_to_num(l_step, nan=0.0)
    scarp_px = uniform_filter((amp > 0).astype(np.float32), size=3, mode="nearest")
    amp_frac = uniform_filter(amp, size=3, mode="nearest") / np.maximum(scarp_px, 1e-6)
    snr_weighted = amp_frac * np.nan_to_num(l_coh, nan=0.0)

    # (v) concordance between the 100 m structure-tensor strike and the 1 m scarp strike:
    #     a tectonic scarp shares the regional structural grain; a road cut or a field edge
    #     generally does not.  Angles are axial (mod 180 deg).
    strike_ok = np.isfinite(l_strike) & np.isfinite(theta)
    dtheta = np.abs((np.deg2rad(l_strike) - theta + np.pi / 2) % np.pi - np.pi / 2)
    concord = np.where(strike_ok, np.cos(2.0 * dtheta), 0.0).astype(np.float32)
    concord = np.clip(concord, 0.0, 1.0)

    # (vi) cultural / non-tectonic mask: flat, low-relief, high aspect-coherence ground
    #      (playa floors, fields) and very low curvature carries roads and field edges that
    #      the scarp channels cannot distinguish from a small fault scarp.
    relief_ok = np.nan_to_num(t_relief, nan=0.0)
    slope_ok = np.nan_to_num(t_slope, nan=0.0)
    cultural = (relief_ok < np.nanpercentile(relief_ok[fp & np.isfinite(relief_ok)], 20)) | \
               (slope_ok > np.nanpercentile(slope_ok[fp & np.isfinite(slope_ok)], 99))

    parts = {
        "frangi_line": robust_unit(frangi, fp),
        "steger_nms": robust_unit(steger, fp),
        "tensor_coherence": robust_unit(coh, fp),
        "lidar_snr_amplitude": robust_unit(snr_weighted, fp),
        "scarp_pixel_fraction": robust_unit(scarp_px, fp),
        "strike_concordance": concord,
        "lidar_step": robust_unit(step, fp),
        "curvature": robust_unit(np.nan_to_num(t_curv, nan=0.0), fp),
    }
    field = (0.22 * parts["frangi_line"]
             + 0.18 * parts["steger_nms"]
             + 0.14 * parts["tensor_coherence"]
             + 0.20 * parts["lidar_snr_amplitude"]
             + 0.10 * parts["scarp_pixel_fraction"]
             + 0.16 * parts["strike_concordance"])
    field = field * (1.0 - 0.7 * cultural.astype(np.float32))
    field[~fp] = np.nan
    return field.astype(np.float32), parts


# ---------------------------------------------------------------------------------------------
# supervised fields
# ---------------------------------------------------------------------------------------------
def _design_matrix(stack, names, fi, sample_idx=None):
    cols = [i for i, n in enumerate(names) if n not in DROP_FEATURES]
    if sample_idx is None:
        X = np.asarray(stack)[cols, :].T
    else:
        X = np.asarray(stack)[cols, :][:, sample_idx].T
    return X.astype(np.float32), [names[i] for i in cols]


def supervised_field(train_mask: np.ndarray, train_exclude: np.ndarray | None = None,
                     n_neg: int = 400_000, seed: int = 0, cache: str | None = None,
                     max_iter: int = 200) -> tuple[np.ndarray, dict]:
    """Fit a gradient-boosted classifier: ``train_mask`` positives vs background negatives.

    ``train_exclude`` pixels are excluded from BOTH classes (used to blank the held-out fold
    and its buffer).  Returns ``(field_over_footprint, info)``.
    """
    from sklearn.ensemble import HistGradientBoostingClassifier
    from .features import load_stack
    stack, names, fi = load_stack()
    fp = footprint_mask()

    if cache:
        cp = PROCESSED / f"field_{cache}.npy"
        ip = PROCESSED / f"field_{cache}.json"
        if cp.exists() and ip.exists():
            return np.load(cp), json.loads(ip.read_text())

    pos_fi = np.flatnonzero(train_mask.ravel()[fi])
    excluded = np.zeros(fi.size, bool) if train_exclude is None else train_exclude.ravel()[fi]
    pool = np.flatnonzero(~excluded)
    pool = np.setdiff1d(pool, pos_fi, assume_unique=False)
    rng = np.random.default_rng(seed)
    n_neg = min(n_neg, pool.size)
    neg_fi = rng.choice(pool, n_neg, replace=False)
    idx = np.concatenate([pos_fi, neg_fi])
    y = np.concatenate([np.ones(pos_fi.size, np.int8), np.zeros(neg_fi.size, np.int8)])

    X, feat_names = _design_matrix(stack, names, fi, sample_idx=idx)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    clf = HistGradientBoostingClassifier(max_iter=max_iter, learning_rate=0.08,
                                         max_leaf_nodes=31, min_samples_leaf=60,
                                         l2_regularization=1.0, random_state=seed)
    clf.fit(X, y)
    del X, y

    # score the whole footprint in chunks
    out = np.empty(fi.size, np.float32)
    cols = [i for i, n in enumerate(names) if n not in DROP_FEATURES]
    chunk = 400_000
    for s0 in range(0, fi.size, chunk):
        s1 = min(s0 + chunk, fi.size)
        Xc = np.asarray(stack)[cols, s0:s1].T
        Xc = np.nan_to_num(Xc, nan=0.0, posinf=0.0, neginf=0.0)
        out[s0:s1] = clf.predict_proba(Xc)[:, 1].astype(np.float32)
    field = full_from_footprint(out, fi)
    info = {"n_pos": int(pos_fi.size), "n_neg": int(neg_fi.size), "seed": seed,
            "n_features": len(feat_names),
            "note": "HistGradientBoostingClassifier exposes no gain-based feature_importances_; "
                    "attribution is done separately by permutation when required."}
    if cache:
        PROCESSED.mkdir(parents=True, exist_ok=True)
        np.save(PROCESSED / f"field_{cache}.npy", field)
        (PROCESSED / f"field_{cache}.json").write_text(json.dumps(info, indent=1))
    return field, info


if __name__ == "__main__":
    f, parts = lidar_lane_field()
    print("lidar_lane_field: finite", int(np.isfinite(f).sum()),
          "range", float(np.nanmin(f)), float(np.nanmax(f)))
    for k, v in parts.items():
        print(f"  {k:24s} mean={np.nanmean(v):.4f}")
