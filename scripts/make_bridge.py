#!/usr/bin/env python3
"""Create the local ``data/bridge/`` view used by the verifier and legacy checks.

The older shared tools (``scripts/verify66.py``, ``scripts/check_submission.py``,
``scripts/h66b_*.py``) read the competition rasters from ``data/bridge/``; the mirror fetch
writes them to ``data/raw/``.  This helper makes ``data/bridge/`` a set of **symlinks** (falling
back to copies on filesystems without symlinks) so both layouts address the same bytes - no
data is duplicated or modified.  ``data/`` is git-ignored: nothing here is committed.

Usage:  .venv/bin/python scripts/make_bridge.py
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
BRIDGE = ROOT / "data" / "bridge"

FILES = ("training_features.tif", "labels.tif", "existing_faults.tif", "sample_submission.tif")


def main() -> int:
    BRIDGE.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        src = RAW / name
        if not src.exists():
            print(f"MISSING {src} - run scripts/fetch_mirrors.py first")
            return 2
        dst = BRIDGE / name
        if dst.exists() or dst.is_symlink():
            if dst.is_symlink() and os.readlink(dst) == str(src.resolve()):
                print(f"ok      {dst.name} -> {src}")
                continue
            dst.unlink()
        try:
            dst.symlink_to(src.resolve())
            print(f"linked  {dst.name} -> {src}")
        except OSError:
            shutil.copy2(src, dst)
            print(f"copied  {dst.name} ({src.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
