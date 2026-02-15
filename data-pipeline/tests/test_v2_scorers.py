"""Tests for V2 scorers - 2-dimension GMG Score framework (100 pts).

Impact (50) + Alignment (50) + Risk (-10 max) + Data Confidence (0-1.0).
"""

import datetime

import pytest
from src.parsers.charity_metrics_aggregator import CharityMetrics
from src.scorers.rubric_registry import (
    BASE_WEIGHTS,
    IMPACT_TOTAL,
    RubricConfig,
    get_archetype_for_category,
    get_rubric_config,
    list_archetypes,
)
from src.scorers.rubric_registry import (
    clear_cache as clear_rubric_cache,
)
from src.scorers.v2_scorers import (
    # Enum-like constants (for coverage assertions)
    CAUSE_BENCHMARKS,
    CAUSE_IMPORTANCE_POINTS,
    CAUSE_URGENCY_POINTS,
    AlignmentScorer,
    AmalScorerV2,
    CredibilityScorer,
    EffectivenessScorer,
    FitScorer,
    ImpactScorer,
    RiskScorer,
    # Legacy wrappers
    TrustScorer,
    interpolate_score,
)

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _base_metrics(**overrides) -> CharityMetrics:
    """Build a CharityMetrics with sensible defaults, override any field."""
    defaults = dict(
        ein="12-3456789",
        name="Test Charity",
    )
    defaults.update(overrides)
    return CharityMetrics(**defaults)


def _component_pts(result, name: str) -> int:
    """Extract scored points for a named component from an assessment."""
    for c in result.components:
        if c.name == name:
            return c.scored
    raise ValueError(f"Component '{name}' not found in {[c.name for c in result.components]}")


def _component(result, name: str):
    """Extract component object by name from an assessment."""
    for c in result.components:
        if c.name == name:
            return c
    raise ValueError(f"Component '{name}' not found in {[c.name for c in result.components]}")


# ─── interpolate_score ──────────────────────────────────────────────────────


class TestInterpolateScore:
    """Piecewise-linear interpolation helper."""

    def test_at_knot(self):
        """Value exactly at a knot → returns that knot's score."""
        knots = [(0, 0), (10, 5), (20, 10)]
        assert interpolate_score(10, knots) == 5

    def test_between_knots(self):
        """Value between knots → linear interpolation."""
        knots = [(0, 0), (10, 10)]
        assert interpolate_score(5, knots) == pytest.approx(5.0)

    def test_below_first_knot(self):
        """Value below first knot → returns first score."""
        knots = [(5, 2), (10, 5)]
        assert interpolate_score(0, knots) == 2

    def test_above_last_knot(self):
        """Value above last knot → returns last score."""
        knots = [(0, 0), (10, 5)]
        assert interpolate_score(100, knots) == 5

    def test_program_ratio_knots(self):
        """Program ratio interpolation: 70% should be between 2 and 4."""
        knots = [(0.0, 0), (0.50, 0), (0.65, 2), (0.75, 4), (0.85, 6), (1.0, 6)]
        score_at_70 = interpolate_score(0.70, knots)
        assert 2 < score_at_70 < 4

    def test_track_record_knots(self):
        """15-year-old org should score between 4 (10yr) and 6 (20yr)."""
        knots = [(0, 1), (5, 2), (10, 4), (20, 6), (50, 6)]
        score = interpolate_score(15, knots)
        assert 4 < score < 6


# ─── CredibilityScorer (internal, 33 pts) ───────────────────────────────────


