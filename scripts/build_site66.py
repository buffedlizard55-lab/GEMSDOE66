#!/usr/bin/env python3
"""Compatibility entry point for the former H66-specific site builder.

All site output now comes from scripts/build_site.py and the single canonical
run card. Keeping a wrapper prevents old automation from regenerating stale
"download: yes" pages from registry/run_card.json.
"""
from __future__ import annotations

from build_site import main as build_canonical_site


def build() -> int:
    build_canonical_site()
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
