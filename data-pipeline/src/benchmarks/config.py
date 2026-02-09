"""
Benchmark configuration - Fixed charity and model sets for reproducible comparisons.

These sets are intentionally static to enable apples-to-apples comparison
across runs over time. Changes should be rare and documented.
"""

# =============================================================================
# BENCHMARK CHARITIES
# =============================================================================
# 10 diverse charities selected for coverage across:
# - Cause areas (humanitarian, education, health, advocacy, environment, etc.)
# - Organization size (large flagships to small niche orgs)
# - Data quality (high CN ratings to sparse data)
# - Muslim vs non-Muslim (for counterfactual scoring validation)

BENCHMARK_CHARITIES = [
    # Large, well-documented orgs
    ("Islamic Relief USA", "95-4453134"),           # Flagship Muslim humanitarian, 100% CN
    ("Against Malaria Foundation", "20-3069841"),   # GiveWell gold standard, 91% CN
    ("Developments in Literacy", "33-0843213"),     # Pakistan education, 100% CN
    ("International Rescue Committee", "13-5660870"),  # Large non-Muslim, accepts zakat

    # Medium orgs with good data
    ("Zaytuna College", "33-0720978"),              # Islamic seminary, 89% CN
    ("Yaqeen Institute", "81-2822877"),             # Islamic research

    # Smaller/niche orgs (stress test for sparse data)
    ("Khalil Center", "47-1313957"),                # Mental health, smaller
    ("Green Muslims", "47-1986437"),                # Environment, niche
    ("Muhsen", "47-3187591"),                       # Disability services, small
    ("Link Outside", "83-1171525"),                 # Prison reentry, very niche
]

# Just the EINs for easy iteration
BENCHMARK_EINS = [ein for _, ein in BENCHMARK_CHARITIES]


# =============================================================================
# BENCHMARK MODELS
# =============================================================================
# 7 models across 3 providers for comprehensive comparison
# Mix of premium and budget options to evaluate quality vs cost tradeoffs

BENCHMARK_MODELS = [
    # Google Gemini
    "gemini-3-flash-preview",   # Current production (best value)
    "gemini-3-pro-preview",     # Premium Gemini
    "gemini-2.5-flash",         # Previous gen mid-tier
    "gemini-2.0-flash",         # Budget Gemini
    "gemini-2.5-flash-lite",    # Cheapest Gemini

    # Anthropic Claude
    "claude-sonnet-4-5",        # Premium Claude
    "claude-haiku-4-5",         # Budget Claude

    # OpenAI
    "gpt-5.2",                  # Current OpenAI flagship
    "gpt-5-mini",               # OpenAI mid-tier
    "gpt-5-nano",               # OpenAI budget
    "gpt-4o-mini",              # Legacy OpenAI budget
]

# Model metadata for reporting
MODEL_INFO = {
    "gemini-3-flash-preview": {"provider": "Google", "tier": "mid", "cost_in": 0.50, "cost_out": 3.00},
    "gemini-3-pro-preview": {"provider": "Google", "tier": "premium", "cost_in": 2.00, "cost_out": 12.00},
    "gemini-2.5-flash": {"provider": "Google", "tier": "mid", "cost_in": 0.15, "cost_out": 0.60},
    "gemini-2.0-flash": {"provider": "Google", "tier": "budget", "cost_in": 0.10, "cost_out": 0.40},
    "gemini-2.5-flash-lite": {"provider": "Google", "tier": "budget", "cost_in": 0.10, "cost_out": 0.40},
    "claude-sonnet-4-5": {"provider": "Anthropic", "tier": "premium", "cost_in": 3.00, "cost_out": 15.00},
    "claude-haiku-4-5": {"provider": "Anthropic", "tier": "mid", "cost_in": 1.00, "cost_out": 5.00},
    "gpt-5.2": {"provider": "OpenAI", "tier": "premium", "cost_in": 1.75, "cost_out": 14.00},
    "gpt-5-mini": {"provider": "OpenAI", "tier": "mid", "cost_in": 0.25, "cost_out": 2.00},
    "gpt-5-nano": {"provider": "OpenAI", "tier": "budget", "cost_in": 0.05, "cost_out": 0.40},
    "gpt-4o-mini": {"provider": "OpenAI", "tier": "budget", "cost_in": 0.15, "cost_out": 0.60},
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_benchmark_charities() -> list[tuple[str, str]]:
    """Get list of (name, ein) tuples for benchmark charities."""
    return BENCHMARK_CHARITIES.copy()


def get_benchmark_eins() -> list[str]:
    """Get list of EINs for benchmark charities."""
    return BENCHMARK_EINS.copy()


def get_benchmark_models() -> list[str]:
    """Get list of model names for benchmarking."""
    return BENCHMARK_MODELS.copy()


def estimate_full_benchmark_cost() -> dict:
    """Estimate cost to run full benchmark (all models × all charities).

    Assumes ~2000 input tokens and ~1000 output tokens per charity.
    """
    input_tokens_per_charity = 2000
    output_tokens_per_charity = 1000
    num_charities = len(BENCHMARK_CHARITIES)

    costs = {}
    total = 0.0

    for model in BENCHMARK_MODELS:
        info = MODEL_INFO[model]
        input_cost = (input_tokens_per_charity * num_charities / 1_000_000) * info["cost_in"]
        output_cost = (output_tokens_per_charity * num_charities / 1_000_000) * info["cost_out"]
        model_cost = input_cost + output_cost
        costs[model] = round(model_cost, 4)
        total += model_cost

    return {
        "per_model": costs,
        "total": round(total, 4),
        "charities": num_charities,
        "models": len(BENCHMARK_MODELS),
    }
