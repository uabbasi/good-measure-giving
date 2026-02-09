#!/usr/bin/env python3
"""Phase 3: Baseline Scorer - Score, validate, and generate baseline narratives.

Combines:
- Confidence scoring (transparency, accountability, etc.)
- Impact scoring
- Zakat eligibility assessment
- Baseline narrative generation via LLM

Usage:
    uv run baseline pilot_charities.txt
    uv run baseline --ein 95-4453134  # Single charity
    uv run baseline --review  # Review pending narratives
"""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from src.db.repository import CharityDataRepository, CharityRepository, EvaluationRepository, RawDataRepository
from src.llm.llm_client import LLMClient

load_dotenv()
console = Console()

# Amal score weights
CONFIDENCE_WEIGHT = 0.4
IMPACT_WEIGHT = 0.4
ZAKAT_WEIGHT = 0.2

# Tier thresholds
HIGH_THRESHOLD = 80
MODERATE_THRESHOLD = 50

# Auto-approval thresholds
DENSITY_THRESHOLD = 0.80
JUDGE_SCORE_AUTO_APPROVE = 85
JUDGE_SCORE_AUTO_REJECT = 60


def _format_ratio(ratio: float | None) -> str:
    """Format expense ratio for display, handling NULL values."""
    if ratio is None:
        return "Not available"
    return f"{ratio * 100:.1f}%"


def calculate_confidence_score(charity_data: dict, raw_sources: list[dict]) -> dict:
    """Calculate confidence score based on transparency indicators."""
    score = 0
    max_score = 100
    details = {}

    # Transparency score from Candid
    transparency = charity_data.get("transparency_score")
    if transparency:
        transparency = float(transparency)  # Handle Decimal from DB
        score += min(transparency * 0.3, 30)  # Max 30 points
        details["transparency"] = "GREEN" if transparency >= 70 else "YELLOW" if transparency >= 50 else "RED"
    else:
        details["transparency"] = "RED"

    # Has multiple data sources
    successful_sources = [s for s in raw_sources if s.get("success")]
    source_score = min(len(successful_sources) * 10, 30)  # Max 30 points
    score += source_score
    details["data_sources"] = len(successful_sources)
    details["source_quality"] = "GREEN" if len(successful_sources) >= 3 else "YELLOW" if len(successful_sources) >= 2 else "RED"

    # Has revenue data
    if charity_data.get("total_revenue"):
        score += 20
        details["financials"] = "GREEN"
    else:
        details["financials"] = "RED"

    # Has program expense ratio
    if charity_data.get("program_expense_ratio"):
        ratio = charity_data["program_expense_ratio"]
        if ratio >= 0.75:
            score += 20
            details["efficiency"] = "GREEN"
        elif ratio >= 0.60:
            score += 10
            details["efficiency"] = "YELLOW"
        else:
            details["efficiency"] = "RED"

    # Determine tier
    if score >= HIGH_THRESHOLD:
        tier = "HIGH"
    elif score >= MODERATE_THRESHOLD:
        tier = "MODERATE"
    else:
        tier = "LOW"

    return {
        "score": min(score, max_score),
        "tier": tier,
        "details": details,
    }


def calculate_impact_score(charity_data: dict) -> dict:
    """Calculate impact score based on scale and efficiency."""
    score = 0
    details = {}

    # Revenue scale
    revenue = charity_data.get("total_revenue") or 0
    if revenue >= 100_000_000:
        score += 40
        details["scale"] = "GREEN"
    elif revenue >= 10_000_000:
        score += 30
        details["scale"] = "YELLOW"
    elif revenue >= 1_000_000:
        score += 20
        details["scale"] = "YELLOW"
    else:
        score += 10
        details["scale"] = "RED"

    # Program expense ratio
    ratio = charity_data.get("program_expense_ratio")
    if ratio is None:
        # Unknown - don't penalize but don't reward either
        score += 15  # Neutral score
        details["efficiency"] = "UNKNOWN"
    elif ratio >= 0.85:
        score += 40
        details["efficiency"] = "GREEN"
    elif ratio >= 0.70:
        score += 25
        details["efficiency"] = "YELLOW"
    else:
        score += 10
        details["efficiency"] = "RED"

    # CN score bonus
    cn_score = charity_data.get("charity_navigator_score")
    if cn_score and cn_score >= 90:
        score += 20
        details["third_party"] = "GREEN"
    elif cn_score and cn_score >= 75:
        score += 10
        details["third_party"] = "YELLOW"
    else:
        details["third_party"] = "RED"

    # Determine tier
    if score >= HIGH_THRESHOLD:
        tier = "HIGH"
    elif score >= MODERATE_THRESHOLD:
        tier = "MODERATE"
    else:
        tier = "LOW"

    return {
        "score": min(score, 100),
        "tier": tier,
        "details": details,
    }


