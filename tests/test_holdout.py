import numpy as np
import pytest
from scipy import ndimage

from gems.holdout import spatial_block_ids, spatial_block_holdout, split_fault_segments


def _fault_mask():
    m = np.zeros((60, 60), bool)
    m[10, 5:25] = True          # segment A
    m[30:50, 40] = True         # segment B
    m[50, 5:15] = True          # segment C
    return m


def _accounted(split, original):
    accounted = (split["visible"] | split["holdout"] |
                 split["unscored_withheld"] | split["buffer_dropped"])
    assert np.array_equal(accounted, original)


def test_split_partitions_whole_fault_components_without_leakage():
    m = _fault_mask()
    s = split_fault_segments(m, holdout_fraction=0.34, buffer_px=2, seed=1)
    assert not (s["visible"] & s["holdout"]).any()
    assert np.array_equal(s["held_segment"], s["holdout"])
    _accounted(s, m)
    assert len(s["held_segment_ids"]) == 1
    assert s["segment_id_source"] == "8-connected components (proxy)"


def test_component_buffer_drops_nearby_visible_faults():
    m = _fault_mask()
    s = split_fault_segments(m, holdout_fraction=0.34, buffer_px=3, seed=2)
    d = ndimage.distance_transform_edt(~s["held_segment"])
    assert not (s["visible"] & (d <= 3)).any()
    _accounted(s, m)


def test_spatial_blocks_are_contiguous_and_validate_size():
    ids = spatial_block_ids((10, 12), block_px=5)
    assert ids.shape == (10, 12)
    assert len(np.unique(ids)) == 2 * 3
    assert (ids[:5, :5] == ids[0, 0]).all()
    with pytest.raises(ValueError):
        spatial_block_ids((10, 12), block_px=0)


def test_block_holdout_uses_lidar_covered_blocks_and_accounts_for_all_faults():
    m = _fault_mask()
    lidar = np.ones_like(m)
    lidar[:10, :] = False     # first block row is not sufficiently covered
    s = spatial_block_holdout(m, lidar, block_px=15, holdout_fraction=0.5,
                              buffer_px=2, seed=3)
    assert s["holdout_fault_cells"] > 0
    assert not (s["visible"] & s["held_segment"]).any()
    assert not (s["visible"] & s["holdout"]).any()
    assert (s["holdout"] <= lidar).all()
    _accounted(s, m)
    ids = spatial_block_ids(m.shape, 15)
    for b in s["held_block_ids"]:
        cells = ids == b
        assert lidar[cells].mean() >= 0.9
        assert not (s["visible"] & cells).any()
    assert s["unscored_withheld_fault_cells"] == int(s["unscored_withheld"].sum())


def test_block_holdout_buffer_covers_complete_held_segment():
    m = np.zeros((60, 60), bool)
    m[20, 5:55] = True  # one connected segment crosses a 30-pixel block boundary
    lidar = np.ones_like(m)
    s = spatial_block_holdout(m, lidar, block_px=30, holdout_fraction=0.5,
                              buffer_px=3, seed=7)
    assert s["eligible_block_count"] == 2
    assert len(s["held_block_ids"]) == 1
    assert s["held_segment"].sum() == m.sum()  # far tail is withheld, not leaked into features
    assert s["unscored_withheld_fault_cells"] > 0  # only selected block positives are scored
    assert s["holdout_fault_cells"] > 0
    d = ndimage.distance_transform_edt(~s["held_segment"])
    assert not (s["visible"] & (d <= 3)).any()
    assert not s["visible"].any()
    _accounted(s, m)


def test_explicit_segment_ids_keep_disconnected_parts_together():
    m = np.zeros((60, 60), bool)
    m[5, 5:12] = True
    m[50, 45:52] = True
    segment_ids = np.zeros(m.shape, dtype=np.int32)
    segment_ids[m] = 42  # authoritative ID says these raster fragments are one segment
    s = spatial_block_holdout(m, np.ones_like(m), block_px=20, holdout_fraction=0.5,
                              buffer_px=0, seed=1, segment_ids=segment_ids)
    assert s["segment_id_source"] == "provided integer segment IDs"
    assert s["held_segment_ids"] == [42]
    assert s["held_segment"].sum() == m.sum()
    assert s["unscored_withheld_fault_cells"] > 0
    _accounted(s, m)


def test_spatial_block_split_is_deterministic():
    m = _fault_mask()
    lidar = np.ones_like(m)
    a = spatial_block_holdout(m, lidar, 15, 0.5, 2, seed=11)
    b = spatial_block_holdout(m, lidar, 15, 0.5, 2, seed=11)
    assert a["held_block_ids"] == b["held_block_ids"]
    assert a["held_segment_ids"] == b["held_segment_ids"]


def test_invalid_split_parameters_are_rejected():
    m = _fault_mask()
    lidar = np.ones_like(m)
    with pytest.raises(ValueError):
        split_fault_segments(m, holdout_fraction=1.1, buffer_px=0, seed=0)
    with pytest.raises(ValueError):
        spatial_block_holdout(m, lidar, block_px=10, holdout_fraction=0.5,
                              buffer_px=-1, seed=0)
    with pytest.raises(ValueError):
        spatial_block_holdout(m, lidar, block_px=10, holdout_fraction=0.5,
                              buffer_px=0, seed=0, min_lidar_fraction=1.1)


def test_shape_mismatch_and_bad_segment_ids_are_rejected():
    m = _fault_mask()
    with pytest.raises(ValueError):
        spatial_block_holdout(m, np.ones((2, 2), bool), 10, 0.5, 1, 0)
    bad_ids = np.zeros(m.shape, dtype=np.int32)
    with pytest.raises(ValueError):
        spatial_block_holdout(m, np.ones_like(m), 10, 0.5, 1, 0, segment_ids=bad_ids)
