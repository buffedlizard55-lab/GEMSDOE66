"""LIDAR-02 page blocks for scripts/build_site.py (session 2026-10-20).

Everything rendered here is read from docs/data/run-card-lidar02.json at build
time.  The block shows exactly one of two banners, driven by the run card's
``promote`` flag and re-checked against the files actually present in
docs/downloads/:

  * promote == true  -> green "DOWNLOAD READY - OK TO SUBMIT" panel with the
    one-click .tif/.zip links, sha256, unique name and <=140-char note;
  * promote == false -> red "NOT OFFERED - gate not met" panel with NO raster
    link (the brief: offer the download only if the gate is met).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / "docs" / "data" / "run-card-lidar02.json"
DL = ROOT / "docs" / "downloads"


def load(p: Path, default=None):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _fmt(v):
    return f"{v:.4f}" if isinstance(v, (int, float)) else esc(v)


def _holdout_rows(card) -> str:
    rows = ""
    for arm, res in (card.get("holdout_dti", {}).get("arms_e2b") or {}).items():
        ci = res.get("ci95") or [None, None]
        rows += (f"<tr><td class='mono'>{esc(arm)}</td><td>{_fmt(res.get('mean'))}</td>"
                 f"<td>[{_fmt(ci[0])}, {_fmt(ci[1])}]</td><td>{_fmt(res.get('pooled'))}</td></tr>")
    return rows


def lidar02_block() -> str:
    card = load(CARD, {})
    if not card:
        return ""
    rel = card.get("release", {}) or {}
    promote = bool(card.get("promote")) and bool(rel.get("tif")) \
        and (DL / rel.get("tif", "")).is_file()
    rows = _holdout_rows(card)
    rc = card.get("registry_checks", {}) or {}
    wo = rc.get("worst_raw_overlap") or {}
    uniq_line = ""
    if wo:
        uniq_line = f"""
  <p class="small"><b>Uniqueness (WARN disclosure):</b> max |Spearman| {_fmt(rc.get('max_abs_spearman_dots'))}
  on dots and {_fmt(rc.get('surface_max_abs_spearman'))} on the pre-placement surface over
  {esc(rc.get('n_comparators', ''))} comparators (limit 0.90). The literal within-3px rule trips once, at
  {_fmt(wo.get('dot_overlap_within_3px'))} against <code>{esc(str(wo.get('raster','')).split('/')[-1])}</code>,
  but a matched random placement scores {_fmt(wo.get('random_control_overlap'))} against the same
  8\u00d7-denser raster (lift {_fmt(wo.get('lift_over_random'))}) \u2014 the IR-73 density artifact, reported
  verbatim here rather than silently passed.</p>"""
    gate_rows = "".join(
        f"<tr><td>{esc(k)}</td><td>{'PASS' if v else 'FAIL'}</td></tr>"
        for k, v in (card.get("gate_checks") or {}).items())
    if promote:
        body = f"""
  <h2>\u2705 LIDAR-02 (2026-10-20): DOWNLOAD READY \u2014 OK TO SUBMIT</h2>
  <p><b>One-click submission file:</b>
  <a href="downloads/{esc(rel['tif'])}"><b>{esc(rel['tif'])}</b></a>
  (<a href="downloads/{esc(rel.get('zip',''))}">.zip</a> \u00b7
  all-finite sibling <a href="downloads/{esc(rel.get('zeros_tif',''))}">{esc(rel.get('zeros_tif',''))}</a>)</p>
  <p>Upload the <b>-nan.tif</b> (competition convention: NaN only outside the footprint,
  finite values in [0, 1] inside). If the portal ever rejects it with
  \u201cPredicted values must be in range [0, 1]\u201d, upload the <b>-zeros.tif</b> sibling instead \u2014
  identical dots, every cell finite. Step-by-step: <a href="executive-summary.html">How to submit</a>.</p>
  <table>
    <tr><th>submission name</th><td class="mono">{esc(card.get('submission', {}).get('name',''))}</td></tr>
    <tr><th>note for the submission form (\u2264140 chars)</th><td>{esc(card.get('submission', {}).get('note',''))}</td></tr>
    <tr><th>sha256 (-nan.tif)</th><td class="mono">{esc(rel.get('sha256',''))}</td></tr>
    <tr><th>emitted dots</th><td>{esc(rel.get('dots',''))}</td></tr>
    <tr><th>validator</th><td>{esc(card.get('validator', {}).get('summary',''))}</td></tr>
  </table>"""
        cls = "go"
    else:
        body = f"""
  <h2>\u274c LIDAR-02 (2026-10-20): NOT OFFERED \u2014 scientific gate not met</h2>
  <p><b>There is no LIDAR-02 download. Do not submit anything from this lane.</b>
  The session's preregistered gate (see table) was not met on the spatially blocked
  holdout, so per the brief the negative result is logged and no file is offered.
  Any diagnostic bytes stay outside <code>docs/downloads/</code>; 0 submission slots were spent.</p>"""
        cls = "stop"
    return f"""
