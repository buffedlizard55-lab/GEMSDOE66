"""Fail-closed static-site checks for the evidence-gated research project."""

import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PAGES = ["index.html", "feed.html", "submission-guide.html", "analysis.html", "hypotheses.html",
         "run-card.html", "irregularities.html", "sources.html", "h66-session.html",
         "executive-summary.html"]
OFFICIAL_HOME = "https://www.drivendata.org/"
OFFICIAL_LEADERBOARD = "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/"
HISTORICAL_STEM = "gems66-h66-1-scarplet-veto-37654-20261011T203224Z"


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


def _links(path):
    parser = _Links()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.hrefs


def test_pages_exist_and_are_well_formed():
    for name in PAGES:
        text = (DOCS / name).read_text(encoding="utf-8")
        assert text.startswith("<!doctype html>")
        assert text.count("<main>") == 1 and text.count("</main>") == 1
        assert not re.search(r">\s*None\s*<", text)
        parser = HTMLParser()
        parser.feed(text)
        parser.close()


def test_download_gate_is_explicit_and_no_historical_file_is_linked():
    """Session-66 policy: the gate is explicit either way, and history stays unpublished.

    The index must state the current download status in the first screen, must never link a
    historical H66 or lidar-lane artifact, and may link a raster only when the session-66 run
    card promotes exactly that file.
    """
    import json as _json
    text = (DOCS / "index.html").read_text(encoding="utf-8")
    card_path = ROOT / "registry66" / "run-card-session66.json"
    card = _json.loads(card_path.read_text()) if card_path.exists() else {}
    if card.get("promote") is True:
        assert "DOWNLOAD IS READY" in text
        allowed = {Path(card["raster"][k]).name for k in ("file", "sibling_allfinite", "zip")
                   if card["raster"].get(k)}
    else:
        assert "Download status: NOT AVAILABLE" in text
        allowed = set()
    assert ("Do not upload a historical" in text) or ("not cleared" in text)
    for name in PAGES:
        links = _links(DOCS / name)
        assert not any(HISTORICAL_STEM in href for href in links), name
        for href in links:
            if urlsplit(href).path.lower().endswith((".tif", ".tiff", ".zip")):
                assert Path(href).name in allowed, f"{name} links an uncleared raster: {href}"
    names = sorted(p.name for p in (DOCS / "downloads").iterdir())
    assert "README.md" in names
    assert all(n in allowed or n == "README.md" or n.endswith(".receipt.json") for n in names), names


def test_run_card_is_blocked_and_has_no_unqualified_score():
    rc = json.loads((DOCS / "data" / "run-card.json").read_text(encoding="utf-8"))
    hd = rc["holdout_dti"]
    assert hd["label"] == "HOLDOUT-DTI"
    assert hd["value"] is None
    assert hd["evaluator_version"] is None
    assert hd["withheld_positive_count"] is None
    assert hd["ci95"] is None
    assert "NO QUALIFIED RESULT" in hd["status"]
    assert rc["leakage_canary"]["status"] == "NOT VALIDATED"
    assert rc["leakage_canary"]["threshold_auc"] == 0.9
    assert rc["registry_checks"]["pre_placement_surface"]["complete_registry"] is False
    assert rc["registry_checks"]["post_placement_final_dots"]["complete_registry"] is False
    assert rc["registry_checks"]["pre_placement_surface"]["status"].startswith("BLOCKED")
    assert rc["registry_checks"]["post_placement_final_dots"]["status"].startswith("BLOCKED")
    assert rc["registry_checks"]["pre_placement_surface"]["correlation_limit"] == 0.9
    assert rc["registry_checks"]["post_placement_final_dots"]["overlap_limit"] == 0.7
    assert rc["raster"]["file"] is None and rc["raster"]["sha256"] is None
    assert rc["validator"]["status"].startswith("NOT PASSED")
    assert rc["validator"]["current_candidate_result"]["status"].startswith("NOT RUN")
    assert "NaN-only" in rc["validator"]["current_candidate_result"]["footprint_nan_status"]
    h66_2_validation = rc["validator"]["historical_h66_2_local_preflight"]
    assert "NOT COMPLIANT" in h66_2_validation["footprint_nan"]
    assert h66_2_validation["range_0_1"].startswith("Local checks passed")
    assert h66_2_validation["crs"].startswith("EPSG:32611")
    assert h66_2_validation["shape"] == [3730, 3292]
    assert rc["submission"]["name"] and rc["submission"]["name_status"].startswith("PROPOSED ONLY")
    assert rc["submission"]["note"] and rc["submission"]["note_chars"] == len(rc["submission"]["note"])
    assert rc["submission"]["note_chars"] <= rc["submission"]["note_limit_chars"] == 140
    assert rc["submission"]["note_status"].startswith("PROPOSED ONLY")
    assert rc["submission"]["download_status"].startswith("NO DOWNLOAD")
    assert rc["promote"] is False and rc["promotion_decision"] == "negative"
    assert rc["data_access"]["strict_premerge_s0_review"]["missing_role_count"] == 9
    assert rc["data_access"]["strict_premerge_s0_review"]["experiment_or_data_load_followed"] is False
    assert all(item["archive_file"].startswith("evidence/archives/h66-1/")
               for item in rc["raster"]["historical_artifacts"])
    assert rc["budget"]["new_experiments_used"] == 0
    assert rc["budget"]["submission_slots_used"] == 0
    assert rc["independent_reviews"]["completed"] == 0
    assert "negative" in rc["verdict"].lower()


