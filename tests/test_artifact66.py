"""Withdrawal checks for historical H66 artifacts; never promotion/score evidence."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CARD_PATH = DOCS / "data" / "run-card.json"

def _k66_files():
    """Whatever the session-66 run card clears, by its own filenames."""
    card = json.loads((Path(__file__).resolve().parents[1] / "registry66"
                       / "run-card-session66.json").read_text())
    r = card["raster"]
    return sorted({Path(r["file"]).name, Path(r["sibling_allfinite"]).name,
                   Path(r["zip"]).name, Path(r["file"]).name + ".receipt.json"})


K66_FILES = _k66_files()


def _h67_geophys_files():
    """Whatever the H67 geophysics lane clears, by its own filenames -- fail closed.

    Read from the lane's own run card so a withdrawn candidate stops being publishable
    automatically, exactly as the session-66 family above does.  If no card is cleared, the
    lane may publish nothing at all.
    """
    import glob
    hits = sorted(glob.glob(str(ROOT / "docs" / "data" / "run-card-h67.json")))
    if not hits:
        return []
    card = json.loads(Path(hits[-1]).read_text())
    if not card.get("cleared_for_download"):
        return []
    return sorted({Path(card["raster"]["file"]).name,
                   Path(card["submission"]["zip"]).name})


H67_GEOPHYS_FILES = _h67_geophys_files()

HISTORICAL_PREFIX = "gems66-h66-1-scarplet-veto-37654-20261011T203224Z"
# LIDAR-01's pointer remains for audit/status; its raster is not a public download.
LIDAR01_FILES = ["current_release.json"]

# The only files this project may offer: the two disclosed H67-1 siblings and their receipts.
H66C_STEM = "gems66-h66c-scarpgap-42000-20261012T021141Z-4023a1c1ef59"

# Parallel-session downloads, listed with their own verdicts exactly as in
# tests/test_site.py (IR-L03-04: this file's allowlist was never updated for them and
# was failing on main).  LIDAR-02 and LIDAR-03 are NEGATIVE-verdict audit downloads;
# unique-msc is its own session's cleared pointer target.
_L2 = "gems66-lidar02-sharpersist-stratified-37654dots-20261020T182135Z"
_L3 = "gems66-lidar03-localsnr-fracpair-37654dots-20261020T190450Z"
LIDAR02_FILES = [f"{_L2}-{s}" for s in ("zeros.tif", "zeros.zip", "zeros.tif.receipt.json",
                                        "nan.tif", "nan.zip", "nan.tif.receipt.json")]
LIDAR03_FILES = [f"{_L3}-{s}" for s in ("zeros.tif", "zeros.zip", "zeros.tif.receipt.json",
                                        "nan.tif", "nan.zip", "nan.tif.receipt.json")]
UNIQUE_MSC_FILES = [
    "gems66-unique-msc-20261020T182024Z.tif",
    "gems66-unique-msc-20261020T182024Z.zip",
    "gems66-unique-msc-20261020T182024Z.manifest.json",
    "uniqueness_gems66-unique-msc-20261020T182024Z.json",
]

PUBLISHED = sorted([
    "README.md",
    "gems66-h67-scarp-lane-novelty-40000dots-v2-nan.tif",
    "gems66-h67-scarp-lane-novelty-40000dots-v2-nan.tif.receipt.json",
    "gems66-h67-scarp-lane-novelty-40000dots-v2-zeros.tif",
    "gems66-h67-scarp-lane-novelty-40000dots-v2-zeros.tif.receipt.json",
    # H66-C is deliberately absent: gate not met, so its bytes are audit-only under
    # artifacts/h66c/ and must never appear in the public download path.
])


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
    # pass 3 policy: the downloads folder may hold the current candidates (H67 + K66 v2) but
    # never a withdrawn historical artifact.
    historical_names = {item["file"] for item in historical}
    names = {path.name for path in (DOCS / "downloads").iterdir()}
    assert not (names & historical_names)
    allowed = set(PUBLISHED + K66_FILES + LIDAR01_FILES + H67_GEOPHYS_FILES
                  + LIDAR02_FILES + LIDAR03_FILES + UNIQUE_MSC_FILES)
    assert names <= allowed, names - allowed
    # and if the H67 geophysics lane is NOT cleared, none of its files may be present
    if not H67_GEOPHYS_FILES:
        assert not any(n.startswith("gems66-h67-geophys-maxcov-") for n in names), names


def test_current_run_card_cannot_clear_a_historical_artifact():
    """A published candidate must never be a re-issued historical artifact, and the card must
    not claim a qualified score, an organizer receipt, or a promotion."""
    card = json.loads(CARD_PATH.read_text(encoding="utf-8"))
    assert card["submission"]["file"].startswith("gems66-h67-scarp-lane-novelty-")
    assert HISTORICAL_PREFIX not in card["submission"]["file"]
    assert card["submission"]["organizer_confirmed_receipt"] is None
    assert card["promote"] is False and card["promotion_decision"] == "negative"
    assert card["budget"]["submission_slots_used"] == 0
    # the holdout block must be labelled and must refuse to present the degenerate number as a result
    hd = card["holdout_dti"]
    assert hd["label"] == "HOLDOUT-DTI" and hd["evaluator_version"]
    assert hd["withheld_positive_count"] > 0
    assert hd["pooled_dti"] == 0.0 and hd["ci95"] == [0.0, 0.0]
    assert "DEGENERATE" in hd["status"]
    assert hd["gain_vs_frozen_best"] is None and hd["off_range_front_gain"] is None
    # the raw uniqueness rule is recorded as failed even though the lift rule passes
    gate = card["correlation_overlap_vs_registry"]
    assert gate["worst_dot_overlap"] > 0.70 and gate["stop_required"] is True
    assert "RAW_RULE_FALSIFIED" in gate["verdict"]
    # and the published siblings must match the hashes the card records
    for item in card["raster"]["historical_artifacts"]:
        assert not (DOCS / "downloads" / item["file"]).exists()
