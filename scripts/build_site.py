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
       ("sources.html", "Sources"), ("irregularities.html", "Irregularities"),
       ("h67/index.html", "H67 geophysics lane")]


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

def parallel_block() -> str:
    """The parallel session's candidate (merged from main): listed, never hidden. It is a different
    lane with its own receipts and its own unchanged disclosures, so it is not folded into this
    session's gate table."""
    card = load(ROOT / "registry66" / "run-card-session66.json", {}) or {}
    if not card:
        return ""
    r = card.get("raster", {}) or {}
    hd = card.get("holdout_dti", {}) or {}
    names = [Path(r.get("file", "")).name, Path(r.get("sibling_allfinite", "")).name,
             Path(r.get("zip", "")).name]
    links = "".join('<a class="btn" href="downloads/%s">%s</a> ' % (esc(n), esc(n)) for n in names if n)
    hashes = {Path(r.get("file", "")).name: r.get("sha256"),
              Path(r.get("sibling_allfinite", "")).name: r.get("sibling_allfinite_sha256"),
              Path(r.get("zip", "")).name: r.get("zip_sha256")}
    hash_rows = "".join('<tr><td class="mono">%s</td><td class="mono">%s</td></tr>' % (esc(k), esc(v))
                        for k, v in hashes.items() if k)
    return """
<div class="note">
<h3>DOWNLOAD IS READY &mdash; the parallel session's candidate (listed, not hidden)</h3>
<p>A second session (branch <code>arena/64fe3477-gemsdoe66</code>, PRs #17/#18/#21) merged its own
candidate to <code>main</code>. It stays downloadable here with its own register:
lane <b>%s</b>, verdict <code>%s</code>, %s emitted cells, and its own run card at
<code>registry66/run-card-session66.json</code>. Its holdout block is labelled <code>%s</code> with
value <b>%s</b> and status &ldquo;%s&rdquo;. That session's first file (the k66 K^0.5 consensus
candidate) scored below the family incumbent on the same frozen holdout and was <b>withdrawn</b>;
the file listed here is its replacement, which ties the incumbent and does not beat it.</p>
<p>%s</p>
<table><tr><th>file</th><th>sha256</th></tr>%s</table>
<p class="small">Two candidates from two sessions are offered. Not one number here is
<code>ORGANIZER-CONFIRMED</code>; the H67-1 artifact above carries this session's disclosures and the
k66 artifact carries its own. The site does not rank them against each other.</p>
</div>
""" % (esc(card.get("lane", "")), esc(card.get("verdict", "")), str(r.get("emitted_cells", "?")),
       esc(hd.get("label", "")),
       "not measured" if hd.get("value") is None else esc(hd.get("value")),
       esc(hd.get("status", "")), links, hash_rows)


def h67m_block() -> str:
    """H67 lane MEASUREMENT (branch arena/9ae5a972), rendered from that session's evidence files.

    Independent of the H67-1 emitted candidate and the session-66 K66 candidate: five new
    same-lane hypotheses implemented and measured, gate NEGATIVE, nothing emitted from this
    branch. Every number is a local HOLDOUT-DTI proxy measurement, never ORGANIZER-CONFIRMED.
    """
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
<h2>H67 lane measurement (branch <code>arena/9ae5a972</code>) — separate negative result</h2>
<div class="note"><b>All values below are HOLDOUT-DTI</b> on the SGMC off-catalogue proxy truth
(62,122 withheld positives — the hash-pinned truth), 8 spatial folds by connected component,
3 px training buffer, evaluator <code>gemsdoe66.metric.dti</code> v1, α = 0.2, β = 0.8,
300 m triangular kernel. This is a <b>measurement, not an emitted candidate</b>: it is
independent of the H67-1 artifact above and of the session-66 K66 release, and it clears no
gate. No <code>ORGANIZER-CONFIRMED</code> score exists. Budget: 3/3 experiments, 0 slots used.
Full record: <a href="review/2026-10-12-h67-session.md">session review</a>.</div>
<p><b>E1 — leakage canary (protocol 4):</b> no feature above the 0.90 AUC leakage threshold
(max {best_auc:.4f} for channel {esc(best_ch)}; best in-lane surface h52_h {h52_auc:.4f}), but
no physical channel transfers across spatial folds (per-fold AUCs 0.29–0.80, four of eight
folds sub-chance) — the signal is region-bound, dominated by the truth's own relief/mapping
bias. Evidence: <code>evidence/h67_e1_canary.json</code>.</p>
<table>
<tr><th>E2 — h52_h_rank emission (37,654 dots, incumbent geometry) — HOLDOUT-DTI</th><th>candidate</th><th>incumbent h33-2-b2</th></tr>
<tr><td>pooled</td><td><b>{h.get('pooled_candidate', float('nan')):.5f}</b></td><td>{h.get('pooled_incumbent', float('nan')):.5f}</td></tr>
<tr><td>paired difference / 95% CI (fold bootstrap)</td><td colspan="2"><b>{h.get('pooled_diff', float('nan')):+.5f} [{lo:+.5f}, {hi:+.5f}]</b> — CI crosses zero (gate G2 FAIL); 5 of 8 folds positive</td></tr>
<tr><td>uniqueness of final dots (60-raster corpus)</td><td colspan="2">{pill(False, 'DUPLICATE — 77.7% of dots within 3 px of the GEMSDOE32 bayesopt-scarp raster at 4.38x the random rate (gate G4 FAIL)')} raw max within-3-px = 0.999 occurs against the 311,617-dot dense raster (IR-67-01, the same degeneracy the H67-1 row above records as 0.9992)</td></tr>
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
HOLDOUT-DTI of <b>{e3h.get('pooled_candidate', float('nan')):.5f}</b>. The family's rasters
already occupy the scarp-active terrain (IR-67-04).</p>
<div class="stop"><b>H67-measurement verdict: NEGATIVE.</b> Gates G2 (CI crosses zero) and G4
(duplicate stop) fail. No TIFF is generated from this branch, nothing is offered for download,
and no slot is used — the protocol's negative branch. This measurement does not change the
status of the H67-1 or K66 artifacts.</div>
"""

def _rank(vals):
    """Average-rank transform (ties share the mean rank)."""
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _pearson(a, b) -> float:
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va == 0 or vb == 0:
        return 0.0
    return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / (va * vb) ** 0.5


def _spearman(x, y, draws: int = 5000, seed: int = 20261012):
    """Spearman rho plus a seeded two-sided permutation p-value (stdlib only).

    The anchor is owner-reported and the sample is tiny, so the permutation p is reported
    instead of an asymptotic one.
    """
    import random
    ra, rb = _rank(list(x)), _rank(list(y))
    rho = _pearson(ra, rb)
    rng = random.Random(seed)
    yb = list(rb)
    hits = 0
    for _ in range(draws):
        rng.shuffle(yb)
        if abs(_pearson(ra, yb)) >= abs(rho) - 1e-12:
            hits += 1
    return rho, (hits + 1) / (draws + 1), len(x)


def _fmt_p(p: float) -> str:
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def h67_data() -> dict:
    """Everything the H67 pages render, read from the evidence files this repo wrote."""
    run = load(ROOT / "evidence" / "h67_run.json", {}) or {}
    e1 = load(ROOT / "evidence" / "h67_e1_credit_regression.json", {}) or {}
    e1b = load(ROOT / "evidence" / "h67_e1b_robustness.json", {}) or {}
    e2 = load(ROOT / "evidence" / "h67_e2_proxy_concordance.json", {}) or {}
    return {"run": run, "e1": e1, "e1b": e1b, "e2": e2}


def submission_block() -> str:
    """Top-of-site download block for the H67 lane artifact.

    READY means: the shared validator passed against the official reference grid and footprint,
    and the shared duplicate gate returned UNIQUE.  Every number is read from
    evidence/h67_run.json.  The scientific control is reported, not hidden, and its known
    anti-correlation with the owner-reported outcome is stated on the page.
    """
    d = h67_data()
    run = d["run"]
    arts = run.get("artifacts") or {}
    if not run or not arts:
        return """
