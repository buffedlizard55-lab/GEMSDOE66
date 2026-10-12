#!/usr/bin/env python3
"""Synchronize legacy run-card mirrors from the canonical blocked review card.

This script never reads experiment evidence, calculates a score, infers a verdict,
or creates/downloads an artifact. Edit docs/data/run-card.json as the single source
of truth, then run this script to update the two historical mirror paths.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "docs" / "data" / "run-card.json"
MIRRORS = (ROOT / "registry" / "run_card.json", ROOT / "docs" / "runcard.json")


def main() -> int:
    card = json.loads(CANONICAL.read_text(encoding="utf-8"))
    run_id = card.get("run_id", "")
    if not isinstance(run_id, str) or not run_id.startswith("gemsdoe66-native-lidar-review-"):
        raise ValueError("unexpected canonical native-LiDAR run-card identity")
    if card.get("submission", {}).get("download_status") != "NO DOWNLOAD — no file is cleared or offered":
        raise ValueError("refusing to mirror a run card that does not explicitly block downloads")
    if card.get("holdout_dti", {}).get("value") is not None:
        raise ValueError("refusing to mirror an unreviewed holdout value")

    serialized = json.dumps(card, indent=2, ensure_ascii=False) + "\n"
    for path in MIRRORS:
        path.write_text(serialized, encoding="utf-8")
    print("Synchronized blocked run-card mirrors; no evidence or score was read.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
