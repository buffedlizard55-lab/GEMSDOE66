"""Small shared helper so the emission script reuses exactly the sweep's dot picker."""
from __future__ import annotations

import numpy as np

H, W = 3730, 3292


def weighted_disk_dots(score, eligible, n_dots, min_sep_px, gamma=1.0, seed=0):
    """Weighted (intensity-proportional) spacing-constrained selection.

    The field is used as an **intensity**, not as a ranking: each eligible cell draws a
    priority from the Efraimidis-Spirakis exponential race
    ``key = log(u) / w`` with ``w = clip(score, 0)^gamma`` (``gamma = 0`` degenerates to a
    uniform random sample), cells are visited in descending key, and a cell is accepted only
    if no accepted dot lies within ``min_sep_px``.  This is what turns a probability field
    into a *dot density* while keeping the hard-core spacing that the marginal-credit rule
    of the DTI metric demands.
    """
    mask = eligible & np.isfinite(score)
    ys, xs = np.nonzero(mask)
    if ys.size == 0 or n_dots <= 0:
        return np.zeros(score.shape, bool)
    s = np.clip(score[ys, xs].astype(np.float64), 0.0, None)
    if gamma == 0.0:
        w = np.ones_like(s)
    else:
        w = np.power(s, float(gamma))
    wmax = float(w.max()) if w.size else 1.0
    if not np.isfinite(wmax) or wmax <= 0:
        w = np.ones_like(s)
        wmax = 1.0
    w = w / wmax
    rng = np.random.default_rng(seed)
    u = rng.random(ys.size)
    u = np.clip(u, 1e-12, 1.0)
    key = np.log(u) / np.maximum(w, 1e-12)
    order = np.argsort(-key, kind="stable")
    ys, xs = ys[order], xs[order]
    r = int(np.ceil(min_sep_px))
    dy, dx = np.mgrid[-r:r + 1, -r:r + 1]
    keep = (dy * dy + dx * dx) < float(min_sep_px) ** 2
    dys, dxs = dy[keep], dx[keep]
    suppressed = np.zeros((H, W), bool)
    cy, cx = [], []
    for y, x in zip(ys.tolist(), xs.tolist()):
        if len(cy) >= n_dots:
            break
        if suppressed[y, x]:
            continue
        cy.append(y)
        cx.append(x)
        yy = y + dys
        xx = x + dxs
        ok = (yy >= 0) & (yy < H) & (xx >= 0) & (xx < W)
        suppressed[yy[ok], xx[ok]] = True
    out = np.zeros((H, W), bool)
    if cy:
        out[np.asarray(cy, dtype=np.int64), np.asarray(cx, dtype=np.int64)] = True
    return out


def poisson_disk_dots(score, eligible, n_dots, min_sep_px):
    """Greedy spacing-constrained selection over a score field (identical to lane_run.py)."""
    mask = eligible & np.isfinite(score)
    ys, xs = np.nonzero(mask)
    if ys.size == 0 or n_dots <= 0:
        return np.zeros(score.shape, bool)
    order = np.argsort(-score[ys, xs], kind="stable")
    ys, xs = ys[order], xs[order]
    r = int(np.ceil(min_sep_px))
    dy, dx = np.mgrid[-r:r + 1, -r:r + 1]
    keep = (dy * dy + dx * dx) < float(min_sep_px) ** 2
    dys, dxs = dy[keep], dx[keep]
    suppressed = np.zeros((H, W), bool)
    cy, cx = [], []
    for y, x in zip(ys.tolist(), xs.tolist()):
        if len(cy) >= n_dots:
            break
        if suppressed[y, x]:
            continue
        cy.append(y)
        cx.append(x)
        yy = y + dys
        xx = x + dxs
        ok = (yy >= 0) & (yy < H) & (xx >= 0) & (xx < W)
        suppressed[yy[ok], xx[ok]] = True
    out = np.zeros((H, W), bool)
    if cy:
        out[np.asarray(cy, dtype=np.int64), np.asarray(cx, dtype=np.int64)] = True
    return out
