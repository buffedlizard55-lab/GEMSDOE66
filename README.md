# GEMSDOE66 — DOE GEMS Prize (DrivenData 306), lane: native-resolution LiDAR scarplet channels

**Start here →** <https://buffedlizard55-lab.github.io/GEMSDOE66/> ·
submission file to download: `docs/downloads/gems66-h66-1-scarplet-veto-37654-20261011T203224Z-allfinite.tif`
(+ a `.zip` with the same single TIFF). **Download: yes. Promoted for a weekly slot: no — negative gate.**
`docs/executive-summary.html` explains the exact five steps and why the previous
`Predicted values must be in range [0, 1]` rejection cannot happen with these bytes.

---

## 0 · Read this first, every session (the project charter, verbatim from the brief)

> Native-resolution lidar scarp channels. The 100 m stack discards the subtle scarps visible in the 1 m GeoDAWN
> lidar, which plausibly is evidence geologists use to add faults. On high-prior tiles first, compute two sets of
> features. (i) scarplet template matching (Sare & Hilley, JOSS 2018, doi:10.21105/joss.01066), which returns
> amplitude, relative age, orientation and SNR from a GeoTIFF DEM, extended with slope-aware scarp templates
> (AGU 2015 poster T31A-2838, tested in Surprise Valley). (ii) Steger sub-pixel ridge/valley lines (IEEE TPAMI
> 20(2):113–125, 1998) and Frangi multiscale Hessian line measures (MICCAI 1998, LNCS 1496:130–137) at 2–20 m
> scales on a slope-detrended surface. Aggregate to 100 m cells as scarp-pixel fraction, SNR-weighted amplitude,
> structure-tensor orientation coherence and dominant strike. Mask roads, canals and field edges with the existing
> cultural-feature mask, then retrain under spatial CV. Gate: DTI gain on lidar-covered holdout blocks that is not
> confined to range fronts. Finish: normalize to [0,1]; write a float32 EPSG:32611 100 m GeoTIFF (NaN only outside
> the footprint); pass validate_submission.py; run a hash/pixel-agreement check against all prior rasters; offer
> the download only if the gate is met, else log the negative result.

> **PARALLEL-RUN PROTOCOL — read first.**
> 1. **LANE.** Your lane is the single method paragraph above. Stay inside it. If your raster's rank-correlation
>    with any registry raster exceeds [0.90], or more than [70%] of your dots fall within 3 px of one registry
>    raster's dots, you have drifted into another lane: log it as a duplicate and stop. Check this on the surface
>    before placement AND on the final dots.
> 2. **REUSE, DON'T REBUILD.** Use the template's cached feature stack, evaluate_holdout.py and submission_writer.py.
>    Holdout = hide-and-recover: withhold whole fault segments with a buffer, derive every catalogue-based feature
>    only from the visible faults, mask visible faults pixel-exactly, score pooled DTI (alpha 0.2, beta 0.8,
>    300 m triangular kernel). If a shared tool is wrong, fix it once in the template and report it; never keep a
>    private fork.
> 3. **LABEL EVERY NUMBER** as HOLDOUT-DTI (evaluator version, number of withheld positives, 95% CI) or
>    ORGANIZER-CONFIRMED (copied from a submission-page receipt). A projection is never written as a score.
> 4. **LEAKAGE CANARY.** Test each feature alone on the holdout before trusting any result. AUC above [0.90] means
>    leakage until proven otherwise.
> 5. **RUN CARD.** End with one JSON card: hypothesis; mechanism; the named non-fault process that could mimic it;
>    holdout DTI + CI; correlation/overlap vs registry; raster sha256; validator output (no NaN inside the
>    footprint, values in [0,1], CRS/shape/transform match); submission name + note of at most 140 characters;
>    verdict promote / negative. Negative results are deliverables.
> 6. **BUDGET.** Stop after [3] experiments or [2] hours. Do not pick submissions: promotion to a real slot is a
>    separate selector step, within the weekly cap shown on the submission page.

> **Core values (Arena).** *Maximize P(Win)* — weigh tradeoffs, assess risk, choose the path that maximises the
> probability of winning, set emotions aside. *Own the Outcome* — own results end to end, not just your slice; act
> without waiting for permission when you have the means; treat failure and success as signals.

