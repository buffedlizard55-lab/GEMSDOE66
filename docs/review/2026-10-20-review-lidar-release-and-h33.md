# Repository review — LIDAR release gate, H33 attribution, and next experiments

**Review date:** 2026-10-20 UTC  
**Scope:** active checkout `GEMSDOE66`; native-resolution LiDAR scarp-channel lane only.  
**Outcome:** **NEGATIVE / NOT CLEARED. Do not download or submit the LIDAR-01 raster.** Its existing audit record shows that the literal duplicate-stop threshold is exceeded. No replacement raster was generated, no experiment was run, and no competition slot was used.

## 1. Executive finding

A prior LIDAR-01 run card described its candidate as cleared after applying a chance-corrected overlap interpretation. That conflicts with the binding run protocol in this repository: **stop if more than 70% of candidate dots are within 3 pixels of any one registry raster**. The stored uniqueness evidence explicitly reports the literal rule as `DUPLICATE - STOP`, with candidate-side overlap above that threshold. Chance correction is informative context, not an exception to the rule. The former public download was therefore withdrawn and the bytes retained only under `artifacts/lidar01/` for audit.

The candidate's recorded local format-validator receipt is a format result, not a uniqueness result. The old internal holdout values remain labeled **HOLDOUT-DTI** in the historic run card; they do not override the duplicate stop or establish a competition score. There is no **ORGANIZER-CONFIRMED** receipt for this raster.

A separate site-build audit also found an orphaned H67 geophysics download: its gate recomputation found the expected raster missing under `artifacts/h67/`, even though copies had been staged under `docs/downloads/`. The fail-closed builder now withdraws those H67 geophysics TIFF/ZIP links and renders **NOT CLEARED**. This is a release-integrity finding, not a judgment about that lane's geology or score; its score claims remain governed by its own evidence and must not be treated as organizer-confirmed.

## 2. Directly auditable repository evidence

| Check | Finding | Evidence / qualification |
|---|---|---|
| Public candidate bytes | Removed from `docs/downloads/`; retained under `artifacts/lidar01/` | Candidate SHA-256 recorded in `evidence/lidar01_uniqueness.json` and the run card; a regression test checks the retained bytes against that digest. |
| Literal dot-overlap gate | **FAIL / STOP** | Recomputed from the retained raster using the historical checker’s 7×7 square dilation, the candidate-side overlap is 0.9210177, matching the stored 0.921018 report and exceeding 0.70. A separate Euclidean-radius-3-pixel check gives 0.8481967; that also exceeds 0.70. The kernel interpretation is therefore immaterial to the stop decision, although it is now explicitly documented. The worst comparison is against a denser raster. |
| Rank correlation | The recorded maximum is below the 0.90 threshold | This does not cancel the independent dot-overlap failure. Evidence is from the earlier local registry scan, not a newly performed scan of a complete organizer corpus. |
| Format | Historical local receipt says format checks passed | It establishes neither official data provenance nor compliance with the uniqueness and scientific gates. The original project-wide requirement that NaN occur only outside the official footprint cannot be freshly rechecked in this environment because the official reference/feature rasters are absent. |
| Native resolution | Not demonstrated | The historic builder says it used 2 m-derived descriptors aggregated at 100 m and did not run Steger/Frangi at the requested native 2–20 m scales. This is a disclosed deviation, not native-resolution validation. |
| Download status | **NOT CLEARED — DO NOT DOWNLOAD OR SUBMIT** | `docs/downloads/current_release.json`, site output, and the LIDAR-01 run card now agree. |
| Competition result | None verified | No submission-page receipt tied to the raster digest is present. No **ORGANIZER-CONFIRMED** score is claimed. |

The dot-overlap figures above were independently recomputed in this review from the retained TIFF and the named registry raster using Rasterio, NumPy and SciPy. The square-window result matches the stored audit to rounding; the Euclidean-window result is additionally reported because the prose rule does not specify its neighborhood metric. Both exceed the stop threshold. The updated regression test checks the TIFF hash and both overlap calculations. The official competition reference/feature rasters remain absent, so official-footprint validation was not recomputed.

## 3. H33-2-B2: what the repository supports, and what it does not

The owner-provided material describes H33-2-B2 as a pruned version of a prior raster. A direct pixel comparison in this review confirms that `registry/rasters/GEMSDOE32__h33-2-b2-zeros.tif` is a strict subset of `registry/rasters/GEMSDOE30__d28-poisson300m-offcat-44090.tif`: the files share CRS, grid and transform; the former has 37,654 positive cells, the latter 44,090, exactly 6,436 base dots are removed, and no dots are added outside the base. The H33 raster SHA-256 matches its local audit JSON. The competition catalogue raster itself is absent, so the removed dots' catalogue distances were not freshly recomputed here.

