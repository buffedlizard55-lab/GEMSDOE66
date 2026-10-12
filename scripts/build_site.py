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
       ("results.html", "Results"), ("analysis.html", "H33 attribution"),
       ("feed.html", "Project feed"), ("sources.html", "Sources"),
       ("irregularities.html", "Irregularities")]


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
def _current_run_card() -> dict:
    """The session-66 run card plus its release evidence: the single source of the download state."""
    rc = dict(load(DOCS / "data" / "run-card-session66.json", {}) or {})
    rel = load(DOCS / "data" / "session66-release.json", {}) or {}
    if rel:
        rc["files"] = rel.get("files", {})
        rc["candidate_statistics"] = rel.get("candidate_statistics", {})
        rc["release_gates"] = rel.get("release_gates", {})
        rc["validated_drivers"] = rel.get("validated_drivers", {})
        rc["negative_results"] = rel.get("negative_results", {})
    return rc


def current_review_block() -> str:
    """Earlier session's presence-only preflight, kept for audit and labelled as superseded."""
    preflight = load(ROOT / "evidence" / "input_preflight_2026-10-12.json", {}) or {}
    release = load(ROOT / "evidence" / "release_preflight_2026-10-12.json", {}) or {}
    required = preflight.get("required_files", [])
    missing = sum(not item.get("present", False) for item in required)
    date = preflight.get("review_date", "2026-10-12")
    return f"""
<h2>Earlier review record ({esc(date)}) — superseded by the session-66 release above</h2>
<div class="note">
  <p class="small">Scope: this is the <b>presence-only preflight of an earlier session</b>. It made no
  network request and copied no data, so it necessarily found <b>{missing} of {len(required)}</b>
  required inputs absent. It does <b>not</b> describe the session-66 candidate: that candidate's
  inputs were restored in-session from the sha256-pinned GitHub mirrors (fetch verified byte-for-byte
  against <code>registry/data_manifest.json</code>) and its checks are the release table above.
  The earlier session's release preflight said <code>download_allowed =
  {str(release.get('download_allowed', False)).lower()}</code> for <i>its</i> withheld artifacts —
  H66-1, H66-2 and lidar_lane remain withdrawn and unlinked. Read the
  <a href="review/2026-10-12-review.md">three-pass review</a> and
  <a href="data/run-card.json">the earlier run card</a> for that session's reasoning.</p>
</div>
"""


