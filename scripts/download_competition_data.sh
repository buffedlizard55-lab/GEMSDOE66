#!/usr/bin/env bash
# Autonomous downloader & SHA-256 verifier for DOE GEMS Prize competition rasters
# and official USGS 3DEP / GeoDAWN feature stacks.
# Uses the hash-pinned public GitHub bridge mirrors in buffedlizard55-lab.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${GEMS_DATA_DIR:-${ROOT}/data}"
export GEMS_DATA_DIR="${DATA_DIR}"
mkdir -p "${DATA_DIR}/bridge" "${DATA_DIR}/external"

EXPECTED_FEAT_SHA="4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5"
EXPECTED_LAB_SHA="7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093"
EXPECTED_SUB_SHA="2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc"
EXPECTED_LIDAR_SHA="d580bb8bdcdb941e32fefb8b38044bc5bf04e199bf2e83498c3576e6fc465568"
EXPECTED_RAD_SHA="c22420f75999030d7cc65c9e31e50d232ea6158423bca051613a18a8b20ba682"
EXPECTED_EXT_SHA="a35a9c6d2a14786f4dab85481ee59769213072f5dab5b2535ea82ae4d9bb7d9b"
EXPECTED_TOPO_SHA="a6398d9950965dec6aae6ccecdaa6ced48645d133eab222cbdd11def9bdabfa4"

sha256_check() {
    local file="$1"
    local expected="$2"
    if [[ ! -f "$file" ]]; then
        return 1
    fi
    local actual
    actual="$(sha256sum "$file" | awk '{print $1}')"
    [[ "$actual" == "$expected" ]]
}

fetch_file() {
    local repo="$1"
    local path="$2"
    local dest="$3"
    if [[ -f "$dest" ]]; then
        return 0
    fi
    echo "  Downloading ${path} from ${repo} -> ${dest}..."
    gh api "repos/${repo}/contents/${path}" -H "Accept: application/vnd.github.raw" > "$dest"
}

echo "[1/4] Placing and verifying labels and sample submission rasters..."
fetch_file "buffedlizard55-lab/60GEMSDOE" "data/bridge/existing_faults.tif" "${DATA_DIR}/bridge/existing_faults.tif"
fetch_file "buffedlizard55-lab/60GEMSDOE" "data/bridge/sample_submission.tif" "${DATA_DIR}/bridge/sample_submission.tif"
fetch_file "buffedlizard55-lab/GEMSDOE24" "data/bridge/labels.tif" "${DATA_DIR}/bridge/labels.tif"

ln -sf "${DATA_DIR}/bridge/labels.tif" "${DATA_DIR}/labels.tif"
ln -sf "${DATA_DIR}/bridge/existing_faults.tif" "${DATA_DIR}/existing_faults.tif"
ln -sf "${DATA_DIR}/bridge/sample_submission.tif" "${DATA_DIR}/sample_submission.tif"
ln -sf "${DATA_DIR}/bridge/sample_submission.tif" "${DATA_DIR}/example_submission.tif"

sha256_check "${DATA_DIR}/labels.tif" "$EXPECTED_LAB_SHA" || { echo "ERROR: labels.tif SHA mismatch"; exit 1; }
echo "  -> Verified labels.tif (${EXPECTED_LAB_SHA})"
sha256_check "${DATA_DIR}/sample_submission.tif" "$EXPECTED_SUB_SHA" || { echo "ERROR: sample_submission.tif SHA mismatch"; exit 1; }
echo "  -> Verified sample_submission.tif (${EXPECTED_SUB_SHA})"

echo "[2/4] Placing and verifying external feature rasters (lidar, topo, geodawn)..."
fetch_file "buffedlizard55-lab/60GEMSDOE" "data/external/lidar_scarp_features_u8.tif" "${DATA_DIR}/external/lidar_scarp_features_u8.tif"
fetch_file "buffedlizard55-lab/GEMSDOE24" "data/external/lidar_scarp_features.json" "${DATA_DIR}/external/lidar_scarp_features.json"
fetch_file "buffedlizard55-lab/60GEMSDOE" "data/external/topo_10m_derived_100m_u8.tif" "${DATA_DIR}/external/topo_10m_derived_100m_u8.tif"
fetch_file "buffedlizard55-lab/60GEMSDOE" "data/external/topo_10m_derived_100m_u8.manifest.json" "${DATA_DIR}/external/topo_10m_derived_100m_u8.manifest.json"
fetch_file "buffedlizard55-lab/60GEMSDOE" "data/external/geodawn_extensions_u8.tif" "${DATA_DIR}/external/geodawn_extensions_u8.tif"
fetch_file "buffedlizard55-lab/60GEMSDOE" "data/external/derived_sgmc_faults_100m_u8.tif" "${DATA_DIR}/external/derived_sgmc_faults_100m_u8.tif"
fetch_file "buffedlizard55-lab/60GEMSDOE" "data/external/sgmc_faults_100m.tif" "${DATA_DIR}/external/sgmc_faults_100m.tif"

sha256_check "${DATA_DIR}/external/lidar_scarp_features_u8.tif" "$EXPECTED_LIDAR_SHA" || { echo "ERROR: lidar_scarp_features_u8.tif SHA mismatch"; exit 1; }
echo "  -> Verified lidar_scarp_features_u8.tif (${EXPECTED_LIDAR_SHA})"
sha256_check "${DATA_DIR}/external/topo_10m_derived_100m_u8.tif" "$EXPECTED_TOPO_SHA" || { echo "ERROR: topo_10m_derived_100m_u8.tif SHA mismatch"; exit 1; }
echo "  -> Verified topo_10m_derived_100m_u8.tif (${EXPECTED_TOPO_SHA})"
sha256_check "${DATA_DIR}/external/geodawn_extensions_u8.tif" "$EXPECTED_EXT_SHA" || { echo "ERROR: geodawn_extensions_u8.tif SHA mismatch"; exit 1; }
echo "  -> Verified geodawn_extensions_u8.tif (${EXPECTED_EXT_SHA})"

echo "[3/4] Reassembling and verifying training_features.tif (19 float32 bands)..."
if ! sha256_check "${DATA_DIR}/training_features.tif" "$EXPECTED_FEAT_SHA"; then
    TMP_PARTS="/tmp/training_parts"
    mkdir -p "$TMP_PARTS"
    for part in part-000 part-001 part-002 part-003 part-004; do
        fetch_file "buffedlizard55-lab/GEMSDOE" "data/bridge/gems-geodawn-numerical-features.tif.${part}" "${TMP_PARTS}/${part}"
    done
    echo "  Concatenating 5 parts -> ${DATA_DIR}/training_features.tif..."
    cat "${TMP_PARTS}/part-000" "${TMP_PARTS}/part-001" "${TMP_PARTS}/part-002" "${TMP_PARTS}/part-003" "${TMP_PARTS}/part-004" > "${DATA_DIR}/training_features.tif"
    rm -rf "$TMP_PARTS"
fi
sha256_check "${DATA_DIR}/training_features.tif" "$EXPECTED_FEAT_SHA" || { echo "ERROR: training_features.tif SHA mismatch"; exit 1; }
echo "  -> Verified training_features.tif (${EXPECTED_FEAT_SHA})"
ln -sf "${DATA_DIR}/training_features.tif" "${DATA_DIR}/numeric_features.tif"

echo "[4/4] All competition rasters placed and verified successfully in ${DATA_DIR}."