class TestCredibilityScorer:
    """Credibility = Verification(10) + Transparency(7) + DataQuality(3)
    + TheoryOfChange(5→3 in Impact) + Evidence&Outcomes(5 in Impact) + Governance(3→2 in Impact).

    Still produces 33pt internal score. Feeds DataConfidence + Impact quality-practice.
    """

    def test_high_verification_two_signals(self):
        """HIGH verification requires 2+ high-bar signals → 10 pts."""
        m = _base_metrics(
            cn_overall_score=92.0,
            candid_seal="Gold",
        )
        scorer = CredibilityScorer()
        result = scorer.evaluate(m)
        assert result.verification_tier == "HIGH"
        assert _component_pts(result, "Verification Tier") == 10

    def test_moderate_verification_one_signal(self):
        """MODERATE verification requires 1 moderate-bar signal → 7 pts."""
        m = _base_metrics(
            cn_overall_score=80.0,
            candid_seal="Silver",
        )
        scorer = CredibilityScorer()
        result = scorer.evaluate(m)
        assert result.verification_tier == "MODERATE"
        assert _component_pts(result, "Verification Tier") == 7

    def test_basic_verification(self):
        """BASIC verification with 990 available → 4 pts."""
        m = _base_metrics(irs_990_available=True, total_revenue=100_000)
        scorer = CredibilityScorer()
        result = scorer.evaluate(m)
        assert result.verification_tier == "BASIC"
        assert _component_pts(result, "Verification Tier") == 4

    def test_unverified(self):
        """No third-party profile → NONE (0 pts)."""
        m = _base_metrics()
        scorer = CredibilityScorer()
        result = scorer.evaluate(m)
        assert result.verification_tier == "NONE"
        assert _component_pts(result, "Verification Tier") == 0

    def test_transparency_gold_seal(self):
        """Candid Gold seal → 6 transparency points."""
        m = _base_metrics(candid_seal="Gold")
        scorer = CredibilityScorer()
        result = scorer.evaluate(m)
        assert _component_pts(result, "Transparency") == 6

    def test_score_bounds(self):
        """Credibility score must be 0-33 (internal)."""
        m = _base_metrics(
            cn_overall_score=95.0,
            candid_seal="Platinum",
            has_outcome_methodology=True,
        )
        scorer = CredibilityScorer()
        result = scorer.evaluate(m)
        assert 0 <= result.score <= 33

    def test_score_components_present(self):
        """Every evaluation should produce score components."""
        m = _base_metrics(cn_overall_score=85.0)
        scorer = CredibilityScorer()
        result = scorer.evaluate(m)
        assert len(result.components) > 0
        for comp in result.components:
            assert comp.name
            assert comp.possible > 0


# ─── ImpactScorer (50 pts) ──────────────────────────────────────────────────


class TestImpactScorer:
    """Impact = CPB(20) + Directness(7) + FinancialHealth(7) + ProgramRatio(6)
    + Evidence&Outcomes(5) + TOC(3) + Governance(2)."""

    def test_high_program_ratio(self):
        """Program ratio ≥ 85% → max pts for archetype (smooth scoring)."""
        m = _base_metrics(program_expense_ratio=0.90)
        scorer = ImpactScorer()
        result = scorer.evaluate(m)
        # Default archetype (DIRECT_SERVICE) has program_ratio=5
        assert _component_pts(result, "Program Ratio") == 5

    def test_low_program_ratio(self):
        """Program ratio ~55% → smooth score between 0 and 2."""
        m = _base_metrics(program_expense_ratio=0.55)
        scorer = ImpactScorer()
        result = scorer.evaluate(m)
        pr_pts = _component_pts(result, "Program Ratio")
        assert 0 <= pr_pts <= 2

    def test_cost_per_beneficiary_humanitarian(self):
        """$20/beneficiary in humanitarian → max CPB for archetype (exceptional, at top of knots)."""
        m = _base_metrics(
            program_expense_ratio=0.85,
            program_expenses=1_000_000,
            beneficiaries_served_annually=50_000,  # $20/beneficiary
            detected_cause_area="HUMANITARIAN",
        )
        scorer = ImpactScorer()
        result = scorer.evaluate(m)
        # Default archetype (DIRECT_SERVICE) has cost_per_beneficiary=13
        assert _component_pts(result, "Cost Per Beneficiary") == 13

    def test_cost_per_beneficiary_general(self):
        """General benchmarks (no cause area) → max 15 pts."""
        m = _base_metrics(
            program_expense_ratio=0.85,
            program_expenses=1_000_000,
            beneficiaries_served_annually=50_000,
        )
        scorer = ImpactScorer()
        result = scorer.evaluate(m)
        assert _component_pts(result, "Cost Per Beneficiary") <= 15

    def test_financial_health_resilient_range(self):
        """Reserves around 6 months should receive top financial-health points."""
        m = _base_metrics(working_capital_ratio=6.0)
        scorer = ImpactScorer()
        result = scorer.evaluate(m)
        assert _component_pts(result, "Financial Health") == 7

    def test_financial_health_high_reserves_get_contextual_guidance(self):
        """High reserves should not tell orgs to 'build to 1-3 months'."""
        m = _base_metrics(working_capital_ratio=18.0, total_revenue=10_000_000)
        scorer = ImpactScorer()
        result = scorer.evaluate(m)
        comp = _component(result, "Financial Health")
        assert comp.improvement_suggestion is not None
        assert "1-3 months" not in comp.improvement_suggestion.lower()
        assert "deployment" in comp.improvement_suggestion.lower() or "policy" in comp.improvement_suggestion.lower()

    def test_financial_health_unknown_reserves_guidance(self):
        """Missing reserves should trigger disclosure/policy guidance."""
        m = _base_metrics(working_capital_ratio=None)
        scorer = ImpactScorer()
        result = scorer.evaluate(m)
        comp = _component(result, "Financial Health")
        assert comp.improvement_suggestion is not None
        assert "publish" in comp.improvement_suggestion.lower()
        assert "policy" in comp.improvement_suggestion.lower()

    def test_has_evidence_and_toc_components(self):
        """Impact scorer now includes Evidence, TOC, and Governance components."""
        m = _base_metrics(cn_overall_score=85.0)
        scorer = ImpactScorer()
        result = scorer.evaluate(m)
        component_names = [c.name for c in result.components]
        assert "Evidence & Outcomes" in component_names
        assert "Theory of Change" in component_names
        assert "Governance" in component_names

    def test_score_bounds(self):
        """Impact score must be 0-50."""
        m = _base_metrics(
            program_expense_ratio=0.90,
            working_capital_ratio=3.0,
            program_expenses=1_000_000,
            beneficiaries_served_annually=50_000,
            detected_cause_area="HUMANITARIAN",
        )
        scorer = ImpactScorer()
        result = scorer.evaluate(m)
        assert 0 <= result.score <= 50


