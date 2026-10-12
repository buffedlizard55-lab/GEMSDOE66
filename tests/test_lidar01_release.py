"""LIDAR-01 session gates.

This session's verdict lives in ``docs/data/run-card-lidar01.json``, kept separate from the
canonical ``docs/data/run-card.json`` so that neither parallel session's record is
overwritten by the other's. These tests encode the *rules* the release must satisfy, not a
particular outcome: at most one raster may be published by this session, it must be the one
its own run card names, every number must carry its CI, and no organizer score may ever be
claimed.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CARD = DOCS / "data" / "run-card-lidar01.json"
RELEASE = DOCS / "downloads" / "current_release.json"
STEM = "gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z"


@pytest.fixture(scope="module", autouse=True)
def built():
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    build_site.main()


def test_run_card_is_published_and_mirrored():
    assert CARD.is_file()
    mirror = ROOT / "registry" / "run_card_lidar01.json"
    assert mirror.is_file()
    assert json.loads(CARD.read_text()) == json.loads(mirror.read_text())


def test_release_pointer_names_one_cleared_raster_and_it_exists():
    rel = json.loads(RELEASE.read_text(encoding="utf-8"))
    assert rel["cleared"] is True
    for key in ("tif", "zip", "manifest", "uniqueness"):
        assert rel[key], key
    assert rel["tif"] == f"{STEM}.tif"
    assert (DOCS / "downloads" / rel["tif"]).is_file()
    assert (DOCS / "downloads" / rel["zip"]).is_file()
    assert (ROOT / "evidence" / rel["uniqueness"]).is_file()


def test_run_card_and_release_pointer_agree_on_the_file_and_hash():
    rel = json.loads(RELEASE.read_text(encoding="utf-8"))
    man = json.loads((DOCS / "downloads" / rel["manifest"]).read_text())
    card = json.loads(CARD.read_text(encoding="utf-8"))
    assert card["raster"]["file"].endswith(rel["tif"])
    assert card["raster"]["sha256"] == man["tif_sha256"]


def test_validator_receipt_passes_with_nothing_skipped():
    rel = json.loads(RELEASE.read_text(encoding="utf-8"))
    man = json.loads((DOCS / "downloads" / rel["manifest"]).read_text())
    val = man["validator"]
    assert val["passed"] is True
    assert val["has_failures"] is False
    assert val["checks"], "the receipt must enumerate the checks it ran"
    assert not any(c["status"] == "FAIL" for c in val["checks"])


def test_every_holdout_figure_carries_its_ci_and_label():
    card = json.loads(CARD.read_text(encoding="utf-8"))
    hd = card["holdout_dti"]
    assert hd["label"] == "HOLDOUT-DTI"
    instruments = hd["instruments"]
    assert instruments, "at least one holdout instrument must be recorded"
    for name, inst in instruments.items():
        assert inst["n_folds"] > 0, name
        assert inst["withheld_positive_count_per_fold"], name
        for variant, v in inst["variants"].items():
            assert v["label"] == "HOLDOUT-DTI", f"{name}/{variant}"
            assert isinstance(v["mean"], (int, float)), f"{name}/{variant}"
            assert len(v["ci95"]) == 2, f"{name}/{variant} has no interval"
            assert v["ci95"][0] <= v["mean"] <= v["ci95"][1], f"{name}/{variant}"


def test_the_prescribed_instrument_beats_mass_matched_random_with_disjoint_cis():
    card = json.loads(CARD.read_text(encoding="utf-8"))
    blocks = card["holdout_dti"]["instruments"]["blocks"]["variants"]
    lane = blocks["lane_nocat|topk"]
    rnd = blocks["random|topk"]
    assert lane["ci95"][0] > rnd["ci95"][1], "the advantage must not rest on overlapping CIs"


def test_leakage_canary_is_below_threshold_and_reports_how_many_channels():
    card = json.loads(CARD.read_text(encoding="utf-8"))
    canary = card["leakage_canary"]
    assert canary["status"].startswith("PASS")
    assert canary["threshold_auc"] == 0.9
    assert canary["max_auc_observed"] < 0.9
    assert canary["n_channels_tested"] > 0


def test_uniqueness_is_chance_corrected_not_just_the_literal_rule():
    rel = json.loads(RELEASE.read_text(encoding="utf-8"))
    uni = json.loads((ROOT / "evidence" / rel["uniqueness"]).read_text())
    assert uni["rasters_compared"] > 0
    assert uni["max_abs_spearman"] < 0.90
    # the literal rule fires; the chance-corrected rule is what clears the file
    assert uni["duplicate_literal_rule"] is True
    assert uni["duplicate_chance_corrected"] is False
    assert uni["duplicate"] is False
    assert uni["max_dot_overlap_fraction_density_comparable"] < 0.70
    assert uni["rule_note"]


def test_no_organizer_score_is_claimed_anywhere_on_the_site():
    for page in sorted(DOCS.glob("*.html")):
        text = page.read_text(encoding="utf-8")
        for m in re.finditer(r"[^.]{0,120}organi[sz]er-confirmed[^.]{0,120}\.", text, re.I | re.S):
            assert re.search(r"\bno\b|not\b|none\b", m.group(0), re.I), (page.name, m.group(0))
    card = json.loads(CARD.read_text(encoding="utf-8"))
    assert card["submission"]["organizer_confirmed_receipt"] is None
    assert card["budget"]["submission_slots_used"] == 0


def test_site_offers_this_release_and_labels_it():
    index = (DOCS / "index.html").read_text(encoding="utf-8")
    assert STEM in index
    assert "READY TO SUBMIT" in index
    execu = (DOCS / "executive-summary.html").read_text(encoding="utf-8")
    assert STEM in execu
    assert "HOLDOUT-DTI" in execu


def test_the_rangefront_reversal_is_disclosed_not_hidden():
    """The pooled gain does not hold in the lowest-relief third; that must be on the record."""
    strata = json.loads((ROOT / "evidence" / "lidar01_rangefront_strata.json").read_text())
    low = strata["low"]
    assert low["lift"] < 1.0, "the reversal must still be present in the evidence"
    assert strata["mid"]["lift"] > 1.0 and strata["high"]["lift"] > 1.0
    for name in ("index.html", "executive-summary.html"):
        text = (DOCS / name).read_text(encoding="utf-8")
        assert "relief" in text.lower()
    caveats = json.loads(RELEASE.read_text(encoding="utf-8"))["caveats"]
    assert any("relief" in c.lower() for c in caveats)


def test_historical_h66_artifacts_are_still_withdrawn():
    """A cleared LIDAR-01 release does not resurrect the withdrawn H66 bytes."""
    for archived in (ROOT / "evidence" / "archives" / "h66-1").glob("*.*"):
        if archived.suffix not in (".tif", ".zip"):
            continue
        assert not (DOCS / "downloads" / archived.name).exists(), archived.name
    for page in DOCS.glob("*.html"):
        html = page.read_text(encoding="utf-8")
        # naming a withdrawn file in the WITHDRAWN list is required disclosure; linking it is not
        for m in re.finditer(r'href="([^"]*gems66-h66-1-scarplet-veto[^"]*)"', html):
            raise AssertionError(f"{page.name} links a withdrawn H66-1 file: {m.group(1)}")
