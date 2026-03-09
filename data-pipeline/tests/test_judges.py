"""Tests for the LLM judge validation system.

Tests cover:
- Schema validation
- Individual judge logic (without LLM calls)
- Orchestrator sampling and aggregation
- URL verifier caching
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.judges.schemas.config import JudgeConfig
from src.judges.schemas.verdict import (
    CharityValidationResult,
    JudgeVerdict,
    Severity,
    ValidationIssue,
)
from src.judges.factual_judge import FactualJudge
from src.judges.url_verifier import FetchResult, URLCache, URLVerifier
from src.judges.orchestrator import BatchResult, JudgeOrchestrator


# =============================================================================
# Schema Tests
# =============================================================================


class TestValidationIssue:
    """Tests for ValidationIssue dataclass."""

    def test_to_dict_basic(self):
        """Test basic serialization."""
        issue = ValidationIssue(
            severity=Severity.ERROR,
            field="test_field",
            message="Test message",
        )
        d = issue.to_dict()
        assert d["severity"] == "error"
        assert d["field"] == "test_field"
        assert d["message"] == "Test message"
        assert "details" not in d
        assert "evidence" not in d

    def test_to_dict_with_details(self):
        """Test serialization with optional fields."""
        issue = ValidationIssue(
            severity=Severity.WARNING,
            field="citation_1",
            message="URL unreachable",
            details={"url": "https://example.com"},
            evidence="HTTP 404 returned",
        )
        d = issue.to_dict()
        assert d["severity"] == "warning"
        assert d["details"]["url"] == "https://example.com"
        assert d["evidence"] == "HTTP 404 returned"


class TestJudgeVerdict:
    """Tests for JudgeVerdict dataclass."""

    def test_properties(self):
        """Test error/warning filtering properties."""
        verdict = JudgeVerdict(
            passed=False,
            judge_name="test",
            issues=[
                ValidationIssue(Severity.ERROR, "f1", "Error 1"),
                ValidationIssue(Severity.WARNING, "f2", "Warning 1"),
                ValidationIssue(Severity.ERROR, "f3", "Error 2"),
                ValidationIssue(Severity.INFO, "f4", "Info 1"),
            ],
        )
        assert len(verdict.errors) == 2
        assert len(verdict.warnings) == 1

    def test_skipped_verdict(self):
        """Test skipped verdict serialization."""
        verdict = JudgeVerdict(
            passed=True,
            judge_name="zakat",
            skipped=True,
            skip_reason="SADAQAH-ELIGIBLE",
        )
        d = verdict.to_dict()
        assert d["skipped"] is True
        assert d["skip_reason"] == "SADAQAH-ELIGIBLE"


class TestJudgeConfig:
    """Tests for JudgeConfig dataclass."""

    def test_defaults(self):
        """Test default configuration values."""
        config = JudgeConfig()
        assert config.sample_rate == 0.1
        assert config.verify_all_citations is True
        assert config.judge_model == "gemini-2.0-flash"
        assert config.cache_dir is not None

    def test_enabled_judges(self):
        """Test get_enabled_judges method."""
        config = JudgeConfig(
            enable_citation_judge=True,
            enable_factual_judge=False,
            enable_score_judge=True,
            enable_zakat_judge=False,
        )
        enabled = config.get_enabled_judges()
        assert "citation" in enabled
        assert "factual" not in enabled
        assert "score" in enabled
        assert "zakat" not in enabled


# =============================================================================
# URL Verifier Tests
# =============================================================================


class TestFetchResult:
    """Tests for FetchResult dataclass."""

    def test_to_dict(self):
        """Test serialization for caching."""
        result = FetchResult(
            success=True,
            content="Test content",
            status_code=200,
            content_type="text/html",
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["content"] == "Test content"

    def test_from_dict(self):
        """Test deserialization from cache."""
        d = {
            "success": False,
            "error": "HTTP 404",
            "status_code": 404,
        }
        result = FetchResult.from_dict(d)
        assert result.success is False
        assert result.error == "HTTP 404"
        assert result.cached is True


class TestURLCache:
    """Tests for URL caching."""

    def test_cache_miss(self):
        """Test cache returns None for unknown URL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = URLCache(Path(tmpdir))
            result = cache.get("https://example.com/unknown")
            assert result is None

    def test_cache_hit(self):
        """Test cache returns stored value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = URLCache(Path(tmpdir))
            url = "https://example.com/test"

            # Store
            stored = FetchResult(success=True, content="Test")
            cache.set(url, stored)

            # Retrieve
            retrieved = cache.get(url)
            assert retrieved is not None
            assert retrieved.success is True
            assert retrieved.content == "Test"
            assert retrieved.cached is True

    def test_hit_rate(self):
        """Test hit rate calculation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = URLCache(Path(tmpdir))

            # Miss
            cache.get("https://example.com/miss1")
            cache.get("https://example.com/miss2")

            # Store and hit
            cache.set("https://example.com/hit", FetchResult(success=True, content=""))
            cache.get("https://example.com/hit")

            # 1 hit, 2 misses = 33% hit rate
            assert 0.3 < cache.hit_rate < 0.4


