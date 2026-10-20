"""LIDAR-04 release invariants: negative verdict, honest banner, byte-level receipts.

The candidate is unique and format-valid but failed pre-registered gates G3/G4.
These tests pin that state so a future rebuild cannot silently promote it:
the run card must stay negative with no organizer score, the published
siblings must hash to the card's values, and every page linking the files
must say NOT OK TO SUBMIT next to a labelled HOLDOUT-DTI number.
"""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
STEM = "gems66-lidar03-localsnr-fracpair-37654dots-20261020T190450Z"
CARD = json.loads((DOCS / "data" / "run-card-lidar04.json").read_text())


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_card_is_negative_and_claims_no_organizer_score():
    assert CARD["verdict"] == "negative" and CARD["promote"] is False
    assert CARD["organizer_confirmed_score"] is None
    assert CARD["gate"]["all_pass"] is False
    assert CARD["gate"]["G3_sgmc_beats_h33"] is False  # the failing gates stay visible
    assert CARD["gate"]["G2_holdout_diff_ci_lower_gt0"] is True
    hd = CARD["holdout_dti"]
    assert hd["label"] == "HOLDOUT-DTI" and hd["total_withheld_positives"] == 48465
    assert hd["paired_diff_ci95"][0] > 0
    assert CARD["leakage_canary"]["worst_auc"] <= 0.90 and CARD["leakage_canary"]["pass"]
    assert len(CARD["submission_note"]) <= 140


def test_published_siblings_match_card_hashes_and_receipts():
    for suffix in ("zeros", "nan"):
        tif = DOCS / "downloads" / f"{STEM}-{suffix}.tif"
        assert tif.is_file()
        assert _sha(tif) == CARD["rasters"][suffix]["sha256"]
        receipt = json.loads(Path(str(tif) + ".receipt.json").read_text())
        assert receipt["sha256"] == CARD["rasters"][suffix]["sha256"]
        assert receipt["nan_inside"] == 0
        assert receipt["emitted_cells_gt0"] == 37654
        assert 0.0 <= receipt["min_inside"] and receipt["max_inside"] <= 1.0
    # -zeros must be fully finite (the portal "[0, 1]" rejection cannot recur)
    rz = json.loads((DOCS / "downloads" / f"{STEM}-zeros.tif.receipt.json").read_text())
    assert rz["finite_outside_count"] == 7111787 and rz["nan_outside_count"] == 0
    assert rz["all_values_in_0_1"] is True


def test_validator_evidence_passed_with_no_failures_or_skips():
    for suffix in ("zeros", "nan"):
        v = json.loads((ROOT / "evidence" / f"lidar04_validate_{suffix}.json").read_text())
        assert v["passed"] is True and v["has_failures"] is False
        statuses = [c["status"] for c in v["checks"]]
        assert "FAIL" not in statuses and "SKIPPED" not in statuses


def test_site_banner_is_negative_wherever_the_file_is_linked():
    linked = []
    for page in sorted(DOCS.glob("*.html")):
        html = page.read_text()
        if re.search(rf'href="[^"]*{re.escape(STEM)}[^"]*\.(?:tif|zip)"', html):
            linked.append(page.name)
            assert "NOT OK TO SUBMIT" in html, page.name
            assert "HOLDOUT-DTI" in html, page.name
            assert "No ORGANIZER-CONFIRMED score" in html or \
                "no ORGANIZER-CONFIRMED score" in html, page.name
    # overview first screen and the how-to-submit page both carry the banner
    assert "index.html" in linked and "executive-summary.html" in linked
    idx = (DOCS / "index.html").read_text()
    assert idx.index("LIDAR-04") < idx.index("LIDAR-02 ("), "this session banner must precede LIDAR-02"
    assert "<<<<<<<" not in idx and ">>>>>>>" not in idx  # IR-L04-SITE-01 stays fixed
