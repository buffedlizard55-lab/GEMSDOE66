"""The historic H66 raster is archival only; nothing is currently publishable."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_historical_bytes_are_archived_outside_public_downloads():
    card = json.loads((ROOT / "docs/data/run-card.json").read_text(encoding="utf-8"))
    submission = card["submission"]
    assert card["verdict"] == "negative" and card["promote"] is False
    assert submission["download_ok"] is False and submission["submit_ok"] is False
    assert (ROOT / card["raster"]["file"]).is_file()
    assert hashlib.sha256((ROOT / card["raster"]["file"]).read_bytes()).hexdigest() == card["raster"]["sha256"]
    assert not list((ROOT / "docs/downloads").glob("*.tif"))
    assert not list((ROOT / "docs/downloads").glob("*.zip"))


def test_proposed_name_and_note_are_not_clearance():
    card = json.loads((ROOT / "docs/data/run-card.json").read_text(encoding="utf-8"))
    submission = card["submission"]
    assert submission["name"] and "PROPOSED" in submission["name_status"]
    assert len(submission["note"]) == submission["note_chars"] <= 140
    assert submission["download_ok"] is False
    assert submission["competition_slot_used"] is False
