import numpy as np
from gemsdoe66.emission import emit, dot_geometry, greedy_minsep


def _grid(n=120, seed=0):
    rng = np.random.default_rng(seed)
    field = rng.random((n, n)).astype(np.float32)
    fp = np.ones((n, n), bool)
    return field, fp


def test_minimum_separation_is_enforced():
    field, fp = _grid()
    dots = greedy_minsep(field, 300, fp, min_sep_px=2.82)
    g = dot_geometry(dots)
    assert g["nn_min_px"] >= 2.828 - 1e-6, g
    assert dots.sum() == 300


def test_budget_is_exact_when_room_exists():
    field, fp = _grid(200)
    dots = greedy_minsep(field, 100, fp, min_sep_px=2.82)
    assert int(dots.sum()) == 100


def test_budget_saturates_rather_than_breaking_separation():
    field, fp = _grid(20)
    dots = greedy_minsep(field, 10_000, fp, min_sep_px=2.82)
    g = dot_geometry(dots)
    assert g["nn_min_px"] >= 2.828 - 1e-6
    assert 0 < dots.sum() < 10_000


def test_exclude_is_respected():
    field, fp = _grid(120)
    ex = np.zeros((120, 120), bool)
    ex[:60, :] = True
    dots = greedy_minsep(field, 200, fp, exclude=ex, min_sep_px=2.82)
    assert not dots[:60, :].any()


def test_scatter_ranking_changes_placement():
    field, fp = _grid(160, seed=3)
    a = emit(field, 400, fp, min_sep_px=2.82)
    b = emit(field, 400, fp, min_sep_px=2.82, scatter_sigma=2.0)
    assert a.sum() == b.sum() == 400
    # both must still respect the separation rule, and they must not be identical
    assert dot_geometry(b)["nn_min_px"] >= 2.828 - 1e-6
    assert not np.array_equal(a, b)