# ─── AlignmentScorer (50 pts) ──────────────────────────────────────────────


class TestAlignmentScorer:
    """Alignment = MuslimDonorFit(19) + CauseUrgency(13) + UnderservedSpace(7)
    + TrackRecord(6) + FundingGap(5)."""

    def test_muslim_focused_with_zakat(self):
        """Muslim-focused + zakat claim → high donor fit."""
        m = _base_metrics(
            is_muslim_focused=True,
            zakat_claim_detected=True,
            detected_cause_area="HUMANITARIAN",
            mission="Providing humanitarian relief to poor communities",
            programs=["Emergency Relief", "Food Security"],
        )
        scorer = AlignmentScorer()
        result = scorer.evaluate(m)
        mdf_pts = _component_pts(result, "Muslim Donor Fit")
        # zakat(2-4) + muslim-focused(2) + asnaf(5) + humanitarian(4) = 13-15
        assert mdf_pts >= 12
        assert mdf_pts <= 19

    def test_mainstream_charity(self):
        """Non-Muslim mainstream charity → low donor fit."""
        m = _base_metrics(
            is_muslim_focused=False,
            zakat_claim_detected=False,
            total_revenue=100_000_000,
        )
        scorer = AlignmentScorer()
        result = scorer.evaluate(m)
        assert _component_pts(result, "Muslim Donor Fit") <= 4

    def test_cause_urgency_humanitarian(self):
        """Humanitarian cause → 13 pts (highest urgency)."""
        m = _base_metrics(detected_cause_area="HUMANITARIAN")
        scorer = AlignmentScorer()
        result = scorer.evaluate(m)
        assert _component_pts(result, "Cause Urgency") == 13

    def test_cause_urgency_prefers_internal_primary_category(self):
        """Internal taxonomy should override detected_cause_area when available."""
        m = _base_metrics(
            detected_cause_area="HUMANITARIAN",
            primary_category="ADVOCACY_CIVIC",
            cause_tags=["advocacy", "systemic-change"],
            program_focus_tags=["advocacy-legal"],
        )
        scorer = AlignmentScorer()
        result = scorer.evaluate(m)
        assert _component_pts(result, "Cause Urgency") == 6

    def test_cause_urgency_advocacy_from_tags(self):
        """Advocacy tags should map urgency to ADVOCACY even if detected cause is missing."""
        m = _base_metrics(
            detected_cause_area=None,
            primary_category=None,
            cause_tags=["advocacy"],
            program_focus_tags=["research-policy"],
        )
        scorer = AlignmentScorer()
        result = scorer.evaluate(m)
        assert _component_pts(result, "Cause Urgency") == 6

    def test_funding_gap_small_org(self):
        """Revenue < $1M → 5 pts (maximum gap)."""
        m = _base_metrics(total_revenue=500_000)
        scorer = AlignmentScorer()
        result = scorer.evaluate(m)
        assert _component_pts(result, "Funding Gap") == 5

    def test_funding_gap_large_org(self):
        """Revenue > $50M → 3 pts (smallest gap)."""
        m = _base_metrics(total_revenue=100_000_000)
        scorer = AlignmentScorer()
        result = scorer.evaluate(m)
        assert _component_pts(result, "Funding Gap") == 3

    def test_track_record_veteran(self):
        """Founded 20+ years ago → 6 pts (smooth, at/near cap)."""
        m = _base_metrics(founded_year=1990)
        scorer = AlignmentScorer()
        result = scorer.evaluate(m)
        assert _component_pts(result, "Track Record") == 6

    def test_track_record_new(self):
        """Founded < 5 years ago → 1 pt."""
        m = _base_metrics(founded_year=datetime.date.today().year - 2)
        scorer = AlignmentScorer()
        result = scorer.evaluate(m)
        assert _component_pts(result, "Track Record") == 1

    def test_track_record_unknown(self):
        """No founded year → 1 pt (benefit of the doubt)."""
        m = _base_metrics()
        scorer = AlignmentScorer()
        result = scorer.evaluate(m)
        assert _component_pts(result, "Track Record") == 1

    def test_track_record_smooth(self):
        """15-year org should score between new (1) and veteran (6) — smooth interpolation."""
        m = _base_metrics(founded_year=datetime.date.today().year - 15)
        scorer = AlignmentScorer()
        result = scorer.evaluate(m)
        tr_pts = _component_pts(result, "Track Record")
        assert 4 <= tr_pts <= 6  # Interpolated between 10yr(4) and 20yr(6)

    def test_underserved_space_max(self):
        """Niche cause + underserved populations → 7 pts max."""
        m = _base_metrics(
            detected_cause_area="RELIGIOUS_CULTURAL",
            populations_served=["refugee communities"],
        )
        scorer = AlignmentScorer()
        result = scorer.evaluate(m)
        assert _component_pts(result, "Underserved Space") == 7

    def test_score_bounds(self):
        """Alignment score must be 0-50."""
        m = _base_metrics(
            is_muslim_focused=True,
            zakat_claim_detected=True,
            detected_cause_area="HUMANITARIAN",
            total_revenue=500_000,
        )
        scorer = AlignmentScorer()
        result = scorer.evaluate(m)
        assert 0 <= result.score <= 50


