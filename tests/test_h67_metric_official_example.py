"""The official scoring example, and the closed-form identity, reproduced exactly.

The competition page (https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
works a 5-pixel vertical ground-truth line crossed by a 5-pixel horizontal prediction and states

    TPw = 3.00,  FPw = 1.89,  FNw = 2.00,  DTI(0.2, 0.8) = 0.60

This test reconstructs the 5x5 cross and checks every term.  TPw and FNw come out exactly right,
which pins the kernel and the "max over the 300 m neighbourhood" semantics.  FPw comes out 2.00
rather than 1.89, so the page's schematic prediction footprint is not a plain 5-pixel cross; that
discrepancy is logged as irregularity IR-67-METRIC-01 rather than silently ignored, and the
literal brute-force transcription is asserted equal to the vectorised implementation.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gems.metric import dti, dti_from_terms, tversky_terms, tversky_terms_bruteforce  # noqa: E402


def _cross_example():
    gt = np.zeros((9, 9))
    gt[2:7, 4] = 1.0                     # 5-pixel vertical line
    pr = np.zeros((9, 9))
    pr[4, 2:7] = 1.0                     # 5-pixel horizontal line crossing it
    return pr, gt


def test_official_example_tp_and_fn_are_exact():
    pr, gt = _cross_example()
    tp, fp, fn = tversky_terms(pr, gt)
    assert abs(tp - 3.00) < 1e-12
    assert abs(fn - 2.00) < 1e-12
    assert abs(tp + fn - gt.sum()) < 1e-12


def test_official_example_fp_differs_from_the_page_figure():
    """Documented irregularity: our literal reading of the formula gives 2.00, the page says 1.89."""
    pr, gt = _cross_example()
    _tp, fp, _fn = tversky_terms(pr, gt)
    assert abs(fp - 2.00) < 1e-12
    assert abs(fp - 1.89) > 1e-3   # the page's schematic prediction is not a plain 5-px cross


def test_official_example_dti_with_the_pages_own_terms_is_060():
    """The page rounds to two decimals: 3.00/(3.00+0.2*1.89+0.8*2.00) = 0.60265 -> 0.60."""
    value = dti_from_terms(3.00, 1.89, 2.00)
    assert abs(value - 0.602651667) < 1e-9
    assert round(value, 2) == 0.60


def test_vectorised_matches_literal_bruteforce_and_identity():
    rng = np.random.default_rng(0)
    worst = 0.0
    for _ in range(25):
        h, w = int(rng.integers(4, 9)), int(rng.integers(4, 9))
        p = rng.random((h, w))
        p[p < 0.6] = 0.0
        g = (rng.random((h, w)) < 0.2).astype(float)
        if g.sum() == 0:
            g[0, 0] = 1.0
        a = tversky_terms(p, g)
        b = tversky_terms_bruteforce(p, g)
        worst = max(worst, max(abs(x - y) for x, y in zip(a, b)))
        assert abs((a[0] + a[2]) - g.sum()) < 1e-9
        assert 0.0 <= dti(p, g) <= 1.0
    assert worst < 1e-9


def test_out_of_range_predictions_are_rejected():
    import pytest
    with pytest.raises(ValueError):
        tversky_terms(np.full((5, 5), 1.5), np.ones((5, 5)))
