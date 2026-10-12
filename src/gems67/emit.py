"""Metric-native greedy emission: choose the dot set that maximises expected DTI.

Why this and not a fixed budget
------------------------------
Read the belief surface ``b(x)`` as independent Bernoulli truth probabilities.  Under the
official metric the three Tversky terms then have exact expectations:

    E[TPw](D) = sum_x b(x) * max_{y in D} k(d(x,y))
    E[FNw](D) = sum_x b(x) - E[TPw](D)                       (TPw + FNw = |G|)
    E[m_y]    = int_0^1 [1 - prod_{j: k_j > t} (1 - b(j))] dt
    E[FPw](D) = sum_{y in D} (1 - E[m_y])

    E[DTI](D) = E[TPw] / (0.2 E[TPw] + 0.2 E[FPw] + 0.8 sum(b))

Adding a dot is worthwhile exactly when that ratio rises, so the emitter runs lazy greedy on
the submodular coverage term and STOPS BY ITSELF when no pixel clears break-even.  The budget
is a safety cap, not the design parameter.  This replaces the "pick a dot count, then
Poisson-disk it" rule used by earlier sessions in this family.

Two facts make it fast: k has 300 m = 3 px support, so a gain is a 7x7 local sum; and a
candidate's score is non-increasing in time while the running DTI is non-decreasing, so once a
candidate falls below break-even it can be dropped forever.  The active set therefore shrinks
monotonically and no priority queue is needed.
"""
from __future__ import annotations

import numpy as np

from gems.constants import KERNEL_RANGE_M, PIXEL_M
from gems.metric import kernel

R_PX = int(np.floor(KERNEL_RANGE_M / PIXEL_M))
_ALPHA, _BETA = 0.2, 0.8


def offsets() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dy, dx = np.meshgrid(np.arange(-R_PX, R_PX + 1), np.arange(-R_PX, R_PX + 1), indexing="ij")
    d = PIXEL_M * np.hypot(dy, dx)
    k = kernel(d, KERNEL_RANGE_M)
    keep = k > 0
    return dy[keep].astype(np.int32), dx[keep].astype(np.int32), k[keep].astype(np.float64)


