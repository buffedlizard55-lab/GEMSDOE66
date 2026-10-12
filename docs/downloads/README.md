# Download folder — what is here and what it is worth

**One file is offered for upload, with one safer-format sibling. Nothing else here is a candidate.**

| file | sha256 | status |
|---|---|---|
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
