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
        # the H66-C review candidate: downloadable, never promoted
        "downloads/%s.tif" % H66C_STEM,
        "downloads/%s.zip" % H66C_STEM,
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
    assert linked_any, "the disclosed candidate should be linked from at least one page"


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