> **Standing requirements.** Verify line by line against official, verified sources; provide links for manual
> review; no hallucinations; flag irregularities; no manual input needed from the owner; the site must make the
> download-and-submit path obvious at the very beginning; 3–5 candidate geological hypotheses ranked by expected
> DTI improvement × implementation cost, each naming the layers, the physical signature, why it catches a fault
> *missing* from the USGS/INGENIOUS catalogue, and how it differs from anything already implemented; validate the
> top candidate on the spatially-blocked holdout **before** touching a weekly submission slot; if a candidate needs
> new external data, name the specific free official source and check it is obtainable first; run Pass 1
> (implement+verify), Pass 2 (bugs, missing requirements, edge cases), Pass 3 (re-check against the original
> request, then improve accuracy/reliability/completeness/quality); open a pull request and merge it; state
> remaining work and limitations.

**Limitations of this sandbox (verified, not assumed).** Egress is allow-listed to
`github.com · codeload.github.com · api.github.com · registry.npmjs.org · pypi.org · files.pythonhosted.org`
(probed: `www.drivendata.org`, `dropbox.com`, `www.usgs.gov`, `zenodo.org` all fail with curl status 000).
Therefore: no DrivenData login download, no 1 m DEM tile, no OpenEI fetch. Everything computed here comes from
hash-pinned mirrors of those files already published in this project's own repositories, plus the public pages
read through the agent's fetcher. 3 GB RAM / 2 cores / no GPU.

## 1 · What this repository is

A self-contained, re-runnable experiment lane for the GEMS Prize, built on the shared template
(`60GEMSDOE`) without forking it:

| path | role |
|---|---|
| `src/gems57/` | vendored **byte-identical** (23/23 files, hash-verified) — official grid, DTI metric, hide-and-recover holdout, validator, gates, uniqueness, emit |
| `src/gems66/spec66.py` | decode of the 12-band 2 m LiDAR stack back to **physical units** using the build sidecar's quantisation rule |
| `src/gems66/channels66.py` | the lane's four named aggregates + scarplet SNR + relative age + the cultural-feature veto |
| `scripts/run_h66.py` | stages `s0…s5` (verify → channels → E1 → spatial CV → holdout → artifact) |
| `scripts/verify66.py` | on-disk validator + registry scan (ρ, 3-px overlap, mass-matched-random correction) |
| `scripts/write_run_card.py` → `registry/run_card.json` | the rule-5 card; the site renders **from** it, so no number is hand-typed |
| `scripts/build_site66.py` → `docs/` | the GitHub Pages site |
| `evidence/h66_*.json` | every measurement, written before the next stage starts |

`docs/` and the small receipts are committed; `data/` and `registry/rasters/` are **not** (100 MB GitHub cap) —
restore them with `bash scripts/fetch_inputs.sh`, which fails closed on any digest mismatch.

## 2 · Result of this session (one paragraph, all numbers tagged)

The scarplet channel set **passed** the lane's holdout clause — HOLDOUT-DTI **0.048007** vs **0.032862** for five
mass-matched uniform-random dot sets on the identical registered protocol (single pooled run of gems57
hide-and-recover; 45,260 withheld positive pixels; no CI claimed for the level because no replicate arms were run),
and **0.040739** restricted to cells off the range-front proxy, so the gain is not confined to range fronts
**[measured-here]**. On the population-matched off-catalogue instrument (USGS SGMC faults >300 m from the
catalogue inside the LiDAR-covered footprint) the emission reaches DTI **0.18796** with **0.0764** credit/dot vs
**0.09028** for mass-matched random — a 2.08× concentration of real, unmapped fault trace **[measured-here]**.
The lane's *headline* mechanism, the cultural-feature veto, is a clean **negative**: it removed 28 of 37,654
top-ranked dots, moved the instrument by **−1.0e-5** DTI (paired 20 km block bootstrap CI
[−1.5e-5, +6.5e-6], P(positive)=0.129), added **0.00000** AUC to the spatial-CV retrain, and received a
**positive** logistic coefficient (1.39, 1.59 in the two usable folds) — valley-floor cultural scarps co-locate
with range-front faults instead of diluting them. Uniqueness vs the 62 rasters physically present:
|ρ|max **0.0196**, worst 3-px overlap **0.5099** (excess over mass-matched random **0.319**), byte- and
pixel-unique **[measured-here, incomplete corpus]**. Format: float32, EPSG:32611, 3730×3292, transform and bounds
identical to `sample_submission.tif`, 37,654 positive pixels, finite values in [0,1], **no NaN anywhere**, 0 dots
on the catalogue **[measured-here]**. No organizer-confirmed score exists for this file; none is projected.

## 3 · Answers to the two questions the brief asks

