"""
Eval orchestration — generates narratives and scores them across multiple models.

AutopromptEvaluator: wraps BenchmarkRunner pattern for multi-model evaluation
PairwiseEvaluator: LLM head-to-head comparison for periodic confirmation
"""

import json
import logging
import random
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from ..benchmarks.metrics import QualityMetrics, evaluate_quality
from ..db import CharityDataRepository, CharityRepository, RawDataRepository
from ..llm.llm_client import LLMClient, LLMResponse
from ..parsers.charity_metrics_aggregator import CharityMetrics, CharityMetricsAggregator
from ..scorers.v2_scorers import AmalScorerV2
from ..services.citation_service import CitationService

logger = logging.getLogger(__name__)


@dataclass
class CharityNarrative:
    """A generated narrative for one charity."""

    ein: str
    name: str
    narrative: Optional[dict] = None
    quality: Optional[QualityMetrics] = None
    cost_usd: float = 0.0
    error: Optional[str] = None


@dataclass
class ModelEvalResult:
    """Evaluation results for one model across all charities."""

    model: str
    charities: list[CharityNarrative] = field(default_factory=list)
    total_cost_usd: float = 0.0

    @property
    def avg_scores(self) -> dict[str, float]:
        """Average scores across all successfully evaluated charities."""
        scored = [c for c in self.charities if c.quality is not None]
        if not scored:
            return {}
        n = len(scored)
        return {
            "overall_score": sum(c.quality.overall_score for c in scored) / n,
            "structural_score": sum(c.quality.structural_score for c in scored) / n,
            "citation_score": sum(c.quality.citation_score for c in scored) / n,
            "specificity_score": sum(c.quality.specificity_score for c in scored) / n,
            "completeness_score": sum(c.quality.completeness_score for c in scored) / n,
            "readability_score": sum(c.quality.readability_score for c in scored) / n,
            "human_voice_score": sum(c.quality.human_voice_score for c in scored) / n,
        }


