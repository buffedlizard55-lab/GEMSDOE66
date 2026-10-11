"""Tests for the distance-weighted Tversky index.

Covers: the published worked example, kernel support, equivalence of the fast
implementation with a literal brute-force transcription, the exact identities the
break-even analysis relies on, and the marginal break-even rule (k > alpha * DTI).
"""

import numpy as np
import pytest

from gems.metric import (dti, dti_from_terms, kernel, marginal_credit_bar,
                         tversky_terms, tversky_terms_bruteforce)


def test_kernel_support_and_values():
    assert kernel(0.0) == 1.0
    assert kernel(150.0) == pytest.approx(0.5)
    assert kernel(300.0) == 0.0
    assert kernel(450.0) == 0.0


def test_worked_example_from_official_page():
    # Problem page: TP_w = 3.00, FP_w = 1.89, FN_w = 2.00  ->  TI_w(0.2, 0.8) = 0.60
    assert round(dti_from_terms(3.00, 1.89, 2.00), 2) == 0.60


def test_perfect_prediction_scores_one():
    g = np.zeros((20, 20), int)
    g[5, 2:15] = 1
    assert dti(g.astype(float), g) == pytest.approx(1.0, abs=1e-6)


def test_empty_prediction_scores_zero():
    g = np.zeros((20, 20), int)
    g[5, 2:15] = 1
    assert dti(np.zeros((20, 20)), g) == 0.0


def test_no_ground_truth_scores_zero_and_all_mass_is_fp():
    p = np.zeros((10, 10))
    p[3, 3] = 0.5
    tp, fp, fn = tversky_terms(p, np.zeros((10, 10), int))
    assert (tp, fn) == (0.0, 0.0)
    assert fp == pytest.approx(0.5)
    assert dti(p, np.zeros((10, 10), int)) == 0.0


def test_one_pixel_offset_gets_partial_credit():
    g = np.zeros((9, 9), int)
    g[4, 4] = 1
    p = np.zeros((9, 9))
    p[4, 5] = 1.0  # 100 m away -> k = 2/3
    tp, fp, fn = tversky_terms(p, g)
    assert tp == pytest.approx(2 / 3)
    assert fn == pytest.approx(1 / 3)
    assert fp == pytest.approx(1 - 2 / 3)


def test_out_of_range_predictions_are_rejected():
    g = np.zeros((5, 5), int)
    with pytest.raises(ValueError):
        dti(np.full((5, 5), 1.2), g)
    with pytest.raises(ValueError):
        dti(np.full((5, 5), -0.1), g)


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_fast_matches_bruteforce(seed):
    rng = np.random.default_rng(seed)
    h, w = 14, 16
    g = (rng.random((h, w)) < 0.06).astype(int)
    if g.sum() == 0:
        g[3, 3] = 1
    p = rng.random((h, w)) * (rng.random((h, w)) < 0.25)
    p[rng.random((h, w)) < 0.05] = 1.0
    fast = tversky_terms(p, g)
    slow = tversky_terms_bruteforce(p, g)
    assert np.allclose(fast, slow, atol=1e-9)


@pytest.mark.parametrize("seed", [0, 5, 9])
def test_identities(seed):
    """TP_w + FN_w = |G|, and DTI = T / (0.2 (T + S - M) + 0.8 |G|) with M computed independently."""
    from scipy import ndimage

    rng = np.random.default_rng(seed)
    h, w = 30, 30
    g = (rng.random((h, w)) < 0.03).astype(int)
    g[10, 10] = 1
    p = rng.random((h, w)) * (rng.random((h, w)) < 0.2)
    tp, fp, fn = tversky_terms(p, g)
    n_g = int(g.sum())
    assert tp + fn == pytest.approx(n_g, abs=1e-9)
    # Independent M = sum_x p(x) max_g k(d(x,g)), computed from a distance transform of the truth
    dist = ndimage.distance_transform_edt(g == 0) * 100.0
    m_sum = float(np.sum(p * kernel(dist)))
    s_sum = float(p.sum())
    assert fp == pytest.approx(s_sum - m_sum, abs=1e-9)
    alt = tp / (0.2 * (tp + s_sum - m_sum) + 0.8 * n_g)
    assert dti(p, g) == pytest.approx(alt, rel=1e-6)


def _dti_with_dots(base_pred, gt, extra=None):
    p = base_pred.copy()
    if extra is not None:
        p[extra] = 1.0
    return dti(p, gt)


@pytest.mark.parametrize("off", [(0, 0), (0, 1), (1, 1), (0, 2), (2, 1), (2, 2), (0, 3), (3, 0), (2, 2)])
def test_marginal_break_even_rule(off):
    """A dot that becomes the nearest emission to an uncovered truth pixel raises DTI iff k > 0.2 DTI."""
    h, w = 40, 40
    g = np.zeros((h, w), int)
    g[5, 5] = 1          # g1, covered by the base prediction
    g[30, 30] = 1        # g2, uncovered; candidate dot placed near it
    base = np.zeros((h, w))
    base[5, 5] = 1.0     # covers g1 fully
    cand = (30 + off[0], 30 + off[1])
    d_px = np.hypot(*off)
    k = float(kernel(100.0 * d_px))
    d0 = _dti_with_dots(base, g)
    d1 = _dti_with_dots(base, g, extra=cand)
    bar = marginal_credit_bar(d0)
    if abs(k - bar) < 1e-9:
        pytest.skip("exact tie")
    assert (d1 > d0) == (k > bar), f"k={k:.4f} bar={bar:.4f} d0={d0:.4f} d1={d1:.4f}"


def test_breakeven_distance_for_base_example():
    # Base DTI 0.5556 (one of two truth pixels covered): break-even distance is 300(1-0.2*DTI0) ~ 266.7 m.
    d0 = 1.0 / (1.0 + 0.8 * 1.0)
    d_star = 300.0 * (1.0 - marginal_credit_bar(d0))
    assert d_star == pytest.approx(266.67, abs=0.01)