This supports a **mechanistic hypothesis**: reducing probability mass on already mapped fault traces could improve an off-catalogue objective if those locations have low expected credit, while keeping a substantial off-catalogue search budget. The DTI denominator charges emitted mass, so eliminating low-credit dots can help even without relocating them.

That is not causal proof of the reported competition result. The repository does not contain a submission-page receipt linking the claimed H33 score to the exact raster hash. Existing owner-side audit material labels its competition result unscored and includes an explicitly projected value; that projection is not a score and is excluded. A leaderboard entry, if observed, would still need an organizer receipt or artifact/hash crosswalk before attributing performance to this method.

**Why it may have ranked well, conditionally:** the pruning rule is simple, reduces mass spent close to the known catalogue, and leaves the remaining spatial arrangement intact. If the organizers reward discovery of faults absent from the catalogue, this can improve precision by removing likely low-credit placements. It can also appear successful because of spatial sampling or a denominator effect unrelated to geological detection. Without a controlled same-budget ablation and a verified receipt, the strongest defensible conclusion is that the prune is a plausible explanation, not a verified cause.

## 4. Four same-lane candidates not validated as native-scale holdout experiments

The repository already has related ideas in `docs/data/hypotheses.json`; the entries below are not represented as wholly new discoveries. They are **unrun or incompletely run at the exact, protocol-compliant native resolution**. Ranks are qualitative only, based on physical specificity versus likely mimics and implementation cost. No DTI improvement is projected.

| Rank | Candidate and specific layers | Physical signature and off-catalogue rationale | Difference from implemented work | Expected improvement / cost (qualitative) |
|---:|---|---|---|---|
| 1 | **Slope-aware scarplet-template ablation:** authorized 1 m DEM profiles; fitted amplitude, morphologic age, orientation, and SNR; explicitly validated road/canal/field-edge mask | A fitted cross-profile with finite regional slope and consistent orientation/age could retain subtle scarps missed by coarse relief summaries. | Existing local code includes proxy/template-like aggregates, but does not establish method-faithful native DEM Scarplet template outputs or an independently validated cultural mask. | Highest qualitative prior among these four because it targets the physical scarp profile directly; very high cost. Expected DTI sign and size unknown. |
| 2 | **Ordered paired cross-profile polarity and along-strike continuity:** native DEM profiles; local dip azimuth, crest/toe sequence, width, relief, and persistence | Repeated profiles with consistent polarity and ordered breaks may separate a fault scarp from an isolated edge and expose short or subtle unmapped traces. | Existing work contains line and orientation summaries, but no validated profile-order/continuity ablation under the specified holdout. | Moderate qualitative prior; medium-high cost. Terrace risers, landslide headscarps, road/canal banks remain serious mimics. |
| 3 | **Signed, scale-persistent Steger/Frangi-only ablation:** native DEM; signed ridge/valley response, Hessian eigenstructure, scale persistence, sub-pixel position, and orientation at physical 2–20 m scales | A polarity-consistent line present across adjacent physical scales may preserve line geometry lost in 100 m aggregate features. | Some operators/aggregates exist in the repository, but the requested native 2–20 m sweep has not been demonstrated; existing runs are not an adequate native-scale validation. | Moderate qualitative prior; high cost. Natural stream banks, terrace breaks, DEM seams and cultural edges can mimic it. |
| 4 | **Sharpness / relative-age gate:** `L_ex_max`, `L_step_max`, `L_lappos_max`, `L_lapneg_max`, `L_cross_max`, relief and orientation channels, recalculated only from provenance-cleared inputs | A dimensionless curvature/step sharpness and polarity-asymmetry gate could prioritize youthful, well-preserved scarps and demote broad degraded landforms. | A hypothesis is listed in the registry but is not validated; ratios must not be mislabeled as Scarplet age outputs. | Lower implementation cost and lower qualitative prior than native profile fitting; high risk of selecting terrace risers and channel banks. |

**Top-candidate validation status:** not run in this review. The previous LIDAR-01 session records that its experiment budget was exhausted and exceeded the two-hour cap; the current checkout lacks the authorized source stack needed to redo a proper native-scale evaluation. The `data/` directory is absent and the presence-only preflight is designed to stop rather than retrieve files. No weekly slot was touched. Thus the top candidate has **not** beaten the current valid holdout best under the present strict protocol, and it must not be promoted.

## 5. Data and methodological blockers

