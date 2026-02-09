"""
Domain-specific numeric bounds validation for extracted fields.

LLMs sometimes extract nonsensical numeric values (e.g., 500% program expense ratio,
negative beneficiaries). This module provides bounds checking to catch these errors.

Usage:
    from src.validators.bounds_validator import validate_bounds, FIELD_BOUNDS

    # Single field validation
    value = validate_bounds("program_expense_ratio", 1.5)  # Returns None (out of bounds)
    value = validate_bounds("program_expense_ratio", 0.85)  # Returns 0.85 (valid)

    # Dict validation
    data = {"beneficiaries_served_annually": 500_000_000, "founded_year": 1950}
    cleaned = validate_dict_bounds(data)  # Sets beneficiaries to None, keeps founded_year

Design:
    - Out-of-bounds values are set to None and logged as warnings
    - Bounds are inclusive on both ends
    - Fields not in FIELD_BOUNDS are passed through unchanged
    - Validation is lenient: None/missing values are allowed
"""

import logging
from datetime import datetime
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

# S-008: Compute current year dynamically in get_bounds() to avoid stale values
# if process runs across year boundary
def _get_current_year() -> int:
    """Get current year with buffer for fiscal year filings."""
    return datetime.now().year + 1

# Type for numeric values
T = TypeVar("T", int, float)

# =============================================================================
# FIELD BOUNDS CONFIGURATION
# =============================================================================

# Bounds are (min, max) inclusive
# Commentary explains the reasoning for each bound
FIELD_BOUNDS: dict[str, tuple[float | int, float | int]] = {
    # Beneficiary counts
    # Max is UNICEF-scale (~100M children reached annually)
    "beneficiaries_served_annually": (1, 100_000_000),
    "total_beneficiaries": (1, 100_000_000),
    "annual_beneficiaries": (1, 100_000_000),

    # Financial ratios (0-1 scale, representing 0-100%)
    "program_expense_ratio": (0.0, 1.0),
    "admin_expense_ratio": (0.0, 1.0),
    "fundraising_expense_ratio": (0.0, 1.0),
    "admin_ratio": (0.0, 1.0),
    "fundraising_ratio": (0.0, 1.0),
    "independent_board_pct": (0.0, 1.0),
    "ceo_compensation_pct_revenue": (0.0, 1.0),
    "payroll_to_revenue_pct": (0.0, 1.0),

    # Scores (0-100 scale)
    "cn_overall_score": (0, 100),
    "cn_financial_score": (0, 100),
    "overall_score": (0, 100),
    "financial_score": (0, 100),
    "accountability_score": (0, 100),
    "transparency_score": (0, 100),
    "confidence_score": (0, 100),
    "amal_score": (0, 100),

    # Working capital / reserves
    # Max 10 years (120 months) is extremely high but possible for endowed foundations
    "working_capital_months": (0, 120),
    "reserves_months": (0, 120),

    # Cost per beneficiary
    # Range from $0.01 (mass distribution items) to $100k (expensive medical procedures)
    "cost_per_beneficiary": (0.01, 100_000),

    # Revenue/expense amounts
    # Max $50B is Red Cross / largest NGO scale
    # Allowing 0 for revenue (some orgs have years with no revenue)
    "total_revenue": (0, 50_000_000_000),
    "total_expenses": (0, 50_000_000_000),
    "total_assets": (0, 100_000_000_000),  # Larger foundations can have huge endowments
    "program_expenses": (0, 50_000_000_000),
    "admin_expenses": (0, 50_000_000_000),
    "fundraising_expenses": (0, 50_000_000_000),
    "annual_revenue": (0, 50_000_000_000),

    # Year fields - handled dynamically in get_bounds() via _YEAR_FIELDS
    # to avoid stale values if process runs across year boundary

    # People counts
    # Max employees: Walmart has ~2.3M, but nonprofits max around 100k
    "employees_count": (0, 100_000),
    "employees": (0, 100_000),
    "volunteers_count": (0, 10_000_000),  # Large volunteer orgs like Red Cross
    "board_size": (1, 100),  # Most boards are 5-25, but some are larger

    # Publication/citation counts (for RESEARCH_POLICY track)
    "publications_count": (0, 10_000),
    "peer_reviewed_count": (0, 5_000),
    "testimony_count": (0, 500),
    "academic_citations": (0, 100_000),

    # Other bounded fields
    "programs_count": (1, 100),
    "outcome_tracking_years": (0, 50),
}

# Year fields with their minimum year - max is computed dynamically
_YEAR_FIELDS: dict[str, int] = {
    "founded_year": 1800,
    "year_founded": 1800,
    "irs_ruling_year": 1800,
    "tax_year": 1900,
    "fiscal_year": 1900,
    "last_verified_year": 1990,
    "source_year": 1990,
}

# Aliases: map common variant field names to canonical bounds
FIELD_ALIASES: dict[str, str] = {
    "num_employees": "employees_count",
    "employee_count": "employees_count",
    "num_beneficiaries": "beneficiaries_served_annually",
    "beneficiary_count": "beneficiaries_served_annually",
    "year": "tax_year",
    "revenue": "total_revenue",
    "expenses": "total_expenses",
}


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================


