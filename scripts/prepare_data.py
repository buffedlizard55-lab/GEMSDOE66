#!/usr/bin/env python3
"""Blocked compatibility stub for the historical owner-mirror preparation pipeline.

The previous script interpreted owner-supplied cached rasters as competition-ready inputs.
This checkout has no authorized raster set or validated tile provenance, so data processing
is disabled. Do not run a derived-stack build until the source/provenance and experiment
release gates are reviewed and the shared pipeline is approved.
"""
from __future__ import annotations


def main() -> int:
    print("BLOCKED: data preparation is disabled; required authorized inputs/provenance are absent.")
    print("No download or processing will occur. Run `bash scripts/fetch_inputs.sh` only for a local presence check.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
