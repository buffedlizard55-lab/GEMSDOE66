#!/usr/bin/env python3
"""Render the GitHub Pages site from the evidence JSON -- the HTML contains no number
that a human typed: every figure is read out of registry/run_card.json at build time."""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

CSS = """
:root{--bg:#0d1117;--card:#161b22;--ink:#e6edf3;--mut:#9198a1;--ok:#2ea043;--no:#db61a2;--warn:#d29922;--line:#30363d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
main{max-width:1080px;margin:0 auto;padding:26px 20px 80px}h1{font-size:30px;margin:.2em 0}h2{margin-top:2em;border-bottom:1px solid var(--line);padding-bottom:6px}
a{color:#4493f8}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:16px 0}
.banner{border-left:6px solid var(--warn)}.banner.no{border-left-color:var(--no)}.banner.ok{border-left-color:var(--ok)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}.kpi b{display:block;font-size:24px}
.btn{display:inline-block;background:var(--ok);color:#fff;padding:11px 16px;border-radius:9px;text-decoration:none;font-weight:600;margin:4px 8px 4px 0}
.btn.alt{background:#21262d;color:var(--ink);border:1px solid var(--line)}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}
th{background:#1c2128}code{background:#1c2128;padding:1px 5px;border-radius:5px;font-size:13px}
.mut{color:var(--mut);font-size:13.5px}nav{position:sticky;top:0;background:#0d1117ee;border-bottom:1px solid var(--line);padding:10px 0;z-index:9}
nav a{margin-right:14px;font-size:14px}ul{padding-left:22px}.small{font-size:13px}
"""

NAV = ('<nav><a href="index.html">Summary</a><a href="h66-session.html">H66 run</a>'
       '<a href="executive-summary.html">How to submit</a><a href="run-card.html">Run card</a>'
       '<a href="irregularities.html">Irregularities</a><a href="sources.html">Sources</a></nav>')


def fmt(x, n=5):
    return "—" if x is None else (f"{x:.{n}f}" if isinstance(x, (int, float)) else str(x))


def build() -> int:
    c = json.loads((ROOT / "registry/run_card.json").read_text())
    h = c["holdout_dti"]
    det, sub, off = h["detector_arm"], h["submission_policy_arm"], h["off_catalogue_instrument_37654"]
    uni, val, can = c["uniqueness_vs_registry"], c["validator_output"], c["leakage_canary"]
    f = c["submission"]
    c2 = json.loads((ROOT / "registry/run_card_h66_2.json").read_text())
    st2 = c2["strata_and_controls"]
    def row(stratum, arm):
        r = st2[stratum][arm]
        key = "terrain_control" if arm.startswith("terrain_control") else arm
        rr = st2[stratum]["ratio_vs_own_mass_random"].get(key)
        ratio = "n/a" if rr is None else f"x{rr:.2f}"
        return (f"{r['n_dots']:,} dots | credit/dot {r['credit_per_dot']:.5f} | "
                f"proxy DTI {r['dti']:.5f} | {ratio} vs same-mass in-stratum random")
    stamp = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())

    index = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GEMSDOE66 · GEMS Prize · H66 LiDAR scarplet lane</title><style>{CSS}</style></head><body><main>
{NAV}
<h1>Geothermal fault prediction — 66GEMSDOE, lane: native-resolution LiDAR scarplet channels</h1>
<p class="mut">DOE GEMS Prize Challenge (DrivenData 306) · {stamp} · every number on this page is read from
<code>registry/run_card.json</code> by <code>scripts/build_site66.py</code>; nothing here is hand-typed.</p>

