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


CURRENT_STEM = "gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z"


def test_current_release_is_offered_and_only_it_is_linked():
    """The cleared LIDAR-01 raster is offered; no historical artifact is linked."""
    rel = json.loads((DOCS / "downloads" / "current_release.json").read_text(encoding="utf-8"))
    assert rel["cleared"] is True
    text = (DOCS / "index.html").read_text(encoding="utf-8")
    assert "Download status: READY TO SUBMIT" in text
    assert "AVAILABLE FOR AUDIT" not in text
    for name in PAGES:
        links = _links(DOCS / name)
        assert not any(HISTORICAL_STEM in href for href in links), name
        for href in links:
            path = urlsplit(href).path.lower()
            if path.endswith((".tif", ".tiff", ".zip")):
                assert CURRENT_STEM in href, f"{name} links a non-current artifact: {href}"
    published = sorted(p.name for p in (DOCS / "downloads").iterdir())
    assert published == sorted([
        "README.md", "current_release.json",
        f"{CURRENT_STEM}.tif", f"{CURRENT_STEM}.zip", f"{CURRENT_STEM}.manifest.json",
    ])


def test_current_raster_passes_the_format_validator():
    man = json.loads((DOCS / "downloads" / f"{CURRENT_STEM}.manifest.json").read_text())
    val = man["validator"]
    assert val["passed"] is True
    assert val["skipped_checks_mean_unverified"] is False
    for c in val["checks"]:
        if c["status"] == "INFO":
            continue
        assert c["status"] == "PASS", c
    assert man["note_chars"] <= 140
    assert 0.0 <= float(man["dots"]) <= 5_167_373


def test_run_card_labels_every_number_and_states_the_verdict():
    rc = json.loads((DOCS / "data" / "run-card.json").read_text(encoding="utf-8"))
    assert rc["verdict"] in ("promote", "negative")
    # every recorded number carries the internal-holdout label or is explicitly a control
    hd = rc["holdout_dti"]
    assert hd["evaluator_version"].startswith("src/gems/metric.py")
    for inst in hd["instruments"].values():
        for name, v in inst["variants"].items():
            assert v["label"] in ("HOLDOUT-DTI", "CONTROL"), name
            assert v["ci95"] is None or len(v["ci95"]) == 2
    # no organizer score is claimed
    assert rc["submission"]["organizer_confirmed_receipt"] is None
    assert rc["leakage_canary"]["threshold_auc"] == 0.9
    assert rc["leakage_canary"]["max_auc_observed"] < 0.9
    assert rc["registry_checks"]["correlation_limit"] == 0.9
    assert rc["registry_checks"]["overlap_limit"] == 0.7
    assert rc["registry_checks"]["max_abs_spearman"] < 0.9
    assert rc["budget"]["submission_slots_used"] == 0
    assert rc["raster"]["file"] and rc["raster"]["sha256"]
    assert rc["submission"]["note_chars"] <= rc["submission"]["note_limit_chars"] == 140


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
    assert len(d["items"]) == 4
    assert [h["rank"] for h in d["items"]] == [1, 2, 3, 4]
    assert {h["lane"] for h in d["items"]} == {"native-resolution LiDAR scarp channels"}
    assert d["protocol"]["feature_scales_m"] == [2, 20]
    assert d["protocol"]["aggregation_m"] == 100
    required = ("layers", "signature", "why_off_catalogue", "named_mimic", "differs_from_repo",
                "cost", "data_status", "validation")
    assert all(all(h.get(field) for field in required) for h in d["items"])
    assert all(any(word in h["expected_gain"].lower() for word in ("unknown", "unquantified", "unmeasured"))
               for h in d["items"])
    assert all("blocked" in h["data_status"].lower() for h in d["items"])


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
    for name in PAGES:
        for href in _links(DOCS / name):
            assert "drivendata.org/competitions/" not in href, f"deep link in {name}: {href}"
    assert OFFICIAL_HOME in _links(DOCS / "sources.html")


def test_no_organizer_confirmed_numeric_score_is_claimed():
    """No page may present a bare number as a score, or an organizer score we do not have.

    Every HOLDOUT-DTI figure that appears on the site must carry its 95 % CI next to it,
    and no number may ever be attributed to the organizer's leaderboard.
    """
    for name in PAGES:
        text = (DOCS / name).read_text(encoding="utf-8")
        assert not re.search(r"ORGANIZER-CONFIRMED\W+0\.\d", text)
        for m in re.finditer(r"HOLDOUT-DTI\s*(?:=\s*)?0\.\d+", text):
            tail = text[m.end():m.end() + 90]
            assert "95" in tail and "CI" in tail, (
                f"{name}: unlabelled/uncertained HOLDOUT-DTI figure: {text[m.start():m.end()+60]!r}")
        # no leaderboard-looking number is ever attributed to the organizer
        assert not re.search(r"(?i)leaderboard\s*(?:score\s*)?(?:of|is|=|:)?\s*0\.\d", text)


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
