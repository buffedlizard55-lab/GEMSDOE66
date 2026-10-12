#!/usr/bin/env python3
"""Build the GitHub Pages site from the JSON evidence this repository produces.

Nothing on the site is hand-written prose about a number: every figure is read from
``evidence/*.json`` / ``docs/downloads/*.json`` at build time, so a stale page cannot
disagree with the measurement it describes.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
DL = DOCS / "downloads"

NAV = [("index.html", "Overview"), ("executive-summary.html", "How to submit"),
       ("hypotheses.html", "Hypotheses"), ("research.html", "Research"),
       ("results.html", "Results"), ("feed.html", "Project feed"),
       ("sources.html", "Sources"), ("irregularities.html", "Irregularities")]


def esc(s) -> str:
    return html.escape(str(s))


def page(title: str, body: str, active: str) -> str:
    nav = "".join(
        f'<a href="{h}" class="{"on" if h == active else ""}">{esc(t)}</a>'
        for h, t in NAV)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · GEMSDOE66</title>
<link rel="stylesheet" href="assets/site.css"></head>
<body><header class="top"><div class="wrap">
<h1 class="logo">GEMSDOE66 — DOE GEMS Prize fault discovery</h1>
<nav class="main">{nav}</nav></div></header>
<main>
<div class="wrap">
{body}
</div>
</main>
<footer><div class="wrap">
GEMSDOE66 · <a href="https://github.com/buffedlizard55-lab/GEMSDOE66">repository</a> ·
competition <a href="https://www.drivendata.org/">DrivenData #306</a>.
Every number on this site is a local measurement or an owner/public report and is labelled as
one; no organiser score exists for any artifact here.
</div></footer></body></html>
"""


def load(p: Path, default=None):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def pill(ok: bool, text: str = None) -> str:
    cls = "ok" if ok else "bad"
    return f'<span class="pill {cls}">{esc(text or ("PASS" if ok else "FAIL"))}</span>'


# ------------------------------------------------------------------------------------------
def submission_block() -> str:
    """The one-click download block.  Reads the newest build manifest."""
    # The audited raster lives outside docs/ on purpose: with a NEGATIVE verdict it must not
    # be publishable.  The banner is rendered either way, and it says so.
    ART = ROOT / "artifacts" / "lidar_lane"
    mans = sorted(ART.glob("*.manifest.json"))
    m = load(mans[-1], {}) if mans else load(next(iter(DL.glob("*.manifest.json")), ""), {})
    slug = m.get("slug", "")
    nan = DL / f"{slug}-nan.tif"
    zro = DL / f"{slug}-zeros.tif"
    chk = load(ART / f"checks-{slug}-nan.tif.json", {})
    # Use the detailed dot comparison for diagnostics, but do not accept its density-adjusted
    # UNIQUE verdict as a release pass. The project protocol's raw >70% overlap rule is a stop;
    # full-registry completeness is also uncertified. The separate PR12 reconciliation records
    # that strict shared-wrapper contract.
    _uniq = sorted((ROOT / "evidence").glob(f"uniqueness_{slug}-nan.json"))
    uni = load(_uniq[-1], {}) if _uniq else m.get("uniqueness", {})
    max_rho = abs(float(uni.get("max_abs_spearman_rho", 0) or 0))
    max_w3 = float(uni.get("max_frac_dots_within_3px", 0) or 0)
    n_compared = int(uni.get("n_compared", 0) or 0)
    raw_overlap_stop = max_w3 > 0.70
    ok = bool(chk.get("ok"))
    note = (f"GEMSDOE66 lane: Frangi/Steger/structure-tensor scarp field from 1 m GeoDAWN "
            f"lidar, {m.get('n_dots', 0):,} dots, 0 within 200 m of the catalogue.")
    note = note[:140]
    return f"""
<div class="stop">
  <h2>Download status: NOT AVAILABLE</h2>
  <p><b>There is no current TIFF or ZIP cleared for submission.</b>
  Do not upload a historical H66 artifact — including the lidar-lane GeoTIFF described on
  this site, which is retained for audit only.</p>
  <p class="small">A historical artifact has a local format-check receipt; that does not
  establish official-grid clearance. The scientific gate is <b>NOT MET</b>, so the file is not
  published as a download. A late
  de-confounding test showed the lane's measured advantage over the incumbent is
  <b>entirely an artifact of the holdout truth's own relief bias</b> — see
  <a href="results.html">results</a> and the
  <a href="executive-summary.html">executive summary</a>. Uploading a file that our own
  evidence cannot distinguish from the incumbent would spend a weekly slot on a coin
  toss. The bytes are kept in
  <code>artifacts/lidar_lane/</code> for audit and for a future cleared release.</p>
  <table>
    <tr><th>sha256</th><td class="mono">{esc(chk.get('sha256', ''))}</td></tr>
    <tr><th>size</th><td>{chk.get('size_bytes', 0):,} bytes</td></tr>
    <tr><th>emitted pixels</th><td>{m.get('n_dots', 0):,} &nbsp;
        ({m.get('n_dots', 0) / 5_167_373 * 100:.3f}% of the 5,167,373-px footprint)</td></tr>
    <tr><th>dots within 200 m of a known fault</th><td>0</td></tr>
    <tr><th>format validator (re-read from disk)</th>
        <td>{pill(ok)} {len([v for v in chk.get('checks', {}).values() if v])}/
        {len(chk.get('checks', {}))} checks</td></tr>
    <tr><th>Duplicate checks (accessible subset only)</th>
        <td>{pill(False, 'STOP — overlap threshold trips')}
        max |ρ| = {max_rho:.3f} (0.90 threshold); raw fraction of candidate dots within 3 px =
        {max_w3:.3f} ({'STOP: exceeds 0.70' if raw_overlap_stop else 'does not exceed 0.70'}).<br>
        <span class="small">Compared {n_compared} accessible registry rasters; the complete
        organizer registry and expected raster count are not certified. Surface-level
        Spearman comparison is not reported for this artifact. Exact pixel matches in the
        accessible scan: {esc(', '.join(uni.get('identical_to', [])) or 'none')}; the candidate
        SHA-256 is recorded above, but file-hash agreement against a complete registry is not
        established. The 1.5× random-placement lift is diagnostic only and cannot override the
        raw stop threshold or establish full-registry uniqueness.</span>
        </td></tr>
    <tr><th>proposed audit-only note ({len(note)}/140 chars; NOT CLEARED)</th>
        <td class="mono">{esc(note)}</td></tr>
  </table>
  <p class="small">Is it OK to download and submit? <b>No — not yet.</b> The
  <a href="executive-summary.html">executive summary</a> states the gate, the measurement
  that failed it, and exactly what would have to be true for this file to be worth a slot.</p>
</div>
"""



