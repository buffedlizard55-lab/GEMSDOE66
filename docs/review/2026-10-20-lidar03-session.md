# LIDAR-03 session review — 2026-10-20 (`arena/6c75ae04-gemsdoe66`)

**Verdict: NEGATIVE (not promoted). A new, lane-unique, format-valid GeoTIFF pair was
generated and is preserved for audit, but the pre-registered gate is not met (G3, G4 fail),
so it is NOT cleared for submission and no weekly slot should be spent on it.**
Machine-readable card: [`docs/data/run-card-lidar03.json`](../data/run-card-lidar03.json).
Builder: [`scripts/build_lidar03.py`](../../scripts/build_lidar03.py) (reuses the shared
`gems66.lidar_channels`, `gems.metric`, `gems.submission_writer`, `gems.validate_submission`
and the LIDAR-02 helpers imported unchanged from `scripts/build_lidar02.py` — no private
forks). Evidence: `evidence/lidar03_e1_canary.json`, `lidar03_e2_holdout.json`,
`lidar03_e3_emission.json`, `lidar03_uniqueness.json`, `lidar03_validate_{zeros,nan}.json`,
`lidar03_revalidate_summary.json`, `lidar03_run.log`.

Core values: *Maximize P(Win)* — one instrument improved decisively and the other got
worse; spending a slot while the two disagree and the basin-floor control is at random
would be gambling, not evidence. *Own the Outcome* — shared-tool bug fixed once in the
template, a live-site merge-conflict artifact found and repaired, two pre-existing red
tests fixed, and the negative result shipped as the deliverable.

---

## 1. Why did `h33-h33-2-b2-…-zeros` get the family's highest reported score (0.2778), and can we beat it?

### 1.1 Provenance first (re-verified this session, IR-L03-05)

On 2026-10-20 this session re-fetched
<https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html>. That site — the raster's
own home — labels the exact file (sha256 `c55bafc4…`) **UNSCORED**, gives a *projected*
live DTI of **0.2747** ("a MODEL, not a score"), and states **"NO ORGANISER SCORE EXISTS
for this or any artifact in this repository."** The brief's 0.2778 (family best), 0.3195 and
0.3774 (leaderboard) therefore remain **owner-reported / unverified**, not
`ORGANIZER-CONFIRMED`. No submission-page receipt tying any of those numbers to a raster
hash exists in any repository this session could read. Nothing below contradicts the
LIDAR-02 review's §1.1; this is an independent same-day confirmation.

### 1.2 Mechanism (why that design is the family incumbent)

Measured on the byte-identical local mirror `registry/rasters/GEMSDOE32__h33-2-b2-zeros.tif`
and re-measured in this run's controls: 37,654 unit dots, 0 within 200 m of the catalogue
(this run: overlap of our dots with it is 0.192 at lift 1.21 — a genuinely different
population). The metric (α=0.2, β=0.8, triangular kernel R=300 m; transcribed in
`src/gems/metric.py`) makes an added dot profitable iff its kernel credit exceeds
α·DTI ≈ 0.056 at DTI ≈ 0.28. H33-2-B2's three properties follow directly: (i) sparse dot
budget (~37 k) instead of a dense map that pays α on every pixel; (ii) zero mass on/near
known faults, which by the organiser's definition (hidden truth = faults *not* in the
public database, problem page 967) can earn no credit; (iii) habitat ~1.5–2 km off the
catalogue. **This session added one new measurement to that picture:** on the SGMC
off-catalogue truth restricted to the *low-relief tercile* (23,406 truth px), h33-2-b2
scores **0.06410** while mass-matched random scores **0.00466** and both LiDAR-scarp
candidates score ≈0.003–0.005-class — i.e. a large part of the incumbent's edge is
basin-floor placement the scarp lane is not reproducing (see §3, G4).

### 1.3 Can a submission score higher than 0.2778 / 0.3195 / 0.3774?

Only by raising mean kernel credit per dot at fixed mass — roughly +36 % credit density in
the top of the ranking to go from a 0.2778-class field to 0.3774 (first order). LIDAR-03
shows the scarp lane can now beat random on the prescribed holdout (paired CI excludes
zero), but it *lost* ground on the off-catalogue inventory proxy and remains at random on
the basin floor, exactly where the incumbent is strong. **No honest claim to beat 0.2778
can be made from this evidence.** The missing capability is a basin-floor signal: in
alluvium the 2 m descriptors have almost no scarp expression, so a field built only from
scarp channels is structurally blind there (next-session candidates, §6).

## 2. Candidate hypotheses ranked before implementation (all inside the assigned lane)