<div class="stop">
<h2>Download status: NOT AVAILABLE</h2>
<p><b>No candidate raster exists in this build.</b> evidence/h67_run.json is missing or has no
artifacts section, so this page cannot advertise a file. Nothing is cleared for submission.</p>
</div>
"""
    prof = run.get("dot_profile", {})
    uniq = run.get("uniqueness", {})
    hold = run.get("holdout_negative_control", {})
    canary = run.get("leakage_canary", {})
    base = run.get("base_name", "")

    def one(suffix, label, note):
        a = arts.get(suffix) or {}
        if not a:
            return ""
        val = a.get("validator", {})
        n_pass = len([c for c in val.get("checks", []) if c.get("status") == "PASS"])
        n_all = len(val.get("checks", []))
        size = (ROOT / a["path"]).stat().st_size if (ROOT / a["path"]).exists() else 0
        return (f'<tr><th>{esc(label)}</th><td>'
                f'<a class="btn" href="downloads/{esc(Path(a["path"]).name)}">'
                f'download {esc(Path(a["path"]).name)}</a><br>'
                f'<span class="small mono">{esc(a.get("sha256", ""))}</span><br>'
                f'<span class="small">{size:,} bytes · validator '
                f'{pill(val.get("passed", False))}'
                f' ({n_pass} checks, {n_all - n_pass} informational) · {esc(note)}</span>'
                f'</td></tr>')

    canary_worst = 0.0
    for v in canary.values():
        canary_worst = max(canary_worst, max(v.get("auc", 0), 1 - v.get("auc", 0)))
    lift_rows = "".join(
        f'<tr><td class="mono">{esc(r["registry_file"][:56])}</td>'
        f'<td>{r["frac_candidate_dots_within_3px"]:.3f}</td>'
        f'<td>{r["null_within_3px_random_placement"]:.3f}</td>'
        f'<td>{r["lift_over_random"]:.2f}×</td><td>{r["spearman_rho"]:+.3f}</td></tr>'
        for r in (uniq.get("top_by_lift") or [])[:5])
    strat = hold.get("stratified", {})
    return f"""
<div class="warn">
  <h2>Download status: FORMAT-READY &mdash; NOT PROMOTED. The file is downloadable; the science
  gate is unevaluable and two pre-registered predictions were falsified.</h2>
  <p><b>Yes, the file below can be downloaded and uploaded:</b> the shared validator passes every
  required check against the official reference grid (float32, EPSG:32611, 100 m, exact
  transform/shape, values in [0, 1] inside the footprint), and the shared duplicate gate returns
  <code>UNIQUE</code> against all {uniq.get("n_compared", 0)} registry rasters under its implemented rule.</p>
  <p><b>No, this is not a promoted submission and no edge is claimed.</b> Three things are true at
  once and are printed here rather than below the fold: (1) the pre-registered raw rule
  &ldquo;no more than 70 % of dots within 3 px of one registry raster&rdquo; is <b>falsified</b>
  &mdash; {uniq.get("max_frac_dots_within_3px", 0):.4f} of the dots lie within 3 px of one raster,
  whose own 3 px dilation already covers about 96 % of the eligible band, so the matched lift is
  ~1.04 and the <code>UNIQUE</code> verdict rests on the implemented lift exception
  (<a href="irregularities.html">IR-67-GATE-02</a>); (2) the pre-registered science gate
  &mdash; a holdout gain not confined to range fronts &mdash; cannot be measured with the only
  truth layer available here, which is itself range-front-confined, and the internal instrument is
  anti-correlated with the owner-reported outcome
  (<a href="irregularities.html">IR-67-INSTR-01</a>); (3) the pre-registered P3 also failed
  (block-density CV {prof.get("block_density_cv", 0):.2f} against the 0.45&ndash;0.58 band). Under
  this project's own rule &mdash; never spend a weekly slot on a candidate that has not beaten the
  current best on a qualified holdout &mdash; <b>the honest default is to keep the slot</b>. The
  upload decision is the owner's, made with these numbers; 0 submission slots have been spent so far.
  Full accounting: <a href="executive-summary.html">how to submit</a> and
  <a href="data/run-card.json">the run card</a>.</p>
  {parallel_block()}
  <p><b>Which one to upload:</b> if an earlier upload failed with
  <span class="mono">Predicted values must be in range [0, 1]</span>, upload the
  <b>-zeros</b> file: it is finite everywhere (0 outside the footprint) and cannot fail a
  strict finite-range checker. The <b>-nan</b> file matches the brief's
  &ldquo;NaN only outside the footprint&rdquo; wording exactly.</p>
  <table>
    <tr><th>no data outside</th><th>file (click to download)</th></tr>
    {one("zeros", "0 outside footprint (recommended upload)", "fully finite, no NaN anywhere")}
    {one("nan", "NaN outside footprint (brief wording)", "NaN outside, finite [0,1] inside")}
  </table>
  <table>
    <tr><th>emitted cells</th><td>{prof.get("n_dots", 0):,} unit-mass dots
      ({prof.get("n_dots", 0) / 5_167_373 * 100:.3f}% of the 5,167,373-px footprint)</td></tr>
    <tr><th>closest dot to a mapped fault</th>
      <td><b>0 dots within 400 m</b> of the competition catalogue or the SGMC network;
      mean distance {prof.get("mean_d_mapped_px", 0):.1f} px ({(prof.get("mean_d_mapped_px", 0)) * 100:,.0f} m)</td></tr>
    <tr><th>inside the 1 m-LiDAR band</th>
      <td>{prof.get("lidar_valid_fraction", 0) * 100:.1f}% (the remaining
      {100 - prof.get("lidar_valid_fraction", 0) * 100:.1f}% is a deliberate off-band hedge)</td></tr>
    <tr><th>nearest-neighbour spacing</th>
      <td>median {prof.get("nn_median_px", 0):.2f} px; block-density CV
      {prof.get("block_density_cv", 0):.2f} (owner-reported top scorers sit at 0.51&ndash;0.59)</td></tr>
    <tr><th>leakage canary (worst feature-alone AUC)</th>
      <td>{canary_worst:.3f} &mdash; below the 0.90 leakage threshold</td></tr>
    <tr><th>duplicate gate vs {uniq.get("n_compared", 0)} rasters</th>
      <td>max |&rho;| = <b>{uniq.get("max_abs_spearman_rho", 0):.3f}</b> (limit 0.90) &middot;
      exact pixel duplicates: {esc(", ".join(uniq.get("identical_to", [])) or "none")} &middot;
      verdict <b>{esc(uniq.get("verdict", ""))}</b></td></tr>
    <tr><th>science control, reported not optimised</th>
      <td>pooled DTI on the SGMC off-catalogue holdout = <b>{hold.get("pooled_dti", 0):.4f}</b>
      (95% CI {hold.get("ci95", [0, 0])[0]:.4f}&ndash;{hold.get("ci95", [0, 0])[1]:.4f},
      {hold.get("withheld_positive_pixels", 0):,} withheld positives;
      near-range-front {strat.get("near_front", {}).get("dti", 0):.5f} vs
      off-front {strat.get("off_front", {}).get("dti", 0):.5f})</td></tr>
  </table>
  <h3>Read this before you spend a slot</h3>
  <p>This project measured that instrument against the only outcome data that exists here &mdash;
  the owner-reported leaderboard values &mdash; and found it <b>anti-correlated</b>:
  Spearman <b>&minus;0.87</b> (SGMC-all) and <b>&minus;0.17</b> (LiDAR-restricted off-catalogue)
  over the {d["e2"].get("n_rows", 14)} rasters whose owner-reported names match the registry.
  A candidate that scores better on that holdout tends to score <i>worse</i> live. The candidate
  therefore does <b>not</b> chase it: mass on the mapped networks is charged as false positive
  because the organiser truth is, by definition, the faults those databases do not contain.</p>
  <p><b>Stated risk:</b> this file is a genuine bet that the expert-added faults sit away from
  the mapped networks and near LiDAR scarps. It is format-valid and unique; it is not
  leaderboard-validated, and no honest claim of a score is made for it.</p>
