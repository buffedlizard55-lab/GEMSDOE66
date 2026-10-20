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
# LIDAR-01 is retained as audit-only evidence and is not allow-listed for download.
LIDAR01_FILES = ["current_release.json"]

# unique-msc session on main (2026-10-20): cleared pointer target; listed for the same
# fail-closed publication rule as every other session's files.
UNIQUE_MSC_FILES = [
    "gems66-unique-msc-20261020T182024Z.tif",
    "gems66-unique-msc-20261020T182024Z.zip",
    "gems66-unique-msc-20261020T182024Z.manifest.json",
    "uniqueness_gems66-unique-msc-20261020T182024Z.json",
]

# LIDAR-02 (2026-10-20): unique + format-valid but verdict NEGATIVE (science gate fail).
# Listed so the audit download is explicit, never silently publishable; the site banner
# must keep saying NOT OK TO SUBMIT (run-card-lidar02.json).
LIDAR02_FILES = [
    "gems66-lidar02-sharpersist-stratified-37654dots-20261020T182135Z-zeros.tif",
    "gems66-lidar02-sharpersist-stratified-37654dots-20261020T182135Z-zeros.zip",
    "gems66-lidar02-sharpersist-stratified-37654dots-20261020T182135Z-zeros.tif.receipt.json",
    "gems66-lidar02-sharpersist-stratified-37654dots-20261020T182135Z-nan.tif",
    "gems66-lidar02-sharpersist-stratified-37654dots-20261020T182135Z-nan.zip",
    "gems66-lidar02-sharpersist-stratified-37654dots-20261020T182135Z-nan.tif.receipt.json",
]

# LIDAR-04 (2026-10-20): unique + format-valid but verdict NEGATIVE (gates G3/G4 fail).
# Same rule as LIDAR02: audit download explicit, banner must keep saying NOT OK TO SUBMIT
# (run-card-lidar04.json).
LIDAR04_STEM = "gems66-lidar03-localsnr-fracpair-37654dots-20261020T190450Z"
LIDAR04_FILES = [
    f"{LIDAR04_STEM}-zeros.tif",
    f"{LIDAR04_STEM}-zeros.zip",
    f"{LIDAR04_STEM}-zeros.tif.receipt.json",
    f"{LIDAR04_STEM}-nan.tif",
    f"{LIDAR04_STEM}-nan.zip",
    f"{LIDAR04_STEM}-nan.tif.receipt.json",
]

# LIDAR-03 (2026-10-20): spatial-CV-retrained classifier; verdict PROMOTE under its
# pre-registered gate (run-card-lidar03.json). Listed explicitly, fail-closed style.
LIDAR03_FILES = [
    "gems66-lidar03-cvretrain-reliefdecile-37654dots-20261020T190152Z-zeros.tif",
    "gems66-lidar03-cvretrain-reliefdecile-37654dots-20261020T190152Z-zeros.zip",
    "gems66-lidar03-cvretrain-reliefdecile-37654dots-20261020T190152Z-zeros.tif.receipt.json",
    "gems66-lidar03-cvretrain-reliefdecile-37654dots-20261020T190152Z-nan.tif",
    "gems66-lidar03-cvretrain-reliefdecile-37654dots-20261020T190152Z-nan.zip",
    "gems66-lidar03-cvretrain-reliefdecile-37654dots-20261020T190152Z-nan.tif.receipt.json",
    "current_release_lidar03.json",
]



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



def _k66_files():
    card = json.loads((ROOT / "registry66" / "run-card-session66.json").read_text())
    r = card["raster"]
    return sorted({Path(r["file"]).name, Path(r["sibling_allfinite"]).name,
                   Path(r["zip"]).name, Path(r["file"]).name + ".receipt.json"})


K66_FILES = _k66_files()

def _h68_files():
    p = DOCS / "data" / "run-card-h68.json"
    if not p.exists():
        return []
    c = json.loads(p.read_text(encoding="utf-8"))
    if not c.get("cleared_for_download"):
        return []
    r = c["raster"]
    return sorted({Path(r["file"]).name, Path(r["zeros_file"]).name, Path(r["zip_file"]).name})


H68_FILES = _h68_files()

ALLOWED_RASTERS = {
    "downloads/gems66-h67-scarp-lane-novelty-40000dots-v2-zeros.tif",
    "downloads/gems66-h67-scarp-lane-novelty-40000dots-v2-nan.tif",
}


