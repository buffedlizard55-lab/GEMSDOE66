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


def test_download_links_follow_the_published_verdict():
    """Whether a raster may be linked is decided by the gate, not by optimism.

    Fail closed: if the site's own recomputed verdict is not CLEARED, no page may link a
    ``.tif`` or ``.zip`` at all -- that is what keeps a future, more optimistic rebuild from
    quietly re-publishing a file the evidence does not support.  If it IS cleared, every link
    must resolve to a real file whose sha256 is the one printed on the page and recorded in the
    run card, so the bytes a reviewer downloads are the bytes that were audited.
    """
    import hashlib
    import re
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    sys.path.insert(0, str(ROOT / "src"))
    import build_site_h67

    card = build_site_h67.newest(str(ROOT / "artifacts" / "h67" / "run-card-*.json"))
    cleared = build_site_h67.assess(card)["cleared"] if card else False
    links = {}
    for f in sorted((ROOT / "docs").glob("*.html")):
        for m in re.finditer(r'href="([^"]+\.(?:tif|zip))"', f.read_text()):
            links.setdefault(m.group(1), []).append(f.name)
    if not cleared:
        assert not links, f"NEGATIVE verdict but downloadable rasters are linked: {links}"
        return
    assert links, "CLEARED verdict but no download is offered"
    expect = json.loads(Path(card).read_text())["raster"]["sha256"]
    for href, pages in links.items():
        target = (ROOT / "docs" / href).resolve()
        assert target.is_file(), f"{pages} link {href}, which does not exist"
        if href.endswith(".tif"):
            got = hashlib.sha256(target.read_bytes()).hexdigest()
            assert got == expect, f"{href} sha256 {got[:12]} != run card {expect[:12]}"


def test_negative_verdict_is_recorded():
    """The historical lidar_lane verdict stays negative and is not overwritten by a new lane."""
    rc = json.loads((ROOT / "docs" / "data" / "run_card.json").read_text())
    assert rc["verdict"] == "negative", rc["verdict"]
    assert "relief" in json.dumps(rc["verdict_basis"]).lower()


def test_current_lane_verdict_is_published_next_to_the_site():
    """The current lane's run card must be on the site and agree with the site's verdict."""
    import sys

    src = ROOT / "docs" / "data" / "run-card-h67.json"
    assert src.is_file(), "the site builder must publish the current run card"
    rc = json.loads(src.read_text())
    assert rc["scores_claimed"].startswith("NONE")
    assert rc["holdout_dti"]["label"] == "HOLDOUT-DTI"
    index = (ROOT / "docs" / "index.html").read_text()
    if rc["promote"]:
        assert "OK TO SUBMIT" in index
    else:
        assert "NOT CLEARED" in index


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
