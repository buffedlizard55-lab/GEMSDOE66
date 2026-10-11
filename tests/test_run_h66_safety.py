"""Fail-closed runner tests; these tests never execute a scientific experiment."""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_h66 as H66  # noqa: E402


def _fixture_inputs(tmp_path, *, omit_pin=None):
    data = tmp_path / "data"
    files = []
    for rel in H66.REQUIRED_H66_INPUTS:
        path = data / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = ("test-input:" + rel).encode()
        path.write_bytes(payload)
        if rel != omit_pin:
            files.append({"dest": rel, "sha256": hashlib.sha256(payload).hexdigest()})
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"files": files}), encoding="utf-8")
    return data, manifest


def test_s0_requires_every_input_and_pin(tmp_path):
    missing_data = tmp_path / "missing-data"
    manifest = tmp_path / "empty-manifest.json"
    manifest.write_text(json.dumps({"files": []}), encoding="utf-8")
    rep = H66.s0_verify(data_dir=missing_data, manifest_path=manifest,
                        evidence_dir=tmp_path / "evidence")
    assert rep["ok"] is False
    assert set(rep["missing"]) == set(H66.REQUIRED_H66_INPUTS)
    assert set(rep["missing_pins"]) == set(H66.REQUIRED_H66_INPUTS)
    assert H66._INPUTS_VERIFIED is False


def test_s0_accepts_only_exact_complete_pins(tmp_path):
    data, manifest = _fixture_inputs(tmp_path)
    rep = H66.s0_verify(data_dir=data, manifest_path=manifest,
                        evidence_dir=tmp_path / "evidence")
    assert rep["ok"] is True
    assert not rep["missing"] and not rep["missing_pins"]
    assert not rep["mismatch"] and not rep["pin_conflicts"]
    assert H66._INPUTS_VERIFIED is True


def test_s0_blocks_unpinned_required_file(tmp_path):
    data, manifest = _fixture_inputs(tmp_path, omit_pin="external/topo_10m_derived_100m_u8.tif")
    rep = H66.s0_verify(data_dir=data, manifest_path=manifest,
                        evidence_dir=tmp_path / "evidence")
    assert rep["ok"] is False
    assert rep["missing_pins"] == ["external/topo_10m_derived_100m_u8.tif"]


def test_s0_reports_changed_bytes_and_conflicting_pins(tmp_path):
    data, manifest = _fixture_inputs(tmp_path)
    first = H66.REQUIRED_H66_INPUTS[0]
    path = data / first
    path.write_bytes(b"changed")
    payload = json.loads(manifest.read_text())
    payload["files"].append({"dest": first, "sha256": "0" * 64})
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    rep = H66.s0_verify(data_dir=data, manifest_path=manifest,
                        evidence_dir=tmp_path / "evidence")
    assert rep["ok"] is False
    assert first in rep["pin_conflicts"]
    # Multiple distinct pins are a conflict; neither one may be selected implicitly.
    assert first not in rep["mismatch"]


def test_main_returns_after_failed_s0_without_loading_state(tmp_path, monkeypatch):
    monkeypatch.setattr(H66, "DATA", tmp_path / "absent-data")
    monkeypatch.setattr(H66, "EV", tmp_path / "evidence")
    monkeypatch.setattr(H66, "load_state", lambda: pytest.fail("load_state ran after failed s0"))
    assert H66.main(["run_h66.py", "s1"]) == 2
    assert (tmp_path / "evidence" / "h66_inputs.json").is_file()


def test_main_budget_guard_stops_before_state_load(tmp_path, monkeypatch):
    monkeypatch.setattr(H66, "s0_verify", lambda: {"ok": True, "missing": [],
                                                    "missing_pins": [], "mismatch": []})
    monkeypatch.setattr(H66, "_research_budget_available", lambda: (False, "test budget exhausted"))
    monkeypatch.setattr(H66, "load_state", lambda: pytest.fail("load_state ran after budget stop"))
    with pytest.raises(SystemExit, match="test budget exhausted"):
        H66.main(["run_h66.py", "s1"])