def _shift_src(field: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """out[x] = field[x + (dy, dx)], zero outside the array (no wrap-around)."""
    h, w = field.shape
    out = np.zeros((h, w), dtype=field.dtype)
    ys, yd = (slice(max(dy, 0), h + min(dy, 0)), slice(max(-dy, 0), h + min(-dy, 0)))
    xs, xd = (slice(max(dx, 0), w + min(dx, 0)), slice(max(-dx, 0), w + min(-dx, 0)))
    out[yd, xd] = field[ys, xs]
    return out


def expected_dot_credit(b: np.ndarray, dy, dx, k) -> np.ndarray:
    """E[max_g k(d(y,g))] at every pixel for one dot, under independent Bernoulli truth ``b``.

    Exact, not a Poisson approximation: P(no truth pixel above level t) = prod_j (1 - b_j),
    accumulated in log space over the 29-cell kernel support.
    """
    if np.nanmax(b) >= 1.0:
        b = np.clip(b, 0.0, 1.0 - 1e-12)   # keep log1p finite; P(no truth) -> 0 correctly
    lognone = np.zeros(b.shape, dtype=np.float64)   # sum_j log(1 - b_j) over the level set
    out = np.zeros(b.shape, dtype=np.float64)
    order = np.argsort(-k)
    levels = np.unique(k)[::-1]                     # L1 > L2 > ... > Lm > 0
    ptr = 0
    for i, lv in enumerate(levels):
        while ptr < order.size and float(k[order[ptr]]) >= float(lv) - 1e-15:
            j = int(order[ptr])
            # the kernel's offset set is symmetric, so this sums b over the same 29-cell
            # neighbourhood that coverage_gain uses (same sign convention)
            lognone += _shift_src(np.log1p(-b), int(dy[j]), int(dx[j]))
            ptr += 1
        nxt = float(levels[i + 1]) if i + 1 < levels.size else 0.0
        out += (float(lv) - nxt) * (1.0 - np.exp(lognone))
    return out


def coverage_gain(b: np.ndarray, cov: np.ndarray, dy, dx, k) -> np.ndarray:
    """gain(y) = sum_j b_j max(0, k_j - cov_j) over the 3 px support, for every y at once."""
    out = np.zeros(b.shape, dtype=np.float64)
    for i in range(dy.size):
        out += _shift_src(b * np.maximum(k[i] - cov, 0.0), int(dy[i]), int(dx[i]))
    return out


def greedy_emit(belief: np.ndarray, eligible: np.ndarray, budget: int = 60000,
                total_truth_mass: float | None = None, verbose: bool = False,
                min_belief: float = 0.0, batch: int = 4000) -> tuple[np.ndarray, dict]:
    """Boolean dot mask maximising expected DTI, plus a diagnostic dict.

    ``belief``: non-negative surface; NaN treated as 0.  ``eligible``: where dots may go.
    ``total_truth_mass``: assumed sum(b) = E|G|; if None the belief's own sum is used, which is
    the scale-free choice (only the ratio T/sum(b) matters for ranking dot sets).

    Implementation: round-batched lazy greedy.  Each round recomputes the exact coverage-gain
    field once over the whole grid, ranks it, and then re-checks the top ``batch`` candidates
    one at a time against the *current* coverage before accepting -- so clustering is caught
    exactly and only the global scalars (T, M, N, DTI) are stale within a round, by construction
    a few percent.  A zero-gain dot can never raise DTI (its denominator grows by 0.2(1-mu) >= 0)
    and a candidate's gain is non-increasing in time, so the stopping rule is sound.
    """
    b = np.nan_to_num(np.asarray(belief, dtype=np.float64), nan=0.0)
    b = np.where(eligible, np.maximum(b, 0.0), 0.0)
    if total_truth_mass is not None and total_truth_mass > 0 and b.sum() > 0:
        b = b * (float(total_truth_mass) / float(b.sum()))
    b_sum = float(b.sum())
    if b_sum <= 0:
        return np.zeros(b.shape, dtype=bool), {"emitted": 0, "expected_dti": 0.0}

    dy, dx, k = offsets()
    h, w = b.shape
    mu = expected_dot_credit(b, dy, dx, k).astype(np.float32)
    if min_belief > 0:
        mu = np.where(mu > min_belief, mu, np.float32(0.0))
    b32 = b.astype(np.float32)
    cov = np.zeros(b.shape, dtype=np.float32)
    dots = np.zeros(b.shape, dtype=bool)
    eight_b = _BETA * b_sum
    T = M = 0.0
    N = 0
    dti = 0.0
    rounds = 0

    while N < budget:
        rounds += 1
        gain = coverage_gain(b32, cov, dy, dx, k).astype(np.float32)
        with np.errstate(divide="ignore", invalid="ignore"):
            sc = (T + gain) / (_ALPHA * (T + gain)
                               + _ALPHA * (N + 1 - M - mu) + eight_b)
        sc = np.where((gain > 0) & (mu > 0) & ~dots, sc, np.float32(-1.0))
        live = int((sc > dti).sum())
        if live == 0:
            break
        q = int(min(batch, live))
        flat = sc.ravel()
        top = np.argpartition(flat, -q)[-q:]
        top = top[np.argsort(-flat[top])]
        added = 0
        for j in top.tolist():
            if N >= budget:
                break
            r, c = divmod(j, w)
            g = _local_gain(b, cov, r, c, dy, dx, k, h, w)
            if g <= 0:
                continue
            m_y = float(mu[r, c])
            new_dti = (T + g) / (_ALPHA * (T + g) + _ALPHA * (N + 1 - M - m_y) + eight_b)
            if new_dti <= dti + 1e-15:
                continue
            T += g
            M += m_y
            N += 1
            dti = new_dti
            dots[r, c] = True
            added += 1
            for i in range(dy.size):
                rr, cc = r + int(dy[i]), c + int(dx[i])
                if 0 <= rr < h and 0 <= cc < w and k[i] > cov[rr, cc]:
                    cov[rr, cc] = np.float32(k[i])
        if verbose:
            print(f"      round {rounds}: +{added:,} dots (total {N:,})  E[DTI]={dti:.4f}  "
                  f"live={live:,}", flush=True)
        if added == 0:
            break

    return dots, {"emitted": int(N), "expected_dti": float(dti),
                  "expected_tp": float(T), "expected_fp_mass": float(N - M),
                  "assumed_truth_mass": b_sum, "rounds": rounds}


def _local_gain(b, cov, r, c, dy, dx, k, h, w) -> float:
    tot = 0.0
    for i in range(dy.size):
        rr, cc = r + int(dy[i]), c + int(dx[i])
        if 0 <= rr < h and 0 <= cc < w:
            deficit = k[i] - float(cov[rr, cc])
            if deficit > 0:
                tot += float(b[rr, cc]) * deficit
    return tot


def greedy_emit_masked(belief, eligible, **kw):
    """Back-compatible alias kept for scripts that import the old name."""
    return greedy_emit(belief, eligible, **kw)[0]