def test_download_gate_is_explicit_and_no_historical_file_is_linked():
    """The top of the site must be unambiguous in both directions: the file is downloadable,
    and it is not a promoted submission."""
    text = (DOCS / "index.html").read_text(encoding="utf-8")
    assert "Download status: FORMAT-READY" in text
    assert "NOT PROMOTED" in text
    assert "the honest default is to keep the slot" in text
    # the prior rejection mode must be addressed explicitly
    assert "Predicted values must be in range [0, 1]" in text
    # and the two disclosures must be on the same page as the buttons
    assert "IR-67-GATE-02" in text and "IR-67-INSTR-01" in text
    assert "0.9992" in text
    for name in PAGES:
        links = _links(DOCS / name)
        assert not any(HISTORICAL_STEM in href for href in links), name
        for href in links:
            path_part = urlsplit(href).path.lower()
            if path_part.endswith((".tif", ".tiff", ".zip")):
                rel = urlsplit(href).path
                assert rel in ALLOWED_RASTERS or rel.split("/")[-1] in (K66_FILES + LIDAR01_FILES + LIDAR02_FILES + UNIQUE_MSC_FILES + LIDAR03_FILES + LIDAR04_FILES + H68_FILES), f"{name}: {href}"
    # the H67 geophysics lane may publish exactly what its own run card clears (fail closed)
    import glob as _glob
    _h67 = []
    _hits = _glob.glob(str(ROOT / "docs" / "data" / "run-card-h67.json"))
    if _hits:
        _c = json.loads(Path(_hits[-1]).read_text())
        if _c.get("cleared_for_download"):
            _h67 = [Path(_c["raster"]["file"]).name, Path(_c["submission"]["zip"]).name]
    assert {p.name for p in (DOCS / "downloads").iterdir()} <= set(_h67) | set([
        "README.md",
        "gems66-h67-scarp-lane-novelty-40000dots-v2-nan.tif",
        "gems66-h67-scarp-lane-novelty-40000dots-v2-nan.tif.receipt.json",
        "gems66-h67-scarp-lane-novelty-40000dots-v2-zeros.tif",
        "gems66-h67-scarp-lane-novelty-40000dots-v2-zeros.tif.receipt.json",
    ] + K66_FILES + LIDAR01_FILES + LIDAR02_FILES + UNIQUE_MSC_FILES + LIDAR03_FILES + LIDAR04_FILES + H68_FILES)


def test_run_card_labels_every_number_and_claims_no_qualified_score():
    rc = json.loads((DOCS / "data" / "run-card.json").read_text(encoding="utf-8"))
    hd = rc["holdout_dti"]
    assert hd["label"] == "HOLDOUT-DTI"
    assert hd["evaluator_version"] and hd["withheld_positive_count"] > 0
    assert hd["pooled_dti"] == 0.0 and hd["ci95"] == [0.0, 0.0]
    assert "DEGENERATE" in hd["status"] and "NOT A QUALIFIED RESULT" in hd["status"]
    assert hd["gain_vs_frozen_best"] is None and hd["off_range_front_gain"] is None
    assert rc["leakage_canary"]["status"] == "PASS"
    assert rc["leakage_canary"]["threshold_auc"] == 0.9
    assert max(max(f["auc"], 1 - f["auc"]) for f in rc["leakage_canary"]["feature_results"]) < 0.9
    gate = rc["correlation_overlap_vs_registry"]
    assert gate["organizer_registry_complete"] is False
    assert gate["registry_rasters_expected"] is None
    assert gate["stop_required"] is True and gate["worst_dot_overlap"] > 0.70
    assert gate["density_adjusted_diagnostic_verdict"] == "UNIQUE"
    assert rc["input_provenance"]["native_1m_dem_verified"] is False
    assert rc["input_provenance"]["cultural_mask_present"] is False
    assert rc["independent_reviews"]["completed"] == 0
    sub = rc["submission"]
    assert sub["name"].startswith("gems66-h67-scarp-lane-novelty-")
    assert sub["note"] and sub["note_chars"] == len(sub["note"]) <= sub["note_limit_chars"] == 140
    assert sub["organizer_confirmed_receipt"] is None
    assert sub["download_status"].startswith("DOWNLOAD ENABLED WITH DISCLOSURES")
    assert rc["promote"] is False and rc["promotion_decision"] == "negative"
    assert rc["budget"]["submission_slots_used"] == 0
    assert "negative" in rc["verdict"].lower()
    assert all(item["archive_file"].startswith("evidence/archives/h66-1/")
               for item in rc["raster"]["historical_artifacts"])


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


