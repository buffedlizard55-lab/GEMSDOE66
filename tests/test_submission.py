import json
from pathlib import Path

import numpy as np
import rasterio
import pytest

from gemsdoe66.grid import (EXPECTED_CRS, EXPECTED_SHAPE, EXPECTED_TRANSFORM,
                            catalogue_mask, footprint_mask)
from gemsdoe66.submission import to_submission_array, write_submission
from gemsdoe66.validate_submission import validate

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_SUBMISSION = ROOT / "data" / "raw" / "sample_submission.tif"
pytestmark = pytest.mark.skipif(
    not SAMPLE_SUBMISSION.is_file(),
    reason="requires the authorized official sample_submission.tif, which is absent locally",
)


def test_to_submission_array_clips_and_nulls():
    fp = footprint_mask()
    a = np.zeros(fp.shape, np.float32)
    a[0, 0] = 5.0        # inside? row0 col0 is outside the footprint for most grids
    a[1000, 1000] = 2.0
    a[1001, 1000] = -1.0
    out = to_submission_array(a, mode="nan", footprint=fp)
    assert out.dtype == np.float32
    assert np.nanmax(out) <= 1.0 and np.nanmin(out) >= 0.0
    assert np.isnan(out[~fp]).all()


def test_roundtrip_passes_validator(tmp_path):
    fp = footprint_mask()
    rng = np.random.default_rng(0)
    v = np.zeros(fp.shape, np.float32)
    idx = np.flatnonzero(fp.ravel())
    sel = rng.choice(idx, 5000, replace=False)
    v.flat[sel] = 1.0
    p = tmp_path / "t.tif"
    write_submission(v, p, mode="nan")
    r = validate(p, mode="nan")
    assert r["ok"], r["checks"]
    assert r["stats"]["positive_pixels"] == 5000
    with rasterio.open(p) as src:
        assert src.dtypes[0] == "float32"
        assert src.crs.to_string() == EXPECTED_CRS
        assert (src.height, src.width) == EXPECTED_SHAPE
        assert tuple(src.transform)[:6] == pytest.approx(EXPECTED_TRANSFORM)


def test_zeros_mode_passes(tmp_path):
    fp = footprint_mask()
    v = np.zeros(fp.shape, np.float32)
    v[fp] = 0.5
    p = tmp_path / "z.tif"
    write_submission(v, p, mode="zeros")
    r = validate(p, mode="zeros")
    assert r["ok"], r["checks"]


def test_validator_rejects_out_of_range(tmp_path):
    fp = footprint_mask()
    v = np.zeros(fp.shape, np.float32)
    v[fp] = 1.5
    p = tmp_path / "bad.tif"
    write_submission(v, p, mode="nan")          # writer clips, so this must pass
    r = validate(p, mode="nan")
    assert r["checks"]["in_footprint_range_0_1"]
    # a hand-made raster that is NOT clipped must fail
    prof = dict(driver="GTiff", height=EXPECTED_SHAPE[0], width=EXPECTED_SHAPE[1], count=1,
                dtype="float32", crs=EXPECTED_CRS,
                transform=rasterio.transform.Affine(*EXPECTED_TRANSFORM))
    with rasterio.open(tmp_path / "bad2.tif", "w", **prof) as dst:
        dst.write(v, 1)
    r2 = validate(tmp_path / "bad2.tif", mode="nan")
    assert not r2["checks"]["in_footprint_range_0_1"]


def test_shipped_artifact_passes_if_present():
    dls = sorted((ROOT / "artifacts" / "lidar_lane").glob("*.manifest.json"))
    if not dls:
        pytest.skip("no submission built")
    man = json.loads(dls[-1].read_text())
    slug = man["slug"]
    for mode in ("nan", "zeros"):
        p = ROOT / "artifacts" / "lidar_lane" / f"{slug}-{mode}.tif"
        r = validate(p, mode=mode, require_off_catalogue=2.0,
                     expected_dots=man["n_dots"])
        assert r["ok"], (mode, r["checks"])
