# Metric derivation: distance-weighted Tversky index (GEMS Prize)

Status: derived from the official problem page and checked numerically in `tests/test_metric.py`.
No competition raster has been scored, so **no HOLDOUT-DTI value exists** for this project.

Source: official DrivenData GEMS Prize problem description (metric section, reviewed for this audit; exact subpage path recorded as non-clickable text in `docs/data/sources.json`). This page is derived from the published metric formula; the example below is an official worked example, not a project score or `HOLDOUT-DTI` result.

## 1. Official definition (as published)

Prediction `p(x) ∈ [0, 1]` on each cell `x`. Ground-truth set `G` (labelled fault cells).
Kernel with range `R = 300 m` (3 cells at 100 m):

    k(d) = max(1 − d / R, 0)

Weighted terms (α = 0.2 penalises false positives, β = 0.8 penalises false negatives):

    TP_w = Σ_{g∈G} max_x p(x) · k(d(x, g))
    FP_w = Σ_{x: p(x)>0} p(x) · (1 − max_{g∈G} k(d(x, g)))
    FN_w = Σ_{g∈G} (1 − max_x p(x) · k(d(x, g)))
    DTI  = TP_w / (TP_w + α·FP_w + β·FN_w)

The page's worked example (TP_w 3.00, FP_w 1.89, FN_w 2.00) gives 0.6027, which rounds to 0.60. Our `dti_from_terms` reproduces this (test `test_worked_example_from_official_page`).

## 2. Interpretation choices (NOT stated on the page)

| Choice | What we assume | Why it matters |
|---|---|---|
| Distance `d` | Pixel-centre to pixel-centre, metres (`100 × Euclidean index distance`) | Sets the 300 m support and the 3-cell radius |
| NaN prediction | Treated as 0 | Only outside the footprint, where the submission must be NaN |
| ε | 1e-9 added to the denominator | Avoids 0/0 on empty truth |
| Multiple truths | Each truth pixel uses its own nearest prediction (max over x) | Follows the formula as written |
| Truth cells | Label value > 0 is a fault cell (matches the reference notebook's `y > 0`); nodata −1 is excluded | The official page does not state the label encoding |

If the organiser uses a different distance convention, every number in this repo changes. The validator cannot detect this, so any scored claim must cite the evaluator version.

## 3. Identity used in the analysis

Because `FN_w = Σ_g (1 − m_g)` with `m_g = max_x p·k`, we have `TP_w + FN_w = |G|` exactly (test `test_identities`). Define `S = Σ_x p(x)` and `M = Σ_x p(x) · max_g k(d(x,g))`. Then `FP_w = S − M` and

    DTI = T / (0.2 (T + S − M) + 0.8 |G|),   T = TP_w

Two consequences:
- Mass placed far from any truth (`max_g k = 0`) costs 0.2 per unit and earns nothing.
- Mass placed near truth earns credit `k` and costs `1 − k`.

## 4. Marginal break-even rule

Add a dot of mass `p` on a cell `x` that is currently not the nearest emission to any truth cell, and let `k` be the credit that `x` would get from the nearest uncovered truth cell `g`. Then:

- `ΔT = p · k` (the uncovered truth cell's best credit rises from 0 to `p·k`)
- `ΔFP = p · (1 − k)`
- `ΔD = 0.2 ΔT + 0.2 ΔFP = 0.2 p`, where `D = 0.2T + 0.2FP + 0.8|G|` from the identity above

So `DTI' > DTI` iff `(T + p k)/(D + 0.2 p) > T/D`, which reduces to

    k > 0.2 · DTI          (independent of p)

Synthetic worked example: with one of two truth cells covered at credit 1 and the other uncovered, `T = 1`, `FN = 1`, and `DTI0 = 1/(1 + 0.8) = 0.5556`. Break-even credit is 0.1111, i.e. distance `300 (1 − 0.1111) = 266.7 m`. This is a toy calculation, not a competition or H33 result. It is verified against the metric in `test_marginal_break_even_rule`.

In general, for a measured DTI value the break-even distance is `R × (1 − α × DTI)` for an emission that becomes the nearest prediction to a previously uncovered truth cell. Do not substitute an unverified H33 attribution into this formula or present the result as a score.

Implication: extra low-confidence emissions can add false-positive mass. The rule is a mathematical consequence of the stated metric, not a score or projection.

## 5. What is not verified

- The official evaluator code (not published on the page).
- Whether `G` is the full label set or a rescored set in round two.
- Behaviour on the private test set (round one), which is scored at the close.
