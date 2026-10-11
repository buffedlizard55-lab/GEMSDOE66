#!/usr/bin/env bash
# Check expected local inputs only. This script does not download, copy, or authenticate.
# Obtain competition files through an authorized official account outside this session,
# then record provenance and checksums before placing them under data/.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_ROOT="${DATA_ROOT:-$ROOT/data}"

core=(
  "bridge/training_features.tif"
  "bridge/labels.tif"
  "bridge/existing_faults.tif"
  "bridge/sample_submission.tif"
  "bridge/1m_DEM_links.csv"
)
cache=(
  "external/lidar_scarp_features_u8.tif"
  "external/lidar_scarp_features.json"
  "external/topo_10m_derived_100m_u8.tif"
)
missing=()
for rel in "${core[@]}" "${cache[@]}"; do
  if [[ ! -f "$DATA_ROOT/$rel" ]]; then
    missing+=("$rel")
  fi
done

if ((${#missing[@]})); then
  echo "Input preflight: BLOCKED. Missing ${#missing[@]} required local files:"
  printf '  - %s\n' "${missing[@]}"
  echo ""
  echo "This script is check-only; it will not contact DrivenData, GitHub mirrors, or data hosts."
  echo "The competition data tab requires an authorized login. No credentials are requested or stored."
  echo "See README.md and docs/data/sources.json for official source and provenance requirements."
  exit 2
fi

echo "Input preflight: all listed files are present under $DATA_ROOT."
echo "Presence alone does not verify organizer origin, hashes, license, tile completeness, or grid alignment."
echo "Do not run the legacy H66 candidate pipeline; see docs/review/2026-10-11-audit.md."
