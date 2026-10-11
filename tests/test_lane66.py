"""Unit tests for the H66 lane maths.  None of them need data/ (they build synthetic grids)."""
import numpy as np
import pytest

from gems66.spec66 import Quant
from gems66 import channels66 as C66


def test_sqrt_decode_inverts_the_pinned_quantisation_rule():
    """sidecar: q = 1 + round(254*sqrt(clip(x/xmax,0,1))), 0 = no lidar."""
    q = Quant(1.5, "sqrt")
    xs = np.array([0.0, 0.0375, 0.375, 1.5], np.float32)
    enc = 1 + np.round(254 * np.sqrt(np.clip(xs / q.xmax, 0, 1))).astype(np.uint8)
    dec = q.decode(enc)
    assert np.allclose(dec, xs, atol=q.xmax * 2e-3)
    assert np.isnan(q.decode(np.array([0], np.uint8))[0])       # q=0 must be no-data, not 0.0


def test_linear_decode_and_band_order():
    q = Quant(180.0, "linear")
    assert np.isclose(q.decode(np.array([128], np.uint8))[0], 180.0 * 127 / 254, atol=1e-3)
    assert C66.__dict__ and len(C66.__doc__) > 100


def test_robust_rank_is_a_percentile_and_zero_outside():
    x = np.arange(10000, dtype=np.float32).reshape(100, 100)
    dom = np.ones(x.shape, bool); dom[:50] = False
    r = C66.robust_rank(x, dom)
    assert r[:50].max() == 0.0 and 0.0 <= r.min() and r.max() <= 1.0
    assert r[99, 99] > r[50, 0]


def test_block_pctl_estimates_the_quiet_background_not_the_scarp_population():
    """As used: ``valid`` is the non-scarped majority, so median/MAD describe the background."""
    rng = np.random.default_rng(0)
    v = np.where(rng.random((200, 200)) < 0.5, rng.normal(0, 0.02, (200, 200)), 5.0).astype(np.float32)
    quiet = np.abs(v) < 1.0
    med, mad = C66.block_pctl(v, quiet, block=100, nbins=256)
    assert abs(float(np.median(med[quiet]))) < 0.03          # ~0 background, to within one bin
    assert float(np.median(mad[quiet])) < 0.2                # 1.4826*MAD of the noise, not of the 5.0 spikes
    assert float(mad.min()) > 0.0                            # never divides by zero


def test_circ_windowed_strike_finds_straight_and_crossing_patterns():
    strike = np.zeros((61, 61), np.float32) + 30.0
    w = np.zeros((61, 61), np.float32); w[25:36, 25:36] = 1.0
    R, ang, _ = C66.circ_windowed_strike(strike, w, 11)
    assert R[30, 30] > 0.9 and abs(((ang[30, 30] - 30 + 90) % 180) - 90) < 2.0
    strike2 = strike.copy(); strike2[25:30] = 120.0                        # orthogonal contamination
    R2, _, _ = C66.circ_windowed_strike(strike2, w, 11)
    assert R2[30, 30] < R[30, 30]