class AutopromptEvaluator:
    """Generates narratives and evaluates quality across multiple models."""

    # Grade ranges by prompt type
    GRADE_RANGES: dict[str, tuple[float, float]] = {
        "baseline_narrative": (8.0, 10.0),   # Public-facing, anyone can read
        "rich_narrative_v2": (8.0, 12.0),    # Engaged donors doing due diligence
        "rich_strategic_narrative": (8.0, 12.0),
    }

    def __init__(
        self,
        eval_eins: list[str],
        grade_range: Optional[tuple[float, float]] = None,
    ):
        self._eval_eins = eval_eins
        self._grade_range = grade_range
        self._charity_repo = CharityRepository()
        self._raw_repo = RawDataRepository()
        self._data_repo = CharityDataRepository()
        self._scorer = AmalScorerV2()
        # Cache prepped charity data so we don't re-fetch every iteration
        self._charity_cache: dict[str, dict[str, Any]] = {}

    def evaluate(
        self,
        prompt_content: str,
        models: list[str],
        temperature: float = 0.3,
    ) -> dict[str, ModelEvalResult]:
        """Evaluate a prompt across multiple models.

        Args:
            prompt_content: The prompt text to use
            models: List of model names to evaluate
            temperature: Generation temperature

        Returns:
            {model_name: ModelEvalResult}
        """
        results: dict[str, ModelEvalResult] = {}

        for model in models:
            logger.info(f"  Evaluating with {model}...")
            client = LLMClient(model=model)
            model_result = ModelEvalResult(model=model)

            for ein in self._eval_eins:
                charity_data = self._get_charity_data(ein)
                if charity_data is None:
                    model_result.charities.append(
                        CharityNarrative(ein=ein, name=ein, error="No data")
                    )
                    continue

                narrative, cost, error = self._generate_narrative(
                    charity_data, client, prompt_content, temperature
                )

                quality = None
                if narrative is not None:
                    quality = evaluate_quality(narrative, grade_range=self._grade_range)

                model_result.charities.append(
                    CharityNarrative(
                        ein=ein,
                        name=charity_data["name"],
                        narrative=narrative,
                        quality=quality,
                        cost_usd=cost,
                        error=error,
                    )
                )
                model_result.total_cost_usd += cost

            results[model] = model_result
            logger.info(
                f"    {model}: avg={model_result.avg_scores.get('overall_score', 0):.1f}, "
                f"cost=${model_result.total_cost_usd:.4f}"
            )

        return results

    def _get_charity_data(self, ein: str) -> Optional[dict[str, Any]]:
        """Get prepped charity data (cached)."""
        if ein in self._charity_cache:
            return self._charity_cache[ein]

        charity = self._charity_repo.get(ein)
        if not charity:
            return None

        charity_data = self._data_repo.get(ein)
        raw_data = self._raw_repo.get_for_charity(ein)
        raw_sources: dict[str, dict] = {}
        for rd in raw_data:
            if rd.get("success") and rd.get("parsed_json"):
                raw_sources[rd["source"]] = rd["parsed_json"]

        if not raw_sources:
            return None

        # Build metrics
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

        evaluation_track = charity_data.get("evaluation_track", "STANDARD") if charity_data else "STANDARD"
        scores = self._scorer.evaluate(metrics, evaluation_track=evaluation_track)

        # Build citation registry
        citation_service = CitationService()
        citation_registry = citation_service.build_registry(ein)
        sources_list = citation_registry.get_sources_for_prompt()
        num_sources = len(citation_registry.sources)

        result = {
            "name": charity.get("name", ein),
            "metrics": metrics,
            "scores": scores,
            "sources_list": sources_list,
            "num_sources": num_sources,
        }
        self._charity_cache[ein] = result
        return result

    def _generate_narrative(
        self,
        charity_data: dict[str, Any],
        client: LLMClient,
        prompt_content: str,
        temperature: float,
    ) -> tuple[Optional[dict], float, Optional[str]]:
        """Generate a narrative for one charity using the given prompt."""
        metrics = charity_data["metrics"]
        scores = charity_data["scores"]
        sources_list = charity_data["sources_list"]
        num_sources = charity_data["num_sources"]

        # Format values
        revenue_str = f"${metrics.total_revenue:,.0f}" if metrics.total_revenue else "N/A"
        ratio_str = f"{metrics.program_expense_ratio:.1%}" if metrics.program_expense_ratio else "N/A"
        cn_score_str = f"{metrics.cn_overall_score}/100" if metrics.cn_overall_score else "N/A"
        programs_str = ", ".join(metrics.programs[:3]) if metrics.programs else "Not available"

        # Build the user prompt with charity data injected
        user_prompt = f"""{prompt_content}

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
- Impact: {scores.impact.score}/50 ({scores.impact.rationale})
- Alignment: {scores.alignment.score}/50 ({scores.alignment.rationale})
- Credibility: {scores.credibility.score}/33 ({scores.credibility.verification_tier} verification)
- Risk Deduction: {scores.risk_deduction}

## Available Sources for Citations (EXACTLY {num_sources} sources)
{sources_list}"""

        cost = 0.0
        try:
            response: LLMResponse = client.generate(
                prompt=user_prompt,
                max_tokens=2000,
                temperature=temperature,
                json_mode=True,
            )
            cost = response.cost_usd

            if not response.text or not response.text.strip():
                return None, cost, "Empty response"

            # Parse JSON
            text = response.text.strip()
            if text.startswith("```"):
                match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
                if match:
                    text = match.group(1).strip()

            narrative = json.loads(text)
            return narrative, cost, None

        except json.JSONDecodeError as e:
            return None, cost, f"Invalid JSON: {e}"
        except Exception as e:
            return None, cost, f"LLM error: {e}"