def get_bounds(field_name: str) -> tuple[float | int, float | int] | None:
    """
    Get bounds for a field, resolving aliases.

    Args:
        field_name: Field name to look up

    Returns:
        (min, max) tuple if field has bounds defined, None otherwise
    """
    # S-008: Check year fields first (computed dynamically)
    if field_name in _YEAR_FIELDS:
        return (_YEAR_FIELDS[field_name], _get_current_year())

    # Check direct match in static bounds
    if field_name in FIELD_BOUNDS:
        return FIELD_BOUNDS[field_name]

    # Check aliases
    canonical = FIELD_ALIASES.get(field_name)
    if canonical:
        # Alias might point to year field or static bounds
        if canonical in _YEAR_FIELDS:
            return (_YEAR_FIELDS[canonical], _get_current_year())
        if canonical in FIELD_BOUNDS:
            return FIELD_BOUNDS[canonical]

    return None


def validate_bounds(
    field_name: str,
    value: T | None,
    ein: str | None = None,
    log_warning: bool = True,
) -> T | None:
    """
    Validate a single field value against domain-specific bounds.

    Args:
        field_name: Name of the field being validated
        value: The value to validate (can be None)
        ein: Optional EIN for logging context
        log_warning: Whether to log a warning for out-of-bounds values

    Returns:
        The original value if within bounds or no bounds defined,
        None if value is out of bounds
    """
    # Pass through None values
    if value is None:
        return None

    # Get bounds for this field
    bounds = get_bounds(field_name)
    if bounds is None:
        return value  # No bounds defined, pass through

    min_val, max_val = bounds

    # Check bounds
    if value < min_val or value > max_val:
        if log_warning:
            context = f" for EIN {ein}" if ein else ""
            logger.warning(
                f"Out-of-bounds value{context}: {field_name}={value} "
                f"(valid range: {min_val}-{max_val}). Setting to None."
            )
        return None

    return value


def validate_dict_bounds(
    data: dict[str, Any],
    ein: str | None = None,
    log_warnings: bool = True,
) -> dict[str, Any]:
    """
    Validate all numeric fields in a dictionary against domain-specific bounds.

    Args:
        data: Dictionary with field values to validate
        ein: Optional EIN for logging context
        log_warnings: Whether to log warnings for out-of-bounds values

    Returns:
        New dictionary with out-of-bounds values set to None
    """
    result = {}

    for key, value in data.items():
        # Only validate numeric types
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            result[key] = validate_bounds(key, value, ein=ein, log_warning=log_warnings)
        elif isinstance(value, dict):
            # Recursively validate nested dicts
            result[key] = validate_dict_bounds(value, ein=ein, log_warnings=log_warnings)
        else:
            result[key] = value

    return result


def validate_pydantic_model_bounds(
    model_instance: Any,
    ein: str | None = None,
    log_warnings: bool = True,
) -> dict[str, Any]:
    """
    Validate a Pydantic model instance and return cleaned dict.

    Args:
        model_instance: A Pydantic BaseModel instance
        ein: Optional EIN for logging context
        log_warnings: Whether to log warnings for out-of-bounds values

    Returns:
        Dictionary with validated/cleaned values
    """
    data = model_instance.model_dump() if hasattr(model_instance, "model_dump") else dict(model_instance)
    return validate_dict_bounds(data, ein=ein, log_warnings=log_warnings)


# =============================================================================
# PYDANTIC FIELD VALIDATORS
# =============================================================================


def create_bounds_validator(field_name: str):
    """
    Create a Pydantic field_validator for a specific field.

    Usage in Pydantic models:
        from src.validators.bounds_validator import create_bounds_validator

        class MyModel(BaseModel):
            program_expense_ratio: Optional[float] = None

            _validate_program_expense_ratio = field_validator("program_expense_ratio")(
                create_bounds_validator("program_expense_ratio")
            )

    Args:
        field_name: The field name to create a validator for

    Returns:
        A validator function suitable for Pydantic's field_validator
    """
    def validator(cls, v):
        if v is None:
            return v
        return validate_bounds(field_name, v, log_warning=True)

    return classmethod(validator)


# =============================================================================
# VALIDATION SUMMARY
# =============================================================================


def get_validation_summary(
    original: dict[str, Any],
    validated: dict[str, Any],
) -> dict[str, Any]:
    """
    Generate a summary of validation changes.

    Args:
        original: Original dictionary before validation
        validated: Dictionary after validation

    Returns:
        Summary dict with counts and list of nullified fields
    """
    nullified = []

    def compare(orig: dict, valid: dict, prefix: str = "") -> None:
        for key, orig_val in orig.items():
            valid_val = valid.get(key)
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(orig_val, dict) and isinstance(valid_val, dict):
                compare(orig_val, valid_val, full_key)
            elif orig_val is not None and valid_val is None:
                bounds = get_bounds(key)
                nullified.append({
                    "field": full_key,
                    "original_value": orig_val,
                    "bounds": bounds,
                })

    compare(original, validated)

    return {
        "fields_checked": len(FIELD_BOUNDS),
        "values_nullified": len(nullified),
        "nullified_fields": nullified,
    }