| rank | id | layers | physical signature | why off-catalogue | differs from repo | expected gain / cost |
|---|---|---|---|---|---|---|
| 1 | **L03-A local-SNR × fraction × crest/toe pair × unsigned polarity (IMPLEMENTED)** | `step/ex/ex_mean/lap±/up/down/cross/relief` + Frangi/Steger on detrended SNR surface | step & ex divided by ~1 km Gaussian background; `ex_mean/(ex_max+ε)`; `sqrt(lappos·lapneg)`; `|up−down|/(up+down+cross)` | Young subtle scarps on fans are locally anomalous at low absolute amplitude; damage zones raise within-cell scarp fraction; diffusion profile pairs crest+toe curvature | No prior field used a signal/background SNR, a fraction ratio, a curvature-pairing product, or unsigned polarity; the signed antislope net (measured anti-signal, AUC 0.301) is removed | Highest / low |
| 2 | L03-B Steger offset-valid density solo field | Detrended SNR surface, σ=1,2 | 5×5 density of pixels whose sub-pixel extremum lands in-pixel with consistent Hessian sign | True line crests localise sub-pixel; diffuse cultural edges do not | Channel included at weight 0.05 and canaried (AUC 0.538/0.528 — weak); solo emission not run | Low after canary / low |
| 3 | L03-C strike-discontinuity (relay) field | `strike`, `coh100` | Circular gradient of dominant strike × coherence (abrupt ≥20° breaks on coherent traces) | Relay ramps/stepovers between mapped segments are classic unmapped sites | Strike has only been a passive channel; canary remains ~chance (0.498/0.510), lowering the prior | Low / medium |
| 4 | L03-D cross-slope-veto complement solo | `cross_max` lows × step highs | Steps with no cross-slope competitor (pure dip-slip geometry) | Roads/canals are orientation-mixed; normal-fault scarps are not | Veto used subtractively before; `cross_max` alone is a *positive* predictor (AUC 0.765/0.578), so the complement prior weakened this session | Low / low |
| 5 | L03-E true native 2–20 m Scarplet/Steger/Frangi on raw 1 m DEM | USGS 3DEP 1 m tiles | Native-resolution template fits (amplitude, age, SNR) + sub-pixel lines at 2–20 m | Exactly the lane's premise; sub-cell geometry is destroyed by the 100 m aggregate | Never measured in any session here | Unknown / **blocked**: named free official source is USGS 3DEP (<https://www.usgs.gov/3d-elevation-program>); checked obtainable — **not from this sandbox** (egress limited to github.com / pypi.org). The hash-pinned 2 m-descriptor aggregate is the disclosed substitute |

Method sources for manual review (same verified set as prior sessions): Scarplet
<https://doi.org/10.21105/joss.01066>; Steger, IEEE TPAMI 20(2):113–125, 1998,
<https://doi.org/10.1109/34.659930>; Frangi et al., MICCAI 1998, LNCS 1496:130–137,
<https://doi.org/10.1007/BFb0056195>; competition
<https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/>; rules PDF
<https://docs.nlr.gov/docs/fy26osti/96647.pdf>; reference solution
<https://github.com/drivendataorg/gems-prize-reference-solution>; GeoDAWN
<https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and>
(DOI 10.5066/P93LGLVQ per `registry/data_manifest.json`); EPSG:32611
<https://epsg.io/32611>; Tversky index <https://en.wikipedia.org/wiki/Tversky_index>.

## 3. Experiments (budget 3/3)

Inputs sha256-verified 5/5 against `registry/data_manifest.json` (`labels`, `sample_submission`,
lidar stack, SGMC via `scripts/fetch_mirrors.py`; `training_features` via git sparse
partial-clone at the pinned ref after the GitHub API quota ran out — IR-L03-02 — concatenated
and verified `4371c82e…` before use; pins prove mirror consistency, not organiser
authentication). Emission geometry identical to LIDAR-02 so the field is the only variable.

**E1 — Leakage canary** (31 channels alone; stop > 0.90). Worst **0.7739** (relief vs SGMC
proxy, the documented relief confound) — PASS. Key replication: the removed signed antislope
net scores **0.3014 / 0.4436** (SGMC / catalogue), confirming the LIDAR-02 canary byte-for-byte
in this checkout. New channels: crest/toe pair **0.7547 / 0.5800** (stronger than either
curvature sign alone), unsigned polarity dominance **0.6222 / 0.5776** (positive against both
truths, unlike the signed version), `snr_step` **0.6566 / 0.5701** (catalogue AUC ≈ raw step
0.5723 while SGMC AUC drops from 0.7509 — deconfounded as designed), fraction
**0.6447 / 0.5207**, Steger offset density **0.5379 / 0.5281** (weak). Composite field
**0.7178 / 0.5763**.

