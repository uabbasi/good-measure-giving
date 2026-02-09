"""
Unified LLM client using LiteLLM for robust multi-provider support.

Task-based model selection with automatic fallback on transient errors.
Tracks (model_version, prompt_version, db_snapshot_version) for reproducibility.

Usage:
    from src.llm.llm_client import LLMClient, LLMTask

    # Use task-based selection (recommended)
    client = LLMClient(task=LLMTask.NARRATIVE_GENERATION)
    response = client.generate("Write a narrative for this charity...")

    # Use specific model
    client = LLMClient(model=MODEL_GEMINI_3_FLASH)
    response = client.generate("Extract data from this page...")
"""

import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import litellm
from litellm import completion, completion_cost

# Suppress verbose LiteLLM logging
litellm.set_verbose = False
litellm.suppress_debug_info = True

logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


# =============================================================================
# MODEL CONSTANTS - Fully specified model versions
# =============================================================================

# Google Gemini models
MODEL_GEMINI_3_PRO = "gemini-3-pro-preview"
MODEL_GEMINI_3_FLASH = "gemini-3-flash-preview"
MODEL_GEMINI_25_PRO = "gemini-2.5-pro"
MODEL_GEMINI_25_FLASH = "gemini-2.5-flash"
MODEL_GEMINI_20_FLASH = "gemini-2.0-flash"
MODEL_GEMINI_25_FLASH_LITE = "gemini-2.5-flash-lite"

# Anthropic Claude models
MODEL_CLAUDE_SONNET_45 = "claude-sonnet-4-5"
MODEL_CLAUDE_HAIKU_45 = "claude-haiku-4-5"

# OpenAI models
MODEL_GPT52 = "gpt-5.2"
MODEL_GPT5_MINI = "gpt-5-mini"
MODEL_GPT5_NANO = "gpt-5-nano"
MODEL_GPT4O_MINI = "gpt-4o-mini"

# =============================================================================
# MODEL REGISTRY - Costs and LiteLLM mapping (Nov 2025 pricing)
# =============================================================================

MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    # Google Gemini
    MODEL_GEMINI_3_PRO: {
        "litellm_name": "gemini/gemini-3-pro-preview",
        "provider": "google",
        "cost_per_1m_input": 2.00,  # ≤200k tokens
        "cost_per_1m_input_large": 4.00,  # >200k tokens
        "cost_per_1m_input_cached": 0.20,  # ≤200k cached
        "cost_per_1m_input_cached_large": 0.40,  # >200k cached
        "cost_per_1m_output": 12.00,  # ≤200k tokens
        "cost_per_1m_output_large": 18.00,  # >200k tokens
        "context_window": 1_000_000,
        "supports_json_mode": True,
    },
    MODEL_GEMINI_3_FLASH: {
        "litellm_name": "gemini/gemini-3-flash-preview",
        "provider": "google",
        "cost_per_1m_input": 0.50,
        "cost_per_1m_input_cached": 0.05,
        "cost_per_1m_output": 3.00,
        "context_window": 1_000_000,
        "supports_json_mode": True,
    },
    MODEL_GEMINI_25_PRO: {
        "litellm_name": "gemini/gemini-2.5-pro",
        "provider": "google",
        "cost_per_1m_input": 1.25,  # ≤200k tokens
        "cost_per_1m_input_large": 2.50,  # >200k tokens
        "cost_per_1m_input_cached": 0.125,  # ≤200k cached
        "cost_per_1m_input_cached_large": 0.25,  # >200k cached
        "cost_per_1m_output": 10.00,  # ≤200k tokens
        "cost_per_1m_output_large": 15.00,  # >200k tokens
        "context_window": 1_000_000,
        "supports_json_mode": True,
    },
    MODEL_GEMINI_25_FLASH: {
        "litellm_name": "gemini/gemini-2.5-flash",
        "provider": "google",
        "cost_per_1m_input": 0.15,
        "cost_per_1m_input_cached": 0.015,
        "cost_per_1m_output": 0.60,
        "context_window": 1_000_000,
        "supports_json_mode": True,
    },
    MODEL_GEMINI_20_FLASH: {
        "litellm_name": "gemini/gemini-2.0-flash",
        "provider": "google",
        "cost_per_1m_input": 0.10,
        "cost_per_1m_input_cached": 0.025,
        "cost_per_1m_output": 0.40,
        "context_window": 1_000_000,
        "supports_json_mode": True,
    },
    MODEL_GEMINI_25_FLASH_LITE: {
        "litellm_name": "gemini/gemini-2.5-flash-lite",
        "provider": "google",
        "cost_per_1m_input": 0.10,
        "cost_per_1m_input_cached": 0.01,
        "cost_per_1m_output": 0.40,
        "context_window": 1_000_000,
        "supports_json_mode": True,
    },
    # Anthropic Claude
    MODEL_CLAUDE_SONNET_45: {
        "litellm_name": "anthropic/claude-sonnet-4-5",
        "provider": "anthropic",
        "cost_per_1m_input": 3.00,  # ≤200k tokens
        "cost_per_1m_input_large": 6.00,  # >200k tokens
        "cost_per_1m_output": 15.00,  # ≤200k tokens
        "cost_per_1m_output_large": 22.50,  # >200k tokens
        "cost_per_1m_input_cached_write": 3.75,  # ≤200k
        "cost_per_1m_input_cached_read": 0.30,  # ≤200k
        "cost_per_1m_input_cached_write_large": 7.50,  # >200k
        "cost_per_1m_input_cached_read_large": 0.60,  # >200k
        "context_window": 200_000,
        "supports_json_mode": True,
    },
    MODEL_CLAUDE_HAIKU_45: {
        "litellm_name": "anthropic/claude-haiku-4-5",
        "provider": "anthropic",
        "cost_per_1m_input": 1.00,
        "cost_per_1m_output": 5.00,
        "cost_per_1m_input_cached_write": 1.25,
        "cost_per_1m_input_cached_read": 0.10,
        "context_window": 200_000,
        "supports_json_mode": True,
    },
    # OpenAI
    MODEL_GPT52: {
        "litellm_name": "gpt-5.2",
        "provider": "openai",
        "cost_per_1m_input": 1.75,
        "cost_per_1m_input_cached": 0.175,
        "cost_per_1m_output": 14.00,
        "context_window": 128_000,
        "supports_json_mode": True,
    },
    MODEL_GPT5_MINI: {
        "litellm_name": "gpt-5-mini",
        "provider": "openai",
        "cost_per_1m_input": 0.25,
        "cost_per_1m_output": 2.00,
        "context_window": 128_000,
        "supports_json_mode": True,
    },
    MODEL_GPT5_NANO: {
        "litellm_name": "gpt-5-nano",
        "provider": "openai",
        "cost_per_1m_input": 0.05,
        "cost_per_1m_output": 0.40,
        "context_window": 128_000,
        "supports_json_mode": True,
    },
    MODEL_GPT4O_MINI: {
        "litellm_name": "gpt-4o-mini",
        "provider": "openai",
        "cost_per_1m_input": 0.15,
        "cost_per_1m_output": 0.60,
        "context_window": 128_000,
        "supports_json_mode": True,
    },
}


# =============================================================================
# TASK-BASED MODEL SELECTION
# =============================================================================


class LLMTask(Enum):
    """LLM task types with specific model configurations."""

    NARRATIVE_GENERATION = "narrative_generation"
    WEBSITE_EXTRACTION = "website_extraction"
    PDF_EXTRACTION = "pdf_extraction"
    # Premium tier for top charities
    PREMIUM_NARRATIVE = "premium_narrative"
    PREMIUM_PDF_EXTRACTION = "premium_pdf_extraction"
    # Evaluation scoring (LLM-as-judge for local audit)
    EVALUATION_SCORING = "evaluation_scoring"
    # Rich strategic narrative - citation-heavy, needs best model
    RICH_STRATEGIC_NARRATIVE = "rich_strategic_narrative"
    # Post-export validation judges (cost-effective validation)
    LLM_JUDGE = "llm_judge"


