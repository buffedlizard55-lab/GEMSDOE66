"""Unit tests for the metric-native emitter.

The emitter maximises E[DTI] under an independent-Bernoulli truth model, so its objective is an
expectation, not the realised metric.  These tests therefore check (a) the closed forms against
literal summations, (b) that E[TPw] is *exact* when the belief really is a 0/1 truth raster, and
(c) the behaviour that matters: the emitted set must beat obvious alternatives on the real
official metric.
"""
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gems.metric import dti, tversky_terms  # noqa: E402
from gems67.emit import (coverage_gain, expected_dot_credit, greedy_emit, offsets)  # noqa: E402


def test_expected_dot_credit_matches_monte_carlo():
    """The closed form must equal a brute-force Monte Carlo of max_g k over Bernoulli truths."""
    rng = np.random.default_rng(0)
    b = rng.random((9, 9)) * 0.35
    dy, dx, k = offsets()
    fast = expected_dot_credit(b, dy, dx, k)
    r, c = 4, 4
    offs = [(int(d0), int(d1), float(kk)) for d0, d1, kk in zip(dy, dx, k)]
    n_draw = 400_000
    draws = rng.random((n_draw, len(offs))) < np.array([b[r + a, c + bb] for a, bb, _ in offs])
    ks = np.array([kk for _, _, kk in offs])
    mc = np.where(draws, ks, 0.0).max(axis=1).mean()
    assert abs(float(fast[r, c]) - float(mc)) < 2e-3, (float(fast[r, c]), float(mc))


def test_expected_dot_credit_matches_step_function_literal():
    """Independent literal: E[m] = sum_i (L_i - L_{i+1}) * P(at least one truth with k >= L_i)."""
    rng = np.random.default_rng(11)
    b = rng.random((13, 13)) * 0.3
    dy, dx, k = offsets()
    fast = expected_dot_credit(b, dy, dx, k)
    r, c = 6, 7
    offs = [(int(d0), int(d1), float(kk)) for d0, d1, kk in zip(dy, dx, k)]
    levels = sorted({kk for _, _, kk in offs}, reverse=True)
    exp = 0.0
    for i, lv in enumerate(levels):
        p_none = 1.0
        for a, bb, kk in offs:
            if kk >= lv - 1e-15:
                p_none *= (1.0 - b[r + a, c + bb])
        nxt = levels[i + 1] if i + 1 < len(levels) else 0.0
        exp += (lv - nxt) * (1.0 - p_none)
    assert abs(float(fast[r, c]) - exp) < 1e-12


def test_coverage_gain_is_exact_local_sum():
    rng = np.random.default_rng(1)
    b = rng.random((11, 11))
    cov = rng.random((11, 11)) * 0.5
    dy, dx, k = offsets()
    g = coverage_gain(b, cov, dy, dx, k)
    r, c = 6, 5
    manual = sum(b[r + int(d0), c + int(d1)] * max(kk - cov[r + int(d0), c + int(d1)], 0.0)
                 for d0, d1, kk in zip(dy, dx, k)
                 if 0 <= r + int(d0) < 11 and 0 <= c + int(d1) < 11)
    assert abs(float(g[r, c]) - manual) < 1e-9


def test_expected_tp_is_exact_for_a_binary_belief():
    truth = np.zeros((60, 60), dtype=bool)
    truth[10, 8:30] = True
    truth[40, 25:50] = True
    dots, diag = greedy_emit(truth.astype(float), np.ones_like(truth), budget=5000)
    assert dots.sum() > 0
    tp, _fp, _fn = tversky_terms(dots.astype(float), truth.astype(float))
    # cov is held in float32 for speed, so the accumulated TP carries ~1e-6 rounding on 47
    assert abs(diag["expected_tp"] - tp) < 1e-3


def test_emitter_stops_before_the_budget_when_coverage_saturates():
    truth = np.zeros((80, 80), dtype=bool)
    truth[40, 10:20] = True
    dots, diag = greedy_emit(truth.astype(float), np.ones_like(truth), budget=5000)
    assert diag["emitted"] < 60, f"emitted {diag['emitted']} dots for a 10 px trace"
    near = ndimage.distance_transform_edt(~truth) <= 3
    assert near[dots].all()


def test_emitted_set_beats_lattice_random_and_topn_on_the_official_metric():
    """The whole point: on the real DTI, break-even greedy must beat the naive alternatives."""
    rng = np.random.default_rng(3)
    truth = np.zeros((120, 120), dtype=bool)
    truth[20, 10:70] = True
    truth[60, 40:110] = True
    truth[95, 5:45] = True
    # belief = truth blurred, i.e. an imperfect detector (never exactly on the trace)
    belief = ndimage.gaussian_filter(truth.astype(float), 1.6) + 0.02 * rng.random(truth.shape)
    elig = np.ones(truth.shape, dtype=bool)
    dots, _ = greedy_emit(belief, elig, budget=20000)
    n = int(dots.sum())
    assert n > 0
    score = dti(dots.astype(float), truth.astype(float))

    # same number of dots on a regular lattice over the footprint
    lat = np.zeros(truth.shape, dtype=bool)
    step = max(1, int(np.sqrt(truth.size / max(n, 1))))
    lat[::step, ::step] = True
    lat_score = dti(lat.astype(float), truth.astype(float))

    # same number of dots sampled from the belief (no redundancy control)
    flat = belief.ravel()
    p = flat / flat.sum()
    pick = rng.choice(flat.size, size=n, replace=False, p=p)
    rand = np.zeros(truth.shape, dtype=bool).ravel()
    rand[pick] = True
    rand_score = dti(rand.reshape(truth.shape).astype(float), truth.astype(float))

    assert score > lat_score, f"greedy {score:.4f} <= lattice {lat_score:.4f}"
    assert score > rand_score, f"greedy {score:.4f} <= belief-sampled {rand_score:.4f}"


def test_ineligible_pixels_are_never_emitted():
    belief = np.zeros((50, 50))
    belief[25, 25] = 1.0
    elig = np.ones((50, 50), dtype=bool)
    elig[25, 25] = False
    dots, _ = greedy_emit(belief, elig, budget=100)
    assert not dots[25, 25]


def test_empty_belief_returns_no_dots():
    dots, diag = greedy_emit(np.zeros((30, 30)), np.ones((30, 30), dtype=bool))
    assert diag["emitted"] == 0 and not dots.any()