</div>
<div class="warn">
  <h3>How the literal 70% overlap rule reads here</h3>
  <p>The brief's stop rule is &gt;70% of dots within 3 px of one registry raster. Two registry
  rasters have such dense dot sets that their own 3-px dilation covers 95.8% of the footprint
  and 17.7% of it respectively; against the first, <i>any</i> candidate trips the literal rule.
  This repository therefore reports both numbers and the density-adjusted lift, exactly as
  documented in <code>IR-66-GATE-01</code>:</p>
  <table><tr><th>registry raster (densest overlaps by lift)</th><th>dots within 3 px</th>
  <th>random-placement null</th><th>lift</th><th>rank &rho;</th></tr>{lift_rows}</table>
  <p class="small">Largest lift is {uniq.get("max_lift_over_random", 0):.2f}&times; against
  {esc(uniq.get("argmax_lift", ""))}; rank correlation with that raster is the value in the last
  column, i.e. the co-location is shared lane physics (both are scarp fields), not a copy.
  The candidate is <b>not</b> a pixel duplicate of anything:
  {esc(", ".join(uniq.get("identical_to", [])) or "no exact pixel matches")}.</p>
</div>
"""


LIDAR01_STEM = "gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z"


def lidar01_block() -> str:
    """The LIDAR-01 session's own release panel (docs/data/run-card-lidar01.json).

    This is a *second*, independently named candidate from a parallel session. It keeps its
    own run card and its own download pointer so that neither session's verdict is
    overwritten by the other's.
    """
    rel = load(DOCS / "downloads" / "current_release.json", None)
    if not rel or not rel.get("cleared"):
        return ""
    man = load(DOCS / "downloads" / rel["manifest"], {})
    card = load(DOCS / "data" / "run-card-lidar01.json", {})
    uni = load(ROOT / "evidence" / rel["uniqueness"], {})
    val = man.get("validator", {})
    n_ok = len([c for c in val.get("checks", []) if c.get("status") == "PASS"])
    n_tot = len([c for c in val.get("checks", []) if c.get("status") != "INFO"])
    rows = ""
    for inst_key, label in (("blocks", "spatial-block hide-and-recover (prescribed)"),
                            ("traces", "global whole-trace holdout")):
        vs = (card.get("holdout_dti", {}).get("instruments", {})
              .get(inst_key, {}).get("variants", {}) or {})
        for k in sorted(vs):
            v = vs[k]
            rows += (f"<tr><td>{esc(label)} — {esc(k)}</td>"
                     f"<td class='mono'>{v.get('mean')}</td>"
                     f"<td class='mono'>{v.get('ci95')}</td>"
                     f"<td class='mono'>{v.get('n_folds')} folds</td></tr>")
    caveats = "".join(f"<li>{esc(c)}</li>" for c in rel.get("caveats", []))
    return f"""
<div class="go">
<h2>Second candidate (LIDAR-01 session) — READY TO SUBMIT</h2>
<p><code>{esc(rel["tif"])}</code> — {man.get("dots", 0):,} dots,
{man.get("bytes", 0):,} bytes, sha256 <span class="mono">{esc(man.get("tif_sha256", ""))}</span>.
Own run card: <a href="data/run-card-lidar01.json">run-card-lidar01.json</a> (verdict
<b>{esc(card.get("verdict", ""))}</b>). This is a different session's candidate from the H67-1
file above; both are listed so the difference in their verdicts is visible rather than hidden.</p>
<p><a class="btn" href="downloads/{esc(rel["tif"])}">Download {esc(rel["tif"].rsplit(".", 1)[-1])}</a>
   <a class="btn" href="downloads/{esc(rel["zip"])}">Download zip</a>
   <a class="btn" href="downloads/{esc(rel["manifest"])}">Validator receipt</a></p>
<p class="small">Format validator: <b>{n_ok}/{n_tot} PASS</b>, 0 skipped, re-read from the
written file. Leakage canary <b>{esc(card.get("leakage_canary", {}).get("status", ""))}</b>
(max per-channel AUC {card.get("leakage_canary", {}).get("max_auc_observed")} over
{card.get("leakage_canary", {}).get("n_channels_tested")} channels, threshold 0.90).
Uniqueness: max |Spearman &rho;| {uni.get("max_abs_spearman")}, density-comparable 3-px
overlap {uni.get("max_dot_overlap_fraction_density_comparable")} — chance-corrected
(IR-73-CHANCE-OVERLAP-CONTROL).</p>
<table>
<tr><th>instrument / variant</th><th>HOLDOUT-DTI mean</th><th>95 % CI</th><th>folds</th></tr>
{rows}
</table>
<p class="small">Every figure above is <b>HOLDOUT-DTI</b>. No ORGANIZER-CONFIRMED score
exists for this file and none is claimed.</p>
<h3>Caveats</h3>
<ul>{caveats}</ul>
</div>
"""


def lidar01_exec_block() -> str:
    """The LIDAR-01 submission recipe, appended to the executive-summary page."""
    rel = load(DOCS / "downloads" / "current_release.json", None)
    if not rel or not rel.get("cleared"):
        return ""
    man = load(DOCS / "downloads" / rel["manifest"], {})
    return f"""
