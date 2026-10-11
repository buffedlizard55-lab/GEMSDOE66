"""Evidence-site tests: negative clearance must never create a public artifact link."""

import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PAGES = ["index.html", "executive-summary.html", "submission-guide.html", "analysis.html",
         "hypotheses.html", "run-card.html", "irregularities.html", "sources.html",
         "h66-session.html"]
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


def test_summary_and_submission_page_show_blocked_clearance_without_artifact_links():
    summary = (DOCS / "index.html").read_text(encoding="utf-8")
    executive = (DOCS / "executive-summary.html").read_text(encoding="utf-8")
    guide = (DOCS / "submission-guide.html").read_text(encoding="utf-8")
    assert "Download: NOT CLEARED" in summary
    assert "Submission: NOT CLEARED" in summary
    assert "No TIF or ZIP download is cleared" in summary
    assert "NEGATIVE — NO DOWNLOAD OR SUBMISSION CLEARANCE" in executive
    assert "Do not download or submit the archived audit artifact" in executive
    assert "No file is available for download or submission" in guide
    assert "cause is unknown" in guide
    for text in (summary, executive, guide):
        assert ".tif\"" not in text and ".zip\"" not in text
        assert "downloads/gems66-h66-1-scarplet-veto-37654" not in text
    for artifact in (DOCS / "downloads").glob("*"):
        assert artifact.name == "README.md", f"uncleared public download remains: {artifact}"


def test_canonical_run_card_keeps_candidate_and_history_separate():
    rc = json.loads((DOCS / "data" / "run-card.json").read_text(encoding="utf-8"))
    assert rc["schema"] == 4
    assert rc["verdict"] == "negative" and rc["promote"] is False
    assert rc["top_candidate"].startswith("LIDAR-01")
    assert rc["holdout_dti"]["label"] == "HOLDOUT-DTI"
    assert rc["holdout_dti"]["value"] is None
    assert rc["holdout_dti"]["withheld_positive_count"] is None
    assert rc["holdout_dti"]["ci95"] is None
    assert "NOT RUN" in rc["holdout_dti"]["status"]
    assert rc["historical_emitted_policy_holdout"]["value"] == 0.0
    assert rc["historical_emitted_policy_holdout"]["withheld_positive_count"] == 45260
    assert rc["historical_emitted_policy_holdout"]["ci95"] is None
    assert rc["historical_detector_arm"]["value"] == pytest.approx(0.04800722761599403)
    assert rc["historical_detector_arm"]["ci95"] is None
    assert rc["leakage_canary"]["status"] == "NOT RUN"
    assert rc["input_verification"]["status"].startswith("BLOCKED")
    assert "external/topo_10m_derived_100m_u8.tif" in rc["input_verification"]["missing"]
    assert "external/lidar_scarp_features.json" in rc["input_verification"]["missing_pins"]
    assert rc["registry_checks"]["pre_placement_surface"]["status"].startswith("NOT RUN")
    post = rc["registry_checks"]["post_placement_final_dots"]
    assert post["registry_count"] == 62 and post["expected_registry_count"] == 655
    assert post["complete_registry"] is False
    assert post["max_dot_overlap"] == pytest.approx(0.5099)
    assert post["historical_sampled_max_abs_rank_correlation"] == pytest.approx(0.0196)
    assert rc["raster"]["sha256"] == "44d6dccbc27ce2e6dbe42794ed24c0f34c86aadb942c9b913afec08fb39953e1"
    archive = ROOT / rc["raster"]["file"]
    assert archive.is_file()
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == rc["raster"]["sha256"]
    assert rc["validator"]["status"].startswith("PARTIAL")
    assert rc["validator"]["footprint_nan_ok"] is False
    assert rc["validator"]["values_0_1_ok"] is False
    assert rc["validator"]["crs_shape_transform_match"] is False
    assert rc["submission"]["download_ok"] is False
    assert rc["submission"]["submit_ok"] is False
    assert len(rc["submission"]["note"]) == rc["submission"]["note_chars"] <= 140
    assert all(value is False for value in rc["release_gates"].values())
    assert rc["budget"]["holdout_experiments_used"] == 3
    assert rc["budget"]["wall_time_hours_reported"] == 3.4


def test_site_gate_fails_closed_even_when_card_flag_is_misset():
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from build_site import _candidate_download

    rc = json.loads((DOCS / "data" / "run-card.json").read_text(encoding="utf-8"))
    rc["verdict"] = "promote"
    rc["promote"] = True
    rc["submission"]["download_ok"] = True
    for key in rc["release_gates"]:
        rc["release_gates"][key] = True
    rc["holdout_dti"].update(status="PASS", value=0.2, ci95=[0.1, 0.3],
                              paired_difference_ci95=[0.01, 0.04],
                              beats_frozen_holdout_best=True)
    rc["leakage_canary"]["status"] = "PASS"
    rc["validator"].update(status="PASS", footprint_nan_ok=True,
                            values_0_1_ok=True, crs_shape_transform_match=True)
    for item in rc["registry_checks"].values():
        item.update(status="PASS", complete_registry=True, pixel_hash_agreement_pass=True,
                    max_abs_rank_correlation=0.1)
    rc["registry_checks"]["post_placement_final_dots"]["max_dot_overlap"] = 0.1
    # Even all asserted gates cannot publish an archival path or a missing file.
    assert _candidate_download(rc) is None


def test_hypotheses_are_ranked_in_one_lane_and_unmeasured():
    data = json.loads((DOCS / "data" / "hypotheses.json").read_text(encoding="utf-8"))
    assert len(data["items"]) == 4
    assert [h["rank"] for h in data["items"]] == [1, 2, 3, 4]
    assert all(h["lane"] == "native-resolution lidar scarp channels" for h in data["items"])
    assert data["protocol"]["feature_scales_m"] == [2, 5, 10, 20]
    assert data["protocol"]["aggregation_m"] == 100
    assert all(any(word in h["expected_gain"].lower() for word in ("unknown", "unquantified", "unmeasured"))
               for h in data["items"])
    assert all(h["named_mimic"] for h in data["items"])


def test_no_leaderboard_snapshot_or_organizer_score_claim():
    assert not (DOCS / "data" / "leaderboard-2026-10-11.json").exists()
    assert not (DOCS / "leaderboard.html").exists()
    sources = json.loads((DOCS / "data" / "sources.json").read_text(encoding="utf-8"))
    s03 = next(source for source in sources["sources"] if source["id"] == "S03")
    assert s03["url"] == OFFICIAL_LEADERBOARD
    assert s03["status"].startswith("LINK ONLY")
    for name in PAGES:
        text = (DOCS / name).read_text(encoding="utf-8")
        assert not re.search(r"ORGANIZER-CONFIRMED\W+0\.\d", text)
        assert "leaderboard-2026-10-11" not in text.lower()


def test_legacy_site_builder_is_only_a_canonical_wrapper():
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site66
    assert build_site66.build() == 0
    text = (DOCS / "h66-session.html").read_text(encoding="utf-8")
    assert "No download clearance" in text
    assert "downloads/gems66-h66-1-scarplet-veto-37654" not in text


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
