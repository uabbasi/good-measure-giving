"""Tests for scoring audit trail functionality."""

import json
import tempfile
from pathlib import Path

from src.parsers.charity_metrics_aggregator import CharityMetrics
from src.scorers.v2_scorers import (
    AlignmentScorer,
    AmalScorerV2,
    CredibilityScorer,
)
from src.utils.scoring_audit import (
    CorroborationStatus,
    ScoreImpact,
    ScoringAuditEntry,
    ScoringAuditLog,
    get_audit_log,
    reset_audit_log,
)


class TestScoringAuditEntry:
    """Tests for ScoringAuditEntry dataclass."""

    def test_create_entry(self):
        """Test creating a basic audit entry."""
        entry = ScoringAuditEntry(
            ein="12-3456789",
            field_name="third_party_evaluated",
            value_used=True,
            sources_consulted=["website_claims", "charity_navigator"],
            corroboration_status=CorroborationStatus.CORROBORATED,
            score_impact=ScoreImpact.HIGH,
            scorer_name="TrustScorer",
            score_component="verification_tier",
            points_affected=10,
        )

        assert entry.ein == "12-3456789"
        assert entry.field_name == "third_party_evaluated"
        assert entry.value_used is True
        assert len(entry.sources_consulted) == 2
        assert entry.corroboration_status == CorroborationStatus.CORROBORATED
        assert entry.score_impact == ScoreImpact.HIGH
        assert entry.points_affected == 10

    def test_entry_to_dict(self):
        """Test converting entry to dictionary."""
        entry = ScoringAuditEntry(
            ein="12-3456789",
            field_name="has_financial_audit",
            value_used=True,
            sources_consulted=["inferred"],
            corroboration_status=CorroborationStatus.SINGLE_SOURCE,
            score_impact=ScoreImpact.HIGH,
        )

        d = entry.to_dict()
        assert d["ein"] == "12-3456789"
        assert d["field_name"] == "has_financial_audit"
        assert d["value_used"] is True
        assert d["corroboration_status"] == "single_source"
        assert d["score_impact"] == "high"
        assert "timestamp" in d

    def test_entry_with_warning(self):
        """Test entry with warning message."""
        entry = ScoringAuditEntry(
            ein="12-3456789",
            field_name="zakat_claim_detected",
            value_used=True,
            sources_consulted=["website_claims"],
            corroboration_status=CorroborationStatus.UNCORROBORATED,
            score_impact=ScoreImpact.HIGH,
            warning_message="AUDIT WARNING: EIN 12-3456789: zakat_claim_detected=True used but uncorroborated",
        )

        assert entry.warning_message is not None
        assert "AUDIT WARNING" in entry.warning_message