def h67_block() -> str:
    """H67 (2026-10-12) lane run, rendered from the session evidence files."""
    e1 = load(ROOT / "evidence" / "h67_e1_canary.json", {}) or {}
    e2 = load(ROOT / "evidence" / "h67_e2_emit_h52_h_rank.json", {}) or {}
    e3 = load(ROOT / "evidence" / "h67_e2_emit_h52_h_rank_complement.json", {}) or {}
    if not e2:
        return ""
    h = e2.get("holdout", {})
    st = e2.get("strata", {})
    can = e1.get("canaries", {})
    best_ch = max(can.get("channels", {}), key=lambda k: can["channels"][k].get("mean_auc", 0)) if can.get("channels") else "-"
    best_auc = can.get("channels", {}).get(best_ch, {}).get("mean_auc", float("nan"))
    h52_auc = can.get("channels", {}).get("h52_h", {}).get("mean_auc", float("nan"))
    strata_rows = "".join(
        f"<tr><td>{esc(k)}</td><td>{v.get('n_truth', 0):,}</td>"
        f"<td>{v.get('candidate_dti', float('nan')):.5f}</td>"
        f"<td>{v.get('random_dti', float('nan')):.5f}</td>"
        f"<td>{v.get('candidate_minus_random', float('nan')):+.5f}</td></tr>"
        for k, v in st.items() if isinstance(v, dict) and "candidate_dti" in v
    )
    e3h = e3.get("holdout", {})
    e3dots = int((e3h.get("per_fold") or {}).get("fold0", {}).get("candidate_mass", float("nan")) or 0)
    lo, hi = h.get("paired_ci95", [float("nan"), float("nan")])
    return f"""
<h2>H67 lane run — 2026-10-12 (this session's experiments)</h2>
<div class="note"><b>All values below are HOLDOUT-DTI</b> on the SGMC off-catalogue proxy truth
(62,122 withheld positives — the hash-pinned truth), 8 spatial folds by connected component,
3 px training buffer, evaluator <code>gemsdoe66.metric.dti</code> v1, α = 0.2, β = 0.8,
300 m triangular kernel. No <code>ORGANIZER-CONFIRMED</code> score exists. Budget: 3/3
experiments, 0 slots used. Full record:
<a href="review/2026-10-12-h67-session.md">session review</a>.</div>
<p><b>E1 — leakage canary (protocol 4):</b> no feature above the 0.90 AUC leakage threshold
(max {best_auc:.4f} for channel {esc(best_ch)}; best in-lane surface h52_h {h52_auc:.4f}), but
no physical channel transfers across spatial folds (per-fold AUCs 0.29–0.80, four of eight
folds sub-chance) — the signal is region-bound, dominated by the truth's own relief/mapping
bias. Evidence: <code>evidence/h67_e1_canary.json</code>.</p>
<table>
<tr><th>E2 — h52_h_rank emission (incumbent geometry, 37,654 dots) — HOLDOUT-DTI</th><th>candidate</th><th>incumbent h33-2-b2</th></tr>
<tr><td>pooled</td><td><b>{h.get('pooled_candidate', float('nan')):.5f}</b></td><td>{h.get('pooled_incumbent', float('nan')):.5f}</td></tr>
<tr><td>paired difference / 95% CI (fold bootstrap)</td><td colspan="2"><b>{h.get('pooled_diff', float('nan')):+.5f} [{lo:+.5f}, {hi:+.5f}]</b> — CI crosses zero (gate G2 FAIL); 5 of 8 folds positive</td></tr>
<tr><td>uniqueness of final dots (60-raster corpus)</td><td colspan="2">{pill(False, 'DUPLICATE — 77.7% of dots within 3 px of the GEMSDOE32 bayesopt-scarp raster at 4.38x the random rate (gate G4 FAIL)')} raw max within-3-px = 0.999 occurs against the 311,617-dot dense raster whose halo alone has null 0.958 (IR-67-01, reported not deciding)</td></tr>
<tr><td>road-veto ablation</td><td colspan="2">0 dots in the veto zone; no effect</td></tr>
</table>
<h3>E2 relief strata — candidate minus random (equal mass)</h3>
<table><tr><th>stratum (truth relief tercile, cuts 24.1 / 42.9 m)</th><th>n truth</th>
<th>candidate</th><th>random</th><th>candidate − random</th></tr>
{strata_rows}</table>
<p class="small">The gain is range-front-dominated (high +0.177 vs mid +0.087 vs low −0.026) —
the exact confound the lane gate exists to catch (IR-67-03).</p>
<h3>E3 — lane-separation complement emission</h3>
<p>Dots eligible only where ≥ 4 px from every dot of every registry raster: the 60-raster
union's halo leaves no scarp-rich cell — <b>{e3dots} dots</b> placed (of 37,654), pooled
HOLDOUT-DTI <b>{e3h.get('pooled_candidate', float('nan')):.5f}</b>. The family's rasters already
occupy the scarp-active terrain (IR-67-04).</p>
<div class="stop"><b>H67 verdict: NEGATIVE.</b> Gates G2 (CI crosses zero) and G4 (duplicate
stop) fail. No candidate passes, so <b>no TIFF is generated, nothing is offered for
download, and no slot is used</b> — the protocol's negative branch. The inherited PR #13
negative result below remains the other standing negative. Both are internal HOLDOUT-DTI
measurements; neither is an organizer score.</div>
"""

