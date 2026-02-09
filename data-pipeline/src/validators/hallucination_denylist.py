"""
Hallucination-Prone Field Denylist.

Certain fields extracted by LLMs are known to be unreliable and frequently
hallucinated. This module documents these fields and provides utilities to
flag them as unverified until corroborated by authoritative sources.

This is a DOCUMENTATION + FLAGGING system, not a blocking system.
Fields get marked as unverified until corroborated.

Usage:
    from src.validators.hallucination_denylist import (
        is_hallucination_prone,
        get_verification_method,
        flag_unverified_fields,
    )

    # Check if a field is prone to hallucination
    if is_hallucination_prone("accepts_zakat"):
        print("This field requires verification")

    # Get the verification method for a field
    method = get_verification_method("accepts_zakat")
    # Returns: "Look for explicit zakat page, zakat calculator, or zakat-specific donation options"

    # Flag unverified fields in a data dictionary
    flagged_data = flag_unverified_fields({"accepts_zakat": True, "name": "Test"})
    # Returns: {"accepts_zakat_unverified": True, "name": "Test"}
"""

from typing import Any, Dict, Optional

# =============================================================================
# Hallucination-Prone Fields
# =============================================================================
#
# These fields are known to be unreliable when extracted by LLMs because:
# - The LLM infers information that isn't explicitly stated
# - The LLM generates plausible-sounding but fabricated data
# - The website data is ambiguous or requires domain expertise to interpret
# - The claim is common in promotional content but rarely verified
#
# Each entry maps field_name -> reason why it's hallucination-prone

HALLUCINATION_PRONE_FIELDS: Dict[str, str] = {
    "accepts_zakat": (
        "LLMs infer zakat eligibility from generic 'donate' buttons or Islamic-sounding names. "
        "Many charities accept donations without specifically processing zakat. "
        "True zakat acceptance requires explicit zakat programs, calculators, or dedicated zakat funds."
    ),
    "populations_served": (
        "LLMs default to generic phrases like 'underserved communities', 'vulnerable populations', "
        "or 'those in need' when specific population data is not found. "
        "Website copy often uses broad language that LLMs take literally."
    ),
    "external_evaluations": (
        "LLMs fabricate evaluation sources based on charity type. "
        "For example, assuming all global health charities are GiveWell-reviewed. "
        "Already caught by SourceRequiredValidator but documented here for completeness."
    ),
    "scholarly_endorsements": (
        "LLMs generate plausible scholar names and endorsements that don't exist. "
        "Religious endorsements are particularly prone to fabrication because LLMs "
        "have training data about scholars but not about specific endorsement relationships."
    ),
    "third_party_evaluated": (
        "LLMs infer evaluation status from website claims without verifying actual profiles. "
        "Websites may claim 'top-rated' or 'award-winning' without third-party verification. "
        "Now corroborated via cross-source validation, but flagged during initial extraction."
    ),
    "cost_per_beneficiary": (
        "LLMs calculate or estimate this from incomplete financial data. "
        "Accurate cost-per-beneficiary requires verified financials AND verified beneficiary counts, "
        "both of which are often unavailable or unreliable."
    ),
    "impact_multiplier": (
        "LLMs generate impact multipliers based on cause area stereotypes. "
        "True impact multipliers require rigorous cost-effectiveness analysis "
        "that only organizations like GiveWell perform."
    ),
    "evidence_quality": (
        "LLMs assign evidence grades based on program descriptions rather than actual studies. "
        "Claims like 'evidence-based' in marketing copy don't indicate actual RCT evidence."
    ),
}

# =============================================================================
# Verification Methods
# =============================================================================
#
# For each hallucination-prone field, specify HOW to verify the claim.
# This guides both human reviewers and automated corroboration systems.

VERIFICATION_REQUIRED_FIELDS: Dict[str, str] = {
    "accepts_zakat": (
        "Look for explicit zakat page, zakat calculator, zakat-specific donation options, "
        "or clear statement that organization distributes zakat to eligible recipients. "
        "Generic Islamic charity status is NOT sufficient."
    ),
    "populations_served": (
        "Require specific population descriptions from annual reports or program pages. "
        "Generic phrases should be flagged. Look for: geographic regions, demographic details, "
        "specific conditions addressed (e.g., 'children under 5 with malnutrition')."
    ),
    "external_evaluations": (
        "Cross-reference with actual evaluator databases: GiveWell top charities list, "
        "Charity Navigator API, Candid API, ImpactMatters archive. "
        "Website claims alone are insufficient."
    ),
    "scholarly_endorsements": (
        "Require verifiable source: published fatwa, signed letter, video/audio recording, "
        "or organization's official endorsement page with named scholars. "
        "Scholar must be identifiable and endorsement independently verifiable."
    ),
    "third_party_evaluated": (
        "Verify via API calls to Charity Navigator, Candid, GiveWell, BBB Wise Giving Alliance. "
        "Cross-source corroboration required. Website badges alone are insufficient."
    ),
    "cost_per_beneficiary": (
        "Require both verified annual expenses (from Form 990 or audited financials) "
        "AND verified beneficiary count (from Candid, annual report, or program evaluations). "
        "LLM-estimated values should be flagged."
    ),
    "impact_multiplier": (
        "Only accept from recognized cost-effectiveness evaluators: GiveWell, Open Philanthropy, "
        "Founders Pledge. Self-reported multipliers should be flagged as unverified."
    ),
    "evidence_quality": (
        "Require citation to actual studies (RCTs, systematic reviews, meta-analyses). "
        "Marketing claims like 'evidence-based' require independent verification of study existence."
    ),
}


