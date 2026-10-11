import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_every_evidence_json_parses():
    d = ROOT / "evidence"
    if not d.exists():
        return
    n = 0
    for p in d.glob("*.json"):
        json.loads(p.read_text())
        n += 1
    assert n > 0


def test_organiser_score_is_always_disclaimed():
    """A repository rule, enforced mechanically.

    The project brief says a projection must never be written as a score and every number
    must be labelled.  So: any page that shows a leaderboard-style number must also carry
    the disclaimer that no organiser-confirmed score exists here, and the label
    "ORGANIZER-CONFIRMED" may only ever appear in a negated sentence.
    """
    pages = sorted((ROOT / "docs").glob("*.html"))
    assert pages
    import re
    for p in pages:
        t = p.read_text()
        if re.search(r"organi[sz]er-confirmed", t, re.I):
            # every occurrence must sit in a negated clause
            for m in re.finditer(r"[^.]{0,120}organi[sz]er-confirmed[^.]{0,120}\.",
                                 t, re.I | re.S):
                assert re.search(r"\bno\b|not\b|none\b", m.group(0), re.I), (p.name, m.group(0))
    # and at least the results page must carry the disclaimer
    assert "ORGANIZER-CONFIRMED" in (ROOT / "docs" / "results.html").read_text()


def test_downloads_have_sidecar_receipts():
    dl = ROOT / "artifacts" / "lidar_lane"
    if not dl.exists():
        return
    for tif in dl.glob("*.tif"):
        assert (dl / f"checks-{tif.name}.json").exists(), tif.name


def test_readme_contains_the_brief():
    t = (ROOT / "README.md").read_text()
    assert "PARALLEL-RUN PROTOCOL" in t
    assert "Predicted values must be in range [0, 1]" in t


def test_site_links_no_downloadable_raster():
    """A NEGATIVE verdict must not publish a submission file.

    The lane's advantage did not survive relief matching, so the GeoTIFF lives in
    ``artifacts/lidar_lane/`` for audit and the site must not offer it as a download.
    Guarding this with a test is what keeps a future, more optimistic rebuild from quietly
    re-publishing a file the evidence does not support.
    """
    import re
    for f in sorted((ROOT / "docs").glob("*.html")):
        html = f.read_text()
        for m in re.finditer(r'href="([^"]+\.(?:tif|zip))"', html):
            raise AssertionError(f"{f.name} links a downloadable raster: {m.group(1)}")


def test_negative_verdict_is_recorded():
    rc = json.loads((ROOT / "docs" / "data" / "run_card.json").read_text())
    assert rc["verdict"] == "negative", rc["verdict"]
    assert "relief" in json.dumps(rc["verdict_basis"]).lower()


def test_relief_matched_evidence_exists_and_reproduces_pooled():
    """The de-confounding instrument must agree with the published pooled run.

    If the two instruments disagreed on the pooled number, the de-confounded one would be
    mis-specified rather than merely stricter.
    """
    d = json.loads((ROOT / "evidence" / "relief_matched.json").read_text())
    assert abs(d["pooled_confounded"]["lane"]["mean"] - 0.07075) < 1e-4
    assert abs(d["pooled_confounded"]["inc"]["mean"] - 0.04896) < 1e-4
    # and the confound must be the whole story
    assert d["gains_matched"]["lane_minus_inc"]["ci95"][0] < 0
    assert d["confound_size"] > 0.02
