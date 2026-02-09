"""
Validators for the data pipeline.

This module provides validation utilities for:
- Source data validation (ProPublica, Charity Navigator, etc.)
- LLM response validation
- Numeric bounds checking
- Cross-source consistency validation
- Hallucination-prone field detection and flagging
"""

from .bounds_validator import (
    FIELD_BOUNDS,
    get_bounds,
    get_validation_summary,
    validate_bounds,
    validate_dict_bounds,
    validate_pydantic_model_bounds,
)
from .consistency_validator import (
    ConsistencyValidator,
    ExportValidator,
    ValidationResult,
    ValidationViolation,
    validate_for_export,
    validate_rich_vs_baseline,
)
from .hallucination_denylist import (
    HALLUCINATION_PRONE_FIELDS,
    VERIFICATION_REQUIRED_FIELDS,
    flag_unverified_fields,
    get_all_hallucination_prone_fields,
    get_hallucination_reason,
    get_verification_method,
    get_verification_report,
    is_hallucination_prone,
    unflag_verified_field,
)
from .source_required_validator import (
    SourceRequiredValidator,
    ValidationRule,
    validate_source_required,
)

__all__ = [
    # Bounds validation
    "FIELD_BOUNDS",
    "validate_bounds",
    "validate_dict_bounds",
    "validate_pydantic_model_bounds",
    "get_bounds",
    "get_validation_summary",
    # Consistency validation
    "ConsistencyValidator",
    "ValidationResult",
    "ValidationViolation",
    "validate_rich_vs_baseline",
    # Export validation
    "ExportValidator",
    "validate_for_export",
    # Source-required validation (anti-hallucination)
    "SourceRequiredValidator",
    "ValidationRule",
    "validate_source_required",
    # Hallucination-prone field denylist
    "HALLUCINATION_PRONE_FIELDS",
    "VERIFICATION_REQUIRED_FIELDS",
    "is_hallucination_prone",
    "get_hallucination_reason",
    "get_verification_method",
    "get_all_hallucination_prone_fields",
    "flag_unverified_fields",
    "unflag_verified_field",
    "get_verification_report",
]
