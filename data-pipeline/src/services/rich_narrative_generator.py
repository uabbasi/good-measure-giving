"""
Rich Narrative Generator - Generate citation-backed rich narratives.

Orchestrates:
1. Loading baseline evaluation
2. Building citation registry from agent discoveries
3. Assembling investment memo data (benchmarks, trends, governance)
4. Generating rich narrative with LLM
5. Injecting immutable fields from baseline
6. Validating consistency
7. Storing results
"""

import json
import logging
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional

from ..db.repository import (
    CharityDataRepository,
    CitationRepository,
    EvaluationRepository,
    RawDataRepository,
)
from ..llm.llm_client import LLMClient, LLMTask
from ..parsers.charity_metrics_aggregator import CharityMetrics, CharityMetricsAggregator
from ..schemas.discovery import (
    SECTION_AWARDS,
    SECTION_EVALUATIONS,
    SECTION_OUTCOMES,
    SECTION_THEORY_OF_CHANGE,
    SECTION_ZAKAT,
)
from ..utils.deep_link_resolver import upgrade_source_url
from ..validators.consistency_validator import ConsistencyValidator
from .benchmark_service import (
    compute_cause_benchmarks,
    extract_filing_trends,
    find_similar_orgs,
    get_filing_history,
)
from .citation_service import CitationService
from .reconciliation_engine import ReconciliationEngine

logger = logging.getLogger(__name__)


