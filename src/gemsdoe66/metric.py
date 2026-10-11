"""Distance-weighted Tversky index (DTI) - the official competition metric.

Transcribed line by line from the organiser's equations on
https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/

    k(d)  = max(1 - d/R, 0),                     R = 300 m  (= 3 px at 100 m)
    TPw   = sum_g  max_x  p(x) * k(d(x,g))
    FPw   = sum_x  p(x) * [ 1 - max_g k(d(x,g)) ]
    FNw   = sum_g  [ 1 - max_x p(x) * k(d(x,g)) ]
    DTI   = TPw / (TPw + alpha*FPw + beta*FNw + eps),   alpha = 0.2, beta = 0.8

Two implementations are provided:

* :func:`dti`  - fast separable kernel-sweep implementation, O(N) in the number of pixels
  plus O(|G| * kernel area).
* :func:`dti_bruteforce` - literal O(N*|G|) transcription used only to prove the fast one
  is correct (``tests/test_metric.py`` asserts agreement to 1e-9).

Because ``FNw = |G| - TPw`` exactly, the score can also be written

    DTI = T / (0.2*T + 0.2*(S - M) + 0.8*|G|)

with ``T = TPw``, ``S = sum_x p(x)`` and ``M = sum_x p(x)*max_g k``.  :func:`dti_parts`
returns those four numbers so the decomposition can be audited.

All distances are Euclidean in **pixels**, evaluated on the 100 m grid.  The organiser's
300 m support is therefore 3.0 px; a prediction 1 px away scores k = 2/3, 2 px -> 1/3.
"""
from __future__ import annotations

import numpy as np

from .grid import ALPHA, BETA, KERNEL_RANGE_PX


def _kernel_offsets(radius_px: float = KERNEL_RANGE_PX):
    """Integer pixel offsets with 0 < k <= 1 inside the triangular kernel support."""
    r = int(np.floor(radius_px))
    dy, dx = np.mgrid[-r : r + 1, -r : r + 1]
    d = np.hypot(dy, dx)
    keep = d < radius_px            # strictly inside: k > 0
    return dy[keep], dx[keep], (1.0 - d[keep] / radius_px)


def _max_kernel(field: np.ndarray, radius_px: float = KERNEL_RANGE_PX) -> np.ndarray:
    """For every pixel x, ``max_x' p(x') * k(d(x, x'))``.

    This is a grey-scale dilation with the (non-flat) triangular structuring element, i.e.
    exactly a max over shifted-and-scaled copies of the input.  Only aligned-slice maxima
    are used, so the cost is one pass per kernel offset with no temporaries.
    """
    dy, dx, k = _kernel_offsets(radius_px)
    h, w = field.shape
    out = field.copy()                      # k = 1 at the centre offset
    for oy, ox, kk in zip(dy, dx, k):
        if oy == 0 and ox == 0:
            continue
        sy0, sy1 = max(0, -oy), min(h, h - oy)
        sx0, sx1 = max(0, -ox), min(w, w - ox)
        if sy1 <= sy0 or sx1 <= sx0:
            continue
        src = field[sy0:sy1, sx0:sx1]
        dst = out[sy0 + oy:sy1 + oy, sx0 + ox:sx1 + ox]
        np.maximum(dst, kk * src, out=dst)
    return out


def _max_kernel_from_points(points_yx: np.ndarray, shape: tuple,
                            radius_px: float = KERNEL_RANGE_PX) -> np.ndarray:
    """max_g k(d(x,g)) for a sparse set of truth pixels g -> dense map."""
    dy, dx, k = _kernel_offsets(radius_px)
    h, w = shape
    out = np.zeros(shape, dtype=np.float64)
    for oy, ox, kk in zip(dy, dx, k):
        ys = points_yx[:, 0] + oy
        xs = points_yx[:, 1] + ox
        ok = (ys >= 0) & (ys < h) & (xs >= 0) & (xs < w)
        np.maximum.at(out, (ys[ok], xs[ok]), kk)
    return out


def dti_parts(pred: np.ndarray, truth: np.ndarray,
              alpha: float = ALPHA, beta: float = BETA,
              radius_px: float = KERNEL_RANGE_PX, eps: float = 1e-12):
    """Return ``(DTI, TPw, FPw, FNw, |G|, S, M)``.

    ``pred``  - float array of predictions p(x) in [0, 1] (NaN treated as 0).
    ``truth`` - boolean or 0/1 array of ground-truth pixels.
    """
    p = np.nan_to_num(np.asarray(pred, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    p = np.clip(p, 0.0, 1.0)
    g = np.asarray(truth, dtype=np.float64) > 0
    n_truth = int(g.sum())
    if n_truth == 0:
        return 0.0, 0.0, float(p.sum()), 0.0, 0, float(p.sum()), 0.0

    # max_g k(d(x,g)) over truth pixels -> dense map
    gy, gx = np.nonzero(g)
    kmap = _max_kernel_from_points(np.stack([gy, gx], 1), p.shape, radius_px)

    # TPw = sum_g max_x p(x) k(d(x,g))  ==  sum_g max over x of p*k
    # computed as: for each truth pixel, max over its kernel neighbourhood of p(x)k(d)
    pk = _max_kernel(p, radius_px)          # max_x' p(x') k(d(x,x')) centred at each x
    tpw = float(pk[g].sum())

    M = float((p * kmap).sum())
    S = float(p.sum())
    fpw = S - M
    fnw = n_truth - tpw
    denom = tpw + alpha * fpw + beta * fnw + eps
    return tpw / denom, tpw, fpw, fnw, n_truth, S, M


def dti(pred: np.ndarray, truth: np.ndarray, alpha: float = ALPHA,
        beta: float = BETA, radius_px: float = KERNEL_RANGE_PX) -> float:
    """Official distance-weighted Tversky index."""
    return dti_parts(pred, truth, alpha, beta, radius_px)[0]


def dti_bruteforce(pred: np.ndarray, truth: np.ndarray, alpha: float = ALPHA,
                   beta: float = BETA, radius_px: float = KERNEL_RANGE_PX,
                   eps: float = 1e-12) -> float:
    """Literal O(N*|G|) transcription of the organiser's equations (test oracle only)."""
    p = np.nan_to_num(np.asarray(pred, dtype=np.float64), nan=0.0)
    p = np.clip(p, 0.0, 1.0)
    g = np.asarray(truth) > 0
    py, px = np.nonzero(p)
    gy, gx = np.nonzero(g)
    if len(gy) == 0:
        return 0.0
    P = p[py, px]
    if len(py) == 0:
        return 0.0
    d = np.hypot(py[:, None] - gy[None, :], px[:, None] - gx[None, :])
    k = np.clip(1.0 - d / radius_px, 0.0, None)
    tpw = float((P[:, None] * k).max(axis=0).sum())
    fpw = float((P * (1.0 - k.max(axis=1))).sum())
    fnw = float((1.0 - (P[:, None] * k).max(axis=0)).sum())
    return tpw / (tpw + alpha * fpw + beta * fnw + eps)


def marginal_credit_bar(score: float, alpha: float = ALPHA) -> float:
    """Kernel credit an added unit of mass must beat to raise the score.

    Derivation: at fixed T, M, |G|, adding unit mass at a pixel that is not already the
    best cover for any truth pixel changes TPw by k, S by 1, M by k, so the denominator
    rises by exactly ``alpha`` and the numerator by k.  d(DTI) > 0  <=>  k > alpha*DTI.
    """
    return alpha * score