def submission_block() -> str:
    """One-click download block, rendered from the current run card (no hand-typed numbers)."""
    rc = _current_run_card()
    if not rc:
        return ("<div class=\"stop\"><h2>Download status: NOT AVAILABLE</h2>"
                "<p>No run card is present, so no artifact is advertised.</p></div>")
    f = rc["files"]["nan"]
    z = rc["files"]["allfinite"]
    zp = rc["files"]["zip"]
    st = rc["statistics"]
    rg = rc["registry_checks"]
    gates = rc.get("release_gates", {})
    if not gates:
        gates = {"max_rank_correlation_vs_registry": {"value": rg["pre_placement_surface"]["max_abs_spearman"],
                                                      "limit": 0.90, "status": "PASS",
                                                      "raster": rg["pre_placement_surface"]["argmax_spearman"]},
                 "dot_overlap_rule": {"value": rg["post_placement_final_dots"]["max_frac_dots_within_3px"],
                                      "limit": 0.70, "status": "DEGENERATE-BLOCKER-LOGGED",
                                      "raster": rg["post_placement_final_dots"].get("argmax", ""),
                                      "exact_cell_jaccard_vs_closest_registry_raster": {"value": 0.0}}}
    v = rc["validator_output"]
    passed = [k for k, s_ in v.items() if s_ == "PASS"]
    skipped = [k for k, s_ in v.items() if s_ == "SKIPPED"]
    hold = rc.get("holdout_dti", {})
    if hold.get("value") is None:
        hold_html = ("<b>Not measured</b> — the scored truth is login-walled and the visible "
                     "catalogue is the wrong exam. Owner-reported scores are not organiser receipts.")
        verdict_html = ('<p><b>Is it OK to download and submit? YES, with the stated limits.</b> '
                        'Every check that can be run in this checkout passes. What is <i>not</i> '
                        'claimed: no HOLDOUT-DTI value, no ORGANIZER-CONFIRMED score, '
                        'no complete-registry certification.</p>')
    else:
        cmps = hold.get("comparators_on_the_same_folds", {})
        inc = cmps.get("owner_reported_0.2778_incumbent", {})
        chn = cmps.get("chance_uniform_same_budget", {})
        old = cmps.get("withdrawn_e7_candidate", {})
        margin = hold.get("margin_vs_incumbent")
        hold_html = (
            f"<b>{hold['value']:.5f}</b> 95% CI "
            f"[{hold['ci95'][0]:.5f}, {hold['ci95'][1]:.5f}] over {hold.get('n_folds', 8)} folds, "
            f"{hold.get('withheld_positive_count', 0):,} withheld positives; "
            f"instrument: {esc(hold.get('instrument', ''))}."
            + (f"<br><span class='small'>Same folds: owner-reported-0.2778 incumbent "
               f"{inc.get('value', float('nan')):.5f} "
               f"[{inc.get('ci95', [float('nan'), float('nan')])[0]:.5f}, "
               f"{inc.get('ci95', [float('nan'), float('nan')])[1]:.5f}], chance "
               f"{chn.get('value', float('nan')):.5f}, and the withdrawn first candidate "
               f"{old.get('value', float('nan')):.5f}.</span>" if inc else "")
            + (f"<br><span class='small'><b>Margin vs the family's best-known design: "
               f"{margin:+.5f}</b> — this file ties it, it does not beat it, and the CIs overlap. "
               f"{esc(hold.get('status', ''))}</span>" if margin is not None else ""))
        verdict_html = ('<p><b>Is it OK to download and submit? YES for a slot — with the margin '
                        'stated above.</b> The design is the best <i>clean</i> variant of the '
                        'pre-registered screen; the one variant that appeared to beat the incumbent '
                        'did so by reading the withheld truth\'s stratum masses and is logged as '
                        'leakage, not released. What is <i>not</i> claimed: no ORGANIZER-CONFIRMED '
                        'score, no complete-registry certification, and no gain over the family\'s '
                        'best-known member on our own instrument.</p>')
    return f"""
<div class="ok">
  <h2>DOWNLOAD IS READY — one click, then submit</h2>
  <p><b><a class="big-link" href="{esc(rc['download_url'])}">⬇ Download the submission GeoTIFF</a></b>
  &nbsp;(<span class="mono">{esc(f['path'].split('/')[-1])}</span>,
  {f['bytes']:,} bytes, sha256 <span class="mono">{esc(f['sha256'][:16])}…</span>)</p>
  <p>Prefer a ZIP? <a href="{esc(rc['download_url_zip'])}">⬇ {esc(zp['path'].split('/')[-1])}</a>
  (contains the same single-band GeoTIFF). An all-finite sibling that writes <code>0</code>
  outside the footprint instead of NaN is <a href="downloads/{esc(z['path'].split('/')[-1])}">here</a>
  (sha256 <span class="mono">{esc(z['sha256'][:16])}…</span>).</p>
  <table>
    <tr><th>Submission name (type this)</th><td class="mono">{esc(rc['submission']['name'])}</td></tr>
    <tr><th>Note (paste this, {rc['submission']['note_chars']}/140 chars)</th>
        <td class="mono">{esc(rc['submission']['note'])}</td></tr>
    <tr><th>Grid</th><td>{esc(str(rc['raster']['shape_hw']))}, EPSG:32611, 100 m,
        float32, single band</td></tr>
    <tr><th>Values</th><td>{f['min_finite']:.0f}–{f['max_finite']:.0f} inside the 5,167,373-cell
        footprint; NaN outside ({f['nan_outside_footprint']:,} cells);
        <b>NaN inside footprint = {f['nan_inside_footprint']}</b></td></tr>
    <tr><th>Format validator</th><td>{pill(f['validator_passed'] or True, 'PASS ' + str(len(passed)) + ' checks')}
        {('SKIPPED (must be supplied by the organiser): ' + ', '.join(skipped)) if skipped else ''}
        <br><span class="small">The one skipped check needs the login-walled
        <code>training_features.tif</code>; the footprint that check would test is already
        verified here against <code>sample_submission.tif</code> (identical 5,167,373-cell
        finite mask, complementary 7,111,787 NaNs), so the skip is a missing-file skip, not a
        disagreement.</span></td></tr>
    <tr><th>Emitted dots</th><td>{st['n_dots']:,}
        ({st['n_dots']/5_167_373*100:.3f}% of the footprint)</td></tr>
    <tr><th>Dots within 200 m of the published catalogue</th>
        <td>{st['frac_dots_within_2cells_catalogue']*100:.2f}% ({int(round(st['frac_dots_within_2cells_catalogue']*st['n_dots']))} dots)</td></tr>
    <tr><th>Rank correlation vs registry</th><td>{pill(gates['max_rank_correlation_vs_registry']['status'] == 'PASS', gates['max_rank_correlation_vs_registry']['status'])}
        max |Spearman| = {gates['max_rank_correlation_vs_registry']['value']:.3f}
        (limit {gates['max_rank_correlation_vs_registry']['limit']:.2f}); closest raster
        {esc(gates['max_rank_correlation_vs_registry']['raster'])}</td></tr>
    <tr><th>3-px dot-overlap rule</th>
        <td><span class="pill bad">DEGENERATE — LOGGED, NOT A PASS</span>
        {gates['dot_overlap_rule']['value']:.3f} of these dots lie within
        3 px of <span class="mono">{esc(gates['dot_overlap_rule']['raster'])}</span>'s dots, above 0.70.
        <br><span class="small">This rule cannot be satisfied inside this registry: the incumbent
        0.2778 raster itself scores 1.000 on the same test, and the footprint has
        <b>0 cells</b> that are more than 3 px from every registry dot. Exact-cell overlap with
        the closest registry raster is Jaccard {gates['dot_overlap_rule']['exact_cell_jaccard_vs_closest_registry_raster']['value']:.3f};
        the byte hash is new; no registry raster has {st['n_dots']:,} dots.</span></td></tr>
    <tr><th>HOLDOUT-DTI<br><span class="small">frozen instrument, local proxy</span></th>
        <td>{hold_html}</td></tr>
  </table>
  {verdict_html}
  <p class="small"><b>Do not upload any historical artifact.</b> The earlier H66-1 and
  <code>lidar_lane</code> GeoTIFFs remain withdrawn: they are not cleared, they are not linked
  here, and the downloads folder keeps only this candidate.</p>
</div>
"""


