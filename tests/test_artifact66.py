"""Invariants of the shipped artifact.  Skipped automatically when data/ is not restored."""
import json
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
card_p = ROOT / "registry/run_card.json"
card = json.loads(card_p.read_text()) if card_p.exists() else {}
f = (card.get("submission") or {})


@pytest.mark.skipif(not (ROOT / "data/bridge/sample_submission.tif").exists(), reason="pinned inputs not restored")
def test_shipped_bytes_match_the_run_card():
    import rasterio
    from gems57 import grid as G57, validate as V57
    p = ROOT / "docs/downloads" / f["file"]
    with rasterio.open(p) as ds:
        a = ds.read(1)
        assert str(ds.crs) == "EPSG:32611" and (ds.height, ds.width) == (3730, 3292)
        assert tuple(ds.transform)[:6] == tuple(G57.TRANSFORM)[:6]
    assert np.isfinite(a).all() and a.min() >= 0.0 and a.max() <= 1.0
    grid = G57.load_grid()
    assert int((a[grid.footprint] > 0).sum()) == int((a > 0).sum())      # nothing outside the footprint
    assert int((a > 0).sum()) == card["validator_output"]["reread"]["n_positive"]
    assert (a[grid.catalogue] == 0).all(), "no positive pixel may sit on the mapped catalogue"
    r = V57.validate(p, footprint=grid.footprint, catalogue=grid.catalogue)
    assert r["all_checks_passed"], [k for k, v in r["checks"].items() if not v]


def test_note_and_name_fit_the_portal_field():
    assert len(f.get("note", "")) <= 140 and f.get("name")
    assert f["file"].endswith("-allfinite.tif")      # the NaN-free variant is the one to upload


def test_zip_contains_exactly_one_tiff():
    import zipfile
    zp = ROOT / "docs/downloads" / f["file_zip"]
    if not zp.exists():
        pytest.skip("zip not built")
    with zipfile.ZipFile(zp) as z:
        assert z.namelist() == [f["file"]]
        assert z.read(f["file"]).startswith((b"II*\x00", b"MM\x00*"))
