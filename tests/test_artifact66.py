"""Withdrawal checks for historical H66 artifacts; never promotion/score evidence."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CARD_PATH = DOCS / "data" / "run-card.json"
HISTORICAL_PREFIX = "gems66-h66-1-scarplet-veto-37654-20261011T203224Z"


def test_historical_h66_downloads_are_withdrawn_and_hashes_retained():
    card = json.loads(CARD_PATH.read_text(encoding="utf-8"))
    historical = card["raster_historical_artifacts"]
    assert len(historical) == 3
    for item in historical:
        assert item["file"].startswith(HISTORICAL_PREFIX)
        assert len(item["sha256"]) == 64
        assert "WITHDRAWN" in item["status"]
        assert not (DOCS / "downloads" / item["file"]).exists()
        archived = ROOT / item["archive_file"]
        assert archived.is_file()
        assert hashlib.sha256(archived.read_bytes()).hexdigest() == item["sha256"]
    zip_path = ROOT / next(item["archive_file"] for item in historical if item["file"].endswith(".zip"))
    with zipfile.ZipFile(zip_path) as archive:
        assert len(archive.namelist()) == 1
        assert archive.testzip() is None
    # The download directory may only ever hold the CURRENT cleared release (plus its
    # manifest and the README); no withdrawn H66 file may reappear there.
    rel = json.loads((DOCS / "downloads" / "current_release.json").read_text(encoding="utf-8"))
    allowed = {"README.md", "current_release.json", rel["tif"], rel["zip"], rel["manifest"]}
    assert set(path.name for path in (DOCS / "downloads").iterdir()) == allowed


def test_current_run_card_cannot_clear_a_historical_artifact():
    """The card may clear only the current raster; no historical artifact is ever cleared."""
    card = json.loads(CARD_PATH.read_text(encoding="utf-8"))
    rel = json.loads((DOCS / "downloads" / "current_release.json").read_text(encoding="utf-8"))
    # the current raster is cleared and is the one that is published
    assert card["raster"]["file"].endswith(rel["tif"])
    assert card["raster"]["sha256"] == json.loads(
        (DOCS / "downloads" / rel["manifest"]).read_text())["tif_sha256"]
    # every historical entry stays WITHDRAWN and absent from the public download dir
    for item in card["raster_historical_artifacts"]:
        assert "WITHDRAWN" in item["status"]
        assert not (DOCS / "downloads" / item["file"]).exists()
    # and no organizer score is ever claimed
    assert card["submission"]["organizer_confirmed_receipt"] is None
    assert card["budget"]["submission_slots_used"] == 0