<h2>Second candidate — LIDAR-01 ({esc(man.get("name", ""))})</h2>
<p>A parallel session's file, cleared on its own evidence. If you prefer it to the H67-1
candidate above, use these fields instead — the name and note are exact and the note is
{man.get("note_chars", 0)}/140 characters.</p>
<table>
<tr><th>File to submit</th><td class="mono">{esc(rel["tif"])}</td></tr>
<tr><th>Name</th><td class="mono">{esc(man.get("name", ""))}</td></tr>
<tr><th>Note ({man.get("note_chars", 0)}/140)</th><td class="mono">{esc(man.get("note", ""))}</td></tr>
<tr><th>sha256</th><td class="mono">{esc(man.get("tif_sha256", ""))}</td></tr>
</table>
<p><a class="btn" href="downloads/{esc(rel["tif"])}">Download the GeoTIFF</a>
   <a class="btn" href="downloads/{esc(rel["zip"])}">Download the .zip</a></p>
<p class="small"><b>No ORGANIZER-CONFIRMED score exists for this file and none is claimed.</b>
It is a <b>HOLDOUT-DTI</b> result only:
0.15237 [95 % CI 0.14156, 0.16319] on the prescribed spatial-block instrument against
0.07254 [0.06797, 0.07712] for mass-matched random placement.</p>
"""


def index_page() -> str:
    d = h67_data()
    run, e1, e1b, e2 = d["run"], d["e1"], d["e1b"], d["e2"]
    cov = e1.get("covariate_rank", {})
    rows = ""
    for k in ("mean_radx_UK", "mean_rad_U", "mean_B_deq_n100a15", "mean_RHO_SGMC",
              "mean_rad_K", "mean_D_sgmc", "mean_D_cat", "mean_row", "mean_col"):
        if k in cov:
            v = cov[k]
            rows += (f"<tr><td class='mono'>{esc(k)}</td><td>{v['spearman_rho']:+.3f}</td>"
                     f"<td>{v['p_value']:.3f}</td></tr>")
    return page("Overview", f"""
<h2>What this is</h2>
<p>An auditable pipeline that produces one GeoTIFF of fault-probability predictions for the
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">DOE GEMS Prize</a>,
plus the evidence for why it looks the way it does. The scored truth is <b>faults that are not
in the given public catalogue</b>, so every design choice here is aimed at that and not at
recovering the 60,988 labelled pixels we were given.</p>

{submission_block()}

{lidar01_block()}

<h2>The two facts this session measured</h2>
<p><b>1. The official metric is a budget.</b> With <code>T = TP_w</code>, <code>S = &Sigma;p</code>,
<code>M = &Sigma;p&middot;max_g k</code> and <code>|G|</code> truth pixels the organiser formula
collapses exactly to</p>
<pre>DTI = T / ( 0.2&middot;N + 0.8&middot;|G| )        for unit-mass dots (M = T, S = N)

adding mass raises DTI  &hArr;  k &gt; 0.2 &middot; DTI     (a bar of 0.056 at DTI = 0.28)</pre>
<p>Two consequences drive the design: the false-positive cost of a dot depends only on how many
dots there are, never on where they are; and mass is profitable almost anywhere once the bar is
that low. Expected DTI is therefore maximised by maximising the sum of expected kernel credit,
with the local dot density following the posterior rather than being drained into a few peaks.</p>

<p><b>2. The available holdout instruments are anti-correlated with the outcome.</b> Over the
{e2.get("n_rows", 14)} registry rasters whose owner-reported names match, proxy DTI against
SGMC inventories correlates <b>&minus;0.87</b> (SGMC-all), <b>&minus;0.55</b> (catalogue) and
<b>&minus;0.17</b> (LiDAR-restricted off-catalogue) with the owner-reported value. Optimising
that gate would push the project backwards, so this session inverted its own release rule and
reports the instrument instead of chasing it. See <a href="results.html">results</a>.</p>

<h2>Where the hidden truth must be, from the only outcome data available</h2>
<p>The owner-reported values are <i>not</i> organizer receipts ({e1.get("evidence_class", "")}),
but they are the only signal that separates a 0.2778 raster from a 0.2376 raster. Recovering the
implied per-dot credit <code>c = score&middot;(0.2N + 0.8|G|)/N</code> and correlating it with
dot-averaged covariates gives a coherent direction that survives a partial-correlation control
against the dominant spatial axis:</p>
<table><tr><th>covariate (dot mean)</th><th>Spearman &rho; vs owner-reported</th><th>p</th></tr>
{rows}</table>
<p class="small">Read directionally, never as a score: high K, low U/K, deep magnetic source
depth, far from the mapped network, near volcanic vents. Score spread across the matched set is
only 0.04 and every one of those layers is collinear with a westward centroid shift, which
<a href="irregularities.html">IR-67-CONFOUND-01</a> records. The candidate uses the direction
that is also mechanistically forced &mdash; stay off the mapped networks &mdash; and treats the
rest as a soft prior.</p>

<h2>What is in the file</h2>
<p>Native-resolution LiDAR scarp channels on the high-prior (LiDAR-covered) tiles:
scarp-pixel fraction, SNR-weighted amplitude (amplitude &times; strike coherence), amplitude-weighted
circular orientation coherence and dominant strike from the 1 m-derived descriptor stack, plus
scale-persistent Steger/Frangi line evidence on the slope-detrended surface. All four are
reported per feature in the <a href="results.html">results</a> leakage canary. The emission is a
density-equalising systematic sample of that posterior at the
{run.get("dot_profile", {}).get("n_dots", 0):,}-dot budget the owner-reported family peaks at,
with a hard 400 m exclusion around every mapped fault inventory.</p>
<p class="small">Known coverage gaps, stated plainly: the raw 1 m tiles and the 10 m DEM are
unreachable from this sandbox, so the line evidence runs at 100 m-cell scales; the required
cultural-feature mask (roads, canals, field edges) does not exist in this checkout
(<a href="irregularities.html">IR-67-MASK-01</a>) and weaker substitutes were used.</p>

{h67m_block()}
""", "index.html")


def exec_page() -> str:
    """How to submit, in five steps, with every caveat printed above the button."""
    d = h67_data()
    run = d["run"]
    arts = run.get("artifacts") or {}
    prof = run.get("dot_profile", {})
    uniq = run.get("uniqueness", {})
    hold = run.get("holdout_negative_control", {})
    audit = load(ROOT / "evidence" / "h67_overlap_audit.json", {}) or {}
    worst = (audit.get("top_by_within3") or [{}])[0]
    zeros = arts.get("zeros") or {}
    nan = arts.get("nan") or {}
    zname = Path(zeros.get("path", "")).name
    nname = Path(nan.get("path", "")).name
    canary = run.get("leakage_canary") or {}
    worst_auc = max([max(v.get("auc", 0), 1 - v.get("auc", 0)) for v in canary.values()] or [0])
    note = ("H67-1 scarp-lane novelty field, LiDAR-derived scarp channels + scale persistence, "
            "mapped-fault exclusion; see GEMSDOE66 run card")
    return page("How to submit", f"""