class TestURLVerifier:
    """Tests for URLVerifier."""

    def test_should_skip_trusted_domains(self):
        """Test trusted domains are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            verifier = URLVerifier(Path(tmpdir))

            should_skip, reason = verifier.should_skip("https://www.irs.gov/form990")
            assert should_skip is True
            assert "irs.gov" in reason

            should_skip, reason = verifier.should_skip("https://propublica.org/nonprofits")
            assert should_skip is True

            should_skip, reason = verifier.should_skip("https://charitynavigator.org/profile")
            assert should_skip is True

    def test_should_not_skip_other_domains(self):
        """Test non-trusted domains are not skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            verifier = URLVerifier(Path(tmpdir))

            should_skip, _ = verifier.should_skip("https://example.com/page")
            assert should_skip is False

            should_skip, _ = verifier.should_skip("https://charity-website.org/about")
            assert should_skip is False


# =============================================================================
# Orchestrator Tests
# =============================================================================


class TestJudgeOrchestrator:
    """Tests for JudgeOrchestrator."""

    def test_stratified_sampling_proportional(self):
        """Test stratified sampling maintains tier proportions."""
        config = JudgeConfig(sample_rate=0.5, ensure_tier_coverage=True)
        orchestrator = JudgeOrchestrator(config)

        # Create charities across tiers
        charities = [
            {"ein": "1", "evaluation": {"amal_score": 90}},  # high
            {"ein": "2", "evaluation": {"amal_score": 85}},  # high
            {"ein": "3", "evaluation": {"amal_score": 80}},  # high
            {"ein": "4", "evaluation": {"amal_score": 60}},  # medium
            {"ein": "5", "evaluation": {"amal_score": 55}},  # medium
            {"ein": "6", "evaluation": {"amal_score": 25}},  # low
        ]

        sample = orchestrator._stratified_sample(charities)

        # Should sample about 3 charities (50%)
        assert 2 <= len(sample) <= 4

    def test_full_validation_rate(self):
        """Test 100% sample rate returns all charities."""
        config = JudgeConfig(sample_rate=1.0)
        orchestrator = JudgeOrchestrator(config)

        charities = [
            {"ein": "1", "evaluation": {"amal_score": 90}},
            {"ein": "2", "evaluation": {"amal_score": 60}},
            {"ein": "3", "evaluation": {"amal_score": 30}},
        ]

        sample = orchestrator._stratified_sample(charities)
        assert len(sample) == 3

    @patch("src.judges.orchestrator.CitationJudge")
    @patch("src.judges.orchestrator.FactualJudge")
    @patch("src.judges.orchestrator.ScoreJudge")
    @patch("src.judges.orchestrator.ZakatJudge")
    def test_validate_single_aggregates_verdicts(self, MockZakat, MockScore, MockFactual, MockCitation):
        """Test single charity validation aggregates all judge verdicts."""
        # Setup mock judges with proper names
        judge_names = ["citation", "factual", "score", "zakat"]
        mock_judges = [MockCitation, MockFactual, MockScore, MockZakat]
        for mock_judge, name in zip(mock_judges, judge_names):
            instance = mock_judge.return_value
            instance.validate.return_value = JudgeVerdict(
                passed=True,
                judge_name=name,
                issues=[],
            )

        # Disable judges that aren't mocked to keep test focused
        config = JudgeConfig(
            enable_data_completeness_judge=False,
            enable_basic_info_judge=False,
            enable_recognition_judge=False,
            enable_crawl_quality_judge=False,
            enable_extract_quality_judge=False,
            enable_discover_quality_judge=False,
            enable_synthesize_quality_judge=False,
            enable_baseline_quality_judge=False,
            enable_export_quality_judge=False,
            enable_narrative_quality_judge=False,
            enable_cross_lens_judge=False,
        )
        orchestrator = JudgeOrchestrator(config)

        charity = {"ein": "12-3456789", "name": "Test Charity"}
        result = orchestrator.validate_single(charity)

        assert result.ein == "12-3456789"
        assert result.passed is True
        assert len(result.verdicts) == 4  # 4 mocked judges