# ─── RiskScorer (-10 max) ────────────────────────────────────────────────────


class TestRiskScorer:
    """Risk deductions capped at -10."""

    def test_no_risks(self):
        """Clean charity → 0 deductions."""
        m = _base_metrics(
            program_expense_ratio=0.85,
            working_capital_ratio=3.0,
            board_size=7,
            reports_outcomes=True,
            has_theory_of_change=True,
        )
        scorer = RiskScorer()
        _case_against, deduction = scorer.evaluate(m)
        assert deduction == 0

    def test_low_program_spending(self):
        """Program spending < 50% → -5."""
        m = _base_metrics(program_expense_ratio=0.40)
        scorer = RiskScorer()
        _case_against, deduction = scorer.evaluate(m)
        assert deduction <= -5

    def test_small_board(self):
        """Board < 3 → -5."""
        m = _base_metrics(board_size=2)
        scorer = RiskScorer()
        _case_against, deduction = scorer.evaluate(m)
        assert deduction <= -5

    def test_cap_at_minus_10(self):
        """Multiple risks → capped at -10."""
        m = _base_metrics(
            program_expense_ratio=0.30,  # -5
            board_size=1,  # -5
            working_capital_ratio=0.5,  # -2
        )
        scorer = RiskScorer()
        _case_against, deduction = scorer.evaluate(m)
        assert deduction >= -10  # Can't go below -10

    def test_emerging_org_no_toc_risk(self):
        """Emerging org (<$1M) → no deduction for missing TOC/outcomes."""
        m = _base_metrics(
            total_revenue=200_000,  # EMERGING tier
            program_expense_ratio=0.85,
            working_capital_ratio=3.0,
            board_size=5,
            reports_outcomes=False,
            has_theory_of_change=False,
        )
        scorer = RiskScorer()
        _case_against, deduction = scorer.evaluate(m)
        assert deduction == 0  # No risk deductions for emerging orgs

    def test_established_org_full_risk(self):
        """Established org (>$10M) → full deduction for missing outcomes (-2) + TOC (-1)."""
        m = _base_metrics(
            total_revenue=50_000_000,  # ESTABLISHED tier
            program_expense_ratio=0.85,
            working_capital_ratio=3.0,
            board_size=7,
            reports_outcomes=False,
            has_theory_of_change=False,
        )
        scorer = RiskScorer()
        _case_against, deduction = scorer.evaluate(m)
        assert deduction == -3  # -2 outcomes + -1 TOC


# ─── DataConfidence ─────────────────────────────────────────────────────────


