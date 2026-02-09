"""
Rule-based LLM quality metrics - No additional LLM cost.

Evaluates narrative quality using pure Python heuristics:
- Structural compliance: JSON valid, required fields present
- Citation validity: [N] markers match entries, sources from input
- Specificity: Concrete facts vs vague language
- Completeness: Substantive content in all fields
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class QualityMetrics:
    """Quality scores for a single evaluation."""

    # Individual scores (0-100)
    structural_score: float = 0.0
    citation_score: float = 0.0
    specificity_score: float = 0.0
    completeness_score: float = 0.0

    # Overall weighted score
    overall_score: float = 0.0

    # Details for debugging
    structural_issues: list[str] = None
    citation_issues: list[str] = None
    specificity_details: dict = None

    def __post_init__(self):
        if self.structural_issues is None:
            self.structural_issues = []
        if self.citation_issues is None:
            self.citation_issues = []
        if self.specificity_details is None:
            self.specificity_details = {}

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "structural_score": round(self.structural_score, 1),
            "citation_score": round(self.citation_score, 1),
            "specificity_score": round(self.specificity_score, 1),
            "completeness_score": round(self.completeness_score, 1),
            "overall_score": round(self.overall_score, 1),
        }

    def to_detailed_dict(self) -> dict:
        """Convert to dict with debugging details."""
        d = self.to_dict()
        d["structural_issues"] = self.structural_issues
        d["citation_issues"] = self.citation_issues
        d["specificity_details"] = self.specificity_details
        return d


def evaluate_quality(
    narrative: Optional[dict],
    input_sources: Optional[list[str]] = None,
) -> QualityMetrics:
    """
    Evaluate LLM output quality using rule-based metrics.

    Args:
        narrative: The LLM-generated narrative dict
        input_sources: List of valid source names/URLs from input data

    Returns:
        QualityMetrics with scores and issues
    """
    if narrative is None:
        return QualityMetrics(
            structural_score=0,
            citation_score=0,
            specificity_score=0,
            completeness_score=0,
            overall_score=0,
            structural_issues=["Narrative is None"],
        )

    # Compute individual metrics
    structural = _check_structural(narrative)
    citation = _check_citations(narrative, input_sources or [])
    specificity = _check_specificity(narrative)
    completeness = _check_completeness(narrative)

    # Weighted overall score
    # Structural is most important (if JSON is broken, nothing works)
    # Citation and specificity matter for quality
    # Completeness is nice-to-have
    overall = structural.score * 0.30 + citation.score * 0.30 + specificity.score * 0.25 + completeness.score * 0.15

    return QualityMetrics(
        structural_score=structural.score,
        citation_score=citation.score,
        specificity_score=specificity.score,
        completeness_score=completeness.score,
        overall_score=overall,
        structural_issues=structural.issues,
        citation_issues=citation.issues,
        specificity_details=specificity.details,
    )


# =============================================================================
# STRUCTURAL COMPLIANCE
# =============================================================================


@dataclass
class StructuralResult:
    score: float
    issues: list[str]


REQUIRED_FIELDS = [
    "headline",
    "summary",
    "strengths",
    "amal_score_rationale",
    "dimension_explanations",
    "all_citations",
]

# V4 rubric: scored dimensions are impact + alignment.
# Rich narratives also output "credibility" as a narrative-only dimension.
# Accept any of: V4 rich (credibility/impact/alignment) or V4 baseline (impact/alignment).
REQUIRED_DIMENSIONS_RICH = ["impact", "alignment"]  # minimum for both baseline and rich
REQUIRED_DIMENSIONS_FULL = ["credibility", "impact", "alignment"]  # expected from rich narratives


def _check_structural(narrative: dict) -> StructuralResult:
    """Check structural compliance: required fields present and valid types."""
    issues = []
    checks_passed = 0
    total_checks = 0

    # Check required top-level fields
    for field in REQUIRED_FIELDS:
        total_checks += 1
        if field not in narrative:
            issues.append(f"Missing field: {field}")
        elif narrative[field] is None:
            issues.append(f"Field is None: {field}")
        else:
            checks_passed += 1

    # Check strengths is a list with items
    total_checks += 1
    strengths = narrative.get("strengths", [])
    if not isinstance(strengths, list):
        issues.append("strengths is not a list")
    elif len(strengths) == 0:
        issues.append("strengths is empty")
    else:
        checks_passed += 1

    # Check dimension_explanations has required keys (V4: impact + alignment minimum)
    dim_exp = narrative.get("dimension_explanations", {})
    if isinstance(dim_exp, dict):
        for dim in REQUIRED_DIMENSIONS_RICH:
            total_checks += 1
            if dim not in dim_exp or not dim_exp[dim]:
                issues.append(f"Missing dimension explanation: {dim}")
            else:
                checks_passed += 1

    # Check all_citations is a list
    total_checks += 1
    citations = narrative.get("all_citations", [])
    if not isinstance(citations, list):
        issues.append("all_citations is not a list")
    else:
        checks_passed += 1

    score = (checks_passed / total_checks * 100) if total_checks > 0 else 0
    return StructuralResult(score=score, issues=issues)


# =============================================================================
# CITATION VALIDITY
# =============================================================================


@dataclass
class CitationResult:
    score: float
    issues: list[str]


def _check_citations(narrative: dict, input_sources: list[str]) -> CitationResult:
    """Check citation validity: markers match entries, sources are valid."""
    issues = []

    # Collect all text that might contain citations
    text_parts = [
        narrative.get("summary", ""),
        narrative.get("amal_score_rationale", ""),
    ]
    dim_exp = narrative.get("dimension_explanations", {})
    if isinstance(dim_exp, dict):
        for val in dim_exp.values():
            text_parts.append(str(val) if val else "")

    full_text = " ".join(str(t) for t in text_parts if t)

    # Find all [N] markers in text
    markers = set(re.findall(r"\[(\d+)\]", full_text))

    # Get defined citation IDs
    citations = narrative.get("all_citations", [])
    if not isinstance(citations, list):
        return CitationResult(score=0, issues=["all_citations is not a list"])

    defined_ids = set()
    for cit in citations:
        if isinstance(cit, dict):
            cid = cit.get("id", "")
            match = re.search(r"\[(\d+)\]", str(cid))
            if match:
                defined_ids.add(match.group(1))

    # Check 1: All markers have definitions
    orphan_markers = markers - defined_ids
    if orphan_markers:
        issues.append(f"Orphan citation markers (no definition): {sorted(orphan_markers)}")

    # Check 2: All definitions are used
    unused_defs = defined_ids - markers
    if unused_defs:
        issues.append(f"Unused citation definitions: {sorted(unused_defs)}")

    # Check 3: Citations have required fields
    for i, cit in enumerate(citations):
        if not isinstance(cit, dict):
            issues.append(f"Citation {i} is not a dict")
            continue
        if not cit.get("source_name"):
            issues.append(f"Citation {i} missing source_name")
        if not cit.get("source_url"):
            issues.append(f"Citation {i} missing source_url")

    # Check 4: Source URLs/names match input (if provided)
    if input_sources:
        input_lower = [s.lower() for s in input_sources]
        for cit in citations:
            if isinstance(cit, dict):
                source_name = str(cit.get("source_name", "")).lower()
                source_url = str(cit.get("source_url", "")).lower()
                # Check if either name or URL matches any input source
                matched = any(
                    inp in source_name or inp in source_url or source_name in inp or source_url in inp
                    for inp in input_lower
                )
                if not matched and source_name:
                    issues.append(f"Possibly hallucinated source: {cit.get('source_name')}")

    # Score calculation
    # Start at 100, deduct for issues
    score = 100.0
    score -= len(orphan_markers) * 15  # Orphan markers are bad
    score -= len(unused_defs) * 5  # Unused defs are minor
    score -= sum(1 for i in issues if "missing" in i.lower()) * 10  # Missing fields
    score -= sum(1 for i in issues if "hallucinated" in i.lower()) * 10  # Hallucinations

    # Bonus for having citations at all
    if len(citations) == 0 and len(markers) == 0:
        score = 50  # No citations used - not great but not an error

    return CitationResult(score=max(0, min(100, score)), issues=issues)


# =============================================================================
# SPECIFICITY
# =============================================================================


@dataclass
class SpecificityResult:
    score: float
    details: dict


# Patterns for specific facts
SPECIFIC_PATTERNS = [
    (r"\$[\d,]+(?:\.\d{2})?(?:\s*(?:million|billion|M|B))?", "dollar_amounts"),
    (r"\d+(?:\.\d+)?%", "percentages"),
    (r"\b(?:19|20)\d{2}\b", "years"),
    (r"\b\d{1,3}(?:,\d{3})+\b", "large_numbers"),  # e.g., 1,000,000
    (r"\b\d+\s*(?:countries|nations|locations|programs|staff|employees)\b", "counts"),
]

# Patterns for vague language (penalize)
VAGUE_PATTERNS = [
    r"make[s]?\s+(?:a\s+)?(?:real\s+)?(?:positive\s+)?(?:significant\s+)?impact",
    r"help[s]?\s+(?:many\s+)?communit(?:y|ies)",
    r"important\s+work",
    r"meaningful\s+(?:change|difference|impact)",
    r"dedicated\s+to",
    r"committed\s+to",
    r"strives?\s+to",
    r"various\s+(?:programs|initiatives|efforts)",
    r"numerous\s+(?:programs|initiatives|efforts)",
]


def _check_specificity(narrative: dict) -> SpecificityResult:
    """Check specificity: concrete facts vs vague language."""
    # Collect all narrative text
    text_parts = [
        narrative.get("headline", ""),
        narrative.get("summary", ""),
        narrative.get("amal_score_rationale", ""),
    ]
    dim_exp = narrative.get("dimension_explanations", {})
    if isinstance(dim_exp, dict):
        for val in dim_exp.values():
            text_parts.append(str(val) if val else "")

    # Also check strengths
    strengths = narrative.get("strengths", [])
    if isinstance(strengths, list):
        text_parts.extend(str(s) for s in strengths)

    full_text = " ".join(str(t) for t in text_parts if t)

    # Count specific facts
    specific_counts = {}
    total_specific = 0
    for pattern, name in SPECIFIC_PATTERNS:
        matches = re.findall(pattern, full_text, re.IGNORECASE)
        specific_counts[name] = len(matches)
        total_specific += len(matches)

    # Count vague phrases
    vague_count = 0
    for pattern in VAGUE_PATTERNS:
        vague_count += len(re.findall(pattern, full_text, re.IGNORECASE))

    # Score calculation
    # Base score from specific facts (each worth 10 points, max 60)
    specificity_points = min(60, total_specific * 10)

    # Bonus for diversity of specific types (max 20)
    types_used = sum(1 for c in specific_counts.values() if c > 0)
    diversity_points = min(20, types_used * 5)

    # Penalty for vague language (each worth -5, max -30)
    vague_penalty = min(30, vague_count * 5)

    # Base of 20 (some content exists)
    score = 20 + specificity_points + diversity_points - vague_penalty
    score = max(0, min(100, score))

    details = {
        "specific_facts": specific_counts,
        "total_specific": total_specific,
        "vague_phrases": vague_count,
        "text_length": len(full_text),
    }

    return SpecificityResult(score=score, details=details)


# =============================================================================
# COMPLETENESS
# =============================================================================


def _check_completeness(narrative: dict) -> StructuralResult:
    """Check that fields have substantive content (not just present but meaningful)."""
    issues = []
    checks_passed = 0
    total_checks = 0

    # Headline should be 10+ chars
    total_checks += 1
    headline = narrative.get("headline", "")
    if len(str(headline)) < 10:
        issues.append(f"Headline too short ({len(str(headline))} chars)")
    else:
        checks_passed += 1

    # Summary should be 100+ chars
    total_checks += 1
    summary = narrative.get("summary", "")
    if len(str(summary)) < 100:
        issues.append(f"Summary too short ({len(str(summary))} chars)")
    else:
        checks_passed += 1

    # Should have 2+ strengths
    total_checks += 1
    strengths = narrative.get("strengths", [])
    if not isinstance(strengths, list) or len(strengths) < 2:
        issues.append(f"Too few strengths ({len(strengths) if isinstance(strengths, list) else 0})")
    else:
        checks_passed += 1

    # Rationale should be 50+ chars
    total_checks += 1
    rationale = narrative.get("amal_score_rationale", "")
    if len(str(rationale)) < 50:
        issues.append(f"Rationale too short ({len(str(rationale))} chars)")
    else:
        checks_passed += 1

    # Each dimension explanation should be 30+ chars
    dim_exp = narrative.get("dimension_explanations", {})
    if isinstance(dim_exp, dict):
        for dim in REQUIRED_DIMENSIONS_RICH:
            total_checks += 1
            exp = dim_exp.get(dim, "")
            if len(str(exp)) < 30:
                issues.append(f"Dimension '{dim}' explanation too short ({len(str(exp))} chars)")
            else:
                checks_passed += 1

    score = (checks_passed / total_checks * 100) if total_checks > 0 else 0
    return StructuralResult(score=score, issues=issues)


# =============================================================================
# AGGREGATE METRICS
# =============================================================================


def aggregate_quality_metrics(metrics_list: list[QualityMetrics]) -> dict:
    """Aggregate quality metrics across multiple evaluations."""
    if not metrics_list:
        return {}

    n = len(metrics_list)

    return {
        "count": n,
        "avg_structural": round(sum(m.structural_score for m in metrics_list) / n, 1),
        "avg_citation": round(sum(m.citation_score for m in metrics_list) / n, 1),
        "avg_specificity": round(sum(m.specificity_score for m in metrics_list) / n, 1),
        "avg_completeness": round(sum(m.completeness_score for m in metrics_list) / n, 1),
        "avg_overall": round(sum(m.overall_score for m in metrics_list) / n, 1),
        "min_overall": round(min(m.overall_score for m in metrics_list), 1),
        "max_overall": round(max(m.overall_score for m in metrics_list), 1),
    }
