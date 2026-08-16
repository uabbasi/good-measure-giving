"""Pydantic validator for Form 990 governance data.

Validates governance data extracted from 990 XML Part VI (Governance,
Management, and Disclosure) and Part VII Section A (officers, directors,
trustees, key employees).
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Form990Officer(BaseModel):
    """One Part VII Section A entry: an officer, director, trustee, or key employee."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    title: Optional[str] = None
    average_hours_per_week: Optional[float] = None
    is_trustee_or_director: bool = False
    is_officer: bool = False
    is_key_employee: bool = False
    is_highest_compensated: bool = False
    is_former: bool = False
    reportable_comp_from_org: Optional[float] = None
    reportable_comp_from_related_orgs: Optional[float] = None
    other_compensation: Optional[float] = None


class Form990GovernanceProfile(BaseModel):
    """Form 990 governance profile, from Part VI and Part VII Section A of the
    single most recent filing (governance structure is a current-state fact,
    not something to merge across tax years like grants)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    ein: str = Field(..., pattern=r"^\d{2}-\d{7}$")
    tax_year: Optional[int] = Field(None, ge=2010, le=2030)
    object_id: Optional[str] = None

    # Part VI, Section A — Governing Body and Management
    voting_board_members: Optional[int] = Field(None, ge=0)
    independent_voting_board_members: Optional[int] = Field(None, ge=0)
    family_or_business_relationships: Optional[bool] = None
    delegates_management_duties: Optional[bool] = None
    changed_governing_documents: Optional[bool] = None
    material_diversion_or_misuse: Optional[bool] = None
    has_members_or_stockholders: Optional[bool] = None
    members_elect_governing_body: Optional[bool] = None
    decisions_subject_to_approval: Optional[bool] = None
    minutes_of_governing_body_documented: Optional[bool] = None
    minutes_of_committees_documented: Optional[bool] = None
    has_local_chapters: Optional[bool] = None

    # Part VI, Section B — Policies
    form_990_provided_to_governing_body: Optional[bool] = None
    has_conflict_of_interest_policy: Optional[bool] = None
    conflict_of_interest_annual_disclosure: Optional[bool] = None
    conflict_of_interest_monitored: Optional[bool] = None
    has_whistleblower_policy: Optional[bool] = None
    has_document_retention_policy: Optional[bool] = None
    ceo_compensation_process_independent: Optional[bool] = None
    other_officer_compensation_process_independent: Optional[bool] = None
    invests_in_joint_venture: Optional[bool] = None

    # Part VI, Section C — Disclosure
    discloses_via_own_website: Optional[bool] = None
    discloses_upon_request: Optional[bool] = None

    # Part VII, Section A
    officers: List[Form990Officer] = Field(default_factory=list)
