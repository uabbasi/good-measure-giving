"""
Benchmark runner - Run evaluations with configurable model/prompt for comparison.

Captures full outputs, costs, and latencies for A/B testing models and prompts.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ..db import (
    CharityDataRepository,
    CharityRepository,
    RawDataRepository,
)
from ..llm.llm_client import LLMClient, LLMResponse
from ..llm.prompt_loader import load_prompt
from ..parsers.charity_metrics_aggregator import CharityMetrics, CharityMetricsAggregator
from ..scorers.v2_scorers import AmalScorerV2
from ..services.citation_service import CitationService
from .metrics import evaluate_quality
from .storage import BenchmarkRun, BenchmarkStorage, CharityEvaluation

logger = logging.getLogger(__name__)


def _repair_json_brackets(text: str) -> str:
    """Attempt to repair JSON with mismatched brackets.

    Some models (like Haiku) confuse ] and } when closing objects.
    This tries to fix that by tracking what was opened.
    """
    # Track bracket stack to identify mismatches
    stack = []
    chars = list(text)

    for i, char in enumerate(chars):
        if char == '{':
            stack.append(('{', i))
        elif char == '[':
            stack.append(('[', i))
        elif char == '}':
            if stack and stack[-1][0] == '{':
                stack.pop()
            elif stack and stack[-1][0] == '[':
                # Mismatch: ] was expected but } found - this is fine
                stack.pop()
        elif char == ']':
            if stack and stack[-1][0] == '[':
                stack.pop()
            elif stack and stack[-1][0] == '{':
                # Mismatch: } was expected but ] found - fix it!
                chars[i] = '}'
                stack.pop()

    return ''.join(chars)


@dataclass
class RunConfig:
    """Configuration for a benchmark run."""

    model: str
    prompt_name: str = "baseline_narrative"
    prompt_version: Optional[str] = None  # None = use current version
    max_charities: Optional[int] = None  # None = all
    notes: str = ""


class BenchmarkRunner:
    """Run evaluations with configurable model/prompt for benchmarking."""

    def __init__(self, storage: Optional[BenchmarkStorage] = None):
        """Initialize the runner.

        Args:
            storage: Storage backend for saving results. Uses default if not provided.
        """
        self.storage = storage or BenchmarkStorage()
        self._charity_repo = CharityRepository()
        self._raw_repo = RawDataRepository()
        self._data_repo = CharityDataRepository()

    def run(
        self,
        eins: list[str],
        config: RunConfig,
    ) -> BenchmarkRun:
        """Run benchmark evaluation on a list of charities.

        Args:
            eins: List of charity EINs to evaluate
            config: Run configuration (model, prompt, etc.)

        Returns:
            BenchmarkRun with all results
        """
        # Limit charities if specified
        if config.max_charities:
            eins = eins[: config.max_charities]

        # Load prompt and get version info
        prompt_info = load_prompt(config.prompt_name)
        prompt_version = config.prompt_version or prompt_info.version
        prompt_hash = prompt_info.content_hash

        # Create LLM client with specified model
        llm_client = LLMClient(model=config.model)

        # Create scorer
        scorer = AmalScorerV2()

        # Generate run ID
        run_id = self.storage.generate_run_id(
            model=config.model,
            prompt_name=config.prompt_name,
            prompt_version=prompt_version,
        )

        logger.info(f"Starting benchmark run: {run_id}")
        logger.info(f"Model: {config.model}, Prompt: {config.prompt_name}@{prompt_version}")
        logger.info(f"Charities: {len(eins)}")

        # Initialize run
        run = BenchmarkRun(
            run_id=run_id,
            model=config.model,
            prompt_name=config.prompt_name,
            prompt_version=prompt_version,
            prompt_hash=prompt_hash,
            timestamp=datetime.now().isoformat(),
            charities_count=len(eins),
            notes=config.notes,
        )

        # Evaluate each charity
        for i, ein in enumerate(eins):
            logger.info(f"[{i + 1}/{len(eins)}] Evaluating {ein}...")

            start_time = time.time()
            try:
                result = self._evaluate_charity(ein, llm_client, scorer)
                latency = time.time() - start_time

                if result["success"]:
                    eval_data = result["evaluation"]
                    llm_cost = result.get("llm_cost_usd", 0.0)
                    narrative = eval_data.get("baseline_narrative")

                    # Compute LLM quality metrics
                    quality = evaluate_quality(narrative)

                    charity_eval = CharityEvaluation(
                        ein=ein,
                        name=result.get("name", ein),
                        amal_score=eval_data.get("amal_score"),
                        wallet_tag=eval_data.get("wallet_tag"),
                        confidence_tier=eval_data.get("confidence_tier"),
                        impact_tier=eval_data.get("impact_tier"),
                        score_details=eval_data.get("score_details"),
                        baseline_narrative=narrative,
                        llm_cost_usd=llm_cost,
                        latency_seconds=latency,
                        quality_metrics=quality.to_dict(),
                    )
                    run.evaluations.append(charity_eval)
                    run.charities_succeeded += 1
                    run.total_cost_usd += llm_cost
                    run.total_latency_seconds += latency
                    logger.info(f"  ✓ Score: {eval_data.get('amal_score')}, Quality: {quality.overall_score:.0f}, Cost: ${llm_cost:.4f}")
                else:
                    # Failed evaluation
                    charity_eval = CharityEvaluation(
                        ein=ein,
                        name=result.get("name", ein),
                        amal_score=None,
                        wallet_tag=None,
                        confidence_tier=None,
                        impact_tier=None,
                        score_details=None,
                        baseline_narrative=None,
                        llm_cost_usd=0.0,
                        latency_seconds=latency,
                        error=result.get("error", "Unknown error"),
                    )
                    run.evaluations.append(charity_eval)
                    run.charities_failed += 1
                    logger.warning(f"  ✗ Error: {result.get('error')}")

            except Exception as e:
                latency = time.time() - start_time
                logger.error(f"  ✗ Exception: {e}")
                charity_eval = CharityEvaluation(
                    ein=ein,
                    name=ein,
                    amal_score=None,
                    wallet_tag=None,
                    confidence_tier=None,
                    impact_tier=None,
                    score_details=None,
                    baseline_narrative=None,
                    llm_cost_usd=0.0,
                    latency_seconds=latency,
                    error=str(e),
                )
                run.evaluations.append(charity_eval)
                run.charities_failed += 1

        # Save results
        save_path = self.storage.save(run)
        logger.info(f"Results saved to: {save_path}")
        logger.info(f"Summary: {run.charities_succeeded}/{run.charities_count} succeeded, ${run.total_cost_usd:.4f} total cost")

        return run

    def _evaluate_charity(
        self,
        ein: str,
        llm_client: LLMClient,
        scorer: AmalScorerV2,
    ) -> dict[str, Any]:
        """Evaluate a single charity.

        Returns dict with:
        - success: bool
        - evaluation: dict (if success)
        - name: str
        - llm_cost_usd: float
        - error: str (if failed)
        """
        result: dict[str, Any] = {"ein": ein, "success": False}

        # Get charity
        charity = self._charity_repo.get(ein)
        if not charity:
            result["error"] = "Charity not found"
            return result

        result["name"] = charity.get("name", ein)

        # Get synthesized data
        charity_data = self._data_repo.get(ein)

        # Get raw data
        raw_data = self._raw_repo.get_for_charity(ein)
        raw_sources: dict[str, dict] = {}
        for rd in raw_data:
            if rd.get("success") and rd.get("parsed_json"):
                raw_sources[rd["source"]] = rd["parsed_json"]

        if not raw_sources:
            result["error"] = "No raw data found"
            return result

        # Build CharityMetrics
        metrics = self._build_metrics(ein, charity_data, raw_sources)

        # Validate minimum data
        has_identity = bool(metrics.mission) or (metrics.programs and len(metrics.programs) > 0)
        has_financials = metrics.total_revenue is not None or metrics.program_expense_ratio is not None

        if not has_identity and not has_financials:
            result["error"] = "Insufficient data (no identity or financials)"
            return result

        # Get evaluation track
        evaluation_track = charity_data.get("evaluation_track", "STANDARD") if charity_data else "STANDARD"

        # Compute scores (deterministic)
        scores = scorer.evaluate(metrics, evaluation_track=evaluation_track)

        # Generate narrative (this is what we're benchmarking)
        narrative, llm_cost, error = self._generate_narrative(
            metrics, scores, llm_client, ein
        )

        result["llm_cost_usd"] = llm_cost

        if narrative is None:
            result["error"] = error or "Narrative generation failed"
            return result

        # Build evaluation dict (not full Evaluation object to avoid circular imports)
        result["evaluation"] = {
            "amal_score": scores.amal_score,
            "wallet_tag": scores.wallet_tag,
            "confidence_tier": scores.trust.verification_tier,
            "impact_tier": self._map_impact_tier(scores.effectiveness.cost_efficiency),
            "score_details": {
                "trust": scores.trust.model_dump(),
                "evidence": scores.evidence.model_dump(),
                "effectiveness": scores.effectiveness.model_dump(),
                "fit": scores.fit.model_dump(),
                "zakat": scores.zakat_bonus.model_dump(),
                "risks": scores.case_against.model_dump(),
                "risk_deduction": scores.risk_deduction,
            },
            "baseline_narrative": narrative,
        }
        result["success"] = True
        return result

    def _build_metrics(
        self,
        ein: str,
        charity_data: Optional[dict],
        raw_sources: dict[str, dict],
    ) -> CharityMetrics:
        """Build CharityMetrics from data sources."""
        cn_data = raw_sources.get("charity_navigator")
        pp_data = raw_sources.get("propublica")
        candid_data = raw_sources.get("candid")
        website_data = raw_sources.get("website")
        givewell_data = raw_sources.get("givewell")
        discovered_data = raw_sources.get("discovered")

        metrics = CharityMetricsAggregator.aggregate(
            charity_id=0,
            ein=ein,
            cn_profile=cn_data.get("cn_profile", cn_data) if cn_data else None,
            propublica_990=pp_data.get("propublica_990", pp_data) if pp_data else None,
            candid_profile=candid_data.get("candid_profile", candid_data) if candid_data else None,
            website_profile=website_data.get("website_profile", website_data) if website_data else None,
            givewell_profile=givewell_data.get("givewell_profile", givewell_data) if givewell_data else None,
            discovered_profile=discovered_data.get("discovered_profile", discovered_data) if discovered_data else None,
        )

        if charity_data:
            metrics.is_muslim_focused = charity_data.get("muslim_charity_fit") == "high"

        return metrics

    def _generate_narrative(
        self,
        metrics: CharityMetrics,
        scores: Any,
        llm_client: LLMClient,
        ein: str,
    ) -> tuple[Optional[dict], float, Optional[str]]:
        """Generate narrative and track cost.

        Returns:
            (narrative, cost_usd, error)
        """
        import json
        import re

        total_cost = 0.0

        # Build citation registry
        citation_service = CitationService()
        citation_registry = citation_service.build_registry(ein)
        sources_list = citation_registry.get_sources_for_prompt()
        num_sources = len(citation_registry.sources)

        # Format values
        revenue_str = f"${metrics.total_revenue:,.0f}" if metrics.total_revenue else "N/A"
        ratio_str = f"{metrics.program_expense_ratio:.1%}" if metrics.program_expense_ratio else "N/A"
        cn_score_str = f"{metrics.cn_overall_score}/100" if metrics.cn_overall_score else "N/A"
        programs_str = ', '.join(metrics.programs[:3]) if metrics.programs else 'Not available'

        # Build prompt (simplified version for benchmarking)
        prompt = f"""Generate a baseline narrative for this charity with Wikipedia-style inline citations.