def test_direct_research_stage_cannot_bypass_input_or_budget_guards(monkeypatch):
    monkeypatch.setattr(H66, "_INPUTS_VERIFIED", False)
    with pytest.raises(RuntimeError, match="strict s0 input verification"):
        H66.s1_channels({})
    monkeypatch.setattr(H66, "_INPUTS_VERIFIED", True)
    monkeypatch.setattr(H66, "_research_budget_available", lambda: (False, "exhausted"))
    with pytest.raises(RuntimeError, match="blocked before execution: exhausted"):
        H66.s1_channels({})


def test_canonical_budget_is_exhausted_without_running_it():
    allowed, reason = H66._research_budget_available()
    assert allowed is False
    assert "3/3 experiments" in reason and "3.4/2 hours" in reason


def test_feature_manifest_covers_every_candidate_plane():
    fields = {
        "feature_manifest": np.asarray(["template_fit", "steger_strength", "frangi_persistence"]),
        "feature__template_fit": np.ones((4, 4), np.float32),
        "feature__steger_strength": np.full((4, 4), 0.5, np.float32),
        "feature__frangi_persistence": np.zeros((4, 4), np.float32),
    }
    planes = H66._feature_planes(fields)
    assert set(planes) == {"template_fit", "steger_strength", "frangi_persistence"}
    del fields["feature__steger_strength"]
    with pytest.raises(ValueError, match="feature_manifest/feature planes disagree"):
        H66._feature_planes(fields)
    fields["feature__steger_strength"] = np.ones((4, 4), np.float32)
    fields["feature__unlisted"] = np.ones((4, 4), np.float32)
    with pytest.raises(ValueError, match="feature_manifest/feature planes disagree"):
        H66._feature_planes(fields)


def test_s5_release_failure_records_block_and_writes_no_tiff(tmp_path, monkeypatch):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    monkeypatch.setattr(H66, "EV", evidence)
    monkeypatch.setattr(H66, "_INPUTS_VERIFIED", True)
    monkeypatch.setattr(H66, "s0_verify", lambda: {"ok": True})
    monkeypatch.setattr(H66, "_release_evidence_failures", lambda: ["synthetic missing holdout gate"])
    with pytest.raises(RuntimeError, match="release blocked; no TIFF written"):
        H66.s5_emit({})
    report = json.loads((evidence / "h66_release_preflight.json").read_text())
    assert report["release_cleared"] is False and report["tiff_written"] is False
    assert report["failures"] == ["synthetic missing holdout gate"]
    assert not list(evidence.rglob("*.tif"))
    assert not list(evidence.rglob("*.zip"))


def test_release_gate_rejects_malformed_or_out_of_range_holdout(tmp_path, monkeypatch):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    monkeypatch.setattr(H66, "EV", evidence)
    (evidence / "h66_inputs.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
    (evidence / "h66_e2_holdout.json").write_text(json.dumps({
        "protocol_id": H66.HOLDOUT_PROTOCOL_ID,
        "hypothesis_id": H66.EXPECTED_TOP_HYPOTHESIS_ID,
        "candidate_arm": "h66_candidate",
        "evidence_class": "HOLDOUT-DTI",
        "evaluator_version": H66.EH57.VERSION,
        "metric": None,
        "candidate": {"evidence_class": "HOLDOUT-DTI", "evaluator_version": H66.EH57.VERSION,
                      "withheld_positive_pixels": 100, "dti": 1.5, "ci95": [1.2, 1.6]},
        "withheld_positive_count": 100,
        "split_receipts": [],
        "candidate_field_hashes": {},
        "source_hashes": None,
        "frozen_holdout_best": None,
        "feature_alone_leakage_canary": None,
    }), encoding="utf-8")
    monkeypatch.setattr(H66, "_frozen_best", lambda: (None, {"available": False}))
    failures = H66._release_evidence_failures()
    assert any("positive count, or 95% CI" in failure for failure in failures)
    assert any("split receipts" in failure for failure in failures)
    assert any("field hashes" in failure for failure in failures)
    assert any("source hashes" in failure for failure in failures)
    assert any("frozen holdout best" in failure for failure in failures)
    assert any("leakage canary" in failure for failure in failures)


def test_unknown_stage_is_rejected_before_input_or_research(monkeypatch):
    monkeypatch.setattr(H66, "s0_verify", lambda: pytest.fail("s0 should not run for an invalid stage"))
    with pytest.raises(SystemExit, match="unknown stages"):
        H66.main(["run_h66.py", "not-a-stage"])
