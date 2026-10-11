#!/usr/bin/env python3
"""Synchronize legacy run-card paths from the single canonical JSON decision.

This utility never derives clearance from an emission receipt, validator summary,
or historical leaderboard claim. Edit docs/data/run-card.json through a reviewed
research/release process; this script only validates and copies that decision.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "docs" / "data" / "run-card.json"
ALIASES = (ROOT / "registry" / "run_card.json", ROOT / "docs" / "runcard.json")


def main() -> int:
    card = json.loads(CANONICAL.read_text(encoding="utf-8"))
    if card.get("schema") != 4:
        raise SystemExit("unsupported canonical run-card schema; refusing to synthesize clearance")
    submission = card.get("submission", {})
    note = submission.get("note")
    note_chars = submission.get("note_chars")
    if note is not None and (len(note) != note_chars or len(note) > 140):
        raise SystemExit("canonical submission note length is inconsistent or exceeds 140 characters")
    if card.get("verdict") == "negative":
        if card.get("promote") is not False or submission.get("download_ok") is not False \
                or submission.get("submit_ok") is not False:
            raise SystemExit("negative card cannot authorize promotion, download, or submission")
    if card.get("promote") is not (card.get("verdict") == "promote"):
        raise SystemExit("canonical verdict/promote fields conflict")
    text = json.dumps(card, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    for path in ALIASES:
        path.write_text(text, encoding="utf-8")
    print(json.dumps({"canonical": str(CANONICAL.relative_to(ROOT)),
                      "aliases_synchronized": [str(p.relative_to(ROOT)) for p in ALIASES],
                      "verdict": card["verdict"],
                      "download_ok": submission.get("download_ok"),
                      "submit_ok": submission.get("submit_ok")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