class TestJudgeFailClosed:
    def test_factual_judge_marks_llm_failure_as_error(self, monkeypatch):
        judge = FactualJudge(JudgeConfig(sample_rate=1.0))

        def explode(_output, _context):
            raise RuntimeError("llm unavailable")

        monkeypatch.setattr(judge, "_verify_claims_with_llm", explode)

        verdict = judge.validate(
            output={"narrative": {"summary": "Test claim."}},
            context={},
        )

        assert verdict.passed is False
        assert any(i.field == "llm_verification" and i.severity == Severity.ERROR for i in verdict.issues)


class TestBatchResult:
    """Tests for BatchResult."""

    def test_properties(self):
        """Test computed properties."""
        from datetime import datetime

        result = BatchResult(
            timestamp=datetime.now(),
            charities_total=10,
            charities_sampled=2,
            results=[
                CharityValidationResult(
                    ein="1",
                    name="Passed Charity",
                    passed=True,
                    verdicts=[],
                ),
                CharityValidationResult(
                    ein="2",
                    name="Failed Charity",
                    passed=False,
                    verdicts=[
                        JudgeVerdict(
                            passed=False,
                            judge_name="citation",
                            issues=[
                                ValidationIssue(Severity.ERROR, "url", "Broken"),
                                ValidationIssue(Severity.WARNING, "claim", "Weak"),
                            ],
                        )
                    ],
                ),
            ],
        )

        assert len(result.passed) == 1
        assert len(result.flagged) == 1
        assert len(result.errors) == 1
        assert len(result.warnings) == 1


# =============================================================================
# Integration Tests (Mocked LLM)
# =============================================================================


class TestCitationJudgeStructural:
    """Test citation judge structural validation (no LLM)."""

    def test_missing_citation_entry(self):
        """Test detection of [N] markers without entries."""
        from src.judges.citation_judge import CitationJudge

        config = JudgeConfig(verify_all_citations=False)  # Skip LLM
        judge = CitationJudge(config)

        # Narrative references [1] and [2], but only citation [1] exists
        output = {
            "narrative": {
                "summary": "This charity [1] does great work [2].",
            },
            "citations": [
                {"id": "[1]", "url": "https://example.com", "claim": "Does great work"},
            ],
        }

        issues = judge._validate_structure(output["narrative"], output["citations"])

        # Should find [2] is missing
        error_issues = [i for i in issues if i.severity == Severity.ERROR]
        assert len(error_issues) == 1
        assert "citation_2" in error_issues[0].field

    def test_orphaned_citation(self):
        """Test detection of citations not referenced in narrative."""
        from src.judges.citation_judge import CitationJudge

        config = JudgeConfig(verify_all_citations=False)
        judge = CitationJudge(config)

        output = {
            "narrative": {
                "summary": "This charity [1] does great work.",
            },
            "citations": [
                {"id": "[1]", "url": "https://example.com/1", "claim": "Referenced"},
                {"id": "[2]", "url": "https://example.com/2", "claim": "Orphaned"},
            ],
        }

        issues = judge._validate_structure(output["narrative"], output["citations"])

        # Should find citation 2 is orphaned (INFO severity)
        info_issues = [i for i in issues if i.severity == Severity.INFO]
        assert len(info_issues) == 1
        assert "citation_2" in info_issues[0].field


