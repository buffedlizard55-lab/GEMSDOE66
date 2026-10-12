# Download folder — what is here and what it is worth

**One file is offered for upload, with one safer-format sibling. Nothing else here is a candidate.**

| file | sha256 | status |
|---|---|---|
<<<<<<< HEAD
| [`gems66-k66c-kbalance-31999-20261012T020000Z-nan.tif`](gems66-k66c-kbalance-31999-20261012T020000Z-nan.tif) | `dbee66e6cd030ad3c619d5aa9b04a4b3a2717cffe1b591c3ef281726af66b638` | primary submission (NaN outside the footprint) |
| [`gems66-k66c-kbalance-31999-20261012T020000Z-nan.zip`](gems66-k66c-kbalance-31999-20261012T020000Z-nan.zip) | `ecc6bac9a3106bd17ae72cb30484befd7719f7eb687a813d243f6083f506a13e` | the same GeoTIFF zipped |
| [`gems66-k66c-kbalance-31999-20261012T020000Z-allfinite.tif`](gems66-k66c-kbalance-31999-20261012T020000Z-allfinite.tif) | `1072d688791fb6f2e801aee90570d0dc2263f8859ab01fc104a5b39a7178c34c` | identical inside the footprint, writes `0` outside instead of NaN |

Submission name `GEMSDOE66-K66C-kbalance-reliefarea-31999`; note (129/140 characters)
`GEMSDOE66 K66C | K prior, lidar-covered, relief-area-balanced dots; ties the family's best-known on our frozen holdout, no margin`.

Cleared by [`registry66/run-card-session66.json`](../../registry66/run-card-session66.json) and
[`evidence66/e13_release.json`](../../evidence66/e13_release.json).

## The holdout result, stated on the download page

* HOLDOUT-DTI **0.04880** [95% CI 0.02950, 0.07327] over
  8 folds, 39,863 withheld positives.
* Same folds: owner-reported-0.2778 incumbent **0.04888**,
  chance 0.03416.
* **Margin -0.00008**: this file ties the family's best-known design on our
  own frozen instrument; it does not beat it.

## Withdrawn earlier today — do NOT upload

* `gems66-k66-kanchor-consensus-32000-20261012T003000Z-*` (sha256 `122fcd16…`): scored 0.03765
  [0.03087, 0.04440] on the same frozen holdout — a loss to the incumbent — and withdrawn. The bytes
  remain under `artifacts66/` for audit and are not linked from the site.

## Historical artifacts — do NOT upload

- **H66-1** bytes stay under `evidence/archives/h66-1/`, outside the Pages document root.
- **H66-2** is a historical negative result under `artifacts/h66-2/`.
- **lidar_lane** is audit-only under `artifacts/lidar_lane/`.
=======
| `gems66-h67-scarp-lane-novelty-40000dots-v2-zeros.tif` | `eeadc5cee0516d9b8cdd10dd3a8e57b6952693ed25cf7ddc8a02003768060d42` | **RECOMMENDED UPLOAD.** float32, EPSG:32611, 100 m, 3730x3292, 40,000 unit-mass dots, zero NaN, every one of the 12,279,160 cells in [0, 1]. Validator PASS. |
| `gems66-h67-scarp-lane-novelty-40000dots-v2-nan.tif` | `1a72bfeb3fcaede5681e9b944aadd703793bf7cf931b410e4a733aaa2e67237f` | Same values inside the footprint; NaN outside (7,111,787 cells), which is the brief-exact convention but can trip a strict finite-range checker (IR-67-FORMAT-01). |
| `*.tif.receipt.json` | — | Writer receipts: grid, range, NaN counts, dot count, the baked-in submission name and the note. Local evidence, **not** organizer acceptance. |

Why two files exist: a previous upload was rejected with *"Predicted values must be in range [0, 1]"*.
A strict `all(0 <= v <= 1)` test returns `False` on NaN, so the writer now offers an explicit
`outside_fill` export and the validator an `outside_policy` switch; the runner writes both siblings from
one dot set. Inside the footprint the files are identical pixel-for-pixel.

**What is NOT claimed.** No organizer score, no leaderboard comparison, no promotion. The
pre-registered science gate is unevaluable (IR-67-INSTR-01), the pre-registered P3 and P4 were
falsified, and the registry comparison carries an open raw-threshold exception (IR-67-GATE-02).
Upload is the owner's decision; the honest default under the project rule is to keep the slot.

**After uploading, write the receipt here** (submission id, timestamp, score or error text). An
organizer receipt tied to the sha256 above is the only route to `ORGANIZER-CONFIRMED`.
>>>>>>> origin/main