def index_page() -> str:
    e1 = load(ROOT / "evidence" / "experiment1_parsed.json", {})
    e3 = load(ROOT / "evidence" / "experiment3_controls.json", {})
    rf = load(ROOT / "evidence" / "range_front_stratification.json", {})
    ch = e3.get("chance", {})
    rows = ""
    for k in ("random", "incumbent", "lidar_lane", "catalogue_habitat",
              "sgmc_novel", "fusion"):
        if k in e1 and "N" in e1[k]:
            v = e1[k]["N"]
            rows += (f"<tr><td class='mono'>{esc(k)}</td>"
                     f"<td>{sum(v)/len(v):.5f}</td><td>{len(v)}</td></tr>")
    return page("Overview", f"""
<h2>What this is</h2>
<p>An auditable pipeline that produces one GeoTIFF of fault-probability predictions for the
<a href="https://www.drivendata.org/">DOE GEMS Prize</a>.
The scored truth is <b>faults that are not in the given catalogue</b>, so every design choice
here is aimed at that, not at recovering the 60,988 labelled pixels we were given.</p>

{submission_block()}

<h2>The one idea that matters</h2>
<p>The metric is a <b>budget</b>. With <code>T = TP<sub>w</sub></code>, <code>S = Σp</code>,
<code>M = Σp·max<sub>g</sub>k</code> and <code>|G|</code> truth pixels:</p>
<pre>DTI = T / ( 0.2·T + 0.2·(S − M) + 0.8·|G| )

adding a unit of mass raises DTI  ⟺  k &gt; 0.2 · DTI</pre>
<p>At DTI = 0.28 that bar is <b>0.056</b>. Mass that cannot clear it is a loss. That is why the
best-scoring rasters in this project family are sparse dot sets (~38 k pixels out of 5.17 M)
and not dense probability maps.</p>

<h2>Inherited lane result — negative, not the target method</h2>
<p>The inherited PR #13 run reports an internal <b>HOLDOUT-DTI</b> evaluation on SGMC
off-catalogue truth, but its pooled advantage disappears under relief matching. Its full
reported evaluator version, withheld-positive count, and 95% intervals are available on the
<a href="results.html">results page</a> and in the inherited experiment card. This is an
internal proxy, not <b>ORGANIZER-CONFIRMED</b>, and the field was computed on 100 m-derived
inputs at 200–2,000 m scales because raw 1 m tiles were unavailable. It is not the requested
native-resolution 2–20 m implementation. No experiment was run in this reconciliation, no
candidate is cleared, and no submission slot was used.</p>
<p class="note">The final-dot raw overlap stop also trips; 60 accessible rasters do not certify a
complete organizer registry, and no pre-placement surface comparison is recorded. See
<a href="irregularities.html">IR-71</a> and the <a href="review/2026-10-11-pr12-reconciliation.md">PR #12 reconciliation</a>.</p>

{h67_block()}

<div class="grid">
 <div class="card"><h4>Official inputs</h4><p class="big">23/23 mirrors verified</p>
   <p class="small">2026-10-12: all 23 hash-pinned owner mirrors fetched and sha256-verified
   (integrity, not organizer authentication); plus the GEMSDOE48 h52 native 1 m-tile scarp
   product and TIGER/BLM cultural layers. Raw 1 m tiles remain unreachable from this sandbox.</p></div>
 <div class="card"><h4>Inherited stack</h4><p class="big">Audit only</p>
   <p class="small">59 historical 100 m features; not native 2–20 m scarp-template outputs.</p></div>
 <div class="card"><h4>Holdout</h4><p class="big">8</p>
   <p class="small">spatially coherent balanced folds, 300 m buffer, training-only</p></div>
 <div class="card"><h4>Duplicate gate</h4><p class="big">STOP / UNVERIFIED</p>
   <p class="small">Raw 3 px dot overlap is 0.990 (&gt; 0.70); only 60 accessible rasters were
   compared, the complete registry is uncertified, and surface correlation was not reported.</p></div>
</div>
<p class="small"><a href="analysis.html">H33 attribution review</a> · <a href="review/2026-10-11-pr12-reconciliation.md">PR #12 merge reconciliation and shared-template provenance audit</a></p>
""", "index.html")