## Charity Information
- Name: {metrics.name}
- EIN: {metrics.ein}
- Mission: {metrics.mission or 'Not available'}
- Programs: {programs_str}

## Financial Data
- Total Revenue: {revenue_str}
- Program Expense Ratio: {ratio_str}
- Charity Navigator Score: {cn_score_str}

## Pre-computed Scores
- AMAL Score: {scores.amal_score}/100
- Wallet Tag: {scores.wallet_tag}
- Trust: {scores.trust.score}/25 ({scores.trust.verification_tier} verification)
- Evidence: {scores.evidence.score}/25 (Grade {scores.evidence.evidence_grade.value})
- Effectiveness: {scores.effectiveness.score}/25 ({scores.effectiveness.cost_efficiency} efficiency)
- Fit: {scores.fit.score}/25 ({scores.fit.counterfactual} counterfactual)

## Available Sources for Citations (EXACTLY {num_sources} sources)
{sources_list}

## Output Format
Return ONLY a valid JSON object:

{{
  "headline": "One compelling sentence about the charity",
  "summary": "2-3 sentences with citations like [1] and [2]",
  "strengths": ["strength 1", "strength 2"],
  "areas_for_improvement": ["area 1"],
  "amal_score_rationale": "1-2 sentences explaining the overall score",
  "dimension_explanations": {{
    "trust": "Explain trust score",
    "evidence": "Explain evidence score",
    "effectiveness": "Explain effectiveness score",
    "fit": "Explain fit score"
  }},
  "all_citations": [
    {{"id": "[1]", "source_name": "Source Name", "source_url": "https://...", "claim": "What this source supports"}}
  ]
}}"""

        try:
            response: LLMResponse = llm_client.generate(
                prompt=prompt,
                max_tokens=1500,
                temperature=0.3,
                json_mode=True,
            )
            total_cost = response.cost_usd

            if not response.text or not response.text.strip():
                return None, total_cost, "LLM returned empty response"

            # Parse JSON (strip markdown if present)
            text = response.text.strip()
            if text.startswith("```"):
                match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
                if match:
                    text = match.group(1).strip()

            narrative = json.loads(text)
            return narrative, total_cost, None

        except json.JSONDecodeError as e:
            # Try to repair common bracket confusion (] vs } for objects)
            # This is a known issue with smaller models like Haiku
            try:
                repaired = _repair_json_brackets(text)
                narrative = json.loads(repaired)
                return narrative, total_cost, None
            except (json.JSONDecodeError, Exception):
                pass  # Repair failed, return original error
            return None, total_cost, f"Invalid JSON: {e}"
        except Exception as e:
            return None, total_cost, f"LLM error: {e}"

    @staticmethod
    def _map_impact_tier(cost_efficiency: str) -> str:
        """Map effectiveness cost_efficiency to impact_tier."""
        mapping = {
            "EXCEPTIONAL": "HIGH",
            "ABOVE_AVERAGE": "ABOVE_AVERAGE",
            "AVERAGE": "AVERAGE",
            "BELOW_AVERAGE": "BELOW_AVERAGE",
            "POOR": "BELOW_AVERAGE",
            "UNKNOWN": "BELOW_AVERAGE",
        }
        return mapping.get(cost_efficiency, "BELOW_AVERAGE")


def load_pilot_charities(file_path: str | Path) -> list[str]:
    """Load charities from pilot_charities.txt format."""
    from src.utils.charity_loader import load_pilot_eins

    return load_pilot_eins(str(file_path))