**E2 — Quadrant hide-and-recover holdout** (HOLDOUT-DTI, `src/gems/metric.py`, α=0.2/β=0.8/
R=300 m; visible-faults-only buffer; 48,465 withheld positives): candidate **0.11600
[0.09775, 0.12785]** vs mass-matched random **0.09186 [0.08973, 0.09367]**; paired diff
**+0.02414 [+0.00588, +0.03779] — CI excludes zero, G2 PASS** (LIDAR-02: +0.01438
[−0.00153, +0.02382], FAIL). 3/4 folds won; NW fold still lost (0.0886 vs 0.0930, 22,989 px —
the same fold LIDAR-02 lost). Controls as-is score ~0.005–0.008/fold by construction
(off-catalogue by design).

**E3 — Emission + SGMC control + uniqueness + format.** SGMC off-catalogue pooled
(62,122 px): candidate **0.08011** vs h33-2-b2 **0.09539**, LIDAR-02 **0.09515**, random
**0.06457**, LIDAR-01 0.04993 — **G3 FAIL**. Relief strata (SGMC truth per tercile):
low candidate **0.00351** vs random **0.00466** vs h33 **0.06410** — **G4 FAIL** (dot share
0.337 ≥ 0.25 passed; placement quality in-stratum did not); mid 0.0576 (random 0.0521, h33
0.0904); high 0.1154 (random 0.0890, h33 0.0788 — the only stratum where the candidate
beats the incumbent). Uniqueness vs **70** rasters: max |surface Spearman| **0.0198**;
density-comparable 3-px overlap max **0.6442** (vs LIDAR-02, lift 2.70 — below the 0.70 stop,
disclosed as close; same emission geometry); raw 0.9914 vs the 311,617-dot raster at lift
0.998 (the IR-73 degeneracy); no identical raster — **G5 PASS**. Format: both siblings
**15 PASS + 2 INFO, 0 FAIL/SKIPPED** with the official features raster; float32 EPSG:32611,
3730×3292, exact transform, 0 NaN inside the 5,167,373-cell footprint, all values in [0,1],
siblings pixel-identical inside (independent re-read); min dot→catalogue 2.236 px > 2 px;
median 23.54 px — **G6 PASS**.

**Interpretation (the falsifiable core).** Removing a measured anti-signal and deconfounding
amplitude by local background moved the *prescribed* instrument by +0.0098 paired-diff over
LIDAR-02 and across the significance line, while moving the SGMC inventory proxy *backwards*
by −0.015. Both movements are consistent with one cause: SGMC-mapped faults preferentially
sit in high-relief range fronts (where raw amplitude and relief already point), and the
SNR field deliberately spends ranking power elsewhere — where, in the low-relief third, it
apparently has no real signal to spend (0.0035 ≈ random). The two-instrument disagreement
recorded by earlier sessions is reproduced *within one controlled ablation*, which is itself
a useful, transferable measurement: in this lane, "deconfounded" and "inventory-like" rank
oppositely, and neither instrument can certify the hidden expert-added set.

## 4. Gate table (pre-registered in the builder docstring before any number was read)

| gate | criterion | result |
|---|---|---|
| G1 canary | worst feature-alone AUC ≤ 0.90 | **PASS** 0.7739 |
| G2 holdout | paired diff vs random, 95% CI lower > 0 | **PASS** +0.0241 [0.0059, 0.0378] |
| G3 incumbent | SGMC pooled > h33-2-b2 (same run) | **FAIL** 0.08011 vs 0.09539 |
| G4 range fronts | low share ≥ 0.25 and low-stratum SGMC ≥ random | **FAIL** share 0.337, DTI 0.00351 < 0.00466 |
| G5 uniqueness | ρ ≤ 0.90, no identical, comparable overlap ≤ 0.70, no lift-dup | **PASS** 0.0198 / 0.6442 |
| G6 format | validator PASS both siblings, 0 skipped | **PASS** 15+2 both |

## 5. Irregularities found (all carried in the run card)

- **IR-L03-TOOL-01 (fixed once in the template):** `multiscale_line_fields` thresholded the
  Steger Hessian response `|λ2|` with a percentile of the *Frangi vesselness* running max —
  a unit mismatch making `steger_frac300`'s operating point arbitrary in LIDAR-01/02. Now
  thresholded on the Steger response's own distribution per scale; verified on a synthetic
  ridge (line pixels exactly on the ridge centre). Frangi outputs unchanged.
- **IR-L03-SITE-01 (fixed):** literal merge-conflict markers in `scripts/build_site.py`
  were rendering as text on the live overview and executive-summary pages (both sides of
  both conflicts printed). Resolved keeping both panels; a regression assertion is in
  `tests/test_lidar03_release.py`.