def is_hallucination_prone(field_name: str) -> bool:
    """
    Check if a field is known to be hallucination-prone.

    Args:
        field_name: The name of the field to check

    Returns:
        True if the field is in the hallucination-prone list, False otherwise
    """
    return field_name in HALLUCINATION_PRONE_FIELDS


def get_hallucination_reason(field_name: str) -> Optional[str]:
    """
    Get the reason why a field is hallucination-prone.

    Args:
        field_name: The name of the field

    Returns:
        The reason string if the field is hallucination-prone, None otherwise
    """
    return HALLUCINATION_PRONE_FIELDS.get(field_name)


def get_verification_method(field_name: str) -> Optional[str]:
    """
    Get the verification method for a hallucination-prone field.

    Args:
        field_name: The name of the field

    Returns:
        The verification method string if defined, None otherwise
    """
    return VERIFICATION_REQUIRED_FIELDS.get(field_name)


def get_all_hallucination_prone_fields() -> list[str]:
    """
    Get a list of all hallucination-prone field names.

    Returns:
        List of field names that are known to be hallucination-prone
    """
    return list(HALLUCINATION_PRONE_FIELDS.keys())


def flag_unverified_fields(
    data: Dict[str, Any],
    verified_fields: Optional[set[str]] = None,
) -> Dict[str, Any]:
    """
    Flag hallucination-prone fields by renaming them with '_unverified' suffix.

    This function transforms a data dictionary by:
    1. Identifying fields that are hallucination-prone
    2. If the field is NOT in verified_fields, renaming it with '_unverified' suffix
    3. Leaving verified fields and non-prone fields unchanged

    Args:
        data: Dictionary containing field values
        verified_fields: Set of field names that have been verified through
                        corroboration. If None, all prone fields are flagged.

    Returns:
        New dictionary with unverified prone fields renamed

    Example:
        >>> data = {"accepts_zakat": True, "name": "Test Charity", "mission": "Help"}
        >>> flag_unverified_fields(data)
        {"accepts_zakat_unverified": True, "name": "Test Charity", "mission": "Help"}

        >>> flag_unverified_fields(data, verified_fields={"accepts_zakat"})
        {"accepts_zakat": True, "name": "Test Charity", "mission": "Help"}
    """
    if verified_fields is None:
        verified_fields = set()

    result = {}
    for field_name, value in data.items():
        # Skip None values - no need to flag them
        if value is None:
            result[field_name] = value
            continue

        # Check if this is a hallucination-prone field that hasn't been verified
        if is_hallucination_prone(field_name) and field_name not in verified_fields:
            # Rename with _unverified suffix
            result[f"{field_name}_unverified"] = value
        else:
            result[field_name] = value

    return result


def unflag_verified_field(
    data: Dict[str, Any],
    field_name: str,
) -> Dict[str, Any]:
    """
    Remove the '_unverified' suffix from a field after verification.

    This function is used when a previously unverified field has been
    corroborated and should be restored to its original name.

    Args:
        data: Dictionary containing field values
        field_name: The original field name (without '_unverified' suffix)

    Returns:
        New dictionary with the field renamed back to its original name

    Example:
        >>> data = {"accepts_zakat_unverified": True, "name": "Test"}
        >>> unflag_verified_field(data, "accepts_zakat")
        {"accepts_zakat": True, "name": "Test"}
    """
    unverified_key = f"{field_name}_unverified"
    if unverified_key not in data:
        return data.copy()

    result = {}
    for key, value in data.items():
        if key == unverified_key:
            result[field_name] = value
        else:
            result[key] = value

    return result


def get_verification_report(data: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """
    Generate a report of hallucination-prone fields in the data.

    For each hallucination-prone field present in the data, returns
    the reason it's prone to hallucination and how to verify it.

    Args:
        data: Dictionary containing field values

    Returns:
        Dictionary mapping field names to their hallucination info:
        {
            "accepts_zakat": {
                "value": True,
                "reason": "LLMs infer zakat eligibility...",
                "verification_method": "Look for explicit zakat page...",
                "status": "unverified"  # or "verified" if no _unverified suffix
            }
        }
    """
    report = {}

    for field_name in HALLUCINATION_PRONE_FIELDS:
        # Check for both verified and unverified versions
        unverified_key = f"{field_name}_unverified"

        if field_name in data:
            report[field_name] = {
                "value": data[field_name],
                "reason": HALLUCINATION_PRONE_FIELDS[field_name],
                "verification_method": VERIFICATION_REQUIRED_FIELDS.get(field_name),
                "status": "verified",
            }
        elif unverified_key in data:
            report[field_name] = {
                "value": data[unverified_key],
                "reason": HALLUCINATION_PRONE_FIELDS[field_name],
                "verification_method": VERIFICATION_REQUIRED_FIELDS.get(field_name),
                "status": "unverified",
            }

    return report
