"""
CharityMetrics Pydantic model for unified metrics across all data sources.

This model aggregates data from:
- Charity Navigator (CN)
- ProPublica/IRS 990
- Candid
- Form 990 Grants (Schedule I/F via ProPublica XML)
- Charity Website

Purpose: Provide a single, canonical representation of charity data for evaluators.
All evaluators (Impact, Confidence, Zakat) consume CharityMetrics, not raw source JSON.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..schemas.discovery import (
    SECTION_AWARDS,
    SECTION_EVALUATIONS,
    SECTION_OUTCOMES,
    SECTION_THEORY_OF_CHANGE,
    SECTION_ZAKAT,
)
from ..services.zakat_eligibility_service import determine_zakat_eligibility
from ..utils.deep_link_resolver import choose_website_evidence_url
from ..validators.source_required_validator import SourceRequiredValidator

logger = logging.getLogger(__name__)

# Module-level validator instance (reused across calls)
_source_validator = SourceRequiredValidator()

# Shared donation platforms where multiple charities coexist on the same domain.
# URLs on these domains require path-level ownership validation to prevent
# cross-charity zakat attribution (e.g., donorbox.org/zakaat != donorbox.org/linkoutside).
SHARED_DONATION_PLATFORMS = {
    "donorbox.org",
    "gofundme.com",
    "givebutter.com",
    "nonprofitsoapbox.com",
    "mightycause.com",
    "classy.org",
    "fundly.com",
    "givegab.com",
    "bonfire.com",
    "fundraise.com",
}


def _normalize_host(url: str) -> str:
    """Extract normalized hostname from URL (strips www. prefix)."""
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = parsed.netloc.lower().split(":")[0]
        return host.removeprefix("www.")
    except Exception:
        return ""


def _is_url_owned_by_charity(discovered_url: str, charity_website: str) -> bool:
    """Check if a discovered URL plausibly belongs to the charity being evaluated.

    For shared donation platforms (Donorbox, GoFundMe, etc.), verifies that the
    URL path corresponds to the charity's own campaign, not another org's page.

    For non-shared domains, checks that the domain matches the charity's website.

    Returns True if ownership can't be disproven (benefit of the doubt).
    """
    if not discovered_url or not charity_website:
        return True  # Can't validate without both URLs

    from urllib.parse import urlparse

    disc_host = _normalize_host(discovered_url)
    charity_host = _normalize_host(charity_website)

    # Check if the discovered URL is on a shared platform
    if disc_host not in SHARED_DONATION_PLATFORMS:
        # Not a shared platform - if domains match, it's fine
        # If domains differ, could be a legitimate cross-reference (e.g., search result)
        # so we don't block it here - other corroboration logic handles that
        return True

    # Shared platform: the charity's own website must also be on this platform
    # for us to trust a zakat URL found there
    if charity_host != disc_host:
        # Charity's website is on a different domain than the shared platform
        # This means the discovered URL is from ANOTHER org's campaign page
        logger.warning(
            f"Shared platform mismatch: discovered {discovered_url} "
            f"is on {disc_host}, but charity website is {charity_website}"
        )
        return False

    # Both on the same shared platform - check if paths are related
    disc_path = urlparse(discovered_url).path.strip("/").lower()
    charity_path = urlparse(charity_website).path.strip("/").lower()

    if not charity_path:
        # Charity URL is just the platform homepage - can't validate
        return False

    # The discovered path should contain or match the charity's campaign slug
    # e.g., charity=donorbox.org/linkoutside, discovered=donorbox.org/linkoutside/zakat
    if disc_path.startswith(charity_path):
        return True

    # Different paths on the same shared platform = different org's page
    logger.warning(
        f"Shared platform path mismatch: discovered path /{disc_path} "
        f"doesn't match charity path /{charity_path} on {disc_host}"
    )
    return False


def _first_non_none(*values):
    """Return the first non-None value, or None if all are None.

    Unlike `or` chains, this correctly preserves falsy-but-valid values
    like False, 0, and empty string.
    """
    for v in values:
        if v is not None:
            return v
    return None


class CharityMetrics(BaseModel):
    """
    Canonical charity metrics aggregated from all 5 data sources.

    This model represents the "single source of truth" for a charity's data,
    combining the best available information from CN, ProPublica, Candid, Form 990 Grants, and Website.
    """

    model_config = ConfigDict(extra="forbid")

    # ========================================================================
    # Core Identification
    # ========================================================================
    ein: str = Field(..., description="IRS EIN (primary identifier)")
    name: str = Field(..., description="Official charity name")
    charity_id: Optional[int] = Field(None, description="Database ID")

    # ========================================================================
    # Mission & Programs (primarily from Candid + Website)
    # ========================================================================
    mission: Optional[str] = Field(None, description="Mission statement")
    tagline: Optional[str] = Field(None, description="Short tagline")
    vision: Optional[str] = Field(None, description="Vision statement")
    strategic_goals: Optional[str] = Field(None, description="Strategic goals")

    programs: List[str] = Field(default_factory=list, description="List of program names/descriptions")
    program_descriptions: List[str] = Field(default_factory=list, description="Detailed program descriptions")

    # ========================================================================
    # Beneficiaries & Reach (from Candid + Website)
    # ========================================================================
    beneficiaries_served_annually: Optional[int] = Field(None, description="Number of beneficiaries served per year")
    populations_served: List[str] = Field(
        default_factory=list, description="Target populations (poor, refugees, orphans, etc.)"
    )
    geographic_coverage: List[str] = Field(
        default_factory=list, description="Geographic areas served (cities, states, countries)"
    )

    # Candid-specific fields (used by ZakatAssessor for raw Candid data access)
    candid_populations_served: Optional[List[str]] = Field(None, description="Populations served (raw from Candid)")
    candid_programs: Optional[List[str]] = Field(None, description="Programs list (raw from Candid)")
    candid_geographic_areas_served: Optional[List[str]] = Field(None, description="Geographic areas (raw from Candid)")

    # ========================================================================
    # Outcomes & Impact (from Candid + Website + PDFs)
    # ========================================================================
    outcomes: List[str] = Field(default_factory=list, description="Reported outcomes and impact metrics")
    impact_metrics: Dict[str, Any] = Field(
        default_factory=dict, description="Quantified impact metrics (key-value pairs)"
    )

    # PDF-extracted data (Form 990s, Annual Reports, Impact Reports)
    pdf_extracted_data: List[Dict[str, Any]] = Field(
        default_factory=list, description="LLM-extracted data from PDFs (programs, outcomes, theory of change)"
    )
    pdf_outcomes: List[Dict[str, Any]] = Field(
        default_factory=list, description="Outcomes data extracted from PDFs with source attribution"
    )

    # ========================================================================
    # Grantmaking (from Form 990 Schedule I/F)
    # ========================================================================
    grants_made: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Grants made to other organizations (from Form 990 Schedule I domestic + Schedule F foreign)",
    )
    grants_received: List[Dict[str, Any]] = Field(
        default_factory=list, description="Grants received from foundations (not available from Form 990)"
    )

    # ========================================================================
    # Financial Metrics (from CN + ProPublica + Candid)
    # ========================================================================

    # Revenue & Expenses
    total_revenue: Optional[float] = Field(None, description="Total revenue (IRS 990)")
    total_expenses: Optional[float] = Field(None, description="Total expenses")
    program_expenses: Optional[float] = Field(None, description="Program service expenses")
    admin_expenses: Optional[float] = Field(None, description="Administrative expenses")
    fundraising_expenses: Optional[float] = Field(None, description="Fundraising expenses")

    # Revenue breakdown (FIX #13: from ProPublica)
    total_contributions: Optional[float] = Field(None, description="Total contributions/gifts/grants (IRS 990)")
    program_service_revenue: Optional[float] = Field(None, description="Program service revenue (IRS 990)")
    investment_income: Optional[float] = Field(None, description="Investment income (IRS 990)")

    # GIK (Gifts-in-Kind) detection
    noncash_contributions: Optional[float] = Field(None, description="Noncash contributions from Form 990 XML")
    noncash_ratio: Optional[float] = Field(None, ge=0, le=1, description="Noncash / total contributions")
    cash_adjusted_program_ratio: Optional[float] = Field(
        None, ge=0, description="Program ratio excluding noncash (when GIK > 10%)"
    )

    # Ratios (calculated or from CN)
    program_expense_ratio: Optional[float] = Field(None, ge=0, le=1, description="Program expenses / Total expenses")
    admin_expense_ratio: Optional[float] = Field(None, ge=0, le=1, description="Admin expenses / Total expenses")
    fundraising_expense_ratio: Optional[float] = Field(
        None, ge=0, le=1, description="Fundraising expenses / Total expenses"
    )
    working_capital_ratio: Optional[float] = Field(None, description="Working capital ratio (months of expenses)")

    # Domestic burn rate (Fix 2: international orgs spending domestically)
    domestic_burn_rate: Optional[float] = Field(
        None, ge=0, le=1, description="Fraction of expenses staying in US (1 - foreign_grants/total_expenses)"
    )

    # Zakat reserve hoarding (Fix 3)
    claims_zakat: Optional[bool] = Field(None, description="Whether charity claims zakat eligibility")
    reserves_months: Optional[float] = Field(
        None, description="Net assets / monthly expenses — broader than working_capital_ratio"
    )

    # Assets & Liabilities
    total_assets: Optional[float] = Field(None, description="Total assets")
    total_liabilities: Optional[float] = Field(None, description="Total liabilities")
    net_assets: Optional[float] = Field(None, description="Net assets")

    # ========================================================================
    # Charity Navigator Scores (from CN)
    # ========================================================================
    cn_overall_score: Optional[float] = Field(None, ge=0, le=100, description="Charity Navigator overall score (0-100)")
    cn_financial_score: Optional[float] = Field(None, ge=0, le=100, description="CN financial score")
    cn_accountability_score: Optional[float] = Field(
        None, ge=0, le=100, description="CN accountability & transparency score"
    )
    cn_beacons: List[str] = Field(default_factory=list, description="List of CN Beacons achieved")

    # ========================================================================
    # BBB Wise Giving Alliance (FIX #5)
    # ========================================================================
    bbb_accredited: Optional[bool] = Field(None, description="Whether BBB WGA rates charity as meeting all 20 standards")
    bbb_standards_met_count: Optional[int] = Field(None, ge=0, le=20, description="Number of BBB standards met (out of 20)")
    bbb_governance_pass: Optional[bool] = Field(None, description="BBB governance standards (1-5) pass")
    bbb_effectiveness_pass: Optional[bool] = Field(None, description="BBB effectiveness standards (6-9) pass")
    bbb_finances_pass: Optional[bool] = Field(None, description="BBB financial standards (10-15) pass")

    # ========================================================================
    # Transparency & Governance (from Candid + CN + IRS 990)
    # ========================================================================
    candid_seal: Optional[str] = Field(None, description="Candid transparency seal (Bronze/Silver/Gold/Platinum)")

    board_size: Optional[int] = Field(None, description="Number of board members")
    independent_board_members: Optional[int] = Field(None, description="Number of independent board members")
    has_conflict_of_interest_policy: Optional[bool] = Field(None, description="Whether org has documented COI policy")
    has_financial_audit: Optional[bool] = Field(None, description="Whether org undergoes independent financial audit")
    irs_990_available: Optional[bool] = Field(None, description="Whether IRS 990 forms are publicly available")

    # ========================================================================
    # Form 990 Filing Status
    # ========================================================================
    form_990_exempt: Optional[bool] = Field(None, description="Exempt from Form 990 (churches/religious orgs)")
    form_990_exempt_reason: Optional[str] = Field(None, description="Reason for exemption")
    no_filings: Optional[bool] = Field(None, description="No Form 990 filings found in ProPublica")
    financial_data_tax_year: Optional[int] = Field(
        None, description="Tax year of the primary financial data (from ProPublica/IRS 990)"
    )
    financial_data_source: Optional[str] = Field(
        None, description="Source of income statement financials: 'propublica', 'charity_navigator', or 'mixed'"
    )
    financial_quality_flags: Optional[list[str]] = Field(
        None, description="Detected data quality issues (e.g., 'program_exceeds_total', 'expense_sum_mismatch')"
    )

    annual_report_published: Optional[bool] = Field(None, description="Whether organization publishes annual reports")
    receives_foundation_grants: Optional[bool] = Field(
        None, description="Whether organization receives foundation grants (evidence of external vetting)"
    )
    reports_outcomes: Optional[bool] = Field(None, description="Whether organization reports outcomes vs just outputs")
    publishes_impact_stories: Optional[bool] = Field(
        None, description="Whether organization publishes beneficiary impact stories"
    )
    has_theory_of_change: Optional[bool] = Field(
        None, description="Whether organization uses a logic model or theory of change"
    )
    theory_of_change: Optional[str] = Field(
        None, description="The organization's theory of change (how they believe their work creates impact)"
    )
    tracks_progress_over_time: Optional[bool] = Field(
        None, description="Whether organization tracks progress metrics over time"
    )
    # Website outcomes summary (from impact pages)
    website_outcomes_summary: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Structured outcomes from website impact pages"
    )

    ceo_name: Optional[str] = Field(None, description="CEO/Executive Director name")
    ceo_compensation: Optional[float] = Field(None, description="CEO compensation from IRS 990")

    # ========================================================================
    # Staff & Volunteers (from IRS 990)
    # ========================================================================
    employees_count: Optional[int] = Field(None, description="Number of employees")
    volunteers_count: Optional[int] = Field(None, description="Number of volunteers")

    # ========================================================================
    # Contact & Online Presence (from Website + Candid + CN)
    # ========================================================================
    website_url: Optional[str] = Field(None, description="Official website URL")
    contact_email: Optional[str] = Field(None, description="Contact email")
    contact_phone: Optional[str] = Field(None, description="Contact phone")
    address: Optional[str] = Field(None, description="Physical address")
    city: Optional[str] = Field(None, description="City")
    state: Optional[str] = Field(None, description="State")
    zip: Optional[str] = Field(None, description="ZIP code")
    founded_year: Optional[int] = Field(None, description="Year charity was founded")

    # Donation Information (from Website)
    donation_methods: List[str] = Field(
        default_factory=list, description="Available donation methods (online, check, etc.)"
    )
    tax_deductible: Optional[bool] = Field(None, description="Whether donations are tax deductible")
    volunteer_opportunities: Optional[bool] = Field(None, description="Whether volunteer opportunities available")

    # ========================================================================
    # Zakat Eligibility (from Website scraping + enrichment)
    # ========================================================================
    zakat_claim_detected: Optional[bool] = Field(
        None, description="Whether charity explicitly claims zakat eligibility on website"
    )
    zakat_claim_evidence: Optional[str] = Field(None, description="Evidence of zakat claim (quote or location)")
    zakat_categories_served: Optional[List[str]] = Field(
        None, description="Asnaf categories served (e.g. fuqara, masakin, fisabilillah)"
    )
    zakat_policy_url: Optional[str] = Field(None, description="URL of charity's zakat policy page")
    zakat_verification_confidence: Optional[float] = Field(
        None, description="Confidence score for zakat verification (0-1)"
    )
    islamic_identity_signals: Optional[dict] = Field(
        None, description="Dict of islamic identity signal names to their values"
    )

    # ========================================================================
    # Evidence & Evaluation (from V2 enrichment)
    # ========================================================================
    # NOTE: candid_seal is defined above in Transparency & Governance section
    has_outcome_methodology: Optional[bool] = Field(
        None, description="Whether charity documents methodology for measuring outcomes"
    )
    has_multi_year_metrics: Optional[bool] = Field(None, description="Whether charity tracks metrics across 3+ years")
    third_party_evaluated: Optional[bool] = Field(
        None, description="Whether charity has been evaluated by third-party evaluators"
    )
    evaluation_sources: List[str] = Field(
        default_factory=list, description="List of third-party evaluators (e.g., GiveWell, J-PAL)"
    )
    is_muslim_focused: Optional[bool] = Field(
        None, description="Whether charity primarily serves Muslim community (for counterfactual)"
    )

    # ========================================================================
    # Cause Area & Risk (from V2 enrichment)
    # ========================================================================
    detected_cause_area: Optional[str] = Field(
        None, description="Detected cause area (GLOBAL_HEALTH, HUMANITARIAN, EDUCATION_GLOBAL, etc.)"
    )
    cause_area_confidence: float = Field(0.0, description="Confidence in cause area detection (0-1)")
    primary_category: Optional[str] = Field(
        None, description="Internal primary category (e.g., ADVOCACY_CIVIC, BASIC_NEEDS)"
    )
    cause_tags: List[str] = Field(default_factory=list, description="Internal cause tags for donor discovery")
    program_focus_tags: List[str] = Field(
        default_factory=list, description="Internal program focus tags for cross-category matching"
    )
    conflict_zones: List[str] = Field(
        default_factory=list, description="Conflict zones where charity operates (for risk scoring)"
    )

    # Candid metrics tracking (for evidence scoring)
    candid_metrics_count: int = Field(0, description="Number of metrics tracked in Candid profile")
    candid_max_years_tracked: int = Field(0, description="Maximum years of data for any Candid metric")

    # ========================================================================
    # Website Transparency Signals (B4: feeds into TrustScorer transparency)
    # ========================================================================
    website_reports_annual_report: bool = Field(False, description="Website links to or mentions annual report")
    website_reports_methodology: bool = Field(False, description="Website describes impact measurement methodology")
    website_reports_outcome_metrics: bool = Field(
        False, description="Website reports specific outcome metrics (not just outputs)"
    )
    website_reports_board_info: bool = Field(False, description="Website discloses board/leadership information")
    website_disclosure_richness: int = Field(0, ge=0, le=4, description="Count of disclosure signals (0-4)")

    # ========================================================================
    # Website Evidence Claims (B1: for corroboration with third-party data)
    # ========================================================================
    website_claims_rcts: bool = Field(False, description="Website claims RCT evidence for interventions")
    website_claims_third_party_eval: bool = Field(False, description="Website claims third-party evaluation")
    website_claims_longitudinal: bool = Field(False, description="Website claims longitudinal/multi-year tracking")

    # ========================================================================
    # GiveWell Data (for effective altruism benchmarks)
    # ========================================================================
    is_givewell_top_charity: Optional[bool] = Field(None, description="Whether charity is a GiveWell top charity")
    givewell_evidence_rating: Optional[str] = Field(None, description="GiveWell evidence rating (A, B, C)")
    givewell_cost_per_life_saved: Optional[float] = Field(None, description="GiveWell cost per life saved estimate ($)")
    givewell_cost_effectiveness_multiplier: Optional[float] = Field(
        None, description="GiveWell cost-effectiveness vs cash transfers (higher = more cost-effective)"
    )
    givewell_cause_area: Optional[str] = Field(None, description="GiveWell cause area classification")

    # ========================================================================
    # Data Source Tracking
    # ========================================================================
    data_sources_available: List[str] = Field(
        default_factory=list, description="Which sources provided data (cn, propublica, candid, website)"
    )
    data_freshness_days: Dict[str, int] = Field(default_factory=dict, description="Age of data per source in days")
    source_attribution: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Maps field names to their source info: {field: {source, method, value}}"
    )
    last_updated: Optional[datetime] = Field(None, description="Most recent data update across all sources")

    # ========================================================================
    # Corroboration Status (for high-stakes fields)
    # ========================================================================
    corroboration_status: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Tracks which high-stakes fields passed/failed cross-source corroboration. "
        "Format: {field_name: {passed: bool, sources: [...], reason: str}}",
    )

    # ========================================================================
    # Reconciliation (adversarial contradiction signals)
    # ========================================================================
    contradiction_signals: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Contradiction signals from the reconciliation phase (deterministic cross-reference checks)",
    )
    reconciliation_completeness_gaps: List[str] = Field(
        default_factory=list,
        description="Metrics that could not be re-derived despite partial source data being available",
    )

    # ========================================================================
    # Calculated Fields
    # ========================================================================

    @property
    def has_outcome_metrics(self) -> bool:
        """Check if charity reports outcome metrics (not just outputs)."""
        return len(self.outcomes) > 0 or len(self.impact_metrics) > 0

    @property
    def data_completeness_score(self) -> float:
        """
        Calculate data completeness (0-1) based on critical fields.

        Checks presence of key fields across all categories.
        """
        critical_fields = [
            self.mission,
            self.program_expense_ratio,
            self.total_revenue,
            self.cn_overall_score,
            self.candid_seal,
            self.beneficiaries_served_annually,
            len(self.programs) > 0,
            len(self.populations_served) > 0,
        ]

        available = sum(1 for field in critical_fields if field)
        return available / len(critical_fields)

    @property
    def cost_per_beneficiary(self) -> Optional[float]:
        """Calculate cost per beneficiary if data available."""
        if self.total_expenses and self.beneficiaries_served_annually and self.beneficiaries_served_annually > 0:
            return self.total_expenses / self.beneficiaries_served_annually
        return None

    @property
    def has_candid_seal(self) -> bool:
        """Check if charity has any Candid transparency seal."""
        return self.candid_seal is not None

    @property
    def candid_seal_level(self) -> int:
        """
        Get numeric seal level (0-4).

        0 = None, 1 = Bronze, 2 = Silver, 3 = Gold, 4 = Platinum
        """
        seal_levels = {
            "Bronze": 1,
            "Silver": 2,
            "Gold": 3,
            "Platinum": 4,
        }
        if self.candid_seal is None:
            return 0
        return seal_levels.get(self.candid_seal, 0)

    @model_validator(mode="after")
    def _cross_field_validation(self) -> "CharityMetrics":
        """Validate cross-field consistency (warnings only, never rejects data)."""
        _logger = logging.getLogger(__name__)

        # 1. Expense ratios should sum to ~1.0
        ratios = [
            r
            for r in [self.program_expense_ratio, self.admin_expense_ratio, self.fundraising_expense_ratio]
            if r is not None
        ]
        if len(ratios) >= 2:
            total = sum(ratios)
            if total > 1.05 or total < 0.8:
                _logger.warning(f"Expense ratios sum to {total:.2f} (expected ~1.0) for {self.ein}")

        # 2. Founded year sanity
        if self.founded_year is not None:
            current_year = datetime.now(timezone.utc).year
            if self.founded_year < 1800 or self.founded_year > current_year:
                _logger.warning(
                    f"Founded year {self.founded_year} outside valid range [1800, {current_year}] for {self.ein}"
                )

        # 3. Revenue/expense consistency
        if (
            self.total_expenses is not None
            and self.total_revenue is not None
            and self.total_revenue > 0
            and self.total_expenses > self.total_revenue * 3
        ):
            _logger.warning(f"Expenses ({self.total_expenses:,}) > 3x revenue ({self.total_revenue:,}) for {self.ein}")

        return self


# ============================================================================
# Corroboration Helper
# ============================================================================


@dataclass
class CorroborationResult:
    """Result of a cross-source corroboration check."""

    passed: bool
    value: Any  # The corroborated value (or None/False if failed)
    sources: List[str] = field(default_factory=list)
    reason: str = ""


class CrossSourceCorroborator:
    """
    Cross-source corroboration for high-stakes fields.

    Certain fields materially affect charity scores and shouldn't be trusted
    from a single LLM extraction. This class requires 2+ sources to agree
    before setting these fields.

    High-stakes fields requiring corroboration:
    1. zakat_claim_detected: Require website extraction + (URL contains 'zakat' OR explicit zakat text)
    2. has_financial_audit: Require website claim + (audit PDF detected OR Form 990 mentions audit)
    3. third_party_evaluated: Require website claim + (actual CN profile with score OR Candid profile exists)
    """

    @staticmethod
    def corroborate_zakat_claim(
        ein: str,
        name: str,
        discovered_profile: Optional[Dict[str, Any]],
        website_profile: Optional[Dict[str, Any]],
        charity_website: Optional[str] = None,
    ) -> CorroborationResult:
        """
        Corroborate zakat claim detection.

        Requires website extraction + (URL contains 'zakat' OR explicit zakat text in content).
        This ensures we don't mark charities as zakat-eligible based on a single LLM hallucination.

        Args:
            ein: Charity EIN
            name: Charity name
            discovered_profile: Discovered data from web search
            website_profile: Website extracted data
            charity_website: The charity's primary website URL (for shared platform validation)

        Returns:
            CorroborationResult with corroboration details
        """
        sources = []
        reasons = []

        # Source 1: Check discovered_profile (from Gemini Search Grounding)
        discovered_zakat = {}
        if discovered_profile:
            discovered_zakat = discovered_profile.get(SECTION_ZAKAT, {})

        discovered_accepts = discovered_zakat.get("accepts_zakat", False)
        discovered_url = discovered_zakat.get("accepts_zakat_url", "")
        discovered_confidence = discovered_zakat.get("zakat_verification_confidence", 0.0)
        discovered_evidence = (discovered_zakat.get("accepts_zakat_evidence") or "").strip()

        # Shared platform guard: if the discovered zakat URL is from a shared donation
        # platform (Donorbox, GoFundMe, etc.) and doesn't match the charity's own
        # campaign page, reject ALL discovery-based evidence since it originates from
        # a different organization's page on the same platform.
        discovery_url_owned = _is_url_owned_by_charity(discovered_url, charity_website)
        if not discovery_url_owned and discovered_url:
            logger.warning(
                f"Rejecting all discovery-based zakat evidence for {ein} ({name}): "
                f"{discovered_url} does not belong to charity (website: {charity_website})"
            )

        if discovered_accepts and discovered_confidence >= 0.5 and discovery_url_owned:
            sources.append("discovered_profile")
            reasons.append(f"Discovered via search (confidence={discovered_confidence:.2f})")

        # Source 1b: Explicit discovered-language evidence.
        # Some sites mention zakat on giving pages that are missed by website extraction.
        # If discovery returns clear first-party positive phrasing, count this as an
        # explicit evidence signal (still gated by minimum discovery confidence).
        # Also gated by URL ownership - evidence from another org's page is not valid.
        has_discovered_explicit_zakat_evidence = False
        if discovered_accepts and discovered_confidence >= 0.5 and discovered_evidence and discovery_url_owned:
            evidence_lower = discovered_evidence.lower()
            positive_patterns = [
                "zakat eligible",
                "zakat-eligible",
                "we are zakat",
                "accepts zakat",
                "accept zakat",
                "your zakat contributions",
                "pay your zakat",
                "give your zakat",
            ]
            negative_patterns = [
                "not zakat eligible",
                "not zakat-eligible",
                "do not accept zakat",
                "does not accept zakat",
                "don't accept zakat",
                "not zakat compliant",
            ]
            if any(p in evidence_lower for p in positive_patterns) and not any(
                n in evidence_lower for n in negative_patterns
            ):
                has_discovered_explicit_zakat_evidence = True
                sources.append("discovered_explicit_zakat_text")
                reasons.append("Discovered evidence includes explicit zakat-acceptance language")

        # Source 2: Check if URL explicitly contains 'zakat'
        # Also gated by URL ownership check above
        if discovered_url and "zakat" in discovered_url.lower() and discovery_url_owned:
            sources.append("url_pattern")
            reasons.append(f"URL contains 'zakat': {discovered_url}")

        # Source 3: Check website_profile for explicit zakat mentions
        if website_profile:
            # Check accepts_zakat flag with evidence (set by website extractor)
            # This is the primary signal from the website extraction LLM
            if website_profile.get("accepts_zakat"):
                zakat_evidence = website_profile.get("zakat_evidence", "")
                zakat_url = website_profile.get("zakat_url", "")
                sources.append("website_accepts_zakat")
                evidence_str = zakat_evidence or "Website extraction detected zakat acceptance"
                if zakat_url:
                    evidence_str += f" ({zakat_url})"
                reasons.append(evidence_str)

            # Check donation methods
            donation_methods = website_profile.get("donation_methods", []) or []
            if any("zakat" in str(m).lower() for m in donation_methods):
                sources.append("website_donation_methods")
                reasons.append("Website donation methods mention zakat")

            # Check mission/programs for zakat mentions
            mission = website_profile.get("mission", "") or ""
            programs = website_profile.get("programs", []) or []
            if "zakat" in mission.lower() or any("zakat" in str(p).lower() for p in programs):
                sources.append("website_content")
                reasons.append("Website mission/programs mention zakat")

        # Source 4: Check name for definitive zakat indicators
        name_lower = name.lower()
        definitive_names = {"baitulmaal", "baytulmaal", "bait ul maal", "zakat foundation", "zakat fund", "zakaat"}
        name_has_zakat = any(dn in name_lower for dn in definitive_names)
        if name_has_zakat:
            sources.append("organization_name")
            reasons.append(f"Organization name implies zakat: {name}")

        # Source 5: Check if zakat was verified via direct HTTP page check (not LLM)
        # This is a deterministic check that fetches /zakat or /donate pages and looks
        # for zakat keywords - independent from the LLM search grounding result
        if discovered_zakat.get("direct_page_verified"):
            direct_url = discovered_zakat.get("accepts_zakat_url", "")
            if _is_url_owned_by_charity(direct_url, charity_website):
                sources.append("zakat_page_direct")
                reasons.append(f"Zakat page verified directly at {direct_url}")
            else:
                logger.warning(
                    f"Rejecting direct zakat verification for {ein} ({name}): {direct_url} "
                    f"does not belong to charity (website: {charity_website})"
                )

        # Corroboration logic:
        # - Direct page verification is sufficient (charity's own website is source of truth)
        # - Definitive name (e.g., "Zakat Foundation") is sufficient
        # - Website extraction with zakat keyword in evidence is sufficient
        #   (the LLM found actual "zakat" text on the charity's website)
        # - Otherwise need 2+ sources to prevent LLM hallucinations
        unique_sources = list(set(sources))
        has_direct_verification = "zakat_page_direct" in unique_sources

        # Check if website extraction found zakat keyword evidence
        has_website_zakat_evidence = False
        if website_profile and website_profile.get("accepts_zakat"):
            zakat_evidence = (website_profile.get("zakat_evidence") or "").lower()
            # Trust if evidence explicitly mentions "zakat" keyword
            if "zakat" in zakat_evidence:
                has_website_zakat_evidence = True

        passed = (
            has_direct_verification
            or name_has_zakat
            or has_website_zakat_evidence
            or has_discovered_explicit_zakat_evidence
            or len(unique_sources) >= 2
        )

        if not passed and len(unique_sources) == 1:
            logger.warning(
                f"Zakat claim for {ein} ({name}) failed corroboration: "
                f"only 1 source ({unique_sources[0]}). "
                f"Requires direct page verification, definitive name, website zakat evidence, or 2+ sources."
            )

        return CorroborationResult(
            passed=passed,
            value=passed,  # True if corroborated, False otherwise
            sources=unique_sources,
            reason="; ".join(reasons) if reasons else "No corroborating evidence found",
        )

    @staticmethod
    def corroborate_financial_audit(
        ein: str,
        name: str,
        cn_profile: Optional[Dict[str, Any]],
        candid_profile: Optional[Dict[str, Any]],
        website_profile: Optional[Dict[str, Any]],
        propublica_990: Optional[Dict[str, Any]],
    ) -> CorroborationResult:
        """
        Corroborate financial audit status.

        Requires multiple signals:
        - Website claim + (audit PDF detected in pdf_extracted_data OR Form 990 mentions audit)
        - OR high CN accountability score (>=85) which requires audit
        - OR Candid Gold/Platinum seal which requires transparency

        Args:
            ein: Charity EIN
            name: Charity name
            cn_profile: Charity Navigator data
            candid_profile: Candid profile data
            website_profile: Website extracted data
            propublica_990: ProPublica/IRS 990 data

        Returns:
            CorroborationResult with corroboration details
        """
        sources = []
        reasons = []

        # Source 1: CN explicit has_financial_audit field
        if cn_profile and cn_profile.get("has_financial_audit"):
            sources.append("charity_navigator")
            reasons.append("CN reports has_financial_audit=True")

        # Source 2: High CN accountability score (>=85) - CN requires audit for high scores
        cn_accountability = (cn_profile or {}).get("accountability_score")
        if cn_accountability and cn_accountability >= 85:
            sources.append("cn_accountability_score")
            reasons.append(f"CN accountability score {cn_accountability}>=85 implies audit")

        # Source 3: Candid Gold/Platinum seal (requires transparency)
        candid_seal = (candid_profile or {}).get("candid_seal")
        if candid_seal and candid_seal.lower() in ("gold", "platinum"):
            sources.append("candid_seal")
            reasons.append(f"Candid {candid_seal} seal implies audit")

        # Source 4: Website absorptive_capacity_data mentions audit
        if website_profile:
            absorptive_data = website_profile.get("absorptive_capacity_data", {}) or {}
            if absorptive_data.get("has_independent_audit"):
                sources.append("website_absorptive_capacity")
                reasons.append("Website claims independent audit")

        # Source 5: PDF extracted data contains audit document
        if website_profile:
            llm_pdfs = website_profile.get("llm_extracted_pdfs", []) or []
            for pdf in llm_pdfs:
                pdf_type = pdf.get("type", "").lower()
                pdf_file = pdf.get("file", "").lower()
                if "audit" in pdf_type or "audit" in pdf_file:
                    sources.append("pdf_audit_document")
                    reasons.append(f"Audit PDF detected: {pdf.get('file', 'unknown')}")
                    break

            pdf_sources = website_profile.get("pdf_extraction_sources", []) or []
            for pdf in pdf_sources:
                pdf_type = pdf.get("type", "").lower()
                pdf_file = pdf.get("file", "").lower()
                if "audit" in pdf_type or "audit" in pdf_file:
                    sources.append("pdf_audit_source")
                    reasons.append(f"Audit PDF source: {pdf.get('file', 'unknown')}")
                    break

        # Source 6: High revenue (>$2M usually requires legal audit)
        total_revenue = (propublica_990 or {}).get("total_revenue") or (cn_profile or {}).get("total_revenue")
        if total_revenue and total_revenue > 2_000_000:
            sources.append("revenue_implies_audit")
            reasons.append(f"Revenue ${total_revenue:,.0f} > $2M implies legal audit requirement")

        # Corroboration logic: Need 2+ independent sources
        unique_sources = list(set(sources))
        passed = len(unique_sources) >= 2

        # Special case: If we have only revenue signal, that's not enough alone
        if unique_sources == ["revenue_implies_audit"]:
            passed = False

        if not passed and len(unique_sources) == 1:
            logger.warning(
                f"Financial audit for {ein} ({name}) failed corroboration: "
                f"only 1 source ({unique_sources[0]}). "
                f"Requires 2+ sources."
            )

        return CorroborationResult(
            passed=passed,
            value=passed,
            sources=unique_sources,
            reason="; ".join(reasons) if reasons else "No corroborating evidence found",
        )

    @staticmethod
    def corroborate_third_party_evaluation(
        ein: str,
        name: str,
        cn_profile: Optional[Dict[str, Any]],
        candid_profile: Optional[Dict[str, Any]],
        website_profile: Optional[Dict[str, Any]],
        givewell_profile: Optional[Dict[str, Any]],
    ) -> CorroborationResult:
        """
        Corroborate third-party evaluation status.

        Requires website claim + (actual CN profile with score exists OR Candid profile exists).
        This prevents claiming third-party evaluation when there's no actual external data.

        Args:
            ein: Charity EIN
            name: Charity name
            cn_profile: Charity Navigator data (must have actual score)
            candid_profile: Candid profile data
            website_profile: Website extracted data
            givewell_profile: GiveWell top charity data

        Returns:
            CorroborationResult with corroboration details
        """
        sources = []
        reasons = []
        evaluation_sources_found = []

        # Source 1: Website claims third-party evaluation
        website_claims = False
        if website_profile:
            evidence_data = website_profile.get("evidence_of_impact_data", {}) or {}
            third_party_evals = evidence_data.get("third_party_evaluations", []) or []
            if third_party_evals:
                website_claims = True
                sources.append("website_claims")
                reasons.append(f"Website claims evaluations: {', '.join(third_party_evals[:3])}")
                evaluation_sources_found.extend(third_party_evals)

            if evidence_data.get("has_rcts"):
                website_claims = True
                sources.append("website_claims_rct")
                reasons.append("Website claims RCT evidence")
                if "RCT" not in evaluation_sources_found:
                    evaluation_sources_found.append("RCT")

        # Source 2: Actual CN profile with score (proves CN evaluated them)
        if cn_profile:
            cn_score = cn_profile.get("overall_score")
            if cn_score is not None and cn_score > 0:
                sources.append("charity_navigator_rated")
                reasons.append(f"CN rated with score {cn_score}")
                if "Charity Navigator" not in evaluation_sources_found:
                    evaluation_sources_found.append("Charity Navigator")

        # Source 3: Candid profile exists with any content
        if candid_profile:
            # Candid having a profile with seal or metrics means they evaluated
            if candid_profile.get("candid_seal") or candid_profile.get("metrics"):
                sources.append("candid_profile")
                reasons.append(f"Candid profile exists with seal={candid_profile.get('candid_seal')}")
                if "Candid" not in evaluation_sources_found:
                    evaluation_sources_found.append("Candid")

        # Source 4: GiveWell top charity (strongest evidence)
        if givewell_profile and givewell_profile.get("is_top_charity"):
            sources.append("givewell_top_charity")
            reasons.append("GiveWell top charity")
            if "GiveWell" not in evaluation_sources_found:
                evaluation_sources_found.append("GiveWell")

        # Corroboration logic:
        # - Need website claim + at least one actual third-party source
        # - OR direct GiveWell/CN/Candid presence (which IS the third-party evaluation)
        unique_sources = list(set(sources))

        # Having actual third-party data IS proof of evaluation
        has_actual_third_party = any(
            s in unique_sources for s in ["charity_navigator_rated", "candid_profile", "givewell_top_charity"]
        )

        # Pass if we have actual third-party data OR (website claims + third-party data)
        passed = has_actual_third_party

        if not passed and website_claims:
            logger.warning(
                f"Third-party evaluation for {ein} ({name}) failed corroboration: "
                f"website claims evaluations but no actual third-party data found. "
                f"Sources: {unique_sources}"
            )

        return CorroborationResult(
            passed=passed,
            value=passed,
            sources=unique_sources,
            reason="; ".join(reasons) if reasons else "No corroborating evidence found",
        )


# ============================================================================
# Aggregation Logic
# ============================================================================


class CharityMetricsAggregator:
    """
    Aggregate data from all sources into unified CharityMetrics model.

    Precedence rules:
    - Financial data: ProPublica (IRS 990) preferred, then CN
    - Scores: CN only
    - Programs/Mission: Candid preferred, then Website, then CN
    - Transparency: Candid preferred, then CN
    """

    @staticmethod
    def aggregate(
        charity_id: int,
        ein: str,
        cn_profile: Optional[Dict[str, Any]] = None,
        propublica_990: Optional[Dict[str, Any]] = None,
        candid_profile: Optional[Dict[str, Any]] = None,
        grants_profile: Optional[Dict[str, Any]] = None,
        website_profile: Optional[Dict[str, Any]] = None,
        website_context: Optional[Dict[str, Any]] = None,
        givewell_profile: Optional[Dict[str, Any]] = None,
        discovered_profile: Optional[Dict[str, Any]] = None,
        bbb_profile: Optional[Dict[str, Any]] = None,
        source_attribution: Optional[Dict[str, Dict[str, Any]]] = None,
        source_timestamps: Optional[Dict[str, Any]] = None,
    ) -> CharityMetrics:
        """
        Aggregate all source data into CharityMetrics.

        Args:
            charity_id: Database ID
            ein: EIN
            cn_profile: Charity Navigator data
            propublica_990: ProPublica/IRS 990 data
            candid_profile: Candid profile data
            grants_profile: Form 990 grants data (Schedule I domestic + Schedule F foreign)
            website_profile: Charity website data
            website_context: Full website source payload (e.g., includes page_extractions)
            discovered_profile: Discovered data from web search (zakat verification, etc.)

        Returns:
            CharityMetrics instance
        """
        # Calculate data freshness from source timestamps
        # S-001/S-002: Use UTC consistently instead of stripping timezone info
        data_freshness = {}
        if source_timestamps:
            now = datetime.now(timezone.utc)
            for source, scraped_at in source_timestamps.items():
                if scraped_at:
                    try:
                        # Handle string or datetime
                        if isinstance(scraped_at, str):
                            scraped_dt = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
                        else:
                            scraped_dt = scraped_at
                        # Ensure scraped_dt is timezone-aware (assume UTC if naive)
                        if scraped_dt.tzinfo is None:
                            scraped_dt = scraped_dt.replace(tzinfo=timezone.utc)
                        days_old = (now - scraped_dt).days
                        data_freshness[source] = max(0, days_old)
                    except (ValueError, TypeError):
                        pass

        # Initialize with empty data
        metrics_data = {
            "charity_id": charity_id,
            "ein": ein,
            "data_sources_available": [],
            "data_freshness_days": data_freshness,
            "source_attribution": source_attribution or {},
        }

        # Track which sources are available
        if cn_profile:
            metrics_data["data_sources_available"].append("charity_navigator")
        if propublica_990:
            metrics_data["data_sources_available"].append("propublica")
        if candid_profile:
            metrics_data["data_sources_available"].append("candid")
        if grants_profile:
            metrics_data["data_sources_available"].append("form990_grants")
        if website_profile:
            metrics_data["data_sources_available"].append("website")
        if givewell_profile:
            metrics_data["data_sources_available"].append("givewell")
        if bbb_profile:
            metrics_data["data_sources_available"].append("bbb")

        # ====================================================================
        # Source Attribution Helper
        # ====================================================================
        attr = metrics_data["source_attribution"]

        def _track(field: str, source: str, value: Any, method: str = "selection"):
            """Record which source provided a field value."""
            if value is not None:
                attr[field] = {"source_name": source, "value": value, "method": method}

        # ====================================================================
        # Aggregate Core Identification
        # ====================================================================
        # Priority: Candid > CN > ProPublica > Website > Unknown
        # Note: All validators use 'name' field (per spec)
        metrics_data["name"] = (
            candid_profile.get("name")
            if candid_profile and candid_profile.get("name")
            else cn_profile.get("name")
            if cn_profile and cn_profile.get("name")
            else propublica_990.get("name")
            if propublica_990 and propublica_990.get("name")
            else website_profile.get("name")
            if website_profile and website_profile.get("name")
            else "Unknown"
        )

        # ====================================================================
        # Aggregate Mission & Programs
        # ====================================================================
        # Prefer Candid, then Website, then CN
        metrics_data["mission"] = (
            candid_profile.get("mission")
            if candid_profile and candid_profile.get("mission")
            else website_profile.get("mission")
            if website_profile and website_profile.get("mission")
            else cn_profile.get("mission")
            if cn_profile
            else None
        )
        if metrics_data["mission"]:
            _track("mission", "candid" if candid_profile and candid_profile.get("mission") else "website" if website_profile and website_profile.get("mission") else "charity_navigator", metrics_data["mission"])

        metrics_data["tagline"] = _first_non_none(
            candid_profile.get("tagline") if candid_profile else None,
            cn_profile.get("tagline") if cn_profile else None,
        )

        metrics_data["vision"] = candid_profile.get("vision") if candid_profile else None

        metrics_data["strategic_goals"] = candid_profile.get("strategic_goals") if candid_profile else None

        # Programs (combine from Candid and Website with deduplication)
        programs = []
        if candid_profile and candid_profile.get("programs"):
            programs.extend(candid_profile["programs"])
        if website_profile and website_profile.get("programs"):
            programs.extend(website_profile["programs"])

        # Deduplicate programs using fuzzy matching (optimized)
        def deduplicate_programs(program_list: List[str]) -> List[str]:
            """Remove duplicate programs using fuzzy string matching.

            Optimizations:
            - Pre-compute lowercase versions once
            - Use set for O(1) exact match lookup
            - Only do expensive fuzzy matching when necessary
            """
            from difflib import SequenceMatcher

            if not program_list:
                return []

            deduplicated: List[str] = []
            seen_exact: set[str] = set()  # O(1) lookup for exact matches
            seen_lower: List[str] = []  # For substring/fuzzy checks

            for prog in program_list:
                prog_lower = prog.lower().strip()

                # Fast path: exact match (O(1))
                if prog_lower in seen_exact:
                    continue

                # Check substring containment and fuzzy similarity
                is_duplicate = False
                for existing_lower in seen_lower:
                    # Substring check (fast)
                    if prog_lower in existing_lower or existing_lower in prog_lower:
                        is_duplicate = True
                        break
                    # Fuzzy match (expensive - only if lengths are similar)
                    # Skip fuzzy if length difference > 30% (can't be 85% similar)
                    len_ratio = len(prog_lower) / len(existing_lower) if existing_lower else 0
                    if 0.7 <= len_ratio <= 1.43:  # Within 30% length
                        similarity = SequenceMatcher(None, prog_lower, existing_lower).ratio()
                        if similarity > 0.85:
                            is_duplicate = True
                            break

                if not is_duplicate:
                    deduplicated.append(prog)
                    seen_exact.add(prog_lower)
                    seen_lower.append(prog_lower)

            return deduplicated

        metrics_data["programs"] = deduplicate_programs(programs)

        # Program descriptions (detailed descriptions from website)
        program_descriptions = []
        if website_profile and website_profile.get("program_descriptions"):
            program_descriptions.extend(website_profile["program_descriptions"])
        if candid_profile and candid_profile.get("program_descriptions"):
            program_descriptions.extend(candid_profile["program_descriptions"])
        metrics_data["program_descriptions"] = program_descriptions

        # ====================================================================
        # Aggregate Beneficiaries & Reach
        # ====================================================================
        # Try multiple sources for beneficiaries data and preserve citation metadata.
        beneficiaries = None
        beneficiaries_source_meta: Dict[str, Any] | None = None

        def _normalize_beneficiary_count(raw_value: Any) -> Optional[int]:
            """Normalize raw beneficiary values to an integer headcount."""
            if raw_value is None:
                return None
            if isinstance(raw_value, (int, float)):
                value = float(raw_value)
            elif isinstance(raw_value, str):
                try:
                    import re

                    val_str = raw_value.lower()
                    multiplier = 1
                    if "million" in val_str:
                        multiplier = 1_000_000
                    elif "thousand" in val_str:
                        multiplier = 1_000
                    match = re.search(r"[\d,]+\.?\d*", val_str)
                    if not match:
                        return None
                    value = float(match.group().replace(",", "")) * multiplier
                except (ValueError, TypeError):
                    return None
            else:
                return None

            # Ignore tiny values that are unlikely to be annual beneficiary counts.
            if value < 100:
                return None
            return int(value)

        def _is_citable_url(url: Any) -> bool:
            return isinstance(url, str) and url.startswith(("http://", "https://"))

        def _set_beneficiary_value(
            raw_value: Any,
            *,
            source_name: str,
            source_url: Any,
            source_path: str,
            method: str = "direct",
        ) -> bool:
            nonlocal beneficiaries, beneficiaries_source_meta
            normalized = _normalize_beneficiary_count(raw_value)
            if normalized is None:
                return False

            resolved_source_url = source_url if _is_citable_url(source_url) else None
            if resolved_source_url and source_name.lower().startswith("charity website"):
                resolved_source_url = choose_website_evidence_url(
                    website_context or website_profile,
                    resolved_source_url,
                    source_name=source_name,
                    claim="Beneficiaries served annually",
                    source_path=source_path,
                )

            beneficiaries = normalized
            beneficiaries_source_meta = {
                "source_name": source_name,
                "source_url": resolved_source_url,
                "source_path": source_path,
                "method": method,
                "value": normalized,
            }
            return True

        # 1) Direct field from Candid (preferred if available)
        if candid_profile:
            _set_beneficiary_value(
                candid_profile.get("beneficiaries_served"),
                source_name="Candid",
                source_url=candid_profile.get("candid_url"),
                source_path="candid_profile.beneficiaries_served",
            )

        # 2) Direct field from website extraction
        if beneficiaries is None and website_profile:
            _set_beneficiary_value(
                website_profile.get("beneficiaries_served"),
                source_name="Charity Website",
                source_url=website_profile.get("url"),
                source_path="website_profile.beneficiaries_served",
            )

        # 3) ummah_gap_data fallback (website extractor)
        if beneficiaries is None and website_profile:
            ummah_gap = website_profile.get("ummah_gap_data", {})
            _set_beneficiary_value(
                ummah_gap.get("beneficiary_count"),
                source_name="Charity Website",
                source_url=website_profile.get("url"),
                source_path="website_profile.ummah_gap_data.beneficiary_count",
            )

        # 4) Extract from impact_metrics.metrics (pattern matching)
        if beneficiaries is None and website_profile:
            impact = website_profile.get("impact_metrics", {})
            metrics_dict = impact.get("metrics", {})

            annual_patterns = ["annually", "annual", "per_year", "yearly"]
            people_patterns = [
                "people",
                "beneficiar",
                "served",
                "impacted",
                "reached",
                "helped",
                "patient",
                "student",
                "household",
                "family",
                "client",
                "recipient",
                "individual",
                "participant",
                "refugee",
                "orphan",
            ]

            annual_choice: tuple[int, str] | None = None
            fallback_choice: tuple[int, str] | None = None

            for key, raw_value in metrics_dict.items():
                key_lower = key.lower()
                if not any(p in key_lower for p in people_patterns):
                    continue

                normalized = _normalize_beneficiary_count(raw_value)
                if normalized is None:
                    continue

                is_annual = any(p in key_lower for p in annual_patterns)
                if is_annual and (annual_choice is None or normalized < annual_choice[0]):
                    annual_choice = (normalized, key)
                elif not is_annual and (fallback_choice is None or normalized < fallback_choice[0]):
                    fallback_choice = (normalized, key)

            selected = annual_choice or fallback_choice
            if selected:
                value, field_key = selected
                _set_beneficiary_value(
                    value,
                    source_name="Charity Website",
                    source_url=website_profile.get("url"),
                    source_path=f"website_profile.impact_metrics.metrics.{field_key}",
                    method="pattern_match",
                )

        metrics_data["beneficiaries_served_annually"] = beneficiaries
        if beneficiaries_source_meta:
            # FIX #20: Website-only beneficiary claims → annotate as unverified
            src_name = (beneficiaries_source_meta.get("source_name") or "").lower()
            if "website" in src_name and not (candid_profile and candid_profile.get("beneficiaries_served")):
                beneficiaries_source_meta["verification_status"] = "unverified"
                beneficiaries_source_meta["verification_note"] = (
                    "Website-only beneficiary count; not corroborated by Candid or other sources"
                )
            metrics_data["source_attribution"]["beneficiaries_served_annually"] = beneficiaries_source_meta

        # FIX #6: Website extractor stores "populations_served", not "beneficiaries"
        metrics_data["populations_served"] = (
            candid_profile.get("populations_served", [])
            if candid_profile and candid_profile.get("populations_served")
            else website_profile.get("populations_served", [])
            if website_profile
            else []
        )
        if metrics_data["populations_served"]:
            _track("populations_served", "candid" if candid_profile and candid_profile.get("populations_served") else "website", metrics_data["populations_served"])

        metrics_data["geographic_coverage"] = (
            candid_profile.get("geographic_coverage", [])
            if candid_profile
            else website_profile.get("geographic_coverage", [])
            if website_profile
            else []
        )
        if metrics_data["geographic_coverage"]:
            _track("geographic_coverage", "candid" if candid_profile else "website", metrics_data["geographic_coverage"])

        # Populate Candid-specific fields (for ZakatAssessor raw access)
        if candid_profile:
            metrics_data["candid_populations_served"] = candid_profile.get("populations_served")
            metrics_data["candid_programs"] = candid_profile.get("programs")
            metrics_data["candid_geographic_areas_served"] = candid_profile.get("geographic_coverage")
            metrics_data["candid_seal"] = candid_profile.get("candid_seal")

            # Extract Candid metrics tracking data (for Evidence scoring)
            candid_metrics = candid_profile.get("metrics", [])
            if candid_metrics:
                metrics_data["candid_metrics_count"] = len(candid_metrics)
                max_years = 0
                for m in candid_metrics:
                    year_data = m.get("year_data", [])
                    if year_data:
                        # Compute actual year span (not just entry count)
                        years = [yd.get("year") for yd in year_data if isinstance(yd, dict) and yd.get("year")]
                        if years:
                            span = max(years) - min(years) + 1
                            max_years = max(max_years, span)
                        else:
                            max_years = max(max_years, len(year_data))
                metrics_data["candid_max_years_tracked"] = max_years

        # ====================================================================
        # Aggregate Outcomes & Impact
        # ====================================================================
        metrics_data["outcomes"] = candid_profile.get("outcomes", []) if candid_profile else []

        metrics_data["impact_metrics"] = website_profile.get("impact_metrics", {}) if website_profile else {}

        # ====================================================================
        # Aggregate PDF-Extracted Data (Form 990s, Annual Reports, etc.)
        # ====================================================================
        # PDF data is stored in website_profile from web_collector.py
        if website_profile:
            # Full LLM-extracted PDF data (programs, outcomes, theory of change, financials)
            metrics_data["pdf_extracted_data"] = website_profile.get("llm_extracted_pdfs", [])

            # Aggregated outcomes from all PDFs with source attribution
            metrics_data["pdf_outcomes"] = website_profile.get("outcomes_data", [])

        # ====================================================================
        # Aggregate Grantmaking (Form 990 Schedule I/F)
        # ====================================================================
        # Combine domestic (Schedule I) and foreign (Schedule F) grants
        grants_made = []
        if grants_profile:
            grants_made.extend(grants_profile.get("domestic_grants", []))
            grants_made.extend(grants_profile.get("foreign_grants", []))
        metrics_data["grants_made"] = grants_made
        if grants_made:
            _track("grants_made", "form990_grants", len(grants_made), "aggregation")

        # grants_received is not available from Form 990 (would need to look at other orgs' 990s)
        metrics_data["grants_received"] = []

        # ====================================================================
        # Aggregate Financial Metrics (ProPublica preferred, then CN)
        # Fiscal-year-aware: income statement fields must come from ONE
        # source when PP and CN report different fiscal years.
        # ====================================================================
        _INCOME_STMT_FIELDS = [
            "total_revenue", "total_expenses", "program_expenses",
            "admin_expenses", "fundraising_expenses",
        ]
        _BALANCE_SHEET_FIELDS = ["total_assets", "total_liabilities", "net_assets"]

        if propublica_990:
            # Always pull PP income statement fields first (may be None)
            for f in _INCOME_STMT_FIELDS:
                metrics_data[f] = propublica_990.get(f)
            # Revenue breakdown fields (PP only)
            metrics_data["total_contributions"] = propublica_990.get("total_contributions")
            metrics_data["program_service_revenue"] = propublica_990.get("program_service_revenue")
            metrics_data["investment_income"] = propublica_990.get("investment_income")
            # Balance sheet (point-in-time, always safe to pull)
            for f in _BALANCE_SHEET_FIELDS:
                metrics_data[f] = propublica_990.get(f)
                _track(f, "propublica", metrics_data.get(f))
            # Staffing
            metrics_data["employees_count"] = propublica_990.get("employees_count")
            metrics_data["volunteers_count"] = propublica_990.get("volunteers_count")
            # Form 990 filing status
            is_form_990_exempt = propublica_990.get("form_990_exempt", False)
            metrics_data["form_990_exempt"] = is_form_990_exempt
            if is_form_990_exempt:
                metrics_data["form_990_exempt_reason"] = propublica_990.get("form_990_exempt_reason")
            else:
                metrics_data["form_990_exempt_reason"] = ""
            metrics_data["no_filings"] = propublica_990.get("no_filings", False)
            # Track the tax year of the financial data
            tax_year = propublica_990.get("tax_year")
            if tax_year is not None:
                try:
                    metrics_data["financial_data_tax_year"] = int(tax_year)
                except (ValueError, TypeError):
                    pass

        # --- Fiscal-year-aware CN gap-fill for income statement ---
        if cn_profile:
            # Determine fiscal years
            pp_tax_year = metrics_data.get("financial_data_tax_year")
            cn_fy = cn_profile.get("fiscal_year")
            try:
                cn_fiscal_year = int(cn_fy) if cn_fy is not None else None
            except (ValueError, TypeError):
                cn_fiscal_year = None

            years_match = (
                pp_tax_year is not None
                and cn_fiscal_year is not None
                and pp_tax_year == cn_fiscal_year
            )
            years_differ = (
                pp_tax_year is not None
                and cn_fiscal_year is not None
                and pp_tax_year != cn_fiscal_year
            )

            # Count how many income statement fields PP provided (non-None)
            pp_income_count = sum(
                1 for f in _INCOME_STMT_FIELDS if metrics_data.get(f) is not None
            )
            # Count how many CN provides
            cn_income_count = sum(
                1 for f in _INCOME_STMT_FIELDS
                if cn_profile.get(f) is not None
                or (f == "admin_expenses" and (
                    cn_profile.get("admin_expenses") is not None
                    or cn_profile.get("administrative_expenses") is not None
                ))
            )

            if years_differ:
                if pp_income_count < 3 and cn_income_count >= 3:
                    # PP has too few fields — use CN for ALL income statement
                    for f in _INCOME_STMT_FIELDS:
                        if f == "admin_expenses":
                            metrics_data[f] = _first_non_none(
                                cn_profile.get("admin_expenses"),
                                cn_profile.get("administrative_expenses"),
                            )
                        else:
                            metrics_data[f] = cn_profile.get(f)
                    metrics_data["financial_data_source"] = "charity_navigator"
                    metrics_data["financial_data_tax_year"] = cn_fiscal_year
                    logger.info(
                        f"Using CN income statement for {ein}: PP year={pp_tax_year} "
                        f"(only {pp_income_count} fields), CN year={cn_fiscal_year} "
                        f"({cn_income_count} fields)"
                    )
                else:
                    # PP has enough fields OR CN doesn't — keep PP, no gap-fill
                    metrics_data["financial_data_source"] = "propublica"
                    if cn_income_count >= 3:
                        logger.info(
                            f"Keeping PP income statement for {ein}: PP year={pp_tax_year} "
                            f"({pp_income_count} fields), CN year={cn_fiscal_year} skipped"
                        )
            elif years_match or pp_tax_year is None:
                # Same year or PP didn't provide year — safe to gap-fill
                gap_filled = False
                for f in _INCOME_STMT_FIELDS:
                    if metrics_data.get(f) is None:
                        if f == "admin_expenses":
                            val = _first_non_none(
                                cn_profile.get("admin_expenses"),
                                cn_profile.get("administrative_expenses"),
                            )
                        else:
                            val = cn_profile.get(f)
                        if val is not None:
                            metrics_data[f] = val
                            gap_filled = True
                if gap_filled:
                    metrics_data["financial_data_source"] = "mixed"
                elif propublica_990:
                    metrics_data["financial_data_source"] = "propublica"
            elif not propublica_990:
                # No PP data at all — use CN entirely
                for f in _INCOME_STMT_FIELDS:
                    if f == "admin_expenses":
                        metrics_data[f] = _first_non_none(
                            cn_profile.get("admin_expenses"),
                            cn_profile.get("administrative_expenses"),
                        )
                    else:
                        metrics_data[f] = cn_profile.get(f)
                metrics_data["financial_data_source"] = "charity_navigator"

            # Balance sheet: always safe to gap-fill (point-in-time snapshots)
            for f in _BALANCE_SHEET_FIELDS:
                if metrics_data.get(f) is None:
                    val = cn_profile.get(f)
                    if val is not None:
                        metrics_data[f] = val
                        _track(f, "charity_navigator", val)

            # Fallback tax year from CN if PP didn't provide one
            if metrics_data.get("financial_data_tax_year") is None and cn_fiscal_year is not None:
                metrics_data["financial_data_tax_year"] = cn_fiscal_year

        # Set financial_data_source if not set yet
        if not metrics_data.get("financial_data_source"):
            if propublica_990 and not cn_profile:
                metrics_data["financial_data_source"] = "propublica"
            elif cn_profile and not propublica_990:
                metrics_data["financial_data_source"] = "charity_navigator"

        # FIX #4: CN ratios are fallback, not overwrite — only set if not already present
        if cn_profile:
            if metrics_data.get("program_expense_ratio") is None and cn_profile.get("program_expense_ratio") is not None:
                metrics_data["program_expense_ratio"] = cn_profile.get("program_expense_ratio")
            if metrics_data.get("admin_expense_ratio") is None and cn_profile.get("admin_expense_ratio") is not None:
                metrics_data["admin_expense_ratio"] = cn_profile.get("admin_expense_ratio")
            if metrics_data.get("fundraising_expense_ratio") is None and cn_profile.get("fundraising_expense_ratio") is not None:
                metrics_data["fundraising_expense_ratio"] = cn_profile.get("fundraising_expense_ratio")
            if metrics_data.get("working_capital_ratio") is None and cn_profile.get("working_capital_ratio") is not None:
                metrics_data["working_capital_ratio"] = cn_profile.get("working_capital_ratio")

        # Fallback to PDF-extracted data for expense ratios (from 990 PDFs on charity website)
        # This is the bullet-proof fallback when CN data is missing
        if not metrics_data.get("program_expense_ratio") and website_profile:
            # Check financial_data from PDF extraction
            pdf_financials = website_profile.get("financial_data", {})
            if pdf_financials.get("program_expense_ratio"):
                metrics_data["program_expense_ratio"] = pdf_financials["program_expense_ratio"]
                # Also grab the raw expense data if available
                if not metrics_data.get("program_expenses") and pdf_financials.get("program_expenses"):
                    metrics_data["program_expenses"] = pdf_financials["program_expenses"]
                if not metrics_data.get("admin_expenses") and pdf_financials.get("management_expenses"):
                    metrics_data["admin_expenses"] = pdf_financials["management_expenses"]
                if not metrics_data.get("fundraising_expenses") and pdf_financials.get("fundraising_expenses"):
                    metrics_data["fundraising_expenses"] = pdf_financials["fundraising_expenses"]

            # Also check llm_extracted_pdfs for financials
            llm_pdfs = website_profile.get("llm_extracted_pdfs", [])
            if not metrics_data.get("program_expense_ratio") and llm_pdfs:
                for pdf in llm_pdfs:
                    extracted = pdf.get("extracted_data", {})
                    financials = extracted.get("financials", {})
                    if financials.get("program_expense_ratio"):
                        metrics_data["program_expense_ratio"] = financials["program_expense_ratio"]
                        if not metrics_data.get("program_expenses") and financials.get("program_expenses"):
                            metrics_data["program_expenses"] = financials["program_expenses"]
                        break  # Use first available

        # ====================================================================
        # GIK / Noncash contributions (Fix 1)
        # ====================================================================
        noncash = grants_profile.get("noncash_contributions") if grants_profile else None
        if noncash is not None and noncash > 0:
            metrics_data["noncash_contributions"] = noncash
            total_contribs = metrics_data.get("total_contributions")
            if total_contribs and total_contribs > 0:
                noncash_ratio = noncash / total_contribs
                metrics_data["noncash_ratio"] = min(noncash_ratio, 1.0)
                # Cash-adjusted program ratio: only compute when GIK > 10%
                if noncash_ratio > 0.10:
                    prog_exp = metrics_data.get("program_expenses")
                    total_exp = metrics_data.get("total_expenses")
                    if prog_exp is not None and total_exp is not None and total_exp > noncash:
                        adjusted = (prog_exp - noncash) / (total_exp - noncash)
                        metrics_data["cash_adjusted_program_ratio"] = max(0.0, adjusted)

        # ====================================================================
        # Domestic burn rate (Fix 2)
        # ====================================================================
        total_foreign = grants_profile.get("total_foreign_grants") if grants_profile else None
        total_exp = metrics_data.get("total_expenses")
        if total_foreign is not None and total_foreign > 0 and total_exp and total_exp > 0:
            metrics_data["domestic_burn_rate"] = max(0.0, min(1.0, 1.0 - (total_foreign / total_exp)))

        # ====================================================================
        # Reserves months (Fix 3) — net_assets / monthly expenses
        # ====================================================================
        net_assets = metrics_data.get("net_assets")
        if net_assets is not None and total_exp and total_exp > 0:
            monthly_expenses = total_exp / 12.0
            if monthly_expenses > 0:
                metrics_data["reserves_months"] = net_assets / monthly_expenses

        # ====================================================================
        # Aggregate CN Scores
        # ====================================================================
        if cn_profile:
            # Only use CN score if fully rated (not just Encompass Award)
            if cn_profile.get("cn_is_rated"):
                metrics_data["cn_overall_score"] = cn_profile.get("overall_score")
                metrics_data["cn_financial_score"] = cn_profile.get("financial_score")
                metrics_data["cn_accountability_score"] = cn_profile.get("accountability_score")
            metrics_data["cn_beacons"] = cn_profile.get("beacons", [])

        # ====================================================================
        # FIX #5: Aggregate BBB Wise Giving Alliance Data
        # ====================================================================
        if bbb_profile:
            metrics_data["bbb_accredited"] = bbb_profile.get("meets_standards")
            metrics_data["bbb_standards_met_count"] = bbb_profile.get("standards_met_count")
            metrics_data["bbb_governance_pass"] = bbb_profile.get("governance_pass")
            metrics_data["bbb_effectiveness_pass"] = bbb_profile.get("effectiveness_pass")
            metrics_data["bbb_finances_pass"] = bbb_profile.get("finances_pass")
            _track("bbb_accredited", "bbb", metrics_data.get("bbb_accredited"))

        # ====================================================================
        # Aggregate Transparency & Governance
        # ====================================================================
        metrics_data["candid_seal"] = candid_profile.get("candid_seal") if candid_profile else None

        # Board size: take max across sources (parsing bugs can undercount)
        # Website stores leadership as a list of people, derive board_size from it
        website_board = None
        if website_profile:
            website_board = website_profile.get("board_size")
            if not website_board:
                leadership = website_profile.get("leadership") or []
                if isinstance(leadership, list) and len(leadership) > 0:
                    website_board = len(leadership)
        board_candidates = [
            candid_profile.get("board_size") if candid_profile else None,
            propublica_990.get("board_size") if propublica_990 else None,
            website_board,
        ]
        valid_boards = [b for b in board_candidates if b and b > 0]
        metrics_data["board_size"] = max(valid_boards) if valid_boards else None
        if valid_boards:
            max_board = max(valid_boards)
            board_src = "candid" if candid_profile and candid_profile.get("board_size") == max_board else "propublica" if propublica_990 and propublica_990.get("board_size") == max_board else "website"
            _track("board_size", board_src, max_board, "max_across_sources")

        metrics_data["independent_board_members"] = (
            candid_profile.get("independent_board_members") if candid_profile else None
        )
        _track("independent_board_members", "candid", metrics_data.get("independent_board_members"))

        metrics_data["ceo_name"] = _first_non_none(
            candid_profile.get("ceo_name") if candid_profile else None,
            cn_profile.get("ceo_name") if cn_profile else None,
        )

        # Charity Navigator has individual CEO compensation (from keyPersons array).
        # ProPublica's compensation_current_officers is AGGREGATE for all officers — not CEO-specific.
        # Prefer CN individual CEO comp; fall back to ProPublica aggregate only when nothing else is available.
        metrics_data["ceo_compensation"] = _first_non_none(
            cn_profile.get("ceo_compensation") if cn_profile else None,
            candid_profile.get("ceo_compensation") if candid_profile else None,
            propublica_990.get("compensation_current_officers") if propublica_990 else None,
        )
        if metrics_data.get("ceo_compensation") is not None:
            comp_src = "charity_navigator" if cn_profile and cn_profile.get("ceo_compensation") is not None else "candid" if candid_profile and candid_profile.get("ceo_compensation") is not None else "propublica"
            _track("ceo_compensation", comp_src, metrics_data["ceo_compensation"])

        # Additional transparency & governance fields
        metrics_data["irs_990_available"] = True if propublica_990 else None

        metrics_data["annual_report_published"] = _first_non_none(
            candid_profile.get("has_annual_report") if candid_profile else None,
            website_profile.get("has_annual_report") if website_profile else None,
        )
        if metrics_data.get("annual_report_published") is not None:
            ar_src = "candid" if candid_profile and candid_profile.get("has_annual_report") is not None else "website"
            _track("annual_report_published", ar_src, metrics_data["annual_report_published"])

        metrics_data["receives_foundation_grants"] = _first_non_none(
            candid_profile.get("receives_foundation_grants") if candid_profile else None,
            website_profile.get("foundation_grants") if website_profile else None,
        )

        metrics_data["reports_outcomes"] = _first_non_none(
            candid_profile.get("reports_outcomes") if candid_profile else None,
            website_profile.get("reports_outcomes") if website_profile else None,
        )
        if metrics_data.get("reports_outcomes") is not None:
            ro_src = "candid" if candid_profile and candid_profile.get("reports_outcomes") is not None else "website"
            _track("reports_outcomes", ro_src, metrics_data["reports_outcomes"])

        metrics_data["publishes_impact_stories"] = _first_non_none(
            candid_profile.get("publishes_impact_stories") if candid_profile else None,
            website_profile.get("has_impact_stories") if website_profile else None,
        )

        # Theory of change: check Candid → website → discovery service
        # Discovery service claims require a URL or evidence text to be trusted;
        # without either, the claim is unverifiable (phantom ToC).
        discovered_toc = discovered_profile.get(SECTION_THEORY_OF_CHANGE, {}) if discovered_profile else {}
        discovered_toc_verified = discovered_toc.get("has_theory_of_change") and (
            discovered_toc.get("url") or discovered_toc.get("evidence")
        )
        metrics_data["has_theory_of_change"] = (
            candid_profile.get("has_theory_of_change")
            if candid_profile and candid_profile.get("has_theory_of_change")
            else bool(website_profile.get("theory_of_change"))
            if website_profile and website_profile.get("theory_of_change")
            else bool(discovered_toc_verified)
        )

        # Theory of change text (website or PDF or discovery evidence)
        metrics_data["theory_of_change"] = (
            website_profile.get("theory_of_change")
            if website_profile and website_profile.get("theory_of_change")
            else discovered_toc.get("evidence")
            if discovered_toc_verified
            else None
        )
        if metrics_data.get("theory_of_change"):
            toc_src = "website" if website_profile and website_profile.get("theory_of_change") else "discovered"
            _track("theory_of_change", toc_src, True)

        # Website outcomes summary (from impact pages)
        metrics_data["website_outcomes_summary"] = (
            website_profile.get("outcomes_summary", {}) if website_profile else {}
        )

        # ====================================================================
        # FIX #1: Wire discovery evaluations/outcomes/awards into scoring
        # ====================================================================
        if discovered_profile:
            # Evaluations: merge discovered evaluators into evaluation_sources
            discovered_evals = discovered_profile.get(SECTION_EVALUATIONS, {})
            if discovered_evals and discovered_evals.get("third_party_evaluated"):
                evaluators = discovered_evals.get("evaluators", [])
                existing_sources = metrics_data.get("evaluation_sources", [])
                for evaluator in evaluators:
                    eval_name = evaluator.get("name", "") if isinstance(evaluator, dict) else str(evaluator)
                    if eval_name and eval_name not in existing_sources:
                        existing_sources.append(eval_name)
                metrics_data["evaluation_sources"] = existing_sources
                if existing_sources:
                    metrics_data["third_party_evaluated"] = True

            # Outcomes: merge discovered metrics into outcomes list
            discovered_outcomes = discovered_profile.get(SECTION_OUTCOMES, {})
            if discovered_outcomes and discovered_outcomes.get("has_reported_outcomes"):
                outcome_metrics = discovered_outcomes.get("metrics", [])
                existing_outcomes = metrics_data.get("outcomes", [])
                for om in outcome_metrics:
                    if isinstance(om, dict):
                        desc = om.get("metric", "")
                        value = om.get("value", "")
                        if desc:
                            outcome_str = f"{desc}: {value}" if value else desc
                            if outcome_str not in existing_outcomes:
                                existing_outcomes.append(outcome_str)
                metrics_data["outcomes"] = existing_outcomes
                # Mark reports_outcomes if discovered outcomes found
                if not metrics_data.get("reports_outcomes"):
                    metrics_data["reports_outcomes"] = True

            # Awards: store in evaluation_sources and mark has_awards
            discovered_awards = discovered_profile.get(SECTION_AWARDS, {})
            if discovered_awards and discovered_awards.get("has_awards"):
                awards_list = discovered_awards.get("awards", [])
                existing_sources = metrics_data.get("evaluation_sources", [])
                for award in awards_list:
                    if isinstance(award, dict):
                        award_name = award.get("name", "")
                        issuer = award.get("issuer", "")
                        label = f"{award_name} ({issuer})" if issuer else award_name
                    else:
                        label = str(award)
                    if label and label not in existing_sources:
                        existing_sources.append(label)
                metrics_data["evaluation_sources"] = existing_sources

        metrics_data["tracks_progress_over_time"] = _first_non_none(
            candid_profile.get("tracks_progress") if candid_profile else None,
            website_profile.get("tracks_metrics_over_time") if website_profile else None,
        )

        # ====================================================================
        # Extract Evidence of Impact Data (from website extractor)
        # ====================================================================
        if website_profile:
            evidence_data = website_profile.get("evidence_of_impact_data", {})

            # Outcome methodology
            if evidence_data.get("measurement_methodology"):
                metrics_data["has_outcome_methodology"] = True
            elif evidence_data.get("tracks_outcomes_vs_outputs"):
                metrics_data["has_outcome_methodology"] = True

            # Multi-year metrics tracking
            if evidence_data.get("longitudinal_tracking"):
                metrics_data["has_multi_year_metrics"] = True

            # Third-party evaluations
            third_party_evals = evidence_data.get("third_party_evaluations", [])
            if third_party_evals:
                metrics_data["third_party_evaluated"] = True
                metrics_data["evaluation_sources"] = third_party_evals

            # RCTs (rare but valuable)
            if evidence_data.get("has_rcts"):
                metrics_data["third_party_evaluated"] = True
                if "RCT" not in metrics_data.get("evaluation_sources", []):
                    metrics_data.setdefault("evaluation_sources", []).append("RCT")

            # Theory of change (fallback if not already set)
            if not metrics_data.get("theory_of_change") and evidence_data.get("theory_of_change"):
                metrics_data["theory_of_change"] = evidence_data.get("theory_of_change")
                metrics_data["has_theory_of_change"] = True

            # Outcome examples (add to outcomes list)
            outcome_examples = evidence_data.get("outcome_examples", [])
            if outcome_examples:
                existing_outcomes = metrics_data.get("outcomes", [])
                metrics_data["outcomes"] = existing_outcomes + outcome_examples

            # ================================================================
            # B4: Website Transparency Signals (for TrustScorer transparency)
            # ================================================================
            # Check for annual report disclosure
            has_annual_report = bool(
                website_profile.get("annual_report_url")
                or website_profile.get("has_annual_report")
                or metrics_data.get("annual_report_published")
            )

            # Check for methodology disclosure
            has_methodology = bool(
                evidence_data.get("measurement_methodology") or evidence_data.get("tracks_outcomes_vs_outputs")
            )

            # Check for outcome metrics disclosure (not just outputs)
            has_outcome_metrics = bool(
                evidence_data.get("outcome_examples")
                or evidence_data.get("has_outcome_data")
                or metrics_data.get("reports_outcomes")
            )

            # Check for board/governance disclosure
            absorptive_data = website_profile.get("absorptive_capacity_data", {})
            has_board_info = bool(
                absorptive_data.get("independent_board_members")
                or absorptive_data.get("board_size")
                or website_profile.get("leadership_team")
            )

            metrics_data["website_reports_annual_report"] = has_annual_report
            metrics_data["website_reports_methodology"] = has_methodology
            metrics_data["website_reports_outcome_metrics"] = has_outcome_metrics
            metrics_data["website_reports_board_info"] = has_board_info
            metrics_data["website_disclosure_richness"] = sum(
                [
                    has_annual_report,
                    has_methodology,
                    has_outcome_metrics,
                    has_board_info,
                ]
            )

            # ================================================================
            # B1: Website Evidence Claims (for corroboration with third-party)
            # ================================================================
            metrics_data["website_claims_rcts"] = bool(evidence_data.get("has_rcts"))
            metrics_data["website_claims_third_party_eval"] = bool(evidence_data.get("third_party_evaluations"))
            metrics_data["website_claims_longitudinal"] = bool(evidence_data.get("longitudinal_tracking"))

        # ====================================================================
        # Aggregate Contact & Online Presence
        # ====================================================================
        metrics_data["website_url"] = _first_non_none(
            cn_profile.get("website_url") if cn_profile else None,
            website_profile.get("url") if website_profile else None,
        )

        metrics_data["contact_email"] = _first_non_none(
            candid_profile.get("contact_email") if candid_profile else None,
            website_profile.get("contact_email") if website_profile else None,
        )

        metrics_data["address"] = _first_non_none(
            cn_profile.get("address") if cn_profile else None,
            candid_profile.get("address") if candid_profile else None,
        )

        # City/State/ZIP - prefer ProPublica (IRS data), then CN, then Candid
        metrics_data["city"] = (
            propublica_990.get("city")
            if propublica_990 and propublica_990.get("city")
            else cn_profile.get("city")
            if cn_profile and cn_profile.get("city")
            else candid_profile.get("city")
            if candid_profile
            else None
        )
        metrics_data["state"] = (
            propublica_990.get("state")
            if propublica_990 and propublica_990.get("state")
            else cn_profile.get("state")
            if cn_profile and cn_profile.get("state")
            else candid_profile.get("state")
            if candid_profile
            else None
        )
        metrics_data["zip"] = (
            propublica_990.get("zipcode")
            if propublica_990 and propublica_990.get("zipcode")
            else propublica_990.get("zip")
            if propublica_990 and propublica_990.get("zip")
            else cn_profile.get("zip")
            if cn_profile and cn_profile.get("zip")
            else candid_profile.get("zip")
            if candid_profile
            else None
        )

        # Founded year — waterfall: website > candid > propublica > charity navigator
        # Candid/PP/CN store IRS ruling year (501c3 grant date), not true founding.
        metrics_data["founded_year"] = (
            website_profile.get("founded_year")
            if website_profile and website_profile.get("founded_year")
            else candid_profile.get("irs_ruling_year")
            if candid_profile and candid_profile.get("irs_ruling_year")
            else propublica_990.get("irs_ruling_year")
            if propublica_990 and propublica_990.get("irs_ruling_year")
            else cn_profile.get("irs_ruling_year")
            if cn_profile and cn_profile.get("irs_ruling_year")
            else None
        )
        if metrics_data.get("founded_year"):
            fy_src = "website" if website_profile and website_profile.get("founded_year") else "candid" if candid_profile and candid_profile.get("irs_ruling_year") else "propublica" if propublica_990 and propublica_990.get("irs_ruling_year") else "charity_navigator"
            _track("founded_year", fy_src, metrics_data["founded_year"])

        metrics_data["donation_methods"] = website_profile.get("donation_methods", []) if website_profile else []

        metrics_data["tax_deductible"] = website_profile.get("tax_deductible") if website_profile else None

        metrics_data["volunteer_opportunities"] = (
            website_profile.get("volunteer_opportunities") if website_profile else None
        )

        # ====================================================================
        # Aggregate Zakat Eligibility (CONFIDENCE-BASED VERIFICATION)
        # ====================================================================
        # Uses the centralized ZakatEligibilityService which:
        # 1. Auto-accepts orgs with definitive zakat names (e.g., "Baitulmaal")
        # 2. Applies strict confidence thresholds for secular charities
        # 3. Uses lower thresholds for orgs with Islamic identity markers
        # 4. Requires evidence URL for non-Islamic organizations
        #
        # Configuration is in config/scoring_weights.yaml under zakat.eligibility_verification
        discovered_zakat = None
        if discovered_profile:
            discovered_zakat = discovered_profile.get(SECTION_ZAKAT, {})

        accepts_zakat, zakat_evidence = determine_zakat_eligibility(
            name=metrics_data.get("name", ""),
            mission=metrics_data.get("mission"),
            discovered_zakat=discovered_zakat,
            ein=ein,
        )

        metrics_data["zakat_claim_detected"] = accepts_zakat
        if zakat_evidence:
            metrics_data["zakat_claim_evidence"] = zakat_evidence

        # ====================================================================
        # Detect Cause Area from internal content signals
        # ====================================================================
        # NTEE is intentionally excluded from cause classification because it is
        # too coarse and often misaligned with current program reality.
        detected_cause = None
        cause_confidence = 0.0

        text_content = " ".join(
            [
                metrics_data.get("name") or "",
                metrics_data.get("mission") or "",
                " ".join(metrics_data.get("programs", [])),
            ]
        ).lower()

        cause_keywords = {
            "GLOBAL_HEALTH": ["health", "medical", "disease", "hospital", "clinic", "vaccine"],
            "HUMANITARIAN": ["relief", "disaster", "emergency", "refugee", "humanitarian", "crisis"],
            "EXTREME_POVERTY": ["poverty", "hunger", "food", "water", "sanitation", "basic needs"],
            "EDUCATION_GLOBAL": ["education", "school", "literacy", "learning", "student", "teacher"],
            "DOMESTIC_POVERTY": ["homeless", "housing", "job training", "domestic", "community"],
            "ADVOCACY": [
                "advocacy",
                "rights",
                "policy",
                "awareness",
                "campaign",
                "representation",
                "civic",
                "public interest",
                "congressional",
            ],
            "RELIGIOUS_CULTURAL": ["mosque", "islamic", "religious", "faith", "spiritual", "cultural"],
        }

        best_match = None
        best_count = 0
        for cause, keywords in cause_keywords.items():
            count = sum(1 for kw in keywords if kw in text_content)
            if count > best_count:
                best_count = count
                best_match = cause

        if best_match and best_count >= 2:
            detected_cause = best_match
            cause_confidence = min(0.7, 0.18 * best_count)

        # GiveWell remains a secondary fallback only when internal signals are weak.
        if not detected_cause and givewell_profile and givewell_profile.get("cause_area"):
            gw_cause = givewell_profile.get("cause_area", "").upper()
            givewell_cause_map = {
                "MEDICAL_HEALTH": "GLOBAL_HEALTH",
                "HEALTH": "GLOBAL_HEALTH",
                "GLOBAL HEALTH": "GLOBAL_HEALTH",
                "MALARIA": "GLOBAL_HEALTH",
                "DEWORMING": "GLOBAL_HEALTH",
                "NUTRITION": "GLOBAL_HEALTH",
                "CASH_TRANSFERS": "EXTREME_POVERTY",
                "POVERTY": "EXTREME_POVERTY",
                "POVERTY ALLEVIATION": "EXTREME_POVERTY",
                "ANIMAL WELFARE": "ADVOCACY",
                "CLIMATE CHANGE": "ADVOCACY",
            }
            detected_cause = givewell_cause_map.get(gw_cause, gw_cause)
            if detected_cause:
                cause_confidence = max(cause_confidence, 0.5)

        metrics_data["detected_cause_area"] = detected_cause
        metrics_data["cause_area_confidence"] = cause_confidence

        # ====================================================================
        # Detect Muslim-Focused Status
        # ====================================================================
        is_muslim = False
        text_for_muslim = " ".join(
            [
                metrics_data.get("name") or "",
                metrics_data.get("mission") or "",
                " ".join(metrics_data.get("programs", [])),
            ]
        ).lower()

        muslim_indicators = [
            "islamic",
            "muslim",
            "zakat",
            "sadaqah",
            "ummah",
            "masjid",
            "mosque",
            "halal",
            "ramadan",
            "eid",
            "quran",
            "allah",
            "imam",
            "islamic relief",
            "zakat foundation",
            "helping hand",
            "penny appeal",
            "human appeal",
        ]
        is_muslim = any(indicator in text_for_muslim for indicator in muslim_indicators)
        metrics_data["is_muslim_focused"] = is_muslim

        # ====================================================================
        # Infer Missing Fields from Other Signals
        # ====================================================================

        # Infer financial audit status
        # Priority:
        # 1. Explicit flag (from CN or other sources)
        # 2. High CN Accountability Score (CN requires audit for high scores)
        # 3. Candid Platinum/Gold Seal (requires financial transparency)
        # 4. High Revenue (>$2M usually implies legal requirement for audit)
        has_audit = False

        if cn_profile and cn_profile.get("has_financial_audit"):
            has_audit = True
        elif (metrics_data.get("cn_accountability_score") or 0) >= 85:
            has_audit = True
        elif metrics_data.get("candid_seal") in ["Platinum", "Gold"]:
            has_audit = True
        elif (metrics_data.get("total_revenue") or 0) > 2_000_000:
            has_audit = True

        metrics_data["has_financial_audit"] = has_audit
        if has_audit:
            audit_src = "charity_navigator" if cn_profile and cn_profile.get("has_financial_audit") else "charity_navigator" if (metrics_data.get("cn_accountability_score") or 0) >= 85 else "candid" if metrics_data.get("candid_seal") in ["Platinum", "Gold"] else "propublica"
            _track("has_financial_audit", audit_src, True, "inferred")

        # Backfill employees/volunteers from PDF data if missing from IRS 990
        if not metrics_data.get("employees_count") and metrics_data.get("pdf_extracted_data"):
            for pdf in metrics_data["pdf_extracted_data"]:
                if not isinstance(pdf, dict):
                    continue
                extracted = pdf.get("extracted_data", {})

                # Check governance section
                gov = extracted.get("governance", {})
                if gov.get("employees_count"):
                    metrics_data["employees_count"] = gov.get("employees_count")

                if not metrics_data.get("volunteers_count") and gov.get("volunteers_count"):
                    metrics_data["volunteers_count"] = gov.get("volunteers_count")

                # Stop if we found both
                if metrics_data.get("employees_count") and metrics_data.get("volunteers_count"):
                    break

        # ====================================================================
        # Extract GiveWell Data (for effective altruism benchmarks)
        # ====================================================================
        if givewell_profile:
            metrics_data["is_givewell_top_charity"] = givewell_profile.get("is_top_charity")
            metrics_data["givewell_evidence_rating"] = givewell_profile.get("evidence_rating")
            metrics_data["givewell_cost_per_life_saved"] = givewell_profile.get("cost_per_life_saved")
            metrics_data["givewell_cost_effectiveness_multiplier"] = givewell_profile.get("cash_benchmark_multiplier")
            metrics_data["givewell_cause_area"] = givewell_profile.get("cause_area")

            # GiveWell top charities should be marked as third-party evaluated
            if givewell_profile.get("is_top_charity"):
                metrics_data["third_party_evaluated"] = True
                if "GiveWell" not in metrics_data.get("evaluation_sources", []):
                    metrics_data.setdefault("evaluation_sources", []).append("GiveWell")

        # S-007: Normalize expense ratios to 0-1 scale
        # Common source formats: 0-1 (decimal), 0-100 (percentage), 0-1000 (rare)
        for ratio_field in ["program_expense_ratio", "admin_expense_ratio", "fundraising_expense_ratio"]:
            ratio_val = metrics_data.get(ratio_field)
            if ratio_val is not None:
                if ratio_val > 100:
                    # Likely 0-1000 scale (very rare) - reject as unreliable
                    logger.warning(f"Rejecting {ratio_field}={ratio_val} (>100, likely invalid)")
                    metrics_data[ratio_field] = None
                elif ratio_val > 1:
                    # Likely 0-100 percentage scale - convert to decimal
                    metrics_data[ratio_field] = ratio_val / 100.0

        # Validate expense ratios against revenue (reject if expenses > 3x revenue)
        # This catches cases like CN reporting stale/wrong expense data
        total_revenue = metrics_data.get("total_revenue") or 0
        total_expenses = metrics_data.get("total_expenses") or 0
        if total_revenue > 0 and total_expenses > 0:
            expense_ratio = total_expenses / total_revenue
            if expense_ratio > 3.0:
                # Expense data is unreliable - null out all expense-derived metrics
                logger.warning(f"Rejecting expense ratios for {ein}: expenses/revenue ratio {expense_ratio:.1f}x > 3.0")
                for ratio_field in ["program_expense_ratio", "admin_expense_ratio", "fundraising_expense_ratio"]:
                    metrics_data[ratio_field] = None

        # ====================================================================
        # Financial Data Quality Flags
        # ====================================================================
        quality_flags: list[str] = []
        _total_rev = metrics_data.get("total_revenue") or 0
        _total_exp = metrics_data.get("total_expenses") or 0
        _prog_exp = metrics_data.get("program_expenses") or 0
        _admin_exp = metrics_data.get("admin_expenses") or 0
        _fund_exp = metrics_data.get("fundraising_expenses") or 0
        _net_assets = metrics_data.get("net_assets")

        if _prog_exp > 0 and _total_exp > 0 and _prog_exp > _total_exp:
            quality_flags.append("program_exceeds_total")
        if _admin_exp > 0 and _total_exp > 0 and _admin_exp > _total_exp:
            quality_flags.append("admin_exceeds_total")
        if _total_exp > 0 and (_prog_exp + _admin_exp + _fund_exp) > 0:
            component_sum = _prog_exp + _admin_exp + _fund_exp
            if abs(component_sum - _total_exp) / _total_exp > 0.10:
                quality_flags.append("expense_sum_mismatch")
        if _total_rev > 0 and _total_exp > 3 * _total_rev:
            quality_flags.append("expenses_exceed_3x_revenue")
        if isinstance(_net_assets, (int, float)) and _net_assets < 0:
            quality_flags.append("negative_net_assets")

        metrics_data["financial_quality_flags"] = quality_flags if quality_flags else None

        # ====================================================================
        # Cross-Source Corroboration (High-Stakes Fields)
        # ====================================================================
        # Certain fields materially affect charity scores and shouldn't be trusted
        # from a single LLM extraction. We require 2+ sources to agree.
        corroboration_status = {}
        charity_name = metrics_data.get("name", "Unknown")

        # 1. Corroborate zakat_claim_detected
        zakat_result = CrossSourceCorroborator.corroborate_zakat_claim(
            ein=ein,
            name=charity_name,
            discovered_profile=discovered_profile,
            website_profile=website_profile,
            charity_website=metrics_data.get("website_url"),
        )
        corroboration_status["zakat_claim_detected"] = {
            "passed": zakat_result.passed,
            "sources": zakat_result.sources,
            "reason": zakat_result.reason,
        }
        if not zakat_result.passed and metrics_data.get("zakat_claim_detected"):
            # Corroboration failed but initial detection was True -> reject
            logger.warning(
                f"Zakat claim for {ein} ({charity_name}) failed corroboration. "
                f"Setting zakat_claim_detected=None. Reason: {zakat_result.reason}"
            )
            metrics_data["zakat_claim_detected"] = None
            metrics_data["zakat_claim_evidence"] = f"CORROBORATION FAILED: {zakat_result.reason}"
        elif zakat_result.passed and not metrics_data.get("zakat_claim_detected"):
            # Corroboration passed but initial detection was False/None
            # This happens when website_profile.accepts_zakat is True but
            # discovered_profile is missing.
            #
            # IMPORTANT: Check denylist before overriding!
            # Initial detection may be False because the charity is in ZAKAT_DENYLIST
            # (e.g., UNICEF USA partners with zakat orgs but doesn't collect directly).
            # We must NOT override the denylist protection.
            from ..services.zakat_eligibility_service import ZAKAT_DENYLIST

            if ein in ZAKAT_DENYLIST:
                logger.info(
                    f"Zakat claim for {ein} ({charity_name}) passed corroboration but "
                    f"charity is in denylist. Keeping zakat_claim_detected=False."
                )
                # Keep as False/None - denylist takes precedence
            else:
                logger.info(
                    f"Zakat claim for {ein} ({charity_name}) corroborated from website. "
                    f"Setting zakat_claim_detected=True. Sources: {zakat_result.sources}"
                )
                metrics_data["zakat_claim_detected"] = True
                metrics_data["zakat_claim_evidence"] = zakat_result.reason

        # 2. Corroborate has_financial_audit
        audit_result = CrossSourceCorroborator.corroborate_financial_audit(
            ein=ein,
            name=charity_name,
            cn_profile=cn_profile,
            candid_profile=candid_profile,
            website_profile=website_profile,
            propublica_990=propublica_990,
        )
        corroboration_status["has_financial_audit"] = {
            "passed": audit_result.passed,
            "sources": audit_result.sources,
            "reason": audit_result.reason,
        }
        if not audit_result.passed and metrics_data.get("has_financial_audit"):
            # FIX #9: Keep value but mark as unverified instead of nulling.
            # Downstream scorers should check verification_status in source_attribution.
            logger.warning(
                f"Financial audit for {ein} ({charity_name}) failed corroboration. "
                f"Marking as unverified. Reason: {audit_result.reason}"
            )
            attr["has_financial_audit"] = {
                **(attr.get("has_financial_audit") or {}),
                "verification_status": "unverified",
                "verification_note": f"Single-source claim; {audit_result.reason}",
            }

        # 3. Corroborate third_party_evaluated
        third_party_result = CrossSourceCorroborator.corroborate_third_party_evaluation(
            ein=ein,
            name=charity_name,
            cn_profile=cn_profile,
            candid_profile=candid_profile,
            website_profile=website_profile,
            givewell_profile=givewell_profile,
        )
        corroboration_status["third_party_evaluated"] = {
            "passed": third_party_result.passed,
            "sources": third_party_result.sources,
            "reason": third_party_result.reason,
        }
        if not third_party_result.passed and metrics_data.get("third_party_evaluated"):
            logger.warning(
                f"Third-party evaluation for {ein} ({charity_name}) failed corroboration. "
                f"Setting third_party_evaluated=False. Reason: {third_party_result.reason}"
            )
            metrics_data["third_party_evaluated"] = False
            # Keep evaluation_sources for transparency, but mark as uncorroborated
            if metrics_data.get("evaluation_sources"):
                metrics_data["evaluation_sources"] = [
                    f"UNCORROBORATED: {s}" for s in metrics_data["evaluation_sources"]
                ]

        metrics_data["corroboration_status"] = corroboration_status

        # ====================================================================
        # Zakat claim flag for scorer (Fix 3: zakat hoarding)
        # ====================================================================
        metrics_data["claims_zakat"] = bool(metrics_data.get("zakat_claim_detected"))

        # ====================================================================
        # Source-Required Field Validation (Anti-Hallucination)
        # ====================================================================
        # Validate that fields requiring specific source data are only set
        # when that source data actually exists. This prevents LLM hallucination
        # of scores, seals, and other values when no underlying data supports them.
        source_data = {
            "cn_profile": cn_profile,
            "candid_profile": candid_profile,
            "website_profile": website_profile,
            "givewell_profile": givewell_profile,
            "evaluation_sources": metrics_data.get("evaluation_sources", []),
        }

        validation_result = _source_validator.validate_dict(metrics_data, source_data)
        if not validation_result.all_valid:
            nullified = validation_result.nullified_fields
            logger.warning(f"Source-required validation nullified {len(nullified)} fields for EIN {ein}: {nullified}")
            # Apply the validation (nullify invalid fields)
            _source_validator.apply_to_dict(metrics_data, source_data)

        # Create and return CharityMetrics instance
        return CharityMetrics(**metrics_data)