# Task -> (primary_model, fallback_models)
# NOTE: Only use Gemini models - Anthropic has JSON schema restrictions
TASK_MODELS: Dict[LLMTask, Tuple[str, List[str]]] = {
    # Standard pipeline - Flash is best value per LLM-as-Judge evaluation
    LLMTask.NARRATIVE_GENERATION: (
        MODEL_GEMINI_3_FLASH,  # Best quality/cost ratio
        [MODEL_GEMINI_3_PRO],
    ),
    LLMTask.WEBSITE_EXTRACTION: (
        MODEL_GEMINI_3_FLASH,  # Default: best field coverage; hallucinations handled post-extraction
        [MODEL_GEMINI_3_PRO],
    ),
    LLMTask.PDF_EXTRACTION: (
        MODEL_GEMINI_3_FLASH,  # Fast, cost-effective extraction
        [MODEL_GEMINI_3_PRO],
    ),
    # Premium tier for top 5-10 charities - still use Flash (proven quality)
    LLMTask.PREMIUM_NARRATIVE: (MODEL_GEMINI_3_FLASH, [MODEL_GEMINI_3_PRO]),
    LLMTask.PREMIUM_PDF_EXTRACTION: (MODEL_GEMINI_3_FLASH, [MODEL_GEMINI_3_PRO]),
    # Evaluation scoring - LLM-as-judge
    LLMTask.EVALUATION_SCORING: (
        MODEL_GEMINI_3_FLASH,  # Fast judge for benchmarking
        [MODEL_GEMINI_3_PRO],
    ),
    # Rich strategic narrative - GPT-5.2: 2x depth + 2x citations vs Flash per A/B test
    LLMTask.RICH_STRATEGIC_NARRATIVE: (
        MODEL_GPT52,  # Best quality (97.8 overall), 2x content depth, ~$0.06/charity
        [MODEL_CLAUDE_SONNET_45, MODEL_GEMINI_3_FLASH],
    ),
    # Post-export validation - use cheapest model
    LLMTask.LLM_JUDGE: (
        MODEL_GEMINI_20_FLASH,  # Cost-effective (~$0.0005/charity)
        [MODEL_GEMINI_3_FLASH],
    ),
}


# =============================================================================
# BACKWARD COMPATIBILITY - Legacy tier system
# =============================================================================


class ModelTier(Enum):
    """Legacy model tiers - prefer LLMTask for new code."""

    BEST = "best"
    BACKUP = "backup"
    CHEAPEST = "cheapest"


TIER_MODELS: Dict[ModelTier, List[str]] = {
    ModelTier.BEST: [MODEL_GEMINI_3_FLASH, MODEL_GEMINI_3_PRO],
    ModelTier.BACKUP: [MODEL_GEMINI_3_FLASH, MODEL_GPT4O_MINI],
    ModelTier.CHEAPEST: [MODEL_GEMINI_3_FLASH, MODEL_GPT4O_MINI],
}


# =============================================================================
# PROMPT VERSIONING
# =============================================================================

# Prompt versions - increment when prompt templates change
PROMPT_VERSIONS: Dict[str, str] = {
    "narrative_generation": "v2.0.0",
    "website_extraction": "v1.2.0",
    "pdf_extraction": "v1.1.0",
    "charity_navigator_financial": "v1.0.0",
}


def get_prompt_version(task_name: str) -> str:
    """Get the current prompt version for a task."""
    return PROMPT_VERSIONS.get(task_name, "v0.0.0")


# =============================================================================
# LLM RESPONSE WITH TRACKING
# =============================================================================


@dataclass
class LLMResponse:
    """
    Standard response from any LLM provider with full tracking metadata.

    The triple (model_version, prompt_version, db_snapshot_version) enables
    reproducibility and debugging of LLM outputs.
    """

    text: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    finish_reason: Optional[str] = None

    # Tracking metadata
    model_version: str = ""  # Fully qualified model name
    prompt_version: str = ""  # Version of the prompt template used
    prompt_hash: str = ""  # SHA256 of actual prompt sent
    db_snapshot_version: Optional[str] = None  # Database version if available
    timestamp: str = ""  # ISO timestamp of the call
    task: Optional[str] = None  # LLMTask name if used

    # Raw response for debugging
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_db_record(self) -> Dict[str, Any]:
        """Convert to a dictionary suitable for database storage."""
        return {
            "model_version": self.model_version,
            "prompt_version": self.prompt_version,
            "prompt_hash": self.prompt_hash,
            "db_snapshot_version": self.db_snapshot_version,
            "timestamp": self.timestamp,
            "task": self.task,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "finish_reason": self.finish_reason,
            "response_length": len(self.text),
        }