def test_h66_2_card_is_historical_proxy_not_score_or_clearance():
    card = json.loads((DOCS / "data" / "run-card-h66-2.json").read_text(encoding="utf-8"))
    assert card["verdict"] == "NEGATIVE-NOT-PROMOTED"
    assert "PROXY ONLY" in card["measurement_class"]
    assert "HOLDOUT-DTI" in card["measurement_class"]
    assert "ORGANIZER-CONFIRMED" in card["measurement_class"]
    assert card["holdout_dti"] is None
    assert card["organizer_confirmed_score"] is None
    assert "NOT CLEARED" in card["clearance"]
    assert card["note_chars"] <= 140


def test_hypotheses_are_ranked_and_meet_same_lane_review_fields():
    d = json.loads((DOCS / "data" / "hypotheses.json").read_text(encoding="utf-8"))
    items = d["items"]
    # 2026-10-12: four pre-implementation LIDAR leads plus the five implemented-and-measured
    # H67-A..E candidates from the H67 lane session (negative gate result; nothing cleared).
    assert len(items) == 9
    assert [h["rank"] for h in items] == list(range(1, len(items) + 1))
    assert {h["lane"] for h in items} == {"native-resolution LiDAR scarp channels"}
    assert d["protocol"]["feature_scales_m"] == [2, 20]
    assert d["protocol"]["aggregation_m"] == 100
    required = ("layers", "signature", "why_off_catalogue", "named_mimic", "differs_from_repo",
                "cost", "data_status", "validation")
    assert all(all(h.get(field) for field in required) for h in items)
    # no quantified DTI projection is claimed as an expected gain, measured or not
    assert all(any(word in h["expected_gain"].lower()
                   for word in ("unknown", "unquantified", "unmeasured", "not a dti projection"))
               for h in items)
    # no item may claim cleared/released data; the unimplemented leads must stay blocked
    assert all(not any(w in h["data_status"].lower() for w in ("cleared", "released")) for h in items)
    assert all("blocked" in h["data_status"].lower() for h in items if h["id"].startswith("LIDAR"))
    # the H67 items are measured, and the four that were not emitted claimed no holdout number
    assert all(h["validation"].startswith("MEASURED 2026-10-12") for h in items if h["id"].startswith("H67"))
    assert all("no holdout dti claimed" in h["validation"].lower() for h in items
               if h["id"] in ("H67-A", "H67-B", "H67-D", "H67-E"))


def test_no_leaderboard_snapshot_and_only_homepage_is_deep_linked():
    assert not (DOCS / "data" / "leaderboard-2026-10-11.json").exists()
    assert not (DOCS / "leaderboard.html").exists()
    sources = json.loads((DOCS / "data" / "sources.json").read_text(encoding="utf-8"))
    s03 = next(s for s in sources["sources"] if s["id"] == "S03")
    assert s03["url"] == OFFICIAL_LEADERBOARD
    assert "NO VALUES MIRRORED" in s03["status"]
    assert "NO ONGOING MONITORING" in s03["status"]
    claims = json.loads((DOCS / "data" / "claims.json").read_text(encoding="utf-8"))
    assert "leaderboard" in json.dumps(claims["claims"]).lower()  # attribution caveat is explicit
    numeric_claim_values = [value for claim in claims["claims"] for value in claim.values()
                            if isinstance(value, (int, float)) and not isinstance(value, bool)]
    assert not numeric_claim_values  # no owner-reported value is promoted as a score
    # The owner's standing charter supplies the competition page URLs and requires a "how to
    # submit" page, so those specific pages are an allowlist; any other competition subpage
    # deep link remains forbidden.
    charter_pages = {
        "https://www.drivendata.org/competitions/306/competition-doe-gems/",
        "https://www.drivendata.org/competitions/306/competition-doe-gems/data/",
        "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/",
        "https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/",
    }
    for name in PAGES:
        for href in _links(DOCS / name):
            if "drivendata.org/competitions/" in href:
                assert href.rstrip("/") + "/" in {p.rstrip("/") + "/" for p in charter_pages}, \
                    f"deep link outside the charter allowlist in {name}: {href}"
    assert OFFICIAL_HOME in _links(DOCS / "sources.html")