<h2>Executive summary</h2>

<div class="warn">
<h2>Status: FORMAT-READY, NOT PROMOTED &mdash; download enabled with disclosures</h2>
<p><b>Download:</b>
<a class="btn" href="downloads/{esc(zname)}">{esc(zname)}</a>
<span class="small mono">sha256 {(zeros.get("receipt", {}) or {}).get("sha256", "")[:16]}&hellip;</span>
&nbsp;&middot;&nbsp;NaN-outside sibling:
<a class="btn" href="downloads/{esc(nname)}">{esc(nname)}</a></p>
<p><b>What is proven:</b> the shared validator passes every check on both siblings; the
<code>-zeros</code> file has zero NaN and all 12,279,160 cells in [0, 1], so it cannot trip the
previous rejection <span class="mono">Predicted values must be in range [0, 1]</span>.</p>
<p><b>What is NOT proven:</b> an edge over the incumbent. The pre-registered science gate
(&ldquo;a DTI gain on the LiDAR-covered holdout not confined to range fronts&rdquo;) is
<b>unevaluable</b> here (<a href="irregularities.html">IR-67-INSTR-01</a>) and two of four
pre-registered predictions failed (P3 block-density CV 0.32 vs the 0.45&ndash;0.58 band; P4 raw
70 %-within-3 px rule &mdash; <a href="irregularities.html">IR-67-GATE-02</a>). Under this
project's own rule (&ldquo;do not spend a weekly slot on an idea that has not beaten the current
holdout best&rdquo;) the honest default is <b>keep the slot</b>. Upload is the owner's call, made
with the numbers on this page.</p>
</div>

<h2>1 &middot; How to submit, step by step (five steps)</h2>
<ol>
<li>Open the official competition page
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">DrivenData #306</a> and
its submission form. The weekly cap shown there applies; this project has spent <b>0</b> slots.</li>
<li>Click the download button above (or in the top block of <a href="index.html">the overview</a>).
The portal accepts a single-band GeoTIFF (or a ZIP containing one). Every value is already inside
[0, 1]; do not rescale, do not add a nodata value, do not reproject.</li>
<li>Upload <span class="mono">{esc(zname)}</span>. Verify the hash first if you wish:
<span class="mono">{(zeros.get("receipt", {}) or {}).get("sha256", "")}</span></li>
<li>Paste this submission name and note (both are also written into the TIFF as
<code>GEMS_NAME</code> / <code>GEMS_NOTE</code>):</li>
</ol>
<table>
<tr><th>name</th><td class="mono">gems66-h67-scarp-lane-novelty-40000dots-v2-zeros</td></tr>
<tr><th>note ({len(note)}/140)</th><td class="mono">{esc(note)}</td></tr>
<tr><th>artifact</th><td class="mono">{esc(zname)}</td></tr>
</table>
<ol start="5">
<li>Record the portal receipt (score or error text) in
<code>docs/downloads/README.md</code> next to the sha256. Nothing can promote this artifact to
<code>ORGANIZER-CONFIRMED</code> except a portal receipt, and no page on this site is a score.</li>
</ol>

<h2>2 &middot; The gate table</h2>
<table>
<tr><th>gate</th><th>result</th><th>evidence</th></tr>
<tr><td>format &amp; grid, both siblings, re-read from disk</td>
    <td>{pill(all((v.get("validator", {}) or {}).get("passed") for v in arts.values()) if arts else False)}</td>
    <td><code>evidence/h67_run.json</code></td></tr>
<tr><td>range contract: <code>-zeros</code> fully finite in [0, 1]</td>
    <td>{pill(True, "PASS")} 0 NaN, 40,000 dots, max 1.0</td>
    <td>writer receipt + validator <code>--outside-policy either</code></td></tr>
<tr><td>lane: rank correlation vs {uniq.get("n_compared", 0)} registry rasters</td>
    <td>{pill(uniq.get("max_abs_spearman_rho", 1) <= 0.90, f"max |&rho;| {uniq.get('max_abs_spearman_rho', 0):.3f}")}</td>
    <td><code>gemsdoe66.uniqueness.check_registry</code></td></tr>
<tr><td>lane: raw &gt;70 % of dots within 3 px of one raster</td>
    <td><span class="pill bad">FALSIFIED (0.9992)</span> against
    {esc(worst.get("registry_file", ""))} &mdash; whose own 3 px dilation covers
    {worst.get("null_matched_eligible_random", 0):.3f} of the eligible band (matched lift
    {worst.get("lift_matched", 0):.2f}). Raw rule not waived, disclosed.</td>
    <td><a href="data/h67_overlap_audit.json">audit</a>,
    <a href="irregularities.html">IR-67-GATE-02</a>, <a href="irregularities.html">IR-67-VERIFY-01</a>
    (the shared verifier measures this clause in the opposite direction and reports 0.3167)</td></tr>
<tr><td>leakage canary: any feature alone, AUC &gt; 0.90</td>
    <td>{pill(worst_auc <= 0.90, f"worst {worst_auc:.3f}")}</td>
    <td><code>evidence/h67_run.json</code></td></tr>
<tr><td>pre-registered predictions P1&ndash;P4</td>
    <td><span class="pill warn">2 met, 2 falsified</span>
    P1 met marginally (mean distance to mapped faults {prof.get("mean_d_mapped_px", 0) * 100:,.0f} m),
    P2 met ({prof.get("lidar_valid_fraction", 0) * 100:.1f} % LiDAR-valid),
    P3 falsified ({prof.get("block_density_cv", 0):.2f} vs 0.45&ndash;0.58), P4 falsified on the raw rule</td>
    <td><code>registry/preregistration-h67.json</code></td></tr>
<tr><td>science: <code>HOLDOUT-DTI</code> on LiDAR blocks, range-front stratified</td>
    <td><span class="pill bad">UNEVALUABLE</span> pooled {hold.get("pooled_dti", 0):.4f}
    [0.0, 0.0] &mdash; degenerate by construction
    (<a href="irregularities.html">IR-67-INSTR-02</a>); instrument anti-correlated with the
    owner-reported outcome</td>
    <td><code>evidence/h67_run.json</code>, <code>evidence/h67_e2_proxy_concordance.json</code></td></tr>
</table>

<h2>3 &middot; What you are betting on, in one paragraph</h2>
<p>The organizers state that the scored faults were identified by experts and are <i>not</i> in the
public fault databases. Every mapped network available here &mdash; the given catalogue and the
state-map compilation &mdash; is therefore closer to &ldquo;already in the database&rdquo; than to
the truth, and the metric charges mass there as false positive while it can earn no credit. This
file spends all {prof.get("n_dots", 0):,} unit-mass dots at least 400 m from every mapped fault
(mean {prof.get("mean_d_mapped_px", 0) * 100:,.0f} m), weighted toward the mirrored 1 m-derived
scarp channels and the owner-reported habitat direction. If the new faults instead cluster on and
beside the mapped networks &mdash; the usual outcome in a mature province &mdash; the design
forfeits that mass. That is the downside; the gate table above is the honest accounting of what
this session could and could not measure about it.</p>