**Why did `h33-h33-2-b2` score 0.2778 (the family's best)?** Not because its field was good, but because its
*mass* was near-minimal on a well-ranked field: a five-rung pruning ladder (121,131 → 60,069 → 44,090 → 40,199 →
37,654 dots; 0.1922 → 0.2477 → 0.2600 → 0.2708 → 0.2778, all owner-reported) in which every deletion of dots
*raised* the score, and the two deletions that were measured removed dots sitting exactly 1 px and 2 px from the
published catalogue. Under the official metric `DTI = TP_w/(TP_w + 0.2·FP_w + 0.8·FN_w)` with a 300 m triangular
kernel, emitted mass costs `0.2·p(x)·(1−k)`, so a dot pays only if its kernel credit exceeds `0.2·DTI` ≈ 0.056.
The 0.2778 artifact has 0 dots on the catalogue, its nearest dot exactly 3.00 px (300 m) away, and a median dot
1.97 km from it: it is a wide-field emission whose merit is that it stops wasting mass where the answer is provably
not. Source for the algebra and the ladder: the official
[problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) (metric + worked example
TP=3.00/FP=1.89/FN=2.00→0.60, read this session) and `60GEMSDOE/docs/research/why-02778-and-what-beats-it-2026-10-11.md`.

**Can we beat 0.3195 — and what is 0.3195?** 0.3195 is **rank 9 today**, not the maximum: the public board read in
this session is #1 `xiaofanhu` **0.4133**, #2 `cfld__` 0.3585, #3 0.3418, #4 0.3361, #5 0.3333, #6 0.3300,
#7 0.3262, #8 0.3261, #9 0.3195 ([leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/),
mirrored in `registry/leaderboard_snapshot_2026-10-11.json`). **Flagged:** the brief's "current high score 0.3774"
does not appear in today's top rows and "0.3195 is the highest" is rank 9 — treat those as stale, not as targets.
Yes, higher is reachable, but not from this lane: (★) is a ratio, so the two levers are (a) remove worthless mass —
nearly exhausted, ≈2.8e-6 per removed dot; (b) re-rank the same mass so each dot carries more credit — the only
big prize, and the reason the *scarplet* channel was proposed. Measured here, the scarplet channel beats random
2.08× but is an order of magnitude below what (b) needs; every LiDAR-scarp emission this family has uploaded
scored 0.0430–0.1589. The lever with the ceiling is the geo-energy convergence family (geodetic strain +
thermal + conductivity + seismicity), which needs one Actions bridge run because those rasters are not in the
checkout.

## 4 · Reproduce

```bash
python -m venv venv && . venv/bin/activate && pip install -r requirements.txt
bash scripts/fetch_inputs.sh                    # hash-pinned inputs, fails closed
python scripts/run_h66.py s0 s1 s2 s3 s4 s4b s5  # ~4 min, 3 GB RAM, no GPU
python scripts/verify66.py --candidate docs/downloads/<file>.tif
python scripts/write_run_card.py && python scripts/build_site66.py
python -m pytest tests -q                        # 8 passed
```

## 5 · Remaining work / limitations (owned, not deferred)

1. **Governance wall #1 (owner decision).** The registered holdout's truth *is* catalogue trace, so an emission that
   excludes everything within 300 m of the catalogue scores exactly 0.0 there — including a file that scored 0.2778
   live (measured: 0.004729 for the champion, 0.0 for ours). Any rule of the form "must beat the current holdout
   best before a slot" cannot promote off-catalogue work. Flag: `IR-66-GATE-01`.
2. **Governance wall #2 (inherited).** The literal "≤70 % of dots within 3 px of any registry raster" clause is
   unsatisfiable against space-filling comparators (60GEMSDOE measured 99.87 %). We report both the literal number
   (0.5099, passes) and the excess over mass-matched random (0.319, passes), plus the corpus coverage, instead of
   quietly redefining the rule.
3. **Native resolution is blocked by data, not by ideas.** Steger sub-pixel lines and a 2–20 m Frangi sweep on 1 m
   pixels cannot be run footprint-wide here. The fix is one GitHub-Actions bridge job (pattern already exists in
   `60GEMSDOE/.github/workflows/dem10-chi.yml`) that fetches the pinned 3DEP 1 m tiles listed by the competition
   DEM-links PDF, computes the lane's two feature sets at 1 m, and uploads a 100 m aggregate with its own manifest
   — then this lane's E1/E2 re-run on real native data. Flag: `IR-66-RES-01`.
4. **Untried this session (budget spent):** H66-4 pluvial-shoreline veto; E0 native check on the two committed 3 m
   pilot tiles (`src/gemsdoe48/scarp3m.py` vendored for it, hashes pinned in `data/pilot/dem3m/dem_pilot_receipt.json`);
   H66-5 geo-energy convergence.
5. **The 0.2778 anchor is owner-reported**: no organizer receipt links it to the exact bytes; every inversion of it
   inherits that caveat.
