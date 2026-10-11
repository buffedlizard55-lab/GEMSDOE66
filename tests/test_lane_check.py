import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from lane_check import lane_check  # noqa: E402

TF = from_origin(0.0, 0.0, 100.0, 100.0)


def _write(path, arr):
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                       dtype="float32", crs="EPSG:32611", transform=TF) as dst:
        dst.write(arr.astype(np.float32), 1)
    return path


def _dots(seed, n=60, shape=(80, 80)):
    rng = np.random.default_rng(seed)
    a = np.zeros(shape, np.float32)
    idx = rng.choice(shape[0] * shape[1], n, replace=False)
    a.flat[idx] = rng.random(n) * 0.9 + 0.05
    return a


def test_identical_raster_is_flagged(tmp_path):
    a = _dots(1)
    c = _write(tmp_path / "c.tif", a)
    r = _write(tmp_path / "r.tif", a.copy())
    rep = lane_check(c, [r])
    assert rep["comparisons"][0]["drift"] is True
    assert rep["verdict"].startswith("LANE DRIFT")


def test_shifted_dots_within_3px_are_flagged(tmp_path):
    a = _dots(2)
    b = np.roll(a, 2, axis=1)  # every dot moved 2 px: all within 3 px
    rep = lane_check(_write(tmp_path / "c.tif", a), [_write(tmp_path / "r.tif", b)])
    assert rep["comparisons"][0]["candidate_dots_within_3px"] > 0.7
    assert rep["comparisons"][0]["drift"] is True


def test_independent_raster_is_not_flagged(tmp_path):
    a = _dots(3)
    b = _dots(99)
    rep = lane_check(_write(tmp_path / "c.tif", a), [_write(tmp_path / "r.tif", b)])
    assert rep["comparisons"][0]["drift"] is False
    assert rep["verdict"] == "no drift vs supplied registry rasters"


def test_report_carries_hashes(tmp_path):
    a = _dots(4)
    c = _write(tmp_path / "c.tif", a)
    rep = lane_check(c, [_write(tmp_path / "r.tif", _dots(5))])
    assert len(rep["candidate_sha256"]) == 64
    assert len(rep["comparisons"][0]["sha256"]) == 64


def test_empty_candidate_is_inconclusive_not_a_pass(tmp_path):
    empty = np.zeros((80, 80), np.float32)
    rep = lane_check(_write(tmp_path / "c.tif", empty), [_write(tmp_path / "r.tif", _dots(6))])
    assert rep["verdict"].startswith("INCONCLUSIVE")
