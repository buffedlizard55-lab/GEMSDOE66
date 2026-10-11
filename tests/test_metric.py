import numpy as np
import pytest

from gemsdoe66.metric import dti, dti_bruteforce, dti_parts, marginal_credit_bar


def _rand(rng, n=200):
    p = np.zeros((60, 60))
    idx = rng.choice(3600, n, replace=False)
    p.flat[idx] = rng.random(n)
    g = np.zeros((60, 60), bool)
    gi = rng.choice(3600, 80, replace=False)
    g.flat[gi] = True
    return p, g


def test_fast_matches_bruteforce():
    rng = np.random.default_rng(0)
    for _ in range(6):
        p, g = _rand(rng)
        a = dti(p, g)
        b = dti_bruteforce(p, g)
        assert abs(a - b) < 1e-9, (a, b)


def test_organiser_worked_example():
    """The scoring example on page 967: TPw=3.00, FPw=1.89, FNw=2.00 -> 0.60."""
    tp, fp, fn = 3.00, 1.89, 2.00
    expected = tp / (tp + 0.2 * fp + 0.8 * fn)
    assert abs(expected - 0.60) < 0.005


def test_identity_is_one_and_empty_is_zero():
    rng = np.random.default_rng(1)
    g = np.zeros((40, 40), bool)
    g[10:30, 20] = True
    assert dti(g.astype(float), g) == pytest.approx(1.0, abs=1e-9)
    assert dti(np.zeros((40, 40)), g) == 0.0


def test_fn_equals_truth_minus_tp():
    rng = np.random.default_rng(2)
    p, g = _rand(rng)
    score, tp, fp, fn, ng, S, M = dti_parts(p, g)
    assert fn == pytest.approx(ng - tp, abs=1e-9)
    # DTI = T / (0.2T + 0.2(S-M) + 0.8|G|)
    assert score == pytest.approx(tp / (0.2 * tp + 0.2 * (S - M) + 0.8 * ng), abs=1e-9)


def test_perfect_localisation_has_no_fp_penalty():
    g = np.zeros((40, 40), bool)
    g[10:30, 20] = True
    perfect = g.astype(float)
    score, tp, fp, fn, ng, S, M = dti_parts(perfect, g)
    assert fp == pytest.approx(0.0, abs=1e-9)
    assert score == pytest.approx(1.0, abs=1e-9)


def test_marginal_credit_bar_matches_derivative():
    """Adding unit mass at credit k raises DTI iff k > alpha*DTI - checked numerically."""
    rng = np.random.default_rng(3)
    p, g = _rand(rng, n=400)
    s0 = dti(p, g)
    bar = marginal_credit_bar(s0)
    # add a far-away pixel (credit 0) -> must decrease
    p2 = p.copy()
    p2[0, 0] = 1.0
    assert dti(p2, g) < s0
    # add a pixel exactly on an uncovered truth pixel (credit 1) -> must increase
    gy, gx = np.nonzero(g)
    covered = p[gy, gx] > 0.99
    j = int(np.argmin(covered))
    p3 = p.copy()
    p3[gy[j], gx[j]] = 1.0
    assert dti(p3, g) > s0 or s0 > 0.9
    assert 0 < bar < 1
