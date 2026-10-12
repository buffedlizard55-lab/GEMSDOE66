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
    historical = card["raster"]["historical_artifacts"]
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
    # Only the historical H66 files are asserted absent; a later lane may legitimately publish
    # its own cleared artifact here (see tests/test_repo_hygiene.py for that gate).
    published = {path.name for path in (DOCS / "downloads").iterdir()}
    assert not any(n.startswith(HISTORICAL_PREFIX) for n in published), published


def test_current_run_card_cannot_clear_a_historical_artifact():
    card = json.loads(CARD_PATH.read_text(encoding="utf-8"))
    assert card["raster"]["file"] is None
    assert card["raster"]["sha256"] is None
    assert card["submission"]["download_status"].startswith("NO DOWNLOAD")
    assert card["submission"]["organizer_confirmed_receipt"] is None
    assert card["budget"]["submission_slots_used"] == 0
    assert card["holdout_dti"]["value"] is None
    assert card["holdout_dti"]["ci95"] is None