def assess_zakat_eligibility(charity: dict, charity_data: dict) -> dict:
    """Assess zakat eligibility based on mission and programs."""
    # Simple keyword-based assessment
    name = (charity.get("name") or "").lower()
    mission = (charity.get("mission") or "").lower()
    # Use muslim_charity_fit from deterministic classification
    muslim_fit = charity_data.get("muslim_charity_fit", "low")
    is_muslim = muslim_fit == "high"

    # Zakat categories (simplified)
    zakat_keywords = ["poor", "needy", "poverty", "hunger", "refugee", "orphan", "disaster", "emergency"]
    sadaqah_keywords = ["education", "mosque", "school", "dawah", "community"]

    text = f"{name} {mission}"

    zakat_match = any(kw in text for kw in zakat_keywords)
    sadaqah_match = any(kw in text for kw in sadaqah_keywords)

    if is_muslim and zakat_match:
        classification = "likely_eligible"
        eligible = True
    elif is_muslim and sadaqah_match:
        classification = "partially_eligible"
        eligible = True
    elif is_muslim:
        classification = "unclear"
        eligible = False
    else:
        classification = "sadaqah_only"
        eligible = False

    return {
        "classification": classification,
        "eligible": eligible,
        "muslim_charity_fit": muslim_fit,  # Use new field name
    }


def calculate_amal_score(confidence: dict, impact: dict, zakat: dict) -> int:
    """Calculate composite Amal score."""
    conf_score = confidence["score"]
    impact_score = impact["score"]

    # Zakat bonus
    zakat_bonus = 10 if zakat["eligible"] else 0

    amal = int(
        conf_score * CONFIDENCE_WEIGHT +
        impact_score * IMPACT_WEIGHT +
        zakat_bonus * ZAKAT_WEIGHT
    )

    return min(amal, 100)


def determine_wallet_tag(amal_score: int, zakat: dict) -> str:
    """Determine wallet tag based on zakat eligibility (binary classification).

    Uses the same logic as V2 scorer for consistency:
    - ZAKAT-ELIGIBLE: Charity claims zakat eligibility on their website
    - SADAQAH-ELIGIBLE: All other charities

    Note: amal_score is not used - classification is purely based on
    charity's self-assertion of zakat eligibility. Score determines
    ranking within each category, not the category itself.
    """
    if zakat["eligible"]:
        return "ZAKAT-ELIGIBLE"
    else:
        return "SADAQAH-ELIGIBLE"


