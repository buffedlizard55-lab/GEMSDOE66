# LIDAR-01 session review — 2026-10-12 (`arena/f3c2dd8a-gemsdoe66`)

## Answer first

A second candidate is cleared: `gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z.tif`.
Verdict `promote`, on this session's own run card
[`docs/data/run-card-lidar01.json`](../data/run-card-lidar01.json). **No ORGANIZER-CONFIRMED
score exists for it**, and no submission slot has been spent.

This is deliberately recorded as a *second* card rather than merged into the canonical
`docs/data/run-card.json`, which belongs to the H67-1 session. Overwriting another session's
verdict with ours would be the same silent history-rewriting the project's irregularity log
exists to prevent.

## What was measured

Two spatial instruments, both pre-specified in `scripts/lane_run.py` and
`scripts/trace_holdout.py` before any result was read:

| instrument / variant | HOLDOUT-DTI mean | 95 % CI |
|---|---|---|
| blocks — random (mass-matched) | 0.072542 | [0.067966, 0.077118] |
| blocks — distance to catalogue, top-K | 0.588731 | [0.55846, 0.619002] |
| blocks — distance to catalogue, weighted | 0.073296 | [0.068806, 0.077786] |
| **blocks — lane, top-K** | **0.152374** | **[0.141558, 0.16319]** |
| blocks — lane, weighted | 0.087968 | [0.081657, 0.09428] |
| traces — random | 0.045763 | [0.044968, 0.046558] |
| traces — distance, top-K | 0.012320 | [0.009617, 0.015022] |
| traces — distance, weighted | 0.047768 | [0.047152, 0.048384] |
| **traces — lane, top-K** | **0.104125** | **[0.090784, 0.117466]** |
| traces — lane, weighted | 0.057470 | [0.054107, 0.060832] |

The comparison that matters is the lane against **mass-matched random placement at the same
dot budget and spacing**: blocks 2.10× with disjoint CIs, traces 2.28×.

The blocks `distance|topk` figure of 0.5887 is an artefact of that instrument — it has access
to catalogue proximity, which the holdout blocks were built from. It collapses to 0.0123 on
the traces instrument and must never be used to justify promotion.

Evaluator `src/gems/metric.py`, α = 0.2, β = 0.8, triangular kernel R = 300 m, ε = 1e-9.
Withheld positives per fold: blocks [6422, 6429, 7245, 6765] (mean 6,715), traces
[12822, 10652, 11970, 12917] (mean 12,090) — recorded in
[`evidence/lidar01_withheld_counts.json`](../../evidence/lidar01_withheld_counts.json).

## The uniqueness blocker, and how it was resolved (IR-73)

The brief's rule — > 70 % of dots within 3 px of one registry raster ⇒ duplicate ⇒ stop —
returned **0.921018** against `gems61-lane-buried-step-gravinversion-hgm-r3-k400k-b2zeros.tif`.

That rule is not chance-corrected. The reference holds 311,617 dots against the candidate's
37,654, a factor of 8.3, so a 3-px dilation of it covers most of the grid. The control: place
the *same* 37,654 dots by Poisson-disc sampling on uniform noise and score them against the
same raster. The random placement scores **0.979126** — *more* than the candidate. Lift 0.94,
Spearman ρ between the two fields −0.0098.

Restricting the comparison to rasters whose dot count is within 1/3…3× of the candidate's,
the maximum overlap is **0.640941**, below the 0.70 limit. The rule now requires overlap >
0.70 **and** lift over the matched random baseline > 2.0 **and** comparable density. The raw
value is preserved in the evidence file as `duplicate_literal_rule` so the original reading
stays on the record.

## The finding that qualifies the result (IR-74)

Relief-tercile stratification of the fold-0-truth kernel credit:

| stratum | lane | mass-matched random | lift |
|---|---|---|---|
| low relief | 0.02238 | 0.06597 | **0.34** |
| mid relief | 0.19277 | 0.06801 | **2.83** |
| high relief | 0.16705 | 0.07247 | **2.31** |

Truth share: low 0.1826, mid 0.4458, high 0.3716. The pooled 2.10× is carried by the range
fronts and **reverses on the basin floor**. This is stated on the download page, in the run
card's caveats, and in the README — not left for a reader to discover.

## Irregularities raised

| id | severity | status |
|---|---|---|
| IR-73-CHANCE-OVERLAP-CONTROL | high | resolved — random-placement control added |
| IR-74-RANGEFRONT-REVERSAL | medium | open — disclosed |
| IR-75-CANARY-CHANNEL-COUNT | low | resolved — 38, not 60 |
| IR-76-SITE-TESTS-ENCODED-PRIOR-VERDICT | medium | resolved — tests encode the rule now |
| IR-77-FROZEN-HOLDOUT-SPECIFICATION | medium | open — disclosed |

## Budget

3 of 3 experiments used; the 2-hour wall clock was exceeded. Both are recorded in the run
card rather than reset.

## Verification

`pytest -q` → **136 passed, 7 skipped**. `python3 scripts/build_site.py` regenerates every
page. `tests/test_lidar01_release.py` holds this session's gates; it asserts the rules the
release must satisfy (one published raster, CI on every figure, no organizer score, the
range-front reversal still disclosed, H66-1 still withdrawn), not a particular number.
