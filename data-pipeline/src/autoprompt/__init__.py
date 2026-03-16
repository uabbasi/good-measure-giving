"""
Autoprompt - Autonomous prompt optimization via eval-driven iteration.

Applies the autoresearch pattern (modify → evaluate → keep/revert) to prompt
optimization. Uses composite metrics (readability, AI-voice, specificity, citations)
as the fast inner loop, with pairwise LLM comparison for periodic confirmation.

Usage:
    uv run python autoprompt.py --models gemini-3-pro-preview,claude-sonnet-4-5 --iterations 20
"""

from .evaluator import AutopromptEvaluator, PairwiseEvaluator
from .optimizer import PromptOptimizer

__all__ = [
    "AutopromptEvaluator",
    "PairwiseEvaluator",
    "PromptOptimizer",
]
