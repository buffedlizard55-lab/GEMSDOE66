"""Site checks: pages build from the JSON registers, the gate is shown as closed, and no unlabelled score appears."""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PAGES = ["index.html", "submission-guide.html", "analysis.html", "hypotheses.html",
         "leaderboard.html", "run-card.html", "irregularities.html", "sources.html"]


@pytest.fixture(scope="module", autouse=True)
def built():
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site
    build_site.main()


@pytest.mark.parametrize("name", PAGES)
def test_page_exists_and_is_well_formed(name):
    t = (DOCS / name).read_text(encoding="utf-8")
    assert t.startswith("<!doctype html>")
    assert t.count("<main>") == 1 and t.count("</main>") == 1
    assert "None" not in re.sub(r"<[^>]+>", "", t)


def test_download_banner_is_closed_on_summary():
    t = (DOCS / "index.html").read_text(encoding="utf-8")
    assert "Submission download: NOT AVAILABLE" in t


def test_run_card_has_no_projected_or_holdout_value():
    rc = json.loads((DOCS / "data" / "run-card.json").read_text())
    assert rc["holdout_dti"]["value"] is None
    assert rc["holdout_dti"]["ci95"] is None
    assert rc["raster"]["sha256"] is None
    assert rc["submission"]["name"] is None


def test_no_organiser_confirmed_values():
    # No receipt exists yet, so no page may carry an ORGANIZER-CONFIRMED value.
    for name in PAGES:
        t = (DOCS / name).read_text(encoding="utf-8")
        assert not re.search(r"ORGANIZER-CONFIRMED\W+0\.\d", t)


def test_leaderboard_top_is_correct():
    lb = json.loads((DOCS / "data" / "leaderboard-2026-10-11.json").read_text())
    rows = lb["rows"]
    assert rows[0]["public_dti"] == 0.4133
    assert [r["rank"] for r in rows] == list(range(1, len(rows) + 1))
    scores = [r["public_dti"] for r in rows]
    assert scores == sorted(scores, reverse=True)
    by_rank = {r["rank"]: r for r in rows}
    assert by_rank[9]["public_dti"] == 0.3195 and by_rank[9]["participant"] == "DARD"
    assert by_rank[23]["public_dti"] == 0.2778 and by_rank[23]["participant"] == "extradr19"
