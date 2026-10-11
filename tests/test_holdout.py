import numpy as np

from gems.holdout import spatial_block_ids, split_fault_segments


def _fault_mask():
    m = np.zeros((60, 60), bool)
    m[10, 5:25] = True          # segment A
    m[30:50, 40] = True         # segment B
    m[50, 5:15] = True          # segment C
    return m


def test_split_partitions_faults_and_never_leaks_held_segments():
    m = _fault_mask()
    s = split_fault_segments(m, holdout_fraction=0.34, buffer_px=2, seed=1)
    v, h, dropped = s["visible"], s["holdout"], s["buffer_dropped"]
    assert not (v & h).any()                      # no visible pixel is a withheld pixel
    assert (h <= m).all() and (v <= m).all()
    assert ((v | h | dropped) == m).all()         # every fault pixel is accounted for
    assert len(s["held_segment_ids"]) == 1


def test_buffer_removes_visible_faults_near_holdout():
    m = _fault_mask()
    s = split_fault_segments(m, holdout_fraction=0.34, buffer_px=3, seed=2)
    from scipy import ndimage
    d = ndimage.distance_transform_edt(~s["holdout"])
    assert not (s["visible"] & (d <= 3)).any()


def test_spatial_blocks_are_contiguous():
    ids = spatial_block_ids((10, 12), block_px=5)
    assert ids.shape == (10, 12)
    assert len(np.unique(ids)) == 2 * 3
    assert (ids[:5, :5] == ids[0, 0]).all()


from gems.holdout import spatial_block_holdout  # noqa: E402


def test_block_holdout_withholds_whole_eligible_blocks_only():
    m = _fault_mask()
    lidar = np.zeros_like(m)
    lidar[:, :] = True
    lidar[:10, :] = False     # first block row has no lidar: must never be chosen
    s = spatial_block_holdout(m, lidar, block_px=15, holdout_fraction=0.5, buffer_px=2, seed=3)
    assert s["holdout_fault_cells"] > 0
    assert not (s["visible"] & s["holdout"]).any()
    assert ((s["visible"] | s["holdout"] | s["buffer_dropped"]) == m).all()
    from gems.holdout import spatial_block_ids
    ids = spatial_block_ids(m.shape, 15)
    for b in s["held_block_ids"]:
        cells = ids == b
        assert lidar[cells].mean() >= 0.9       # only lidar-covered blocks are withheld
        assert not (s["visible"] & cells).any()  # held blocks carry no visible faults


def test_block_holdout_buffer_removes_nearby_visible_faults():
    from scipy import ndimage
    m = _fault_mask()
    lidar = np.ones_like(m)
    s = spatial_block_holdout(m, lidar, block_px=20, holdout_fraction=0.4, buffer_px=3, seed=7)
    d = ndimage.distance_transform_edt(~s["holdout"])
    assert not (s["visible"] & (d <= 3)).any()


def test_block_holdout_is_deterministic_for_seed():
    m = _fault_mask()
    lidar = np.ones_like(m)
    a = spatial_block_holdout(m, lidar, 15, 0.5, 2, seed=11)
    b = spatial_block_holdout(m, lidar, 15, 0.5, 2, seed=11)
    assert a["held_block_ids"] == b["held_block_ids"]
