"""Dot emission: turn a continuous belief field into a sparse set of scored pixels.

Why emission is a first-class object
------------------------------------
The metric is a *budget*, not a segmentation score.  Writing ``T = TPw``, ``S = sum p`` and
``M = sum p * max_g k``, and using ``FNw = |G| - TPw``:

    DTI = T / (0.2*T + 0.2*(S - M) + 0.8*|G|)

so every unit of emitted mass costs exactly ``alpha = 0.2`` in the denominator and returns
only the kernel credit it actually earns.  Adding a pixel raises the score iff

    k > alpha * DTI                      (the metric's own first-order condition)

which at DTI = 0.28 is a credit bar of 0.056.  Mass that cannot clear the bar is a loss.
That is why the highest-scoring rasters in this project family are all **sparse dot sets**
rather than dense probability maps.

The emission rules here are:

``greedy_minsep``
    Take pixels in decreasing field order, skipping any pixel within ``min_sep_px`` of an
    already-taken pixel.  This is a maximal-independent-set packing: it spends the budget on
    the highest-belief pixels while preventing several pixels from competing for the same
    truth pixel (which adds FP mass without adding TP credit).
``greedy_scatter_cover``
    Same, but ranks by the field **blurred by the expected truth scatter** ``sigma``: if the
    hidden truth is displaced from the field's ridge by about ``sigma``, the expected credit
    of an emitted pixel is the metric kernel applied to the *scattered* density, so the
    correct thing to cover is the blurred field, not the raw field.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage


def _valid(field: np.ndarray, fp: np.ndarray) -> np.ndarray:
    return fp & np.isfinite(field)


def greedy_minsep(field: np.ndarray, n_dots: int, fp: np.ndarray,
                  exclude: np.ndarray | None = None, min_sep_px: float = 2.8,
                  ranking: np.ndarray | None = None) -> np.ndarray:
    """Greedy highest-belief packing with a minimum separation.

    Returns a boolean mask of chosen pixels.  ``ranking`` overrides the field for ordering
    (used by the scatter-cover rule); selection still requires the pixel to be valid.
    """
    valid = _valid(field, fp)
    if exclude is not None:
        valid &= ~exclude
    order_field = np.where(valid, ranking if ranking is not None else field, -np.inf)
    order_field = np.where(np.isfinite(order_field), order_field, -np.inf).astype(np.float32)

    shape = order_field.shape
    H, W = shape
    sep = int(np.ceil(min_sep_px))
    yy, xx = np.mgrid[-sep:sep + 1, -sep:sep + 1]
    keep = np.hypot(yy, xx) <= min_sep_px
    offs = np.stack([yy[keep].ravel(), xx[keep].ravel()], 1)   # exclusion disc offsets

    flat = order_field.ravel()
    finite_idx = np.flatnonzero(valid.ravel())
    order = np.argsort(-flat[finite_idx], kind="stable")
    ordered_idx = finite_idx[order]
    del flat, order

    blocked = np.zeros(shape, bool)
    chosen = np.zeros(shape, bool)
    remaining = int(n_dots)
    # Each accepted pixel stamps its exclusion disc, so the minimum separation is enforced
    # against every previously accepted pixel (a full re-dilation per block would miss
    # neighbours accepted inside the same block).
    for idx in ordered_idx:
        if remaining <= 0:
            break
        r, c = divmod(int(idx), W)
        if blocked[r, c]:
            continue
        chosen[r, c] = True
        remaining -= 1
        rows = offs[:, 0] + r
        cols = offs[:, 1] + c
        ok = (rows >= 0) & (rows < H) & (cols >= 0) & (cols < W)
        blocked[rows[ok], cols[ok]] = True
    return chosen


def blur_for_scatter(field: np.ndarray, sigma_px: float) -> np.ndarray:
    """Expected-credit ranking: convolve the field with the metric's own kernel support.

    Rationale: if a truth pixel lies within ~``sigma_px`` of a high-belief pixel, the credit
    an emitted pixel earns is the kernel applied to the *scattered* truth density, so the
    surface to cover is the blurred field.  GEMSDOE32 measured this single change as
    +0.0247 DTI at identical mass on its live-anchored truth model; we re-test it on the
    blocked novelty holdout instead of trusting that number.
    """
    valid = np.isfinite(field)
    filled = np.where(valid, field, 0.0).astype(np.float32)
    w = np.where(valid, 1.0, 0.0).astype(np.float32)
    num = ndimage.gaussian_filter(filled, sigma_px, mode="constant", cval=0.0)
    den = ndimage.gaussian_filter(w, sigma_px, mode="constant", cval=0.0)
    return np.where(den > 1e-6, num / np.maximum(den, 1e-6), 0.0).astype(np.float32)


def emit(field: np.ndarray, n_dots: int, fp: np.ndarray,
         exclude: np.ndarray | None = None, min_sep_px: float = 2.8,
         scatter_sigma: float | None = None) -> np.ndarray:
    ranking = None if scatter_sigma is None else blur_for_scatter(field, scatter_sigma)
    return greedy_minsep(field, n_dots, fp, exclude=exclude, min_sep_px=min_sep_px,
                         ranking=ranking)


def dot_geometry(dots: np.ndarray) -> dict:
    """Nearest-neighbour spacing statistics of an emitted dot set.

    Distances are between *distinct* dots, so a dot's neighbour is never itself; the
    distance transform of the complement would report 0 at every dot and is the wrong tool.
    """
    from scipy.spatial import cKDTree
    ys, xs = np.nonzero(dots)
    pts = np.stack([ys, xs], 1).astype(np.float64)
    if len(pts) < 2:
        return {"n": int(len(pts))}
    tree = cKDTree(pts)
    dd, _ = tree.query(pts, k=2)
    dd = dd[:, 1]
    return {"n": int(len(pts)),
            "nn_median_px": float(np.median(dd)),
            "nn_p10_px": float(np.percentile(dd, 10)),
            "nn_p90_px": float(np.percentile(dd, 90)),
            "nn_min_px": float(dd.min()),
            "frac_touching_8conn": float((dd <= 1.0).mean())}