class PairwiseEvaluator:
    """Head-to-head LLM comparison for periodic confirmation."""

    def __init__(
        self,
        judge_model: str = "claude-sonnet-4-5",
        eval_eins: Optional[list[str]] = None,
    ):
        self.client = LLMClient(model=judge_model)
        self._eval_eins = eval_eins or []

    def compare(
        self,
        baseline_narratives: dict[str, dict[str, dict]],
        candidate_narratives: dict[str, dict[str, dict]],
    ) -> tuple[dict[str, float], list[str]]:
        """Run pairwise comparison across all models.

        Args:
            baseline_narratives: {model: {ein: narrative_dict}}
            candidate_narratives: {model: {ein: narrative_dict}}

        Returns:
            ({model: win_rate}, [judge_reasons])
        """
        win_rates: dict[str, float] = {}
        all_reasons: list[str] = []

        for model in baseline_narratives:
            if model not in candidate_narratives:
                continue

            wins = 0
            total = 0

            eins = list(baseline_narratives[model].keys())

            for ein in eins:
                baseline = baseline_narratives[model].get(ein)
                candidate = candidate_narratives[model].get(ein)

                if baseline is None or candidate is None:
                    continue

                winner, reason = self._judge_pair(baseline, candidate)
                total += 1
                if winner == "B":
                    wins += 1
                elif winner == "TIE":
                    wins += 0.5
                if reason:
                    all_reasons.append(f"[{model}] {winner}: {reason}")

            win_rates[model] = wins / total if total > 0 else 0.5
            logger.info(f"  Pairwise {model}: {wins}/{total} wins ({win_rates[model]:.2f})")

        return win_rates, all_reasons

    def _judge_pair(self, narrative_a: dict, narrative_b: dict) -> tuple[str, str]:
        """Judge which narrative is better. Returns ('A'|'B'|'TIE', reason).

        Uses a rubric-based evaluation across 5 dimensions.
        Randomizes A/B ordering to prevent position bias.
        """
        # Randomize order
        if random.random() < 0.5:
            first, second = narrative_a, narrative_b
            first_is_baseline = True
        else:
            first, second = narrative_b, narrative_a
            first_is_baseline = False

        prompt = f"""You are evaluating two charity narratives for a Muslim donor audience.
Score each narrative on these 6 dimensions (1-5 scale each):

1. **Nuance**: Does it go beyond surface-level? Does it explain WHY numbers matter,
   not just state them? Does it acknowledge tradeoffs or limitations?
   (1=generic platitudes, 5=insight a donor couldn't get from the charity's website)

2. **Correctness**: Are claims properly sourced? Do citations match real claims?
   Are numbers used accurately (not out of context)?
   (1=unsourced or misleading, 5=every claim cited and contextualized)

3. **Differentiation**: Would a donor learn what makes THIS charity different from
   similar ones? Does it say something specific, not interchangeable boilerplate?
   (1=could describe any charity, 5=clearly about this specific organization)

4. **Readability**: Can a non-expert understand it? Short sentences, clear structure,
   no jargon? Does it flow naturally?
   (1=academic/dense, 5=clear to any adult reader)

5. **Voice**: Does it sound like a journalist or analyst, not a chatbot? No filler
   phrases, no hedging, willing to state opinions?
   (1=obvious AI, 5=sounds fully human)

6. **Score discipline**: Does the narrative avoid revealing INTERNAL ASSESSMENT scores
   like "81/100 AMAL score" or "impact score of 37/50"? These are internal rating
   numbers that donors shouldn't see. The narrative should describe quality
   qualitatively ("strong financial health", "limited reach") instead.
   NOTE: Real financial data IS fine and encouraged — things like "$907 cost per
   beneficiary", "80% program ratio", "$147M revenue", "100/100 Charity Navigator
   rating" are actual data points, NOT score leaks.
   (1=leaks internal scores, 5=uses real data without exposing internal ratings)

## Narrative A
{json.dumps(first, indent=2)[:3000]}

## Narrative B
{json.dumps(second, indent=2)[:3000]}

Score each dimension for both narratives, then pick a winner.
Reply in this EXACT format:
A: nuance=N correctness=N differentiation=N readability=N voice=N score_discipline=N
B: nuance=N correctness=N differentiation=N readability=N voice=N score_discipline=N
WINNER: A or B or TIE
REASON: one sentence why"""

        try:
            response = self.client.generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=200,
            )
            text = response.text.strip()

            # Parse winner
            winner_match = re.search(r"WINNER:\s*(A|B|TIE)", text, re.IGNORECASE)
            if winner_match:
                raw = winner_match.group(1).upper()
            else:
                # Fallback: count dimension scores
                a_scores = re.findall(r"^A:.*?(\d).*?(\d).*?(\d).*?(\d).*?(\d).*?(\d)", text, re.MULTILINE)
                b_scores = re.findall(r"^B:.*?(\d).*?(\d).*?(\d).*?(\d).*?(\d).*?(\d)", text, re.MULTILINE)
                if a_scores and b_scores:
                    a_total = sum(int(x) for x in a_scores[0])
                    b_total = sum(int(x) for x in b_scores[0])
                    if a_total > b_total:
                        raw = "A"
                    elif b_total > a_total:
                        raw = "B"
                    else:
                        raw = "TIE"
                else:
                    raw = "TIE"

            # Extract reasoning
            reason_match = re.search(r"REASON:\s*(.+)", text, re.IGNORECASE)
            reason = reason_match.group(1).strip() if reason_match else ""
            logger.info(f"    Judge: {raw} — {reason}")

            # Un-randomize: if we swapped, flip the answer
            if not first_is_baseline:
                if raw == "A":
                    return "B", reason
                elif raw == "B":
                    return "A", reason
            return raw, reason

        except Exception as e:
            logger.warning(f"Pairwise judge error: {e}")
            return "TIE", str(e)