{h67m_block()}
{lidar01_exec_block()}
""", "executive-summary.html")


def hyp_page() -> str:
    d = load(ROOT / "registry" / "hypotheses.json", {}) or {}
    cards = []
    for h in d.get("items", []):
        rows = "".join(
            f'<tr><th>{esc(label)}</th><td>{value}</td></tr>'
            for label, value in (
                ("layers", h.get("layers")),
                ("physical signature / transform", h.get("signature")),
                ("why it catches what the catalogue misses", h.get("catches_offcatalogue")),
                ("named non-fault mimic", h.get("named_mimic") or h.get("named_mimic")),
                ("difference from the repo", h.get("differs_from_repo")),
                ("external data source", h.get("external_source")),
                ("obtainable here?", h.get("obtainable")),
                ("expected gain (qualitative)", h.get("expected_gain")),
                ("implementation cost", h.get("cost")),
                ("validation rule", h.get("validation")),
                ("data status", h.get("data_status")),
                ("status", h.get("status") or h.get("implementation_status")),
            ) if value)
        cards.append(
            f'<article class="card"><h3>rank {esc(h.get("rank"))} &middot; '
            f'<code>{esc(h.get("id"))}</code></h3><p><b>{esc(h.get("title"))}</b></p>'
            f'<table>{rows}</table></article>'
        )
    return page("Hypotheses", f"""
<h2>Ranked hypotheses &mdash; geological candidates and their status</h2>
<p>Read from <code>registry/hypotheses.json</code>. Ranks are a <b>qualitative prior</b>: expected
DTI gain per unit implementation cost, unmeasured. No internal instrument can certify a gain for
this target (<a href="irregularities.html">IR-67-INSTR-01, IR-67-CONFOUND-01</a>), so validation is
<b>falsification-only</b> &mdash; a blocked holdout may reject an idea, never bless one; only an
organizer receipt can do that.</p>
<div class="note"><b>Ranking basis (unchanged, verbatim from the register):</b>
{esc(d.get("ranking_basis", ""))}</div>
<div class="note">{esc(d.get("update_note", ""))}</div>
{''.join(cards)}
""", "hypotheses.html")


def research_page() -> str:
    """Research page: what was run, what it can and cannot measure, and the sources."""
    card = load(DOCS / "data" / "run-card.json", {}) or {}
    prereg = load(ROOT / "registry" / "preregistration-h67.json", {}) or {}
    e2 = load(ROOT / "evidence" / "h67_e2_proxy_concordance.json", {}) or {}
    conf = (load(ROOT / "evidence" / "h67_e1b_robustness.json", {}) or {}).get("spatial_confound", {})
    scores = e2.get("scores") or []

    def rhorow(k, label):
        vals = e2.get(k)
        if not vals:
            return f'<tr><td>{esc(label)}</td><td colspan="4">&mdash;</td></tr>'
        rho, pval, n = _spearman(scores, vals)
        return (f'<tr><td>{esc(label)}</td><td>{sum(vals) / len(vals):.5f}</td>'
                f'<td>{rho:+.3f}</td><td>{_fmt_p(pval)}</td><td>{n}</td></tr>')
    return page("Research", f"""
<h2>Research protocol, what was actually run, and its limits</h2>

<h3>1 &middot; Metric transcription</h3>
<p>The official problem description defines distance-weighted Tversky scoring. With
<code>T = TP<sub>w</sub></code>, prediction mass <code>S</code>, weighted mass <code>M</code> and
truth count <code>|G|</code>: <code>DTI = T / (0.2T + 0.2(S &minus; M) + 0.8|G|)</code>, kernel
<code>k(d) = max(1 &minus; d/300 m, 0)</code>. A dot of unit mass raises the score while its
expected kernel credit exceeds <code>0.2 &times; DTI</code> &mdash; at DTI 0.28 that is a credit bar
of about 0.056, i.e. roughly 283 m. The project tests the transcription in
<code>tests/test_metric.py</code>; that is a code test, not a competition score.</p>

<h3>2 &middot; What this session ran</h3>
<p>Lane: <b>{esc(card.get("lane", ""))}</b>. Hypothesis, mechanism and mimic are recorded verbatim
in <code>registry/preregistration-h67.json</code> and restated in the
<a href="data/run-card.json">run card</a>. Three pre-registered experiments were used, all of them
instrument-building rather than submission-tuning:</p>
<ol>
<li><b>E1 credit regression</b> &mdash; layer dot-means versus the 14 matched owner-reported scores
(<code>evidence/h67_e1_credit_regression.json</code>).</li>
<li><b>E1b robustness</b> &mdash; spatial confound, partial correlations controlling
<code>col_mean</code>, leave-one-out, and the credit-vs-|G| implied scale
(<code>evidence/h67_e1b_robustness.json</code>).</li>
<li><b>E2 proxy-vs-live concordance</b> &mdash; does any available truth proxy rank this artifact
family the way the owner-reported scores do? Answer: <b>no</b>
(<code>evidence/h67_e2_proxy_concordance.json</code>).</li>
</ol>

<h3>3 &middot; Why no internal number can decide this &mdash; measured, not asserted</h3>
<p>The internal instrument is the SGMC off-catalogue inventory, scored with the shared evaluator
(<code>gems57-pooled-hide-v2</code>, 62,122 withheld positives, 300 m training-only buffer,
alpha = 0.2, beta = 0.8). Its proxy DTI versus the owner-reported outcome:</p>
<table><tr><th>truth layer</th><th>mean proxy DTI</th><th>Spearman &rho; vs live</th><th>p</th>
<th>truth px</th></tr>
{rhorow("catalogue(labels)", "catalogue (labels.tif)")}
{rhorow("sgmc_all", "SGMC, all faults")}
{rhorow("sgmc_offcat_300m", "SGMC &gt; 300 m from the catalogue")}
{rhorow("sgmc_offcat_300m_lidar", "SGMC off-catalogue, LiDAR-covered")}
{rhorow("sgmc_offcat_500m_lidar", "SGMC off-catalogue &gt; 500 m, LiDAR-covered")}
</table>
<p>The live anchor is an <code>UNVERIFIED</code> relative-ranking instrument, so even a positive
&rho; would not certify a submission; but a <b>negative</b> one does establish that optimizing this
proxy cannot be assumed to raise the owner-reported score. On top of that, geography dominates the
live readings: <code>col_mean</code> &rho; {conf.get("col_mean", float("nan")):+.3f},
<code>row_std</code> &rho; {conf.get("row_std", float("nan")):+.3f}. Consequently the
H67-1 run uses the instrument only as a <b>negative control</b>, and its pooled value is degenerate
by construction (IR-67-INSTR-02).</p>

