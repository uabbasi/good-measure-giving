#!/usr/bin/env python3
"""
Generate a charity-facing score report (markdown, optionally PDF).

Audience: the charity itself — organizations that want to be featured on
Good Measure Giving and understand how to improve their scores. Tone is
constructive and concrete: here is your scorecard, here is exactly where
points are available, here is how to update the data we read.

Data source: the website export (website/data/charities/charity-{ein}.json),
so the report always matches what donors currently see on the site.

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

REPO_ROOT = Path(__file__).resolve().parent.parent
CHARITY_DATA_DIR = REPO_ROOT / "website" / "data" / "charities"
DEFAULT_OUT_DIR = REPO_ROOT / "docs" / "charity-reports"
MAKE_PDF_DEFAULT = Path.home() / ".claude" / "skills" / "gstack" / "make-pdf" / "dist" / "pdf"

STATUS_LABELS = {"full": "Strong", "partial": "Partial", "missing": "Missing data"}

DATA_CONFIDENCE_ACTIONS = {
    "verification": "Submit for a Charity Navigator evaluation and keep your Candid (GuideStar) profile current — third-party verification is half of the data-confidence signal.",
    "transparency": "Work toward a Candid Gold or Platinum transparency seal and publish audited financials on your website.",
    "data_quality": "Publish consistent program descriptions, beneficiary counts, and financial detail across your website and IRS filings so sources corroborate each other.",
}


def load_charity(ein: str) -> dict:
    path = CHARITY_DATA_DIR / f"charity-{ein}.json"
    if not path.exists():
        sys.exit(f"Error: no exported data for EIN {ein} ({path})")
    with open(path) as f:
        return json.load(f)


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


def build_report(d: dict) -> str:
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
        "Your organization is evaluated from public data — your website, IRS Form 990 filings, Charity Navigator, "
        "and Candid — and donors use the resulting score to decide where to give. This report shows you exactly "
        "what donors see, how each component of your score was earned, and where points are available. "
        "Every improvement below is something within your control."
    )

    md.append("")
    md.append("## How the score works")
    md.append("")
    md.append(
        "- **Impact (50 points)** — program effectiveness, weighted by what kind of organization you are. "
        "We don't grade an advocacy organization on meals served.\n"
        "- **Alignment (50 points)** — fit for Muslim donors: zakat clarity, cause urgency, underserved space, track record, funding gap.\n"
        "- **Risk (up to −10)** — deductions for governance red flags (low program spending, very small board, low reserves).\n"
        "- **Data Confidence (0–1, shown beside the score)** — how much verified information sits beneath the evaluation."
    )

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
    md.append("## Where you can gain points")
    md.append("")
    if improvements:
        total_avail = sum(i["value"] for i in improvements)
        md.append(
            f"We identified **up to {total_avail} points** of headroom, listed by potential gain. "
            "These reflect what our pipeline could verify from public sources — if you already do these "
            "things but don't publish them, publishing is the fix."
        )
        md.append("")
        md.append("| Priority | Component | Currently | Potential gain | What to do |")
        md.append("|---|---|---|---|---|")
        for rank, item in enumerate(improvements, 1):
            md.append(
                f"| {rank} | {item['name']} ({item['section']}) | {fmt_pts(item['scored'], item['possible'])} | +{item['value']} | {item['suggestion']} |"
            )
    else:
        md.append("Your component scores are at or near their maximums — we found no concrete point opportunities. Keep your public data current so it stays that way.")

    md.append("")
    md.append("## Risk deductions")
    md.append("")
    risk_list = risks.get("risks") or []
    if risk_list:
        md.append(f"Current deduction: **−{abs(risks.get('total_deduction') or 0)}** (risk level: {risks.get('overall_risk_level', '')}).")
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
        md.append("No risk deductions — no governance red flags were identified. ")

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
    md.append("## How to update what we see")
    md.append("")
    md.append(
        "Our pipeline re-reads public sources on a recurring basis. To make improvements visible:\n\n"
        "1. **Your website** — publish your zakat policy (if you accept zakat), program outcomes, beneficiary "
        "counts, board composition, and annual reports where a crawler can find them.\n"
        "2. **Candid (GuideStar)** — keep your profile current; Gold/Platinum seals feed the transparency signal directly.\n"
        "3. **Charity Navigator** — an up-to-date evaluation feeds the verification signal.\n"
        "4. **IRS Form 990** — file on time; we read program ratios, reserves, and governance data from it.\n\n"
        "Once you've made changes, contact us at goodmeasuregiving.org and we'll re-run your evaluation."
    )

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
    report = build_report(d)

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