def test_no_organizer_confirmed_numeric_score_is_claimed():
    for name in PAGES:
        text = (DOCS / name).read_text(encoding="utf-8")
        assert not re.search(r"ORGANIZER-CONFIRMED\W+0\.\d", text)
        assert "HOLDOUT-DTI 0." not in text


def test_historical_evidence_is_quarantined_and_sgmc_source_is_internal():
    for path in (ROOT / "evidence").glob("h66_*.json"):
        d = json.loads(path.read_text(encoding="utf-8"))
        assert d["evidence_disposition"]["status"].startswith("UNQUALIFIED LEGACY")
        if d.get("evidence_class", "").startswith("HOLDOUT-DTI"):
            pytest.fail(f"legacy evidence still exposes a qualified score class: {path}")
    irr = json.loads((DOCS / "data" / "irregularities.json").read_text(encoding="utf-8"))
    ir13 = next(x for x in irr["items"] if x["id"] == "IR-13-H66-NEGATIVE-RESULT")
    assert ir13["source_ids"] == []
    assert "evidence/h66_e1_offcat.json" in ir13["internal_evidence"]
    assert "GeoDAWN" in ir13["detail"]
    assert "S08" not in ir13["detail"]


def test_legacy_data_ingress_entrypoints_are_check_only():
    downloader = (ROOT / "scripts" / "download_competition_data.sh").read_text(encoding="utf-8")
    preflight = (ROOT / "scripts" / "fetch_inputs.sh").read_text(encoding="utf-8")
    prepare = (ROOT / "scripts" / "prepare_data.py").read_text(encoding="utf-8")
    for text in (downloader, preflight):
        assert "gh api" not in text
        assert "curl " not in text
        assert "wget " not in text
    assert "exec bash" in downloader
    assert "disabled" in prepare.lower()
    assert "download" in prepare.lower()


def test_canonical_and_legacy_mirrors_are_synchronized():
    pairs = [
        (DOCS / "data" / "hypotheses.json", ROOT / "registry" / "hypotheses.json"),
        (DOCS / "data" / "irregularities.json", ROOT / "registry" / "irregularities.json"),
        (DOCS / "data" / "run-card.json", ROOT / "registry" / "run_card.json"),
        (DOCS / "data" / "run-card.json", DOCS / "runcard.json"),
    ]
    for canonical, mirror in pairs:
        assert json.loads(canonical.read_text(encoding="utf-8")) == json.loads(mirror.read_text(encoding="utf-8"))


def test_template_provenance_matches_local_sources_and_discloses_upstream_limit():
    provenance = json.loads((ROOT / "registry" / "template_provenance.json").read_text(encoding="utf-8"))
    assert provenance["n_files"] == len(provenance["files"]) == 23
    assert provenance["n_identical"] == sum(bool(row["identical"]) for row in provenance["files"].values()) == 19
    for name, row in provenance["files"].items():
        path = ROOT / "src" / "gems57" / name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert row["sha256"] == digest
        assert row["bytes"] == path.stat().st_size
        assert row["identical"] is (digest == row["template_sha256"])
    assert "registry/template_pin.json" in provenance["comparison_limitations"]
    assert "not submitted or merged" in provenance["local_shared_source_patch"]["upstream_status"]


def test_all_local_links_resolve():
    for name in PAGES:
        path = DOCS / name
        for href in _links(path):
            parsed = urlsplit(href)
            if parsed.scheme or href.startswith("#"):
                continue
            target = (path.parent / parsed.path).resolve()
            assert target.exists(), f"{name}: broken local link {href}"
