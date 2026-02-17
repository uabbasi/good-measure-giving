"""Phase boundary contracts for pipeline validation.

Each phase transition (crawl→extract, extract→discover, discover→synthesize)
has a machine-enforced contract defining required outputs. Missing required
fields = hard fail at that boundary, not silent propagation.

Usage:
    from src.schemas.phase_contracts import validate_crawl_output, validate_extract_output

    errors = validate_crawl_output(report)
    if errors:
        raise ValueError(f"Crawl contract violated: {errors}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PhaseValidationResult:
    """Result of validating a phase's output against its contract."""

    phase: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.passed


# ============================================================================
# Crawl → Extract boundary
# ============================================================================
# Crawl must produce raw_content for each source. Website is special (combined
# fetch+parse), so parsed_json is acceptable instead.

# Sources that must succeed for a crawl to be considered complete
CRAWL_REQUIRED_SOURCES = {"propublica"}

# Sources that should succeed but won't block the pipeline
CRAWL_EXPECTED_SOURCES = {"propublica", "charity_navigator", "candid", "form990_grants", "website"}


def validate_crawl_output(report: dict[str, Any]) -> PhaseValidationResult:
    """Validate crawl phase output before handing off to extract.

    Args:
        report: The crawl report from fetch_charity_data()

    Returns:
        PhaseValidationResult with pass/fail and reasons
    """
    result = PhaseValidationResult(phase="crawl", passed=True)

    if not report.get("ein"):
        result.errors.append("Missing EIN in crawl report")
        result.passed = False
        return result

    succeeded = set(report.get("sources_succeeded", []))
    failed = report.get("sources_failed", {})

    # Check required sources
    for source in CRAWL_REQUIRED_SOURCES:
        if source not in succeeded:
            error_msg = failed.get(source, "not attempted")
            result.errors.append(f"Required source '{source}' failed: {error_msg}")
            result.passed = False

    # Warn about expected but missing sources
    for source in CRAWL_EXPECTED_SOURCES - CRAWL_REQUIRED_SOURCES:
        if source not in succeeded:
            error_msg = failed.get(source, "not attempted/skipped")
            result.warnings.append(f"Expected source '{source}' missing: {error_msg}")

    return result


# ============================================================================
# Extract → Discover/Synthesize boundary
# ============================================================================
# Extract must produce parsed_json for each source that was crawled.
# We validate that the parsed data has the minimum required structure.

# Minimum required fields per source's parsed_json
EXTRACT_REQUIRED_FIELDS: dict[str, list[str]] = {
    "propublica": ["propublica_990"],
}

EXTRACT_EXPECTED_FIELDS: dict[str, list[str]] = {
    "propublica": ["propublica_990"],
    "charity_navigator": ["cn_profile"],
    "candid": ["candid_profile"],
    "form990_grants": ["grants_profile"],
    "website": ["website_profile"],
    "bbb": ["bbb_profile"],
}

# Minimum fields within propublica_990 that must be non-None
PROPUBLICA_CRITICAL_FIELDS = ["ein", "name"]


def validate_extract_output(
    ein: str,
    raw_data_rows: list[dict[str, Any]],
) -> PhaseValidationResult:
    """Validate extract phase output before handing off to synthesize.

    Args:
        ein: The charity EIN
        raw_data_rows: All raw_scraped_data rows for this charity

    Returns:
        PhaseValidationResult with pass/fail and reasons
    """
    result = PhaseValidationResult(phase="extract", passed=True)

    if not raw_data_rows:
        result.errors.append(f"No raw data rows found for {ein}")
        result.passed = False
        return result

    # Index rows by source
    by_source: dict[str, dict] = {}
    for row in raw_data_rows:
        source = row.get("source")
        if source and row.get("success"):
            by_source[source] = row

    # Check required sources have parsed_json
    for source, required_keys in EXTRACT_REQUIRED_FIELDS.items():
        row = by_source.get(source)
        if not row:
            result.errors.append(f"Required source '{source}' not found or not successful")
            result.passed = False
            continue

        parsed = row.get("parsed_json")
        if not parsed or not isinstance(parsed, dict):
            result.errors.append(f"Source '{source}' has no parsed_json")
            result.passed = False
            continue

        for key in required_keys:
            if key not in parsed or not parsed[key]:
                result.errors.append(f"Source '{source}' missing required key '{key}' in parsed_json")
                result.passed = False

    # Validate ProPublica critical fields
    pp_row = by_source.get("propublica")
    if pp_row:
        pp_data = (pp_row.get("parsed_json") or {}).get("propublica_990", {})
        for field_name in PROPUBLICA_CRITICAL_FIELDS:
            if not pp_data.get(field_name):
                result.errors.append(f"ProPublica missing critical field '{field_name}'")
                result.passed = False

    # Warn about expected sources
    for source, expected_keys in EXTRACT_EXPECTED_FIELDS.items():
        if source in EXTRACT_REQUIRED_FIELDS:
            continue  # Already checked above
        row = by_source.get(source)
        if not row:
            result.warnings.append(f"Expected source '{source}' not available")
            continue
        parsed = row.get("parsed_json")
        if not parsed:
            result.warnings.append(f"Source '{source}' has no parsed_json")

    return result