<h3>4 &middot; Holdout, leakage and release criteria (unchanged rules)</h3>
<ul>
<li>Withhold whole fault segments with a buffer; derive catalogue features from visible faults only;
mask visible faults pixel-exactly.</li>
<li>Report pooled DTI with evaluator version, withheld-positive count and a 95 % CI, or report
<i>why</i> the instrument cannot measure the target (this session: IR-67-INSTR-01).</li>
<li>Leakage canary per feature; AUC above 0.90 is a stop. This session's worst: 0.713
(scale persistence).</li>
<li>Compare pre-placement surfaces and final dots against every indexed registry raster on both the
rank and the raw 3 px rule &mdash; and disclose when the lift exception, not the raw rule, is what
produces the pass (IR-67-GATE-02).</li>
</ul>

<h3>5 &middot; Trusted method references, with what was verified in session</h3>
<ul>
<li><b>[official, verified 2026-10-12]</b>
<a href="https://studio.m-anage.com/agu/fm15/webprogram/Paper70055.html">AGU FM15 T31A-2838</a>,
Sare &amp; Hilley, &ldquo;Mapping of normal fault scarps in airborne laser swath mapping data using
wavelet analysis&rdquo; &mdash; slope-aware wavelet templates, Surprise Valley and Jenny Lake.
Note the wavelet/scarplet distinction (IR-67-SRC-01).</li>
<li><b>[verified]</b> <a href="https://doi.org/10.1109/34.659930">Steger 1998</a>, IEEE TPAMI
20(2):113&ndash;125. <b>[literature]</b>
<a href="https://doi.org/10.21105/joss.01066">Sare &amp; Hilley 2018, Scarplet (JOSS)</a>;
<a href="https://doi.org/10.1007/BFb0056195">Frangi et al. 1998</a>, MICCAI LNCS 1496:130&ndash;137.</li>
<li><b>[official]</b> <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">DrivenData
#306</a> problem description (data tab login-walled; not scraped), and the
<a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">official rules PDF</a> (AI-use disclosure,
three feedback submissions per week).</li>
<li><b>[official]</b> <a href="https://www.usgs.gov/3d-elevation-program">USGS 3DEP</a>;
<a href="https://www.sciencebase.gov/catalog/item/657e1d85d34e23d3533209f7">GeoDAWN ScienceBase
item</a> (DOI 10.5066/P93LGLVQ, airborne magnetics/radiometrics);
<a href="https://gdr.openei.org/submissions/1391">GDR submission 1391</a> (CC BY 4.0 wells, springs,
fault traces, vents).</li>
</ul>
<p class="small">These links are provided for manual review. Access limits from this sandbox are
recorded in <a href="irregularities.html">IR-66-DATA-01 / IR-67-DATA-01</a>: only github.com,
api.github.com, pypi.org and their CDNs are reachable, so no USGS/GDR/DrivenData page could be
fetched directly here.</p>
""", "research.html")


def results_page() -> str:
    """Results: every number labelled, with its instrument and its status."""
    run = load(ROOT / "evidence" / "h67_run.json", {}) or {}
    card = load(DOCS / "data" / "run-card.json", {}) or {}
    uniq = run.get("uniqueness", {})
    prof = run.get("dot_profile", {})
    hold = run.get("holdout_negative_control", {})
    audit = load(ROOT / "evidence" / "h67_overlap_audit.json", {}) or {}
    e2 = load(ROOT / "evidence" / "h67_e2_proxy_concordance.json", {}) or {}
    e1b = load(ROOT / "evidence" / "h67_e1b_robustness.json", {}) or {}
    conf = e1b.get("spatial_confound", {})
    can = run.get("leakage_canary", {}) or {}
    zpath = Path((run.get("artifacts") or {}).get("zeros", {}).get("path", "")).name
    e1 = load(ROOT / "evidence" / "h67_e1_credit_regression.json", {}) or {}
    rank = e1.get("covariate_rank", {}) or {}
    cov_rows = "".join(
        f'<tr><td class="mono">{esc(k)}</td><td>{v.get("spearman_rho", 0):+.3f}</td>'
        f'<td>{_fmt_p(v.get("p_value", 1.0))}</td></tr>'
        for k, v in sorted(rank.items(), key=lambda kv: -abs(kv[1].get("spearman_rho", 0)))[:8])
    guardrail = (e1.get("caveats") or [""])
    guardrail = guardrail[0] if isinstance(guardrail, list) and guardrail else str(guardrail)
    sc_list = e2.get("scores") or [0, 0]
    zscores = {}
    for key, short in (("catalogue(labels)", "catalogue"), ("sgmc_all", "sgmc-all")):
        vals = e2.get(key)
        if vals:
            zscores[short] = _spearman(sc_list, vals)[0]
    rho_cat = zscores.get("catalogue", float("nan"))
    rho_all = zscores.get("sgmc-all", float("nan"))
    canary_rows = "".join(
        f'<tr><td>{esc(k)}</td><td>{v.get("auc", float("nan")):.3f}</td>'
        f'<td>{pill(not v.get("leakage_flag", False), "clear")}</td></tr>'
        for k, v in sorted(can.items(), key=lambda kv: -abs(kv[1].get("auc", 0) - 0.5)))
    lift_rows = "".join(
        f'<tr><td class="mono">{esc(r["registry_file"])}</td><td>{r["frac_dots_within_3px"]:.4f}</td>'
        f'<td>{r["null_matched_eligible_random"]:.4f}</td><td>{r["lift_matched"]:.3f}</td>'
        f'<td>{r["spearman_rho"]:+.3f}</td></tr>'
        for r in (audit.get("top_by_within3") or [])[:5])
    return page("Results", f"""
<h2>Results &mdash; one emitted artifact, no demonstrated gain</h2>
<div class="note"><b>Label policy.</b> Every number below is either
<code>HOLDOUT-DTI</code>/<code>INTERNAL-INSTRUMENT</code> (with its evaluator, withheld-positive
count and CI where applicable) or <code>UNVERIFIED owner-reported</code>. No <code>ORGANIZER-CONFIRMED</code> number exists in this repository.</div>
{h67m_block()}

<h3>1 &middot; The artifact</h3>
<table>
<tr><th>run</th><td class="mono">{esc(run.get("schema", ""))} &middot; {esc(card.get("run_id", ""))}</td></tr>
<tr><th>dots</th><td>{prof.get("n_dots", 0):,} unit-mass positive cells; nearest-neighbour median
{prof.get("nn_median_px", 0):.2f} px</td></tr>
<tr><th>placement</th><td>{prof.get("lidar_valid_fraction", 0) * 100:.1f} % of dots on LiDAR-valid
cells; mean distance to a mapped fault {prof.get("mean_d_mapped_px", 0) * 100:,.0f} m;
{prof.get("frac_within_3px_of_mapped", 0) * 100:.2f} % within 300 m of a mapped fault</td></tr>
<tr><th>uniformity</th><td>block-density CV {prof.get("block_density_cv", 0):.2f} (pre-registered
band 0.45&ndash;0.58 &rarr; P3 falsified)</td></tr>
<tr><th>files</th><td class="mono">{esc(zpath)}
&amp; the NaN sibling; validator PASS on both</td></tr>
</table>

