"""Fail-closed static-site checks for the evidence-gated research project."""

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PAGES = ["index.html", "submission-guide.html", "analysis.html", "hypotheses.html",
         "run-card.html", "irregularities.html", "sources.html", "h66-session.html",
         "executive-summary.html"]
OFFICIAL_LEADERBOARD = "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/"


@pytest.fixture(scope="module", autouse=True)
def built():
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    build_site.main()


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)


def test_pages_exist_and_are_well_formed():
    for name in PAGES:
        text = (DOCS / name).read_text(encoding="utf-8")
        assert text.startswith("<!doctype html>")
        assert text.count("<main>") == 1 and text.count("</main>") == 1
        assert "None" not in re.sub(r"<[^>]+>", "", text)
        parser = HTMLParser()
        parser.feed(text)
        parser.close()


def test_summary_download_gate_states_both_clearances():
    """The summary page must state, at the top, that the file is downloadable AND not slot-cleared."""
    text = (DOCS / "index.html").read_text(encoding="utf-8")
    assert "Submission download: AVAILABLE FOR AUDIT" in text
    assert "not cleared for a weekly slot" in text
    assert "downloads/gems66-h66-1-scarplet-veto-37654" in text   # the actual bytes are linked
    assert "verified competition result" in text                    # and no score is implied
    assert OFFICIAL_LEADERBOARD in text


def test_run_card_is_measured_and_still_unpromoted():
    """Every gate number must carry its label, protocol version, denominator and uncertainty clause."""
    rc = json.loads((DOCS / "data" / "run-card.json").read_text(encoding="utf-8"))
    hd = rc["holdout_dti"]
    assert hd["label"] == "HOLDOUT-DTI"
    assert isinstance(hd["value"], float) and 0.0 < hd["value"] < 1.0
    assert hd["withheld_positives"] > 1000 and hd["evaluator_version"] and "not claimed" in hd["ci95"]
    assert rc["leakage_canary"]["status"] == "PASS" and rc["leakage_canary"]["threshold_auc"] in (0.9, "0.9")
    assert rc["registry_checks"]["pre_placement_surface"]["status"].startswith("PASS")
    assert rc["registry_checks"]["post_placement_final_dots"]["status"].startswith("PASS")
    assert "incomplete corpus" in rc["registry_checks"]["post_placement_final_dots"]["status"]
    assert rc["registry_checks"]["post_placement_final_dots"]["correlation_limit"] == 0.9
    assert rc["registry_checks"]["post_placement_final_dots"]["overlap_limit"] == 0.7
    assert len(rc["raster"]["sha256"]) == 64 and (DOCS / "downloads" / rc["raster"]["file"]).exists()
    assert rc["validator"]["status"].startswith("PASS")
    assert rc["submission"]["note_limit_chars"] == 140 and rc["submission"]["note_chars"] <= 140
    assert rc["submission"]["clearance"].startswith("PARTIAL")
    assert "slot NO" in rc["submission"]["clearance"] or "not" in rc["submission"]["clearance"].lower()
    assert rc["budget"]["submission_slots_used"] == 0
    assert rc["budget"]["holdout_experiments_used"] <= rc["budget"]["max_holdout_experiments"]
    assert "negative" in rc["verdict"]


def test_hypotheses_are_ranked_and_stay_in_one_lane():
    d = json.loads((DOCS / "data" / "hypotheses.json").read_text(encoding="utf-8"))
    assert len(d["items"]) == 4
    assert [h["rank"] for h in d["items"]] == [1, 2, 3, 4]
    assert all(h["lane"] == "native-resolution lidar scarp channels" for h in d["items"])
    assert d["protocol"]["feature_scales_m"] == [2, 20]
    assert d["protocol"]["aggregation_m"] == 100
    assert all("unknown" in h["expected_gain"].lower() or "unquantified" in h["expected_gain"].lower()
               or "unmeasured" in h["expected_gain"].lower() for h in d["items"])
    assert all(h["named_mimic"] for h in d["items"])


def test_no_leaderboard_snapshot_or_local_table_remains():
    assert not (DOCS / "data" / "leaderboard-2026-10-11.json").exists()
    assert not (DOCS / "leaderboard.html").exists()
    sources = json.loads((DOCS / "data" / "sources.json").read_text(encoding="utf-8"))
    s03 = next(s for s in sources["sources"] if s["id"] == "S03")
    assert s03["url"] == OFFICIAL_LEADERBOARD
    assert s03["status"].startswith("LINK ONLY")
    claims = json.loads((DOCS / "data" / "claims.json").read_text(encoding="utf-8"))
    assert "leaderboard" not in json.dumps(claims["claims"]).lower()
    for page in PAGES:
        text = (DOCS / page).read_text(encoding="utf-8").lower()
        assert "leaderboard-2026-10-11" not in text
        assert "top 50 rendered" not in text.lower()
        assert "participant" not in text.lower()


def test_no_organizer_confirmed_numeric_score_is_claimed():
    for name in PAGES:
        text = (DOCS / name).read_text(encoding="utf-8")
        assert not re.search(r"ORGANIZER-CONFIRMED\W+0\.\d", text)


def test_all_local_links_resolve():
    for name in PAGES:
        path = DOCS / name
        parser = _Links()
        parser.feed(path.read_text(encoding="utf-8"))
        for href in parser.hrefs:
            parsed = urlsplit(href)
            if parsed.scheme or href.startswith("#"):
                continue
            target = (path.parent / parsed.path).resolve()
            assert target.exists(), f"{name}: broken local link {href}"
