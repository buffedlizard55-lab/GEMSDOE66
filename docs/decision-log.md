---
layout: default
title: Decision log and negative run
---

# Decision log — H33 attribution, current target, and negative run

**Review date:** 2026-10-11 UTC  
**Decision:** `negative` — no experiment, no TIFF, no download or submission clearance.

## H33-2-B2: what can and cannot be concluded

### Reconciled evidence

1. **The prompt's H33 attribution is not receipt-verified here.** `0.2778` is an **OWNER-REPORTED / USER-SUPPLIED attribution, not an ORGANIZER-CONFIRMED H33 score**. A separate sibling project page (59GEMSDOE) reports a public leaderboard row with that value and says its association with the H33 file is owner-reported. It is not an organizer receipt tying exact raster bytes to a submission row.
2. **GEMSDOE32's own page conflicts with a scored-file interpretation.** It says the H33-2-B2 artifact is unscored, distinguishes a model projection from a score, and states that no organizer score exists for artifacts in that repository. The page links its TIFF and format audit, but this checkout did not download either file and does not treat them as candidate inputs.
3. **The official board is the authority for public standings.** The prompt supplies several dated or apparently current leaderboard numbers that conflict with each other. Use the live official board link for standings, but do not scrape or mirror it here: DrivenData's published Terms of Use restrict automated monitoring/copying and manual monitoring/copying without prior written consent.
4. **No cause can be inferred from a score row alone.** Without a verified receipt, a byte-identical artifact match, and a controlled comparison, we cannot scientifically say that H33's TIFF caused the reported public result or why it received it.

### Plausible mechanism, explicitly an inference

The GEMSDOE32 owner page describes H33-2-B2 as a **pruning/post-processing variant of an earlier dotted field**, deleting predictions near the existing catalogue. If the removed dots were mostly unsupported false positives while useful coverage of the new expert faults remained, a distance-weighted metric could rise. Conversely, because the metric gives partial credit to nearby predictions and the new labels may occur near known faults, the same buffer could delete useful predictions. The proposed mechanism is therefore conditional, not a measured causal explanation.

The H33 page also describes local proxy comparisons and a projected value. Those are owner-reported local evidence, not the organizer's score. They do not satisfy this branch's required run-card format unless the evaluator version, withheld positives, 95% CI, and frozen holdout details are available. No such run assets are present locally.

### Answer to “can we score above it?”

**In principle, a better generalizing detector can score higher. This checkout cannot establish that it will.** The attributed value may not belong to the H33 raster, and the prompt's leaderboard snapshots are inconsistent and time-sensitive. A meaningful attempt must first validate the native-resolution scarp hypothesis against the frozen spatial holdout, pass leakage and range-front checks, and clear the registry uniqueness tests. None can run in this checkout. No score improvement is claimed and no slot should be spent.

## Related lidar results and duplicate risk

Public sibling pages show that this lane is not unexplored across the project family:

- 7GEMSDOE describes regional lidar scarp descriptors with ridge-thinned emission.
- GEMSDOE47 H60 describes a ranked six-channel lidar scarp field; H71 describes multi-channel scarp consensus; H74 describes an eight-channel extension.
- GEMSDOE46 R11F combines lidar scarp and radiometric evidence; radiometric fusion is outside this branch's single-method lane.

These are owner-maintained reports. Their local holdout results do not establish hidden-test performance. Their method overlap makes the specified continuous-surface and final-dot registry checks mandatory. Since the registry is absent, novelty is **unverified**; no candidate surface or dots were made.

The prompt's score-like entries for some of these lidar files also need reconciliation: the linked owner pages describe relevant artifacts as unscored, not uploaded, or local-proxy-only. Without a submission receipt and exact artifact hash, those entries remain owner/user-reported context rather than organizer-confirmed scores.

## Why the “highest score” numbers conflict

The brief contains multiple score snapshots called “current,” including `0.3195` and a higher value, while different sibling pages label public scores, owner-attributed artifacts, model projections, and local proxy results in different ways. The official rules explicitly separate public-board performance from private/final evaluation. A stale value or a sibling site's attribution is not a durable current score or proof of file provenance.

This project does not publish a copied live score table. The [official leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) is linked for an entitled user to open directly. The [Terms of Use](https://www.drivendata.org/termsofuse/) are recorded in the [source register](sources.md).

## Current branch outcome

- The only initial tracked project file was `README.md`; no project code, data, or rasters were available.
- The official competition data page resolved to login. No credentials were requested, stored, or used.
- The requested shared template stack/evaluator/writer/validator, cultural-feature mask, range-front masks, and complete registry are absent.
- The shared tools were not recreated privately. No substitute experiment or synthetic TIFF was generated.
- The holdout, feature-alone canary, pre-placement uniqueness check, final-dot uniqueness check, and TIFF validator were all **not run**.
- No submission slot was used. The site explicitly states **no download / do not submit**.

The detailed fields and null metrics are in [run-card.json](evidence/run-card.json). The next valid work step is not an upload: first make the shared template assets and lawful input data available to this repository, then preregister and run the single top candidate under the original protocol.