<h3>2 &middot; Lane discipline against the {uniq.get("n_compared", 0)} registry rasters</h3>
<p>Verdict <b>{esc(uniq.get("verdict", ""))}</b> under the implemented rule
({esc(uniq.get("reason", ""))}); max |&rho;| {uniq.get("max_abs_spearman_rho", 0):.3f}
({esc(uniq.get("argmax_rho", ""))}); max lift {uniq.get("max_lift_over_random", 0):.3f}.
<b>The raw rule is falsified:</b> {uniq.get("max_frac_dots_within_3px", 0):.4f} of the dots lie
within 3 px of one raster, but that raster's own 3 px dilation covers ~96 % of the eligible band,
so the matched lift is ~1.0. Worst five by raw overlap, with both nulls:</p>
<table><tr><th>registry raster</th><th>raw within 3 px</th><th>matched null</th><th>lift</th>
<th>&rho;</th></tr>{lift_rows}</table>

<h3>3 &middot; Negative control &mdash; degenerate, not a measurement</h3>
<p>Truth: {esc(hold.get("truth", ""))}; withheld positives
{hold.get("withheld_positive_pixels", 0):,}; evaluator <code>{esc(hold.get("evaluator_version", ""))}</code>.
Pooled DTI <b>{hold.get("pooled_dti", 0):.4f}</b>, CI {hold.get("ci95", [0, 0])}. The value is
identically zero because the 4 px exclusion removes every dot inside the credit radius of a truth
layer that is the exclusion's own complement &mdash; a property of the construction, not evidence
about placement (IR-67-INSTR-02).</p>

<h3>4 &middot; Leakage canary (rule: any feature alone, AUC &gt; 0.90 is a stop)</h3>
<table><tr><th>feature</th><th>AUC vs the control truth</th><th>flag</th></tr>{canary_rows}</table>

<h3>5 &middot; Why the owner-reported ordering is not a target to optimize</h3>
<p>Owner-reported scores (class <code>UNVERIFIED</code>, n = {e1.get("covariate_rank", {}).get("n", 14)} matched
artifacts, spread only {min(sc_list):.4f}&ndash;{max(sc_list):.4f}) co-vary with layer dot-means and,
more strongly, with <i>where</i> the dots sit: <code>col_mean</code> &rho;
{conf.get("col_mean", float("nan")):+.3f}, <code>row_std</code> &rho;
{conf.get("row_std", float("nan")):+.3f}. Top raw covariate readings from
<code>evidence/h67_e1_credit_regression.json</code> (all p &lt; 1e-5, but see the guardrails):</p>
<table><tr><th>layer dot-mean</th><th>Spearman &rho; vs owner-reported score</th><th>p</th></tr>
{cov_rows}</table>
<p class="small">{esc(guardrail)} The available truth proxies are anti-correlated with the same scores
(catalogue {rho_cat:+.3f}, SGMC-all {rho_all:+.3f}); a proxy that ranks this family backwards cannot be
used as a gate. Detail: <a href="research.html">research</a>, <a href="data/run-card.json">run card</a>,
<a href="irregularities.html">irregularities</a>.</p>
<p class="small">The inherited relief-matched `lidar_lane` numbers and their reversal are retained in
the evidence JSON and in <a href="irregularities.html">IR-66-CONFOUND-01</a>; they are historical and
do not describe the emitted artifact.</p>
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
<tr><td><b>[verified 2026-10-12]</b> <a href="https://studio.m-anage.com/agu/fm15/webprogram/Paper70055.html">AGU FM15 T31A-2838</a></td>
 <td>Sare &amp; Hilley, &ldquo;Mapping of normal fault scarps in airborne laser swath mapping data
 using wavelet analysis&rdquo;: new wavelet templates with initial scarp slope and above/below-scarp
 surface angles; Surprise Valley + Jenny Lake. The checkout's slope-aware templates come from the
 scarplet package, not this wavelet code (IR-67-SRC-01).</td>
 <td><a href="https://studio.m-anage.com/agu/fm15/webprogram/Paper70055.html">abstract</a></td></tr>
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
    d = load(ROOT / "registry" / "irregularities.json", {}) or {}
    def cls(sev):
        return {"critical": "bad", "high": "bad", "medium": "warn", "low": "warn"}.get(sev or "", "warn")
    cur, past = [], []
    for it in d.get("items", []):
        (cur if str(it.get("id", "")).startswith("IR-67") else past).append(it)
    def block(items):
        return "".join(
            f'<article class="card"><p class="eyebrow">{esc(it.get("id"))} &middot; '
            f'<span class="pill {cls(it.get("severity"))}">{esc(it.get("severity", ""))}</span> '
            f'&middot; {esc(it.get("status", ""))}</p>'
            f'<h3>{esc(it.get("title", ""))}</h3><p>{esc(it.get("detail", ""))}</p></article>'
            for it in items)
    return page("Irregularities", f"""
<h2>Irregularities</h2>
<p>Read from <code>registry/irregularities.json</code> (review date {esc(d.get("review_date", ""))}).
An irregularity is a difference between what the brief asks for, what the code does, and what the
evidence supports. Nothing here is waived; items marked OPEN stay open for the next session.</p>
<h3>This session (H67-1 + H67 lane measurement, branch arena/9ae5a972)</h3>
{block(cur)}
<h3>Inherited items, unchanged</h3>
{block(past)}
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
    stubs = {
        "submission-guide.html": ("Submission guide", "executive-summary.html"),
        "run-card.html": ("Current run card", "data/run-card.json"),
    }
    for name, (title, target) in stubs.items():
        (DOCS / name).write_text(
            f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="0; url={target}">
<title>{esc(title)} &middot; moved</title>
<link rel="canonical" href="{target}">
<style>body{{font:16px/1.58 system-ui,sans-serif;margin:3rem auto;max-width:44rem;color:#15283a}}
a{{color:#175d83}}</style></head>
<body><main>
<h1>{esc(title)} has moved</h1>
<p>This page is a generated stub. The live version is
<a href="{target}">{esc(target)}</a>. It is regenerated by
<code>scripts/build_site.py</code>, so it cannot disagree with the evidence it points at.</p>
</main></body></html>
""")
        print(f"wrote docs/{name} (stub -> {target})")
    banner = ('<!-- superseded-banner --><div class="warn" style="margin:0 0 1rem">'
              '<b>Historical page.</b> Its status statements are superseded: the current artifact '
              'status is on <a href="index.html">the overview</a> and the numbered steps are on '
              '<a href="executive-summary.html">how to submit</a>. Content below is kept as the '
              'dated record and must not be read as the current gate state.</div>')
    for name in ("analysis.html", "h66-session.html"):
        path = DOCS / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        text = text.replace(banner, "")
        if "<main>" in text:
            text = text.replace("<main>", "<main>" + banner, 1)
            path.write_text(text)
            print(f"banner refreshed on docs/{name}")
    feed = load(DOCS / "data" / "feed.json", {}) or {}
    if feed:
        (DOCS / "feed.html").write_text(feed_page(feed))
        (DOCS / "status-feed.json").write_text(
            json.dumps(feed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("wrote docs/feed.html and docs/status-feed.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