class TestDataConfidence:
    """Data Confidence signal (0.0-1.0, outside score)."""

    def test_high_confidence(self):
        """HIGH verification + Gold transparency → HIGH confidence badge."""
        m = _base_metrics(
            cn_overall_score=92.0,
            candid_seal="Gold",
        )
        scorer = AmalScorerV2()
        result = scorer.evaluate(m)
        assert result.data_confidence.badge == "HIGH"
        assert result.data_confidence.overall >= 0.7

    def test_low_confidence(self):
        """No verification signals → LOW confidence badge."""
        m = _base_metrics()
        scorer = AmalScorerV2()
        result = scorer.evaluate(m)
        assert result.data_confidence.badge == "LOW"
        assert result.data_confidence.overall < 0.4

    def test_confidence_bounds(self):
        """Confidence always 0.0-1.0."""
        m = _base_metrics(cn_overall_score=95.0, candid_seal="Platinum")
        scorer = AmalScorerV2()
        result = scorer.evaluate(m)
        assert 0.0 <= result.data_confidence.overall <= 1.0

    def test_confidence_components(self):
        """DataConfidence has all component breakdown fields."""
        m = _base_metrics(cn_overall_score=85.0)
        scorer = AmalScorerV2()
        result = scorer.evaluate(m)
        dc = result.data_confidence
        assert dc.verification_tier in ("HIGH", "MODERATE", "BASIC", "NONE")
        assert dc.transparency_label in ("PLATINUM", "GOLD", "SILVER", "BRONZE", "NONE")
        assert dc.data_quality_label in ("HIGH", "MODERATE", "LOW", "CONFLICTING")


# ─── AmalScorerV2 (full pipeline) ────────────────────────────────────────────


class TestAmalScorerV2:
    """Full 2-dimension evaluation: Impact(50) + Alignment(50) + Risk(-10)."""

    def test_full_evaluation_score_bounds(self):
        """Total score 0-100, each dimension within bounds."""
        m = _base_metrics(
            cn_overall_score=92.0,
            candid_seal="Gold",
            program_expense_ratio=0.85,
            working_capital_ratio=3.0,
            is_muslim_focused=True,
            zakat_claim_detected=True,
            detected_cause_area="HUMANITARIAN",
        )
        scorer = AmalScorerV2()
        result = scorer.evaluate(m)

        assert 0 <= result.amal_score <= 100
        assert 0 <= result.impact.score <= 50
        assert 0 <= result.alignment.score <= 50

    def test_zakat_wallet_tag(self):
        """Zakat claim → ZAKAT-ELIGIBLE tag."""
        m = _base_metrics(
            is_muslim_focused=True,
            zakat_claim_detected=True,
        )
        scorer = AmalScorerV2()
        result = scorer.evaluate(m)
        assert result.wallet_tag == "ZAKAT-ELIGIBLE"

    def test_sadaqah_wallet_tag(self):
        """No zakat claim → SADAQAH-ELIGIBLE tag."""
        m = _base_metrics(
            is_muslim_focused=False,
            zakat_claim_detected=False,
        )
        scorer = AmalScorerV2()
        result = scorer.evaluate(m)
        assert result.wallet_tag == "SADAQAH-ELIGIBLE"

    def test_score_summary_present(self):
        """Score summary should be generated for every evaluation."""
        m = _base_metrics(cn_overall_score=85.0)
        scorer = AmalScorerV2()
        result = scorer.evaluate(m)
        assert result.score_summary
        assert len(result.score_summary) > 20  # Not a trivial string

    def test_score_is_sum_of_dimensions_minus_risk(self):
        """amal_score = impact + alignment + risk_deduction (no credibility)."""
        m = _base_metrics(
            cn_overall_score=92.0,
            candid_seal="Gold",
            program_expense_ratio=0.85,
            working_capital_ratio=3.0,
            is_muslim_focused=True,
            detected_cause_area="HUMANITARIAN",
        )
        scorer = AmalScorerV2()
        result = scorer.evaluate(m)

        expected = result.impact.score + result.alignment.score + result.risk_deduction
        expected = max(0, min(100, expected))
        assert result.amal_score == expected

    def test_credibility_not_in_score(self):
        """Credibility is internal — it should NOT affect the total score."""
        m = _base_metrics(
            program_expense_ratio=0.85,
            working_capital_ratio=2.0,
            detected_cause_area="HUMANITARIAN",
        )
        scorer = AmalScorerV2()
        result = scorer.evaluate(m)

        # Credibility exists but isn't in the sum
        assert result.credibility.score >= 0
        assert result.amal_score == max(
            0, min(100, result.impact.score + result.alignment.score + result.risk_deduction)
        )

    def test_data_confidence_present(self):
        """Every evaluation should include data confidence."""
        m = _base_metrics()
        scorer = AmalScorerV2()
        result = scorer.evaluate(m)
        assert result.data_confidence is not None
        assert 0.0 <= result.data_confidence.overall <= 1.0

    def test_minimal_metrics(self):
        """Scorer should handle minimal metrics without crashing."""
        m = _base_metrics()
        scorer = AmalScorerV2()
        result = scorer.evaluate(m)
        assert 0 <= result.amal_score <= 100