class RichNarrativeGenerator:
    """Generates rich narratives with citation support."""

    def __init__(self):
        self.eval_repo = EvaluationRepository()
        self.charity_data_repo = CharityDataRepository()
        self.raw_data_repo = RawDataRepository()
        self.citation_repo = CitationRepository()
        self.citation_service = CitationService()
        self.reconciliation_engine = ReconciliationEngine()
        self.validator = ConsistencyValidator()
        self.llm_client = LLMClient(task=LLMTask.PREMIUM_NARRATIVE)
        # Track LLM cost for the last generate() call
        self.last_generation_cost = 0.0

    def _load_metrics(self, ein: str) -> Optional[CharityMetrics]:
        """Load authoritative CharityMetrics for narrative sanitization."""
        charity_data = self.charity_data_repo.get(ein) or {}
        metrics_json = charity_data.get("metrics_json")
        if isinstance(metrics_json, dict) and metrics_json:
            try:
                return CharityMetrics.model_validate(metrics_json)
            except Exception as e:
                logger.warning(f"Failed to load synthesized metrics_json for {ein}: {e}")

        # Fallback for older rows that may not have metrics_json persisted.
        raw_data = self.raw_data_repo.get_for_charity(ein)
        if not raw_data:
            return None

        cn_profile = pp_990 = candid_profile = website_profile = None
        for rd in raw_data:
            source = rd.get("source_name") or rd.get("source") or ""
            parsed = rd.get("parsed_json")
            if not parsed:
                continue
            if source == "charity_navigator":
                cn_profile = parsed
            elif source == "propublica":
                pp_990 = parsed
            elif source == "candid":
                candid_profile = parsed
            elif source == "website":
                website_profile = parsed

        try:
            return CharityMetricsAggregator.aggregate(
                charity_id=0,
                ein=ein,
                cn_profile=cn_profile,
                propublica_990=pp_990,
                candid_profile=candid_profile,
                website_profile=website_profile,
            )
        except Exception as e:
            logger.warning(f"Failed to aggregate metrics for {ein}: {e}")
            return None

    def generate(self, ein: str, force: bool = False) -> Optional[dict]:
        """
        Generate rich narrative for a charity.

        Args:
            ein: Charity EIN
            force: If True, regenerate even if rich narrative exists

        Returns:
            Rich narrative dict or None if generation fails
        """
        # 1. Load baseline evaluation
        baseline = self._load_baseline(ein)
        if not baseline:
            logger.error(f"No baseline evaluation found for {ein}")
            return None

        # Check if rich narrative already exists
        existing_rich = baseline.get("rich_narrative")
        if existing_rich and not force:
            logger.info(f"Rich narrative already exists for {ein}, use force=True to regenerate")
            return existing_rich

        logger.info(f"Generating rich narrative for {ein}")

        # Reset cost tracking for this generation
        self.last_generation_cost = 0.0

        # 2. Build citation registry from agent discoveries
        citation_registry = self.citation_service.build_registry(ein)
        logger.info(f"Built citation registry with {len(citation_registry.sources)} sources")

        # 3. Load charity data from reconciliation
        charity_bundle = self.reconciliation_engine.reconcile(ein)
        if not charity_bundle:
            logger.warning(f"No reconciled data for {ein}, proceeding with baseline only")

        # 4. Assemble investment memo data (benchmarks, trends, governance)
        investment_memo_data = self._assemble_investment_memo_data(ein, baseline)

        # 5. Build prompt
        prompt = self._build_prompt(
            baseline=baseline,
            charity_bundle=charity_bundle,
            citation_registry=citation_registry,
            investment_memo_data=investment_memo_data,
        )

        # 6. Generate with LLM
        try:
            response = self.llm_client.generate(
                prompt=prompt,
                temperature=0.3,  # Lower temp for consistency
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

        # 7. Inject immutable fields from baseline
        baseline_narrative = baseline.get("baseline_narrative", {})
        rich_content = self._inject_immutable_fields(rich_content, baseline_narrative, baseline)
        charity_data = self.charity_data_repo.get(ein) or {}
        source_attribution = charity_data.get("source_attribution", {})
        rich_content = self._canonicalize_citation_urls(
            rich_content,
            citation_registry.sources,
            extra_context=[source_attribution, investment_memo_data],
        )

        # 7a. Validate external evaluations against actual data sources
        rich_content = self._validate_external_evaluations(ein, rich_content, investment_memo_data)

        # 8. Validate consistency
        validation_result = self.validator.validate(rich_content, baseline_narrative)

        # 8a. Validate CN score citations against actual collected data
        cn_is_rated = None
        if isinstance(investment_memo_data, dict):
            cn_ratings = investment_memo_data.get("cn_ratings", {})
            if isinstance(cn_ratings, dict):
                cn_is_rated = cn_ratings.get("cn_is_rated")
        self.validator.validate_cn_score_citations(
            rich_content,
            source_attribution,
            validation_result,
            cn_is_rated=cn_is_rated,
        )

        if not validation_result.is_valid:
            logger.error(f"Consistency validation failed for {ein} (hard failure):")
            for v in validation_result.violations:
                logger.error(f"  - {v.field}: {v.message}")
            # Invalidate rich fields to avoid serving stale or hallucinated content.
            try:
                self.eval_repo.clear_rich_narrative(ein)
            except Exception as e:
                logger.error(f"Failed to clear rich narrative for {ein}: {e}")
            return None

        # 9. Sanitize metrics in rich narrative (same safety net as baseline)
        metrics = self._load_metrics(ein)
        if metrics:
            from baseline import sanitize_narrative_metrics

            scores_ns = SimpleNamespace(
                amal_score=baseline.get("amal_score"),
                wallet_tag=baseline.get("wallet_tag"),
            )
            rich_content = sanitize_narrative_metrics(rich_content, metrics, scores_ns)

        # 9a. Re-inject authoritative fields that sanitizer may have stripped
        # amal_score_rationale is from baseline scoring, not LLM — must survive sanitization
        baseline_narrative = baseline.get("baseline_narrative", {})
        if baseline_narrative.get("amal_score_rationale"):
            rich_content["amal_score_rationale"] = baseline_narrative["amal_score_rationale"]

        # 10. Store results
        self._store_results(ein, rich_content, validation_result)

        logger.info(
            f"Generated rich narrative for {ein}: "
            f"{len(rich_content.get('all_citations', []))} citations, "
            f"valid={validation_result.is_valid}"
        )

        return rich_content

    @staticmethod
    def _canonicalize_citation_urls(
        rich_content: dict, citation_sources: list[Any], extra_context: list[Any] | None = None
    ) -> dict:
        """Upgrade homepage-like citation URLs to deeper links using registry context."""
        citations = rich_content.get("all_citations")
        if not isinstance(citations, list):
            return rich_content

        context = [
            {
                "source_name": source.source_name,
                "source_url": source.source_url,
                "claim": getattr(source, "claim_topic", ""),
            }
            for source in citation_sources
            if getattr(source, "source_url", None)
        ]
        resolver_context: dict[str, Any] = {"registry_sources": context}
        if extra_context:
            resolver_context["extra_context"] = extra_context

        for citation in citations:
            if not isinstance(citation, dict):
                continue
            source_url = citation.get("source_url")
            if not source_url:
                continue
            citation["source_url"] = upgrade_source_url(
                source_url,
                source_name=str(citation.get("source_name") or ""),
                claim=str(citation.get("claim") or citation.get("quote") or ""),
                context=resolver_context,
            )

        return rich_content

    def _load_baseline(self, ein: str) -> Optional[dict]:
        """Load baseline evaluation from database."""
        return self.eval_repo.get(ein)

    def _assemble_investment_memo_data(self, ein: str, baseline: dict) -> dict:
        """
        Assemble all data needed for investment memo sections.

        Pulls from:
        - charity_data (cause area, revenue)
        - raw_scraped_data (Candid governance, website programs, ProPublica filings,
          BBB standards, Form 990 grants, Charity Navigator scores)
        - evaluation (score_details)
        - benchmark_service (peer benchmarks, similar orgs, trends)

        Returns:
            Dict with all investment memo data
        """
        data = {}

        # Get charity data
        charity_data = self.charity_data_repo.get(ein)
        cause_area = charity_data.get("detected_cause_area") if charity_data else None
        revenue = charity_data.get("total_revenue") if charity_data else None
        primary_category = charity_data.get("primary_category") if charity_data else None
        size_tier = charity_data.get("nonprofit_size_tier") if charity_data else None
        cause_tags = charity_data.get("cause_tags") if charity_data else None
        program_focus_tags = charity_data.get("program_focus_tags") if charity_data else None

        # Get benchmarks
        if cause_area:
            benchmarks = compute_cause_benchmarks(cause_area)
            data["benchmarks"] = {
                "cause_area": cause_area,
                "peer_count": benchmarks.peer_count,
                "peer_program_ratio_median": benchmarks.program_expense_ratio_median,
                "industry_program_ratio": benchmarks.program_expense_ratio_industry,
                "peer_revenue_median": benchmarks.revenue_median,
            }

            # Find similar orgs using multi-factor similarity scoring
            # program_focus_tags enable cross-category matching for functionally similar orgs
            similar_orgs = find_similar_orgs(
                ein=ein,
                cause_area=cause_area,
                revenue=revenue,
                primary_category=primary_category,
                size_tier=size_tier,
                cause_tags=cause_tags,
                program_focus_tags=program_focus_tags,
            )
            data["similar_orgs"] = [
                {
                    "name": org.name,
                    "differentiator": org.differentiator,
                    "similarity_score": org.similarity_score,
                }
                for org in similar_orgs
            ]

        # Get filing trends
        filing_history = get_filing_history(ein)
        if filing_history:
            trends = extract_filing_trends(filing_history)
            data["filing_trends"] = {
                "years": trends.years,
                "revenue": trends.revenue,
                "expenses": trends.expenses,
                "net_assets": trends.net_assets,
                "revenue_cagr_3yr": trends.revenue_cagr_3yr,
            }

        # Get Candid data for governance + outcome metrics + charting impact
        candid_data = self._get_raw_source(ein, "candid")
        if candid_data:
            candid_profile = candid_data.get("candid_profile", {})
            data["governance"] = {
                "board_members": candid_profile.get("board_members", []),
                "board_size": candid_profile.get("board_size"),
                "ceo_name": candid_profile.get("ceo_name"),
                "mission": candid_profile.get("mission"),
                "ntee_code": candid_profile.get("ntee_code"),
                "candid_seal": candid_profile.get("candid_seal"),
                "strategic_goals": candid_profile.get("strategic_goals", []),
                "areas_served": candid_profile.get("geographic_coverage", []),
                "populations_served": candid_profile.get("populations_served", []),
                # NEW: Outcome metrics from Candid
                "metrics": candid_profile.get("metrics", []),
                "metrics_count": candid_profile.get("metrics_count"),
                "max_years_tracked": candid_profile.get("max_years_tracked"),
                # NEW: Charting Impact data
                "has_charting_impact": candid_profile.get("has_charting_impact"),
                "charting_impact_goal": candid_profile.get("charting_impact_goal"),
                "charting_impact_strategies": candid_profile.get("charting_impact_strategies"),
                "charting_impact_progress": candid_profile.get("charting_impact_progress"),
                # NEW: Feedback practices (Platinum seals)
                "feedback_practices": candid_profile.get("feedback_practices", []),
                "feedback_usage": candid_profile.get("feedback_usage"),
                # NEW: Evaluation documents
                "evaluation_documents": candid_profile.get("evaluation_documents", []),
            }

        # Get website data for programs and geographic coverage
        website_data = self._get_raw_source(ein, "website")
        if website_data:
            website_profile = website_data.get("website_profile", {})
            data["website"] = {
                "programs": website_profile.get("programs", []),
                "geographic_coverage": website_profile.get("geographic_coverage", []),
                "founded_year": website_profile.get("founded_year"),
                "impact_metrics": website_profile.get("impact_metrics", {}),
                # NEW: Beneficiaries and cost metrics
                "beneficiaries_served": website_profile.get("beneficiaries_served"),
                "cost_metrics": website_profile.get("cost_metrics", {}),
                # NEW: Report availability
                "has_annual_report": website_profile.get("has_annual_report"),
                "annual_report_url": website_profile.get("annual_report_url"),
                "has_impact_report": website_profile.get("has_impact_report"),
                "impact_report_url": website_profile.get("impact_report_url"),
                # NEW: Leadership from website
                "leadership": website_profile.get("leadership", []),
                # NEW: PDF-extracted outcomes (stored as outcomes_data in website_profile)
                "pdf_outcomes": website_profile.get("outcomes_data", []),
            }

        # Get discovered data for zakat verification + external evidence
        discovered_data = self._get_raw_source(ein, "discovered")
        if discovered_data:
            discovered_profile = discovered_data.get("discovered_profile", {})
            zakat_data = discovered_profile.get(SECTION_ZAKAT, {})
            data["zakat"] = {
                "accepts_zakat": zakat_data.get("accepts_zakat", False),
                "zakat_categories_served": zakat_data.get("zakat_categories_served", []),
            }
            # NEW: Non-zakat discoveries
            # Note: awards can be a nested dict with 'awards' list inside, or a list directly
            awards_data = discovered_profile.get(SECTION_AWARDS, {})
            if isinstance(awards_data, dict):
                awards_list = awards_data.get("awards", [])
                awards_evidence = awards_data.get("evidence")
            else:
                awards_list = awards_data if isinstance(awards_data, list) else []
                awards_evidence = None
            data["discoveries"] = {
                "evaluations": discovered_profile.get(SECTION_EVALUATIONS, {}),
                "outcomes": discovered_profile.get(SECTION_OUTCOMES, {}),
                "theory_of_change": discovered_profile.get(SECTION_THEORY_OF_CHANGE, {}),
                "awards": awards_list,
                "awards_evidence": awards_evidence,
            }

        # Get ProPublica data for additional financials + revenue breakdown
        propublica_data = self._get_raw_source(ein, "propublica")
        if propublica_data:
            p990 = propublica_data.get("propublica_990", {})
            data["form_990"] = {
                "tax_year": p990.get("tax_year"),
                "employees_count": p990.get("employees_count"),
                "volunteers_count": p990.get("volunteers_count"),
                "compensation_current_officers": p990.get("compensation_current_officers"),
                "other_salaries_wages": p990.get("other_salaries_wages"),
                "total_revenue": p990.get("total_revenue"),
                "total_expenses": p990.get("total_expenses"),
                "net_assets": p990.get("net_assets"),
                "subsection_code": p990.get("subsection_code"),
                # NEW: Revenue breakdown
                "revenue_breakdown": {
                    "contributions": p990.get("total_contributions"),
                    "program_service": p990.get("program_service_revenue"),
                    "investment_income": p990.get("investment_income"),
                    "other_revenue": p990.get("other_revenue"),
                },
                # NEW: Balance sheet
                "total_assets": p990.get("total_assets"),
                "total_liabilities": p990.get("total_liabilities"),
            }

        # NEW: BBB Wise Giving Alliance data
        bbb_data = self._get_raw_source(ein, "bbb")
        if bbb_data:
            bbb = bbb_data.get("bbb_profile", {})
            data["bbb_standards"] = {
                "meets_standards": bbb.get("meets_standards"),
                "status_text": bbb.get("status_text"),
                "standards_met_count": bbb.get("standards_met_count", 0),
                "standards_not_met_count": bbb.get("standards_not_met_count", 0),
                "standards_met": bbb.get("standards_met", []),
                "standards_not_met": bbb.get("standards_not_met", []),
                # Category pass/fail
                "governance_pass": bbb.get("governance_pass"),
                "effectiveness_pass": bbb.get("effectiveness_pass"),
                "finances_pass": bbb.get("finances_pass"),
                "solicitations_pass": bbb.get("solicitations_pass"),
                # Governance details
                "board_meetings_per_year": bbb.get("board_meetings_per_year"),
                "conflict_of_interest_policy": bbb.get("conflict_of_interest_policy"),
                "audit_status": bbb.get("audit_status"),
                # Financial ratios
                "program_expense_ratio": bbb.get("program_expense_ratio"),
                "fundraising_expense_ratio": bbb.get("fundraising_expense_ratio"),
                "reserves_ratio": bbb.get("reserves_ratio"),
                # Transparency
                "annual_report_available": bbb.get("annual_report_available"),
                "donor_privacy_policy": bbb.get("donor_privacy_policy"),
                "form_990_on_website": bbb.get("form_990_on_website"),
                # Metadata
                "last_review_date": bbb.get("last_review_date"),
                "review_url": bbb.get("review_url"),
            }

        # NEW: Form 990 Grants data (Schedule I/F)
        grants_data = self._get_raw_source(ein, "form990_grants")
        if grants_data:
            grants = grants_data.get("grants_profile", {})
            total_grants = grants.get("total_grants", 0)
            total_expenses = grants.get("total_expenses") or data.get("form_990", {}).get("total_expenses") or 1
            data["grantmaking"] = {
                "is_grantmaker": total_grants > (total_expenses * 0.1),  # >10% of expenses as grants
                "total_domestic_grants": grants.get("total_domestic_grants"),
                "total_foreign_grants": grants.get("total_foreign_grants"),
                "total_grants": total_grants,
                "domestic_grant_count": grants.get("domestic_grant_count"),
                "foreign_grant_count": grants.get("foreign_grant_count"),
                # Top grants by amount
                "top_domestic_grants": sorted(
                    grants.get("domestic_grants", []),
                    key=lambda x: x.get("amount", 0) if x else 0,
                    reverse=True,
                )[:5],
                "top_foreign_grants": sorted(
                    grants.get("foreign_grants", []),
                    key=lambda x: x.get("amount", 0) if x else 0,
                    reverse=True,
                )[:5],
            }

        # NEW: Charity Navigator scores and beacons
        cn_data = self._get_raw_source(ein, "charity_navigator")
        if cn_data:
            cn = cn_data.get("cn_profile", {})
            cn_is_rated = cn.get("cn_is_rated") is True
            data["cn_ratings"] = {
                # Rating-state flags
                "cn_is_rated": cn_is_rated,
                "cn_has_encompass_award": cn.get("cn_has_encompass_award"),
                # Beacon scores are only trusted when CN marks the profile as fully rated.
                "overall_score": cn.get("overall_score") if cn_is_rated else None,
                "financial_score": cn.get("financial_score") if cn_is_rated else None,
                "accountability_score": cn.get("accountability_score") if cn_is_rated else None,
                "impact_score": cn.get("impact_score") if cn_is_rated else None,
                "culture_score": cn.get("culture_score") if cn_is_rated else None,
                "leadership_score": cn.get("leadership_score") if cn_is_rated else None,
                # Special badges
                "beacons": cn.get("beacons", []) if cn_is_rated else [],
                # Efficiency metrics
                "fundraising_efficiency": cn.get("fundraising_efficiency"),
                "working_capital_ratio": cn.get("working_capital_ratio"),
                # Expense ratios
                "program_expense_ratio": cn.get("program_expense_ratio"),
                "admin_expense_ratio": cn.get("admin_expense_ratio"),
                "fundraising_expense_ratio": cn.get("fundraising_expense_ratio"),
                # Governance
                "independent_board_percentage": cn.get("independent_board_percentage"),
                "board_size": cn.get("board_size"),
                # Leadership compensation
                "ceo_name": cn.get("ceo_name"),
                "ceo_compensation": cn.get("ceo_compensation"),
                # Financial totals
                "total_revenue": cn.get("total_revenue"),
                "total_expenses": cn.get("total_expenses"),
                "fiscal_year": cn.get("fiscal_year"),
            }

        # Get score details — V4 rubric: impact (50pts) + alignment (50pts) with components
        score_details = baseline.get("score_details", {})
        if score_details:
            data["score_details"] = {}

            # V4 dimensions with full component-level detail
            for dim_name in ["impact", "alignment"]:
                dim_data = score_details.get(dim_name, {})
                if dim_data.get("score") is not None:
                    data["score_details"][dim_name] = dim_data

            # Data confidence (feeds credibility narrative)
            if score_details.get("data_confidence"):
                data["score_details"]["data_confidence"] = score_details["data_confidence"]

            # Risk details
            if score_details.get("risks"):
                data["score_details"]["risks"] = score_details["risks"]
            if score_details.get("risk_deduction") is not None:
                data["score_details"]["risk_deduction"] = score_details["risk_deduction"]

            # Zakat details from scoring
            zakat = score_details.get("zakat", {})
            if zakat:
                data["score_details"]["zakat"] = {
                    "charity_claims_zakat": zakat.get("charity_claims_zakat"),
                    "asnaf_category": zakat.get("asnaf_category"),
                    "claim_evidence": zakat.get("claim_evidence"),
                }

        return data

    def _get_raw_source(self, ein: str, source: str) -> Optional[dict]:
        """Get parsed data from a specific raw data source."""
        result = self.raw_data_repo.get_by_source(ein, source)

        if result and result.get("success"):
            return result.get("parsed_json", {})
        return None

    def _build_prompt(
        self,
        baseline: dict,
        charity_bundle: Any,
        citation_registry: Any,
        investment_memo_data: Optional[dict] = None,
    ) -> str:
        """Build the prompt for rich narrative generation."""
        # Load prompt template
        prompt_path = Path(__file__).parent.parent / "llm" / "prompts" / "rich_narrative_v2.txt"
        with open(prompt_path) as f:
            template = f.read()

        # Format charity data
        charity_data = self._format_charity_data(baseline, charity_bundle, investment_memo_data)

        # Format citation sources
        citation_sources = citation_registry.get_sources_for_prompt()

        # Format baseline context
        baseline_context = self._format_baseline_context(baseline)

        # Replace placeholders
        prompt = template.replace("{charity_data}", charity_data)
        prompt = prompt.replace("{citation_sources}", citation_sources)
        prompt = prompt.replace("{baseline_context}", baseline_context)

        return prompt

    def _format_charity_data(
        self, baseline: dict, charity_bundle: Any, investment_memo_data: Optional[dict] = None
    ) -> str:
        """Format charity data for the prompt including investment memo sections."""
        lines = ["## Charity Information\n"]
        baseline_narrative = baseline.get("baseline_narrative") or baseline
        if not isinstance(baseline_narrative, dict):
            baseline_narrative = {}

        # Basic info from baseline
        if baseline_narrative.get("headline"):
            lines.append(f"**Headline (immutable):** {baseline_narrative['headline']}")

        at_glance = baseline_narrative.get("at_a_glance", {})
        if at_glance:
            lines.append("\n**At a Glance (immutable):**")
            for k, v in at_glance.items():
                if v:
                    lines.append(f"- {k}: {v}")

        # AMAL scores from baseline
        amal = baseline_narrative.get("amal_scores", {})
        if not amal:
            amal = {
                "amal_score": baseline.get("amal_score"),
                "wallet_tag": baseline.get("wallet_tag"),
                "confidence_tier": baseline.get("confidence_tier"),
                "impact_tier": baseline.get("impact_tier"),
            }
            if baseline.get("confidence_scores"):
                amal["confidence_scores"] = baseline["confidence_scores"]
            if baseline.get("impact_scores"):
                amal["impact_scores"] = baseline["impact_scores"]
        if amal:
            lines.append(f"\n**AMAL Score (immutable):** {amal.get('amal_score', 'N/A')}/100")
            lines.append(f"**Wallet Tag (immutable):** {amal.get('wallet_tag', 'SADAQAH-ELIGIBLE')}")

        # Zakat guidance
        zakat = baseline_narrative.get("zakat_guidance", {})
        if not zakat:
            zakat = {
                "eligibility": baseline.get("wallet_tag"),
                "classification": baseline.get("zakat_classification"),
            }
        if zakat:
            lines.append(f"\n**Zakat Eligibility (immutable):** {zakat.get('eligibility', 'SADAQAH-ELIGIBLE')}")

        # Strengths from baseline
        strengths = baseline_narrative.get("strengths", [])
        if strengths:
            lines.append("\n**Baseline Strengths (must be covered):**")
            for s in strengths:
                # Handle both string and dict formats
                if isinstance(s, str):
                    lines.append(f"- {s}")
                elif isinstance(s, dict):
                    lines.append(f"- {s.get('point', '')}")

        # Add charity bundle data if available
        if charity_bundle:
            lines.append("\n## Additional Data from Sources\n")

            if charity_bundle.financials:
                fin = charity_bundle.financials
                lines.append("**Financials:**")
                if fin.total_revenue:
                    lines.append(f"- Revenue: ${fin.total_revenue:,.0f}")
                if fin.program_expense_ratio is not None:
                    lines.append(f"- Program Expense Ratio: {fin.program_expense_ratio * 100:.1f}%")
                    # Flag if ratio is suspiciously low
                    if fin.program_expense_ratio < 0.1:
                        lines.append(
                            "  ⚠️ WARNING: Program expense ratio is very low - expense breakdown may be incomplete"
                        )

                # Add MANDATORY VALUES section to prevent hallucination
                lines.append("\n## MANDATORY VALUES (USE EXACTLY - DO NOT CALCULATE OR INVENT)")
                lines.append(
                    "When mentioning these metrics ANYWHERE in the narrative (summary, strengths, explanations),"
                )
                lines.append(
                    "you MUST use the EXACT values below. Do NOT round differently, calculate your own values, or invent numbers.\n"
                )
                if fin.total_revenue:
                    lines.append(f"- Total Revenue: ${fin.total_revenue:,.0f} (use this exact amount)")
                if fin.program_expense_ratio is not None:
                    lines.append(
                        f"- Program Expense Ratio: {fin.program_expense_ratio * 100:.1f}% (use this exact percentage everywhere)"
                    )
                if hasattr(fin, "working_capital_ratio") and fin.working_capital_ratio is not None:
                    lines.append(f"- Working Capital: {fin.working_capital_ratio:.1f} months (use this exact value)")
                if hasattr(fin, "fundraising_expenses") and fin.fundraising_expenses is not None and fin.total_revenue:
                    efficiency = fin.fundraising_expenses / fin.total_revenue
                    lines.append(f"- Fundraising Efficiency: ${efficiency:.2f} per $1 raised (use this exact value)")
                lines.append("\nIf a value is not listed above, do NOT mention that metric at all.\n")

            # Add ZAKAT ELIGIBILITY CONSTRAINT
            wallet_tag = amal.get("wallet_tag", "SADAQAH-ELIGIBLE") if amal else "SADAQAH-ELIGIBLE"
            lines.append("\n## ZAKAT ELIGIBILITY CONSTRAINT (CRITICAL)")
            if wallet_tag == "SADAQAH-ELIGIBLE":
                lines.append("⚠️ This charity is SADAQAH-ELIGIBLE (NOT zakat-eligible).")
                lines.append("DO NOT mention:")
                lines.append("- Zakat eligibility or zakat-eligible status")
                lines.append("- Zakat policies, zakat pathways, or zakat programs")
                lines.append("- Fuqara, masakin, or other zakat recipient categories")
                lines.append("- Any implication that donations qualify as zakat")
                lines.append("\nOnly mention 'sadaqah' or general charitable giving.\n")
            else:
                lines.append(f"✓ This charity is {wallet_tag}.")
                lines.append("You MAY mention zakat eligibility if supported by source data.\n")

            if charity_bundle.ratings:
                lines.append(f"\n**Ratings:** {len(charity_bundle.ratings)} discovered")
                for r in charity_bundle.ratings[:5]:
                    lines.append(f"- {r.source_name}: {r.rating_value}/{r.rating_max}")

            if charity_bundle.evidence:
                lines.append(f"\n**Evidence:** {len(charity_bundle.evidence)} items discovered")

            if charity_bundle.reputation:
                lines.append(f"\n**Reputation:** {len(charity_bundle.reputation)} items discovered")

        # Add investment memo data
        if investment_memo_data:
            lines.append("\n## Investment Memo Data\n")
            lines.append("Use this data to populate the new investment memo sections.\n")

            # Benchmarks
            if investment_memo_data.get("benchmarks"):
                b = investment_memo_data["benchmarks"]
                lines.append("### Peer Benchmarks")
                lines.append(f"- Cause Area: {b.get('cause_area')}")
                lines.append(f"- Peer Count: {b.get('peer_count')}")
                if b.get("peer_program_ratio_median"):
                    lines.append(f"- Peer Program Ratio Median: {b['peer_program_ratio_median'] * 100:.1f}%")
                lines.append(f"- Industry Standard: {b.get('industry_program_ratio', 0.75) * 100:.0f}%")

            # Similar Organizations
            if investment_memo_data.get("similar_orgs"):
                lines.append("\n### Similar Organizations")
                for org in investment_memo_data["similar_orgs"]:
                    lines.append(f"- {org['name']}: {org['differentiator']}")

            # Filing Trends
            has_cagr = False
            if investment_memo_data.get("filing_trends"):
                t = investment_memo_data["filing_trends"]
                lines.append("\n### 3-Year Financial Trends")
                lines.append(f"- Years: {t.get('years')}")
                lines.append(f"- Revenue: {t.get('revenue')}")
                lines.append(f"- Expenses: {t.get('expenses')}")
                lines.append(f"- Net Assets: {t.get('net_assets')}")
                if t.get("revenue_cagr_3yr"):
                    lines.append(f"- 3-Year Revenue CAGR: {t['revenue_cagr_3yr']}%")
                    has_cagr = True

            # Add explicit CAGR constraint
            lines.append("\n## REVENUE GROWTH/CAGR CONSTRAINT (CRITICAL)")
            if has_cagr:
                cagr_val = investment_memo_data["filing_trends"]["revenue_cagr_3yr"]
                lines.append(f"✓ 3-Year Revenue CAGR is available: {cagr_val}%")
                lines.append(f"Use EXACTLY {cagr_val}% when mentioning revenue growth or CAGR.\n")
            else:
                lines.append("⚠️ 3-Year Revenue CAGR is NOT available in source data.")
                lines.append("DO NOT mention:")
                lines.append("- 3-year revenue CAGR or compound annual growth rate")
                lines.append("- Revenue growth percentages")
                lines.append("- Multi-year growth trends")
                lines.append("\nYou may only mention single-year revenue figures if provided.\n")

            # Add OTHER MANDATORY FIELDS constraint
            lines.append("\n## OTHER MANDATORY FIELDS (USE EXACTLY OR NOT AT ALL)")

            # Candid Seal
            candid_seal = None
            if investment_memo_data.get("governance"):
                candid_seal = investment_memo_data["governance"].get("candid_seal")
            if candid_seal:
                lines.append(
                    f"- Candid Seal: {candid_seal.upper()} (use this exact level - not platinum if silver, not gold if bronze)"
                )
            else:
                lines.append("- Candid Seal: NOT AVAILABLE (do not mention Candid seal or transparency level)")

            # Founded Year
            founded_year = None
            if investment_memo_data.get("website"):
                founded_year = investment_memo_data["website"].get("founded_year")
            if founded_year:
                lines.append(f"- Founded Year: {founded_year} (use this exact year)")
            else:
                lines.append("- Founded Year: NOT AVAILABLE (do not mention founding year)")

            # Peer Median
            peer_median = None
            if investment_memo_data.get("benchmarks"):
                peer_median = investment_memo_data["benchmarks"].get("peer_program_ratio_median")
            if peer_median:
                lines.append(
                    f"- Peer Program Ratio Median: {peer_median * 100:.1f}% (use this exact percentage for peer comparison)"
                )
            else:
                lines.append("- Peer Median: NOT AVAILABLE (do not compare to peer group median)")

            # Audited Financials - general constraint since we don't have it in this context
            lines.append(
                "- Audited Financials: Only claim 'audited financial statements' if explicitly stated in source data"
            )
            lines.append(
                "- Beneficiary Counts: Only use specific numbers if provided in source data (do not invent impact statistics)\n"
            )

            # Governance (from Candid)
            if investment_memo_data.get("governance"):
                g = investment_memo_data["governance"]
                lines.append("\n### Governance & Organization")
                if g.get("ceo_name"):
                    lines.append(f"- CEO: {g['ceo_name']}")
                if g.get("board_size"):
                    lines.append(f"- Board Size: {g['board_size']}")
                if g.get("candid_seal"):
                    lines.append(f"- Candid Seal: {g['candid_seal']}")
                if g.get("mission"):
                    lines.append(f"- Mission: {g['mission'][:200]}...")
                if g.get("areas_served"):
                    lines.append(f"- Areas Served: {', '.join(g['areas_served'][:5])}")

            # Website Data
            if investment_memo_data.get("website"):
                w = investment_memo_data["website"]
                lines.append("\n### Website Information")
                if w.get("programs"):
                    lines.append(f"- Programs: {', '.join(w['programs'][:5])}")
                if w.get("geographic_coverage"):
                    lines.append(f"- Geographic Coverage: {', '.join(w['geographic_coverage'][:10])}")
                if w.get("founded_year"):
                    lines.append(f"- Founded: {w['founded_year']}")

                # PDF-extracted outcomes (from Form 990s and Annual Reports)
                if w.get("pdf_outcomes"):
                    lines.append("\n### PDF-Extracted Outcomes")
                    for outcome_data in w["pdf_outcomes"][:3]:  # Limit to 3 most recent
                        source = outcome_data.get("source", "Unknown")
                        fiscal_year = outcome_data.get("fiscal_year", "")
                        source_url = outcome_data.get("source_url", "")
                        outcomes = outcome_data.get("outcomes", {})

                        year_str = f" ({fiscal_year})" if fiscal_year else ""
                        lines.append(f"\n**{source}{year_str}:**")
                        if source_url:
                            lines.append(f"- Source URL: {source_url}")

                        # Key outcomes
                        key_outcomes = outcomes.get("key_outcomes", [])
                        if key_outcomes:
                            lines.append("- Key Outcomes:")
                            for outcome in key_outcomes[:5]:
                                metric = outcome.get("metric", "")
                                value = outcome.get("value", "")
                                if metric and value:
                                    lines.append(f"  - {metric}: {value}")

            # Zakat Data (from discover.py verification)
            if investment_memo_data.get("zakat"):
                z = investment_memo_data["zakat"]
                if z.get("accepts_zakat"):
                    lines.append("\n### Zakat Eligibility")
                    lines.append("- Accepts Zakat: Yes")
                if z.get("zakat_categories_served"):
                    lines.append(f"- Zakat Categories: {', '.join(z['zakat_categories_served'])}")

            # Form 990 Data (enhanced with revenue breakdown)
            if investment_memo_data.get("form_990"):
                f = investment_memo_data["form_990"]
                lines.append("\n### Form 990 Data")
                lines.append(f"- Tax Year: {f.get('tax_year')}")
                if f.get("employees_count"):
                    lines.append(f"- Employees: {f['employees_count']}")
                if f.get("volunteers_count"):
                    lines.append(f"- Volunteers: {f['volunteers_count']}")
                if f.get("compensation_current_officers"):
                    lines.append(f"- Officer Compensation: ${f['compensation_current_officers']:,.0f}")
                # NEW: Revenue breakdown
                rb = f.get("revenue_breakdown", {})
                if any(rb.values()):
                    lines.append("- Revenue Sources:")
                    if rb.get("contributions"):
                        lines.append(f"  - Contributions: ${rb['contributions']:,.0f}")
                    if rb.get("program_service"):
                        lines.append(f"  - Program Service Revenue: ${rb['program_service']:,.0f}")
                    if rb.get("investment_income"):
                        lines.append(f"  - Investment Income: ${rb['investment_income']:,.0f}")
                # NEW: Balance sheet
                if f.get("total_assets"):
                    lines.append(f"- Total Assets: ${f['total_assets']:,.0f}")
                if f.get("total_liabilities"):
                    lines.append(f"- Total Liabilities: ${f['total_liabilities']:,.0f}")

            # NEW: BBB Wise Giving Alliance
            if investment_memo_data.get("bbb_standards"):
                b = investment_memo_data["bbb_standards"]
                lines.append("\n### BBB Wise Giving Alliance Standards")
                if b.get("meets_standards") is not None:
                    status = "Yes" if b["meets_standards"] else "No"
                    lines.append(f"- Meets All 20 Standards: {status}")
                lines.append(f"- Standards Met: {b.get('standards_met_count', 0)}/20")
                if b.get("standards_not_met"):
                    # Limit to first 3 for brevity
                    not_met = b["standards_not_met"][:3]
                    lines.append(f"- Standards Not Met: {', '.join(not_met)}")
                # Category breakdown
                categories = []
                if b.get("governance_pass") is True:
                    categories.append("Governance ✓")
                elif b.get("governance_pass") is False:
                    categories.append("Governance ✗")
                if b.get("effectiveness_pass") is True:
                    categories.append("Effectiveness ✓")
                elif b.get("effectiveness_pass") is False:
                    categories.append("Effectiveness ✗")
                if b.get("finances_pass") is True:
                    categories.append("Finances ✓")
                elif b.get("finances_pass") is False:
                    categories.append("Finances ✗")
                if categories:
                    lines.append(f"- Category Status: {', '.join(categories)}")
                # Governance details
                if b.get("board_meetings_per_year"):
                    lines.append(f"- Board Meetings/Year: {b['board_meetings_per_year']}")
                if b.get("conflict_of_interest_policy") is True:
                    lines.append("- Conflict of Interest Policy: Yes")
                if b.get("audit_status"):
                    lines.append(f"- Audit Status: {b['audit_status']}")
                if b.get("review_url"):
                    lines.append(f"- BBB Review URL: {b['review_url']}")

            # NEW: Grantmaking Activity
            if investment_memo_data.get("grantmaking"):
                g = investment_memo_data["grantmaking"]
                if g.get("is_grantmaker") or g.get("total_grants"):
                    lines.append("\n### Grantmaking Activity")
                    if g.get("total_grants"):
                        lines.append(f"- Total Grants: ${g['total_grants']:,.0f}")
                    if g.get("total_domestic_grants"):
                        lines.append(
                            f"- Domestic Grants: ${g['total_domestic_grants']:,.0f} ({g.get('domestic_grant_count', 0)} recipients)"
                        )
                    if g.get("total_foreign_grants"):
                        lines.append(
                            f"- Foreign Grants: ${g['total_foreign_grants']:,.0f} ({g.get('foreign_grant_count', 0)} recipients)"
                        )
                    # Top recipients
                    if g.get("top_domestic_grants"):
                        lines.append("- Top Domestic Recipients:")
                        for grant in g["top_domestic_grants"][:3]:
                            if grant and grant.get("recipient_name") and grant.get("amount"):
                                lines.append(f"  - {grant['recipient_name']}: ${grant['amount']:,.0f}")
                    if g.get("top_foreign_grants"):
                        lines.append("- Top Foreign Recipients:")
                        for grant in g["top_foreign_grants"][:3]:
                            if grant and grant.get("recipient_name") and grant.get("amount"):
                                region = f" ({grant.get('region')})" if grant.get("region") else ""
                                lines.append(f"  - {grant['recipient_name']}{region}: ${grant['amount']:,.0f}")

            # NEW: Charity Navigator Ratings
            if investment_memo_data.get("cn_ratings"):
                cn = investment_memo_data["cn_ratings"]
                lines.append("\n### Charity Navigator Ratings")
                cn_is_rated = cn.get("cn_is_rated") is True
                if not cn_is_rated:
                    lines.append("- CN profile exists, but this charity is not fully rated (cn_is_rated=false).")
                    lines.append("- Do NOT cite CN overall/accountability/impact scores.")
                if cn.get("overall_score"):
                    lines.append(f"- Overall Score: {cn['overall_score']}/100")
                # Beacon scores
                beacon_scores = []
                if cn.get("impact_score"):
                    beacon_scores.append(f"Impact: {cn['impact_score']}")
                if cn.get("accountability_score"):
                    beacon_scores.append(f"Accountability: {cn['accountability_score']}")
                if cn.get("culture_score"):
                    beacon_scores.append(f"Culture: {cn['culture_score']}")
                if cn.get("leadership_score"):
                    beacon_scores.append(f"Leadership: {cn['leadership_score']}")
                if beacon_scores:
                    lines.append(f"- Beacon Scores: {', '.join(beacon_scores)}")
                # Special badges
                if cn.get("beacons"):
                    lines.append(f"- Special Badges: {', '.join(cn['beacons'])}")
                # Efficiency metrics
                if cn.get("fundraising_efficiency") is not None:
                    # Cost to raise $1
                    lines.append(f"- Fundraising Efficiency: ${cn['fundraising_efficiency']:.2f} to raise $1")
                if cn.get("working_capital_ratio") is not None:
                    lines.append(f"- Working Capital: {cn['working_capital_ratio']:.1f} months of operating expenses")
                # Expense ratios (prefer CN over BBB/ProPublica as it's often more current)
                if cn.get("program_expense_ratio") is not None:
                    per = cn["program_expense_ratio"]
                    lines.append(f"- Program Expense Ratio (CN): {per * 100:.1f}%")
                    # Flag if ratio is suspiciously low - 0% is a red flag
                    if per < 0.1:
                        lines.append(
                            "  ⚠️ WARNING: Program expense ratio is 0% or very low - DO NOT describe as 'efficient' or 'lean'. This indicates incomplete expense breakdown data."
                        )
                # Governance
                if cn.get("independent_board_percentage"):
                    lines.append(f"- Independent Board Members: {cn['independent_board_percentage']}%")
                # CEO compensation
                if cn.get("ceo_name") and cn.get("ceo_compensation"):
                    lines.append(f"- CEO ({cn['ceo_name']}): ${cn['ceo_compensation']:,.0f}")

            # Enhanced: Candid outcome metrics (if has_charting_impact or metrics)
            gov = investment_memo_data.get("governance", {})
            if gov.get("has_charting_impact") or gov.get("metrics"):
                lines.append("\n### Candid Outcome Tracking")
                if gov.get("metrics_count"):
                    lines.append(f"- Outcome Metrics Tracked: {gov['metrics_count']}")
                if gov.get("max_years_tracked"):
                    lines.append(f"- Longest Tracking Period: {gov['max_years_tracked']} years")
                if gov.get("charting_impact_goal"):
                    goal = (
                        gov["charting_impact_goal"][:200] + "..."
                        if len(gov.get("charting_impact_goal", "")) > 200
                        else gov.get("charting_impact_goal", "")
                    )
                    lines.append(f"- Charting Impact Goal: {goal}")
                if gov.get("evaluation_documents"):
                    lines.append(f"- External Evaluation Documents: {len(gov['evaluation_documents'])}")
                if gov.get("feedback_practices"):
                    lines.append(f"- Feedback Practices: {', '.join(gov['feedback_practices'][:3])}")

            # Enhanced: Website beneficiary data
            web = investment_memo_data.get("website", {})
            if web.get("beneficiaries_served") or web.get("cost_metrics") or web.get("has_annual_report"):
                if web.get("beneficiaries_served"):
                    lines.append("\n### Beneficiary Impact")
                    lines.append(f"- Beneficiaries Served: {web['beneficiaries_served']}")
                if web.get("cost_metrics"):
                    cm = web["cost_metrics"]
                    if cm:
                        lines.append("- Cost Metrics:")
                        for metric, value in list(cm.items())[:3]:
                            lines.append(f"  - {metric}: {value}")
                if web.get("has_annual_report"):
                    lines.append("- Annual Report Available: Yes")
                    if web.get("annual_report_url"):
                        lines.append(f"  - URL: {web['annual_report_url']}")
                if web.get("has_impact_report"):
                    lines.append("- Impact Report Available: Yes")

            # Enhanced: Discoveries (external evidence, awards)
            if investment_memo_data.get("discoveries"):
                d = investment_memo_data["discoveries"]
                awards_list = d.get("awards", [])
                if d.get("evidence") or awards_list or d.get("awards_evidence"):
                    lines.append("\n### External Discoveries")
                    if d.get("evidence"):
                        lines.append("- External Evidence Found: Yes")
                    if awards_list and isinstance(awards_list, list):
                        # Extract award names from award objects
                        award_names = []
                        for a in awards_list[:5]:
                            if isinstance(a, dict) and a.get("name"):
                                award_names.append(a["name"])
                            elif isinstance(a, str):
                                award_names.append(a)
                        if award_names:
                            lines.append(f"- Awards: {', '.join(award_names[:3])}")
                    if d.get("awards_evidence"):
                        lines.append(f"- Awards Evidence Summary: {d['awards_evidence'][:200]}...")
                    if d.get("theory_of_change"):
                        lines.append("- Theory of Change Documented: Yes")

            # Score Details — full dimension breakdowns
            score_details = investment_memo_data.get("score_details", {})
            if score_details:
                lines.append("\n### Score Details (V4: Impact/50 + Alignment/50)")

                # V4 dimensions with component-level detail
                for dim_name in ["impact", "alignment"]:
                    dim = score_details.get(dim_name, {})
                    if dim.get("score") is not None:
                        lines.append(f"\n**{dim_name.title()} ({dim['score']}/50):**")
                        if dim.get("rationale"):
                            lines.append(f"- Rationale: {dim['rationale'][:300]}")
                        components = dim.get("components", [])
                        if components:
                            lines.append("- Components:")
                            for comp in components:
                                status = comp.get("status", "unknown")
                                imp_val = comp.get("improvement_value", 0)
                                line = (
                                    f"  - {comp['name']}: {comp.get('scored', 0)}/{comp.get('possible', 0)} ({status})"
                                )
                                if imp_val > 0:
                                    line += f" [+{imp_val} recoverable]"
                                lines.append(line)
                                if comp.get("evidence"):
                                    lines.append(f"    Evidence: {comp['evidence'][:150]}")
                                if comp.get("improvement_suggestion"):
                                    lines.append(f"    Improvement: {comp['improvement_suggestion']}")

                # Data confidence (feeds credibility narrative dimension)
                dc = score_details.get("data_confidence", {})
                if dc:
                    lines.append(f"\n**Data Confidence ({dc.get('badge', 'UNKNOWN')}, {dc.get('overall', 'N/A')}):**")
                    lines.append(
                        f"- Verification: {dc.get('verification_tier', 'N/A')} ({dc.get('verification_value', 'N/A')})"
                    )
                    lines.append(
                        f"- Transparency: {dc.get('transparency_label', 'N/A')} ({dc.get('transparency_value', 'N/A')})"
                    )
                    lines.append(
                        f"- Data Quality: {dc.get('data_quality_label', 'N/A')} ({dc.get('data_quality_value', 'N/A')})"
                    )

                # Risk details
                risks = score_details.get("risks", {})
                risk_deduction = score_details.get("risk_deduction", 0)
                if risk_deduction:
                    lines.append(f"\n**Risk Deduction: -{risk_deduction} pts**")
                    if risks.get("risk_summary"):
                        lines.append(f"- {risks['risk_summary'][:200]}")

            # --- CN RATING CONSTRAINT ---
            cn_score = None
            cn_is_rated = False
            if investment_memo_data.get("cn_ratings"):
                cn_ratings = investment_memo_data["cn_ratings"]
                cn_is_rated = cn_ratings.get("cn_is_rated") is True
                if cn_is_rated:
                    cn_score = cn_ratings.get("overall_score")

            lines.append("\n## CHARITY NAVIGATOR RATING CONSTRAINT (CRITICAL)")
            if cn_is_rated and cn_score:
                lines.append(f"✓ CN Overall Score: {cn_score}/100 — use this exact value.")
            else:
                lines.append("⚠️ This charity is NOT fully rated by Charity Navigator.")
                lines.append("DO NOT mention any Charity Navigator score, rating, or accountability rating")
                lines.append("in the summary, credibility explanation, or any dimension rationale.")
                lines.append("DO NOT claim '100/100', '4-star', or any other CN rating.\n")

            # --- DATA CONFIDENCE CONSTRAINT ---
            dc = score_details.get("data_confidence", {}) if score_details else {}
            dc_overall = dc.get("overall")
            if dc_overall is not None and dc_overall < 0.4:
                lines.append("\n## LOW DATA CONFIDENCE CONSTRAINT (CRITICAL)")
                lines.append(f"⚠️ Data confidence is {dc_overall:.2f} ({dc.get('badge', 'LOW')}).")
                lines.append("The credibility explanation MUST acknowledge limited data availability.")
                lines.append("DO NOT overstate the charity's transparency or accountability.\n")

            # --- ZAKAT CONSTRAINT ---
            zakat_details = score_details.get("zakat", {}) if score_details else {}
            if not zakat_details.get("charity_claims_zakat"):
                lines.append("\n## ZAKAT CONSTRAINT")
                lines.append("⚠️ This charity does NOT claim zakat eligibility.")
                lines.append("The alignment explanation must NOT say 'zakat-eligible', 'zakat-compliant',")
                lines.append("or 'verified zakat eligibility'.\n")

        return "\n".join(lines)

    def _format_baseline_context(self, baseline: dict) -> str:
        """Format baseline narrative context."""
        lines = ["## Baseline Narrative Context\n"]
        baseline_narrative = baseline.get("baseline_narrative") or baseline
        if not isinstance(baseline_narrative, dict):
            baseline_narrative = {}

        # Summary
        if baseline_narrative.get("summary"):
            lines.append(f"**Summary:** {baseline_narrative['summary'][:500]}...")

        # Improvement areas (aligned field name: areas_for_improvement)
        improvements = baseline_narrative.get("areas_for_improvement", [])
        if improvements:
            lines.append("\n**Areas for Improvement:**")
            for imp in improvements:
                if isinstance(imp, dict):
                    lines.append(f"- {imp.get('area', '')}: {imp.get('context', '')}")
                else:
                    lines.append(f"- {imp}")

        # V4 score details: impact/alignment with rationale
        score_details = baseline.get("score_details") or baseline_narrative.get("score_details", {})
        if score_details:
            lines.append("\n**Score Breakdown (V4):**")
            amal_score = baseline.get("amal_score")
            if amal_score is None:
                amal_score = (baseline_narrative.get("amal_scores") or {}).get("amal_score")
            if amal_score is not None:
                lines.append(f"- Overall GMG Score: {amal_score}/100")
            for dim_name in ["impact", "alignment"]:
                dim = score_details.get(dim_name, {})
                if dim.get("score") is not None:
                    lines.append(f"- {dim_name.title()}: {dim['score']}/50")
                    if dim.get("rationale"):
                        lines.append(f"  Rationale: {dim['rationale'][:200]}")

        return "\n".join(lines)

    def _inject_immutable_fields(self, rich_content: dict, baseline_narrative: dict, evaluation: dict) -> dict:
        """Inject immutable fields from baseline into rich narrative.

        Args:
            rich_content: The LLM-generated rich narrative
            baseline_narrative: The baseline_narrative dict from evaluation
            evaluation: The full evaluation record (has amal_score, wallet_tag, etc.)
        """
        ein = evaluation.get("charity_ein")

        # Headline from baseline_narrative
        if baseline_narrative.get("headline"):
            rich_content["headline"] = baseline_narrative["headline"]

        # AMAL scores from evaluation level
        amal_scores = {
            "amal_score": evaluation.get("amal_score"),
            "wallet_tag": evaluation.get("wallet_tag"),
            "confidence_tier": evaluation.get("confidence_tier"),
            "impact_tier": evaluation.get("impact_tier"),
        }
        # Add dimension scores if available
        if evaluation.get("confidence_scores"):
            amal_scores["confidence_scores"] = evaluation["confidence_scores"]
        if evaluation.get("impact_scores"):
            amal_scores["impact_scores"] = evaluation["impact_scores"]
        rich_content["amal_scores"] = amal_scores

        # Zakat guidance from evaluation level
        rich_content["zakat_guidance"] = {
            "eligibility": evaluation.get("wallet_tag", "SADAQAH-ELIGIBLE"),
            "classification": evaluation.get("zakat_classification"),
        }

        # Score rationale always comes from baseline (authoritative source)
        # Injected post-sanitize in generate() to avoid sanitizer stripping it
        if baseline_narrative.get("amal_score_rationale"):
            rich_content["amal_score_rationale"] = baseline_narrative["amal_score_rationale"]

        # At a glance from baseline_narrative if present
        if baseline_narrative.get("at_a_glance"):
            rich_content["at_a_glance"] = baseline_narrative["at_a_glance"]

        # Inject BBB review_url from raw data (LLM doesn't output URLs)
        if rich_content.get("bbb_assessment") and ein:
            bbb_data = self._get_raw_source(ein, "bbb")
            if bbb_data:
                bbb_profile = bbb_data.get("bbb_profile", {})
                if bbb_profile.get("review_url"):
                    rich_content["bbb_assessment"]["review_url"] = bbb_profile["review_url"]

        # Inject verified metrics from source data (LLM often hallucinates these)
        if ein:
            rich_content = self._inject_verified_metrics(ein, rich_content)

        return rich_content

    def _inject_verified_metrics(self, ein: str, rich_content: dict) -> dict:
        """
        Inject verified metrics from source data into rich narrative.

        The LLM often hallucinates or confuses financial metrics. This fixes
        those errors by overwriting with actual source values for:
        - CN overall score (vs beacon scores)
        - Program expense ratio
        - Transparency/accountability score
        - Working capital months

        Args:
            ein: Charity EIN
            rich_content: The LLM-generated rich narrative

        Returns:
            rich_content with corrected metrics
        """
        # Get actual data from charity_data
        charity_data = self.charity_data_repo.get(ein)
        if not charity_data:
            return rich_content

        source_attr = charity_data.get("source_attribution", {})

        # Helper to extract value from source attribution
        def get_source_value(key: str) -> Optional[float]:
            attr = source_attr.get(key, {})
            val = attr.get("value") if isinstance(attr, dict) else attr
            return float(val) if val is not None else None

        # Ensure financial_deep_dive exists
        if "financial_deep_dive" not in rich_content:
            rich_content["financial_deep_dive"] = {}
        fd = rich_content["financial_deep_dive"]

        # Track corrections for logging
        corrections = []
        # Save original LLM values before correction (for text replacement later)
        original_llm_values: dict[str, float | None] = {
            "program_expense_ratio": fd.get("program_expense_ratio"),
            "cn_financial_score": fd.get("cn_financial_score") or fd.get("cn_overall_score"),
            "working_capital_months": fd.get("working_capital_months") or fd.get("reserves_months"),
        }

        # 1. CN Overall Score
        actual_cn = get_source_value("charity_navigator_score")
        if actual_cn is not None:
            llm_cn = fd.get("cn_financial_score") or fd.get("cn_overall_score")
            if llm_cn is not None and abs(float(llm_cn) - actual_cn) > 1:
                corrections.append(f"CN score: {llm_cn} -> {actual_cn}")
            fd["cn_overall_score"] = actual_cn

        # 2. Program Expense Ratio
        # Check source_attribution first, then CN data
        actual_per = get_source_value("program_expense_ratio")
        if actual_per is None:
            # Fall back to raw CN data
            try:
                cn_raw = self.raw_data_repo.get_by_source(ein, "charity_navigator")
                if cn_raw:
                    cn = cn_raw.get("parsed_json", {}).get("cn_profile", {})
                    cn_per = cn.get("program_expense_ratio")
                    if cn_per is not None:
                        actual_per = cn_per / 100 if cn_per > 1 else cn_per  # Normalize to 0-1
            except Exception:
                pass
        if actual_per is not None:
            llm_per = fd.get("program_expense_ratio")
            if llm_per is not None and abs(float(llm_per) - actual_per) > 0.02:
                corrections.append(f"Program expense ratio: {llm_per:.1%} -> {actual_per:.1%}")
            fd["program_expense_ratio"] = actual_per
        elif fd.get("program_expense_ratio") is not None:
            # Source is NULL but LLM fabricated a value - remove it
            corrections.append(f"Program expense ratio: {fd['program_expense_ratio']} -> NULL (no source)")
            fd["program_expense_ratio"] = None

        # 2b. Admin and Fundraising Ratios - NULL out if no source data
        # These are often fabricated by LLM when expense breakdown is missing
        if charity_data.get("admin_expenses") is None and fd.get("admin_ratio") is not None:
            corrections.append(f"Admin ratio: {fd['admin_ratio']} -> NULL (no source)")
            fd["admin_ratio"] = None
        if charity_data.get("fundraising_expenses") is None and fd.get("fundraising_ratio") is not None:
            # Exception: fundraising_ratio=0 is valid if CN explicitly reports $0 fundraising
            cn_fundraising = None
            try:
                cn_raw = self.raw_data_repo.get_by_source(ein, "charity_navigator")
                if cn_raw:
                    cn = cn_raw.get("parsed_json", {}).get("cn_profile", {})
                    cn_fundraising = cn.get("fundraising_expenses")
            except Exception:
                pass
            if cn_fundraising != 0:
                corrections.append(f"Fundraising ratio: {fd['fundraising_ratio']} -> NULL (no source)")
                fd["fundraising_ratio"] = None

        # 3. Transparency Score (Candid)
        actual_trans = get_source_value("transparency_score")
        if actual_trans is not None:
            llm_trans = fd.get("transparency_score")
            if llm_trans is not None and abs(float(llm_trans) - actual_trans) > 1:
                corrections.append(f"Transparency score: {llm_trans} -> {actual_trans}")
            fd["transparency_score"] = actual_trans

        # 4. Working Capital Months
        actual_wc = get_source_value("working_capital_months")
        if actual_wc is not None:
            llm_wc = fd.get("working_capital_months")
            if llm_wc is not None and abs(float(llm_wc) - actual_wc) > 0.5:
                corrections.append(f"Working capital: {llm_wc} -> {actual_wc} months")
            fd["working_capital_months"] = actual_wc

        # Log corrections if any
        if corrections:
            logger.info(f"{ein}: Fixing metrics - {', '.join(corrections)}")

        # 5. Fix wrong values in narrative text (pass original LLM values so we
        # can detect what the LLM generated before JSON fields were corrected above)
        rich_content = self._fix_narrative_values(rich_content, source_attr, original_llm_values)

        return rich_content

    def _fix_narrative_values(
        self,
        rich_content: dict,
        source_attr: dict,
        original_llm_values: dict[str, float | None] | None = None,
    ) -> dict:
        """Fix incorrect metric values embedded in narrative text."""

        # Helper to get source value
        def get_val(key: str) -> Optional[float]:
            attr = source_attr.get(key, {})
            val = attr.get("value") if isinstance(attr, dict) else attr
            return float(val) if val is not None else None

        fd = rich_content.get("financial_deep_dive", {})
        original_llm_values = original_llm_values or {}
        replacements = []

        # CN score replacement
        actual_cn = get_val("charity_navigator_score")
        llm_cn = original_llm_values.get("cn_financial_score") or fd.get("cn_financial_score")
        if actual_cn and llm_cn and abs(float(llm_cn) - actual_cn) > 1:
            wrong = int(llm_cn)
            correct = int(actual_cn)
            replacements.extend(
                [
                    (rf"\b{wrong}/100\b", f"{correct}/100"),
                    (rf"score of {wrong}\b", f"score of {correct}"),
                    (rf"score: {wrong}\b", f"score: {correct}"),
                    (rf"rating of {wrong}\b", f"rating of {correct}"),
                ]
            )

        # Program expense ratio replacement (e.g., "83.6%" -> "80.3%")
        actual_per = get_val("program_expense_ratio")
        # Use original LLM value (before JSON correction) so we know what to search for in text
        original_llm_per = original_llm_values.get("program_expense_ratio")
        llm_per = original_llm_per if original_llm_per is not None else fd.get("program_expense_ratio")
        if actual_per is None:
            # No source data - remove any hallucinated percentage claims
            # Match patterns like "85% program expense ratio", "185% of its expenses", etc.
            # NOTE: LLM sometimes outputs "1XX%" instead of "XX%" so we match up to 3 digits
            replacements.extend(
                [
                    (r"\d{1,3}(\.\d)?% program expense ratio", "program expense data unavailable"),
                    (r"an? \d{1,3}(\.\d)?% program", "program"),
                    (r"with \d{1,3}(\.\d)?% of (funds|revenue|budget|its expenses)", "with"),
                    (r", with \d{1,3}(\.\d)?% of its expenses dedicated", ", dedicating funds"),
                ]
            )
        elif actual_per is not None:
            # We have actual data - replace ANY wrong percentage near program expense context
            correct_pct = actual_per * 100 if actual_per < 1 else actual_per

            # First, replace the specific wrong value from financial_deep_dive if known
            if llm_per and abs(float(llm_per) - actual_per) > 0.02:
                wrong_pct = float(llm_per) * 100 if float(llm_per) < 1 else float(llm_per)
                replacements.append((rf"{wrong_pct:.1f}%", f"{correct_pct:.1f}%"))

            # FIX: LLM sometimes outputs "1XX%" instead of "XX%" (e.g., "190.2%" instead of "90.2%")
            # If correct is between 35-100%, also replace the "1XX" variant
            if 35 <= correct_pct <= 100:
                wrong_1xx = 100 + correct_pct
                replacements.append((rf"{wrong_1xx:.1f}%", f"{correct_pct:.1f}%"))

            # Then, find and fix any other percentages in program expense context
            # that differ from actual value by >2 percentage points
            # Pattern: any percentage (1-3 digits) followed by program-related words
            def replace_wrong_pct(match):
                found_pct = float(match.group(1))
                # Handle the "1XX%" bug: if found is >100 and (found - 100) is close to correct, fix it
                if found_pct > 100 and abs(found_pct - 100 - correct_pct) < 2:
                    return f"{correct_pct:.1f}%{match.group(2)}"
                if abs(found_pct - correct_pct) > 2:
                    return f"{correct_pct:.1f}%{match.group(2)}"
                return match.group(0)

            # Add pattern-based replacement for program expense contexts (match 1-3 digits)
            replacements.append(
                (
                    r"(\d{1,3}(?:\.\d)?)%( (?:program expense|of expenses|of its expenses|dedicated to program|directed to programs|toward programs))",
                    replace_wrong_pct,
                )
            )

        # Working capital months replacement (e.g., "20.0 months" -> "18.0 months")
        actual_wc = get_val("working_capital_months")
        original_llm_wc = original_llm_values.get("working_capital_months")
        llm_wc = original_llm_wc if original_llm_wc is not None else fd.get("working_capital_months")
        if actual_wc is not None and llm_wc is not None and abs(float(llm_wc) - actual_wc) > 0.5:
            wrong_wc = f"{float(llm_wc):.1f}"
            correct_wc = f"{actual_wc:.1f}"
            # Replace "20.0 months" with "18.0 months" in working capital contexts
            replacements.append((rf"{wrong_wc} months", f"{correct_wc} months"))
            # Also fix "Working Capital: 20.0 months" citation claims
            replacements.append((rf"Working Capital: {wrong_wc}", f"Working Capital: {correct_wc}"))

        if not replacements:
            return rich_content

        # Recursively apply replacements
        def apply_replacements(obj: Any) -> Any:
            if isinstance(obj, str):
                result = obj
                for pattern, replacement in replacements:
                    result = re.sub(pattern, replacement, result)
                return result
            elif isinstance(obj, dict):
                return {k: apply_replacements(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [apply_replacements(item) for item in obj]
            return obj

        return apply_replacements(rich_content)

    def _validate_external_evaluations(self, ein: str, rich_content: dict, investment_memo_data: dict) -> dict:
        """
        Validate external_evaluations claims against actual data sources.

        Removes fabricated claims that can't be verified (e.g., "Charity Navigator
        Impact Score" when the charity isn't actually rated by CN).

        Args:
            ein: Charity EIN
            rich_content: The LLM-generated rich narrative
            investment_memo_data: Data from all sources used in generation

        Returns:
            rich_content with unverifiable external_evaluations removed
        """
        impact_evidence = rich_content.get("impact_evidence", {})
        if not isinstance(impact_evidence, dict):
            impact_evidence = {}
        external_evals = impact_evidence.get("external_evaluations", [])

        if not external_evals:
            return rich_content

        # Build verification map from actual data sources
        if not isinstance(investment_memo_data, dict):
            investment_memo_data = {}
        cn_data = investment_memo_data.get("cn_ratings", {})
        if not isinstance(cn_data, dict):
            cn_data = {}
        bbb_data = investment_memo_data.get("bbb_standards", {})
        if not isinstance(bbb_data, dict):
            bbb_data = {}
        governance = investment_memo_data.get("governance", {})  # Candid data
        if not isinstance(governance, dict):
            governance = {}
        discoveries = investment_memo_data.get("discoveries", {})
        if not isinstance(discoveries, dict):
            discoveries = {}
        discoveries_evidence = discoveries.get("evaluations")
        if not isinstance(discoveries_evidence, dict):
            discoveries_evidence = {}

        # What we can actually verify
        cn_is_rated = cn_data.get("cn_is_rated") is True
        has_cn_rating = cn_is_rated and bool(cn_data.get("overall_score"))
        has_cn_impact = cn_is_rated and bool(cn_data.get("impact_score"))
        has_bbb_review = bbb_data.get("meets_standards") is not None
        has_candid_metrics = bool(governance.get("metrics")) or bool(governance.get("evaluation_documents"))
        has_candid_charting = bool(governance.get("has_charting_impact"))
        has_givewell = discoveries_evidence.get("givewell_top_charity", False)

        # Keywords that require verification
        verification_rules = {
            "charity navigator": has_cn_rating,
            "cn ": has_cn_rating,  # Abbreviation
            "charity navigator impact": has_cn_impact,
            "impact score": has_cn_impact,
            "bbb": has_bbb_review,
            "wise giving": has_bbb_review,
            "givewell": has_givewell,
            "give well": has_givewell,
            "candid": has_candid_metrics or has_candid_charting,
            "guidestar": has_candid_metrics or has_candid_charting,
            "charting impact": has_candid_charting,
        }

        validated_evals = []
        removed_evals = []

        for eval_claim in external_evals:
            if not isinstance(eval_claim, str):
                continue

            claim_lower = eval_claim.lower()
            is_fabricated = False

            # Check each verification rule
            for keyword, has_data in verification_rules.items():
                if keyword in claim_lower and not has_data:
                    is_fabricated = True
                    removed_evals.append(eval_claim)
                    break

            if not is_fabricated:
                validated_evals.append(eval_claim)

        # Log removed fabrications
        if removed_evals:
            logger.warning(f"EIN {ein}: Removed {len(removed_evals)} fabricated external_evaluations: {removed_evals}")

        # Update the rich_content
        if "impact_evidence" in rich_content:
            rich_content["impact_evidence"]["external_evaluations"] = validated_evals

        return rich_content

    def _store_results(self, ein: str, rich_content: dict, validation_result: Any) -> None:
        """Store rich narrative and citations in database."""
        # Store rich narrative in evaluations table
        try:
            self.eval_repo.upsert(
                {
                    "charity_ein": ein,
                    "rich_narrative": rich_content,
                }
            )
        except Exception as e:
            logger.error(f"Failed to store rich narrative: {e}")

        # Store citations
        citations = rich_content.get("all_citations", [])
        if citations:
            citation_records = []
            for c in citations:
                if not isinstance(c, dict):
                    continue
                citation_records.append(
                    {
                        "id": f"{ein}_rich_{c.get('id', '')}",
                        "charity_ein": ein,
                        "narrative_type": "rich",
                        "claim": c.get("claim", ""),
                        "source_name": c.get("source_name", ""),
                        "source_url": c.get("source_url"),
                        "source_type": c.get("source_type", "website"),
                        "quote": c.get("quote"),
                        "confidence": c.get("confidence", 0.8),
                    }
                )

            try:
                self.citation_repo.upsert_batch(citation_records)
            except Exception as e:
                logger.error(f"Failed to store citations: {e}")


def generate_rich_narrative(ein: str, force: bool = False) -> Optional[dict]:
    """Convenience function to generate rich narrative."""
    generator = RichNarrativeGenerator()
    return generator.generate(ein, force=force)
