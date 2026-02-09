"""
Pydantic validator for charity website data.

Validates data extracted from charity websites via LLM-assisted parsing.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SocialMedia(BaseModel):
    """Social media links."""

    model_config = ConfigDict(extra="forbid")

    facebook: Optional[str] = None
    twitter: Optional[str] = None
    instagram: Optional[str] = None
    linkedin: Optional[str] = None
    youtube: Optional[str] = None


class Leadership(BaseModel):
    """Leadership team member."""

    model_config = ConfigDict(extra="forbid")

    name: str
    title: str


class WebsiteProfile(BaseModel):
    """
    Charity website profile data extracted via LLM.

    This data is less structured than official sources (CN, Candid, IRS 990)
    but may contain unique information about programs, impact, and mission.
    """

    model_config = ConfigDict(extra="ignore")  # Allow extra fields from LLM extraction

    # Required field
    url: str = Field(..., min_length=1)

    # Basic information (per spec: use 'mission' not 'mission_statement')
    name: Optional[str] = None
    mission: Optional[str] = None
    vision_statement: Optional[str] = None

    # Programs and impact (per spec: use 'populations_served' not 'beneficiaries')
    programs: List[str] = Field(default_factory=list)
    program_descriptions: List[str] = Field(default_factory=list)
    primary_activities: List[str] = Field(default_factory=list)  # Cause areas (distinct from programs)
    populations_served: List[str] = Field(default_factory=list)
    geographic_coverage: List[str] = Field(default_factory=list)
    impact_metrics: Dict[str, Any] = Field(default_factory=dict)
    beneficiaries_served: Optional[int] = Field(None, ge=0)

    # Donation information
    donation_methods: List[str] = Field(default_factory=list)
    donation_page_url: Optional[str] = None
    donate_url: Optional[str] = None  # Alternative field name
    tax_deductible: Optional[bool] = None
    ein_mentioned: Optional[str] = None
    ein: Optional[str] = None  # Direct EIN field
    related_ein: Optional[str] = None  # EIN found on website that differs from expected (parent/subsidiary)

    # Zakat/Islamic finance fields - extracted during content-aware crawling
    accepts_zakat: Optional[bool] = None
    zakat_evidence: Optional[str] = None
    zakat_url: Optional[str] = None

    # Contact information
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None

    # Volunteer information
    volunteer_opportunities: Optional[bool] = None
    volunteer_page_url: Optional[str] = None

    # Social media (can be dict or SocialMedia object)
    social_media: Optional[Dict[str, str]] = Field(default_factory=dict)

    # Transparency and evidence (per spec)
    has_annual_report: Optional[bool] = None
    annual_report_url: Optional[str] = None
    has_impact_report: Optional[bool] = None
    impact_report_url: Optional[str] = None
    transparency_info: Optional[str] = None

    # Beneficiary and impact metrics (per spec)
    impact_claims_raw: List[str] = Field(
        default_factory=list, description="Raw text claims about impact - always captured verbatim"
    )
    beneficiary_metrics: Optional[Dict[str, Any]] = Field(
        None, description="Structured beneficiary data: total_beneficiaries, beneficiaries_year, by_program[]"
    )
    cost_metrics: Optional[Dict[str, Any]] = Field(
        None, description="Self-reported cost efficiency: cost_per_meal, cost_per_beneficiary, source"
    )

    # PDF-extracted data (from Form 990s, Annual Reports, Impact Reports)
    llm_extracted_pdfs: List[Dict[str, Any]] = Field(
        default_factory=list, description="LLM-extracted data from PDFs (programs, outcomes, theory of change)"
    )
    pdf_outcomes: List[Dict[str, Any]] = Field(
        default_factory=list, description="Outcomes data extracted from PDFs with source attribution"
    )
    outcomes_data: List[Dict[str, Any]] = Field(
        default_factory=list, description="Aggregated outcomes from all PDFs (alternative field name)"
    )
    pdf_extraction_sources: List[Dict[str, Any]] = Field(
        default_factory=list, description="PDF documents that were processed (type, file, metadata)"
    )

    # Scoring data fields (for AMAL evaluation)
    # These capture structured data about the charity's approach to change
    systemic_leverage_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Systemic change indicators: policy_wins, scalable_models, training_programs, program_type_classification (GENERATIVE/SCALABLE/MIXED/CONSUMPTIVE)",
    )
    ummah_gap_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Underserved population data: beneficiary_count, demographics, geographic_specificity, gap_evidence, orphaned_causes",
    )
    evidence_of_impact_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Evidence quality: theory_of_change, has_rcts, longitudinal_tracking, third_party_evaluations, outcome_examples",
    )
    absorptive_capacity_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Operational capacity: has_independent_audit, independent_board_members, total_revenue, financial_controls_mentioned",
    )

    # Organization details
    founded_year: Optional[int] = Field(None, ge=1800, le=2100)
    leadership: List[Leadership] = Field(default_factory=list)

    @field_validator(
        "url", "donation_page_url", "donate_url", "volunteer_page_url", "annual_report_url", "impact_report_url"
    )
    @classmethod
    def validate_url_format(cls, v: Optional[str]) -> Optional[str]:
        """Basic URL validation."""
        if v is not None and v.strip():
            v = v.strip()
            # Ensure it looks like a URL
            if not v.startswith(("http://", "https://")):
                # Try to fix common issues
                if v.startswith("www."):
                    v = f"https://{v}"
                else:
                    # Might be relative URL or malformed
                    pass  # Allow it for now, will be validated by CharityMetrics aggregator
        return v

    @field_validator("social_media")
    @classmethod
    def clean_social_media(cls, v: Optional[Dict[str, str]]) -> Dict[str, str]:
        """Remove None values from social media dict."""
        if v is None:
            return {}
        # Filter out None values
        return {k: v_val for k, v_val in v.items() if v_val is not None}

    @field_validator("ein_mentioned", "ein")
    @classmethod
    def validate_ein_if_present(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate EIN format if mentioned on website.

        EIN can be in various formats on websites, normalize to XX-XXXXXXX.
        """
        if v is not None and v.strip():
            # LLMs sometimes return the literal string "null" instead of JSON null
            if v.strip().lower() in ("null", "none", "n/a"):
                return None

            ein = v.strip().replace("-", "").replace(" ", "")

            if len(ein) == 9 and ein.isdigit():
                # Format as XX-XXXXXXX
                return f"{ein[:2]}-{ein[2:]}"
            else:
                # Invalid format, but don't fail - just return as-is
                # This is website data, so it might be malformed
                return v

        return v

    @field_validator("contact_email")
    @classmethod
    def validate_email_basic(cls, v: Optional[str]) -> Optional[str]:
        """Basic email validation."""
        if v is not None and v.strip():
            v = v.strip()
            if "@" not in v or "." not in v:
                # Invalid email, but don't fail - this is user-provided data
                pass  # Return as-is for logging/review
        return v

    @field_validator("social_media")
    @classmethod
    def filter_none_social_media(cls, v: Optional[Dict[str, str]]) -> Dict[str, str]:
        """Filter out None values from social media dict."""
        if v is None:
            return {}
        # Remove None values (LLM sometimes returns null for missing platforms)
        return {k: val for k, val in v.items() if val is not None and isinstance(val, str) and val.strip()}

    @property
    def has_donation_info(self) -> bool:
        """Check if website has donation information."""
        return bool(self.donation_methods or self.donation_page_url or self.tax_deductible is not None)

    @property
    def has_impact_data(self) -> bool:
        """Check if website reports impact metrics or outcomes."""
        return bool(self.impact_metrics or self.beneficiaries_served is not None or self.programs)

    @property
    def has_contact_info(self) -> bool:
        """Check if website has contact information."""
        return bool(self.contact_email or self.contact_phone or self.address)
