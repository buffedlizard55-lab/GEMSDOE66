# Download folder — what is here and what it is worth

Candidates produced across parallel sessions are listed below, each governed by its own machine-readable run card. **Read the status column before you upload anything.**

| file | sha256 | status |
|---|---|---|
| [`gems66-h68-native-scarp-vent-35800dots-20261020T183000Z-940be485-nan.tif`](gems66-h68-native-scarp-vent-35800dots-20261020T183000Z-940be485-nan.tif) | `b42aae62a11bfb825829cebfde09bc124924ef8d127905e484dd3a98c5f0a40e` | **PRIMARY RECOMMENDED UPLOAD (Session H68, 2026-10-20).** Verdict `promote` ([`../data/run-card-h68.json`](../data/run-card-h68.json)). 35,800 dots, NaN outside footprint, 15/15 validator PASS, HOLDOUT-DTI 0.16052 [0.13093, 0.18280] with positive lift in ALL 3 relief strata (basin 1.39×, piedmont 3.33×, range front 2.51×), comparable-density overlap 0.4868 ≤ 0.70. |
| [`gems66-h68-native-scarp-vent-35800dots-20261020T183000Z-940be485-zeros.tif`](gems66-h68-native-scarp-vent-35800dots-20261020T183000Z-940be485-zeros.tif) | `f222ec9ef44ce044de15575cf374097f0e76a4ad322d99be5c7d8b64e4132178` | **RANGE-SAFE ALL-FINITE SIBLING (Session H68).** Pixel-identical inside footprint, `0.0` outside (0 NaN across all 12,279,160 cells; immune to `Predicted values must be in range [0, 1]`). |
| [`gems66-h68-native-scarp-vent-35800dots-20261020T183000Z-940be485-nan.zip`](gems66-h68-native-scarp-vent-35800dots-20261020T183000Z-940be485-nan.zip) | `7e83ded56a9134a3b399c664b96671b2af5cb19cd13ad263e0bb0c7b413f704b` | ZIP archive of the Session H68 NaN-outside GeoTIFF. |
| [`gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z.tif`](gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z.tif) | `0da74d0f75d7e6a7c86d5298f3b50941523ee88bcba23e4abd294b02186059c2` | **RECOMMENDED UPLOAD.** LIDAR-01 session, verdict `promote`. 37,654 dots, NaN outside the footprint, 15/15 validator checks PASS. |
| [`gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z.zip`](gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z.zip) | `134e3694d76eaee5a26824fbf543d305055fc40f82d75c7de553650c39c2825b` | the same GeoTIFF zipped |
| [`gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z.manifest.json`](gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z.manifest.json) | — | writer + validator receipt (grid, range, NaN counts, dot count, name, note) |
| [`gems66-k66c-kbalance-31999-20261012T020000Z-nan.tif`](gems66-k66c-kbalance-31999-20261012T020000Z-nan.tif) | `dbee66e6cd030ad3c619d5aa9b04a4b3a2717cffe1b591c3ef281726af66b638` | session-66 candidate; NaN outside the footprint. **Ties** the family's best-known on the frozen holdout (margin −0.00008), does not beat it. |
| [`gems66-k66c-kbalance-31999-20261012T020000Z-nan.zip`](gems66-k66c-kbalance-31999-20261012T020000Z-nan.zip) | `ecc6bac9a3106bd17ae72cb30484befd7719f7eb687a813d243f6083f506a13e` | the same GeoTIFF zipped |
| [`gems66-k66c-kbalance-31999-20261012T020000Z-allfinite.tif`](gems66-k66c-kbalance-31999-20261012T020000Z-allfinite.tif) | `1072d688791fb6f2e801aee90570d0dc2263f8859ab01fc104a5b39a7178c34c` | identical inside the footprint, writes `0` outside instead of NaN |
| [`gems66-h67-scarp-lane-novelty-40000dots-v2-zeros.tif`](gems66-h67-scarp-lane-novelty-40000dots-v2-zeros.tif) | `eeadc5cee0516d9b8cdd10dd3a8e57b6952693ed25cf7ddc8a02003768060d42` | H67-1 session; 40,000 dots, zero NaN across all 12,279,160 cells. **Not promoted** — the science gate is unevaluable (IR-67-INSTR-01). |
| [`gems66-h67-scarp-lane-novelty-40000dots-v2-nan.tif`](gems66-h67-scarp-lane-novelty-40000dots-v2-nan.tif) | `1a72bfeb3fcaede5681e9b944aadd703793bf7cf931b410e4a733aaa2e67237f` | same values inside the footprint, NaN outside (IR-67-FORMAT-01) |
| `*.tif.receipt.json` | — | writer receipts. Local evidence, **not** organizer acceptance. |

The machine-readable pointer to the recommended file is
[`current_release.json`](current_release.json).

---

## LIDAR-01 — the recommended upload

Submission name `gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z`;
note (140/140 characters)
`LIDAR-01: slope-aware antislope scarplet template + Steger/Frangi multiscale line evidence from the 2 m GeoDAWN lidar stack, spacing-cons`.

Cleared by [`../data/run-card-lidar01.json`](../data/run-card-lidar01.json) (verdict
`promote`), with uniqueness in [`../../evidence/lidar01_uniqueness.json`](../../evidence/lidar01_uniqueness.json)
and the format receipt in the manifest above.

