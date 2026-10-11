import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_submission import strict_registry_report  # noqa: E402


def test_missing_shared_registry_index_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr("check_submission.ROOT", tmp_path)
    report = strict_registry_report(
        np.zeros((4, 4), dtype=np.float32),
        np.ones((4, 4), dtype=bool),
        phase="emitted",
    )
    assert report["unique"] is False
    assert report["complete_registry_pass"] is False
    assert "missing evidence/registry_refreshed.json" in report["reason"]


def test_inherited_lidar_lane_card_uses_raw_overlap_stop():
    card_path = ROOT / "docs" / "data" / "run_card.json"
    card = json.loads(card_path.read_text(encoding="utf-8"))
    gate = card["correlation_overlap_vs_registry"]
    assert gate["max_frac_dots_within_3px"] > 0.70
    assert gate["verdict"] == "DUPLICATE_OVERLAP"
    assert gate["density_adjusted_diagnostic_verdict"] == "UNIQUE"
    assert gate["organizer_registry_complete"] is False
    assert gate["preplacement_surface_status"].startswith("not reported")
    assert card["verdict"] == "negative"
    assert card["promote"] is False
