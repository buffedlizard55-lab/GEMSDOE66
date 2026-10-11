#!/usr/bin/env bash
# Safety replacement for the historical owner-mirror downloader.
# This entry point is intentionally check-only; no GitHub API, mirrors, or data hosts are contacted.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "BLOCKED: competition/cache inputs are not authorized or provenance-cleared in this checkout."
echo "No download, copy, or authentication will be attempted."
echo "Running the local presence-only input check instead."
exec bash "$ROOT/scripts/fetch_inputs.sh"
