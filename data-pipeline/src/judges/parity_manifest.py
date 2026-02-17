"""Judge Parity Manifest — tracks which critical rules have both runtime gates and judge checks.

Every critical rule should exist both as:
1. A **runtime gate** (code assertion that blocks the pipeline)
2. A **judge check** (quality validation that catches edge cases)

This manifest is the single source of truth for parity status. Update it when
adding new judges or runtime gates.

Usage:
    from src.judges.parity_manifest import PARITY_MANIFEST, get_gaps

    gaps = get_gaps()
    for gap in gaps:
        print(f"{gap['rule']}: {gap['parity']} — {gap['recommendation']}")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class ParityEntry:
    """A single validation rule and its coverage across gate types."""

    rule: str
    description: str
    parity: Literal["both", "runtime_only", "judge_only"]
    runtime_gate: str | None  # File:function or None
    judge_check: str | None  # Judge ID (e.g., J-001) or None
    severity: Literal["critical", "high", "medium", "low"]
    recommendation: str | None = None  # Action needed if parity not achieved


PARITY_MANIFEST: list[ParityEntry] = [
    # ========================================================================
    # PARITY ACHIEVED (both runtime gate and judge check)
    # ========================================================================
    ParityEntry(
        rule="propublica_ein_mismatch",
        description="ProPublica EIN must match requested EIN",
        parity="both",
        runtime_gate="propublica.py:parse",
        judge_check="J-001",
        severity="critical",
    ),
    ParityEntry(
        rule="financial_sanity",
        description="Financial values must be non-negative and within plausible ranges",
        parity="both",
        runtime_gate="bounds_validator.py:validate_bounds",
        judge_check="J-002",
        severity="critical",
    ),
    ParityEntry(
        rule="cn_score_consistency",
        description="CN scores must be 0-100 and internally consistent",
        parity="both",
        runtime_gate="charity_navigator.py:parse",
        judge_check="J-003",
        severity="high",
    ),
    ParityEntry(
        rule="expense_ratio_sanity",
        description="Expense ratios must be ≤1.0 (≤3.0 with tolerance)",
        parity="both",
        runtime_gate="charity_metrics_aggregator.py:aggregate",
        judge_check="S-J-001",
        severity="critical",
    ),
    ParityEntry(
        rule="zakat_corroboration",
        description="Zakat claims require 2-source verification",
        parity="both",
        runtime_gate="charity_metrics_aggregator.py:_corroborate + source_required_validator.py",
        judge_check="S-J-004",
        severity="critical",
    ),
    ParityEntry(
        rule="schema_validation",
        description="Parsed data must match Pydantic schemas",
        parity="both",
        runtime_gate="collector validators (propublica/cn/candid/website/bbb/grants)",
        judge_check="E-J-001",
        severity="critical",
    ),
    ParityEntry(
        rule="muslim_charity_fit_truth_table",
        description="muslim_charity_fit must follow (identity, serves_muslims) truth table",
        parity="both",
        runtime_gate="synthesize.py:compute_muslim_charity_fit",
        judge_check="S-J-003",
        severity="high",
    ),
    ParityEntry(
        rule="phase_boundary_contracts",
        description="Each phase output must pass its boundary contract",
        parity="both",
        runtime_gate="phase_contracts.py:validate_*",
        judge_check="Phase-specific quality judges (crawl/extract/synthesize)",
        severity="critical",
    ),
    ParityEntry(
        rule="source_attribution_completeness",
        description="Key fields must have source attribution",
        parity="both",
        runtime_gate="charity_metrics_aggregator.py:_track",
        judge_check="S-J-002",
        severity="high",
    ),
    # ========================================================================
    # RUNTIME GATE ONLY (no judge cross-check)
    # ========================================================================
    ParityEntry(
        rule="empty_parsed_json",
        description="parsed_json must not be empty for successful sources",
        parity="runtime_only",
        runtime_gate="synthesize.py:S-005 EmptyParsedJsonError",
        judge_check=None,
        severity="critical",
        recommendation="Low priority — this is a crawl bug detector, not a data quality check",
    ),
    ParityEntry(
        rule="content_substance_check",
        description="Raw content must have minimum substance (not empty/shell HTML)",
        parity="runtime_only",
        runtime_gate="orchestrator.py:_has_content_substance",
        judge_check=None,
        severity="high",
        recommendation="Add J-009: content substance validation in CrawlQualityJudge",
    ),
    ParityEntry(
        rule="db_write_confirmation",
        description="DB writes must succeed before marking source as succeeded",
        parity="runtime_only",
        runtime_gate="orchestrator.py:_store_raw_data/_store_raw_content_only",
        judge_check=None,
        severity="high",
        recommendation="Low priority — infrastructure check, not data quality",
    ),
    ParityEntry(
        rule="failure_ttl_reset",
        description="Permanent failures expire after FAILURE_TTL_DAYS",
        parity="runtime_only",
        runtime_gate="orchestrator.py:_should_skip_failed_source",
        judge_check=None,
        severity="medium",
        recommendation="Low priority — retry mechanism, not data quality",
    ),
    ParityEntry(
        rule="collector_parse_success",
        description="raw_content → parsed_json parse must succeed",
        parity="runtime_only",
        runtime_gate="Individual collector .parse() methods",
        judge_check=None,
        severity="high",
        recommendation="Add E-J-004: parse success rate check in ExtractQualityJudge",
    ),
    # ========================================================================
    # JUDGE CHECK ONLY (advisory, no code enforcement)
    # ========================================================================
    ParityEntry(
        rule="candid_seal_evidence_mismatch",
        description="Candid seal level should match reported transparency evidence",
        parity="judge_only",
        runtime_gate=None,
        judge_check="J-004",
        severity="medium",
        recommendation="Acceptable as advisory — Candid data inconsistency, not our bug",
    ),
    ParityEntry(
        rule="multi_source_revenue_divergence",
        description="Revenue should not diverge >80% across ProPublica/CN/Candid",
        parity="judge_only",
        runtime_gate=None,
        judge_check="J-008",
        severity="high",
        recommendation="Add aggregator check: null financials if revenue diverges >80% across sources",
    ),
    ParityEntry(
        rule="working_capital_bounds",
        description="Working capital months should be 0-120 (reasonable range)",
        parity="judge_only",
        runtime_gate=None,
        judge_check="S-J-005",
        severity="medium",
        recommendation="Add clamping in aggregator: clamp to 0-120 months",
    ),
    ParityEntry(
        rule="website_citation_depth",
        description="Citations should link to specific pages, not just homepage",
        parity="judge_only",
        runtime_gate=None,
        judge_check="S-J-002b",
        severity="low",
        recommendation="Acceptable as advisory — quality signal, not blocker",
    ),
    ParityEntry(
        rule="hallucination_prone_uncorroborated",
        description="Hallucination-prone fields without corroboration should be flagged",
        parity="judge_only",
        runtime_gate=None,
        judge_check="S-J-006",
        severity="medium",
        recommendation="Partially enforced via source_required_validator; judge catches remaining cases",
    ),
    ParityEntry(
        rule="bbb_name_threshold_gap",
        description="BBB name similarity: collector=60%, judge=85%",
        parity="judge_only",
        runtime_gate=None,
        judge_check="J-007",
        severity="medium",
        recommendation="Align collector threshold to 85% to match judge strictness",
    ),
]


def get_gaps() -> list[ParityEntry]:
    """Return all entries that lack full parity (runtime_only or judge_only)."""
    return [e for e in PARITY_MANIFEST if e.parity != "both"]


def get_critical_gaps() -> list[ParityEntry]:
    """Return critical/high severity entries lacking parity."""
    return [e for e in PARITY_MANIFEST if e.parity != "both" and e.severity in ("critical", "high")]


def print_summary() -> None:
    """Print a human-readable parity summary."""
    both = [e for e in PARITY_MANIFEST if e.parity == "both"]
    runtime_only = [e for e in PARITY_MANIFEST if e.parity == "runtime_only"]
    judge_only = [e for e in PARITY_MANIFEST if e.parity == "judge_only"]

    print(f"Parity Manifest: {len(PARITY_MANIFEST)} rules")
    print(f"  Both (parity achieved): {len(both)}")
    print(f"  Runtime gate only:      {len(runtime_only)}")
    print(f"  Judge check only:       {len(judge_only)}")
    print()

    critical_gaps = get_critical_gaps()
    if critical_gaps:
        print(f"Critical/High gaps needing attention ({len(critical_gaps)}):")
        for entry in critical_gaps:
            print(f"  [{entry.severity.upper()}] {entry.rule}: {entry.recommendation}")


if __name__ == "__main__":
    print_summary()