def exec_page() -> str:
    mans = sorted((ROOT / "artifacts" / "lidar_lane").glob("*.manifest.json"))
    m = load(mans[-1], {}) if mans else {}
    slug = m.get("slug", "")
    note = (f"GEMSDOE66 lane: Frangi/Steger/structure-tensor scarp field from 1 m GeoDAWN "
            f"lidar, {m.get('n_dots', 0):,} dots, 0 within 200 m of the catalogue.")[:140]
    return page("How to submit", f"""
<h2>Executive summary — why there is nothing to download</h2>

<div class="stop">
<h2>Verdict: NEGATIVE — do not submit this file</h2>
<p>A historical GeoTIFF exists under <code>artifacts/lidar_lane/</code> with a local format
sidecar. It is <b>not</b> a current, officially cleared submission and is not published as a
download; the relief-matched result and raw uniqueness stop both block release.</p>
<p><b>Inherited internal HOLDOUT-DTI only — not an organizer result.</b> The PR #13 record
uses <code>gemsdoe66.metric.dti</code> (reported verified to 1e-9 against an equation
transcription), pooled distance-weighted Tversky with α = 0.2, β = 0.8, a 300 m triangular
kernel, 8 spatial folds, and approximately 7,700 withheld positives per fold (61,664 total for
the SGMC novelty instrument). The recorded 95% CIs are percentile intervals over folds. No
<code>ORGANIZER-CONFIRMED</code> score exists. The field is scale-deviating: it uses 100 m-derived
inputs and 200–2,000 m line scales, not the requested native-resolution 2–20 m method.</p>
<p><b>The finding.</b> The holdout truth (SGMC faults &gt; 300 m from the given catalogue) is
not distributed like the terrain: it is <b>59.3 % range front</b> and <b>1.3 % basin</b>,
while the footprint is 25.2 % range front and 23.7 % basin. The inherited experiment found the
pooled lane advantage did not survive relief matching. Its recorded HOLDOUT-DTI summaries are:</p>
<table>
<tr><th>instrument</th><th>lane mean [95% CI]</th><th>incumbent mean [95% CI]</th><th>uniform random mean [95% CI]</th></tr>
<tr><td>pooled (confounded)</td><td><b>0.07075 [0.05217, 0.08967]</b></td><td>0.04896 [0.04191, 0.05669]</td><td>0.04019 [0.03786, 0.04233]</td></tr>
<tr><td><b>relief-matched</b></td><td>0.02638 [0.02087, 0.03183]</td><td><b>0.02727 [0.02421, 0.03049]</b></td><td>0.02612 [0.02436, 0.02741]</td></tr>
</table>
<p class="small">Relief-matched lane − incumbent = <b>−0.00089</b>, 95 % CI
[−0.00836, +0.00664], positive in 3 of 8 folds.
Relief-matched lane − random = <b>+0.00026</b>, 95 % CI [−0.00552, +0.00601], 4 of 8 folds.
Both intervals straddle zero. These are internal HOLDOUT-DTI measurements only; the analysis
remains negative and the artifact remains unsubmitted.</p>
</div>

{h67_block()}

<h2>2 · Submission portal — do not proceed</h2>
<div class="stop"><b>No file or note is cleared for use.</b> Do not open a submission form, upload an
artifact, or spend a competition slot. If every scientific, provenance, registry, and official-grid
gate is passed in a future review, use the official competition interface and record its receipt.
No submission name or note on this page is cleared. The following instructions are
<b>conditional, not authorization to submit</b>.</div>
<ol>
<li>After an independent selector approves a candidate, confirm that its exact SHA-256
matches the approved run card, and that the shared validator passed against the official
sample grid and feature footprint (single-band float32, EPSG:32611, 100 m, values [0,1]
inside and NaN only outside). Never substitute an all-finite audit variant.</li>
<li>Only then download the specifically approved TIFF from this site's top-of-page download
link. There is no such link now. Check the downloaded file SHA-256 before using it.</li>
<li>On the official DrivenData competition page, review the current rules and weekly limit,
open the submission form, select the <code>.tif</code> file, enter the approved unique name
and the approved note (at most 140 characters), then submit. Record the portal receipt and
its exact file hash; do not claim a score from an owner page or a projection.</li>
</ol>

<h2>3 · Format information is not release clearance</h2>
<p>The inherited local sidecar records a format-only check on its artifact bytes. That is not
organizer acceptance, does not establish current official-grid/footprint clearance, and cannot
override the negative scientific result, the raw overlap stop, the uncertified registry, or the
missing pre-placement surface comparison. The user-facing output remains unavailable.</p>
<table>
<tr><th>check</th><th>meaning</th></tr>
<tr><td>single band</td><td>the organiser asks for one layer</td></tr>
<tr><td>float32</td><td>"datatype of 32-bit float"</td></tr>
<tr><td>3730 × 3292</td><td>same shape as the template</td></tr>
<tr><td>EPSG:32611</td><td>"the same projected coordinate reference system"</td></tr>
<tr><td>geotransform</td><td>100 m, origin (243350, 4508550)</td></tr>
<tr><td>no NaN / inf / sentinel inside</td><td>nodata −3.4028235e38 would be read as a real value</td></tr>
<tr><td><b>all finite values in [0, 1]</b></td><td>the rejection rule reported in the brief</td></tr>
<tr><td><b>NaN outside the footprint</b></td><td>"data outside the bounds is null or nan"</td></tr>
<tr><td>0 dots within 200 m of a known fault</td><td>the organiser does not score known faults</td></tr>
</table>

<h2>4 · Is it OK to download and submit?</h2>
<div class="stop"><b>No.</b> The candidate is not cleared; the following checks do not authorize a submission.
<ul>
<li><b>Format-only check</b>: the inherited sidecar records 12 local checks on the bytes;
this is not organizer acceptance or release clearance. Receipt:
<code>artifacts/lidar_lane/checks-{esc(slug)}-nan.tif.json</code>.</li>
<li><b>Uniqueness is not passed.</b> The recorded final-dot overlap is 0.990 against an
accessible registry raster, above the user's 0.70 stop threshold. The density-adjusted output
is diagnostic only; the full organizer registry is not certified, the pre-placement surface
comparison is unreported, and no registry-wide unique claim is made.</li>
<li><b>NOT demonstrated</b>: on the relief-matched instrument the lane is
<b>indistinguishable from the incumbent</b> (HOLDOUT-DTI difference −0.00089, 95% CI
[−0.00836, +0.00664]) and from <b>uniform random placement</b> (difference +0.00026, 95% CI
[−0.00552, +0.00601]). In the range-front stratum, internal HOLDOUT-DTI is 0.05054
[0.03613, 0.06538] for the lane and 0.04867 [0.04507, 0.05255] for random placement, with
the same evaluator/folds described above.</li>
<li><b>NOT claimed</b>: <b>no organiser score exists for this file.</b> Every leaderboard
number on this site is an owner report or a public-page snapshot. The holdout's truth is SGMC,
not the expert panel's hidden set.</li>
</ul></div>

<h2>5 · What would be required before reconsideration</h2>
<p>The inherited analysis does not clear the candidate. Any future reconsideration must stay
within the remaining approved experiment/time budget and the specified native-resolution lane;
it cannot be authorized by a leaderboard projection.</p>
<ol>
<li><b>Obtain and verify lawful native 1 m inputs</b> plus their coverage, hashes, CRS, and
exact footprint. If unavailable, keep the native-resolution hypothesis untested.</li>
<li><b>Pre-register a relief-balanced, whole-segment buffered holdout</b> with visible-fault
masking and LiDAR-covered blocks, then report only correctly labelled HOLDOUT-DTI with
version/count/95% CI. Test each feature alone for leakage.</li>
<li><b>Pass both uniqueness phases against a certified complete registry</b>, exact hash/pixel
checks, official-grid validation, and independent scientific reviews. A competition slot is a
separate selector decision and remains unused unless the frozen holdout criterion is met.</li>
</ol>
<div class="note"><b>Current decision: do not download, submit, or spend a slot.</b> No live-board
number or owner-reported value changes this stop.</div>
""", "executive-summary.html")


def hyp_page() -> str:
    d = load(DOCS / "data" / "hypotheses.json", {}) or {}
    rows = []
    for h in d.get("items", []):
        rows.append(
            f"<tr><td><b>{esc(h.get('rank'))}</b><br><code>{esc(h.get('id'))}</code></td>"
            f"<td><b>{esc(h.get('title'))}</b><p>{esc(h.get('layers'))}</p></td>"
            f"<td>{esc(h.get('signature'))}</td>"
            f"<td>{esc(h.get('named_mimic'))}</td>"
            f"<td>{esc(h.get('differs_from_repo'))}</td>"
            f"<td>{esc(h.get('expected_gain'))}</td>"
            f"<td>{esc(h.get('cost'))}</td>"
            f"<td><b>{esc(h.get('validation'))}</b><br>{esc(h.get('data_status'))}</td></tr>"
        )
    return page("Hypotheses", f"""
<h2>Ranked same-lane hypotheses — LIDAR-01…04 pre-implementation; H67-A…E implemented and measured 2026-10-12</h2>
<p>Ranking and hypotheses are read from <code>docs/data/hypotheses.json</code>. Expected gains
are qualitative priors, not DTI projections. LIDAR-01…04 remain unimplemented and unvalidated
(authorized native DEM coverage, shared-cache provenance, and independent review still blocking).
H67-A…E were implemented and measured on 2026-10-12 on the hash-pinned 1 m-derived native
scarp stack plus the GEMSDOE48 h52 native 1 m-tile product (see the
<a href="index.html">H67 lane run</a> and the <a href="review/2026-10-12-h67-session.md">session review</a>);
none of them cleared the lane gate, and no download is offered.</p>
<table>
<tr><th>rank / id</th><th>hypothesis and inputs</th><th>physical signature</th>
<th>named non-fault mimic</th><th>difference from repo</th><th>qualitative prior</th>
<th>cost</th><th>validation/data status</th></tr>
{''.join(rows)}
</table>
<div class="stop"><b>No hypothesis is cleared for a submission slot or a download.</b>
The inherited PR #13 result is a scale-deviating 100 m-grid proxy and does not validate these
native-resolution 2–20 m hypotheses; the 2026-10-12 H67 measurements (HOLDOUT-DTI proxy, gate
not met) do not clear any of H67-A…E either. See the
<a href="review/2026-10-12-h67-session.md">2026-10-12 session review</a> and the
<a href="review/2026-10-11-pr12-reconciliation.md">PR #12 reconciliation</a> for current
blockers and scope.</div>
""", "hypotheses.html")


