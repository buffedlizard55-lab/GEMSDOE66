import json
from pathlib import Path

H66C_STEM = "gems66-h66c-scarpgap-42000-20261012T021141Z-4023a1c1ef59"

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


def test_site_links_only_the_disclosed_allowlisted_raster():
    """A downloadable raster may only be the disclosed H67-1 sibling, and any page that links a
    raster file must state the two disclosures in the same page: the raw uniqueness rule is
    falsified and the artifact is not promoted.

    Guarding this with a test is what keeps a future, more optimistic rebuild from quietly
    publishing a file the evidence does not support - or from dropping the disclosures.
    """
    import re
    allowed = {
        "downloads/gems66-h67-scarp-lane-novelty-40000dots-v2-zeros.tif",
        "downloads/gems66-h67-scarp-lane-novelty-40000dots-v2-nan.tif",
        # LIDAR-01 session: cleared on its own run card (docs/data/run-card-lidar01.json)
        # and named by docs/downloads/current_release.json.
        "downloads/gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z.tif",
        "downloads/gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z.zip",
        # H66-C is deliberately absent: its gate is not met, so it is never offered here.
    }
    linked_any = False
    for f in sorted((ROOT / "docs").glob("*.html")):
        html = f.read_text()
        hits = [m.group(1) for m in re.finditer(r'href="([^"]+\.(?:tif|zip))"', html)]
        for href in hits:
            rel = href.split("?")[0]
            # session-66 pass 3: the k66 family allowlist is read from its own run card, so a
            # withdrawn file (the k66 consensus candidate) stops being linkable automatically.
            import json as _json
            _card = _json.loads((ROOT / "registry66" / "run-card-session66.json").read_text())
            _r = _card["raster"]
            k66_names = {Path(_r["file"]).name, Path(_r["sibling_allfinite"]).name, Path(_r["zip"]).name}
            k66 = rel.split("/")[-1] in k66_names
            assert rel in allowed or k66, f"{f.name} links an unlisted raster: {href}"
            linked_any = True
        if hits:
            links_h67 = any("gems66-h67" in h for h in hits)
            links_k66 = any(h.split("/")[-1] in k66_names for h in hits)
            if links_h67:
                assert "IR-67-GATE-02" in html, f"{f.name} links a raster without the raw-rule disclosure"
                assert "NOT PROMOTED" in html, f"{f.name} links a raster without the not-promoted status"
                assert "0.9992" in html, f"{f.name} does not state the measured raw overlap"
            if links_k66:
                assert "HOLDOUT-DTI" in html, f"{f.name} links the k66 raster without its holdout row"
                assert "95% CI" in html, f"{f.name} links the k66 raster without its CI"
            if any("gems66-lidar01" in h for h in hits):
                # the LIDAR-01 candidate must carry its own labelling next to the buttons
                assert "HOLDOUT-DTI" in html, f"{f.name} links LIDAR-01 without its holdout label"
                assert "95 % CI" in html or "95% CI" in html, f"{f.name} links LIDAR-01 without its CI"
                assert ("No ORGANIZER-CONFIRMED score" in html
                        or "no ORGANIZER-CONFIRMED score" in html), (
                    f"{f.name} links LIDAR-01 without disclaiming an organizer score")
    assert linked_any, "the disclosed candidate should be linked from at least one page"


def test_h67_geophys_pages_disclose_and_match_their_own_verdict():
    """The H67 geophysics lane keeps its own pages under docs/h67/ and must obey the same rule:
    link a raster only when its recomputed verdict is cleared, and always show the label, the CI
    and the null it is compared against.  A projection is never written as a score.
    """
    import re
    import sys

    pages = sorted((ROOT / "docs" / "h67").glob("*.html"))
    assert pages, "scripts/build_site_h67.py must publish the lane's pages"
    sys.path.insert(0, str(ROOT / "scripts"))
    sys.path.insert(0, str(ROOT / "src"))
    import build_site_h67

    card = build_site_h67.newest(str(ROOT / "artifacts" / "h67" / "run-card-*.json"))
    a = build_site_h67.assess(card)
    index = (ROOT / "docs" / "h67" / "index.html").read_text()
    assert ("OK TO SUBMIT" in index) == a["cleared"], "banner disagrees with the recomputed verdict"
    for f in pages:
        html = f.read_text()
        assert "HOLDOUT-DTI" in html or f.name in ("sources.html", "method.html"), f.name
        for m in re.finditer(r'href="([^"]+\.(?:tif|zip))"', html):
            assert a["cleared"], f"{f.name} links {m.group(1)} while the verdict is negative"
            assert (ROOT / "docs" / "h67" / m.group(1)).resolve().is_file(), m.group(1)
        assert not re.search(r"ORGANIZER-CONFIRMED\W+0\.\d", html), f.name


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