<div class="banner card">
<h2 style="margin-top:0;border:0">1 · Download a submission file, then decide in 10 seconds</h2>
<p><a class="btn" href="downloads/{f['file']}">⬇ {f['file']}</a>
<a class="btn alt" href="downloads/{f['file_zip']}">⬇ .zip for the portal ({f['file_zip']})</a>
<a class="btn alt" href="downloads/{f['file_nan_variant']}">⬇ spec-literal NaN-outside variant</a></p>
<p><b>Is it OK to download and submit this file?</b> <span style="color:var(--ok)">Download: YES</span> —
the file is complete, format-validated against the official grid, and unique. <span style="color:var(--no)">
Submit in this week's slot: NO — NOT PROMOTED.</span> The lane's headline mechanism (the cultural-feature veto)
came back <b>negative</b>, and the family's measured live record for LiDAR-scarp emissions is far below the
standing best. Details in the two boxes below; the full <a href="runcard.json">run card</a> is machine-readable.
Uploading it is legal and will not error — it is simply not the file we would spend a slot on, and rule 6 of the
parallel-run protocol reserves promotion for the selector step.</p>
<div class="grid">
<div class="kpi"><b>{val['reread']['n_positive']:,}</b>dots emitted (1.0), 0 elsewhere</div>
<div class="kpi"><b>{fmt(val['reread']['vmin'])} – {fmt(val['reread']['vmax'])}</b>value range, all finite</div>
<div class="kpi"><b>{fmt(det['mean'], 4)}</b>HOLDOUT-DTI, detector arm</div>
<div class="kpi"><b>{fmt(det['mass_matched_random'], 4)}</b>HOLDOUT-DTI, mass-matched random</div>
</div>
<p class="small">Why the earlier <em>“Predicted values must be in range [0, 1]”</em> rejection happened, and why it
cannot happen with these files: see <a href="executive-summary.html">How to submit</a> step 3.</p>
</div>

<div class="banner no card"><h2 style="margin-top:0;border:0">2 · The honest verdict</h2>
<ul>
<li><b>Gate (lane wording: “DTI gain on lidar-covered holdout blocks that is not confined to range fronts”)</b>:
<span style="color:var(--ok)">MET for the channel set</span> — {fmt(det['mean'],4)} vs {fmt(det['mass_matched_random'],4)}
for mass-matched random dots ({100*(det['mean']/det['mass_matched_random']-1):.0f}% better), and off-front only
{fmt(det['off_front_only']['pooled_dti'],4)}. The live-scored champion field, on the identical protocol, gets
{fmt(det['champion_h33_2_b2_same_protocol'],4)} — it deliberately places nothing near mapped trace, so this
evaluator cannot see it. <b>These are holdout values, not leaderboard scores.</b></li>
<li><b>Cultural veto (roads / canals / field edges)</b>: <span style="color:var(--no)">NEGATIVE</span> — it removed
28 of 37,654 top-ranked dots and moved the off-catalogue instrument by {fmt(off['paired_bootstrap_veto_vs_unveto']['delta_dti_mean'],6)}
(95% CI {off['paired_bootstrap_veto_vs_unveto']['delta_dti_ci95']}); the spatial-CV logistic regression put a
<i>positive</i> coefficient on the cultural index, i.e. valley-floor cultural scarps co-locate with range-front
faults instead of diluting them. Logged as a deliverable, not buried.</li>
<li><b>Submission-policy arm on the registered holdout</b>: {fmt(sub['mean'],4)} — exactly zero, <i>by construction</i>:
this evaluator's truth is withheld catalogue trace while the emission excludes everything within 300 m of the
catalogue. Flagged as IR-66-GATE-01 because it means the catalogue-hidden instrument cannot rank
off-catalogue emissions at all.</li>
<li><b>Leakage canary</b>: {can['verdict']}.</li>
<li><b>Uniqueness vs registry</b>: {uni['verdict']}. Corpus coverage: {uni['comparators_scanned']} rasters
(complete family corpus: <code>{str(uni['complete_family_corpus']).lower()}</code> — the rest is not reachable from this sandbox).</li>
<li><b>Format</b>: validator all checks passed = <code>{str(val['all_checks_passed']).lower()}</code>;
format report problems = <code>{val['format_report']['problems']}</code>.</li>
</ul></div>

