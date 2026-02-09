"""Configuration for the judge system.

Two judge categories:
- **Deterministic judges**: Pure Python, rule-based (no LLM cost, fully reproducible)
- **LLM judges**: Use LLM for semantic validation (citation/factual/score/zakat/narrative/cross-lens)

Defines sampling rates, thresholds, model selection, and caching settings.
Uses cost-effective defaults (Gemini 2.0 Flash at ~$0.0005/charity for LLM judges).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class JudgeConfig:
    """Configuration for the judge orchestrator.

    Attributes:
        sample_rate: Fraction of charities to validate (0.0-1.0)
        verify_all_citations: Whether to verify ALL cited URLs (vs sampling)
        url_fetch_timeout: Timeout in seconds for URL fetching
        url_cache_ttl_days: How long to cache fetched URL content
        max_content_chars: Truncate fetched pages to this length
        error_threshold: Number of errors to flag a charity for review
        warning_threshold: Number of warnings to flag a charity
        judge_model: Primary model for judge tasks
        fallback_model: Fallback if primary fails
        cache_dir: Directory for URL content cache
        enable_citation_judge: Run citation validation
        enable_factual_judge: Run factual claim validation
        enable_score_judge: Run score rationale validation
        enable_zakat_judge: Run zakat classification validation
    """

    # Sampling configuration
    sample_rate: float = 0.1  # 10% of charities
    verify_all_citations: bool = True  # Verify ALL cited URLs

    # URL verification
    url_fetch_timeout: int = 10  # seconds
    url_cache_ttl_days: int = 7  # Cache fetched content
    max_content_chars: int = 10000  # Truncate large pages

    # Thresholds
    error_threshold: int = 1  # Errors to flag charity
    warning_threshold: int = 3  # Warnings to flag

    # Model selection (cost-effective)
    judge_model: str = "gemini-2.0-flash"  # Cheapest option
    fallback_model: str = "gemini-3-flash"  # Already in pipeline

    # Caching
    cache_dir: Optional[Path] = None

    # Deterministic judges — pure Python, no LLM cost, fully reproducible
    enable_basic_info_judge: bool = True
    enable_data_completeness_judge: bool = True
    enable_recognition_judge: bool = True
    enable_crawl_quality_judge: bool = True
    enable_extract_quality_judge: bool = True
    enable_discover_quality_judge: bool = True
    enable_synthesize_quality_judge: bool = True
    enable_baseline_quality_judge: bool = True
    enable_export_quality_judge: bool = True

    # LLM judges — use LLM for semantic validation, non-deterministic, has cost
    enable_citation_judge: bool = True     # Verifies URL content supports claims
    enable_factual_judge: bool = True      # Verifies narrative claims match source data
    enable_score_judge: bool = True        # Verifies rationale-score alignment
    enable_zakat_judge: bool = True        # Verifies zakat classification vs programs
    enable_narrative_quality_judge: bool = True  # Assesses specificity, actionability, genuineness
    enable_cross_lens_judge: bool = True   # Finds contradictions across narrative lenses

    # Stratified sampling options
    ensure_tier_coverage: bool = True  # Sample from all score tiers
    escalate_flagged: bool = True  # 100% validation for flagged charities

    def __post_init__(self):
        """Set default cache directory if not provided."""
        if self.cache_dir is None:
            self.cache_dir = Path.home() / ".amal-metric-data" / "judge_cache"

    def get_enabled_judges(self) -> list[str]:
        """Get list of enabled judge names."""
        judges = []
        if self.enable_citation_judge:
            judges.append("citation")
        if self.enable_factual_judge:
            judges.append("factual")
        if self.enable_score_judge:
            judges.append("score")
        if self.enable_zakat_judge:
            judges.append("zakat")
        if self.enable_data_completeness_judge:
            judges.append("data_completeness")
        if self.enable_basic_info_judge:
            judges.append("basic_info")
        if self.enable_recognition_judge:
            judges.append("recognition_data")
        if self.enable_crawl_quality_judge:
            judges.append("crawl_quality")
        if self.enable_extract_quality_judge:
            judges.append("extract_quality")
        if self.enable_discover_quality_judge:
            judges.append("discover_quality")
        if self.enable_synthesize_quality_judge:
            judges.append("synthesize_quality")
        if self.enable_baseline_quality_judge:
            judges.append("baseline_quality")
        if self.enable_export_quality_judge:
            judges.append("export_quality")
        if self.enable_narrative_quality_judge:
            judges.append("narrative_quality")
        if self.enable_cross_lens_judge:
            judges.append("cross_lens")
        return judges