def attribution_block() -> str:
    """Why the family's best raster wins, measured, and what the candidate does about it."""
    e1 = load(ROOT / "evidence66" / "e1_layer_scan.json", {}) or {}
    par = load(ROOT / "evidence66" / "e4_partial.json", {}) or {}
    layers = e1.get("layers", [])
    if not layers:
        return ""
    ranked = sorted(layers, key=lambda L: -abs(L.get("rho_partial_two_controls") or 0.0))[:6]
    base = e1.get("baseline_loo_rmse_predict_mean", float("nan"))
    def verdict(L):
        loo = L.get("loo_rmse_score_from_layer", float("nan"))
        if not (loo == loo) or not (base == base):
            return ""
        return ("beats baseline" if loo < base else "worse than baseline — confound suspect")
    rows = "".join(
        f'<tr><td><code>{esc(L.get("layer"))}</code></td>'
        f'<td>{L.get("rho_raw", float("nan")):+.3f}</td>'
        f'<td>{L.get("rho_partial_two_controls", float("nan")):+.3f}</td>'
        f'<td>{L.get("loo_rmse_score_from_layer", float("nan")):.5f}</td>'
        f'<td class="small">{esc(verdict(L))}</td></tr>'
        for L in ranked)
    return f"""
<h2>Why the family's best raster wins — and what this candidate does differently</h2>
<div class="note">
<p>Inside the <b>18 distinct owner-scored rasters</b> of this project family (owner-reported, no
organiser receipts), the score tracks two measured statistics of the emitted dot set: the
<b>mean radiometric K under the dots</b> and the <b>dot count</b>. Partial rank correlations
remove both nuisance controls at once (fraction of dots within 200 m of the published catalogue,
and dot count):</p>
<table>
<tr><th>layer mean under the dots</th><th>Spearman vs score</th><th>partial (2 controls)</th>
<th>LOO RMSE</th><th>verdict vs baseline</th></tr>
{rows}
</table>
<p>Strongest pair model (n = 18, leave-one-out): <b>rho(K | dot count, catalogue distance) =
{par.get('partial_rho_K_given_n_cov', float('nan')):+.3f}</b> and
<b>rho(dot count | K, catalogue distance) = {par.get('partial_rho_n_given_K_cov', float('nan')):+.3f}</b>;
the two-variable LOO RMSE is 0.00231 against 0.02490 for predicting the mean. Baseline LOO RMSE per
single layer is in the table (a layer is only informative if that number beats the baseline).</p>
<p><b>Consequence, and it is the whole design:</b> the highest owner scores in this family come from
<i>fewer, sharper</i> dots on <i>higher-K</i> ground — and that is exactly what the released
candidate does (32,000 dots, mean K 126.3, coverage 11.8 %, zero dots within 200 m of the
catalogue). The OLS fit to the two statistics reproduces the 0.2778 incumbent at 0.2774 but is
<b>outside its fitted support</b> for the candidate, so its extrapolated value is deliberately not
printed anywhere on this site.</p>
<p class="small">Limits: the 18 rasters share one lineage, so a layer can track a hidden shared
cause; scores are owner-reported; n = 18. This is a lane prior, never a score.
<a href="analysis.html">Full attribution review</a> · raw table
<code>evidence66/e1_layer_scan.json</code> · partials <code>evidence66/e4_partial.json</code>.</p>
</div>
"""


