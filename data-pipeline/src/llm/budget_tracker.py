"""
Per-run LLM budget enforcement.

A thread-safe, process-wide cost accumulator with a hard cap. The check
happens BEFORE each LLM call in LLMClient.generate() — NOT via LiteLLM
callbacks, which swallow exceptions raised inside them (see
docs/infrastructure-upgrade-plan.md, Phase 3 implementation notes).

Usage:
    from src.llm.budget_tracker import set_budget, check_budget, add_cost

    set_budget(5.0)        # streaming_runner --budget 5.0
    check_budget()         # raises BudgetExceededError once spent >= limit
    add_cost(resp.cost_usd)

With no budget set (the default), check_budget() is a no-op.
"""

import threading
from typing import Optional


class BudgetExceededError(Exception):
    """Raised before an LLM call once the run's budget cap is reached."""


_lock = threading.Lock()
_limit_usd: Optional[float] = None
_spent_usd: float = 0.0


def set_budget(limit_usd: Optional[float]) -> None:
    """Set (or clear, with None) the budget cap and reset spend."""
    global _limit_usd, _spent_usd
    with _lock:
        _limit_usd = limit_usd
        _spent_usd = 0.0


def add_cost(cost_usd: float) -> None:
    """Accumulate the cost of a completed LLM call."""
    global _spent_usd
    if not cost_usd:
        return
    with _lock:
        _spent_usd += cost_usd


def check_budget() -> None:
    """Raise BudgetExceededError if the cap is set and already reached."""
    with _lock:
        if _limit_usd is not None and _spent_usd >= _limit_usd:
            raise BudgetExceededError(
                f"LLM budget exhausted: ${_spent_usd:.4f} spent of "
                f"${_limit_usd:.2f} cap. Increase --budget or narrow the run."
            )


def get_spent() -> float:
    with _lock:
        return _spent_usd


def get_limit() -> Optional[float]:
    with _lock:
        return _limit_usd