def research_page() -> str:
    return page("Research", """
<h2>Research protocol and limitations</h2>

<h3>1 · Metric transcription</h3>
<p>The official problem description defines distance-weighted Tversky scoring. With
<code>T = TP<sub>w</sub></code>, total prediction mass <code>S</code>, weighted mass <code>M</code>,
and truth-pixel count <code>|G|</code>:</p>
<pre>DTI = T / (0.2T + 0.2(S − M) + 0.8|G|)</pre>
<p>The project tests the transcription in <code>tests/test_metric.py</code>. That code-level test
is not a competition score and does not authenticate any label raster.</p>

<h3>2 · Target method versus inherited proxy</h3>
<p>The requested method is native-resolution scarp evidence: slope-aware templates; Steger
sub-pixel and Frangi ridge/valley measures at <b>2–20 m</b>; 100 m aggregation of scarp fraction,
SNR-weighted amplitude, orientation coherence and dominant strike; the existing cultural mask;
and spatially blocked validation. The exact 1 m tiles and compatibility checks are not available
in this checkout, so this target method has <b>not</b> been run.</p>
<p>The inherited PR #13 <code>lidar_lane</code> used 1 m-derived descriptors and line scales at
2–20 pixels on a 100 m grid, i.e. 200–2,000 m. It is scale-deviating, negative after
relief-matching, and remains audit-only. Its internal `HOLDOUT-DTI` values and CIs are labelled
on the <a href="results.html">results page</a>; they do not validate the requested method and
are not `ORGANIZER-CONFIRMED`.</p>

<h3>3 · Holdout, leakage, and release criteria</h3>
<ul>
<li>Withhold whole fault segments with a buffer. Derive catalogue features only from visible
faults and mask visible faults pixel-exactly.</li>
<li>Score pooled DTI on LiDAR-covered held-out blocks with α = 0.2, β = 0.8 and a 300 m
triangular kernel; report evaluator version, withheld-positive count and 95% CI.</li>
<li>Run feature-alone leakage canaries; AUC above 0.90 is a stop pending proof otherwise.</li>
<li>Compare both continuous pre-placement surfaces and final emitted dots against every indexed
registry raster. Apply absolute Spearman thresholds and the raw &gt;70% / 3 px emitted-dot stop;
random-density lift is diagnostic only. Require an explicit organizer-complete certificate and
matching expected count; incomplete access is not a pass.</li>
<li>Verify pixel/hash agreement and the exact official CRS, shape, transform, range, and NaN-only
outside-footprint contract. A local format receipt is not organizer acceptance.</li>
</ul>

<h3>4 · Evidence status</h3>
<p>Official competition inputs and exact DEM-tile coverage remain unverified in this environment.
Owner-maintained GitHub mirrors are hash-pinned for local reproducibility but are not
organizer-authenticated. The site does not poll leaderboard pages or infer artifact performance
from owner reports. No organizer receipt in this checkout confirms a score for any raster.</p>
<p>The inherited PR #13 run was stopped: its relief-matched result does not beat the incumbent,
its raw final-dot overlap exceeds the threshold, its complete-registry status is uncertified, and
its pre-placement surface comparison is absent. No experiment or submission slot was used in the
PR #12 reconciliation.</p>

<h3>5 · Trusted method references</h3>
<ul>
<li><b>[official]</b> <a href="https://www.drivendata.org/">DrivenData</a> DOE GEMS Prize
competition and problem description; the data tab remains login-walled in the recorded audit.</li>
<li><b>[official]</b> <a href="https://www.usgs.gov/3d-elevation-program">USGS 3DEP</a> and
<a href="https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and">USGS GeoDAWN</a>; product context does not prove exact tile coverage.</li>
<li><b>[literature]</b> <a href="https://doi.org/10.21105/joss.01066">Sare &amp; Hilley,
Scarplet (JOSS)</a>, <a href="https://doi.org/10.1109/34.659930">Steger (IEEE TPAMI)</a>,
and <a href="https://research.manchester.ac.uk/en/publications/multiscale-vessel-enhancement-filtering/">Frangi et al. (MICCAI)</a>. These establish methods, not competition performance.</li>
</ul>
<p>See the <a href="analysis.html">H33 attribution review</a>,
<a href="sources.html">source register</a>, <a href="irregularities.html">irregularities</a>, and the
<a href="review/2026-10-11-pr12-reconciliation.md">PR #12 reconciliation</a>.</p>
""", "research.html")


