# Public download directory status

Only candidates that pass every applicable release gate belong in this directory. The current LIDAR-01 pointer is retained as a machine-readable status record, but its TIFF/ZIP are deliberately absent because the literal registry-overlap stop rule was exceeded.

| Candidate | Public status | Audit record |
|---|---|---|
| `gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z` | **NOT CLEARED — DO NOT DOWNLOAD OR SUBMIT** | `../review/2026-10-20-review-lidar-release-and-h33.md`; audit-only TIFF/ZIP under `../../artifacts/lidar01/` |

The site builder renders the pointer at `current_release.json`; when `cleared` is false, no LIDAR-01 download link is emitted. A format-validator pass does not override a failed uniqueness or scientific gate.