- `scripts/fetch_inputs.sh` and `scripts/download_competition_data.sh` are intentionally check-only. They do not download competition files or authenticate.
- The competition data page is login-gated according to the repository source register. Required competition rasters and `1m_DEM_links.csv` are not in this checkout.
- USGS 3DEP's official 1 m DEM collection is a plausible public source, but neither exact tile coverage for the competition footprint nor alignment with its submission grid has been verified here. Do not claim the needed tiles are obtainable until their footprint, access, licenses, hashes, and grid alignment are checked.
- No complete prior-submission raster registry is certified. The available local scan is not equivalent to “all prior rasters.”
- The prior LIDAR holdout scores are historical **HOLDOUT-DTI**, not **ORGANIZER-CONFIRMED**. They are not reproduced in this review and should not be used as evidence that the withdrawn artifact is promotable.
- No leader-board values were fetched or authenticated in this review. User-supplied score values and projections are not treated as verified scores.

## 6. Official / primary references for manual review

These links are copied from the repository's source register. They were **not fetched afresh during this review**; the outbound network allow-list for this workspace does not include these hosts. Their earlier repository statuses are not asserted as fresh verification here.

- [DrivenData — GEMS Prize overview](https://www.drivendata.org/competitions/306/competition-doe-gems/)
- [DrivenData — problem description / submission contract](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
- [DrivenData — competition data tab (login may be required)](https://www.drivendata.org/competitions/306/competition-doe-gems/data/)
- [NLR — official GEMS Prize rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf)
- [USGS — 1 m 3DEP DEM collection](https://data.usgs.gov/datacatalog/data/USGS:77ae0551-c61e-4979-aedd-d797abdcde0e)
- [Sare & Hilley — Scarplet, JOSS 2018](https://doi.org/10.21105/joss.01066)
- [Steger — sub-pixel curvilinear structure detector, TPAMI 1998](https://doi.org/10.1109/34.659930)
- [Frangi et al. — multiscale Hessian filtering, MICCAI 1998](https://doi.org/10.1007/BFb0056195)
- [DrivenData — organizer reference-solution repository](https://github.com/drivendataorg/gems-prize-reference-solution)
- [GEMSDOE32 owner-maintained H33 project page](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html) — unverified in this workspace; not an official competition score receipt.

## 7. Run card — this review

```json
{
  "hypothesis": "Native-scale LiDAR scarp channels can identify some catalogue-missing faults, but the existing LIDAR-01 emission fails the literal registry-overlap stop rule.",
  "mechanism": "Slope-tolerant profile templates and persistent signed ridge/valley lines can measure scarp morphology; no new native-scale run was performed.",
  "named_non_fault_process": "Fluvial terrace risers / stream-bank edges; roads, canals, field boundaries, landslides and DEM seams are additional mimics.",
  "holdout_dti": "Historical HOLDOUT-DTI only; not reproduced in this review and not release-clearing.",
  "correlation_overlap_vs_registry": "Existing scan max |Spearman rho| is below 0.90; candidate-dot overlap is 0.9210177 under the historical 7x7 square dilation and 0.8481967 under Euclidean radius 3 px. Both exceed the 0.70 stop threshold.",
  "raster_sha256": "0da74d0f75d7e6a7c86d5298f3b50941523ee88bcba23e4abd294b02186059c2 (audit-only raster; no public download)",
  "validator_output": "Historical local receipt reports [0,1]/grid checks passed; official inputs are absent, so not freshly revalidated. The site has no downloadable LIDAR-01 file.",
  "submission_name": "gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z (withdrawn; do not submit)",
  "submission_note": "Slope-aware scarp channels; audit-only, duplicate stop triggered",
  "verdict": "negative"
}
```

## 8. Next work, in order

1. Obtain authorized competition inputs and inventory official 1 m DEM tiles against the study footprint; preserve source, license, acquisition, hashes, and exact grid checks.
2. Correct/reuse the shared holdout and writer path; hold out whole segments with buffer, derive catalogue features only from visible faults, and mask visible faults pixel-exactly.
3. Freeze one of the unrun same-lane hypotheses above before looking at its holdout result. Test every feature alone for leakage; stop if AUC exceeds 0.90 pending proof otherwise.
4. Evaluate the candidate under the shared pooled DTI evaluator, with positive counts and 95% spatial-block CI; stratify by lidar-covered range-front and non-range-front blocks.
5. Run both literal registry tests on the pre-placement surface and final dots against a complete registry. Any >0.90 rank correlation or >70% dot overlap is a stop; no density correction waiver.
6. Only if every gate is satisfied, normalize to [0,1], write the exact official-grid float32 GeoTIFF, verify its hash and pixels, and publish a clearly labeled download. Do not use a competition slot before it beats the current valid holdout best.