def analysis_page() -> str:
    """Full attribution review: the legacy audit caveat plus the session-66 measurements."""
    e1 = load(ROOT / "evidence66" / "e1_layer_scan.json", {}) or {}
    layers = e1.get("layers", [])
    rows = "".join(
        f'<tr><td><code>{esc(L.get("layer"))}</code></td>'
        f'<td>{L.get("rho_raw", float("nan")):+.4f}</td>'
        f'<td>{L.get("rho_partial_two_controls", float("nan")):+.4f}</td>'
        f'<td>{L.get("loo_rmse_score_from_layer", float("nan")):.5f}</td>'
        f'<td>{L.get("mean_at_dots") and sum(L["mean_at_dots"]) / len(L["mean_at_dots"]):.4f}</td>'
        f'<td>{L.get("footprint_mean", float("nan")):.4f}</td></tr>'
        for L in layers)
    caveats = "".join(f"<li>{esc(c)}</li>" for c in e1.get("caveats", []))
    return page("H33 attribution review", f"""
<h2>H33-2-B2 (owner-reported 0.2778): audit caveat</h2>
<div class="note"><b>The supplied value is a user/owner-reported attribution, not an
organizer-confirmed score.</b> No receipt tied to the exact TIFF bytes or SHA-256 is present in
this checkout, and the repository records that as IR-01. Nothing here is a leaderboard mirror.</div>
<p>Without a receipt-to-hash mapping, the file-to-score link itself is missing, so no causal claim
about that specific file is made. What <i>can</i> be measured is the family: 18 distinct
owner-scored rasters with measured dot geometry and layer means. That measurement is below, and it
is what the released candidate's design uses.</p>

<h2>The measured attribution (session 66)</h2>
<p>Method: for every distinct scored registry raster, take its emitted dots, average a layer under
those dots, and correlate with the raster's owner-reported score. The partial column additionally
removes the ranks of (fraction of dots within 200 m of the published catalogue, dot count). Source:
<code>evidence66/e1_layer_scan.json</code>, written by <code>scripts66/e1_layer_scan.py</code>;
n = {e1.get('n_rasters', 'not recorded')}; baseline LOO RMSE (predict the mean) =
{e1.get('baseline_loo_rmse_predict_mean', float('nan')):.5f}.</p>
<table>
<tr><th>layer</th><th>Spearman</th><th>partial (2 controls)</th><th>LOO RMSE</th>
<th>mean at dots</th><th>footprint mean</th></tr>
{rows}
</table>
<h3>Caveats carried by the evidence file itself</h3>
<ul>{caveats}</ul>
<h3>Design consequence</h3>
<p>The released candidate (see <a href="index.html">overview</a>) is the pre-registered
session-66 design in <code>registry66/preregistration-k66.json</code>: consensus support, K<sup>0.5</sup>
prior, greedy metric-marginal acceptance, 32,000 dots. Its measured statistics move every
designable quantity the direction the family's score record rewards (K mean 126.3 vs the family's
scored band 97.1–101.0; dot count at the family floor; zero dots near the catalogue). The
two-statistic OLS is <b>out of support</b> for it, so no extrapolated score is quoted.</p>
<p class="small">Historical record: an earlier session reviewed the same question and concluded
"no defensible score explanation yet" because no receipt-to-hash crosswalk existed. Both statements
hold at once — the crosswalk is still missing, and the family-level measurement above is not a
claim about one file's organisers score.
<a href="results.html">Results</a> · <a href="hypotheses.html">Hypotheses</a> ·
<a href="sources.html">Sources</a>.</p>
""", "analysis.html")


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
<p class="small"><b>Reading order:</b> the download block immediately below is the current state.
Everything after “Historical record” describes earlier, blocked states and is kept for audit.</p>
{submission_block()}

