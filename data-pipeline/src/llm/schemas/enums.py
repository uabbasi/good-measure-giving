"""Enums for V2 narrative workflow state machine.

These enums define the possible states for charity narratives.
Data completeness (collected/derived/reconciled) is computed from
the charities table, not stored as state.
"""

from enum import Enum


class NarrativeKind(str, Enum):
    """Type of narrative - baseline (concise) or rich (comprehensive)."""

    BASELINE = "baseline"
    RICH = "rich"


class WorkflowState(str, Enum):
    """V2 simplified workflow state - tracks narrative status only.

    Data completeness is computed from charities table:
    - collected = has rows in raw_scraped_data
    - derived = is_muslim_charity IS NOT NULL
    - reconciled = total_revenue IS NOT NULL

    Narrative workflow:
    - PENDING: Ready for narrative generation (has data)
    - BASELINE: Has baseline narrative (exportable)
    - RICH: Has rich narrative (exportable)
    - REJECTED: Excluded from pipeline

    Export eligibility: state IN (BASELINE, RICH) AND judge_score >= 60
    """

    PENDING = "pending"      # Ready for narrative generation
    BASELINE = "baseline"    # Has baseline narrative
    RICH = "rich"            # Has rich narrative
    REJECTED = "rejected"    # Excluded from pipeline


class RejectionReason(str, Enum):
    """Reason for rejecting a narrative."""

    INSUFFICIENT_DATA = "insufficient_data"
    OUT_OF_SCOPE = "out_of_scope"
    LOW_PRIORITY = "low_priority"
    QUALITY_ISSUE = "quality_issue"
    DUPLICATE = "duplicate"
    GENERATION_FAILED = "generation_failed"


# Quality thresholds for auto-approval
SCORE_AUTO_APPROVE = 85  # >= 85: auto-approve
SCORE_AUTO_REJECT = 60   # < 60: auto-reject
# 60-84: optional manual review


def is_exportable_state(state: WorkflowState) -> bool:
    """Check if a state is ready for export."""
    return state in (WorkflowState.BASELINE, WorkflowState.RICH)


def needs_review(state: WorkflowState, judge_score: float | None) -> bool:
    """Check if narrative needs manual review based on score."""
    if state not in (WorkflowState.BASELINE, WorkflowState.RICH):
        return False
    if judge_score is None:
        return True
    return SCORE_AUTO_REJECT <= judge_score < SCORE_AUTO_APPROVE


def should_auto_reject(judge_score: float | None) -> bool:
    """Check if narrative should be auto-rejected."""
    if judge_score is None:
        return False
    return judge_score < SCORE_AUTO_REJECT


# Legacy state mapping for migration
LEGACY_STATE_MAP = {
    "not_started": WorkflowState.PENDING,
    "collected": WorkflowState.PENDING,
    "derived": WorkflowState.PENDING,
    "reconciled": WorkflowState.PENDING,
    "baseline_queued": WorkflowState.PENDING,
    "baseline_review": WorkflowState.BASELINE,
    "rich_queued": WorkflowState.BASELINE,
    "rich_review": WorkflowState.RICH,
    "approved": WorkflowState.RICH,  # Approved with rich -> RICH
    "rejected": WorkflowState.REJECTED,
}