# ─── Legacy wrapper compatibility ────────────────────────────────────────────


class TestLegacyWrappers:
    """Legacy classes (TrustScorer, EffectivenessScorer, FitScorer) still work."""

    def test_trust_scorer_delegates(self):
        """TrustScorer wraps CredibilityScorer."""
        m = _base_metrics(cn_overall_score=92.0, candid_seal="Gold")
        scorer = TrustScorer()
        result = scorer.evaluate(m)
        assert result.verification_tier == "HIGH"

    def test_effectiveness_scorer_delegates(self):
        """EffectivenessScorer wraps ImpactScorer and returns a valid assessment."""
        m = _base_metrics(program_expense_ratio=0.90)
        scorer = EffectivenessScorer()
        result = scorer.evaluate(m)
        # Legacy wrapper hardcodes cost_efficiency="AVERAGE"
        assert result.cost_efficiency == "AVERAGE"
        assert 0 <= result.score <= 25

    def test_fit_scorer_delegates(self):
        """FitScorer wraps AlignmentScorer."""
        m = _base_metrics(
            is_muslim_focused=True,
            zakat_claim_detected=True,
            zakat_claim_evidence="100% zakat fund",
            detected_cause_area="HUMANITARIAN",
            mission="Providing humanitarian relief to poor communities",
            programs=["Emergency Relief", "Food Security"],
        )
        scorer = FitScorer()
        result = scorer.evaluate(m)
        # Rescaled: zakat(4) + muslim-focused(2) + identity(1) + asnaf(5) + humanitarian(4) = 16 → HIGH
        assert result.counterfactual == "HIGH"


# ─── Enum Coverage ────────────────────────────────────────────────────────────
# Catch missing entries in cause-area maps (e.g., adding ADVOCACY to urgency
# but forgetting to add CPB benchmarks). A failure here means a cause area
# exists in one map but not another — it will silently fall back to defaults.
# ─────────────────────────────────────────────────────────────────────────────


class TestCauseAreaEnumCoverage:
    """Verify all cause-area maps cover the same set of cause areas."""

    # UNKNOWN: appears in urgency but not benchmarks (uses general CPB fallback)
    # FOOD_HUNGER, HEALTHCARE_COMPLEX: CPB-only sub-causes for finer benchmarks;
    # charities with these cause areas are classified under parent causes
    # (EXTREME_POVERTY, GLOBAL_HEALTH) for urgency/importance scoring.
    URGENCY_ONLY = {"UNKNOWN"}
    CPB_ONLY = {"FOOD_HUNGER", "HEALTHCARE_COMPLEX"}

    def test_benchmarks_cover_urgency(self):
        """Every primary cause in CAUSE_URGENCY_POINTS should have CPB benchmarks."""
        missing = set(CAUSE_URGENCY_POINTS) - set(CAUSE_BENCHMARKS) - self.URGENCY_ONLY
        assert not missing, (
            f"Cause areas in CAUSE_URGENCY_POINTS but missing from CAUSE_BENCHMARKS: {missing}. "
            f"These will silently fall back to GENERAL_CPB_KNOTS (capped at 15 pts)."
        )

    def test_benchmarks_cover_importance(self):
        """Every primary cause in CAUSE_IMPORTANCE_POINTS should have CPB benchmarks."""
        missing = set(CAUSE_IMPORTANCE_POINTS) - set(CAUSE_BENCHMARKS) - self.URGENCY_ONLY
        assert not missing, (
            f"Cause areas in CAUSE_IMPORTANCE_POINTS but missing from CAUSE_BENCHMARKS: {missing}. "
            f"These will silently fall back to GENERAL_CPB_KNOTS (capped at 15 pts)."
        )

    def test_urgency_covers_benchmarks(self):
        """Every primary cause with CPB benchmarks should have urgency points."""
        missing = set(CAUSE_BENCHMARKS) - set(CAUSE_URGENCY_POINTS) - self.CPB_ONLY
        assert not missing, (
            f"Cause areas in CAUSE_BENCHMARKS but missing from CAUSE_URGENCY_POINTS: {missing}. "
            f"These will fall back to default urgency of 6."
        )

    def test_importance_covers_benchmarks(self):
        """Every primary cause with CPB benchmarks should have importance points."""
        missing = set(CAUSE_BENCHMARKS) - set(CAUSE_IMPORTANCE_POINTS) - self.CPB_ONLY
        assert not missing, (
            f"Cause areas in CAUSE_BENCHMARKS but missing from CAUSE_IMPORTANCE_POINTS: {missing}. "
            f"These will fall back to default importance."
        )

    def test_aggregator_keywords_cover_urgency(self):
        """Every primary cause in the scorer urgency map should be detectable by the aggregator."""
        import inspect
        import re

        from src.parsers.charity_metrics_aggregator import CharityMetricsAggregator

        source = inspect.getsource(CharityMetricsAggregator.aggregate)
        # Extract cause areas from the cause_keywords dict in the aggregator source
        keyword_causes = set(re.findall(r'"([A-Z_]+)":\s*\[', source))
        # Filter to only actual cause area constants
        keyword_causes = {c for c in keyword_causes if c in CAUSE_URGENCY_POINTS}

        scorer_causes = set(CAUSE_URGENCY_POINTS) - self.URGENCY_ONLY
        missing = scorer_causes - keyword_causes
        assert not missing, (
            f"Cause areas in scorer but not detectable by aggregator keywords: {missing}. "
            f"Charities with these causes can only be detected via NTEE fallback."
        )