def generate_narrative(charity: dict, charity_data: dict, confidence: dict, impact: dict, zakat: dict) -> dict:
    """Generate baseline narrative using LLM."""
    llm = LLMClient()

    # Build financial context note for Form 990-exempt or no-filings orgs
    financial_note = ""
    if charity_data.get("form_990_exempt"):
        reason = charity_data.get("form_990_exempt_reason", "religious organization")
        financial_note = (
            f"\nNote: This organization is exempt from filing Form 990 ({reason}). "
            "Evaluate transparency through website disclosures."
        )
    elif charity_data.get("no_filings"):
        financial_note = "\nNote: No Form 990 filings found. This may be a new or small organization."

    prompt = f"""Generate a concise charity evaluation narrative (150-200 words) for:

Charity: {charity.get('name')}
EIN: {charity.get('ein')}
Mission: {charity.get('mission', 'Not available')}

Financial Data:
- Total Revenue: ${charity_data.get('total_revenue', 0):,}
- Program Expense Ratio: {_format_ratio(charity_data.get('program_expense_ratio'))}
- Charity Navigator Score: {charity_data.get('charity_navigator_score', 'N/A')}{financial_note}

Evaluation:
- Confidence Tier: {confidence['tier']} (score: {confidence['score']})
- Impact Tier: {impact['tier']} (score: {impact['score']})
- Zakat Classification: {zakat['classification']}
- Muslim Charity Fit: {zakat['muslim_charity_fit']}

Write a donor-facing narrative that:
1. Summarizes what the charity does
2. Highlights financial transparency and efficiency
3. Notes any concerns or strengths
4. Provides zakat eligibility guidance if applicable

Return JSON with keys: summary, strengths, concerns, zakat_guidance, recommendation
"""

    response = None
    try:
        response = llm.generate(prompt, json_schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "strengths": {"type": "array", "items": {"type": "string"}},
                "concerns": {"type": "array", "items": {"type": "string"}},
                "zakat_guidance": {"type": "string"},
                "recommendation": {"type": "string"},
            },
            "required": ["summary", "strengths", "concerns", "zakat_guidance", "recommendation"],
        })

        # Strip markdown code fences if present
        text = response.text.strip()
        if text.startswith("```"):
            # Remove opening fence (```json or ```)
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3].strip()
        return json.loads(text)
    except Exception as e:
        console.print(f"[yellow]LLM narrative generation failed: {e}[/yellow]")
        if response:
            console.print(f"[dim]Response text: {repr(response.text[:500])}[/dim]")
        return {
            "summary": f"{charity.get('name')} is a charity with {confidence['tier'].lower()} confidence.",
            "strengths": [],
            "concerns": ["Unable to generate full narrative"],
            "zakat_guidance": zakat["classification"],
            "recommendation": "Manual review recommended",
        }


def calculate_information_density(narrative: dict) -> float:
    """Calculate how complete the narrative is."""
    required_fields = ["summary", "strengths", "concerns", "zakat_guidance", "recommendation"]
    filled = sum(1 for f in required_fields if narrative.get(f))
    return filled / len(required_fields)


def score_charity(ein: str) -> dict:
    """Run full scoring pipeline for a charity."""
    charity_repo = CharityRepository()
    data_repo = CharityDataRepository()
    raw_repo = RawDataRepository()
    eval_repo = EvaluationRepository()

    # Get data
    charity = charity_repo.get(ein)
    if not charity:
        return {"ein": ein, "status": "not_found"}

    charity_data = data_repo.get(ein)
    if not charity_data:
        return {"ein": ein, "status": "no_synthesized_data"}

    raw_sources = raw_repo.get_for_charity(ein)

    # Calculate scores
    confidence = calculate_confidence_score(charity_data, raw_sources)
    impact = calculate_impact_score(charity_data)
    zakat = assess_zakat_eligibility(charity, charity_data)
    amal_score = calculate_amal_score(confidence, impact, zakat)
    wallet_tag = determine_wallet_tag(amal_score, zakat)

    # Generate narrative
    narrative = generate_narrative(charity, charity_data, confidence, impact, zakat)
    density = calculate_information_density(narrative)

    # Determine state (auto-approve high quality, review otherwise)
    if density >= DENSITY_THRESHOLD and amal_score >= JUDGE_SCORE_AUTO_APPROVE:
        state = "approved"
    elif density < 0.5 or amal_score < JUDGE_SCORE_AUTO_REJECT:
        state = "rejected"
    else:
        state = "review"

    # Store evaluation
    eval_repo.upsert({
        "charity_ein": ein,
        "amal_score": amal_score,
        "wallet_tag": wallet_tag,
        "confidence_tier": confidence["tier"],
        "impact_tier": impact["tier"],
        "zakat_classification": zakat["classification"],
        "confidence_scores": confidence["details"],
        "impact_scores": impact["details"],
        "baseline_narrative": narrative,
        "judge_score": amal_score,  # Use amal score as judge proxy
        "information_density": density,
        "state": state,
    })

    return {
        "ein": ein,
        "status": "success",
        "amal_score": amal_score,
        "wallet_tag": wallet_tag,
        "confidence_tier": confidence["tier"],
        "impact_tier": impact["tier"],
        "zakat": zakat["classification"],
        "state": state,
        "density": density,
    }