# ============================================================================
# Discover → Synthesize boundary
# ============================================================================
# Discovery is optional — synthesize can proceed without it.
# But if discovery ran, validate that the output is well-formed.


def validate_discover_output(
    discovered_profile: dict[str, Any] | None,
) -> PhaseValidationResult:
    """Validate discovery phase output (if it ran).

    Args:
        discovered_profile: The discovered_profile dict, or None if discovery didn't run

    Returns:
        PhaseValidationResult (always passes if discovery didn't run)
    """
    result = PhaseValidationResult(phase="discover", passed=True)

    if discovered_profile is None:
        result.warnings.append("Discovery phase did not run — synthesize will proceed without it")
        return result

    if not isinstance(discovered_profile, dict):
        result.errors.append(f"discovered_profile is not a dict: {type(discovered_profile)}")
        result.passed = False
        return result

    # Validate each section if present
    valid_sections = {"zakat", "evaluations", "outcomes", "theory_of_change", "awards"}
    for key in discovered_profile:
        if key in ("ein", "charity_name", "website_url", "discovered_at"):
            continue
        if key not in valid_sections:
            result.warnings.append(f"Unknown section in discovered_profile: '{key}'")

    # Validate zakat section structure
    zakat = discovered_profile.get("zakat")
    if zakat and isinstance(zakat, dict):
        if "accepts_zakat" not in zakat:
            result.warnings.append("Zakat section missing 'accepts_zakat' field")

    return result


# ============================================================================
# Synthesize → Baseline boundary
# ============================================================================
# Synthesize must produce metrics_json (CharityMetrics blob) and key scorer fields.

SYNTHESIZE_REQUIRED_FIELDS = ["metrics_json"]

SYNTHESIZE_SCORER_FIELDS = [
    "detected_cause_area",
    "muslim_charity_fit",
    "primary_category",
]


def validate_synthesize_output(
    charity_data: dict[str, Any],
) -> PhaseValidationResult:
    """Validate synthesize phase output before handing off to baseline.

    Args:
        charity_data: The synthesized CharityData dict

    Returns:
        PhaseValidationResult with pass/fail and reasons
    """
    result = PhaseValidationResult(phase="synthesize", passed=True)

    if not charity_data:
        result.errors.append("Empty charity_data")
        result.passed = False
        return result

    # Check required fields
    for field_name in SYNTHESIZE_REQUIRED_FIELDS:
        value = charity_data.get(field_name)
        if value is None:
            result.errors.append(f"Missing required field '{field_name}'")
            result.passed = False
        elif isinstance(value, dict) and not value:
            result.errors.append(f"Empty required field '{field_name}'")
            result.passed = False

    # Warn about scorer-critical fields
    for field_name in SYNTHESIZE_SCORER_FIELDS:
        if charity_data.get(field_name) is None:
            result.warnings.append(f"Scorer field '{field_name}' is None — scoring may be incomplete")

    # Validate metrics_json has minimum structure
    metrics = charity_data.get("metrics_json")
    if isinstance(metrics, dict):
        if not metrics.get("ein"):
            result.errors.append("metrics_json missing 'ein'")
            result.passed = False

    return result