# ─── Rubric Archetypes (v5.0.0) ──────────────────────────────────────────────


class TestRubricArchetypes:
    """Per-category Impact weight profiles — all sum to 50."""

    def setup_method(self):
        """Clear cache before each test for isolation."""
        clear_rubric_cache()

    def test_all_archetypes_sum_to_50(self):
        """Every archetype's Impact weights must sum to 50."""
        for name in list_archetypes():
            config = get_rubric_config(name)
            total = sum(config.weights.values())
            assert total == IMPACT_TOTAL, f"{name} weights sum to {total}, expected {IMPACT_TOTAL}"

    def test_advocacy_org_gets_systemic_rubric(self):
        """CIVIL_RIGHTS_LEGAL category maps to SYSTEMIC_CHANGE archetype."""
        archetype = get_archetype_for_category("CIVIL_RIGHTS_LEGAL")
        assert archetype == "SYSTEMIC_CHANGE"

    def test_humanitarian_gets_direct_service(self):
        """HUMANITARIAN category maps to DIRECT_SERVICE archetype."""
        archetype = get_archetype_for_category("HUMANITARIAN")
        assert archetype == "DIRECT_SERVICE"

    def test_unknown_category_fallback(self):
        """Unknown category falls back to DIRECT_SERVICE."""
        archetype = get_archetype_for_category("TOTALLY_UNKNOWN")
        assert archetype == "DIRECT_SERVICE"

    def test_none_category_fallback(self):
        """None category falls back to DIRECT_SERVICE."""
        archetype = get_archetype_for_category(None)
        assert archetype == "DIRECT_SERVICE"

    def test_all_16_categories_mapped(self):
        """Every category in charity_categories.yaml has an archetype mapping."""
        from src.llm.category_classifier import list_categories

        for cat in list_categories():
            archetype = get_archetype_for_category(cat)
            assert archetype in list_archetypes(), f"Category {cat} maps to unknown archetype {archetype}"

    def test_base_weights_sum_to_50(self):
        """Base weights (v4.0.0 denominator for scaling) must sum to 50."""
        assert sum(BASE_WEIGHTS.values()) == IMPACT_TOTAL

    def test_rubric_config_scale_score(self):
        """Proportional scaling: 4/5 evidence → 8/10 for archetype with evidence=10."""
        config = RubricConfig(
            archetype="TEST",
            weights={
                "cost_per_beneficiary": 10,
                "directness": 5,
                "financial_health": 7,
                "program_ratio": 5,
                "evidence_outcomes": 10,
                "theory_of_change": 5,
                "governance": 8,
            },
        )
        # Evidence: base=5, new=10, raw=4 → scaled = round(4 * 10/5) = 8
        assert config.scale_score("evidence_outcomes", 4) == 8
        # Governance: base=2, new=8, raw=2 → scaled = round(2 * 8/2) = 8
        assert config.scale_score("governance", 2) == 8