- **IR-L03-02:** GitHub REST API quota (shared token, 5000/h) exhausted mid-session;
  `training_features` fetched by git sparse partial-clone at the pinned commit and
  sha256-verified against the manifest before use. The other four inputs verified normally
  through `fetch_mirrors.py`.
- **IR-L03-03 (pre-existing, flagged, not fixed here):** `current_release.json` points at
  the unique-msc session's raster (`cleared: true`) while `lidar01_block()` renders that
  pointer under a "LIDAR-01 session" heading with `run-card-lidar01.json`'s holdout rows,
  and `docs/downloads/README.md` still calls the pointer LIDAR-01's. Two candidates'
  evidence are conflated in one site panel. Left to the owning session to avoid silently
  rewriting another session's release semantics.
- **IR-L03-04 (fixed):** `tests/test_artifact66.py` and `tests/test_repo_hygiene.py` were
  already failing on `main` — their allowlists never learned about the LIDAR-02 and
  unique-msc downloads. Extended with the same fail-closed conditions as `test_site.py`
  (negative candidates linkable only beside their NOT-OK banner + HOLDOUT-DTI label;
  pointer target read dynamically).
- **IR-L03-05:** owner-reported score provenance (§1.1). No number in this review is
  ORGANIZER-CONFIRMED.

## 6. Next work, in order (for the next session in this lane)

1. **Basin-floor signal problem (the binding constraint).** Within-lane options not yet
   tried: scarp-fraction at coarser aggregation (300–900 m fraction of fraction), or
   fan-surface age contrasts from the dequantised `relief`/`ex_mean` ratio fields. Any
   candidate must first beat random *in the low-relief SGMC stratum* (this run's G4
   instrument) before a full emission is worth building.
2. **Resolve the instrument disagreement** before spending slots: a truth set that is
   neither the catalogue nor an inventory proxy (e.g. the withheld catalogue *segments*
   re-weighted by distance-to-catalogue) would separate "recovers mapped-style faults"
   from "invents SGMC-like linework". Until then both instruments stay falsification-only.
3. **Native 1 m execution (L03-E)** remains the lane's untested premise; it needs an
   environment that can reach USGS 3DEP, with tile inventory + hashes recorded first.
4. **IR-L03-03** release-pointer conflation needs the owning sessions to reconcile
   `current_release.json`, `lidar01_block()` and `docs/downloads/README.md`.
5. Cultural-feature mask (roads/canals/field edges) still does not exist in this checkout;
   every scarp-lane candidate to date is exposed to that mimic class.

## 7. Run card (summary; full JSON in `docs/data/run-card-lidar03.json`)

```json
{
  "hypothesis": "Locally anomalous (signal/~1 km background), within-cell distributed, crest/toe-paired, single-polarity scarps are the off-catalogue faults; the signed antislope preference is an anti-signal whose removal + local-SNR deconfounding gives gain not confined to range fronts.",
  "mechanism": "rank01((0.25*snr + 0.20*persist_snr + 0.15*frac + 0.15*pair + 0.10*pdom + 0.10*frangi + 0.05*steger_offset) * amp_gate); LIDAR-02 emission geometry unchanged (37,654 dots).",
  "named_non_fault_process": "Fluvial terrace risers / irrigation canal banks.",
  "holdout_dti": "HOLDOUT-DTI src/gems/metric.py, 48,465 withheld: candidate 0.11600 [0.09775,0.12785], paired diff vs random +0.02414 [0.00588,0.03779]; SGMC control 0.08011 vs h33-2-b2 0.09539 (FAIL).",
  "correlation_overlap_vs_registry": "70 rasters: max |rho| 0.0198; comparable 3-px overlap max 0.6442 (LIDAR-02, lift 2.70); raw 0.9914 @ lift 0.998 (dense-raster degeneracy); none identical.",
  "raster_sha256": "zeros 6b8e14be5aec8cde4c97b77003aa477922c1594a2bf60c3a53eed6ec52f33a94; nan 09883a2f1498f2a4312c73f95d7909f17737d32b2b72e1d94d19d1bca105b544",
  "validator_output": "Both siblings 15 PASS + 2 INFO, 0 FAIL/SKIPPED; float32 EPSG:32611 3730x3292; 0 NaN inside footprint; values in [0,1]; -zeros fully finite.",
  "submission_name": "gems66-lidar03-localsnr-fracpair-37654dots-20261020T190450Z",
  "submission_note": "LIDAR-03 local-SNR x scarp-fraction x crest/toe pair, antislope-net removed, relief-stratified; GEMSDOE66 lidar03",
  "verdict": "negative"
}
```

Submission slots used by this session: **0**. Organizer-confirmed scores claimed: **none**.
