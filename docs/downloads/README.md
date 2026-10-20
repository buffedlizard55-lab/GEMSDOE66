# Public download directory status

Only candidates that pass every applicable release gate belong in this directory. The current LIDAR-01 pointer is retained as a machine-readable status record, but its TIFF/ZIP are deliberately absent because the literal registry-overlap stop rule was exceeded.

| Candidate | Public status | Audit record |
|---|---|---|
| `gems66-lidar03-cvretrain-reliefdecile-37654dots-20261020T190152Z` (zeros sha256 `7c7d30c2…d5972b7e`, nan `cbcd9139…75cb84`) | **✅ CLEARED — OK TO DOWNLOAD AND SUBMIT** (pre-registered gate passed; no organizer score claimed; SGMC conflict disclosed) | `../review/2026-10-20-lidar03-session.md`; `../data/run-card-lidar03.json` (verdict `promote`); pointer `current_release_lidar03.json` |
| `gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z` | **NOT CLEARED — DO NOT DOWNLOAD OR SUBMIT** | `../review/2026-10-20-review-lidar-release-and-h33.md`; audit-only TIFF/ZIP under `../../artifacts/lidar01/` |
| `gems66-lidar02-sharpersist-stratified-37654dots-20261020T182135Z` (zeros sha256 `26b264d7…484a0c`, nan `23195d6c…2d6858`) | **🔴 NOT CLEARED — DO NOT SUBMIT** (unique + format-valid audit artifact; science gate FAIL) | `../review/2026-10-20-lidar02-session.md`; `../data/run-card-lidar02.json` (verdict `negative`) |

The site builder renders the pointer at `current_release.json`; when `cleared` is false, no LIDAR-01 download link is emitted. A format-validator pass does not override a failed uniqueness or scientific gate.
