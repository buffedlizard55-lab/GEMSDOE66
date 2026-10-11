#!/usr/bin/env python3
"""Deprecated legacy entry point; delegate to the single safe site builder.

The previous generator exposed historical TIFF/ZIP downloads unconditionally.
All current and legacy site builds now use scripts/build_site.py, which only
advertises an artifact if a current run card explicitly clears it.
"""
from __future__ import annotations

from build_site import main


if __name__ == "__main__":
    raise SystemExit(main())
