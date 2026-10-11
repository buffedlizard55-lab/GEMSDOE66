#!/usr/bin/env python3
"""Check whether the GEMS competition files are present in data/ and report their metadata.

This script does NOT download anything. The official data tab is login-gated. It only
reports on files that are already available locally to an authorized user; do not send
credentials or competition files in chat. Missing files are a blocker, not permission to
use an unofficial mirror. See README.md and docs/submission-guide.html for the gate.

Exit codes: 0 = core files present; 2 = core files missing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Accepted names. The problem page says training_features.tif; the official reference
# notebook reads data/numeric_features.tif; the labels file is labels.tif in the notebook.
EXPECTED = {
    "features": ["training_features.tif", "numeric_features.tif"],
    "labels": ["labels.tif", "existing_faults.tif"],
    "sample_submission": ["sample_submission.tif", "example_submission.tif"],
}

# OWNER-REPORTED sha256 values from another repository (GEMSDOE32, registry/data_manifest.json,
# data/prepared_manifest.json). They are NOT organiser-verified. A mismatch is a finding to review,
# not proof of anything.
OWNER_REPORTED_SHA256 = {
    "training_features.tif": "4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5",
    "labels.tif": "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    "sample_submission.tif": "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def raster_meta(path: Path) -> dict:
    import rasterio

    with rasterio.open(path) as src:
        return {
            "shape_hw": [src.height, src.width],
            "count": src.count,
            "dtype": src.dtypes[0],
            "crs": src.crs.to_string() if src.crs else None,
            "res": list(src.res),
            "transform": list(src.transform)[:6],
            "nodata": src.nodata,
        }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=str(ROOT / "data"))
    ap.add_argument("--deep", action="store_true", help="also read raster metadata (needs rasterio)")
    ap.add_argument("--hash", action="store_true", help="compute sha256 (slow for 400 MB files)")
    args = ap.parse_args(argv)

    data = Path(args.data_dir)
    report = {"data_dir": str(data), "files": {}, "missing_roles": []}
    for role, names in EXPECTED.items():
        found = [n for n in names if (data / n).exists()]
        if not found:
            report["missing_roles"].append({"role": role, "accepted_names": names})
            continue
        name = found[0]
        p = data / name
        entry = {"role": role, "name": name, "bytes": p.stat().st_size}
        if args.hash or name in OWNER_REPORTED_SHA256:
            entry["sha256"] = sha256(p)
            if name in OWNER_REPORTED_SHA256:
                entry["owner_reported_sha256_match"] = entry["sha256"] == OWNER_REPORTED_SHA256[name]
        if args.deep and name.endswith(".tif"):
            entry["raster"] = raster_meta(p)
        report["files"][role] = entry

    core_missing = [r for r in report["missing_roles"] if r["role"] in ("features", "labels")]
    report["core_ready"] = not core_missing
    print(json.dumps(report, indent=2))
    if core_missing:
        print("\nCore files missing (expected while the official data tab is login-gated). "
              "This script does not download. See docs/submission-guide.html.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
