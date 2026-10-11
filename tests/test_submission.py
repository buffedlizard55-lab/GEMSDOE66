"""Writer/validator tests on synthetic rasters (no competition data needed)."""

import json

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from gems.submission_writer import write_submission
from gems.validate_submission import validate

H, W = 12, 15
TF = from_origin(500000.0, 4500000.0, 100.0, 100.0)


@pytest.fixture()
def reference(tmp_path):
    p = tmp_path / "labels_ref.tif"
    arr = np.zeros((H, W), dtype=np.int32)
    with rasterio.open(p, "w", driver="GTiff", height=H, width=W, count=1, dtype="int32",
                       crs="EPSG:32611", transform=TF, nodata=-1) as dst:
        dst.write(arr, 1)
    return p


@pytest.fixture()
def features(tmp_path, footprint):
    """A features raster whose first band is finite inside the footprint and the nodata sentinel outside."""
    p = tmp_path / "features.tif"
    band = np.where(footprint, 1.0, -3.4028234663852886e38).astype(np.float32)
    with rasterio.open(p, "w", driver="GTiff", height=H, width=W, count=1, dtype="float32",
                       crs="EPSG:32611", transform=TF, nodata=-3.4028234663852886e38) as dst:
        dst.write(band, 1)
    return p


@pytest.fixture()
def footprint():
    fp = np.ones((H, W), bool)
    fp[:, -2:] = False
    return fp


def test_writer_output_passes_validator(tmp_path, reference, footprint, features):
    pred = np.random.default_rng(0).random((H, W))
    out = tmp_path / "sub.tif"
    receipt = write_submission(out, pred, footprint, reference,
                               name="gems_test_01", note="synthetic grid test, not a submission")
    assert receipt["nan_inside"] == 0
    assert receipt["nan_outside_count"] == int((~footprint).sum())
    assert receipt["name"] == "gems_test_01" and receipt["note_chars"] == len("synthetic grid test, not a submission")
    rep = validate(out, reference_path=reference, features_path=features)
    assert rep["passed"], rep
    assert not rep["skipped_checks_mean_unverified"]
    with rasterio.open(out) as src:
        assert src.tags()["GEMS_NAME"] == "gems_test_01"
        assert src.tags()["GEMS_NOTE"].startswith("synthetic grid test")
    with rasterio.open(out) as src:
        assert src.dtypes[0] == "float32"
        assert src.nodata is None
        assert src.crs.to_string() == "EPSG:32611"
        assert src.transform == TF
        arr = src.read(1)
    assert np.isnan(arr[~footprint]).all()
    assert np.isfinite(arr[footprint]).all()
    assert arr[footprint].min() >= 0 and arr[footprint].max() <= 1
    # receipt file is written next to the submission
    assert json.loads((tmp_path / "sub.tif.receipt.json").read_text())["sha256"] == receipt["sha256"]


def test_writer_refuses_values_outside_unit_interval(tmp_path, reference, footprint):
    pred = np.full((H, W), 0.5)
    pred[0, 0] = 1.4
    with pytest.raises(ValueError):
        write_submission(tmp_path / "bad.tif", pred, footprint, reference)


def test_writer_refuses_nan_inside_footprint(tmp_path, reference, footprint):
    pred = np.full((H, W), 0.5)
    pred[0, 0] = np.nan
    with pytest.raises(ValueError):
        write_submission(tmp_path / "bad.tif", pred, footprint, reference)


def test_writer_refuses_note_over_140_chars(tmp_path, reference, footprint):
    pred = np.zeros((H, W))
    with pytest.raises(ValueError):
        write_submission(tmp_path / "n.tif", pred, footprint, reference, note="x" * 141)
    write_submission(tmp_path / "n2.tif", pred, footprint, reference, note="x" * 140)


def test_skipped_checks_do_not_pass(tmp_path, reference, footprint):
    """A file checked without features is NOT a full pass, so it cannot clear the gate."""
    pred = np.zeros((H, W))
    out = tmp_path / "s.tif"
    write_submission(out, pred, footprint, reference)
    rep = validate(out, reference_path=reference)  # no features raster
    assert rep["skipped_checks_mean_unverified"]
    assert rep["passed"] is False
    assert rep["has_failures"] is False


def test_writer_refuses_existing_file_without_overwrite(tmp_path, reference, footprint):
    pred = np.zeros((H, W))
    write_submission(tmp_path / "a.tif", pred, footprint, reference)
    with pytest.raises(FileExistsError):
        write_submission(tmp_path / "a.tif", pred, footprint, reference)


def test_validator_rejects_out_of_range_values(tmp_path, reference):
    out = tmp_path / "oob.tif"
    arr = np.full((H, W), 0.2, dtype=np.float32)
    arr[3, 3] = 1.7
    with rasterio.open(out, "w", driver="GTiff", height=H, width=W, count=1, dtype="float32",
                       crs="EPSG:32611", transform=TF, nodata=None) as dst:
        dst.write(arr, 1)
    rep = validate(out, reference_path=reference)
    assert not rep["passed"]
    assert any(c["check"] == "values within [0, 1]" and c["status"] == "FAIL" for c in rep["checks"])


def test_validator_rejects_large_negative_nodata_sentinel(tmp_path, reference):
    out = tmp_path / "sentinel.tif"
    arr = np.full((H, W), 0.2, dtype=np.float32)
    with rasterio.open(out, "w", driver="GTiff", height=H, width=W, count=1, dtype="float32",
                       crs="EPSG:32611", transform=TF, nodata=-3.4028234663852886e38) as dst:
        dst.write(arr, 1)
    rep = validate(out, reference_path=reference)
    assert not rep["passed"]
    assert any(c["check"] == "nodata tag is none or NaN" and c["status"] == "FAIL" for c in rep["checks"])


def test_validator_rejects_wrong_crs(tmp_path, reference):
    out = tmp_path / "wgs.tif"
    arr = np.zeros((H, W), dtype=np.float32)
    with rasterio.open(out, "w", driver="GTiff", height=H, width=W, count=1, dtype="float32",
                       crs="EPSG:4326", transform=TF, nodata=None) as dst:
        dst.write(arr, 1)
    rep = validate(out, reference_path=reference)
    assert not rep["passed"]
    assert any(c["check"] == "CRS EPSG:32611" and c["status"] == "FAIL" for c in rep["checks"])


def test_validator_flags_shape_mismatch(tmp_path, reference):
    out = tmp_path / "small.tif"
    arr = np.zeros((H - 1, W), dtype=np.float32)
    with rasterio.open(out, "w", driver="GTiff", height=H - 1, width=W, count=1, dtype="float32",
                       crs="EPSG:32611", transform=TF, nodata=None) as dst:
        dst.write(arr, 1)
    rep = validate(out, reference_path=reference)
    assert not rep["passed"]


def test_skipped_checks_are_reported_not_passed(tmp_path):
    out = tmp_path / "noref.tif"
    arr = np.zeros((H, W), dtype=np.float32)
    with rasterio.open(out, "w", driver="GTiff", height=H, width=W, count=1, dtype="float32",
                       crs="EPSG:32611", transform=TF, nodata=None) as dst:
        dst.write(arr, 1)
    rep = validate(out)
    statuses = {c["check"]: c["status"] for c in rep["checks"]}
    assert statuses["transform matches reference"] == "SKIPPED"
    assert rep["skipped_checks_mean_unverified"] is True
    assert rep["passed"] is False