class TestArchetypeScoring:
    """Impact scoring with different archetype rubrics."""

    def setup_method(self):
        clear_rubric_cache()

    def test_systemic_change_rubric_applied(self):
        """ImpactScorer with SYSTEMIC_CHANGE rubric uses correct weights."""
        m = _base_metrics(
            program_expense_ratio=0.85,
            working_capital_ratio=2.0,
            board_size=7,
        )
        rubric = get_rubric_config("SYSTEMIC_CHANGE")
        scorer = ImpactScorer()
        result = scorer.evaluate(m, rubric=rubric)

        # Verify rubric_archetype is set
        assert result.rubric_archetype == "SYSTEMIC_CHANGE"

        # Verify component `possible` values match SYSTEMIC_CHANGE weights
        expected_possibles = {
            "Cost Per Beneficiary": 7,
            "Directness": 3,
            "Financial Health": 7,
            "Program Ratio": 7,
            "Evidence & Outcomes": 9,
            "Theory of Change": 7,
            "Governance": 10,
        }
        for comp in result.components:
            assert comp.possible == expected_possibles[comp.name], (
                f"{comp.name}: possible={comp.possible}, expected={expected_possibles[comp.name]}"
            )

    def test_direct_service_rubric_applied(self):
        """ImpactScorer with DIRECT_SERVICE rubric uses correct weights."""
        m = _base_metrics(
            program_expense_ratio=0.85,
            working_capital_ratio=2.0,
        )
        rubric = get_rubric_config("DIRECT_SERVICE")
        scorer = ImpactScorer()
        result = scorer.evaluate(m, rubric=rubric)

        assert result.rubric_archetype == "DIRECT_SERVICE"
        expected_possibles = {
            "Cost Per Beneficiary": 13,
            "Directness": 5,
            "Financial Health": 7,
            "Program Ratio": 5,
            "Evidence & Outcomes": 5,
            "Theory of Change": 5,
            "Governance": 10,
        }
        for comp in result.components:
            assert comp.possible == expected_possibles[comp.name], (
                f"{comp.name}: possible={comp.possible}, expected={expected_possibles[comp.name]}"
            )

    def test_governance_scales_up(self):
        """STRONG governance (2/2 base) scales to 10/10 across all archetypes."""
        m = _base_metrics(board_size=7)  # STRONG governance
        scorer = ImpactScorer()

        for archetype_name in list_archetypes():
            rubric = get_rubric_config(archetype_name)
            result = scorer.evaluate(m, rubric=rubric)
            gov_comp = next(c for c in result.components if c.name == "Governance")
            assert gov_comp.possible == rubric.weights["governance"]
            # STRONG = 2/2 base → should scale to possible/possible (full marks)
            assert gov_comp.scored == gov_comp.possible, (
                f"{archetype_name}: governance scored={gov_comp.scored}, possible={gov_comp.possible}"
            )

    def test_total_score_still_100(self):
        """Total GMG score is still 0-100 with archetype rubric."""
        m = _base_metrics(
            ein="77-0411194",  # CAIR SFBA — maps to CIVIL_RIGHTS_LEGAL → SYSTEMIC_CHANGE
            program_expense_ratio=0.85,
            working_capital_ratio=3.0,
            is_muslim_focused=True,
            detected_cause_area="ADVOCACY",
        )
        scorer = AmalScorerV2()
        result = scorer.evaluate(m)
        assert 0 <= result.amal_score <= 100
        assert 0 <= result.impact.score <= 50
        assert 0 <= result.alignment.score <= 50

    def test_impact_components_sum_to_at_most_50(self):
        """Sum of component scored values should not exceed 50 for any archetype."""
        m = _base_metrics(
            program_expense_ratio=0.90,
            working_capital_ratio=2.0,
            program_expenses=1_000_000,
            beneficiaries_served_annually=50_000,
            detected_cause_area="HUMANITARIAN",
            board_size=7,
            has_theory_of_change=True,
            theory_of_change="Detailed theory of change document explaining how our programs create lasting impact through direct service delivery and capacity building in vulnerable communities",
            third_party_evaluated=True,
        )
        scorer = ImpactScorer()

        for archetype_name in list_archetypes():
            rubric = get_rubric_config(archetype_name)
            result = scorer.evaluate(m, cause_area="HUMANITARIAN", rubric=rubric)
            assert result.score <= 50, f"{archetype_name}: impact score {result.score} > 50"

    def test_possible_values_sum_to_50(self):
        """All component possible values should sum to exactly 50."""
        m = _base_metrics()
        scorer = ImpactScorer()

        for archetype_name in list_archetypes():
            rubric = get_rubric_config(archetype_name)
            result = scorer.evaluate(m, rubric=rubric)
            total_possible = sum(c.possible for c in result.components)
            assert total_possible == 50, (
                f"{archetype_name}: sum of possible={total_possible}, expected 50"
            )
