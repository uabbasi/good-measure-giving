"""
Benchmarks - Model and prompt evaluation framework.

Captures LLM evaluation outputs for comparison across:
- Different models (Gemini 3 Flash vs Claude Sonnet 4)
- Different prompt versions (baseline_v2.0.0 vs v2.1.0)

Results are stored in results/ and checked into git for diffing.

Usage:
    # Run full benchmark suite
    uv run python -m src.benchmarks suite

    # Estimate cost
    uv run python -m src.benchmarks cost

    # Run single model
    uv run python -m src.benchmarks run --model gemini-3-flash-preview
"""

from .config import (
    BENCHMARK_CHARITIES,
    BENCHMARK_EINS,
    BENCHMARK_MODELS,
    MODEL_INFO,
)
from .runner import BenchmarkRunner
from .storage import BenchmarkRun, BenchmarkStorage

__all__ = [
    "BenchmarkRunner",
    "BenchmarkStorage",
    "BenchmarkRun",
    "BENCHMARK_CHARITIES",
    "BENCHMARK_EINS",
    "BENCHMARK_MODELS",
    "MODEL_INFO",
]