# =============================================================================
# LLM CLIENT
# =============================================================================


class LLMClient:
    """
    Unified LLM client with task-based model selection and automatic fallback.

    Features:
    - Task-based model selection (NARRATIVE_GENERATION, WEBSITE_EXTRACTION, etc.)
    - Automatic fallback on transient errors
    - Full tracking of (model_version, prompt_version, db_snapshot_version)
    - Cost tracking

    Usage:
        # Task-based (recommended)
        client = LLMClient(task=LLMTask.NARRATIVE_GENERATION)

        # Specific model
        client = LLMClient(model=MODEL_GEMINI_3_FLASH)

        # Legacy tier-based
        client = LLMClient(tier=ModelTier.CHEAPEST)
    """

    def __init__(
        self,
        task: Optional[LLMTask] = None,
        tier: Optional[ModelTier] = None,
        model: Optional[str] = None,
        api_keys: Optional[Dict[str, str]] = None,
        db_snapshot_version: Optional[str] = None,
        logger=None,
    ):
        """
        Initialize LLM client.

        Args:
            task: LLM task type (determines model and fallbacks)
            tier: Legacy model tier (BEST, BACKUP, CHEAPEST)
            model: Specific model name (overrides task/tier)
            api_keys: Dict of provider -> API key
            db_snapshot_version: Current database version for tracking
            logger: Optional logger instance
        """
        self.logger = logger
        self.api_keys = api_keys or {}
        self.db_snapshot_version = db_snapshot_version
        self.task = task

        self._setup_api_keys()

        # Determine model configuration
        if model:
            if model not in MODEL_REGISTRY:
                raise ValueError(f"Unknown model: {model}. Available: {list(MODEL_REGISTRY.keys())}")
            self.model_name = model
            self.model_config = MODEL_REGISTRY[model]
            self.fallback_models = []
        elif task:
            primary, fallbacks = TASK_MODELS[task]
            self.model_name = primary
            self.model_config = MODEL_REGISTRY[primary]
            self.fallback_models = fallbacks
        elif tier:
            models = TIER_MODELS[tier]
            self.model_name = models[0]
            self.model_config = MODEL_REGISTRY[models[0]]
            self.fallback_models = models[1:] if len(models) > 1 else []
        else:
            # Default to Gemini 3 Flash (fast, cost-effective)
            self.model_name = MODEL_GEMINI_3_FLASH
            self.model_config = MODEL_REGISTRY[MODEL_GEMINI_3_FLASH]
            self.fallback_models = [MODEL_GEMINI_3_PRO]

        if self.logger:
            fallback_str = f" (fallbacks: {self.fallback_models})" if self.fallback_models else ""
            self.logger.info(f"LLM client initialized: {self.model_name}{fallback_str}")

    def _setup_api_keys(self):
        """Set API keys in environment for LiteLLM (only if not already set)."""
        key_map = {
            "GEMINI_API_KEY": self.api_keys.get("google") or self.api_keys.get("gemini"),
            "ANTHROPIC_API_KEY": self.api_keys.get("anthropic"),
            "OPENAI_API_KEY": self.api_keys.get("openai"),
        }
        for env_var, value in key_map.items():
            if value and not os.environ.get(env_var):
                os.environ[env_var] = value

    def _is_transient_error(self, error: Exception) -> bool:
        """Check if an error is transient and worth retrying with fallback."""
        error_str = str(error).lower()
        transient_indicators = [
            "rate limit",
            "quota exceeded",
            "too many requests",
            "429",
            "503",
            "502",
            "timeout",
            "connection",
            "temporary",
            "overloaded",
        ]
        return any(indicator in error_str for indicator in transient_indicators)

    def _is_permanent_error(self, error: Exception) -> bool:
        """
        Check if an error is permanent and should NOT trigger fallback.

        Permanent errors include:
        - Authentication/API key errors
        - Invalid request format/schema errors
        - Permission errors
        """
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()

        permanent_indicators = [
            "authentication",
            "invalid api key",
            "api key",
            "unauthorized",
            "401",
            "403",
            "permission denied",
            "invalid request",
            "validation error",
            "schema",
            "authenticationerror",
            "invalidrequesterror",
        ]
        return any(indicator in error_str or indicator in error_type for indicator in permanent_indicators)

    def _compute_prompt_hash(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Compute SHA256 hash of the full prompt for tracking."""
        full_prompt = f"{system_prompt or ''}|||{prompt}"
        return hashlib.sha256(full_prompt.encode()).hexdigest()[:16]

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        json_schema: Optional[Dict] = None,
        prompt_version: Optional[str] = None,
        retry_on_error: bool = True,
    ) -> LLMResponse:
        """
        Generate text using the configured model with automatic fallback.

        Args:
            prompt: User prompt
            system_prompt: Optional system instructions
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            json_mode: Request JSON output
            json_schema: Optional JSON schema for structured output
            prompt_version: Version string for this prompt template
            retry_on_error: Automatic retry on failures

        Returns:
            LLMResponse with text, tracking metadata, and cost
        """
        models_to_try = [self.model_name] + self.fallback_models
        last_error = None
        prompt_hash = self._compute_prompt_hash(prompt, system_prompt)

        for model_name in models_to_try:
            try:
                return self._generate_with_model(
                    model_name=model_name,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=json_mode,
                    json_schema=json_schema,
                    prompt_version=prompt_version,
                    prompt_hash=prompt_hash,
                    retry_on_error=retry_on_error,
                )
            except Exception as e:
                last_error = e

                # Check for permanent errors - don't retry these
                if self._is_permanent_error(e):
                    if self.logger:
                        self.logger.error(
                            f"Permanent error with {model_name}: {e}. "
                            f"Not trying fallback - this requires fixing the request or API key."
                        )
                    raise

                # If last model, raise regardless of error type
                if model_name == models_to_try[-1]:
                    raise

                # Transient errors: try fallback
                if self._is_transient_error(e):
                    if self.logger:
                        self.logger.warning(
                            f"TRANSIENT error with {model_name}: {type(e).__name__}: {e}. "
                            f"Trying fallback to {models_to_try[models_to_try.index(model_name) + 1] if models_to_try.index(model_name) < len(models_to_try) - 1 else 'none'}..."
                        )
                    continue

                # Other errors: log and try fallback
                if self.logger:
                    self.logger.warning(
                        f"UNEXPECTED error with {model_name}: {type(e).__name__}: {e}. "
                        f"Trying fallback to {models_to_try[models_to_try.index(model_name) + 1] if models_to_try.index(model_name) < len(models_to_try) - 1 else 'none'}..."
                    )
                continue

        raise RuntimeError(f"All models failed. Last error: {last_error}")

    def _generate_with_model(
        self,
        model_name: str,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
        json_mode: bool,
        json_schema: Optional[Dict],
        prompt_version: Optional[str],
        prompt_hash: str,
        retry_on_error: bool,
    ) -> LLMResponse:
        """Internal method to generate with a specific model."""
        model_config = MODEL_REGISTRY[model_name]

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Build kwargs for LiteLLM
        kwargs = {
            "model": model_config["litellm_name"],
            "messages": messages,
            "temperature": temperature,
        }

        # Handle max_tokens (some models have issues with this)
        if max_tokens and model_config["provider"] != "google":
            kwargs["max_tokens"] = max_tokens

        # JSON mode
        if json_mode and model_config.get("supports_json_mode"):
            if json_schema:
                kwargs["response_format"] = {"type": "json_schema", "json_schema": json_schema}
            else:
                kwargs["response_format"] = {"type": "json_object"}

        # Retries
        if retry_on_error:
            kwargs["num_retries"] = 2

        kwargs["timeout"] = 180  # 3 minutes max

        # Provider-specific settings
        if model_config["provider"] == "google":
            kwargs["safety_settings"] = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            # Use top_k for more deterministic outputs (limits token sampling)
            kwargs["top_k"] = 40

        # GPT-5 model restrictions: temperature must be 1.0, and max_tokens cuts into
        # reasoning tokens (192+ tokens used internally before generating output)
        if model_name.startswith("gpt-5"):
            kwargs["temperature"] = 1.0  # Only supported value
            kwargs.pop("max_tokens", None)  # Let model decide (reasoning needs headroom)
            if self.logger:
                self.logger.debug("GPT-5 model: forcing temperature=1.0, no max_tokens")

        litellm.drop_params = True

        # Make the call
        response = completion(**kwargs)

        # Validate response structure (LiteLLM/API might return empty choices)
        if not response.choices or len(response.choices) == 0:
            raise RuntimeError(
                f"LLM API returned empty choices array. "
                f"Model: {model_name}, Response: {getattr(response, 'id', 'unknown')}"
            )

        # Extract text
        text = response.choices[0].message.content or ""

        # Calculate cost with proper error handling
        try:
            cost = completion_cost(completion_response=response)
        except Exception:
            # Fallback cost calculation - verify usage object exists
            if not hasattr(response, "usage") or response.usage is None:
                if self.logger:
                    self.logger.warning(f"Response missing usage data, cannot calculate cost for {model_name}")
                input_tokens = 0
                output_tokens = 0
                cost = 0.0
            else:
                input_tokens = getattr(response.usage, "prompt_tokens", 0)
                output_tokens = getattr(response.usage, "completion_tokens", 0)
                cost = (input_tokens / 1_000_000) * model_config["cost_per_1m_input"] + (
                    output_tokens / 1_000_000
                ) * model_config["cost_per_1m_output"]

        # Extract token counts safely (including cache tokens if available)
        if hasattr(response, "usage") and response.usage:
            input_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
            output_tokens = getattr(response.usage, "completion_tokens", 0) or 0
            # Cache tokens (for Claude/Gemini prompt caching)
            cache_read_tokens = getattr(response.usage, "cache_read_input_tokens", None)
            if cache_read_tokens is None:
                # Try alternative location (prompt_tokens_details.cached_tokens)
                prompt_details = getattr(response.usage, "prompt_tokens_details", None)
                if prompt_details:
                    cache_read_tokens = getattr(prompt_details, "cached_tokens", None)
            # Convert None to 0
            cache_read_tokens = cache_read_tokens or 0
            cache_creation_tokens = getattr(response.usage, "cache_creation_input_tokens", None) or 0
        else:
            input_tokens = 0
            output_tokens = 0
            cache_read_tokens = 0
            cache_creation_tokens = 0

        # Extract response time if available (also handle None)
        response_ms = getattr(response, "_response_ms", None)

        # Build response with full tracking
        llm_response = LLMResponse(
            text=text,
            model=model_name,
            provider=model_config["provider"],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            finish_reason=response.choices[0].finish_reason,
            # Tracking fields
            model_version=model_config["litellm_name"],
            prompt_version=prompt_version or get_prompt_version(self.task.value if self.task else "unknown"),
            prompt_hash=prompt_hash,
            db_snapshot_version=self.db_snapshot_version,
            timestamp=datetime.now(timezone.utc).isoformat(),
            task=self.task.value if self.task else None,
            metadata={
                "raw_response_id": getattr(response, "id", None),
                "cache_read_input_tokens": cache_read_tokens,
                "cache_creation_input_tokens": cache_creation_tokens,
                "response_ms": response_ms,
            },
        )

        if self.logger:
            self.logger.debug(
                f"LLM call: {model_name} | "
                f"Tokens: {llm_response.input_tokens}->{llm_response.output_tokens} | "
                f"Cost: ${llm_response.cost_usd:.6f}"
            )

        return llm_response

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the currently configured model."""
        return {
            "model": self.model_name,
            "litellm_name": self.model_config["litellm_name"],
            "provider": self.model_config["provider"],
            "cost_per_1m_input": self.model_config["cost_per_1m_input"],
            "cost_per_1m_output": self.model_config["cost_per_1m_output"],
            "fallback_models": self.fallback_models,
            "task": self.task.value if self.task else None,
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def get_client_for_task(task: LLMTask, logger=None) -> LLMClient:
    """Get an LLM client configured for a specific task."""
    return LLMClient(task=task, logger=logger)


def get_extraction_client(logger=None) -> LLMClient:
    """Get a cheap client for extraction tasks."""
    return LLMClient(task=LLMTask.WEBSITE_EXTRACTION, logger=logger)


def get_narrative_client(logger=None) -> LLMClient:
    """Get a high-quality client for narrative generation."""
    return LLMClient(task=LLMTask.NARRATIVE_GENERATION, logger=logger)


def get_premium_client(logger=None) -> LLMClient:
    """Get the best client for top charity deep analysis."""
    return LLMClient(task=LLMTask.PREMIUM_NARRATIVE, logger=logger)