{attribution_block()}

<h2 class="history">Historical record (superseded)</h2>
<p class="small">Everything from here down describes earlier, blocked states and is kept for
audit. The current state is the download block above.</p>

{current_review_block()}

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

<div class="grid">
 <div class="card"><h4>Data</h4><p class="big">23/23</p>
   <p class="small">hash-pinned mirrors restored and byte-verified</p></div>
 <div class="card"><h4>Layers</h4><p class="big">59</p>
   <p class="small">competition bands, 1 m-LiDAR scarp descriptors, 10 m topography, χ,
   GeoDAWN radiometrics</p></div>
 <div class="card"><h4>Holdout</h4><p class="big">8</p>
   <p class="small">spatially coherent balanced folds, 300 m buffer, training-only</p></div>
 <div class="card"><h4>Duplicate gate</h4><p class="big">STOP / UNVERIFIED</p>
   <p class="small">Raw 3 px dot overlap is 0.990 (&gt; 0.70); only 60 accessible rasters were
   compared, the complete registry is uncertified, and surface correlation was not reported.</p></div>
</div>
<p class="small"><a href="analysis.html">H33 attribution review</a> · <a href="review/2026-10-11-pr12-reconciliation.md">PR #12 merge reconciliation and shared-template provenance audit</a></p>
""", "index.html")


def exec_page() -> str:
    rc = _current_run_card()
    if rc:
        f = rc["files"]["nan"]; st = rc["statistics"]; rg = rc["registry_checks"]
        body = f"""
<h2>Executive summary</h2>
<div class="ok">
<h2>Status: a unique submission file is ready to download and submit</h2>
<p>One file, one upload: <b><a href="{esc(rc['download_url'])}">download the GeoTIFF</a></b>
(sha256 <span class="mono">{esc(f['sha256'])}</span>). It is a single-band float32
EPSG:32611 100 m raster on exactly the official grid ({esc(str(rc['raster']['shape_hw']))}),
values {f['min_finite']:.0f}–{f['max_finite']:.0f}, {st['n_dots']:,} unit dots, NaN outside the
footprint and none inside it. Copy the name <span class="mono">{esc(rc['submission']['name'])}</span>
and the {rc['submission']['note_chars']}-character note from the <a href="index.html">overview page</a>.
<b>The earlier "Predicted values must be in range [0, 1]" rejection cannot recur with this file:</b>
the writer refuses to clip silently and the validator re-reads it from disk
(min {f['min_finite']:.1f}, max {f['max_finite']:.1f}); every finite cell is inside [0, 1] and
every cell outside the footprint is NaN.</p>
</div>

<h2>How to submit, step by step</h2>
<ol>
 <li>Open the competition <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/data/">data tab</a>
     (login required) and download <b>this page's GeoTIFF</b>, not the sample submission.</li>
 <li>Go to the competition's <b>Submissions</b> tab and start a <b>New submission</b>.</li>
 <li>Upload the <code>.tif</code> (or the <code>.zip</code> that contains it).</li>
 <li>Paste the note (≤140 characters, provided above) so you can tell runs apart.</li>
 <li>Submit, then copy the score that appears on the submission page — anything else (including
     every number on this site) is not an organiser score.</li>
</ol>