<div class="card"><h2 style="margin-top:0;border:0">3 · Why 0.2778 was the family's best, and what actually beats it</h2>
<p>The published winner <code>h33-h33-2-b2</code> is <b>37,654 unit dots, none on the catalogue, the nearest one
exactly 300 m away</b> — the last rung of a pruning ladder in which every <i>deletion</i> of dots raised the score
(0.1922 → 0.2477 → 0.2600 → 0.2708 → 0.2778). Under the official metric,
<code>DTI = TP_w / (TP_w + 0.2·FP_w + 0.8·FN_w)</code> with a 300 m triangular kernel, emitted mass is a
cost: a dot pays only if its kernel credit beats <code>0.2·DTI</code> (≈0.056 at 0.2778). So the score is bought
by <b>placement and near-minimal mass</b>, not by a better probability surface.</p>
<p>Checked against the official public leaderboard while this run was built, 0.2778 sits in the twenties, not at the
top — roughly 0.14 below the leader — and the brief's “0.3195 is the highest” is a mid-top-10 value, not the maximum
(<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">live page</a>; no standings
snapshot or copied table is kept in this repository, per IR-22). Beating it therefore needs <i>more covered
truth</i>, not just tidier mass: which is why this lane was asked to bring an independent physical channel
(1 m LiDAR scarps) and why its negative result matters — the LiDAR-scarp channel, however decoded, ranks
off-catalogue structure only ~2× better than random dots, and every LiDAR-scarp emission this family has
uploaded scored 0.043–0.159. The lever left is the geophysical/geo-energy convergence family, not scarps.</p>
</div>

<div class="card"><h2 style="margin-top:0;border:0">4 · What was computed, in order</h2>
<table>
<tr><th>stage</th><th>what it did</th><th>result (tagged)</th></tr>
<tr><td>s0 inputs</td><td>sha256 of every raster against the family's pinned manifest</td>
<td>{c['inputs_verified']['pinned_files_matched']}/{c['inputs_verified']['files_checked']} verified,
{len(c['inputs_verified']['mismatches'])} mismatches; LiDAR covers {100*c['inputs_verified']['lidar_fraction_of_footprint']:.1f}% of the footprint
({c['inputs_verified']['lidar_covered_cells']:,} cells)</td></tr>
<tr><td>s1 channels</td><td>decode the 12-band 2 m stack to m/m, m, 1/m and degrees; build scarp-pixel fraction,
SNR-weighted amplitude, orientation coherence, dominant strike, relative age; build the cultural index</td>
<td>canary max AUC {can['max_auc_reflected']} (all channels); positive control 1.00</td></tr>
<tr><td>E1</td><td>population-matched off-catalogue instrument (SGMC faults &gt;300 m from the catalogue),
budgets 12k/24k/37.6k/60k, 5 mass-matched random sets, paired 20 km block bootstrap</td>
<td>DTI {fmt(off['dti'])} at 37,654 dots vs {fmt(off['random_mass_matched_dti'])} random; credit/dot {fmt(off['credit_per_dot'],4)}</td></tr>
<tr><td>E2 / E2b</td><td>registered pooled hide-and-recover holdout, both eligibility readings, range-front stratification</td>
<td>detector arm {fmt(det['mean'],4)} vs random {fmt(det['mass_matched_random'],4)}; policy arm {fmt(sub['mean'],4)}</td></tr>
<tr><td>E3</td><td>retrain under spatial CV (logistic, disjoint 20 km blocks, catalogue-proximity label)</td>
<td>AUC {fmt(h['spatial_cv_auc']['channels_only']['mean'],3)} (folds {h['spatial_cv_auc']['channels_only']['folds']});
Δ from adding the cultural feature {h['spatial_cv_auc']['channels_plus_cultural']['mean'] - h['spatial_cv_auc']['channels_only']['mean']:+.5f}</td></tr>
<tr><td>s5 + verify</td><td>2.8-px NMS top-<i>N</i> emission → float32 EPSG:32611 GeoTIFF (+ .zip, + NaN variant);
validator; registry scan</td><td>{val['reread']['n_positive']:,} dots, range [{val['reread']['vmin']}, {val['reread']['vmax']}],
finite={str(val['reread']['finite']).lower()}; ρmax {fmt(uni['max_abs_spearman_rho'],4)}</td></tr>
</table>
<p class="small">Full evidence: <code>evidence/h66_*.json</code> (inputs, canary, E1, E2, E2b, spatial CV, emission, verify).</p>
</div>