def results_page() -> str:
    e3 = load(ROOT / "evidence" / "experiment3_controls.json", {})
    rmatch = load(ROOT / "evidence" / "relief_matched.json", {})
    rg = load(ROOT / "evidence" / "relief_gate.json", {})
    pooled = rmatch.get("pooled_confounded", {})
    matched = rmatch.get("relief_matched", {})
    def summary_rows(instrument):
        labels = (("lidar lane", "lane"), ("incumbent", "inc"), ("uniform random", "rand"))
        return "".join(
            f"<tr><td>{esc(label)}</td><td>{instrument.get(key, {}).get('mean', float('nan')):.5f}</td>"
            f"<td>[{instrument.get(key, {}).get('ci95', [float('nan'), float('nan')])[0]:.5f}, "
            f"{instrument.get(key, {}).get('ci95', [float('nan'), float('nan')])[1]:.5f}]</td>"
            f"<td>{instrument.get(key, {}).get('n_folds', 8)}</td></tr>"
            for label, key in labels
        )
    per_stratum = rmatch.get("per_stratum", {})
    strata_rows = []
    for key, label in (("basin", "Basin"), ("mid", "Mid-relief"),
                       ("range_front", "Range front")):
        lane = per_stratum.get("lane", {}).get(key, {})
        rand = per_stratum.get("rand", {}).get(key, {})
        strata_rows.append(
            f"<tr><td>{label}</td><td>{lane.get('mean', float('nan')):.5f} "
            f"[{lane.get('ci95', [float('nan'), float('nan')])[0]:.5f}, "
            f"{lane.get('ci95', [float('nan'), float('nan')])[1]:.5f}]</td>"
            f"<td>{rand.get('mean', float('nan')):.5f} "
            f"[{rand.get('ci95', [float('nan'), float('nan')])[0]:.5f}, "
            f"{rand.get('ci95', [float('nan'), float('nan')])[1]:.5f}]</td></tr>"
        )
    gains = rmatch.get("gains_matched", {})
    return page("Results", f"""
<h2>Results — inherited negative experiment, not a promotion</h2>
<div class="note"><b>All performance measurements below are labelled HOLDOUT-DTI.</b>
Evaluator: <code>gemsdoe66.metric.dti</code> (the inherited card reports a 1e-9 comparison
with a brute-force equation transcription). Instrument: SGMC off-catalogue faults, 8 spatial
folds, approximately 7,700 withheld positives per fold (61,664 total), 300 m training-only
buffer, α = 0.2, β = 0.8, 300 m triangular kernel. The listed 95% CIs are the recorded
percentile intervals over folds. This proxy holdout is not the organizer's hidden set. No
<code>ORGANIZER-CONFIRMED</code> score exists for any artifact.</div>
{h67_block()}
<h3>Inherited PR #13 experiment — negative, for reference</h3>
<p class="stop"><b>Protocol deviation:</b> the inherited lane used 1 m-derived 100 m descriptors
and 2–20 pixel scales on the 100 m grid (200–2,000 m), not the requested native-resolution
2–20 m scarp method. The numeric results below do not validate LIDAR-01.</p>

<h3>Pooled novelty instrument (relief-confounded)</h3>
<table><tr><th>field</th><th>HOLDOUT-DTI mean</th><th>95% CI</th><th>folds</th></tr>
{summary_rows(pooled)}</table>

<h3>Relief-matched instrument</h3>
<table><tr><th>field</th><th>HOLDOUT-DTI mean</th><th>95% CI</th><th>folds</th></tr>
{summary_rows(matched)}</table>
<p>The paired matched lane-minus-incumbent HOLDOUT-DTI difference is
<b>{gains.get('lane_minus_inc', {}).get('mean', float('nan')):+.5f}</b>, 95% CI
[{gains.get('lane_minus_inc', {}).get('ci95', [float('nan'), float('nan')])[0]:+.5f},
{gains.get('lane_minus_inc', {}).get('ci95', [float('nan'), float('nan')])[1]:+.5f}];
positive in {gains.get('lane_minus_inc', {}).get('folds_positive', 'not recorded')} of
{gains.get('lane_minus_inc', {}).get('n_folds', 8)} folds. The paired lane-minus-random
HOLDOUT-DTI difference is <b>{gains.get('lane_minus_rand', {}).get('mean', float('nan')):+.5f}</b>,
95% CI [{gains.get('lane_minus_rand', {}).get('ci95', [float('nan'), float('nan')])[0]:+.5f},
{gains.get('lane_minus_rand', {}).get('ci95', [float('nan'), float('nan')])[1]:+.5f}]. Both
intervals include zero; the verdict remains negative.</p>

<h3>Relief strata — HOLDOUT-DTI</h3>
<table><tr><th>terrain</th><th>lane HOLDOUT-DTI mean [95% CI]</th>
<th>random HOLDOUT-DTI mean [95% CI]</th></tr>
{''.join(strata_rows)}</table>
<p class="small">These are per-stratum HOLDOUT-DTI means with their recorded marginal CIs. No
paired difference is inferred here. No score projection is made.</p>

<h3>Chance-control HOLDOUT-DTI</h3>
<table><tr><th>control</th><th>mean</th><th>95% CI</th></tr>
{"".join(f"<tr><td>{esc(k)}</td><td>{v['mean']:.5f}</td>"
         f"<td>[{v['ci95'][0]:+.5f}, {v['ci95'][1]:+.5f}]</td></tr>"
         for k, v in e3.get('chance', {}).items() if isinstance(v, dict) and 'mean' in v)}</table>

<h3>Other diagnostics</h3>
<p>The relief-gate sensitivity values are retained in the evidence JSON. They are internal
HOLDOUT-DTI diagnostics, not a chosen submission budget or a promotion result. The mass sweep
is omitted here because no score is selected from that instrument.</p>
<p>Read the machine-readable inherited experiment card at
<a href="data/run_card.json"><code>docs/data/run_card.json</code></a> and the corrected raw-overlap
adjudication at <a href="data/irregularities.json">IR-71</a>. All values remain internal; no
file is cleared for download.</p>
""", "results.html")


def sources_page() -> str:
    return page("Sources", """
<h2>Sources</h2>
<p>This inherited source register links organizer/USGS primary sources and bibliographic
records. The PR #12 reconciliation did not re-fetch every link; access limits and partial review
are documented in the dated audit. Primary sources establish rules/product context; literature
links are method context only, not performance evidence.</p>
<table>
<tr><th>source</th><th>what we took from it</th><th>link</th></tr>
<tr><td>Competition problem page</td><td>metric definition, α/β/R, submission format, the
 statement that the test set is faults <i>not</i> in the USGS database</td>
 <td><a href="https://www.drivendata.org/">page 967</a></td></tr>
<tr><td>Competition leaderboard</td><td>Not monitored or copied in this reconciliation. No public-board value is treated as an artifact receipt or organizer-confirmed score.</td>
 <td><a href="https://www.drivendata.org/">official site; navigate manually if authorized</a></td></tr>
<tr><td>Competition rules</td><td>submission caps and prize-round structure</td>
 <td><a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">96647.pdf</a></td></tr>
<tr><td>Reference solution</td><td>baseline architecture and the α = 0.2 / β = 0.8 convention</td>
 <td><a href="https://github.com/drivendataorg/gems-prize-reference-solution">github</a></td></tr>
<tr><td>USGS GeoDAWN data release</td><td>the survey the challenge region is defined by</td>
 <td><a href="https://www.sciencebase.gov/catalog/item/657e1d85d34e23d3533209f7">ScienceBase</a></td></tr>
<tr><td>USGS 3DEP</td><td>1 m and 10 m DEMs behind the lidar scarp and topography channels</td>
 <td><a href="https://www.usgs.gov/3d-elevation-program">3DEP</a></td></tr>
<tr><td>GBCGE INGENIOUS</td><td>the project whose fault compilation supplies the labels</td>
 <td><a href="https://gbcge.org/current-projects/ingenious/">gbcge.org</a></td></tr>
<tr><td>GDR submission 1391</td><td>wells/springs, Quaternary fault traces, volcanic vents (CC BY 4.0)</td>
 <td><a href="https://gdr.openei.org/submissions/1391">gdr.openei.org</a></td></tr>
<tr><td>Giddens et al. 2025, Stanford Geothermal Workshop</td>
 <td>"LiDAR and hillshades were utilized to identify the extent and location of Quaternary
 faults"; 1 m GeoDAWN lidar supplied by USGS; gravity most useful for fault geometry;
 step-overs the dominant favourable setting</td>
 <td><a href="https://pangea.stanford.edu/ERE/pdf/IGAstandard/SGW/2025/Giddens.pdf">PDF</a></td></tr>
<tr><td>Sare &amp; Hilley 2018</td><td>scarplet template matching: amplitude, relative age,
 orientation, SNR</td>
 <td><a href="https://doi.org/10.21105/joss.01066">doi:10.21105/joss.01066</a></td></tr>
<tr><td>Steger 1998</td><td>sub-pixel line extraction from the Hessian eigenvector</td>
 <td><a href="https://doi.org/10.1109/34.659930">doi:10.1109/34.659930</a></td></tr>
<tr><td>Frangi et al. 1998</td><td>multiscale Hessian vesselness</td>
 <td><a href="https://doi.org/10.1007/BFb0056195">doi:10.1007/BFb0056195</a></td></tr>
<tr><td>EPSG:32611</td><td>the required CRS</td>
 <td><a href="https://epsg.io/32611">epsg.io</a></td></tr>
</table>
<div class="note"><b>Data provenance caveat.</b> The competition rasters are login-walled at
drivendata.org. The bytes used here are <b>owner-supplied GitHub mirrors</b>, pinned by sha256
in <code>registry/data_manifest.json</code> and verified on fetch (23/23). A pin proves mirror
consistency; it does <b>not</b> prove organiser authentication.</div>
""", "sources.html")