def test_hypotheses_are_ranked_and_meet_the_review_fields():
    """Every ranked hypothesis must carry the fields the brief demands, with the field names
    the register actually uses (the five new geological candidates use ``catches_offcatalogue``
    and an explicit obtainability statement)."""
    d = json.loads((DOCS / "data" / "hypotheses.json").read_text(encoding="utf-8"))
    items = d["items"]
    assert len(items) >= 5
    assert [h["rank"] for h in items] == sorted(h["rank"] for h in items)
    assert d["protocol"]["feature_scales_m"] == [2, 20]
    assert d["protocol"]["aggregation_m"] == 100
    required = ("layers", "signature", "named_mimic", "differs_from_repo", "cost", "data_status",
                "validation", "expected_gain")
    for h in items:
        for field in required:
            assert h.get(field), (h["id"], field)
        assert h.get("why_off_catalogue") or h.get("catches_offcatalogue"), h["id"]
    new = [h for h in items if h["id"].startswith("G-")]
    assert new, "the new geological candidates must be registered"
    for h in new:
        assert h.get("external_source") and h.get("obtainable") and h.get("status")
    assert any("blocked" in h["status"].lower() for h in new), "the native-resolution option is data-blocked"


def test_no_leaderboard_snapshot_and_leaderboard_pages_are_not_linked():
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
    # The competition problem statement may be linked for manual review; no leaderboard page,
    # and no automated snapshot, may ever be.
    for name in PAGES:
        for href in _links(DOCS / name):
            assert "/leaderboard" not in href, f"leaderboard deep link in {name}: {href}"
    assert OFFICIAL_HOME in _links(DOCS / "sources.html")


def test_no_organizer_confirmed_numeric_score_is_claimed():
    """Session-66 pass 3 policy: a HOLDOUT-DTI value may be shown, but only next to its CI.

    The pre-66 rule banned the string "HOLDOUT-DTI 0." outright, because no qualified holdout
    existed.  A measured holdout now exists, so the rule becomes: an ORGANIZER-CONFIRMED number
    is still forbidden, and every printed HOLDOUT-DTI value must be accompanied by a 95% CI on
    the same page.
    """
    for name in PAGES:
        text = (DOCS / name).read_text(encoding="utf-8")
        assert not re.search(r"ORGANIZER-CONFIRMED\W+0\.\d", text)
        if "HOLDOUT-DTI 0." in text:
            assert "95% CI" in text, name


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


H66C_STEM = "gems66-h66c-scarpgap-42000-20261012T021141Z-4023a1c1ef59"


def test_h66c_negative_result_is_logged_and_never_offered_as_a_download():
    """The H66-C gate is not met, so its bytes must not be in the download path.

    The brief is unconditional: offer the download only if the gate is met, else log the
    negative result. The measurement, the hashes and the audit path still have to be on the
    page, and the run card has to say `promote: false`.
    """
    assert not list((DOCS / "downloads").glob(H66C_STEM + "*")), \
        "the unmet-gate candidate must not be published in docs/downloads"
    text = (DOCS / "index.html").read_text(encoding="utf-8")
    low = text.lower()
    assert H66C_STEM in text
    assert "gate not met" in low or "gate is not met" in low
    assert "not offered" in low or "there is no h66-c download" in low
    # the hashes and the audit path are published so the bytes stay verifiable
    card = json.loads((DOCS / "data" / "run-card-h66c.json").read_text(encoding="utf-8"))
    assert card["promote"] is False
    assert card["promotion_decision"] == "negative"
    assert card["submission"]["slots_used"] == 0
    assert card["raster"]["sha256"] in text
    assert "artifacts/h66c/" in text
    for name in PAGES:
        for href in _links(DOCS / name):
            assert H66C_STEM not in href or not href.lower().endswith((".tif", ".zip")), \
                f"{name} offers the unmet-gate candidate: {href}"


def test_h66c_audit_bytes_still_verify_if_rebuilt():
    """If the audit copy exists locally it must match the published hash."""
    audit = ROOT / "artifacts" / "h66c" / (H66C_STEM + ".tif")
    if not audit.is_file():
        return
    card = json.loads((DOCS / "data" / "run-card-h66c.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(audit.read_bytes()).hexdigest() == card["raster"]["sha256"]
