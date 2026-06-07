#!/usr/bin/env python3
"""
Designed HTML renderer for the charity score report.

Produces a print-quality document (letter size) rendered to PDF via the
browse daemon's Chromium print pipeline. Design system: emerald brand on
report-grade: serif body, cover page with typographic score, hairline
tables with tabular numerals, and amber conflict highlighting.

Consumed by charity_report.py (--pdf); not run directly.
"""

import html as html_mod

import charity_report as cr


def esc(v) -> str:
    return html_mod.escape(str(v)) if v is not None else "—"


CSS = """
@page { size: letter; margin: 24mm 22mm 26mm 22mm; }
* { box-sizing: border-box; margin: 0; padding: 0; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body {
  font-family: Georgia, "Times New Roman", serif;
  font-size: 9.5pt; line-height: 1.62; color: #1a1a1a;
}
.sans { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; }

/* No running footer: Chromium's print pipeline clips position:fixed
   elements at the page content box, colliding with body text at page
   breaks. Attribution lives on the cover and in the closing disclaimer. */

/* ── Cover ─────────────────────────────────────────────── */
.cover { display: flex; flex-direction: column; height: 215mm; break-after: page; }
.cover .wordmark {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 9pt; font-weight: 700; letter-spacing: 0.28em; color: #14532d;
  border-bottom: 1pt solid #14532d; padding-bottom: 8pt;
}
.cover .doctype {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  margin-top: 64pt; font-size: 8pt; letter-spacing: 0.24em; text-transform: uppercase; color: #6b7280;
}
.cover h1 { font-size: 30pt; font-weight: 400; letter-spacing: -0.01em; line-height: 1.15; margin: 10pt 0 0; color: #111; }
.cover .scoreline { margin-top: 36pt; }
.cover .bignum { font-size: 58pt; line-height: 1; color: #14532d; font-weight: 400; }
.cover .bignum small { font-size: 14pt; color: #6b7280; }
.cover .breakdown { font-size: 10pt; color: #374151; margin-top: 8pt; }
.cover .scalebar { margin-top: 14pt; width: 320pt; height: 3pt; background: #e5e7eb; position: relative; }
.cover .scalebar .fill { position: absolute; left: 0; top: 0; bottom: 0; background: #14532d; }
.cover .meta { margin-top: auto; font-size: 9pt; color: #4b5563; line-height: 1.8; }
.cover .meta b { color: #111; font-weight: 600; }
.cover .conf {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  margin-top: 14pt; font-size: 7pt; letter-spacing: 0.18em; text-transform: uppercase; color: #9ca3af;
}

/* ── Headings & text ───────────────────────────────────── */
h2 {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 8.5pt; font-weight: 700; letter-spacing: 0.2em; text-transform: uppercase;
  color: #111; margin: 22pt 0 9pt; padding-bottom: 4pt;
  border-bottom: 0.75pt solid #14532d; break-after: avoid;
}
h2 .n { color: #14532d; margin-right: 10pt; }
h3 { font-size: 10.5pt; font-weight: 700; color: #111; margin: 13pt 0 5pt; break-after: avoid; }
p { margin: 0 0 7pt; }
p.lede { font-size: 10.5pt; line-height: 1.7; color: #1f2937; }
.muted { color: #6b7280; font-size: 8.5pt; }

/* ── Tables: annual-report style ───────────────────────── */
table { width: 100%; border-collapse: collapse; margin: 7pt 0 10pt; font-size: 8.5pt; }
th {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  text-align: left; font-size: 6.5pt; letter-spacing: 0.14em; text-transform: uppercase;
  color: #6b7280; font-weight: 600; padding: 0 7pt 4pt 0;
  border-bottom: 1pt solid #111;
}
td { padding: 4.5pt 7pt 4.5pt 0; border-bottom: 0.25pt solid #d9dce1; vertical-align: top; }
tr { break-inside: avoid; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
td.center, th.center { text-align: center; }
tr.conflict td { color: #7c2d12; }
.warn { color: #92400e; font-weight: 700; }
.gain { color: #14532d; font-weight: 700; font-variant-numeric: tabular-nums; }
.rank { font-variant-numeric: tabular-nums; color: #6b7280; }
.status-full { color: #14532d; }
.status-partial { color: #92400e; }
.status-missing { color: #991b1b; font-style: italic; }

/* ── Notes & quotes ────────────────────────────────────── */
.callout {
  border-left: 1.5pt solid #14532d; padding: 4pt 0 4pt 12pt; margin: 10pt 0;
  font-size: 9pt; break-inside: avoid;
}
.callout.amber { border-left-color: #92400e; }
.callout b.label {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  display: block; font-size: 6.5pt; letter-spacing: 0.18em; text-transform: uppercase;
  color: #6b7280; margin-bottom: 3pt;
}
blockquote {
  border-left: 0.75pt solid #9ca3af; padding: 1pt 0 1pt 12pt; margin: 7pt 0;
  color: #374151; font-style: italic; font-size: 9pt;
}
ul { margin: 4pt 0 9pt 14pt; }
li { margin-bottom: 3.5pt; }
ol { margin: 4pt 0 9pt 17pt; }
ol li { margin-bottom: 4.5pt; }
.links { font-size: 8pt; color: #6b7280; }
.links a { color: #14532d; text-decoration: none; }
.pagebreak { break-before: page; }
.disclaimer {
  margin-top: 20pt; padding-top: 9pt; border-top: 0.25pt solid #d9dce1;
  font-size: 7.5pt; color: #8a8f98; font-style: italic; line-height: 1.6;
}
"""


