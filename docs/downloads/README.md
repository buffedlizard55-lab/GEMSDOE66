# Public download directory status

Only candidates that pass every applicable release gate belong in this directory. The current LIDAR-01 pointer is retained as a machine-readable status record, but its TIFF/ZIP are deliberately absent because the literal registry-overlap stop rule was exceeded.

| Candidate | Public status | Audit record |
|---|---|---|
| `gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z` | **NOT CLEARED — DO NOT DOWNLOAD OR SUBMIT** | `../review/2026-10-20-review-lidar-release-and-h33.md`; audit-only TIFF/ZIP under `../../artifacts/lidar01/` |
| `gems66-lidar02-sharpersist-stratified-37654dots-20261020T182135Z` (zeros sha256 `26b264d7…484a0c`, nan `23195d6c…2d6858`) | **🔴 NOT CLEARED — DO NOT SUBMIT** (unique + format-valid audit artifact; science gate FAIL) | `../review/2026-10-20-lidar02-session.md`; `../data/run-card-lidar02.json` (verdict `negative`) |
| `gems66-lidar03-localsnr-fracpair-37654dots-20261020T190450Z` (zeros sha256 `6b8e14be…f33a94`, nan `09883a2f…05b544`) | **🔴 NOT CLEARED — DO NOT SUBMIT** (unique + format-valid audit artifact; holdout gate PASS but SGMC-incumbent and low-relief gates FAIL) | `../review/2026-10-20-lidar04-session.md`; `../data/run-card-lidar04.json` (verdict `negative`) |

The site builder renders the pointer at `current_release.json`; when `cleared` is false, no LIDAR-01 download link is emitted. A format-validator pass does not override a failed uniqueness or scientific gate.