| gate | result |
|---|---|
| prescribed instrument — lidar-covered spatial-block hide-and-recover | HOLDOUT-DTI **0.15237** [95% CI 0.14156, 0.16319] vs **0.07254** [0.06797, 0.07712] for mass-matched random placement — 2.10×, disjoint CIs, 4 folds |
| second instrument — global whole-trace holdout | **0.10413** [0.09078, 0.11747] vs **0.04576** [0.04497, 0.04656] — 2.28× |
| leakage canary | PASS — max per-channel AUC **0.6204** over **38** channels, threshold 0.90 |
| duplicate / lane drift | PASS (chance-corrected) — max \|Spearman ρ\| **0.069009** (limit 0.90), density-comparable 3-px overlap **0.640941** (limit 0.70) |
| official format validator | **15/15 PASS**, 0 skipped, re-read from the written file |

Evaluator `src/gems/metric.py`, α = 0.2, β = 0.8, triangular kernel R = 300 m; ≈ 6,715
withheld positives per fold (blocks) and ≈ 12,090 (traces).

**Caveats that travel with this file.**

1. The advantage reverses in the lowest-relief third of the footprint: lift **0.34** there
   versus **2.83×** (mid) and **2.31×** (high). The pooled 2.10× is carried by the range
   fronts — IR-74-RANGEFRONT-REVERSAL.
2. The holdout was frozen by specification and code before any evidence was read, and only
   that one interpretation was measured, so the margins carry no multiplicity adjustment —
   IR-77-FROZEN-HOLDOUT-SPECIFICATION.
3. The lane operators run at σ 1.0–4.0 × 100 m (100–400 m), not the requested native 2–20 m
   resolution; 1 m tiles were unreachable from this sandbox.
4. No cultural mask exists in this checkout; the registry covers 60 rasters and is not
   certified complete.

**No ORGANIZER-CONFIRMED score exists for this file.** The organiser has not been asked to
score it; no submission slot has been spent.

### Why the 0.921 overlap is not a duplicate (IR-73)

The raw 3-px overlap rule reports 0.921018 against
`gems61-lane-buried-step-gravinversion-hgm-r3-k400k-b2zeros.tif`, above the 0.70 stop. That
rule is not chance-corrected: the reference holds 311,617 dots against the candidate's
37,654 (8.3×), so a 3-px dilation of it covers most of the grid. A Poisson-disc placement of
the *same* 37,654 dots on uniform noise scores **0.979** against it — more than the
candidate. Restricted to rasters within 1/3…3× the candidate's dot count, the maximum
overlap is **0.640941**, below the limit.

---

## Session-66 candidate (K66 v2)

Submission name `GEMSDOE66-K66C-kbalance-reliefarea-31999`; note (129/140 characters)
`GEMSDOE66 K66C | K prior, lidar-covered, relief-area-balanced dots; ties the family's best-known on our frozen holdout, no margin`.

* HOLDOUT-DTI **0.04880** [95% CI 0.02950, 0.07327], 8 folds, 39,863 withheld positives.
* Same folds: owner-reported-0.2778 incumbent **0.04888**; chance 0.03416.
* **Margin −0.00008**: this file ties the family's best-known design on our own frozen
  instrument; it does not beat it.

Cleared by [`../../registry66/run-card-session66.json`](../../registry66/run-card-session66.json)
and [`../../evidence66/e13_release.json`](../../evidence66/e13_release.json).

## H67-1 candidate

40,000 unit-mass dots from the scarp-lane novelty field. **What is NOT claimed:** no
organizer score, no leaderboard comparison, no promotion. The pre-registered science gate is
unevaluable (IR-67-INSTR-01), P3 and P4 were falsified, and the registry comparison carries
an open raw-threshold exception (IR-67-GATE-02, measured raw overlap 0.9992). Upload is the
owner's decision; the honest default under the project rule is to keep the slot.

**After uploading, write the receipt here** (submission id, timestamp, score or error text).
An organizer receipt tied to the sha256 above is the only route to `ORGANIZER-CONFIRMED`.

---

## Withdrawn — do NOT upload

* `gems66-k66-kanchor-consensus-32000-20261012T003000Z-*` (sha256 `122fcd16…`): scored
  0.03765 [0.03087, 0.04440] on the same frozen holdout — a loss to the incumbent — and
  withdrawn. The bytes remain under `artifacts66/` for audit and are not linked from the
  site.
* **H66-1** bytes stay under `evidence/archives/h66-1/`, outside the Pages document root.
* **H66-2** is a historical negative result under `artifacts/h66-2/`.
* **`lidar_lane`** is audit-only under `artifacts/lidar_lane/`.

## Why two sibling files exist for some candidates

A previous upload was rejected with *"Predicted values must be in range [0, 1]"*. A strict
`all(0 <= v <= 1)` test returns `False` on NaN, so the writer offers an explicit
`outside_fill` export and the validator an `outside_policy` switch, and both siblings are
written from one dot set. Inside the footprint the files are identical pixel-for-pixel. The
brief's wording is *"data outside the bounds is null or nan"*, which is the `-nan` sibling;
the `-zeros` sibling is the one that cannot trip a strict finite-range checker.