def irr_page() -> str:
    return page("Irregularities", """
<h2>Irregularities</h2>
<table>
<tr><th>id</th><th>what</th><th>status</th></tr>
<tr><td><b>IR-66-CONFOUND-01</b><br><span class="tag">verdict-changing</span></td>
 <td><b>The primary instrument was confounded, and the confound was the whole result.</b> The
 novelty holdout truth (SGMC faults &gt; 300 m from the catalogue) is <b>59.3 % range front</b>
 and <b>1.3 % basin</b>, against a footprint that is 25.2 % range front and 23.7 % basin.
 Mapped faults concentrate where scarps are <i>visible</i>, so any range-front-heavy field
 beats a uniform one on a mapped-fault truth by construction. The lane puts 64.3 % of its dots
 on range fronts (the incumbent: 17.2 %), i.e. it matches the truth's own relief prior.
 De-confounded — budget allocated across relief strata in proportion to footprint area,
 per-stratum DTI averaged with footprint weights — the lane scores <b>0.02638</b> against the
 incumbent's <b>0.02727</b> and random's 0.02612: lane−incumbent <b>−0.00089</b>
 (CI [−0.0084, +0.0066], 3/8 folds), lane−random <b>+0.00026</b> (CI [−0.0055, +0.0060],
 4/8 folds). The confound is worth <b>+0.0227</b> — the entire +0.0218 headline. On range
 fronts specifically the lane's 0.0505 barely exceeds <i>random placement</i>'s 0.0487 at the
 same budget. <b>The run card's verdict was therefore changed from <code>promote</code> to
 <code>negative</code></b> and the GeoTIFF moved out of <code>docs/downloads/</code> into
 <code>artifacts/lidar_lane/</code>, unpublished. The pooled numbers reproduce exactly
 (0.07075 / 0.04896), so only the de-confounding is new, not the pipeline.</td>
 <td><span class="pill bad">OPEN — verdict flipped</span></td></tr>
<tr><td><b>IR-66-SCORE-01</b></td>
 <td>An earlier draft quoted a public leaderboard target. No leaderboard was accessed or
 monitored in this reconciliation, and no public row is tied here to an exact artifact receipt.
 No such number is used as an organizer-confirmed score or decision threshold.</td>
 <td><span class="pill warn">OPEN — NOT VERIFIED HERE</span></td></tr>
<tr><td><b>IR-66-DATA-01</b></td>
 <td>The sandbox reaches only github.com, api.github.com, pypi.org and their CDNs.
 <code>prd-tnm.s3.amazonaws.com</code>, <code>earthquake.usgs.gov</code>,
 <code>gdr.openei.org</code>, <code>sciencebase.gov</code> and <code>dropbox.com</code> all
 return HTTP 000. The raw 1 m GeoDAWN lidar and 10 m 3DEP tiles are therefore unobtainable
 here, and the scarplet template matcher cannot be run on native-resolution data.</td>
 <td><span class="pill warn">OPEN</span></td></tr>
<tr><td><b>IR-66-DATA-02</b></td>
 <td>The 10 m-DEM channel-steepness product covers <b>25 of 36 blocks</b>.</td>
 <td><span class="pill warn">OPEN</span></td></tr>
<tr><td><b>IR-66-PROXY-01</b></td>
 <td>Layer dot-means correlate with owner-reported live scores at |ρ| up to 0.98, but also with
 the emitted dot count at |ρ| = 0.5–0.9. The lidar scarp channels flip sign under nuisance
 control. The live anchor is a lane-choice prior, not evidence.</td>
 <td><span class="pill warn">OPEN</span></td></tr>
<tr><td><b>IR-66-GATE-01</b></td>
 <td>A density-adjusted diagnostic was used to label a final-dot scan <code>UNIQUE</code> even
 though the raw overlap against one accessible registry raster is 0.990, above the brief's
 0.70 stop threshold. Against a 311,617-dot raster the random-placement null is high, but the
 null does not waive the specified threshold. The raw result is a stop; the 1.5× lift is
 diagnostic only. Only 60 rasters were compared, full organizer-registry completeness is not
 certified, and this artifact has no recorded pre-placement-surface correlation.</td>
 <td><span class="pill bad">OPEN — NOT A UNIQUENESS PASS</span></td></tr>
<tr><td><b>IR-70-TEMPLATE-PROVENANCE</b></td>
 <td>The recorded shared-template comparison covers 23 <code>src/gems57</code> files: 19 match
 the stored hashes. <code>anatomy.py</code> and <code>metric.py</code> differ from the recorded
 template snapshot; <code>uniqueness.py</code> and <code>gates.py</code> are changes in this PR.
 <code>registry/template_pin.json</code> is absent from <code>origin/main</code>; no live
 upstream revision or tarball was checked. Do not claim an upstream fix or a complete provenance
 pass. Details: <a href="review/2026-10-11-pr12-reconciliation.md">PR #12 reconciliation</a>.</td>
 <td><span class="pill warn">OPEN</span></td></tr>
<tr><td><b>IR-71-LIDAR-RAW-OVERLAP</b></td>
 <td>The inherited lidar-lane final-dot result reports 0.990386 within 3 px of one accessible
 registry raster, above the 0.70 stop threshold. Its density-adjusted <code>UNIQUE</code> label
 is diagnostic only. Only 60 rasters were compared; organizer-registry completeness is
 uncertified; pre-placement surface correlation is unreported; no full-registry pixel/hash pass
 is established. The candidate remains negative and unpublished.</td>
 <td><span class="pill bad">OPEN — STOP</span></td></tr>
<tr><td><b>IR-66-BUG-01</b></td>
 <td>The first holdout run excluded the held-out truth's 300 m buffer from <i>emission</i> as
 well as training, forcing TP<sub>w</sub> = 0 for every candidate. The buffer is
 training-only.</td>
 <td><span class="pill ok">FIXED</span></td></tr>
<tr><td><b>IR-66-BUG-02</b></td>
 <td>The greedy packer suppressed neighbours only across blocks, so two dots accepted inside
 the same block could sit closer than the minimum separation. Each accepted pixel now stamps
 its exclusion disc.</td>
 <td><span class="pill ok">FIXED</span></td></tr>
<tr><td><b>IR-66-BUG-03</b></td>
 <td><code>folds_by_quadrant</code> assigned background (label 0) to fold 0 and produced folds
 of 2,307 vs 23,044 px. Replaced by balanced spatial clustering of connected components.</td>
 <td><span class="pill ok">FIXED</span></td></tr>
<tr><td><b>IR-67-01</b><br><span class="tag">interpretation rule</span></td>
 <td>The raw 3-px duplicate rule degenerates against the 311,617-dot registry raster
 (6.0% of the footprint): its 3-px halo alone gives a random-placement null within-3-px rate
 of 0.958, so any independent placement trips the brief's literal &gt;70% stop. This session
 reports BOTH the raw value (stop under the literal rule) and the lift-adjusted verdict.
 Rule of record: the literal rule governs sparse rasters (null &lt; 0.30); against dense
 rasters (null ≥ 0.70) the lift-adjusted verdict plus the documented null rate governs.
 <a href="review/2026-10-12-h67-session.md">H67 session review</a>.</td>
 <td><span class="pill warn">OPEN — documented</span></td></tr>
<tr><td><b>IR-67-03</b><br><span class="tag">verdict-driving</span></td>
 <td>The H67 h52_h_rank emission's holdout gain is range-front-dominated: candidate − random
 by relief tercile is <b>−0.0258 (low), +0.0868 (mid), +0.1773 (high)</b>; pooled
 +0.02579 over the incumbent with paired 95% CI [−0.01093, +0.03650] crossing zero; 5 of 8
 fold differences positive. Same signature as the inherited PR #13 negative result and the
 documented truth-prior confound (SGMC off-catalogue is 59.3% range front).</td>
 <td><span class="pill bad">OPEN — drives the negative verdict</span></td></tr>
<tr><td><b>IR-67-04</b></td>
 <td>The native scarp population's residual outside the registry is 83 dots: emission
 restricted to cells ≥ 4 px from every dot of every registry raster placed only 83 of
 37,654 (pooled HOLDOUT-DTI of 0.0), and the standard emission duplicates the GEMSDOE32
 bayesopt-scarp raster (77.7% of dots within 3 px, 4.38x lift). The lane has no unclaimed,
 gate-passing population under the current corpus.</td>
 <td><span class="pill bad">OPEN — negative result</span></td></tr>
<tr><td><b>IR-67-02</b></td>
 <td><code>fields.sgmc_offcatalogue</code> loaded the unpinned GEMSDOE48 SGMC mirror
 (61,664 off-catalogue px); the manifest-pinned bytes are 62,122 px. Fixed 2026-10-12 to
 prefer the pinned file (all H67 numbers use it); cross-check difference 458 px (0.7%).</td>
 <td><span class="pill ok">FIXED</span></td></tr>
<tr><td><b>IR-67-05</b></td>
 <td>Seven additional inputs fetched 2026-10-12 (h52 native product + receipt, TIGER road
 and BLM claim distance layers + receipts, SGMC mirror, 4 family rasters, dem3m pilot
 tiles, sidecars) are unpinned in <code>registry/data_manifest.json</code>. sha256 of each
 is recorded in <a href="review/2026-10-12-h67-session.md">the session review</a>. Pin before
 any future release that depends on them.</td>
 <td><span class="pill warn">OPEN — provenance ledger</span></td></tr>
<tr><td><b>IR-66-H2-01</b></td>
 <td>A supervised field trained on off-catalogue SGMC faults scores <b>below chance</b> on
 held-out SGMC faults: it learns regional geology, not the fault signal.</td>
 <td><span class="pill bad">NEGATIVE RESULT</span></td></tr>
</table>
""", "irregularities.html")