class TestScoreJudgeQuickChecks:
    """Test score judge quick tone checks (no LLM)."""

    def test_poor_score_with_positive_language(self):
        """Test detection of tone mismatch."""
        from src.judges.score_judge import ScoreJudge

        config = JudgeConfig()
        judge = ScoreJudge(config)

        evaluation = {"amal_score": 25}  # Poor tier
        narrative = {
            "trust_rationale": "This is an excellent organization with outstanding practices.",
        }

        issues = judge._quick_tone_checks(evaluation, narrative)

        assert len(issues) == 1
        assert issues[0].severity == Severity.WARNING
        assert "poor" in issues[0].message.lower()

    def test_exceptional_score_with_negative_language(self):
        """Test detection of negative tone with high score."""
        from src.judges.score_judge import ScoreJudge

        config = JudgeConfig()
        judge = ScoreJudge(config)

        evaluation = {"amal_score": 95}  # Exceptional tier
        narrative = {
            "trust_rationale": "This organization has concerning and inadequate practices.",
        }

        issues = judge._quick_tone_checks(evaluation, narrative)

        assert len(issues) == 1
        assert issues[0].severity == Severity.WARNING


class TestZakatJudgeQuickChecks:
    """Test zakat judge quick checks (no LLM)."""

    def test_zakat_eligible_without_asnaf_is_allowed(self):
        """Test ZAKAT-ELIGIBLE without asnaf does not error.

        Asnaf classification is for donors to decide, not a hard requirement.
        The zakat judge only verifies the wallet tag is valid.
        """
        from src.judges.zakat_judge import ZakatJudge

        config = JudgeConfig()
        judge = ZakatJudge(config)

        output = {
            "evaluation": {
                "wallet_tag": "ZAKAT-ELIGIBLE",
                "zakat_classification": {},  # No asnaf — that's OK
            }
        }

        issues = judge._quick_checks(output, {})

        error_issues = [i for i in issues if i.severity == Severity.ERROR]
        assert len(error_issues) == 0

    def test_invalid_wallet_tag(self):
        """Test invalid wallet tag is caught."""
        from src.judges.zakat_judge import ZakatJudge

        config = JudgeConfig()
        judge = ZakatJudge(config)

        output = {
            "evaluation": {
                "wallet_tag": "INVALID-TAG",
            }
        }

        issues = judge._quick_checks(output, {})

        error_issues = [i for i in issues if i.severity == Severity.ERROR]
        assert len(error_issues) == 1
        assert "wallet_tag" in error_issues[0].field


class TestFactualJudgeQuickChecks:
    """Test factual judge quick checks (no LLM)."""

    def test_amal_score_mismatch(self):
        """Test AMAL score mismatch detection."""
        from src.judges.factual_judge import FactualJudge

        config = JudgeConfig()
        judge = FactualJudge(config)

        output = {
            "evaluation": {"amal_score": 75},
            "financials": {},
        }
        context = {"metrics": {"amal_score": 80}}  # Different score

        issues = judge._quick_checks(output, context)

        error_issues = [i for i in issues if i.severity == Severity.ERROR]
        assert len(error_issues) == 1
        assert "amal_score" in error_issues[0].field

    def test_program_ratio_bounds(self):
        """Test program expense ratio bounds checking."""
        from src.judges.factual_judge import FactualJudge

        config = JudgeConfig()
        judge = FactualJudge(config)

        output = {
            "evaluation": {},
            "financials": {"program_expense_ratio": 1.5},  # Invalid > 1
        }

        issues = judge._quick_checks(output, {})

        error_issues = [i for i in issues if i.severity == Severity.ERROR]
        assert len(error_issues) == 1
        assert "program_expense_ratio" in error_issues[0].field
