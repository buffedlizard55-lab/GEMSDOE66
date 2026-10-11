import numpy as np
from gemsdoe66.holdout import (bootstrap_ci, buffer_around, component_centroids,
                               fold_masks, folds_by_spatial_cluster)


def _lines():
    m = np.zeros((400, 400), bool)
    m[10:20, 50:120] = True          # component A
    m[200:210, 200:270] = True       # component B
    m[300:390, 300:302] = True       # component C
    return m


def test_components_are_the_unit_of_assignment():
    m = _lines()
    folds = folds_by_spatial_cluster(m, 4, n_clusters=3)
    assert (folds < 0).sum() > 0                     # background marked -1
    assert set(np.unique(folds[folds >= 0])) <= {0, 1, 2, 3}
    # every pixel of one connected component must land in one fold
    lab, n, *_ = component_centroids(m)
    assert n == 3
    for i in range(1, n + 1):
        assert np.unique(folds[lab == i]).size == 1


def test_background_is_never_fold_zero():
    m = _lines()
    folds = folds_by_spatial_cluster(m, 4, n_clusters=3)
    assert not np.any(folds[~m] >= 0)


def test_folds_disjoint_and_buffer_is_training_side():
    m = np.zeros((200, 200), bool)
    for r in range(5, 195, 20):
        m[r, 5:195] = True
    seen = []
    for f, truth, excl in fold_masks(m, 4):
        assert truth.any()
        assert (excl & truth).sum() == truth.sum()     # buffer contains the truth
        seen.append(truth)
    for i in range(len(seen)):
        for j in range(i + 1, len(seen)):
            assert not (seen[i] & seen[j]).any()


def test_buffer_radius():
    m = np.zeros((50, 50), bool)
    m[25, 25] = True
    b = buffer_around(m, 3.0)
    assert b.sum() > 25 and b[25, 25] and b[22, 25] and not b[20, 25]


def test_bootstrap_ci_brackets_the_mean():
    rng = np.random.default_rng(0)
    v = rng.normal(0.5, 0.1, 40)
    lo, hi = bootstrap_ci(v, n_boot=500, seed=1)
    assert lo < v.mean() < hi