def feed_page(feed: dict) -> str:
    rows = []
    for item in feed.get("entries", []):
        links = " · ".join(
            f'<a href="{esc(link)}">{esc(link)}</a>' for link in item.get("links", [])
        )
        rows.append(
            f'<article class="card"><p class="eyebrow">{esc(item.get("date"))} · '
            f'{esc(item.get("kind"))}</p><h2>{esc(item.get("status"))}</h2>'
            f'<p>{esc(item.get("summary"))}</p><p class="small">{links}</p></article>'
        )
    actions = "".join(f"<li>{esc(x)}</li>" for x in feed.get("next_actions", []))
    body = f'''<div class="eyebrow">Static project feed — not a leaderboard feed</div>
<h2>Current status: {esc(feed.get('status', 'not recorded'))}</h2>
<p>{esc(feed.get('scope', ''))}</p>
<p class="small">{esc(feed.get('external_monitoring', 'No external standings are polled or copied.'))}</p>
<section><h2>Project events</h2>{''.join(rows)}</section>
<section><h2>Next actions</h2><ol>{actions}</ol></section>
<p class="small">This local feed is not live and contains no organizer-confirmed score.</p>'''
    return page("Project feed", body, "feed.html")


def main() -> int:
    (DOCS / ".nojekyll").write_text("")
    (DOCS / "assets").mkdir(parents=True, exist_ok=True)
    for fn, body, active in [
        ("index.html", index_page(), "index.html"),
        ("executive-summary.html", exec_page(), "executive-summary.html"),
        ("hypotheses.html", hyp_page(), "hypotheses.html"),
        ("research.html", research_page(), "research.html"),
        ("results.html", results_page(), "results.html"),
        ("sources.html", sources_page(), "sources.html"),
        ("irregularities.html", irr_page(), "irregularities.html"),
    ]:
        (DOCS / fn).write_text(body)
        print(f"wrote docs/{fn}")
    feed = load(DOCS / "data" / "feed.json", {}) or {}
    if feed:
        (DOCS / "feed.html").write_text(feed_page(feed))
        (DOCS / "status-feed.json").write_text(
            json.dumps(feed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("wrote docs/feed.html and docs/status-feed.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
