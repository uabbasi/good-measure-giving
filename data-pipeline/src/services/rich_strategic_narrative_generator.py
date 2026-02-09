"""
Rich Strategic Narrative Generator - Deep strategic analysis with grounded evidence.

Follows the RichNarrativeGenerator pattern:
1. Load baseline strategic narrative from evaluation
2. Build citation registry via CitationService
3. Assemble strategic memo data (evidence signals, programs, financials, outcomes)
4. Generate via LLM with comprehensive prompt
5. Inject immutable fields from baseline strategic (headline, scores)
6. Validate and store
"""

import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from ..db.repository import (
    CharityDataRepository,
    EvaluationRepository,
    RawDataRepository,
)
from ..llm.llm_client import LLMClient, LLMTask
from ..parsers.charity_metrics_aggregator import CharityMetrics, CharityMetricsAggregator
from ..scorers.strategic_evidence import StrategicEvidence
from .citation_service import CitationService

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE_PATH = Path(__file__).parent.parent / "llm" / "prompts" / "rich_strategic_narrative.txt"


class RichStrategicNarrativeGenerator:
    """Generates rich strategic narratives with citation support and grounded evidence."""

    def __init__(self):
        self.eval_repo = EvaluationRepository()
        self.charity_data_repo = CharityDataRepository()
        self.raw_data_repo = RawDataRepository()
        self.citation_service = CitationService()
        self.llm_client = LLMClient(task=LLMTask.RICH_STRATEGIC_NARRATIVE)
        self.last_generation_cost = 0.0

    def generate(self, ein: str, force: bool = False) -> Optional[dict]:
        """Generate rich strategic narrative for a charity.

        Args:
            ein: Charity EIN
            force: If True, regenerate even if rich strategic narrative exists

        Returns:
            Rich strategic narrative dict or None if generation fails
        """
        # 1. Load baseline evaluation
        baseline = self.eval_repo.get(ein)
        if not baseline:
            logger.error(f"No baseline evaluation found for {ein}")
            return None

        # Check prerequisites
        strategic_narrative = baseline.get("strategic_narrative")
        if not strategic_narrative:
            logger.error(f"No baseline strategic narrative for {ein} — run baseline first")
            return None

        # Check if already exists
        existing = baseline.get("rich_strategic_narrative")
        if existing and not force:
            logger.info(f"Rich strategic narrative exists for {ein}, use force=True to regenerate")
            return existing

        logger.info(f"Generating rich strategic narrative for {ein}")
        self.last_generation_cost = 0.0

        # 2. Load charity data and metrics
        charity_data = self.charity_data_repo.get(ein)
        if not charity_data:
            logger.error(f"No charity_data for {ein}")
            return None

        metrics = self._load_metrics(ein)

        # 3. Load strategic evidence
        evidence_dict = charity_data.get("strategic_evidence")
        evidence = StrategicEvidence.from_dict(evidence_dict)

        # 4. Build citation registry
        citation_registry = self.citation_service.build_registry(ein)
        sources_list = citation_registry.get_sources_for_prompt()
        num_sources = len(citation_registry.sources)
        logger.info(f"Built citation registry with {num_sources} sources")

        # 5. Assemble prompt data
        prompt = self._build_prompt(
            metrics=metrics,
            charity_data=charity_data,
            strategic_narrative=strategic_narrative,
            evidence=evidence,
            sources_list=sources_list,
            num_sources=num_sources,
        )

        # 6. Generate with LLM
        try:
            response = self.llm_client.generate(
                prompt=prompt,
                temperature=0.3,
                json_mode=True,
            )
            self.last_generation_cost = response.cost_usd
            rich_content = json.loads(response.text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return None

        # 7. Inject immutable fields from baseline strategic narrative
        rich_content = self._inject_immutable_fields(rich_content, strategic_narrative, baseline)

        # 8. Validate citation structure
        self._validate_citations(rich_content, num_sources)

        # 9. Sanitize metrics in rich narrative (same safety net as baseline)
        if metrics:
            from baseline import sanitize_narrative_metrics

            scores_ns = SimpleNamespace(
                amal_score=baseline.get("amal_score"),
                wallet_tag=baseline.get("wallet_tag"),
            )
            rich_content = sanitize_narrative_metrics(rich_content, metrics, scores_ns)

        # 10. Store results
        self._store_results(ein, rich_content)

        citation_count = len(rich_content.get("all_citations", []))
        logger.info(f"Generated rich strategic narrative for {ein}: {citation_count} citations")

        return rich_content

    def _load_metrics(self, ein: str) -> Optional[CharityMetrics]:
        """Reconstruct CharityMetrics from raw data sources."""
        raw_data = self.raw_data_repo.get_for_charity(ein)
        if not raw_data:
            return None

        # Extract parsed profiles from each source
        cn_profile = None
        propublica_990 = None
        candid_profile = None
        website_profile = None

        for rd in raw_data:
            source = rd.get("source_name", "")
            parsed = rd.get("parsed_json")
            if not parsed:
                continue
            if source == "charity_navigator":
                cn_profile = parsed
            elif source == "propublica":
                propublica_990 = parsed
            elif source == "candid":
                candid_profile = parsed
            elif source == "website":
                website_profile = parsed

        try:
            return CharityMetricsAggregator.aggregate(
                charity_id=0,
                ein=ein,
                cn_profile=cn_profile,
                propublica_990=propublica_990,
                candid_profile=candid_profile,
                website_profile=website_profile,
            )
        except Exception as e:
            logger.warning(f"Failed to aggregate metrics for {ein}: {e}")
            return None

    def _build_prompt(
        self,
        metrics: Optional[CharityMetrics],
        charity_data: dict,
        strategic_narrative: dict,
        evidence: Optional[StrategicEvidence],
        sources_list: str,
        num_sources: int,
    ) -> str:
        """Build the full prompt from template + charity data."""
        template = PROMPT_TEMPLATE_PATH.read_text()

        # Charity info
        if metrics:
            charity_info = (
                f"- Name: {metrics.name}\n"
                f"- EIN: {metrics.ein}\n"
                f"- Mission: {metrics.mission or 'Not available'}\n"
                f"- Programs: {', '.join(metrics.programs[:5]) if metrics.programs else 'Not available'}\n"
                f"- Cause Area: {metrics.detected_cause_area or 'Unknown'}\n"
                f"- Founded: {metrics.founded_year or 'Unknown'}\n"
                f"- Employees: {metrics.employees_count or 'Unknown'}"
            )
        else:
            charity_info = f"- Name: {charity_data.get('charity_ein', 'Unknown')}\n- Limited data available"

        # Strategic scores from baseline narrative
        archetype = strategic_narrative.get("archetype", "Unknown")
        score = strategic_narrative.get("strategic_score", "N/A")
        strategic_scores = (
            f"- Strategic Score: {score}/100\n"
            f"- Archetype: {archetype}\n"
            f"- Headline: {strategic_narrative.get('headline', 'N/A')}"
        )

        # Add dimension scores if available from score_profiles
        score_profiles = charity_data.get("strategic_classification", {})
        if score_profiles:
            strategic_scores += (
                f"\n- Loop Breaking: {score_profiles.get('loop_breaking', 'N/A')}/10"
                f"\n- Multiplier: {score_profiles.get('multiplier', 'N/A')}/10"
                f"\n- Asset Creation: {score_profiles.get('asset_creation', 'N/A')}/10"
                f"\n- Sovereignty: {score_profiles.get('sovereignty', 'N/A')}/10"
            )

        # Strategic evidence
        evidence_str = evidence.format_for_prompt() if evidence else "No strategic evidence computed"

        # Program data
        if metrics:
            prog_descs = metrics.program_descriptions or []
            program_data = (
                f"- Programs ({len(metrics.programs)}): {', '.join(metrics.programs[:5])}\n"
                f"- Program Descriptions: {' | '.join(d[:300] for d in prog_descs[:5]) or 'Not available'}\n"
                f"- Theory of Change: {(metrics.theory_of_change or 'Not available')[:800]}\n"
                f"- Populations Served: {', '.join(metrics.populations_served[:5]) if metrics.populations_served else 'Unknown'}\n"
                f"- Geographic Coverage: {', '.join(metrics.geographic_coverage[:10]) if metrics.geographic_coverage else 'Unknown'}\n"
                f"- Beneficiaries/Year: {metrics.beneficiaries_served_annually or 'Unknown'}"
            )
        else:
            program_data = "Limited program data available"

        # Financial data
        if metrics:
            revenue = f"${metrics.total_revenue:,.0f}" if metrics.total_revenue else "Unknown"
            ratio = f"{metrics.program_expense_ratio:.1%}" if metrics.program_expense_ratio else "Unknown"
            financial_data = (
                f"- Total Revenue: {revenue}\n"
                f"- Program Expense Ratio: {ratio}\n"
                f"- Financial Audit: {metrics.has_financial_audit}\n"
                f"- Candid Seal: {metrics.candid_seal or 'None'}\n"
                f"- Board Size: {metrics.board_size or 'Unknown'} "
                f"({metrics.independent_board_members or 'Unknown'} independent)\n"
                f"- CN Score: {metrics.cn_overall_score or 'Not rated'}"
            )
            if not metrics.cn_overall_score:
                financial_data += (
                    "\n\n⚠️ CONSTRAINT: Charity Navigator score is null/missing."
                    "\nDO NOT mention any CN score, rating, or accountability rating in the narrative."
                )
        else:
            financial_data = "Limited financial data available"

        # Outcomes data
        if metrics:
            outcomes = metrics.outcomes or []
            outcomes_data = (
                f"- Reported Outcomes ({len(outcomes)}): {' | '.join(o[:200] for o in outcomes[:5]) or 'None reported'}\n"
                f"- Impact Metrics: {json.dumps(metrics.impact_metrics, default=str)[:500] if metrics.impact_metrics else 'None'}\n"
                f"- Reports Outcomes: {metrics.reports_outcomes}\n"
                f"- Has Theory of Change: {metrics.has_theory_of_change}"
            )
        else:
            outcomes_data = "Limited outcomes data available"

        # Build prompt from template
        prompt = template.format(
            charity_info=charity_info,
            strategic_scores=strategic_scores,
            num_sources=num_sources,
            citation_sources=sources_list,
            strategic_evidence=evidence_str,
            program_data=program_data,
            financial_data=financial_data,
            outcomes_data=outcomes_data,
        )

        return prompt

    def _inject_immutable_fields(
        self,
        rich_content: dict,
        strategic_narrative: dict,
        baseline: dict,
    ) -> dict:
        """Inject immutable fields from baseline strategic narrative.

        These fields should not be regenerated — they come from scoring.
        """
        # Inject headline from baseline strategic
        if strategic_narrative.get("headline"):
            rich_content["headline"] = strategic_narrative["headline"]

        # Inject score interpretation
        if strategic_narrative.get("score_interpretation"):
            rich_content["score_interpretation"] = strategic_narrative["score_interpretation"]

        # Inject strategic scores
        rich_content["strategic_score"] = baseline.get("strategic_score")
        rich_content["archetype"] = strategic_narrative.get("archetype")

        # Inject dimension scores from score_profiles if available
        score_profiles = baseline.get("score_profiles", {})
        strategic_profile = score_profiles.get("strategic", {})
        if strategic_profile:
            rich_content["dimension_scores"] = strategic_profile

        return rich_content

    def _validate_citations(self, rich_content: dict, num_sources: int) -> None:
        """Log warnings for citation issues."""
        citations = rich_content.get("all_citations", [])
        # With limited sources, minimum is the source count; otherwise target 12+
        effective_minimum = min(num_sources, 12)
        if len(citations) < effective_minimum:
            logger.warning(
                f"Rich strategic narrative has only {len(citations)} citations "
                f"(available sources: {num_sources}, effective minimum: {effective_minimum})"
            )

        # Check for out-of-range citation IDs
        for citation in citations:
            cid = citation.get("id", "")
            try:
                num = int(cid.strip("[]"))
                if num < 1 or num > num_sources:
                    logger.warning(f"Citation {cid} is out of range (1-{num_sources})")
            except (ValueError, AttributeError):
                pass

    def _store_results(self, ein: str, rich_content: dict) -> None:
        """Store rich strategic narrative in evaluations table."""
        self.eval_repo.upsert(
            {
                "charity_ein": ein,
                "rich_strategic_narrative": rich_content,
            }
        )
        logger.info(f"Stored rich strategic narrative for {ein}")