def _status_cell(status: str) -> str:
    label = cr.STATUS_LABELS.get(status, status)
    return f'<span class="status-{esc(status)}">{esc(label)}</span>'


def _components_rows(components: list[dict]) -> str:
    rows = []
    for c in components:
        evidence = cr.strip_urls(c.get("evidence") or "")
        rows.append(
            f"<tr><td><b>{esc(c['name'])}</b></td>"
            f"<td class='num'>{esc(c['scored'])}/{esc(c['possible'])}</td>"
            f"<td>{_status_cell(c.get('status', ''))}</td>"
            f"<td class='muted'>{esc(evidence)}</td></tr>"
        )
    return "".join(rows)


def _scorecard_table(components: list[dict]) -> str:
    return (
        "<table><thead><tr><th>Component</th><th class='num'>Score</th><th>Status</th><th>What we saw</th></tr></thead>"
        f"<tbody>{_components_rows(components)}</tbody></table>"
    )


def build_html(d: dict, archetypes: dict, per_source: dict | None = None) -> str:
    name = d.get("name", "Unknown")
    ein = d.get("ein", "")
    # The detail export rarely carries walletTag; derive from the zakat
    # assessment (charity_claims_zakat) with zakatEligible as fallback.
    _zakat_claim = ((d.get("amalEvaluation") or {}).get("score_details") or {}).get("zakat") or {}
    _claims = _zakat_claim.get("charity_claims_zakat")
    if _claims is None:
        _claims = d.get("zakatEligible")
    wallet = d.get("walletTag") or (
        "ZAKAT-ELIGIBLE" if _claims else ("SADAQAH-ELIGIBLE" if _claims is False else "")
    )
    last_updated = (d.get("lastUpdated") or "")[:10]
    amal = d.get("amalEvaluation") or {}
    sd = amal.get("score_details") or {}
    impact = sd.get("impact") or {}
    alignment = sd.get("alignment") or {}
    risks = sd.get("risks") or {}
    dc = sd.get("data_confidence") or {}
    narrative = amal.get("baseline_narrative") or {}

    overall = amal.get("amal_score")
    if overall is None and isinstance(impact.get("score"), int) and isinstance(alignment.get("score"), int):
        overall = impact["score"] + alignment["score"] - abs(risks.get("total_deduction") or 0)
    cn_overall = (d.get("scores") or {}).get("overall")
    deduction = abs(risks.get("total_deduction") or 0)
    pct = max(0, min(100, int(overall or 0)))

    from datetime import date

    today = date.today().isoformat()
    parts: list[str] = []
    a = parts.append

    a(f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>")

    # ── Cover page ──────────────────────────────────────────────────────
    a("<div class='cover'>")
    a("<div class='wordmark'>GOOD MEASURE GIVING</div>")
    a("<div class='doctype'>Charity Score Report · 2026</div>")
    a(f"<h1>{esc(name)}</h1>")
    a("<div class='scoreline'>")
    a(f"<div class='bignum'>{esc(overall if overall is not None else '—')}<small> / 100 GMG Score</small></div>")
    a(
        f"<div class='breakdown'>Impact {esc(impact.get('score', '—'))} of 50 &nbsp;·&nbsp; "
        f"Alignment {esc(alignment.get('score', '—'))} of 50 &nbsp;·&nbsp; Risk deduction −{esc(deduction)}"
        + (f" &nbsp;·&nbsp; Data confidence {esc(dc['badge'])}" if dc.get("badge") else "")
        + "</div>"
    )
    a(f"<div class='scalebar'><div class='fill' style='width:{pct}%'></div></div>")
    if cn_overall is not None:
        a(
            f"<p class='muted' style='margin-top:10pt'>For reference, Charity Navigator rates this organization "
            f"{esc(cn_overall)}/100 — a separate score measuring different things; the two will not match.</p>"
        )
    a("</div>")
    a("<div class='meta'>")
    a(f"<b>EIN</b> {esc(ein)}<br><b>Report date</b> {esc(today)}<br><b>Data as of</b> {esc(last_updated or 'latest run')}")
    if wallet:
        a(f"<br><b>Wallet tag</b> {esc(wallet)} <span class='muted'>(records a public claim to accept zakat; not a religious ruling by us)</span>")
    a("</div>")
    a(f"<div class='conf'>Prepared for the leadership of {esc(name)} · Good Measure Giving · goodmeasuregiving.org</div>")
    a("</div>")

    a(
        "<p class='lede'>Good Measure Giving is a charity-evaluation platform for Muslim donors. "
        "This report shows exactly what donors see: where every data point came from, the full scoring rubric, and the "
        "specific gaps between your current score and the points available to you. Every gap is closable with "
        "information you control.</p>"
    )

    # ── 01 Gaps to close (lead with the most useful section) ───────────
    improvements = cr.collect_improvements(sd)
    a("<h2><span class='n'>01</span>Gaps to close</h2>")
    if improvements:
        total_avail = sum(i["value"] for i in improvements)
        a(
            f"<p>We identified <b>up to {total_avail} points</b> of headroom, ranked by potential gain. The last column "
            "shows exactly where our pipeline reads the evidence — if you already do these things but don't publish "
            "them there, publishing is the entire fix.</p>"
        )
        a("<table><thead><tr><th class='center'>#</th><th>Component</th><th class='num'>Now</th><th class='num'>Gain</th><th>What to do</th><th>Where we'll read it</th></tr></thead><tbody>")
        for rank, item in enumerate(improvements, 1):
            read_from = cr.COMPONENT_READ_FROM.get(item["name"], "Your website / IRS filings")
            a(
                f"<tr><td class='center'><span class='rank'>{rank}</span></td>"
                f"<td><b>{esc(item['name'])}</b><br><span class='muted'>{esc(item['section'])}</span></td>"
                f"<td class='num'>{esc(item['scored'])}/{esc(item['possible'])}</td>"
                f"<td class='num'><span class='gain'>+{esc(item['value'])}</span></td>"
                f"<td>{esc(item['suggestion'])}</td><td class='muted'>{esc(read_from)}</td></tr>"
            )
        a("</tbody></table>")
    else:
        a("<p>Your component scores are at or near their maximums — keep your public data current so it stays that way.</p>")

    # ── 02 Scorecards ───────────────────────────────────────────────────
    a("<h2><span class='n'>02</span>Your scorecard</h2>")
    if impact.get("components"):
        a("<h3>Impact</h3>")
        a(_scorecard_table(impact["components"]))
    if alignment.get("components"):
        a("<h3>Alignment</h3>")
        a(_scorecard_table(alignment["components"]))

    # Risk
    a("<h3>Risk deductions</h3>")
    risk_list = risks.get("risks") or []
    if risk_list:
        a(f"<p>Current deduction: <b class='warn'>−{esc(deduction)}</b> (risk level: {esc(risks.get('overall_risk_level', ''))}).</p><ul>")
        for r in risk_list:
            if isinstance(r, dict):
                category = (r.get("category") or "risk").replace("_", " ").title()
                severity = f", {r['severity']} severity" if r.get("severity") else ""
                source = f" (source: {r['data_source']})" if r.get("data_source") else ""
                a(f"<li><b>{esc(category)}{esc(severity)}</b>: {esc(r.get('description') or '')}<span class='muted'>{esc(source)}</span></li>")
            else:
                a(f"<li>{esc(r)}</li>")
        a("</ul>")
    else:
        a("<p>No risk deductions — no governance red flags were identified.</p>")

    # Data confidence
    a("<h3>Data confidence</h3>")
    a(
        f"<p>Your badge is <b>{esc(dc.get('badge', 'UNKNOWN'))}</b>. This sits outside the score itself — it tells donors "
        "how much verified information underpins the evaluation.</p>"
    )
    a("<table style='max-width:340pt'><thead><tr><th>Signal</th><th>Level</th><th class='num'>Value</th></tr></thead><tbody>")
    dc_rows = [
        ("Verification (50%)", dc.get("verification_tier", "—"), dc.get("verification_value"), "verification"),
        ("Transparency (35%)", dc.get("transparency_label", "—"), dc.get("transparency_value"), "transparency"),
        ("Data quality (15%)", dc.get("data_quality_label", "—"), dc.get("data_quality_value"), "data_quality"),
    ]
    for label, level, value, _k in dc_rows:
        v = f"{value:.2f}" if isinstance(value, (int, float)) else "—"
        a(f"<tr><td>{esc(label)}</td><td>{esc(level)}</td><td class='num'>{esc(v)}</td></tr>")
    a("</tbody></table>")
    actions = [cr.DATA_CONFIDENCE_ACTIONS[k] for _l, _lv, value, k in dc_rows if isinstance(value, (int, float)) and value < 1]
    if actions:
        a("<p><b>To raise it:</b></p><ul>")
        for act in actions:
            a(f"<li>{esc(act)}</li>")
        a("</ul>")

    # ── 03 Where the data comes from ────────────────────────────────────
    a("<div class='pagebreak'></div>")
    a("<h2><span class='n'>03</span>Where our data comes from</h2>")
    a(
        "<p>Every figure in this report traces to a public source. If anything here is wrong or stale, the correction "
        "process in section 06 exists exactly for that.</p>"
    )
    sa_data = d.get("sourceAttribution") or {}
    source_links: dict[str, str] = {}
    if sa_data:
        a("<table><thead><tr><th>Data point</th><th>Value we read</th><th>Source</th><th>Retrieved</th></tr></thead><tbody>")
        for key in sorted(sa_data.keys()):
            entry = sa_data[key] or {}
            if not isinstance(entry, dict):
                continue
            label = cr.FIELD_LABELS.get(key, key.replace("_", " ").capitalize())
            value = entry.get("value")
            if isinstance(value, bool):
                value = "Yes" if value else "No"
            elif isinstance(value, float):
                value = f"{value:,.2f}"
            src_name = entry.get("source_name", "—")
            url = entry.get("source_url")
            if url and url not in source_links:
                source_links[url] = src_name
            ts = (entry.get("timestamp") or "")[:10]
            a(f"<tr><td>{esc(label)}</td><td><b>{esc(value if value is not None else '—')}</b></td><td>{esc(src_name)}</td><td class='muted'>{esc(ts)}</td></tr>")
        a("</tbody></table>")
    if source_links:
        a("<p class='links'><b>Source links</b> — ")
        a(" &nbsp;·&nbsp; ".join(f"<a href='{esc(u)}'>{esc(cr.strip_urls(u))}</a>" for u in sorted(source_links)))
        a("</p>")
    zce = d.get("zakatClaimEvidence") or []
    if zce:
        a("<p style='margin-top:6pt'><b>Zakat claim — the evidence we recorded:</b></p>")
        for quote in zce[:3]:
            a(f"<blockquote>{esc(cr.strip_urls(quote))}</blockquote>")
    evals = (d.get("evidenceQuality") or {}).get("evaluationSources") or []
    if evals:
        a(f"<p class='muted'><b>External evaluations and recognitions we found:</b> {esc(cr.strip_urls('; '.join(evals)))}</p>")

    a("<h3>Order of precedence when sources disagree</h3>")
    a("<table style='max-width:460pt'><thead><tr><th>Data domain</th><th>Precedence (first wins)</th></tr></thead><tbody>")
    for domain, order in cr.PRECEDENCE_RULES:
        a(f"<tr><td>{esc(domain)}</td><td>{esc(order)}</td></tr>")
    a("</tbody></table>")
    a(
        "<p class='muted'>Fields prone to unreliable automated extraction (zakat claims, beneficiary counts, external "
        "evaluations, endorsements) additionally require corroborating evidence before they affect any score — an "
        "uncorroborated claim is treated as absent, never guessed.</p>"
    )

    # ── 04 All values, all sources ──────────────────────────────────────
    a("<h2><span class='n'>04</span>All values, all sources — including where they disagree</h2>")
    if per_source:
        sources_present = [s for s in cr.SOURCE_ORDER if s in per_source]
        a(
            "<p>Sources don't always agree — different fiscal years, stale profiles, or genuine errors. Rather than hide "
            "that, this matrix shows every value from every source; conflict rows are tinted and marked.</p>"
        )
        a("<table><thead><tr><th>Field</th>")
        for s in sources_present:
            a(f"<th class='num'>{esc(cr.SOURCE_DISPLAY[s])}</th>")
        a("<th class='center'></th></tr></thead><tbody>")
        conflicts = []
        for label, kind, keys in cr.COMPARABLE_FIELDS:
            raw = [per_source.get(s, {}).get(keys.get(s)) if keys.get(s) else None for s in sources_present]
            if all(v is None for v in raw):
                continue
            conflict = cr._values_conflict([v for s, v in zip(sources_present, raw) if keys.get(s)], kind)
            if conflict:
                conflicts.append((label, kind, dict(zip(sources_present, raw))))
            cls = " class='conflict'" if conflict else ""
            a(f"<tr{cls}><td>{esc(label)}</td>")
            for s, v in zip(sources_present, raw):
                cell = cr.fmt_value(v, kind) if keys.get(s) else "·"
                a(f"<td class='num'>{esc(cell)}</td>")
            a(f"<td class='center'>{'<span class=warn>⚠</span>' if conflict else ''}</td></tr>")
        a("</tbody></table>")
        a("<p class='muted'>— = source has no value &nbsp;·&nbsp; “·” = source doesn't report this field</p>")
        if conflicts:
            a("<h3>Conflicts and how we resolved them</h3><ul>")
            sa_keys = {
                "Total revenue": "total_revenue",
                "Program expenses": "program_expenses",
                "Admin expenses": "admin_expenses",
                "Fundraising expenses": "fundraising_expenses",
                "Program expense ratio": "program_expense_ratio",
                "Founded year (self-reported)": "founded_year",
                "NTEE code": "ntee_code",
                "Candid seal": "candid_seal",
            }
            for label, kind, by_source in conflicts:
                bits = [f"{cr.SOURCE_DISPLAY[s]}: {cr.fmt_value(v, kind)}" for s, v in by_source.items() if v is not None]
                used = ""
                sa_key = sa_keys.get(label)
                if sa_key and isinstance(sa_data.get(sa_key), dict):
                    e = sa_data[sa_key]
                    used = f" → <b>we use {esc(cr.fmt_value(e.get('value'), kind))}</b> <span class='muted'>(from {esc(e.get('source_name', '?'))}, per precedence)</span>"
                a(f"<li><b>{esc(label)}</b> <span class='warn'>⚠</span> {esc('; '.join(bits))}{used}</li>")
            a("</ul>")
            a(
                "<p class='muted'>Financial figures that differ across sources usually reflect different filing years "
                "(see the Tax / fiscal year row) rather than errors — each source updates on its own schedule. Where a "
                "conflict is not a fiscal-year artifact, the correction process below applies.</p>"
            )
        else:
            a("<p>No conflicting values across sources for the fields above.</p>")
    else:
        a("<p class='muted'>Source-level detail was unavailable when this report was generated — the Sources table above still cites the winning source per field.</p>")

    # ── 05 Rubric ───────────────────────────────────────────────────────
    a("<div class='pagebreak'></div>")
    a("<h2><span class='n'>05</span>The scoring rubric, in full</h2>")
    a("<p>We publish the rubric in full so nothing about your score is a black box. Rubric v5.0.0; the same rules apply to every organization in our database.</p>")
    archetype_name = impact.get("rubric_archetype") or "UNKNOWN"
    archetype = archetypes.get(archetype_name) or {}
    weights = archetype.get("weights") or {}
    scored_by_name = {c["name"]: c for c in impact.get("components", [])}
    a(f"<h3>Impact — 50 points, weighted for your archetype: {esc(archetype_name.replace('_', ' ').title())}</h3>")
    if archetype.get("description"):
        a(f"<p class='muted'>{esc(archetype['description'])}. Weights vary by archetype so an advocacy organization is not graded on meals served.</p>")
    if weights:
        a("<table style='max-width:340pt'><thead><tr><th>Component</th><th class='num'>Weight</th><th class='num'>You scored</th></tr></thead><tbody>")
        for key, weight in weights.items():
            cname = cr.ARCHETYPE_KEY_LABELS.get(key, key.replace("_", " ").title())
            got = scored_by_name.get(cname, {}).get("scored", "—")
            a(f"<tr><td>{esc(cname)}</td><td class='num'>{esc(weight)}</td><td class='num'><b>{esc(got)}</b></td></tr>")
        a("</tbody></table>")
        a("<p class='muted'>Governance carries a 10-point floor in every archetype.</p>")
    a("<h3>Alignment — 50 points, fixed for all organizations</h3>")
    a("<table><thead><tr><th>Component</th><th class='num'>Max</th><th>How points are earned</th></tr></thead><tbody>")
    alignment_rubric = [
        ("Muslim Donor Fit", 19, "Layered: explicit zakat program +4 (or accepts zakat +2), Muslim-focused organization +2, Islamic identity +1, serving a named asnaf category +5, Muslim-majority regions +3, humanitarian service +4. Capped at 19."),
        ("Cause Urgency", 13, "Fixed points by detected cause area; humanitarian relief highest."),
        ("Underserved Space", 7, "Serving populations or geographies with limited nonprofit coverage."),
        ("Track Record", 6, "Years of operation, smoothly interpolated."),
        ("Funding Gap", 5, "Smaller organizations with greater funding gaps score higher."),
    ]
    for cname, mx, how in alignment_rubric:
        a(f"<tr><td><b>{esc(cname)}</b></td><td class='num'>{esc(mx)}</td><td class='muted'>{esc(how)}</td></tr>")
    a("</tbody></table>")
    a("<h3>Risk — deductions up to −10</h3>")
    a("<table style='max-width:400pt'><thead><tr><th>Trigger</th><th class='num'>Deduction</th><th>Source we check</th></tr></thead><tbody>")
    for trig, ded, src in [
        ("Program expense ratio below 50%", "−5", "IRS Form 990"),
        ("Board smaller than 3 members", "−5", "Form 990 / Candid"),
        ("Operating reserves under 1 month", "−2", "Form 990"),
    ]:
        a(f"<tr><td>{esc(trig)}</td><td class='num'>{esc(ded)}</td><td class='muted'>{esc(src)}</td></tr>")
    a("</tbody></table>")
    a(
        "<p class='muted'>Deductions are size-adjusted: emerging organizations (&lt;$1M revenue) are not penalized for "
        "missing data; established organizations (&gt;$10M) receive full deductions. Conflict-zone operations are never penalized.</p>"
    )
    a(
        "<p class='muted'><b>Data confidence</b> — verification 50% (Charity Navigator/Candid evaluation), transparency 35% "
        "(Candid seal, audited financials), data quality 15% (consistency across sources). Not part of the 100-point score.</p>"
    )

    # ── 06 Strengths, analysts, corrections ────────────────────────────
    strengths = narrative.get("strengths") or []
    areas = narrative.get("areas_for_improvement") or []
    if strengths or areas:
        a("<h2><span class='n'>06</span>Analyst notes</h2>")
        if strengths:
            a("<h3>What's working in your favor</h3><ul>")
            for s in strengths:
                a(f"<li>{esc(cr.strip_urls(s))}</li>")
            a("</ul>")
        if areas:
            a("<h3>Areas our analysts flagged</h3><ul>")
            for ar in areas:
                a(f"<li>{esc(cr.strip_urls(ar))}</li>")
            a("</ul>")

    a(f"<h2><span class='n'>0{7 if (strengths or areas) else 6}</span>Correcting or updating our data</h2>")
    a("<div class='callout'><b class='label'>A defined process, not an inbox black hole</b>")
    a("<ol>")
    a("<li><b>Tell us what's wrong</b> — via goodmeasuregiving.org, with the data point, what it should be, and where the correct value is published.</li>")
    a("<li><b>We triage into one of three lanes.</b> We misread a source → we fix the pipeline and re-crawl. The data isn't public yet → you publish it (section 03 shows where we read each field), then we re-run. You dispute the methodology → logged in our public issue tracker for the next rubric version.</li>")
    a("<li><b>Your evaluation is re-run end-to-end</b> — never hand-edited. Scores only ever come from the pipeline.</li>")
    a("<li><b>Every change is version-controlled</b> — we can show you exactly what changed and when.</li>")
    a("</ol>")
    a("<p>Re-evaluations are typically completed within two weeks of a verified correction.</p></div>")

    a("<div class='callout amber'><b class='label'>How to update what we see</b>")
    a(
        "<p><b>Your website</b>: publish your zakat policy, program outcomes, beneficiary counts, board composition, and "
        "annual reports where a crawler can find them. <b>Candid</b>: keep your profile current — Gold/Platinum seals feed "
        "the transparency signal. <b>Charity Navigator</b>: an up-to-date evaluation feeds verification. <b>IRS Form 990</b>: "
        "file on time — we read ratios, reserves, and governance from it. Then contact us and we'll re-run your evaluation.</p></div>"
    )

    a(
        f"<p class='disclaimer'>Good Measure Giving · goodmeasuregiving.org · Score report for {esc(name)} · {esc(today)}<br>"
        "This report is informational, generated from public data as of the date above. Scores change "
        "as data changes. The ZAKAT-ELIGIBLE tag records a verifiable public claim by your organization, not a fiqh ruling — "
        "zakat eligibility judgments belong to donors and the scholars they consult. Methodology: goodmeasuregiving.org/methodology.</p>"
    )

    a("</body></html>")
    return "".join(parts)