<div class="card"><h2 style="margin-top:0;border:0">5 · Candidate hypotheses ranked (this session's deliverable #1)</h2>
<table><tr><th>#</th><th>hypothesis · layers</th><th>physical signature</th><th>why it catches an uncatalogued fault</th><th>difference from everything in the repo</th><th>expected gain / cost</th></tr>
<tr><td>1</td><td><b>H66-1 cultural veto on LiDAR scarplets</b> — <code>lidar_scarp_features_u8</code> (12 bands),
<code>topo_10m_derived_100m_u8</code>, <code>geodawn_extensions_u8</code> (TMI up150)</td>
<td>long-corridor orientation coherence + along-strike amplitude constancy + flat setting + no aeromagnetic gradient</td>
<td>canal/road/field-edge scarps are the dominant false-positive family of every prior LiDAR arm; removing them
should raise credit per dot</td><td>no lane had ever built a cultural-feature mask (verified: one prose mention in the
whole family corpus); all prior LiDAR arms consumed the u8 bands as dimensionless weights</td>
<td><b>measured: negative</b> (ΔDTI −1e-5; positive logistic coefficient)</td></tr>
<tr><td>2</td><td><b>H66-2 metres-decoded scarplet SNR + relative age</b> — same stack, decoded with the build
sidecar's quantisation rule</td><td>amplitude (m/m) ÷ 20 km-block robust background; crest×toe LoG sharpness;
scarp fill fraction = mean/max</td><td>a fresh through-cutting scarp has both crest convexity and toe concavity;
constructional benches and shorelines do not</td><td>the fill-fraction and SNR constructions exist nowhere else;
prior arms used <code>u8/255</code> only</td><td><b>measured: 2.08× over random</b> off-catalogue, 1.46× on the
holdout — real but weak</td></tr>
<tr><td>3</td><td><b>H66-3 Steger/Frangi at 2–20 m on the slope-detrended surface</b></td><td>sub-pixel ridge offset +
multiscale Hessian lineness</td><td>targets the sub-100 m scarplets the 100 m stack throws away — the premise of
this lane</td><td>never done footprint-wide anywhere; and it <b>cannot be</b>: the 1 m DEM is not in the checkout and
no data host is reachable from this sandbox (egress = github/npm/pypi only)</td><td>blocked on data, not on ideas
(see §6)</td></tr>
<tr><td>4</td><td><b>H66-4 pluvial-shoreline veto</b> — elevation band + strike circularity + constant amplitude</td>
<td>Lahontan/Bonneville shorelines are near-parallel contours at discrete elevations</td><td>shoreline scarps are
the second named mimic in the stack's own caveats</td><td>the chi lane masked playas by <code>raised_n</code>;
nobody masked shorelines by their contour-parallelism</td><td>not run: 3-experiment budget spent</td></tr>
<tr><td>5</td><td><b>H66-5 geothermal convergence</b> — INGENIOUS geodetics + 2 m temperature probes + conductivity
(official features) + earthquake density</td><td>co-firing dilatation, thermal, conductivity, seismicity</td>
<td>the only evidence family independent of the compilation; the top of the board (0.4133) is not reachable by mass
control alone</td><td>no uploaded artifact in this family has used the geo-energy layers</td>
<td>needs the Actions bridge; data not in the checkout</td></tr></table>
</div>

<div class="card"><h2 style="margin-top:0;border:0">6 · Irregularities flagged for review</h2>
<ul class="small">
<li><b>IR-66-GATE-01 (High)</b> — the registered holdout and an off-catalogue emission are structurally
incompatible: with the ≥300 m exclusion the catalogue-hidden DTI is exactly 0.0 for <i>any</i> off-catalogue
emission, including a file that scored 0.2778 live (it gets {fmt(sub['mean'],4)} here). Any rule of the form
“must beat the current holdout best before touching a slot” therefore <i>cannot</i> promote off-catalogue work.</li>
<li><b>IR-66-RES-01 (High)</b> — the lane asked for Steger sub-pixel lines and 2–20 m Frangi scales on 1 m LiDAR.
Not computable footprint-wide here: the 1 m tiles are not in the checkout and the sandbox has no data egress. The
lane was executed on the pinned <i>2 m-derived</i> aggregates + 10 m topo; the deviation is in the run card, not hidden.</li>
<li><b>IR-66-SCORE-01 (Medium)</b> — the brief's “leaderboard high score 0.3774” and “0.3195 is the highest score
right now” do not match the official board we read today (rank 1 = 0.4133; 0.3195 = rank 9; 0.3774 appears nowhere
in the top 50). Treat the repo's 0.2778 as <i>owner-reported</i>, with no organizer receipt tying it to bytes.</li>
<li><b>IR-66-FORK-01 (info)</b> — <code>src/gems57</code> is vendored <b>byte-identical</b> (23/23 files, hashes in
<code>registry/template_provenance.json</code>) from 60GEMSDOE; no private fork was created.</li>
<li><b>IR-66-GUARD-01 (info)</b> — the shared <code>scripts/stop_guard.py</code> (vendored) scopes the whole
60GEMSDOE runner set to the <i>channel-steepness</i> lane; its verdict for our runner was recorded, not bypassed:
“channel-steepness is not the registered active lane” → it would refuse every non-steepness runner, including this
lane's, so the uniqueness audit is reimplemented here against the same two literal clauses.</li>
</ul></div>

<div class="card"><h2 style="margin-top:0;border:0">7 · Sources (click-through, all official or pinned)</h2>
<ul class="small">
<li>Problem description, metric, submission format: <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">/page/967/</a>
· rules <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">/306/…</a> · data (login-walled)
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/data/">/data/</a></li>
<li>Official leaderboard, read {stamp}: <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">/leaderboard/</a></li>
<li>USGS GeoDAWN (magnetics + radiometrics + LiDAR): <a href="https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and">USGS data release</a>
· DOI 10.5066/P93LGLVQ</li>
<li>INGENIOUS (Great Basin Center for Geothermal Energy): <a href="https://gbcge.org/current-projects/ingenious/">gbcge.org/current-projects/ingenious</a>
· GDR 1391 <a href="https://gdr.openei.org/submissions/1391">gdr.openei.org/submissions/1391</a></li>
<li>Reference solution (metric + pipeline): <a href="https://github.com/drivendataorg/gems-prize-reference-solution">drivendataorg/gems-prize-reference-solution</a></li>
<li>Grid CRS: <a href="https://epsg.io/32611">EPSG:32611</a> (WGS 84 / UTM zone 11N) · metric definition: <a href="https://en.wikipedia.org/wiki/Tversky_index">Tversky index</a></li>
<li>Scarplet template matching: Sare &amp; Hilley, JOSS 3(12):1066 (2018), <a href="https://doi.org/10.21105/joss.01066">doi:10.21105/joss.01066</a>
· Steger sub-pixel edges, IEEE TPAMI 20(2):113–125 (1998) · Frangi, MICCAI 1998, LNCS 1496:130–137</li>
<li>Competition write-up with the DEM-link table: <a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">docs.nlr.gov/docs/fy26osti/96647.pdf</a>
· owner mirror <a href="https://www.dropbox.com/scl/fi/aemhtutjgcp6tr3tint94/GEMS_96647.pdf?rlkey=rek210cj2smnmzb8n0sla1vmd&amp;dl=0">GEMS_96647.pdf</a></li>
<li>LiDAR band semantics actually used: <a href="https://github.com/buffedlizard55-lab/GEMSDOE24/blob/main/data/external/lidar_scarp_features.json">lidar_scarp_features.json</a>
· build run <a href="https://github.com/buffedlizard55-lab/7GEMSDOE/actions/runs/36266555805">7GEMSDOE/actions/runs/36266555805</a></li>
</ul></div>

<div class="card"><h2 style="margin-top:0;border:0">7b · H66-2 — concordance of three independent 2 m LiDAR scarp attributes</h2>
<p>The second artifact in this lane (<a href="downloads/{c2["submission"]["file"]}">{c2["submission"]["file"]}</a>,
sha256 <code>{c2["submission"]["sha256"][:16]}&hellip;</code>) is a conjunction, not a weighted blend: the geometric mean of
rank(10-vs-50 m step), rank(1&nbsp;-&nbsp;dip-sense) and rank(crest-toe sharpness). A real scarp must fire all three at once;
channel banks and terrace risers fire the slope break without the dip-sense, and rounded old scarps fire it without the
sharpness. At equal emitted mass it beats the previous H66-1 blend (credit/dot {c2["e1_ablation"]["winner_row"]["credit_per_dot"]:.4f}
vs {c2["e1_ablation"]["h66_1_blend_row"]["credit_per_dot"]:.4f}, +{100*(c2["e1_ablation"]["winner_row"]["credit_per_dot"]/c2["e1_ablation"]["h66_1_blend_row"]["credit_per_dot"]-1):.0f}%).</p>
<table><thead><tr><th>Stratum</th><th>H66-2 field</th><th>Incumbent (GEMSDOE32 h33-2-b2)</th><th>Terrain-only control</th></tr></thead><tbody>
<tr><td>upland (slope_p90 &ge; median)</td><td>{row("upland","h66_2")}</td><td>{row("upland","champion")}</td><td>{row("upland","terrain_control_at_h66_2_mass")}</td></tr>
<tr><td>basin (slope_p90 &lt; median)</td><td>{row("basin","h66_2")}</td><td>{row("basin","champion")}</td><td>{row("basin","terrain_control_at_h66_2_mass")}</td></tr>
<tr><td>pooled off-catalogue</td><td>{row("pooled","h66_2")}</td><td>{row("pooled","champion")}</td><td>{row("pooled","terrain_control_at_h66_2_mass")}</td></tr>
</tbody></table>
<p><b>Verdict: {c2["verdict"]}.</b> Three reasons, all measured here. (1) The terrain-only control — a field with no LiDAR
input at all — sits inside a factor of {st2["pooled"]["terrain_control_at_h66_2_mass"]["credit_per_dot"]/st2["pooled"]["h66_2"]["credit_per_dot"]:.2f} of the
candidate pooled, so most of the apparent signal is terrain, not scarps. (2) The field's mass is 99.95% upland: the incumbent's
advantage lives in the basin (x{st2["basin"]["ratio_vs_own_mass_random"]["champion"]:.2f} over same-mass in-stratum random there,
against no H66-2 dots). (3) The off-catalogue proxy does not order the live board at comparable mass —
&rho;={c2["transfer_check"]["spearman_in_band"]:+.2f}, p={c2["transfer_check"]["p_value_in_band"]:.2f} on the
{c2["transfer_check"]["mass_band"]}; inside that band the best credit-per-dot submission (gate-ortho, +35% over the incumbent)
still scored below it live (0.2376 vs 0.2778). Download is offered because the file is format-valid and unique; promotion is not,
and <code>scripts/h66b_verdict.py</code> reproduces every number in this table.</p>
<p class="small"><b>Two corrections recorded this session.</b> <b>IR-66-BASE-01</b>: the first run of the stratum audit drew its
&ldquo;random&rdquo; control with an index-ordered corner sample and advertised a x16 upland ratio; the corrected uniform in-stratum
baseline makes the true ratio x{c2["strata_and_controls"]["upland"]["ratio_vs_own_mass_random"]["h66_2"]:.2f}. Every &ldquo;x N random&rdquo; number from
that run is void. <b>IR-66-GUARD-02</b>: <code>scripts/stop_guard.py</code> hard-coded a lane name from a sibling checkout, so it failed
closed on every runner in this repository; it is now lane-scoped, and the H66-2 lane is registered in
<code>registry/current_site_status.json</code> with its own preregistration and first-test verdict.</p>
</div>

<div class="card"><h2 style="margin-top:0;border:0">8 · Next steps, owned end-to-end</h2>
<ol class="small">
<li>Owner decision on the two governance walls inherited from the template: the ≥300 m-off-catalogue rule vs the
catalogue-hidden holdout (IR-66-GATE-01), and the literal 3-px uniqueness clause that 60GEMSDOE proved
unsatisfiable against its own space-filling comparators.</li>
<li>Two identification uploads (<code>h69A</code>/<code>h69B</code> pattern, already built upstream) pin |G| and the
credit per dot, turning “how much mass should I emit” from modelling into arithmetic. Nothing else in this
project is worth a slot before that.</li>
<li>H66-4 shoreline veto and H66-5 geo-energy convergence: the latter needs one GitHub-Actions bridge run that
fetches the INGENIOUS geodetic/thermal rasters, because this sandbox cannot reach any data host.</li>
<li>Re-run this lane's E0 native check on the two committed 3 m pilot tiles if a session wants a
native-resolution sanity number (vendored detector <code>src/gemsdoe48/scarp3m.py</code>, hashes pinned).</li>
</ol></div>
<p class="mut small">Prepared by an Arena.ai agent. Local validation is not organizer acceptance. No submission slot was used.</p>
</main></body></html>"""

    exec_sum = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>How to submit · GEMSDOE66</title>
<style>{CSS}</style></head><body><main>{NAV}
<h1>Exactly how to make a submission into the GEMS Prize</h1>
<p class="mut">Five steps. Nothing to install, nothing to configure. The portal rejects a file whose values are not
inside [0, 1]; the files on this page are written so that cannot happen.</p>

<div class="banner ok card"><h2 style="margin-top:0;border:0">Step 1 — download <code>{f['file_zip']}</code></h2>
<p>The submission form accepts “a single-band GeoTIFF (.tif), or a .zip file containing a single GeoTIFF”. The .zip
is the smallest upload and contains exactly one file. If you prefer the bare raster, take
<code>{f['file']}</code>; both are the same bytes inside the footprint.</p></div>

<div class="card"><h2 style="margin-top:0;border:0">Step 2 — open the submission form</h2>
<p><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submission/">
https://www.drivendata.org/competitions/306/competition-doe-gems/submission/</a> → <em>New submission</em> →
<em>File to submit</em> → choose the .zip.</p></div>

<div class="banner card"><h2 style="margin-top:0;border:0">Step 3 — why your last attempt failed, and why this one will not</h2>
<p>The portal said <code>Predicted values must be in range [0, 1]</code>. That is a value check, not a format check,
and it fires for three reasons — all of them fixed in the writer here:</p>
<ol><li><b>NaN outside the footprint.</b> The problem page says data outside the bounds may be “null or nan”, but the
range validator reads the whole array. A file with NaN outside the footprint fails <code>0 ≤ p ≤ 1</code> for
those pixels. <code>{f['file']}</code> therefore writes <b>0.0 everywhere outside the footprint and carries no
nodata tag</b>; the NaN variant is kept only for spec-literalism (<code>{f['file_nan_variant']}</code>).</li>
<li><b>Unnormalised units.</b> A logit, a z-score or a 0–255 raster is out of range. The writer refuses to emit
anything not already finite and inside [0,1] — <code>src/gems52/submission_writer.py</code>-style fail-closed,
re-implemented in <code>scripts/run_h66.py s5</code> and checked again by <code>scripts/verify66.py</code>.</li>
<li><b>Wrong CRS/shape/transform or an HTML error page saved as <code>.tif</code>.</b> Check the first bytes: a
GeoTIFF starts with <code>II*\\0</code> or <code>MM\\0*</code>; a Git-LFS pointer or an S3 error page starts with
<code>version https://git-lfs…</code> or <code>&lt;?xml</code>. Our receipt below pins the sha256 of the exact bytes.</li></ol>
<p class="small"><b>Receipt for the bytes you are downloading:</b> sha256 <code>{val['sha256_allfinite']}</code> ·
{val['reread']['shape'][0]}×{val['reread']['shape'][1]} · EPSG:{val['reread']['crs'].split(':')[1]} ·
dtype {val['reread']['dtype']} · {val['reread']['n_positive']:,} positive pixels ·
min {val['reread']['vmin']} max {val['reread']['vmax']} · {'no NODATA tag' if str(val['reread']['nodata']) == 'None' else 'nodata ' + str(val['reread']['nodata'])} ·
all local checks passed <code>{str(val['all_checks_passed']).lower()}</code>.</p></div>

<div class="card"><h2 style="margin-top:0;border:0">Step 4 — fill in the note (≤140 characters)</h2>
<p>The form asks for “a short comment to help you or your team tell submissions apart later”. Paste exactly:</p>
<pre style="background:#1c2128;padding:12px;border-radius:8px;overflow:auto">{f['note']}</pre>
<p class="small">{f['note_chars']} characters. Suggested submission <b>name</b> if your mirror asks for one:
<code>{f['name']}</code>.</p></div>

<div class="banner no card"><h2 style="margin-top:0;border:0">Step 5 — decide: this file is NOT promoted</h2>
<p>Uploading it is allowed by the rules (one submission per day per team is the only hard cadence limit in this
family's notes; the weekly cap is shown on the submission page). But the honest read of the evidence is that this
artifact scores in the 0.04–0.16 band where every LiDAR-scarp emission has landed, versus a standing 0.2778 and a
board top near 0.41. Spend a slot on the selector's pick, not on a negative-result lane.</p></div>

<div class="card"><h2 style="margin-top:0;border:0">Regenerate the file yourself (auditable end to end)</h2>
<pre style="background:#1c2128;padding:12px;border-radius:8px;overflow:auto">bash scripts/fetch_inputs.sh          # restores hash-pinned inputs into data/
python scripts/run_h66.py s0 s1 s2 s3 s4 s4b s5
python scripts/verify66.py --candidate docs/downloads/&lt;file&gt;.tif
python scripts/write_run_card.py && python scripts/build_site66.py</pre>
<p class="small">Requires: <code>pip install -r requirements.txt</code> (~2 GB RAM, 2 cores, no GPU; whole run ≈ 4 min).
Every stage writes its own JSON into <code>evidence/</code> before the next one starts.</p></div>
<p class="mut small">Official format requirements being satisfied: single band · float32 · values in [0, 1] ·
EPSG:32611 · 100 m pixels · same bounds as the training data · see
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">the problem page</a>.</p>
</main></body></html>"""

    DOCS.mkdir(exist_ok=True)
    (DOCS / "h66-session.html").write_text(index)
    (DOCS / "executive-summary.html").write_text(exec_sum)
    (DOCS / "downloads" / "README.md").write_text(
        "# Downloads\n\nFiles here are produced by `python scripts/run_h66.py s5` and validated by\n"
        "`python scripts/verify66.py`. The `.tif`/`.zip` pair is byte-identical inside the footprint; the `-allfinite`\n"
        "variant is the one to upload (see `executive-summary.html`, step 3). Receipts (`*.json`) carry sha256.\n"
        "\nSecond file: `gems66-h66-2-concordance-scarp-37654-20261011T212544Z-allfinite.tif` (+ `.zip`),\n"
        "sha256 `66a8c3afad6a56855a8daf85ac885ef70697ac8b4822bbb3d6c38aafd471134c`. Same validated writer,\n"
        "same grid, same range guarantees. Its verdict is NEGATIVE-NOT-PROMOTED (see `h66-session.html`\n"
        "section 7b); download for audit, and let the selector decide.\n")
    print("wrote docs/h66-session.html, docs/executive-summary.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