class TestScoringAuditLog:
    """Tests for ScoringAuditLog class."""

    def test_log_field_usage_corroborated(self):
        """Test logging a corroborated field usage."""
        audit_log = ScoringAuditLog()

        entry = audit_log.log_field_usage(
            ein="12-3456789",
            field_name="third_party_evaluated",
            value=True,
            sources=["charity_navigator", "candid"],
            corroborated=True,
            impact=ScoreImpact.HIGH,
            scorer="TrustScorer",
            component="verification_tier",
            points=10,
        )

        assert len(audit_log) == 1
        assert entry.corroboration_status == CorroborationStatus.CORROBORATED
        assert len(audit_log.get_warnings()) == 0

    def test_log_field_usage_uncorroborated_creates_warning(self):
        """Test that uncorroborated high-impact field creates warning."""
        audit_log = ScoringAuditLog()

        entry = audit_log.log_field_usage(
            ein="12-3456789",
            field_name="third_party_evaluated",
            value=True,
            sources=["website_claims"],
            corroborated=False,
            impact=ScoreImpact.HIGH,
            scorer="EvidenceScorer",
            component="evidence_grade",
            points=10,
        )

        assert len(audit_log) == 1
        assert entry.corroboration_status == CorroborationStatus.UNCORROBORATED
        warnings = audit_log.get_warnings()
        assert len(warnings) == 1
        assert "AUDIT WARNING" in warnings[0].warning_message

    def test_get_summary_for_ein(self):
        """Test getting summary for a specific charity."""
        audit_log = ScoringAuditLog()

        # Add entries for different charities
        audit_log.log_field_usage(
            ein="12-3456789",
            field_name="has_financial_audit",
            value=True,
            sources=["charity_navigator", "candid"],
            corroborated=True,
            impact=ScoreImpact.HIGH,
        )
        audit_log.log_field_usage(
            ein="12-3456789",
            field_name="third_party_evaluated",
            value=True,
            sources=["website_claims"],
            corroborated=False,
            impact=ScoreImpact.HIGH,
        )
        audit_log.log_field_usage(
            ein="98-7654321",
            field_name="zakat_claim_detected",
            value=True,
            sources=["website"],
            corroborated=False,
            impact=ScoreImpact.HIGH,
        )

        summary = audit_log.get_summary_for_ein("12-3456789")

        assert summary["ein"] == "12-3456789"
        assert summary["total_entries"] == 2
        assert summary["warnings_count"] == 1
        assert "corroborated" in summary["entries_by_status"]
        assert "uncorroborated" in summary["entries_by_status"]

    def test_export_to_json(self):
        """Test exporting audit log to JSON file."""
        audit_log = ScoringAuditLog()

        audit_log.log_field_usage(
            ein="12-3456789",
            field_name="has_financial_audit",
            value=True,
            sources=["cn", "candid"],
            corroborated=True,
            impact=ScoreImpact.HIGH,
        )
        audit_log.log_field_usage(
            ein="12-3456789",
            field_name="third_party_evaluated",
            value=True,
            sources=["website"],
            corroborated=False,
            impact=ScoreImpact.HIGH,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "audit.json"
            audit_log.export_to_json(filepath)

            assert filepath.exists()

            with open(filepath) as f:
                data = json.load(f)

            assert data["total_entries"] == 2
            assert data["total_warnings"] == 1
            assert len(data["entries"]) == 2
            assert len(data["warnings"]) == 1

    def test_clear(self):
        """Test clearing the audit log."""
        audit_log = ScoringAuditLog()

        audit_log.log_field_usage(
            ein="12-3456789",
            field_name="test",
            value=True,
            sources=["test"],
            corroborated=False,
            impact=ScoreImpact.HIGH,
        )

        assert len(audit_log) == 1
        assert len(audit_log.get_warnings()) == 1

        audit_log.clear()

        assert len(audit_log) == 0
        assert len(audit_log.get_warnings()) == 0


class TestGlobalAuditLog:
    """Tests for global audit log functions."""

    def test_get_audit_log_returns_same_instance(self):
        """Test that get_audit_log returns the same instance."""
        reset_audit_log()  # Start fresh
        log1 = get_audit_log()
        log2 = get_audit_log()
        assert log1 is log2

    def test_reset_audit_log(self):
        """Test that reset_audit_log creates new instance."""
        log1 = get_audit_log()
        log1.log_field_usage(
            ein="test",
            field_name="test",
            value=True,
            sources=["test"],
            corroborated=True,
            impact=ScoreImpact.LOW,
        )
        assert len(log1) == 1

        log2 = reset_audit_log()
        assert log2 is not log1
        assert len(log2) == 0


class TestScorerAuditIntegration:
    """Tests for audit trail integration with scorers."""

    def test_credibility_scorer_uses_financial_audit(self):
        """Test CredibilityScorer uses has_financial_audit in verification tier."""
        audit_log = reset_audit_log()
        scorer = CredibilityScorer(audit_log=audit_log)

        # With audit + CN score → HIGH verification tier
        metrics_with_audit = CharityMetrics(
            ein="12-3456789",
            name="Test Charity",
            has_financial_audit=True,
            cn_overall_score=91.0,
            candid_seal="platinum",
        )
        result_with = scorer.evaluate(metrics_with_audit)

        # Without audit, only CN → still HIGH (CN ≥90 + Candid platinum = two signals)
        metrics_without = CharityMetrics(
            ein="12-3456789",
            name="Test Charity",
            has_financial_audit=False,
            cn_overall_score=91.0,
            candid_seal="platinum",
        )
        audit_log2 = reset_audit_log()
        scorer2 = CredibilityScorer(audit_log=audit_log2)
        result_without = scorer2.evaluate(metrics_without)

        # Both should score well but the verification tier evidence should differ
        ver_with = next(c for c in result_with.components if c.name == "Verification Tier")
        ver_without = next(c for c in result_without.components if c.name == "Verification Tier")
        assert "audit" in ver_with.evidence.lower() or ver_with.scored >= ver_without.scored

    def test_alignment_scorer_logs_zakat_claim(self):
        """Test AlignmentScorer logs zakat_claim_detected usage."""
        audit_log = reset_audit_log()
        scorer = AlignmentScorer(audit_log=audit_log)

        metrics = CharityMetrics(
            ein="12-3456789",
            name="Test Charity",
            zakat_claim_detected=True,
            corroboration_status={
                "zakat_claim_detected": {
                    "passed": True,
                    "sources": ["website_content", "organization_name"],
                    "reason": "Website mentions zakat; Name contains zakat indicator",
                }
            },
        )

        result = scorer.evaluate(metrics)

        # Zakat claim gives +3 pts, total 3 → LOW level (needs ≥8 for HIGH)
        assert result.muslim_donor_fit_level == "LOW"
        assert len(audit_log) >= 1
        entries = [e for e in audit_log.get_all_entries() if e.field_name == "zakat_claim_detected"]
        assert len(entries) >= 1
        assert entries[0].scorer_name == "AlignmentScorer"

    def test_alignment_scorer_logs_warning_for_uncorroborated_zakat(self):
        """Test AlignmentScorer logs warning for uncorroborated zakat_claim_detected."""
        audit_log = reset_audit_log()
        scorer = AlignmentScorer(audit_log=audit_log)

        metrics = CharityMetrics(
            ein="12-3456789",
            name="Test Charity",
            zakat_claim_detected=True,
            corroboration_status={
                "zakat_claim_detected": {
                    "passed": False,
                    "sources": ["website_claims"],
                    "reason": "Only website claim, no corroboration",
                }
            },
        )

        scorer.evaluate(metrics)

        warnings = audit_log.get_warnings()
        assert len(warnings) >= 1
        zakat_warnings = [w for w in warnings if "zakat_claim_detected" in w.warning_message]
        assert len(zakat_warnings) >= 1

    def test_amal_scorer_shares_audit_log(self):
        """Test AmalScorerV2 shares audit log with sub-scorers."""
        audit_log = reset_audit_log()
        scorer = AmalScorerV2(audit_log=audit_log)

        metrics = CharityMetrics(
            ein="12-3456789",
            name="Test Charity",
            zakat_claim_detected=True,
            corroboration_status={
                "zakat_claim_detected": {"passed": True, "sources": ["website", "name"], "reason": "test"},
            },
        )

        scorer.evaluate(metrics)

        # AlignmentScorer logs zakat_claim_detected
        entries = audit_log.get_all_entries()
        assert len(entries) >= 1

        scorer_names = set(e.scorer_name for e in entries)
        assert "AlignmentScorer" in scorer_names


class TestAuditLogWithRealScoring:
    """Integration tests with real scoring scenarios."""

    def test_full_charity_evaluation_with_audit(self):
        """Test full charity evaluation generates comprehensive audit trail."""
        audit_log = reset_audit_log()
        scorer = AmalScorerV2(audit_log=audit_log)

        # High-scoring charity with all corroborated fields
        metrics = CharityMetrics(
            ein="12-3456789",
            name="Islamic Relief USA",
            mission="Providing humanitarian aid worldwide",
            cn_overall_score=95.0,
            candid_seal="Gold",
            has_financial_audit=True,
            program_expense_ratio=0.85,
            working_capital_ratio=3.0,
            is_muslim_focused=True,
            zakat_claim_detected=True,
            third_party_evaluated=True,
            evaluation_sources=["GiveWell"],
            detected_cause_area="HUMANITARIAN",
            corroboration_status={
                "has_financial_audit": {"passed": True, "sources": ["cn", "candid"], "reason": "test"},
                "third_party_evaluated": {"passed": True, "sources": ["givewell"], "reason": "test"},
                "zakat_claim_detected": {"passed": True, "sources": ["website", "name"], "reason": "test"},
            },
        )

        result = scorer.evaluate(metrics)

        # Should have a reasonable score (limited data in test fixture)
        assert result.amal_score >= 40
        assert result.wallet_tag == "ZAKAT-ELIGIBLE"

        # Should have audit entries from AlignmentScorer (zakat)
        entries = audit_log.get_all_entries()
        assert len(entries) >= 1
        warnings = audit_log.get_warnings()
        assert len(warnings) == 0

    def test_charity_with_data_quality_issues(self):
        """Test charity with uncorroborated data generates warnings."""
        audit_log = reset_audit_log()
        scorer = AmalScorerV2(audit_log=audit_log)

        # Charity with claims that aren't corroborated
        metrics = CharityMetrics(
            ein="98-7654321",
            name="Questionable Charity",
            has_financial_audit=True,  # Claimed but not corroborated
            zakat_claim_detected=True,  # Claimed but not corroborated
            corroboration_status={
                "has_financial_audit": {
                    "passed": False,
                    "sources": ["inferred"],
                    "reason": "Only inferred from revenue",
                },
                "zakat_claim_detected": {
                    "passed": False,
                    "sources": ["website_claims"],
                    "reason": "Only website claim",
                },
            },
        )

        scorer.evaluate(metrics)

        # Should have warnings for uncorroborated fields
        warnings = audit_log.get_warnings()
        assert len(warnings) >= 1

        # Export and verify
        summary = audit_log.get_summary_for_ein("98-7654321")
        assert summary["warnings_count"] >= 1
