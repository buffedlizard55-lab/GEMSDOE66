"""H66-C experiment: native-resolution LiDAR scarp channels under spatial CV.

Protocol (preregistered in ``registry/preregistration-h66c.json``)
------------------------------------------------------------------
Instruments
  * **S (primary, split-catalogue).**  The public catalogue is the INGENIOUS
    Quaternary-fault compilation.  Its fault segments (authoritative
    ``record_id`` from the GDR trace table) are split at random into two halves.
    Half A is the *visible* public database; half B stands in for the faults the
    organisers' experts added.  Every catalogue-derived quantity -- distance to
    the mapped faults, mapped-fault density, the gap weight -- is computed from
    half A only.  Scoring is pooled DTI (alpha 0.2, beta 0.8, 300 m triangular
    kernel) on half-B pixels inside LiDAR-covered held-out blocks.  Visible
    (half-A) pixels are masked out of the prediction so rediscovery of the
    visible catalogue cannot earn credit.
  * **N (secondary, independent inventory).**  Truth = USGS SGMC geologic-map
    fault pixels farther than 300 m from the full catalogue, inside LiDAR
    coverage.  Independent of the catalogue but a different population (bedrock
    map faults, many without Quaternary expression), so it is a corroboration,
    not a substitute.
  * **C (control).**  Withheld catalogue segments scored with the *full* rest of
    the catalogue visible, i.e. the classic hide-and-recover.  Reported for
    continuity with the family's earlier runs.

Leakage canary
  Each proposed feature is scored alone on instrument S (AUC of the raw feature
  against half-B positives vs. matched non-fault controls).  AUC > 0.90 is
  leakage until proven otherwise.

Blocks
  ``block_px`` square blocks are used both for the holdout selection and as the
  bootstrap resampling unit for the 95% CI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

from .grid import EXTERNAL, PROCESSED, RAW, footprint_mask
from .features import load_stack
from .scarp66 import build_scarp_channels
from gems.metric import tversky_terms, dti_from_terms
from gems.holdout import spatial_block_ids

PIXEL_M = 100.0
RANGE_M = 300.0


# --------------------------------------------------------------------------------------
# inputs
# --------------------------------------------------------------------------------------
def load_context():
    fp = footprint_mask()
    stack, names, fi = load_stack()
    idx = {n: i for i, n in enumerate(names)}

    def get(name: str) -> np.ndarray:
        a = np.full(fp.size, np.nan, np.float32)
        a[fi] = stack[idx[name]]
        return a.reshape(fp.shape)

    with rasterio.open(RAW / "labels.tif") as ds:
        lab = ds.read(1)
    catalogue = np.isfinite(lab) & (lab > 0)

    with rasterio.open(EXTERNAL / "tiger_road_distance_m.tif") as ds:
        road = ds.read(1).astype(np.float32)
    with rasterio.open(EXTERNAL / "blm_closed_claim_distance_m.tif") as ds:
        claim = ds.read(1).astype(np.float32)
    with rasterio.open(EXTERNAL / "acquisition_block_id_100m.tif") as ds:
        acq = ds.read(1)
    with rasterio.open(EXTERNAL / "sgmc_faults_100m.tif") as ds:
        sgmc = ds.read(1) > 0
    return dict(fp=fp, get=get, names=names, catalogue=catalogue, road=road, claim=claim,
                acq=acq, sgmc=sgmc)


def segment_ids_from_traces(shape, transform) -> np.ndarray:
    """Rasterise GDR/INGENIOUS ``trace_segments_utm11.csv`` -> authoritative segment IDs.

    ``record_id`` is the fault-section identifier published with the INGENIOUS
    Quaternary-fault traces, so it is a real geologic segment ID rather than an
    8-connected raster component.  Cells claimed by more than one record keep the
    first (lowest) id; ties are irrelevant because the whole segment is withheld.
    """
    import pandas as pd

    df = pd.read_csv(EXTERNAL / "trace_segments_utm11.csv")
    a, b, c, d, e, f = transform[0], transform[1], transform[2], transform[3], transform[4], transform[5]
    det = a * f - b * d
    ia, ib = f / det, -b / det
    ic, id_ = -e / det, a / det
    seg = np.zeros(shape, dtype=np.int32)
    h, w = shape
    for rid, grp in df.groupby("record_id", sort=True):
        pts = []
        for _, r in grp.iterrows():
            for (x, y) in ((r.x0, r.y0), (r.x1, r.y1)):
                col = int(np.floor(ia * (x - c) + ib * (y - f)))
                row = int(np.floor(ic * (x - c) + id_ * (y - f)))
                pts.append((row, col))
            # densify long segments so the rasterised trace is 8-connected
            n = int(max(abs(r.x1 - r.x0), abs(r.y1 - r.y0)) / (PIXEL_M * 0.5)) + 2
            for t in np.linspace(0, 1, min(n, 64)):
                x = r.x0 + t * (r.x1 - r.x0)
                y = r.y0 + t * (r.y1 - r.y0)
                col = int(np.floor(ia * (x - c) + ib * (y - f)))
                row = int(np.floor(ic * (x - c) + id_ * (y - f)))
                pts.append((row, col))
        for row, col in pts:
            if 0 <= row < h and 0 <= col < w and seg[row, col] == 0:
                seg[row, col] = int(rid)
    return seg


# --------------------------------------------------------------------------------------
# splits
# --------------------------------------------------------------------------------------
@dataclass
class Split:
    visible: np.ndarray        # half-A catalogue pixels (the "public database")
    withheld: np.ndarray       # half-B catalogue pixels (stand-in for the experts' new faults)
    held_block: np.ndarray     # LiDAR-covered spatial blocks used for scoring
    segment_ids: np.ndarray
    diagnostics: dict = field(default_factory=dict)


def split_catalogue(catalogue: np.ndarray, seg: np.ndarray, lidar: np.ndarray,
                    block_px: int, holdout_fraction: float, buffer_px: int,
                    seed: int, min_lidar_fraction: float = 0.9) -> Split:
    """Withhold whole fault segments selected through LiDAR-covered spatial blocks."""
    fm = catalogue
    block_ids = spatial_block_ids(fm.shape, block_px)
    flat = block_ids.ravel()
    n_blocks = int(flat.max()) + 1
    lid_n = np.bincount(flat, weights=lidar.ravel().astype(float), minlength=n_blocks)
    cell_n = np.bincount(flat, minlength=n_blocks).astype(float)
    flt_n = np.bincount(flat, weights=(fm & lidar).ravel().astype(float), minlength=n_blocks)
    cov = lid_n / np.maximum(cell_n, 1.0)
    eligible = np.flatnonzero((cov >= min_lidar_fraction) & (flt_n > 0))
    rng = np.random.default_rng(seed)
    k = max(1, int(round(holdout_fraction * eligible.size)))
    chosen = rng.choice(eligible, size=min(k, eligible.size), replace=False)
    held_block = np.isin(block_ids, chosen)

    # A segment touched by a held block is withheld everywhere (no long-trace leakage).
    touched = fm & held_block & (seg > 0)
    held_ids = np.unique(seg[touched])
    held_ids = held_ids[held_ids > 0]
    withheld = fm & np.isin(seg, held_ids)
    visible_raw = fm & ~withheld
    if buffer_px:
        buf = ndi.distance_transform_edt(~withheld) <= buffer_px
    else:
        buf = np.zeros_like(fm)
    visible = visible_raw & ~buf
    return Split(visible=visible, withheld=withheld, held_block=held_block, segment_ids=seg,
                 diagnostics=dict(block_px=block_px, holdout_fraction=holdout_fraction,
                                  buffer_px=buffer_px, seed=seed,
                                  eligible_blocks=int(eligible.size), held_blocks=int(len(chosen)),
                                  held_block_cells=int(held_block.sum()),
                                  withheld_fault_cells=int(withheld.sum()),
                                  scored_fault_cells=int((withheld & held_block & lidar).sum()),
                                  visible_fault_cells=int(visible.sum()),
                                  buffer_dropped_cells=int((visible_raw & buf).sum())))


# --------------------------------------------------------------------------------------
# feature matrix
# --------------------------------------------------------------------------------------
def build_matrix(ch, ctx, d_vis: np.ndarray, gap_ref_m: float,
                 out_path: str | Path | None = None) -> tuple[np.memmap, list[str]]:
    """Return (X, names) with X of shape ``(n_features, n_footprint)``.

    Only footprint cells are stored (5.17 M rather than 12.28 M), and the array
    is an on-disk ``float32`` memmap so the 59-feature matrix never has to live
    in RAM: 59 x 5.17 M x 4 B = 1.2 GB on disk, one column in memory at a time.
    """
    fp = ctx["fp"]
    get = ctx["get"]
    fi = np.flatnonzero(fp.ravel()).astype(np.int64)

    base_names = ["mag_anom", "rtp", "tmi_hg", "geod_2ndinv", "iso_grav_anom_slope", "tc",
                  "geod_shearrate", "geod_dilaterate", "tmi_vg", "deq_n100a15",
                  "iso_grav_anom_vg", "det_elev", "iso_grav_anom", "tmi",
                  "depth_to_base_surf", "ieq_n100a15", "cond_surf", "iso_grav_anom_hg",
                  "det_elev_slope", "T_slope_p90", "T_slope_max", "T_steep_frac",
                  "T_slope_std", "T_relief_local", "T_curv_prof_absmax",
                  "T_aspect_coherence", "T_hs_lineament", "T_dem_mean",
                  "rad_K", "rad_Th", "rad_U", "rad_TC", "ext_ThK", "ext_UK", "ext_UTh",
                  "ext_TMI_up150", "chi_b1", "chi_b2", "chi_b3", "chi_b4", "chi_b5",
                  "chi_sig"]
    cols, names = [], []
    for n in base_names:
        cols.append(get(n).ravel()[fi].astype(np.float32))
        names.append(n)

    lane = [
        ("sc_amp", ch["amp"]),
        ("sc_frac", ch["frac"]),
        ("sc_snr", ch["snr"]),
        ("sc_amp_snr", ch["amp_snr"]),
        ("sc_a_hat", ch["a_hat"]),
        ("sc_kt_hat", ch["kt_hat"]),
        ("sc_dipole", ch["dipole"]),
        ("sc_facing", ch["facing"]),
        ("sc_coh_cell", ch["coh_cell"]),
        ("sc_frangi_amp", ch["frangi_amp"]),
        ("sc_frangi_det", ch["frangi_det"]),
        ("sc_steger_amp", ch["steger_amp"]),
        ("sc_steger_det", ch["steger_det"]),
        ("sc_coh_line", ch["coh_line"]),
        ("sc_relief", ch["relief_m"]),
    ]
    for n, a in lane:
        v = np.asarray(a, np.float32).ravel()[fi]
        v[~np.isfinite(v)] = np.nan
        cols.append(v)
        names.append(n)

    # catalogue-derived: distance to the *visible* faults and the implied gap weight
    gap = np.clip(d_vis / float(gap_ref_m), 0.0, 1.0).astype(np.float32)
    dens = ndi.uniform_filter((d_vis <= 300.0).astype(np.float32), 11).astype(np.float32)
    cols.append(d_vis.ravel()[fi].astype(np.float32))
    names.append("cat_dist_m")
    cols.append(gap.ravel()[fi])
    names.append("cat_gap")
    cols.append(dens.ravel()[fi])
    names.append("cat_density")

    # ---- multi-line corroboration: how many *independent* line detectors fire here?
    # (Stack's own structure-tensor coherence, Steger and Frangi on the scarp-amplitude
    # field, and Steger and Frangi on the slope-detrended elevation.)
    def _q(a, q):
        v = np.asarray(a, np.float32).ravel()
        v = v[np.isfinite(v)]
        return float(np.quantile(v, q)) if v.size else 0.0

    line_terms = []
    for nm, arr in (("coh_cell", ch["coh_cell"]), ("steger_amp", ch["steger_amp"]),
                    ("frangi_amp", ch["frangi_amp"]), ("steger_det", ch["steger_det"]),
                    ("frangi_det", ch["frangi_det"])):
        thr = _q(arr, 0.90)
        v = np.asarray(arr, np.float32).ravel()[fi]
        fire = (np.nan_to_num(v, nan=-np.inf) >= thr).astype(np.float32)
        fire[~np.isfinite(v)] = np.nan
        line_terms.append((nm, fire, v, thr))
    nan_free = np.zeros(fi.size, bool)
    for _, f, _, _ in line_terms:
        nan_free |= np.isfinite(f)
    votes = np.zeros(fi.size, np.float32)
    for _, f, _, _ in line_terms:
        votes += np.nan_to_num(f, nan=0.0)
    votes[~nan_free] = np.nan
    cols.append(votes)
    names.append("sc_votes")

    def _nz(a):
        v = np.asarray(a, np.float32).ravel()[fi]
        v = np.where(np.isfinite(v), v, 0.0)
        hi = _q(a, 0.99)
        return np.clip(v / max(hi, 1e-12), 0.0, 1.0).astype(np.float32)

    corr = (_nz(ch["steger_amp"]) * _nz(ch["frangi_amp"]) * _nz(ch["coh_cell"]) *
            np.maximum(_nz(ch["steger_det"]), _nz(ch["frangi_det"]))) ** 0.25
    cols.append(corr)
    names.append("sc_corroboration")
    # subtle-scarp index: coherent lineament with a *low* diffusion-inverted height and a
    # large morphologic age -- the signature of a scarp the compilers plausibly missed.
    a_hat = np.asarray(ch["a_hat"], np.float32).ravel()[fi]
    kt = np.asarray(ch["kt_hat"], np.float32).ravel()[fi]
    sub = np.where(np.isfinite(a_hat) & np.isfinite(kt), corr / np.sqrt(np.maximum(a_hat, 0.1)), np.nan)
    cols.append(sub.astype(np.float32))
    names.append("sc_subtle_index")

    n_feat = len(cols)
    if out_path is None:
        X = np.empty((n_feat, fi.size), np.float32)
    else:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        X = np.lib.format.open_memmap(out_path, mode="w+", dtype=np.float32,
                                      shape=(n_feat, fi.size))
    for j, v in enumerate(cols):
        X[j] = v
        del v
    X.flush()
    return X, names


# --------------------------------------------------------------------------------------
# emission
# --------------------------------------------------------------------------------------
def poisson_dots(score: np.ndarray, domain: np.ndarray, min_sep: int, budget: int,
                 seed: int = 0) -> np.ndarray:
    """Greedy top-score packing with a minimum separation of ``min_sep`` cells.

    Cells are visited in descending score order; a cell is emitted only if no
    already-emitted cell lies within ``min_sep`` cells (Chebyshev distance).
    """
    out = np.zeros(score.shape, bool)
    s = np.where(domain & np.isfinite(score), score, -np.inf).astype(np.float32)
    flat = np.argsort(-s.ravel(), kind="stable")
    taken_rows, taken_cols = [], []
    # chunked check against the emitted set using a coarse grid for speed
    step = int(max(1, min_sep))
    h, w = score.shape
    gh, gw = (h + step - 1) // step, (w + step - 1) // step
    grid = [[] for _ in range(gh * gw)]
    n = 0
    for k in flat:
        if not np.isfinite(s.ravel()[k]):
            break
        if n >= budget:
            break
        r, c = divmod(int(k), w)
        ok = True
        for dr in range(-1, 2):
            for dc in range(-1, 2):
                gr, gc = r // step + dr, c // step + dc
                if 0 <= gr < gh and 0 <= gc < gw:
                    for (rr, cc) in grid[gr * gw + gc]:
                        if abs(rr - r) <= min_sep and abs(cc - c) <= min_sep:
                            ok = False
                            break
                    if not ok:
                        break
            if not ok:
                break
        if ok:
            out[r, c] = True
            grid[(r // step) * gw + (c // step)].append((r, c))
            n += 1
    return out


# --------------------------------------------------------------------------------------
# scoring
# --------------------------------------------------------------------------------------
def pooled_dti(pred: np.ndarray, truth: np.ndarray, region: np.ndarray,
               mask_out: np.ndarray | None = None) -> dict:
    """Pooled DTI of ``pred`` against ``truth`` restricted to ``region``.

    ``mask_out`` pixels are zeroed in the prediction (they are visible-fault
    pixels that must not earn credit).
    """
    p = np.where(region, np.nan_to_num(pred, nan=0.0), 0.0).astype(np.float64)
    if mask_out is not None:
        p[mask_out] = 0.0
    g = truth & region
    tp, fpw, fnw = tversky_terms(np.clip(p, 0.0, 1.0), g)
    return dict(tp=float(tp), fp=float(fpw), fn=float(fnw),
                dti=float(dti_from_terms(tp, fpw, fnw)), n_truth=int(g.sum()),
                emitted=float(p[region].sum()))


def block_bootstrap_dti(pred: np.ndarray, truth: np.ndarray, region: np.ndarray,
                        block_px: int, mask_out: np.ndarray | None = None,
                        n_boot: int = 400, seed: int = 0) -> dict:
    """Block bootstrap over the scoring blocks; returns the 95% percentile CI."""
    bids = spatial_block_ids(truth.shape, block_px)
    region_blocks = np.unique(bids[region])
    region_blocks = [int(b) for b in region_blocks if (truth & (bids == b)).any()]
    if len(region_blocks) < 3:
        return dict(ci95=None, n_blocks=len(region_blocks), note="too few blocks for a CI")
    p = np.where(region, np.nan_to_num(pred, nan=0.0), 0.0).astype(np.float64)
    if mask_out is not None:
        p[mask_out] = 0.0
    p = np.clip(p, 0.0, 1.0)
    g = truth & region
    per = {}
    for b in region_blocks:
        m = (bids == b)
        tp, fpw, fnw = tversky_terms(p * m, g & m)
        per[b] = (tp, fpw, fnw)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        draw = rng.choice(region_blocks, size=len(region_blocks), replace=True)
        T = F = N = 0.0
        for b in draw:
            tp, fpw, fnw = per[b]
            T += tp; F += fpw; N += fnw
        vals.append(dti_from_terms(T, F, N))
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return dict(ci95=[float(lo), float(hi)], n_blocks=len(region_blocks),
                boot_mean=float(np.mean(vals)), boot_sd=float(np.std(vals)))
