#!/usr/bin/env bash
# Restore the hash-pinned inputs this lane needs, from the pinned sibling repositories,
# and FAIL CLOSED on any digest mismatch (the same policy as 60GEMSDOE/scripts/fetch_mirrors.sh).
#
# Nothing in here contacts DrivenData, Dropbox or any data host: the mirrors are public GitHub
# blobs in this project's own repositories, pinned by sha256 in registry/data_manifest.json.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TPL="${TPL:-/home/user/_ext/tpl}"
mkdir -p "$ROOT/data/bridge" "$ROOT/data/external" "$ROOT/data/pilot/dem3m"
for f in bridge/existing_faults.tif bridge/sample_submission.tif labels.tif \
         external/lidar_scarp_features_u8.tif external/lidar_scarp_features.json \
         external/topo_10m_derived_100m_u8.tif external/geodawn_extensions_u8.tif \
         external/sgmc_faults_100m.tif external/derived_sgmc_faults_100m_u8.tif; do
  src="$TPL/data/$f"; dst="$ROOT/data/${f#labels.tif}"; dst="${dst/external\//external/}"
  [ "$(basename "$f")" = "labels.tif" ] && dst="$ROOT/data/bridge/labels.tif"
  [ -f "$dst" ] || { echo "missing $dst -- copy from the pinned mirror:"; echo "  gh api repos/buffedlizard55-lab/60GEMSDOE/contents/data/$f -H 'Accept: application/vnd.github.raw' > $dst"; exit 1; }
done
python3 "$ROOT/scripts/run_h66.py" s0
echo "inputs restored and verified (see evidence/h66_inputs.json)"
