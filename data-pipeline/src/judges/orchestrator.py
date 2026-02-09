"""Judge Orchestrator - coordinates sampling, parallel execution, and aggregation.

Handles:
1. Stratified sampling of charities for validation
2. Parallel execution of multiple judges
3. Aggregation of results into final report
4. Diff-based validation using DoltDB versioning
5. Verdict persistence for regression detection
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from ..db.repository import JudgeVerdictRepository

from .base_judge import BaseJudge, JudgeType
from .baseline_quality_judge import BaselineQualityJudge
from .basic_info_judge import BasicInfoJudge
from .citation_judge import CitationJudge
from .crawl_quality_judge import CrawlQualityJudge
from .cross_lens_judge import CrossLensJudge
from .data_completeness_judge import DataCompletenessJudge
from .diff_validator import ChangeRecord, DiffValidationReport, DiffValidator
from .discover_quality_judge import DiscoverQualityJudge
from .export_quality_judge import ExportQualityJudge
from .extract_quality_judge import ExtractQualityJudge
from .factual_judge import FactualJudge
from .narrative_quality_judge import NarrativeQualityJudge
from .recognition_judge import RecognitionDataJudge
from .schemas.config import JudgeConfig
from .schemas.verdict import (
    CharityValidationResult,
    JudgeVerdict,
    Severity,
    ValidationIssue,
)
from .score_judge import ScoreJudge
from .synthesize_quality_judge import SynthesizeQualityJudge
from .url_verifier import URLVerifier
from .zakat_judge import ZakatJudge

logger = logging.getLogger(__name__)


def _get_current_commit_hash() -> str | None:
    """Get the current HEAD commit hash from DoltDB.

    Returns:
        Commit hash string or None if unable to retrieve
    """
    try:
        from ..db.client import execute_query

        row = execute_query("SELECT commit_hash FROM dolt_log LIMIT 1", fetch="one")
        if row and isinstance(row, dict):
            return row.get("commit_hash")
        return None
    except Exception as e:
        logger.warning(f"Failed to get current commit hash: {e}")
        return None


@dataclass
class BatchResult:
    """Result from validating a batch of charities.

    Attributes:
        timestamp: When the validation was run
        charities_total: Total charities in input
        charities_sampled: Number actually validated
        results: Per-charity validation results
        total_cost_usd: Total LLM cost for the batch
        config: Configuration used for validation
        diff_report: Optional report from diff-based validation
        score_warnings: Score changes that exceeded thresholds
        regressions: Charities that went from passing to failing
        commit_hash: The commit hash verdicts were persisted against
    """

    timestamp: datetime
    charities_total: int
    charities_sampled: int
    results: list[CharityValidationResult] = field(default_factory=list)
    total_cost_usd: float = 0.0
    config: Optional[JudgeConfig] = None

    # Diff-based validation fields
    diff_report: Optional[DiffValidationReport] = None
    score_warnings: list[ChangeRecord] = field(default_factory=list)
    regressions: list[dict] = field(default_factory=list)
    commit_hash: Optional[str] = None

    @property
    def sampled(self) -> list[CharityValidationResult]:
        """Alias for results (for compatibility)."""
        return self.results

    @property
    def flagged(self) -> list[CharityValidationResult]:
        """Get charities that were flagged for review."""
        return [r for r in self.results if r.flagged]

    @property
    def passed(self) -> list[CharityValidationResult]:
        """Get charities that passed validation."""
        return [r for r in self.results if r.passed]

    @property
    def errors(self) -> list[ValidationIssue]:
        """Get all errors across all charities."""
        errors = []
        for result in self.results:
            errors.extend(result.all_errors)
        return errors

    @property
    def warnings(self) -> list[ValidationIssue]:
        """Get all warnings across all charities."""
        warnings = []
        for result in self.results:
            warnings.extend(result.all_warnings)
        return warnings

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "timestamp": self.timestamp.isoformat(),
            "charities_total": self.charities_total,
            "charities_sampled": self.charities_sampled,
            "charities_flagged": len(self.flagged),
            "charities_passed": len(self.passed),
            "total_errors": len(self.errors),
            "total_warnings": len(self.warnings),
            "total_cost_usd": self.total_cost_usd,
            "commit_hash": self.commit_hash,
            "results": [r.to_dict() for r in self.results],
        }

        # Include diff report if available
        if self.diff_report:
            result["diff_report"] = self.diff_report.to_dict()

        # Include score warnings
        if self.score_warnings:
            result["score_warnings"] = [
                {
                    "ein": w.ein,
                    "old_score": w.old_score,
                    "new_score": w.new_score,
                    "delta": w.score_delta,
                    "severity": w.severity.value if w.severity else None,
                    "trend": w.score_trend,
                }
                for w in self.score_warnings
            ]

        # Include regressions
        if self.regressions:
            result["regressions"] = self.regressions

        return result


class JudgeOrchestrator:
    """Orchestrates validation across multiple judges.

    Handles sampling, parallel execution, result aggregation,
    diff-based validation, and verdict persistence.
    """

    def __init__(
        self,
        config: Optional[JudgeConfig] = None,
        diff_mode: bool = False,
        since_commit: str = "HEAD~1",
        persist_verdicts: bool = True,
    ):
        """Initialize the orchestrator.

        Args:
            config: Judge configuration. Uses defaults if not provided.
            diff_mode: Enable diff-based validation (validate only changed charities)
            since_commit: Commit to compare against for diff mode (default: HEAD~1)
            persist_verdicts: Save verdicts to judge_verdicts table for regression tracking (default: True)
        """
        self.config = config or JudgeConfig()
        self.diff_mode = diff_mode
        self.since_commit = since_commit
        self.persist_verdicts = persist_verdicts

        self._url_verifier: Optional[URLVerifier] = None
        self._judges: Optional[list[BaseJudge]] = None
        self._verdict_repo: Optional["JudgeVerdictRepository"] = None

    def _get_verdict_repo(self) -> "JudgeVerdictRepository":
        """Lazy-load verdict repository."""
        if self._verdict_repo is None:
            from ..db.repository import JudgeVerdictRepository

            self._verdict_repo = JudgeVerdictRepository()
        return self._verdict_repo

    def get_url_verifier(self) -> URLVerifier:
        """Get or create shared URL verifier."""
        if self._url_verifier is None:
            # cache_dir is set in __post_init__ if None
            cache_dir = self.config.cache_dir or Path.home() / ".amal-metric-data" / "judge_cache"
            self._url_verifier = URLVerifier(
                cache_dir=cache_dir / "url_cache",
                timeout=self.config.url_fetch_timeout,
                ttl_days=self.config.url_cache_ttl_days,
                max_content_chars=self.config.max_content_chars,
            )
        return self._url_verifier

    def get_judges(self) -> list[BaseJudge]:
        """Get list of enabled judges."""
        if self._judges is None:
            self._judges = []

            if self.config.enable_citation_judge:
                self._judges.append(CitationJudge(self.config, url_verifier=self.get_url_verifier()))

            if self.config.enable_factual_judge:
                self._judges.append(FactualJudge(self.config))

            if self.config.enable_score_judge:
                self._judges.append(ScoreJudge(self.config))

            if self.config.enable_zakat_judge:
                self._judges.append(ZakatJudge(self.config))

            if self.config.enable_data_completeness_judge:
                self._judges.append(DataCompletenessJudge(self.config))

            if self.config.enable_basic_info_judge:
                self._judges.append(BasicInfoJudge(self.config))

            if self.config.enable_recognition_judge:
                self._judges.append(RecognitionDataJudge(self.config))

            if self.config.enable_crawl_quality_judge:
                self._judges.append(CrawlQualityJudge(self.config))

            if self.config.enable_extract_quality_judge:
                self._judges.append(ExtractQualityJudge(self.config))

            if self.config.enable_discover_quality_judge:
                self._judges.append(DiscoverQualityJudge(self.config))

            if self.config.enable_synthesize_quality_judge:
                self._judges.append(SynthesizeQualityJudge(self.config))

            if self.config.enable_baseline_quality_judge:
                self._judges.append(BaselineQualityJudge(self.config))

            if self.config.enable_export_quality_judge:
                self._judges.append(ExportQualityJudge(self.config))

            if self.config.enable_narrative_quality_judge:
                self._judges.append(NarrativeQualityJudge(self.config))

            if self.config.enable_cross_lens_judge:
                self._judges.append(CrossLensJudge(self.config))

        return self._judges

    def validate_batch(
        self,
        charities: list[dict[str, Any]],
        context_provider: Optional[Callable[[str], dict[str, Any]]] = None,
    ) -> BatchResult:
        """Validate a batch of charities.

        Args:
            charities: List of exported charity data dicts
            context_provider: Optional function to get context for a charity
                             Signature: (ein: str) -> dict[str, Any]

        Returns:
            BatchResult with validation results
        """
        start_time = datetime.now()
        total_charities = len(charities)
        current_commit = _get_current_commit_hash()

        # Initialize diff-related data
        diff_report: Optional[DiffValidationReport] = None
        score_warnings: list[ChangeRecord] = []
        regressions: list[dict] = []

        # Step 1: Run diff validation if enabled
        if self.diff_mode:
            logger.info(f"Running diff validation since {self.since_commit}")
            diff_validator = DiffValidator(
                since_commit=self.since_commit,
                include_score_history=True,
            )
            diff_report = diff_validator.validate()

            # Extract score warnings from diff report
            score_warnings = diff_report.unexplained_score_changes

            # Check for regressions if we have previous verdicts
            if self.persist_verdicts and current_commit:
                try:
                    verdict_repo = self._get_verdict_repo()
                    regressions = verdict_repo.get_regressions(
                        since_commit=self.since_commit,
                        to_commit=current_commit,
                    )
                    if regressions:
                        logger.warning(f"Found {len(regressions)} regressions")
                except Exception as e:
                    logger.warning(f"Failed to check for regressions: {e}")

            logger.info(
                f"Diff validation: {diff_report.charities_changed} changed, {len(score_warnings)} score warnings"
            )

        # Step 2: Sample charities
        sample = self._stratified_sample(charities)
        judges = self.get_judges()
        deterministic_judges = [j for j in judges if j.judge_type == JudgeType.DETERMINISTIC]
        llm_judges = [j for j in judges if j.judge_type == JudgeType.LLM]
        logger.info(
            f"Sampled {len(sample)} of {total_charities} charities ({self.config.sample_rate * 100:.0f}%) — "
            f"{len(deterministic_judges)} deterministic judges, {len(llm_judges)} LLM judges"
        )

        # Step 3: Validate each sampled charity
        results = []
        total_cost = 0.0

        for charity in sample:
            ein = charity.get("ein", "unknown")
            name = charity.get("name", "Unknown")

            # Get context for this charity
            context = {}
            if context_provider:
                try:
                    context = context_provider(ein)
                except Exception as e:
                    logger.warning(f"Failed to get context for {ein}: {e}")

            # Validate this charity
            result = self._validate_single(charity, context)
            results.append(result)
            total_cost += result.total_cost_usd

            # Log progress
            status = "PASS" if result.passed else "FLAGGED"
            logger.info(
                f"Validated {ein} ({name}): {status} "
                f"({len(result.all_errors)} errors, {len(result.all_warnings)} warnings)"
            )

            # Persist verdicts if enabled
            if self.persist_verdicts and current_commit:
                self._persist_verdicts(result, current_commit)

        # Step 4: Create batch result
        batch_result = BatchResult(
            timestamp=start_time,
            charities_total=total_charities,
            charities_sampled=len(sample),
            results=results,
            total_cost_usd=total_cost,
            config=self.config,
            diff_report=diff_report,
            score_warnings=score_warnings,
            regressions=regressions,
            commit_hash=current_commit,
        )

        logger.info(
            f"Validation complete: {len(batch_result.passed)} passed, "
            f"{len(batch_result.flagged)} flagged, "
            f"${total_cost:.4f} total cost"
        )

        return batch_result

    def _persist_verdicts(self, result: CharityValidationResult, commit_hash: str) -> None:
        """Persist judge verdicts to the database.

        Args:
            result: Validation result for a charity
            commit_hash: Current commit hash
        """
        try:
            verdict_repo = self._get_verdict_repo()
            for verdict in result.verdicts:
                verdict_repo.save_verdict(
                    {
                        "charity_ein": result.ein,
                        "commit_hash": commit_hash,
                        "judge_name": verdict.judge_name,
                        "passed": verdict.passed,
                        "error_count": len(verdict.errors),
                        "warning_count": len(verdict.warnings),
                        "issues": [i.to_dict() for i in verdict.issues],
                        "cost_usd": verdict.cost_usd,
                    }
                )
        except Exception as e:
            logger.error(f"Failed to persist verdicts for {result.ein}: {e}")

    def _stratified_sample(self, charities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sample charities with stratification by score tier.

        Ensures representation across score tiers if configured.
        """
        if self.config.sample_rate >= 1.0:
            return charities

        target_count = max(1, int(len(charities) * self.config.sample_rate))

        if not self.config.ensure_tier_coverage:
            # Simple random sample
            return random.sample(charities, min(target_count, len(charities)))

        # Stratified sampling by score tier
        tiers: dict[str, list[dict[str, Any]]] = {
            "high": [],  # 70-100
            "medium": [],  # 40-69
            "low": [],  # 0-39
            "unknown": [],
        }

        for charity in charities:
            score = charity.get("evaluation", {}).get("amal_score")
            if score is None:
                tiers["unknown"].append(charity)
            elif score >= 70:
                tiers["high"].append(charity)
            elif score >= 40:
                tiers["medium"].append(charity)
            else:
                tiers["low"].append(charity)

        # Sample proportionally from each tier
        sample = []
        for tier_name, tier_charities in tiers.items():
            if not tier_charities:
                continue

            # Calculate this tier's proportion
            tier_proportion = len(tier_charities) / len(charities)
            tier_target = max(1, int(target_count * tier_proportion))
            tier_sample = random.sample(tier_charities, min(tier_target, len(tier_charities)))
            sample.extend(tier_sample)

        # If we're short, add more randomly
        remaining = [c for c in charities if c not in sample]
        while len(sample) < target_count and remaining:
            sample.append(remaining.pop(random.randint(0, len(remaining) - 1)))

        return sample

    # LLM judges run per narrative variant (AMAL + strategic).
    # Determined dynamically via judge.judge_type == JudgeType.LLM.
    # Only these specific LLM judges run per-variant (others like zakat run once).
    _VARIANT_JUDGE_NAMES = {"citation", "factual", "score"}

    def _build_narrative_variants(self, charity: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        """Build narrative variants for multi-lens judge execution.

        Returns list of (prefix, output_override) tuples. The first variant
        is always AMAL (no prefix). If strategic narrative data exists,
        a second variant swaps in strategic narrative/citations/evaluation.
        """
        variants: list[tuple[str, dict[str, Any]]] = [("", charity)]

        strat_narr = charity.get("strategic_narrative")
        if strat_narr and strat_narr.get("summary"):
            strat_output = {
                **charity,
                "narrative": strat_narr,
                "citations": charity.get("strategic_citations", []),
                "evaluation": charity.get("strategic_evaluation", {}),
            }
            variants.append(("strategic_", strat_output))

        return variants

    def _validate_single(self, charity: dict[str, Any], context: dict[str, Any]) -> CharityValidationResult:
        """Validate a single charity with all enabled judges.

        LLM judges (citation, factual, score) run once per narrative variant
        (AMAL, then strategic if present). Deterministic judges run once.

        Args:
            charity: Exported charity data
            context: Source data context

        Returns:
            CharityValidationResult with all judge verdicts
        """
        ein = charity.get("ein", "unknown")
        name = charity.get("name", "Unknown")

        verdicts: list[JudgeVerdict] = []
        total_cost = 0.0

        judges = self.get_judges()
        variants = self._build_narrative_variants(charity)

        for judge in judges:
            is_variant_judge = (
                judge.judge_type == JudgeType.LLM
                and judge.name in self._VARIANT_JUDGE_NAMES
            )

            if is_variant_judge:
                # Run per-variant LLM judges once per narrative variant
                for prefix, variant_output in variants:
                    try:
                        verdict = judge.validate(variant_output, context)
                        # Prefix the judge name for non-AMAL variants
                        if prefix:
                            verdict = JudgeVerdict(
                                passed=verdict.passed,
                                judge_name=f"{prefix}{verdict.judge_name}",
                                issues=verdict.issues,
                                skipped=verdict.skipped,
                                skip_reason=verdict.skip_reason,
                                cost_usd=verdict.cost_usd,
                                metadata=verdict.metadata,
                            )
                        verdicts.append(verdict)
                        total_cost += verdict.cost_usd
                    except Exception as e:
                        judge_label = f"{prefix}{judge.name}" if prefix else judge.name
                        logger.error(f"Judge {judge_label} failed for {ein}: {e}")
                        verdicts.append(
                            JudgeVerdict(
                                passed=False,
                                judge_name=f"{prefix}{judge.name}" if prefix else judge.name,
                                issues=[
                                    ValidationIssue(
                                        severity=Severity.ERROR,
                                        field="judge_execution",
                                        message=f"Judge execution failed: {str(e)[:100]}",
                                    )
                                ],
                            )
                        )
            else:
                # Non-variant judges run once on the full charity data
                # (deterministic judges + LLM judges like zakat, narrative_quality, cross_lens)
                try:
                    verdict = judge.validate(charity, context)
                    verdicts.append(verdict)
                    total_cost += verdict.cost_usd
                except Exception as e:
                    logger.error(f"Judge {judge.name} failed for {ein}: {e}")
                    verdicts.append(
                        JudgeVerdict(
                            passed=False,
                            judge_name=judge.name,
                            issues=[
                                ValidationIssue(
                                    severity=Severity.ERROR,
                                    field="judge_execution",
                                    message=f"Judge execution failed: {str(e)[:100]}",
                                )
                            ],
                        )
                    )

        # Aggregate results
        all_passed = all(v.passed for v in verdicts if not v.skipped)

        return CharityValidationResult(
            ein=ein,
            name=name,
            passed=all_passed,
            verdicts=verdicts,
            total_cost_usd=total_cost,
        )

    def validate_single(
        self, charity: dict[str, Any], context: Optional[dict[str, Any]] = None
    ) -> CharityValidationResult:
        """Public method to validate a single charity.

        Useful for testing or ad-hoc validation.

        Args:
            charity: Exported charity data
            context: Optional source data context

        Returns:
            CharityValidationResult with all judge verdicts
        """
        result = self._validate_single(charity, context or {})

        # Persist verdicts if enabled
        if self.persist_verdicts:
            current_commit = _get_current_commit_hash()
            if current_commit:
                self._persist_verdicts(result, current_commit)

        return result

    def close(self) -> None:
        """Clean up resources."""
        if self._url_verifier:
            self._url_verifier.close()
            self._url_verifier = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
