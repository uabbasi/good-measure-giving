"""
Prompt mutation engine — proposes prompt modifications based on metric feedback.

The optimizer builds a meta-prompt with:
- Current prompt text
- Per-metric breakdown from evaluate_quality()
- Which metrics are weakest → focus optimization there
- Last N iteration history
- Constraints (keep JSON schema, target 8th grade reading, etc.)
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from ..llm.llm_client import LLMClient

logger = logging.getLogger(__name__)


@dataclass
class IterationFeedback:
    """Feedback from one iteration, per model."""

    iteration: int
    kept: bool
    changelog: str = ""
    # Per-model scores: {model_name: {metric: value}}
    model_scores: dict[str, dict[str, float]] = field(default_factory=dict)
    # Per-model deltas from baseline: {model_name: {metric: delta}}
    model_deltas: dict[str, dict[str, float]] = field(default_factory=dict)
    pairwise_win_rate: Optional[float] = None
    # Judge reasoning from pairwise comparison
    pairwise_reasons: list[str] = field(default_factory=list)


class PromptOptimizer:
    """Proposes prompt modifications based on metric feedback."""

    def __init__(
        self,
        optimizer_model: str = "claude-sonnet-4-5",
        target_prompt_name: str = "rich_narrative_v2",
    ):
        self.client = LLMClient(model=optimizer_model)
        self.target_prompt_name = target_prompt_name
        self.history: list[IterationFeedback] = []

    def propose(
        self,
        current_prompt: str,
        baseline_scores: dict[str, dict[str, float]],
        current_scores: dict[str, dict[str, float]],
        iteration: int,
    ) -> str:
        """Propose a modified prompt based on metric feedback.

        Args:
            current_prompt: The current prompt text
            baseline_scores: {model: {metric: score}} from baseline
            current_scores: {model: {metric: score}} from current best
            iteration: Current iteration number

        Returns:
            Modified prompt text
        """
        meta_prompt = self._build_meta_prompt(
            current_prompt, baseline_scores, current_scores, iteration
        )

        response = self.client.generate(
            prompt=meta_prompt,
            system_prompt=self._system_prompt(),
            temperature=0.4,
            max_tokens=4000,
        )

        # Extract the prompt from the response (between markers)
        candidate = self._extract_prompt(response.text, current_prompt)
        return candidate

    def record_iteration(self, feedback: IterationFeedback):
        """Record feedback from an iteration for history context."""
        self.history.append(feedback)
        # Keep last 5
        if len(self.history) > 5:
            self.history = self.history[-5:]

    def _system_prompt(self) -> str:
        return """You are a prompt engineer optimizing LLM prompts for charity narrative generation.

## Iteration Strategy (CRITICAL)

You are making ONE SMALL, TARGETED change per iteration. This is an autoresearch-style
optimization loop: small edits → measure → keep/revert → repeat.

DO NOT rewrite the prompt from scratch. Instead:
1. Look at the weakest metric(s) in the scores below
2. Identify ONE specific instruction in the prompt that could address it
3. Add, modify, or sharpen that ONE instruction
4. Leave everything else UNCHANGED

Examples of good single changes:
- Add a "DO NOT reveal internal scores" instruction to fix score leakage
- Add an example of a good tradeoff sentence to improve nuance
- Tighten a vague instruction like "be specific" into "every sentence must have a number"
- Add a banned phrase to the AI-isms list
- Add a self-check bullet point for a specific failure mode

Examples of BAD changes (too much at once):
- Rewriting the entire output format section
- Adding 5 new sections simultaneously
- Restructuring the prompt from scratch

## Metrics you're optimizing:
- Specificity (25%): Concrete numbers, dates, percentages. No vague language.
- Citation quality (20%): [N] markers matching definitions, real sources.
- Readability (15%): 8th-10th grade Flesch-Kincaid. Simple sentences.
- Human voice (15%): No AI-isms. No internal score leakage.
- Structural compliance (15%): Valid JSON, required fields.
- Completeness (10%): Substantive content in all fields.

## Constraints (never violate):
1. The output JSON schema must remain unchanged
2. Citation format must be maintained
3. Must work across multiple LLM providers (Gemini, Claude, GPT)
4. Target readability: 8th-10th grade level
5. Write like a human journalist — direct, specific, opinionated
6. NEVER reveal internal assessment scores (no "AMAL score 81/100", "impact 37/50").
   Real financial data like "$907 cost per beneficiary" or "100/100 CN rating" IS fine.

## Response format:
1. State what ONE thing you're changing and why (1-2 sentences).
2. Return the COMPLETE modified prompt between these EXACT markers:

---PROMPT_START---
[complete prompt with your targeted change applied]
---PROMPT_END---

CRITICAL: Include the full prompt, not just the diff. The markers must appear exactly as shown."""

    def _build_meta_prompt(
        self,
        current_prompt: str,
        baseline_scores: dict[str, dict[str, float]],
        current_scores: dict[str, dict[str, float]],
        iteration: int,
    ) -> str:
        parts = [f"## Iteration {iteration}\n"]

        # Per-model score breakdown
        parts.append("## Current Scores by Model\n")
        for model, scores in current_scores.items():
            baseline = baseline_scores.get(model, {})
            parts.append(f"### {model}")
            for metric, value in sorted(scores.items()):
                base_val = baseline.get(metric, 0)
                delta = value - base_val
                arrow = "↑" if delta > 0 else "↓" if delta < 0 else "="
                parts.append(f"  {metric}: {value:.1f} ({arrow}{abs(delta):.1f} from baseline)")
            parts.append("")

        # Identify weakest metrics across all models
        all_metrics: dict[str, list[float]] = {}
        for scores in current_scores.values():
            for metric, value in scores.items():
                if metric != "overall_score":
                    all_metrics.setdefault(metric, []).append(value)

        if all_metrics:
            avg_by_metric = {m: sum(v) / len(v) for m, v in all_metrics.items()}
            weakest = sorted(avg_by_metric.items(), key=lambda x: x[1])[:3]
            parts.append("## Weakest Metrics (focus here)")
            for metric, avg in weakest:
                parts.append(f"  {metric}: avg {avg:.1f}")
            parts.append("")

        # History
        if self.history:
            parts.append("## Recent History")
            for fb in self.history[-5:]:
                status = "KEPT" if fb.kept else "REVERTED"
                pw = f", pairwise={fb.pairwise_win_rate:.2f}" if fb.pairwise_win_rate is not None else ""
                parts.append(f"  iter {fb.iteration}: {status}{pw} — {fb.changelog}")
            parts.append("")

        # Pairwise judge feedback — the most important signal
        all_reasons = []
        for fb in self.history:
            all_reasons.extend(fb.pairwise_reasons)
        if all_reasons:
            parts.append("## Pairwise Judge Feedback (CRITICAL — address these)")
            parts.append("A human-simulating judge compared your optimized narratives against")
            parts.append("the original. These are the reasons it rejected your changes:")
            parts.append("")
            for reason in all_reasons[-6:]:  # last 6 reasons
                parts.append(f"  - {reason}")
            parts.append("")
            parts.append("Your next modification MUST address the judge's concerns above.")
            parts.append("The judge values nuance, differentiation, and correctness over")
            parts.append("raw readability scores. Don't just simplify — add insight.")
            parts.append("")

        # Current prompt
        parts.append("## Current Prompt (modify this)\n")
        parts.append(current_prompt)

        return "\n".join(parts)

    def _extract_prompt(self, response_text: str, fallback: str) -> str:
        """Extract the modified prompt from optimizer response."""
        import re

        # Try exact markers first
        match = re.search(
            r"---PROMPT_START---\s*\n(.*?)\n\s*---PROMPT_END---",
            response_text,
            re.DOTALL,
        )
        if match:
            return match.group(1).strip()

        # Try relaxed markers (some models add extra formatting)
        for start_pat, end_pat in [
            (r"PROMPT_START", r"PROMPT_END"),
            (r"<prompt>", r"</prompt>"),
            (r"\[PROMPT\]", r"\[/PROMPT\]"),
        ]:
            match = re.search(
                rf"{start_pat}[-—]*\s*\n(.*?)\n\s*[-—]*{end_pat}",
                response_text,
                re.DOTALL,
            )
            if match:
                return match.group(1).strip()

        # Fallback: find the largest code block (likely the prompt)
        code_blocks = re.findall(r"```(?:\w+)?\s*\n(.*?)\n```", response_text, re.DOTALL)
        if code_blocks:
            largest = max(code_blocks, key=len)
            if len(largest) > len(fallback) * 0.3:
                return largest.strip()

        # Last resort: if response is long enough and starts with prompt-like content,
        # strip the preamble (text before first # heading) and use the rest
        lines = response_text.strip().split("\n")
        prompt_start = None
        for i, line in enumerate(lines):
            if line.startswith("# ") and i > 0:
                prompt_start = i
                break
        if prompt_start is not None:
            candidate = "\n".join(lines[prompt_start:]).strip()
            if len(candidate) > len(fallback) * 0.3:
                return candidate

        logger.warning("Could not extract prompt from optimizer response, using fallback")
        return fallback
