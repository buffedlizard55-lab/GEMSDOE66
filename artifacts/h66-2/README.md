# H66-2 research artifact — NOT CLEARED, do not submit

| File | sha256 | Bytes |
|---|---|---|
| `gems66-h66-2-concordance-scarp-37654-20261011T212544Z-allfinite.tif` | `66a8c3afad6a56855a8daf85ac885ef70697ac8b4822bbb3d6c38aafd471134c` | 142,873 |
| `gems66-h66-2-concordance-scarp-37654-20261011T212544Z-allfinite.zip` | (zip of the above) | 106,854 |
| `gems66-h66-2-concordance-scarp-37654-20261011T212544Z-allfinite.json` | writer receipt | 3,744 |

**Status: NEGATIVE-NOT-PROMOTED.** This is the emission of the H66-2 experiment (concordance of three
independent 2 m LiDAR scarp attributes) and it is *not* submission-cleared:

1. The 2026-10-11 audit (`docs/review/2026-10-11-audit.md`) requires a valid buffered whole-segment
   `HOLDOUT-DTI` with a 95 % spatial-block interval, a complete registry, exact official-grid
   validation and two independent scientific reviews before any artifact is published. H66-2 has
   none of those; its holdout was not run (the 3-experiment budget was spent on the ablation, the
   strata/terrain audit and the emission).
2. The H66-2 verdict itself is negative: the mass-matched terrain-only control is within 1.9x of the
   field pooled, the field's mass is 99.95 % upland while the live-best incumbent's edge lives in
   the basin, and the off-catalogue proxy does not order the live board at comparable mass
   (rho=+0.46, p=0.29 over the 35k–70k band).

Why the bytes are here rather than in `docs/downloads/`: the site's release gate forbids publishing
an artifact that has not passed those gates, and `tests/test_site.py` enforces that the site links no
TIFF/ZIP. Keeping the bytes in a research directory preserves the exact deliverable of the session
for audit and for a future cleared release, while the site still says, correctly, that nothing is
cleared to submit.

Format facts (verified by the shared writer's validator, all checks true):
single-band float32 · 3730 × 3292 · EPSG:32611 · transform `[100, 0, 243350, 0, -100, 4508550]` ·
37,654 pixels = 1.0, every other cell 0.0 · no NaN, no value outside [0, 1] · 0 positive pixels on
the mapped catalogue · unique among the 21 rasters present in the registry scan (max |rho| 0.117).

Rebuild:

```bash
python scripts/h66b_emit.py        # writes this trio here (delete existing trio first)
python scripts/h66b_verdict.py     # writes evidence/h66b_verdict.json
python scripts/write_run_card_h66_2.py
```

Evidence: `evidence/h66b_e1_ablation.json`, `evidence/h66b_e2_strata.json`,
`evidence/h66b_emission.json`, `evidence/h66b_verdict.json`, `registry/preregistration-h66-2.json`,
`registry/run_card_h66_2.json`.