def review_pending():
    """Interactive review of pending evaluations."""
    eval_repo = EvaluationRepository()
    charity_repo = CharityRepository()

    pending = eval_repo.get_by_state("review")
    if not pending:
        console.print("[green]No pending reviews[/green]")
        return

    console.print(f"[bold]{len(pending)} charities pending review[/bold]\n")

    for i, evaluation in enumerate(pending):
        ein = evaluation["charity_ein"]
        charity = charity_repo.get(ein)
        name = charity.get("name", "Unknown") if charity else "Unknown"

        console.print(f"\n[bold]({i+1}/{len(pending)}) {name}[/bold]")
        console.print(f"EIN: {ein}")
        console.print(f"Amal Score: {evaluation.get('amal_score')}")
        console.print(f"Wallet Tag: {evaluation.get('wallet_tag')}")
        console.print(f"Zakat: {evaluation.get('zakat_classification')}")

        # Show narrative
        narrative = evaluation.get("baseline_narrative", {})
        if narrative:
            console.print(Panel(
                Markdown(f"""
**Summary:** {narrative.get('summary', 'N/A')}

**Strengths:** {', '.join(narrative.get('strengths', []))}

**Concerns:** {', '.join(narrative.get('concerns', []))}

**Zakat Guidance:** {narrative.get('zakat_guidance', 'N/A')}

**Recommendation:** {narrative.get('recommendation', 'N/A')}
"""),
                title="Narrative",
            ))

        # Get action
        action = console.input("\n[a]pprove / [r]eject / [s]kip / [q]uit: ").strip().lower()

        if action == "a":
            eval_repo.set_state(ein, "approved")
            console.print("[green]Approved[/green]")
        elif action == "r":
            eval_repo.set_state(ein, "rejected")
            console.print("[red]Rejected[/red]")
        elif action == "q":
            break
        # 's' or anything else skips


def parse_pilot_file(path: Path) -> list[str]:
    """Parse pilot_charities.txt into list of EINs."""
    eins = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("#", 1)
            ein = parts[0].strip()
            if len(ein) >= 9 and "-" in ein:
                eins.append(ein)
    return eins


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Score and generate narratives for charities")
    parser.add_argument("charities_file", type=Path, nargs="?", help="Path to pilot_charities.txt")
    parser.add_argument("--ein", help="Process single charity by EIN")
    parser.add_argument("--review", action="store_true", help="Review pending evaluations")

    args = parser.parse_args()

    if args.review:
        review_pending()
        return

    if args.ein:
        result = score_charity(args.ein)
        if result["status"] == "success":
            console.print(f"[green]OK[/green] {args.ein}")
            console.print(f"  Amal Score: {result['amal_score']}")
            console.print(f"  Wallet Tag: {result['wallet_tag']}")
            console.print(f"  Confidence: {result['confidence_tier']}")
            console.print(f"  Impact: {result['impact_tier']}")
            console.print(f"  Zakat: {result['zakat']}")
            console.print(f"  State: {result['state']}")
        else:
            console.print(f"[red]{result['status']}[/red] {args.ein}")
        return

    if not args.charities_file:
        console.print("[red]Provide charities_file or --ein[/red]")
        sys.exit(1)

    if not args.charities_file.exists():
        console.print(f"[red]File not found: {args.charities_file}[/red]")
        sys.exit(1)

    eins = parse_pilot_file(args.charities_file)
    console.print(f"[bold]Scoring {len(eins)} charities[/bold]\n")

    stats = {"approved": 0, "review": 0, "rejected": 0, "failed": 0}

    for ein in eins:
        result = score_charity(ein)
        if result["status"] == "success":
            state = result["state"]
            stats[state] = stats.get(state, 0) + 1

            icon = {"approved": "[green]✓[/green]", "review": "[yellow]?[/yellow]", "rejected": "[red]✗[/red]"}.get(state, " ")
            console.print(f"  {icon} {ein} - {result['wallet_tag']} (Amal: {result['amal_score']})")
        else:
            stats["failed"] += 1
            console.print(f"  [red]X[/red] {ein} - {result['status']}")

    console.print()
    console.print("[bold]Summary:[/bold]")
    console.print(f"  [green]Approved:[/green]  {stats['approved']}")
    console.print(f"  [yellow]Review:[/yellow]    {stats['review']}")
    console.print(f"  [red]Rejected:[/red]  {stats['rejected']}")
    console.print(f"  [red]Failed:[/red]    {stats['failed']}")


if __name__ == "__main__":
    main()