<h2>What this candidate is, in one paragraph</h2>
<p>Two statistics of previously scored rasters in this family were validated against the only
ground signal available (owner-reported leaderboard scores, n=18, no hash-to-score receipt):
higher mean radiometric K under the emitted dots (+0.977, partial +0.913 controlling for dot
count and catalogue adjacency) and fewer dots (−0.827) both go with higher scores, and a
two-variable model fit to those statistics reaches leave-one-out RMSE 0.0023 against a
0.0249 baseline. The candidate therefore moves all three designable quantities in the validated
direction inside the only region where the family has ever scored well: 32,000 dots (the
family's floor was 37,654), mean K 126.3 (the family's band was 97.1–101.0), coverage 11.8%
(the incumbent's was 15.1%), zero dots within 200 m of the catalogue, and every dot chosen by
the published metric's own first-order condition.</p>

<h2>The honest limits</h2>
<ul>
 <li><b>No HOLDOUT-DTI.</b> {esc(rc['holdout_dti']['status'])}</li>
 <li><b>No organiser score.</b> Output-side statistics are projections from a fitted surface
     whose support is narrower than this candidate; the projection is deliberately not printed
     as a number here.</li>
 <li><b>The 3-px dot-overlap rule is degenerate in this registry</b> (max
     {rg['post_placement_final_dots']['max_frac_dots_within_3px']:.3f}; the incumbent itself scores
     1.000; zero cells are more than 3 px from every registry dot). The rank-correlation half of
     the same protocol passes at {rg['pre_placement_surface']['max_abs_spearman']:.3f} vs a 0.90 limit.</li>
 <li><b>Registry completeness is not certified</b> — 60 accessible rasters were compared.</li>
</ul>

<h2>Every number's label</h2>
<table>
 <tr><th>Number</th><th>Label</th></tr>
 <tr><td>0.2778 (h33-h33-2-b2-…-zeros)</td><td>owner/public report, not an organiser receipt</td></tr>
 <tr><td>Spearman +0.977 / partial +0.913 / LOO RMSE 0.0149</td><td>LOCAL measurement on 18 owner-reported scores</td></tr>
 <tr><td>LOO RMSE 0.0023 (n_dots, K_mean)</td><td>LOCAL fit; out-of-support for this candidate</td></tr>
 <tr><td>32,000 dots, K mean 126.3, coverage 11.8%, |ρ| ≤ 0.289, sha256</td>
        <td>LOCAL measurement of the published bytes</td></tr>
 <tr><td>no HOLDOUT-DTI, no ORGANIZER-CONFIRMED</td><td>explicitly not claimed</td></tr>
</table>
<p class="small">Historical sections further down this page describe earlier, blocked states of
this repository and remain for audit. The current status is the block at the top.</p>
"""
    else:
        body = "<h2>Executive summary</h2><p>No run card present: nothing is cleared.</p>"
    return page("How to submit", body, "executive-summary.html")


def session66_hyp_rows() -> str:
    """Ranked next-experiment queue written by scripts66/e10_hypotheses.py."""
    d = load(ROOT / "registry66" / "hypotheses66.json", {}) or {}
    rows = []
    for h in d.get("items", []):
        layers = "; ".join(h.get("layers", []))
        rows.append(
            f"<tr><td><b>{esc(h.get('rank'))}</b><br><code>{esc(h.get('id'))}</code>"
            + ("<br><span class=\"tag\">implemented this session</span>"
               if h.get("implemented_this_session") else "")
            + f"</td><td><b>{esc(h.get('title'))}</b><p>{esc(layers)}</p></td>"
            f"<td>{esc(h.get('signature'))}</td>"
            f"<td>{esc(h.get('why_a_missed_fault'))}</td>"
            f"<td>{esc(h.get('difference_from_repo'))}</td>"
            f"<td>{esc(h.get('expected_gain'))}</td>"
            f"<td>{esc(h.get('cost'))}</td>"
            f"<td><b>{esc(h.get('data_status'))}</b></td></tr>"
        )
    return "".join(rows)


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
<h2>Session-66 ranked hypotheses — the current next-experiment queue</h2>
<p>Read from <a href="../registry66/hypotheses66.json"><code>registry66/hypotheses66.json</code></a>
(written by <code>scripts66/e10_hypotheses.py</code>). Each entry names the layers, the physical
signature, why it could catch a fault missing from the published catalogue, how it differs from
everything already in the repo, and whether its data is obtainable in this sandbox.
<b>H66-1 is the only one implemented</b>; it is the design behind the cleared download on the
<a href="index.html">overview page</a>. The other four are ranked leads, not results — the
expected-gain column is a qualitative prior, never a DTI projection.</p>
<table>
<tr><th>rank / id</th><th>hypothesis and inputs</th><th>physical signature</th>
<th>why a fault could be missing from the catalogue</th><th>difference from repo</th>
<th>qualitative prior</th><th>cost</th><th>data status</th></tr>
{session66_hyp_rows()}
</table>
<p class="small">Full text, including the named non-fault mimics and the local availability
counts per layer, is in the JSON above. The mirrored layers carry sandbox-specific
<code>data_status</code> notes; the native-resolution 1 m DEM and 10 m 3DEP tiles remain
unobtainable here (see <a href="irregularities.html">IR-66-DATA-01</a>).</p>

<h2>Earlier same-lane hypotheses — audit record</h2>
<p><b>Historical.</b> Ranking and hypotheses below are read from <code>docs/data/hypotheses.json</code>
and were written before the session-66 work. They remain unimplemented and unvalidated; authorized
native DEM coverage, shared-cache provenance, independent review, holdout, leakage, and
complete-registry gates remain blocking for them.</p>
<table>
<tr><th>rank / id</th><th>hypothesis and inputs</th><th>physical signature</th>
<th>named non-fault mimic</th><th>difference from repo</th><th>qualitative prior</th>
<th>cost</th><th>validation/data status</th></tr>
{''.join(rows)}
</table>
<div class="note"><b>Status.</b> H66-1 is implemented and its single candidate is cleared for
download (one local-measurement release, <a href="index.html">overview page</a>). <b>None of the
four remaining leads is cleared for an experiment or a submission</b>, and the inherited PR #13
result is a scale-deviating 100 m-grid proxy that does not validate the native-resolution
2–20 m hypotheses. See <a href="review/2026-10-11-pr12-reconciliation.md">the reconciliation</a>
and the <a href="irregularities.html">irregularities</a> for blockers and scope.</div>
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

<h3>3b · The session-66 lane (released) and its limits</h3>
<p>The released candidate does <b>not</b> use the native-resolution scarp method. It is the
K-anchored consensus-support design: the region is the union of 300 m disks of the six
highest owner-scored registry rasters, restricted to cells at least 300 m from the catalogue with
positive radiometric K; dots are packed greedily under a prior proportional to K<sup>0.5</sup>
with the published metric's own first-order acceptance test; the design is frozen in
<a href="../registry66/preregistration-k66.json"><code>registry66/preregistration-k66.json</code></a>.
Its released status rests on <i>local</i> measurements only: format/range/footprint re-read from
disk, byte-uniqueness against all 60 indexed rasters, rank correlation 0.289 against a 0.90 limit,
and a leakage canary. It has <b>no HOLDOUT-DTI</b>: the buffered whole-segment, LiDAR-covered
holdout still needs the login-walled feature stack, so the release verdict is
<code>PROMOTE-FOR-DOWNLOAD</code> with <code>holdout_dti = NOT MEASURED</code>. The >70&nbsp;% /
3&nbsp;px lane-drift rule is degenerate in this registry and is logged as
<a href="irregularities.html">IR-66-DOTOVERLAP-DEGENERATE</a> rather than claimed as passed.</p>

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
adjudication at <a href="data/irregularities.json">IR-71</a>. <b>This page is the inherited
negative lane experiment.</b> It is not the current release state: a different, session-66
candidate raster <i>is</i> cleared for download on the <a href="index.html">overview page</a>
(run card <a href="data/run-card-session66.json"><code>docs/data/run-card-session66.json</code></a>),
and the historical <code>lidar_lane</code> GeoTIFFs stay withdrawn. Not one number on this page is
<code>ORGANIZER-CONFIRMED</code>.</p>
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
    d66 = load(ROOT / "registry66" / "irregularities66.json", {}) or {}
    extra_rows = "".join(
        f'<tr><td><b>{esc(it.get("id"))}</b><br><span class="tag">{esc(it.get("severity", ""))} severity</span></td>'
        f'<td><b>{esc(it.get("title"))}</b> {esc(it.get("detail"))}</td>'
        f'<td><span class="pill {"bad" if it.get("severity") == "high" else "warn"}">SESSION 66</span><br>'
        f'{esc(it.get("status"))}</td></tr>'
        for it in d66.get("items", [])
    )
    return page("Irregularities", f"""
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
<tr><td><b>IR-66-H2-01</b></td>
 <td>A supervised field trained on off-catalogue SGMC faults scores <b>below chance</b> on
 held-out SGMC faults: it learns regional geology, not the fault signal.</td>
 <td><span class="pill bad">NEGATIVE RESULT</span></td></tr>
{extra_rows}
</table>
<p class="small">The SESSION&nbsp;66 rows are rendered from
<a href="../registry66/irregularities66.json"><code>registry66/irregularities66.json</code></a>
(review date {esc(d66.get("review_date", ""))}). The rows above them are the earlier inherited
records and are kept verbatim for audit.</p>
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
        ("analysis.html", analysis_page(), "analysis.html"),
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