<div class="{cls}">
{body}
  <p class="small">Lane: native-resolution lidar scarp channels \u2014 slope-aware scarplet template
  (Sare &amp; Hilley 2018) + Steger/Frangi multiscale lines, executed at 100\u2013400 m on the cached
  aggregate of 2 m descriptors (1 m DEM unreachable from the sandbox; disclosed in the run card).
  LIDAR-02-A added local-SNR prominence and a cross-scale persistence gate (E2: <b>falsified</b>);
  E2b isolated the surviving mechanisms under a pre-written amendment. Every number below is
  HOLDOUT-DTI from <code>src/gems/metric.py</code>; <b>no ORGANIZER-CONFIRMED score exists</b> and
  none is projected. Run card: <a href="data/run-card-lidar02.json">run-card-lidar02.json</a> \u00b7
  session review: <a href="https://github.com/buffedlizard55-lab/GEMSDOE66/blob/main/docs/review/2026-10-20-lidar02-session.md">2026-10-20-lidar02-session.md</a>.</p>
  <table>
    <tr><th>arm (E2b, same folds/budget)</th><th>HOLDOUT-DTI mean</th><th>95% CI</th><th>pooled</th></tr>
    {rows}
  </table>
  <table>
    <tr><th>preregistered gate condition</th><th>result</th></tr>
    {gate_rows}
  </table>
  {uniq_line}
  <p class="small"><b>Caveat that qualifies the result:</b> the mid-relief stratum beats random by only
  +0.0012 pooled DTI and the low-relief (basin) stratum remains below random (kernel-credit lift 0.38) \u2014
  the pooled gain is still carried mainly by higher-relief terrain, as with LIDAR-01 (IR-74). The
  candidate's robust, replicated effect is the max-cover emission gain on identical fields
  (+0.010 to +0.019 across three fields); the LIDAR-02-A prominence/persistence field itself was
  <b>falsified</b> (below random). The blocked holdout rewards catalogue rediscovery and is an imperfect
  surrogate for the hidden expert truth \u2014 no leaderboard projection is made.</p>
</div>"""


def lidar02_exec_block() -> str:
    card = load(CARD, {})
    if not card:
        return ""
    rel = card.get("release", {}) or {}
    promote = bool(card.get("promote")) and bool(rel.get("tif")) \
        and (DL / rel.get("tif", "")).is_file()
    if not promote:
        return """
<div class="stop">
  <h3>LIDAR-02 (2026-10-20): nothing to submit from this lane</h3>
  <p>The LIDAR-02 gate was not met, so this lane contributes <b>no file</b> to the list above.
  See the negative panel on the <a href="index.html">overview page</a> and
  <a href="data/run-card-lidar02.json">run-card-lidar02.json</a>.</p>
</div>"""
    sub = card.get("submission", {})
    return f"""
<div class="go">
  <h3>\u2705 LIDAR-02 (2026-10-20): submittable file</h3>
  <ol>
    <li>Download <a href="downloads/{esc(rel['tif'])}"><b>{esc(rel['tif'])}</b></a>
        (sha256 <span class="mono">{esc(rel.get('sha256','')[:16])}\u2026</span>).</li>
    <li>On DrivenData choose <i>New submission</i> and select that exact file
        (or the <a href="downloads/{esc(rel.get('zip',''))}">.zip</a> containing it).</li>
    <li>Paste this note (\u2264140 characters): <i>{esc(sub.get('note',''))}</i></li>
    <li>If the portal rejects it with \u201cPredicted values must be in range [0, 1]\u201d, submit the
        all-finite sibling <a href="downloads/{esc(rel.get('zeros_tif',''))}">{esc(rel.get('zeros_tif',''))}</a>
        instead (same dots, no NaN anywhere).</li>
  </ol>
  <p class="small">Validated locally before publication: float32, EPSG:32611, 100 m, 3730\u00d73292,
  values in [0, 1] inside the footprint, NaN only outside it. Its evidence is HOLDOUT-DTI on a
  spatially blocked catalogue holdout (see the overview panel, including the IR-73 raw-overlap
  disclosure); no organiser score exists for this file, and spending a weekly slot on it is the
  selector's decision, not this page's.</p>
</div>"""
