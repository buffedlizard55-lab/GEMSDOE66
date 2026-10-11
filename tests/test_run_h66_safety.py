"""The audited legacy H66 runner must remain disabled; these tests run no experiment."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_h66 as H66  # noqa: E402


def test_every_legacy_stage_fails_closed_without_loading_or_writing():
    stages = {
        "s0": H66.s0_verify,
        "s1": H66.s1_channels,
        "s2": H66.s2_e1,
        "s3": H66.s3_retrain,
        "s4": H66.s4_e2_holdout,
        "s4b": H66.s4b_detector_holdout,
        "s5": H66.s5_emit,
    }
    for name, stage in stages.items():
        with pytest.raises(RuntimeError, match="disabled after the 2026-10-11 audit"):
            stage(None)


def test_cli_refuses_named_historical_stages_before_any_execution():
    for name in H66.LEGACY_STAGES:
        with pytest.raises(SystemExit) as exc:
            H66.main([name])
        assert exc.value.code == 2


def test_cli_without_stage_exits_before_any_execution():
    with pytest.raises(SystemExit) as exc:
        H66.main([])
    assert exc.value.code == 2
