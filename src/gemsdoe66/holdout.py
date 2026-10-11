"""Spatially blocked hide-and-recover holdout.

Design (frozen before any result was looked at)
-----------------------------------------------
The organiser's hidden test set is "faults manually identified by experts that are **not**
contained within the current public USGS database".  Any proxy whose truth is the *given*
catalogue therefore measures the wrong thing: it rewards covering faults that are already
known, which the organiser explicitly does not score.

We use two instruments, and require a field to be judged on both.

**Instrument N - novelty (primary).**
Truth = SGMC (USGS State Geologic Map Compilation) fault pixels that lie more than
300 m from the given catalogue.  These are *real* faults, mapped by the USGS, that the
competition's label set does not contain - the closest available analogue of the hidden set.
They are split into 4 spatial folds **by connected component**, and for each fold the whole
component plus a 3 px (300 m) buffer is removed from training.  Scoring is pooled DTI with
alpha = 0.2, beta = 0.8 and a 300 m triangular kernel, exactly as the organiser defines it.
Everything not in the withheld truth is background, so a prediction on a *known* fault is
charged as a false positive - which is exactly how the organiser charges it.

**Instrument C - catalogue recovery (generalisation control).**
Truth = withheld *connected components of the given catalogue*, buffer 3 px, visible
catalogue faults removed from training.  This measures ordinary fault-detection skill and is
the control that tells us whether a field is a fault detector at all.

**Matching.** Every field is emitted at the *same* budget (the incumbent's 37,654 dots) and
the same geometry (minimum separation 2.82 px, zero dots within 200 m of the known
catalogue), so the comparison isolates the field and nothing else.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy import ndimage

from .grid import PROCESSED, catalogue_mask, footprint_mask
from .metric import dti, dti_parts

N_FOLDS = 4
BUFFER_PX = 3.0


def components(mask: np.ndarray) -> tuple[np.ndarray, int]:
    lab, n = ndimage.label(mask, structure=np.ones((3, 3), bool))
    return lab, n


def component_centroids(mask: np.ndarray):
    """Return ``(labels, n, rows, cols, sizes)`` for the connected components of ``mask``."""
    lab, n = components(mask)
    if n == 0:
        return lab, 0, np.zeros(0), np.zeros(0), np.zeros(0, np.int64)
    objs = ndimage.find_objects(lab)
    rows = np.zeros(n)
    cols = np.zeros(n)
    sizes = np.zeros(n, np.int64)
    for i in range(n):
        sl = objs[i]
        if sl is None:
            continue
        sub = lab[sl] == (i + 1)
        ys, xs = np.nonzero(sub)
        rows[i] = sl[0].start + ys.mean()
        cols[i] = sl[1].start + xs.mean()
        sizes[i] = int(sub.sum())
    return lab, n, rows, cols, sizes


def folds_by_spatial_cluster(mask: np.ndarray, n_folds: int = N_FOLDS,
                             n_clusters: int = 32, seed: int = 0) -> np.ndarray:
    """Spatially coherent **and** balanced folds.

    Connected components are the unit of assignment, so a single fault never straddles a
    fold boundary.  Components are grouped into ``n_clusters`` spatial clusters by k-means on
    their centroids, and whole clusters are then assigned to folds greedily by size so that
    the folds carry comparable numbers of truth pixels.  Plain quadrant splits were measured
    to be badly unbalanced here (2,307 px vs 23,044 px), which makes a pooled per-fold mean
    needlessly noisy.

    Background (label 0) is returned as **-1** so it can never be mistaken for fold 0.
    """
    from sklearn.cluster import KMeans

    lab, n, rows, cols, sizes = component_centroids(mask)
    out = np.full(lab.shape, -1, np.int32)
    if n == 0:
        return out
    k = int(min(n_clusters, max(n_folds, n)))
    km = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(
        np.stack([rows / max(1.0, mask.shape[0]), cols / max(1.0, mask.shape[1])], 1))
    cl = km.labels_
    csize = np.bincount(cl, weights=sizes, minlength=k)
    order = np.argsort(-csize)
    load = np.zeros(n_folds, np.int64)
    fold_of_cluster = np.empty(k, np.int32)
    for c in order:
        f = int(np.argmin(load))
        fold_of_cluster[c] = f
        load[f] += int(csize[c])
    lut = np.full(n + 1, -1, np.int32)
    lut[1:] = fold_of_cluster[cl]
    return lut[lab]


def folds_by_quadrant(mask: np.ndarray, n_folds: int = N_FOLDS) -> np.ndarray:
    """Backwards-compatible alias for the quadrant split (kept for reproducibility)."""
    lab, n, rows, cols, sizes = component_centroids(mask)
    out = np.full(lab.shape, -1, np.int32)
    if n == 0:
        return out
    H, W = mask.shape
    lut = np.full(n + 1, -1, np.int32)
    lut[1:] = (((rows > H / 2).astype(int) * 2 + (cols > W / 2).astype(int)) % n_folds)
    return lut[lab]


def buffer_around(mask: np.ndarray, radius_px: float = BUFFER_PX) -> np.ndarray:
    if not mask.any():
        return np.zeros(mask.shape, bool)
    return ndimage.binary_dilation(
        mask, structure=_disc(radius_px), border_value=0)


def _disc(radius_px: float) -> np.ndarray:
    r = int(np.ceil(radius_px))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    return np.hypot(yy, xx) <= radius_px


def fold_masks(mask: np.ndarray, n_folds: int = N_FOLDS):
    """Yield ``(fold_id, truth_mask, train_exclude_mask)`` for each spatial fold."""
    folds = folds_by_spatial_cluster(mask, n_folds)
    for f in range(n_folds):
        truth = folds == f
        if not truth.any():
            continue
        excl = buffer_around(truth, BUFFER_PX)
        yield f, truth, excl


def novelty_truth(min_dist_px: float = 3.0):
    """SGMC faults farther than ``min_dist_px`` from the given catalogue."""
    from .fields import sgmc_offcatalogue
    m, _ = sgmc_offcatalogue(min_dist_px)
    return m


def score_emission(pred: np.ndarray, truth: np.ndarray,
                   mask_from_fp: np.ndarray | None = None) -> dict:
    """Pooled DTI of a prediction against ``truth``.

    ``mask_from_fp`` optionally removes pixels from the *false-positive* sum (used for the
    lenient variant in which predictions that land on other real, already-known faults are
    not charged).  It never touches the truth side.
    """
    if mask_from_fp is None:
        s, tp, fpw, fnw, ng, S, M = dti_parts(pred, truth)
        return {"dti": s, "tpw": tp, "fpw": fpw, "fnw": fnw, "n_truth": ng,
                "mass": S, "covered_mass": M}
    p = np.nan_to_num(np.asarray(pred, np.float64), nan=0.0)
    p = np.clip(p, 0.0, 1.0).copy()
    p[mask_from_fp] = 0.0
    s, tp, fpw, fnw, ng, S, M = dti_parts(p, truth)
    return {"dti": s, "tpw": tp, "fpw": fpw, "fnw": fnw, "n_truth": ng,
            "mass": S, "covered_mass": M}


def bootstrap_ci(values: np.ndarray, n_boot: int = 2000, seed: int = 0) -> tuple[float, float]:
    """Percentile bootstrap CI for the mean of a small sample."""
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    means = rng.choice(v, size=(n_boot, v.size), replace=True).mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))
