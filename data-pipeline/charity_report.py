#!/usr/bin/env python3
"""
Generate a charity-facing score report (markdown, optionally PDF).

Audience: charity leadership — organizations that want to be featured on
Good Measure Giving and understand how to improve their scores. The report
commits to three things:

1. Citations — every data point names its source, with URL and retrieval date.
2. Rubric transparency — the full scoring rubric, including the archetype
   weights applied to this specific organization.
3. Gap analysis — concrete steps to close each gap, including exactly where
   our pipeline will read the evidence.

Data source: the website export (website/data/charities/charity-{ein}.json),
so the report always matches what donors currently see on the site. Rubric
weights are read live from config/rubric_archetypes.yaml so the report can
never drift from the implementation.

Usage:
    uv run python charity_report.py --ein 95-4453134
    uv run python charity_report.py --ein 95-4453134 --pdf
    uv run python charity_report.py --ein 95-4453134 --out /tmp/reports

PDF rendering uses the make-pdf binary if available (MAKE_PDF_BIN env var,
or the default install path); otherwise the markdown is the deliverable.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CHARITY_DATA_DIR = REPO_ROOT / "website" / "data" / "charities"
ARCHETYPES_YAML = Path(__file__).resolve().parent / "config" / "rubric_archetypes.yaml"
DEFAULT_OUT_DIR = REPO_ROOT / "docs" / "charity-reports"
MAKE_PDF_DEFAULT = Path.home() / ".claude" / "skills" / "gstack" / "make-pdf" / "dist" / "pdf"

STATUS_LABELS = {"full": "Strong", "partial": "Partial", "missing": "Missing data"}

# Friendly labels for sourceAttribution field keys.
FIELD_LABELS = {
    "total_revenue": "Total revenue",
    "program_expenses": "Program expenses",
    "admin_expenses": "Administrative expenses",
    "fundraising_expenses": "Fundraising expenses",
    "program_expense_ratio": "Program expense ratio",
    "working_capital_months": "Operating reserves (months)",
    "founded_year": "Founded year",
    "ntee_code": "NTEE classification",
    "charity_navigator_score": "Charity Navigator score",
    "candid_seal": "Candid transparency seal",
    "transparency_score": "Transparency score",
    "has_audited_financials": "Audited financials",
    "claims_zakat_eligible": "Zakat acceptance claim",
}

# Which public source feeds each scored component — tells the charity
# exactly where our pipeline will read the evidence for a fix.
COMPONENT_READ_FROM = {
    "Cost Per Beneficiary": "Beneficiary counts on your website / annual report",
    "Financial Health": "IRS Form 990 (reserves) + a published reserve policy",
    "Program Ratio": "IRS Form 990 expense allocation",
    "Evidence & Outcomes": "Outcome reports / external evaluations on your website",
    "Theory of Change": "Program pages on your website",
    "Governance": "Form 990 board roster / Candid profile",
    "Directness": "Program descriptions on your website",
    "Muslim Donor Fit": "Zakat page and policy on your website",
    "Cause Urgency": "Mission and program pages on your website",
    "Underserved Space": "Program + geography descriptions on your website",
    "Track Record": "Founding date in filings / your website",
    "Funding Gap": "IRS Form 990 revenue",
}

# Yaml weight keys → display component names (must match scorer output).
ARCHETYPE_KEY_LABELS = {
    "cost_per_beneficiary": "Cost Per Beneficiary",
    "directness": "Directness",
    "financial_health": "Financial Health",
    "program_ratio": "Program Ratio",
    "evidence_outcomes": "Evidence & Outcomes",
    "theory_of_change": "Theory of Change",
    "governance": "Governance",
}

DATA_CONFIDENCE_ACTIONS = {
    "verification": "Submit for a Charity Navigator evaluation and keep your Candid (GuideStar) profile current — third-party verification is half of the data-confidence signal.",
    "transparency": "Work toward a Candid Gold or Platinum transparency seal and publish audited financials on your website.",
    "data_quality": "Publish consistent program descriptions, beneficiary counts, and financial detail across your website and IRS filings so sources corroborate each other.",
}

# Order of precedence when sources disagree. Mirrors the documented rules in
# src/parsers/charity_metrics_aggregator.py — update both together.
PRECEDENCE_RULES = [
    ("Financial data (revenue, expenses, assets)", "IRS Form 990 (ProPublica) → Charity Navigator"),
    ("Third-party ratings", "Charity Navigator only"),
    ("Programs & mission", "Candid → your website → Charity Navigator"),
    ("Transparency signals", "Candid → Charity Navigator"),
    ("Cause classification", "Candid → Charity Navigator → IRS NTEE → your website"),
    ("Location", "IRS Form 990 → Charity Navigator → Candid"),
    ("CEO compensation", "Charity Navigator → IRS Form 990 aggregate"),
    ("Zakat acceptance", "Your website only — explicit evidence required (a zakat page, fund, or policy); inferred claims are rejected"),
]

# Per-source storage layout in raw_scraped_data.parsed_json.
SOURCE_WRAPPERS = {
    "propublica": "propublica_990",
    "charity_navigator": "cn_profile",
    "candid": "candid_profile",
    "website": "website_profile",
    "form990_grants": "grants_profile",
}
SOURCE_DISPLAY = {
    "propublica": "IRS 990 (ProPublica)",
    "charity_navigator": "Charity Navigator",
    "candid": "Candid",
    "website": "Your website",
    "form990_grants": "Form 990 grants",
}
SOURCE_ORDER = ["propublica", "charity_navigator", "candid", "website", "form990_grants"]

# Canonical fields for the all-values-by-source matrix: label, format,
# and the key under which each source reports it.
COMPARABLE_FIELDS = [
    ("Tax / fiscal year", "int", {"propublica": "tax_year", "charity_navigator": "fiscal_year", "form990_grants": "tax_year"}),
    ("Total revenue", "money", {"propublica": "total_revenue", "charity_navigator": "total_revenue", "form990_grants": "total_revenue"}),
    ("Total expenses", "money", {"propublica": "total_expenses", "charity_navigator": "total_expenses", "form990_grants": "total_expenses"}),
    ("Program expenses", "money", {"propublica": "program_expenses", "charity_navigator": "program_expenses", "form990_grants": "program_expenses"}),
    ("Admin expenses", "money", {"propublica": "admin_expenses", "charity_navigator": "admin_expenses"}),
    ("Fundraising expenses", "money", {"propublica": "fundraising_expenses", "charity_navigator": "fundraising_expenses"}),
    ("Net assets", "money", {"propublica": "net_assets", "charity_navigator": "net_assets"}),
    ("Total assets", "money", {"propublica": "total_assets", "charity_navigator": "total_assets"}),
    ("Program expense ratio", "ratio", {"charity_navigator": "program_expense_ratio"}),
    ("Board size", "int", {"candid": "board_size", "charity_navigator": "board_size"}),
    ("CEO name", "str", {"candid": "ceo_name", "charity_navigator": "ceo_name"}),
    ("IRS ruling year", "int", {"propublica": "irs_ruling_year", "charity_navigator": "irs_ruling_year", "candid": "irs_ruling_year"}),
    ("Founded year (self-reported)", "int", {"website": "founded_year"}),
    ("NTEE code", "str", {"propublica": "ntee_code", "candid": "ntee_code"}),
    ("Candid seal", "str", {"candid": "candid_seal"}),
    ("Financial audit", "bool", {"charity_navigator": "has_financial_audit"}),
    ("Accepts zakat (explicit evidence)", "bool", {"website": "accepts_zakat"}),
]


def load_charity(ein: str) -> dict:
    path = CHARITY_DATA_DIR / f"charity-{ein}.json"
    if not path.exists():
        sys.exit(f"Error: no exported data for EIN {ein} ({path})")
    with open(path) as f:
        return json.load(f)


def load_archetypes() -> dict:
    if not ARCHETYPES_YAML.exists():
        return {}
    with open(ARCHETYPES_YAML) as f:
        return (yaml.safe_load(f) or {}).get("archetypes", {})


def fmt_pts(scored, possible) -> str:
    return f"{scored}/{possible}"


def components_table(components: list[dict]) -> list[str]:
    lines = [
        "| Component | Your score | Status | What we saw |",
        "|---|---|---|---|",
    ]
    for c in components:
        evidence = (c.get("evidence") or "").replace("|", "/")
        status = STATUS_LABELS.get(c.get("status", ""), c.get("status", ""))
        lines.append(f"| {c['name']} | {fmt_pts(c['scored'], c['possible'])} | {status} | {evidence} |")
    return lines


def fetch_source_values(ein: str) -> dict | None:
    """Per-source parsed values from DoltDB (raw_scraped_data).

    Returns {source: {field: value}} for the wrapped profile of each source,
    or None when the database isn't reachable (the report then carries a
    note instead of the matrix).
    """
    try:
        from src.db.client import execute_query  # noqa: PLC0415 — optional dependency on a running DoltDB

        rows = execute_query(
            "SELECT source, parsed_json FROM raw_scraped_data WHERE charity_ein=%s AND success=TRUE",
            (ein,),
            fetch="all",
        )
    except Exception as e:  # DB down, driver missing, etc. — degrade gracefully
        print(f"  (source matrix skipped — DoltDB not reachable: {type(e).__name__})")
        return None

    per_source: dict[str, dict] = {}
    for row in rows or []:
        source = row["source"]
        wrapper = SOURCE_WRAPPERS.get(source)
        if not wrapper:
            continue
        pj = row["parsed_json"]
        if isinstance(pj, str):
            pj = json.loads(pj)
        inner = (pj or {}).get(wrapper) or {}
        if inner:
            per_source[source] = inner
    return per_source


def fmt_value(value, kind: str) -> str:
    if value is None:
        return "—"
    if kind == "money":
        try:
            return f"${float(value):,.0f}"
        except (TypeError, ValueError):
            return str(value)
    if kind == "ratio":
        try:
            return f"{float(value):.0%}"
        except (TypeError, ValueError):
            return str(value)
    if kind == "bool":
        return "Yes" if value else "No"
    return str(value)


def _values_conflict(values: list, kind: str) -> bool:
    """≥2 non-null values that genuinely differ (with rounding tolerance)."""
    present = [v for v in values if v is not None]
    if len(present) < 2:
        return False
    if kind in ("money", "ratio"):
        try:
            nums = [float(v) for v in present]
            lo, hi = min(nums), max(nums)
            return hi - lo > max(abs(hi), 1) * 0.005  # >0.5% apart
        except (TypeError, ValueError):
            pass
    norm = {str(v).strip().lower() for v in present}
    return len(norm) > 1


def source_matrix_section(d: dict, per_source: dict | None) -> list[str]:
    """All values from all sources, conflicts flagged, precedence shown."""
    lines = []
    lines.append(
        "We read multiple sources, and they don't always agree — different fiscal years, stale profiles, "
        "or genuine errors. Rather than hide that, the matrix below shows every value from every source. "
        "Conflicts are marked ⚠; the order-of-precedence table above determines which value we use."
    )
    lines.append("")
    if not per_source:
        lines.append(
            "*(Source-level detail was unavailable when this report was generated — the pipeline database "
            "was not reachable. The Sources table above still cites the winning source per field.)*"
        )
        return lines

    sources_present = [s for s in SOURCE_ORDER if s in per_source]
    sa = d.get("sourceAttribution") or {}

    header = "| Field | " + " | ".join(SOURCE_DISPLAY[s] for s in sources_present) + " | |"
    lines.append(header)
    lines.append("|" + "---|" * (len(sources_present) + 2))
    conflicts = []
    for label, kind, keys in COMPARABLE_FIELDS:
        raw_values = [per_source.get(s, {}).get(keys.get(s)) if keys.get(s) else None for s in sources_present]
        if all(v is None for v in raw_values):
            continue
        conflict = _values_conflict([v for s, v in zip(sources_present, raw_values) if keys.get(s)], kind)
        flag = "⚠" if conflict else ""
        if conflict:
            conflicts.append((label, kind, dict(zip(sources_present, raw_values))))
        cells = " | ".join(fmt_value(v, kind) if keys.get(s) else "·" for s, v in zip(sources_present, raw_values))
        lines.append(f"| {label} | {cells} | {flag} |")
    lines.append("")
    lines.append("*— = source has no value · · = source doesn't report this field*")

    if conflicts:
        lines.append("")
        lines.append("### Conflicts and how we resolved them")
        lines.append("")
        for label, kind, by_source in conflicts:
            parts = [f"{SOURCE_DISPLAY[s]}: {fmt_value(v, kind)}" for s, v in by_source.items() if v is not None]
            # What did we actually use? Look up the exported winner where mappable.
            sa_key = {
                "Total revenue": "total_revenue",
                "Program expenses": "program_expenses",
                "Admin expenses": "admin_expenses",
                "Fundraising expenses": "fundraising_expenses",
                "Program expense ratio": "program_expense_ratio",
                "Founded year (self-reported)": "founded_year",
                "NTEE code": "ntee_code",
                "Candid seal": "candid_seal",
            }.get(label)
            used = ""
            if sa_key and isinstance(sa.get(sa_key), dict):
                entry = sa[sa_key]
                used = f" → **we use {fmt_value(entry.get('value'), kind)}** (from {entry.get('source_name', '?')}, per precedence)"
            lines.append(f"- **{label}** ⚠ {'; '.join(parts)}{used}")
        lines.append("")
        lines.append(
            "Financial figures that differ across sources usually reflect different filing years (see the "
            "Tax / fiscal year row) rather than errors — each source updates on its own schedule. Where a "
            "conflict is not a fiscal-year artifact, the correction process at the end of this report applies."
        )
    else:
        lines.append("")
        lines.append("No conflicting values across sources for the fields above.")
    return lines


def sources_section(d: dict) -> list[str]:
    """Every data point we used, with its source, URL, and retrieval date."""
    lines = []
    lines.append(
        "Every figure in this report traces to a public source. The table below lists each data point, "
        "where we read it, and when. If anything here is wrong or stale, the correction process at the "
        "end of this report exists exactly for that."
    )
    lines.append("")
    sa = d.get("sourceAttribution") or {}
    if sa:
        lines.append("| Data point | Value we read | Source | Retrieved |")
        lines.append("|---|---|---|---|")
        for key in sorted(sa.keys()):
            entry = sa[key] or {}
            if not isinstance(entry, dict):
                continue
            label = FIELD_LABELS.get(key, key.replace("_", " ").capitalize())
            value = entry.get("value")
            if isinstance(value, bool):
                value = "Yes" if value else "No"
            elif isinstance(value, float):
                value = f"{value:,.2f}"
            src_name = entry.get("source_name", "—")
            src_url = entry.get("source_url")
            src = f"[{src_name}]({src_url})" if src_url else src_name
            ts = (entry.get("timestamp") or "")[:10]
            lines.append(f"| {label} | {value if value is not None else '—'} | {src} | {ts} |")
    else:
        lines.append("*(No per-field source attribution was exported for this organization — flag this with us.)*")

    # Zakat claim evidence: quote what we actually read.
    zce = d.get("zakatClaimEvidence") or []
    if zce:
        lines.append("")
        lines.append("**Zakat claim — the evidence we recorded:**")
        for quote in zce[:3]:
            lines.append(f"> {quote}")
    evals = (d.get("evidenceQuality") or {}).get("evaluationSources") or []
    if evals:
        lines.append("")
        lines.append("**External evaluations and recognitions we found:** " + "; ".join(evals))

    lines.append("")
    lines.append("### Order of precedence when sources disagree")
    lines.append("")
    lines.append("| Data domain | Precedence (first wins) |")
    lines.append("|---|---|")
    for domain, order in PRECEDENCE_RULES:
        lines.append(f"| {domain} | {order} |")
    lines.append("")
    lines.append(
        "Fields known to be unreliable when read by automated extraction (zakat claims, beneficiary counts, "
        "external evaluations, scholarly endorsements) additionally require corroborating evidence before "
        "they affect any score — an uncorroborated claim is treated as absent, never guessed."
    )
    return lines


def rubric_section(d: dict, archetypes: dict) -> list[str]:
    """The full scoring rubric, with the archetype weights applied to this org."""
    sd = (d.get("amalEvaluation") or {}).get("score_details") or {}
    impact = sd.get("impact") or {}
    archetype_name = impact.get("rubric_archetype") or "UNKNOWN"
    archetype = archetypes.get(archetype_name) or {}
    weights = archetype.get("weights") or {}
    scored_by_name = {c["name"]: c for c in impact.get("components", [])}

    lines = []
    lines.append(
        "We publish the rubric in full so nothing about your score is a black box. "
        "Rubric version 5.0.0; the same rules apply to every organization in our database."
    )

    lines.append("")
    lines.append(f"### Impact — 50 points, weighted for your archetype: {archetype_name.replace('_', ' ').title()}")
    lines.append("")
    if archetype.get("description"):
        lines.append(
            f"*{archetype['description']}.* Impact weights vary by archetype so that, for example, "
            "an advocacy organization is not graded on meals served. Your weights:"
        )
        lines.append("")
    if weights:
        lines.append("| Component | Weight (max points) | You scored |")
        lines.append("|---|---|---|")
        for key, weight in weights.items():
            name = ARCHETYPE_KEY_LABELS.get(key, key.replace("_", " ").title())
            got = scored_by_name.get(name, {}).get("scored", "—")
            lines.append(f"| {name} | {weight} | {got} |")
        lines.append("")
        lines.append("Governance carries a 10-point floor in every archetype.")
    else:
        lines.append("*(Archetype weights unavailable — see goodmeasuregiving.org/methodology.)*")

    lines.append("")
    lines.append("### Alignment — 50 points, fixed weights for all organizations")
    lines.append("")
    lines.append("| Component | Max | How points are earned |")
    lines.append("|---|---|---|")
    lines.append(
        "| Muslim Donor Fit | 19 | Layered: explicit zakat program +4 (or accepts zakat +2), Muslim-focused organization +2, "
        "Islamic identity +1, serving a named asnaf category +5, operating in Muslim-majority regions +3, humanitarian service +4. Capped at 19. |"
    )
    lines.append("| Cause Urgency | 13 | Fixed points by cause area (humanitarian relief highest), from your detected primary category. |")
    lines.append("| Underserved Space | 7 | Serving populations or geographies with limited nonprofit coverage. |")
    lines.append("| Track Record | 6 | Years of operation, smoothly interpolated. |")
    lines.append("| Funding Gap | 5 | Smaller organizations with greater funding gaps score higher. |")

    lines.append("")
    lines.append("### Risk — deductions up to −10")
    lines.append("")
    lines.append("| Trigger | Deduction | Source we check |")
    lines.append("|---|---|---|")
    lines.append("| Program expense ratio below 50% | −5 | IRS Form 990 |")
    lines.append("| Board smaller than 3 members | −5 | Form 990 / Candid |")
    lines.append("| Operating reserves under 1 month | −2 | Form 990 |")
    lines.append("")
    lines.append(
        "Deductions are size-adjusted: emerging organizations (<$1M revenue) are not penalized for *missing* "
        "data, while established organizations (>$10M) receive full deductions. Operating in conflict zones is never penalized."
    )

    lines.append("")
    lines.append("### Data Confidence — 0 to 1, displayed beside the score")
    lines.append("")
    lines.append(
        "Verification 50% (third-party evaluation by Charity Navigator/Candid), transparency 35% "
        "(Candid seal level, audited financials), data quality 15% (consistency across sources). "
        "This is not part of the 100-point score — it tells donors how much verified information sits beneath it."
    )
    return lines


def collect_improvements(score_details: dict) -> list[dict]:
    """All components with an improvement suggestion, across impact + alignment."""
    items = []
    for section_name, section in (("Impact", score_details.get("impact")), ("Alignment", score_details.get("alignment"))):
        if not section:
            continue
        for c in section.get("components", []):
            if c.get("improvement_suggestion"):
                items.append(
                    {
                        "section": section_name,
                        "name": c["name"],
                        "scored": c["scored"],
                        "possible": c["possible"],
                        "suggestion": c["improvement_suggestion"],
                        "value": c.get("improvement_value") or 0,
                    }
                )
    items.sort(key=lambda x: x["value"], reverse=True)
    return items


def data_confidence_section(dc: dict) -> list[str]:
    lines = []
    badge = dc.get("badge", "UNKNOWN")
    lines.append(
        f"Your data-confidence badge is **{badge}**. This sits outside the score itself — it tells donors "
        f"how much verified information underpins your evaluation. The three signals:"
    )
    lines.append("")
    rows = [
        ("Verification (50%)", dc.get("verification_tier", "—"), dc.get("verification_value"), "verification"),
        ("Transparency (35%)", dc.get("transparency_label", "—"), dc.get("transparency_value"), "transparency"),
        ("Data quality (15%)", dc.get("data_quality_label", "—"), dc.get("data_quality_value"), "data_quality"),
    ]
    lines.append("| Signal | Level | Value |")
    lines.append("|---|---|---|")
    for label, level, value, _key in rows:
        v = f"{value:.2f}" if isinstance(value, (int, float)) else "—"
        lines.append(f"| {label} | {level} | {v} |")
    actions = [DATA_CONFIDENCE_ACTIONS[key] for _label, _level, value, key in rows if isinstance(value, (int, float)) and value < 1]
    if actions:
        lines.append("")
        lines.append("**To raise it:**")
        for a in actions:
            lines.append(f"- {a}")
    else:
        lines.append("")
        lines.append("All three signals are at their maximum — donors see your evaluation as fully verified.")
    return lines


def corrections_section() -> list[str]:
    return [
        "Corrections follow a defined process, not an inbox black hole:",
        "",
        "1. **Tell us what's wrong** — contact us via goodmeasuregiving.org with the data point, "
        "what it should be, and where the correct value is published.",
        "2. **We triage into one of three lanes.** *We misread a source* → we correct the pipeline and re-crawl. "
        "*The data isn't public yet* → you publish it (the Sources table above shows where we read each field), "
        "then we re-run. *You dispute the methodology* → it's logged in our public issue tracker and considered "
        "for the next rubric version.",
        "3. **Your evaluation is re-run end-to-end** — not hand-edited. Scores only ever come from the pipeline.",
        "4. **Every change is version-controlled.** Our database keeps a full audit history of every value, "
        "every score, and every re-run — we can show you exactly what changed and when.",
        "",
        "Re-evaluations are typically completed within two weeks of a verified correction.",
    ]


def build_report(d: dict, archetypes: dict, per_source: dict | None = None) -> str:
    name = d.get("name", "Unknown")
    ein = d.get("ein", "")
    wallet = d.get("walletTag", "")
    last_updated = (d.get("lastUpdated") or "")[:10]
    amal = d.get("amalEvaluation") or {}
    overall = d.get("overallScore") or (d.get("scores") or {}).get("overall") or amal.get("amal_score")
    sd = amal.get("score_details") or {}
    impact = sd.get("impact") or {}
    alignment = sd.get("alignment") or {}
    risks = sd.get("risks") or {}
    dc = sd.get("data_confidence") or {}
    narrative = amal.get("baseline_narrative") or {}

    md: list[str] = []
    md.append(f"# Good Measure Giving Score Report: {name}")
    md.append("")
    md.append(f"**EIN:** {ein} · **Report date:** {date.today().isoformat()} · **Data as of:** {last_updated or 'latest pipeline run'}")
    md.append("")
    deduction = abs(risks.get("total_deduction") or 0)
    md.append(
        f"**Your GMG Score: {overall if overall is not None else '—'}/100** · "
        f"Impact {impact.get('score', '—')}/50 · Alignment {alignment.get('score', '—')}/50 · Risk deduction −{deduction}"
    )
    if wallet:
        md.append("")
        md.append(f"**Wallet tag:** {wallet} — this records whether your organization publicly states it accepts zakat; it is not a religious ruling by us.")

    md.append("")
    md.append("## Why you're receiving this")
    md.append("")
    md.append(
        "Good Measure Giving (goodmeasuregiving.org) is a charity-evaluation platform for Muslim donors. "
        "Your organization is evaluated from public data, and donors use the resulting score to decide where "
        "to give. This report shows you exactly what donors see: where every data point came from, the full "
        "scoring rubric, and — most usefully — the specific gaps between your current score and the points "
        "available to you. Every gap below is closable with information you control."
    )

    md.append("")
    md.append("## Where our data comes from")
    md.append("")
    md.extend(sources_section(d))

    md.append("")
    md.append("## All values, all sources — including where they disagree")
    md.append("")
    md.extend(source_matrix_section(d, per_source))

    md.append("")
    md.append("## The scoring rubric, in full")
    md.append("")
    md.extend(rubric_section(d, archetypes))

    if impact.get("components"):
        md.append("")
        md.append("## Your Impact scorecard")
        md.append("")
        md.extend(components_table(impact["components"]))
    if alignment.get("components"):
        md.append("")
        md.append("## Your Alignment scorecard")
        md.append("")
        md.extend(components_table(alignment["components"]))

    improvements = collect_improvements(sd)
    md.append("")
    md.append("## Gaps to close")
    md.append("")
    if improvements:
        total_avail = sum(i["value"] for i in improvements)
        md.append(
            f"We identified **up to {total_avail} points** of headroom, ranked by potential gain. "
            "The last column tells you exactly where our pipeline reads the evidence — if you already do these "
            "things but don't publish them there, publishing is the entire fix."
        )
        md.append("")
        md.append("| Priority | Component | Currently | Potential gain | What to do | Where we'll read it |")
        md.append("|---|---|---|---|---|---|")
        for rank, item in enumerate(improvements, 1):
            read_from = COMPONENT_READ_FROM.get(item["name"], "Your website / IRS filings")
            md.append(
                f"| {rank} | {item['name']} ({item['section']}) | {fmt_pts(item['scored'], item['possible'])} "
                f"| +{item['value']} | {item['suggestion']} | {read_from} |"
            )
    else:
        md.append("Your component scores are at or near their maximums — we found no concrete point opportunities. Keep your public data current so it stays that way.")

    md.append("")
    md.append("## Risk deductions")
    md.append("")
    risk_list = risks.get("risks") or []
    if risk_list:
        md.append(f"Current deduction: **−{deduction}** (risk level: {risks.get('overall_risk_level', '')}).")
        md.append("")
        for r in risk_list:
            if isinstance(r, dict):
                category = (r.get("category") or "risk").replace("_", " ").title()
                severity = r.get("severity")
                sev = f", {severity} severity" if severity else ""
                source = f" (source: {r['data_source']})" if r.get("data_source") else ""
                md.append(f"- **{category}{sev}**: {r.get('description') or ''}{source}")
            else:
                md.append(f"- {r}")
    else:
        md.append("No risk deductions — no governance red flags were identified.")

    md.append("")
    md.append("## Data confidence")
    md.append("")
    md.extend(data_confidence_section(dc))

    strengths = narrative.get("strengths") or []
    if strengths:
        md.append("")
        md.append("## What's working in your favor")
        md.append("")
        for s in strengths:
            md.append(f"- {s}")

    areas = narrative.get("areas_for_improvement") or []
    if areas:
        md.append("")
        md.append("## From our analysts")
        md.append("")
        for a in areas:
            md.append(f"- {a}")

    md.append("")
    md.append("## Correcting or updating our data")
    md.append("")
    md.extend(corrections_section())

    md.append("")
    md.append("---")
    md.append("")
    md.append(
        "*This report is informational, generated from public data as of the date above. Scores change as data "
        "changes. The ZAKAT-ELIGIBLE tag records a verifiable public claim by your organization, not a fiqh "
        "ruling — zakat eligibility judgments belong to donors and the scholars they consult. Methodology: "
        "goodmeasuregiving.org/methodology.*"
    )

    return "\n".join(md) + "\n"


def render_pdf(md_path: Path, pdf_path: Path) -> bool:
    binary = os.environ.get("MAKE_PDF_BIN") or str(MAKE_PDF_DEFAULT)
    if not os.access(binary, os.X_OK):
        print(f"  (make-pdf binary not found at {binary}; markdown only)")
        return False
    # The make-pdf daemon restricts output paths to cwd or /tmp — render
    # there, then move to the requested location.
    tmp_out = Path("/tmp") / pdf_path.name
    result = subprocess.run(
        [binary, "generate", str(md_path), str(tmp_out), "--cover", "--author", "Good Measure Giving", "--no-confidential", "--quiet"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  PDF render failed (exit {result.returncode}): {result.stderr.strip()[:200]}")
        return False
    tmp_out.replace(pdf_path)
    return True


def main():
    parser = argparse.ArgumentParser(description="Generate a charity-facing score report")
    parser.add_argument("--ein", required=True, help="Charity EIN (with dash, e.g. 95-4453134)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR, help=f"Output directory (default: {DEFAULT_OUT_DIR})")
    parser.add_argument("--pdf", action="store_true", help="Also render a PDF via make-pdf if available")
    args = parser.parse_args()

    d = load_charity(args.ein)
    archetypes = load_archetypes()
    per_source = fetch_source_values(args.ein)
    report = build_report(d, archetypes, per_source)

    args.out.mkdir(parents=True, exist_ok=True)
    slug = (d.get("name") or args.ein).lower().replace(" ", "-").replace(",", "").replace(".", "")[:50]
    md_path = args.out / f"gmg-score-report-{args.ein}-{slug}.md"
    md_path.write_text(report)
    print(f"Report: {md_path}")

    if args.pdf:
        pdf_path = md_path.with_suffix(".pdf")
        if render_pdf(md_path, pdf_path):
            print(f"PDF:    {pdf_path}")


if __name__ == "__main__":
    main()
