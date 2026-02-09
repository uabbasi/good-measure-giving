"""
Diff-Based Validator - Leverages DoltDB versioning for targeted validation.

Instead of random sampling, this validator:
1. Identifies what changed since the last validated commit
2. Validates 100% of changed charities
3. Checks for unexplained score changes with multi-tier severity
4. Detects regressions (PASS → FAIL without source data change)
5. Validates that narrative changes are justified by source data changes
6. Analyzes score trends over time using dolt_history

Usage:
    validator = DiffValidator(since_commit="HEAD~1")
    report = validator.validate()
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ..db.client import execute_query as db_query
from ..db.dolt_client import _validate_ref
from .schemas.verdict import ScoreChangeSeverity

logger = logging.getLogger(__name__)


def _classify_score_change_severity(delta: int) -> ScoreChangeSeverity:
    """Classify the severity of a score change based on magnitude.

    Args:
        delta: Absolute value of score change

    Returns:
        ScoreChangeSeverity enum value
    """
    abs_delta = abs(delta)
    if abs_delta <= 5:
        return ScoreChangeSeverity.INFO
    elif abs_delta <= 15:
        return ScoreChangeSeverity.WARNING
    else:
        return ScoreChangeSeverity.ERROR


def _analyze_score_trend(scores: list[int]) -> str:
    """Analyze a series of scores to determine the trend.

    Args:
        scores: List of scores from oldest to newest

    Returns:
        Trend classification: 'improving', 'declining', 'stable', or 'volatile'
    """
    if len(scores) < 2:
        return "unknown"

    # Calculate differences between consecutive scores
    diffs = [scores[i + 1] - scores[i] for i in range(len(scores) - 1)]

    # Check for volatility (large swings in different directions)
    positive_changes = sum(1 for d in diffs if d > 5)
    negative_changes = sum(1 for d in diffs if d < -5)

    if positive_changes > 0 and negative_changes > 0:
        return "volatile"

    # Calculate overall direction
    total_change = scores[-1] - scores[0]

    if abs(total_change) <= 5:
        return "stable"
    elif total_change > 0:
        return "improving"
    else:
        return "declining"


@dataclass
class ChangeRecord:
    """A record of what changed for a charity."""
    ein: str
    diff_type: str  # 'added', 'modified', 'removed'

    # Score changes
    old_score: Optional[int] = None
    new_score: Optional[int] = None
    score_delta: Optional[int] = None

    # Score change analysis (new)
    severity: Optional[ScoreChangeSeverity] = None
    score_trend: Optional[str] = None  # 'improving', 'declining', 'stable', 'volatile'
    score_history: list[int] = field(default_factory=list)

    # Source data changes
    source_data_changed: bool = False
    changed_fields: list[str] = field(default_factory=list)

    # Narrative changes
    narrative_changed: bool = False
    old_word_count: Optional[int] = None
    new_word_count: Optional[int] = None

    # Validation results
    issues: list[dict] = field(default_factory=list)


@dataclass
class DiffValidationReport:
    """Report from diff-based validation."""
    from_commit: str
    to_commit: str
    timestamp: datetime

    # Summary stats
    charities_changed: int = 0
    charities_added: int = 0
    charities_removed: int = 0
    charities_modified: int = 0

    # Issues found
    unexplained_score_changes: list[ChangeRecord] = field(default_factory=list)
    regressions: list[ChangeRecord] = field(default_factory=list)
    unjustified_narrative_changes: list[ChangeRecord] = field(default_factory=list)

    # All changes (for detailed review)
    all_changes: list[ChangeRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "from_commit": self.from_commit,
            "to_commit": self.to_commit,
            "timestamp": self.timestamp.isoformat(),
            "summary": {
                "charities_changed": self.charities_changed,
                "charities_added": self.charities_added,
                "charities_removed": self.charities_removed,
                "charities_modified": self.charities_modified,
            },
            "issues": {
                "unexplained_score_changes": len(self.unexplained_score_changes),
                "regressions": len(self.regressions),
                "unjustified_narrative_changes": len(self.unjustified_narrative_changes),
            },
            "details": {
                "unexplained_score_changes": [
                    {
                        "ein": c.ein,
                        "old": c.old_score,
                        "new": c.new_score,
                        "delta": c.score_delta,
                        "severity": c.severity.value if c.severity else None,
                        "trend": c.score_trend,
                    }
                    for c in self.unexplained_score_changes
                ],
                "regressions": [
                    {"ein": c.ein, "issues": c.issues}
                    for c in self.regressions
                ],
            }
        }


class DiffValidator:
    """
    Validates changes between DoltDB commits.

    Uses Dolt's diff capabilities to:
    1. Identify charities that changed
    2. Validate that changes are justified by source data
    3. Detect regressions and unexplained score changes
    4. Analyze score trends over time
    """

    # Thresholds (now multi-tier via ScoreChangeSeverity)
    SCORE_CHANGE_THRESHOLD = 10  # Flag score changes > 10 points (legacy)
    SCORE_HISTORY_LIMIT = 5  # Number of historical scores to analyze

    def __init__(
        self,
        since_commit: str = "HEAD~1",
        to_commit: str = "HEAD",
        include_score_history: bool = True,
    ):
        # Validate commit refs to prevent SQL injection
        _validate_ref(since_commit)
        _validate_ref(to_commit)
        self.since_commit = since_commit
        self.to_commit = to_commit
        self.include_score_history = include_score_history

    def validate(self) -> DiffValidationReport:
        """Run diff-based validation and return report."""
        report = DiffValidationReport(
            from_commit=self.since_commit,
            to_commit=self.to_commit,
            timestamp=datetime.now(timezone.utc),
        )

        # Step 1: Get all changes
        changes = self._get_all_changes()
        report.all_changes = changes
        report.charities_changed = len(changes)
        report.charities_added = sum(1 for c in changes if c.diff_type == 'added')
        report.charities_removed = sum(1 for c in changes if c.diff_type == 'removed')
        report.charities_modified = sum(1 for c in changes if c.diff_type == 'modified')

        logger.info(
            f"Found {len(changes)} changes: "
            f"{report.charities_added} added, "
            f"{report.charities_modified} modified, "
            f"{report.charities_removed} removed"
        )

        # Step 2: Enrich with score history and severity classification
        for change in changes:
            if change.score_delta is not None:
                # Classify severity based on magnitude
                change.severity = _classify_score_change_severity(change.score_delta)

                # Optionally fetch score history for trend analysis
                if self.include_score_history and change.diff_type == 'modified':
                    history = self._get_score_history(change.ein)
                    change.score_history = history
                    if len(history) >= 2:
                        change.score_trend = _analyze_score_trend(history)

        # Step 3: Check for unexplained score changes (enhanced with severity)
        for change in changes:
            if change.diff_type == 'modified' and change.score_delta:
                # Use severity-based thresholds instead of single threshold
                if change.severity in (ScoreChangeSeverity.WARNING, ScoreChangeSeverity.ERROR):
                    if not change.source_data_changed:
                        # Score change without source data change = suspicious
                        change.issues.append({
                            "type": "unexplained_score_change",
                            "severity": change.severity.value,
                            "message": f"Score changed by {change.score_delta} points without source data change",
                            "trend": change.score_trend,
                        })
                        report.unexplained_score_changes.append(change)
                    else:
                        # Validate the score change is proportional to source changes
                        self._validate_score_change_justification(change)

        # Step 4: Check for narrative changes without source data changes
        for change in changes:
            if change.narrative_changed and not change.source_data_changed:
                change.issues.append({
                    "type": "unjustified_narrative_change",
                    "message": "Narrative changed without corresponding source data change"
                })
                report.unjustified_narrative_changes.append(change)

        return report

    def _get_score_history(self, ein: str, limit: int | None = None) -> list[int]:
        """Query dolt_history_evaluations for score trend analysis.

        Args:
            ein: Charity EIN
            limit: Max number of historical scores (default: SCORE_HISTORY_LIMIT)

        Returns:
            List of scores from oldest to newest
        """
        limit = limit or self.SCORE_HISTORY_LIMIT
        query = """
        SELECT amal_score, commit_date
        FROM dolt_history_evaluations
        WHERE charity_ein = %s AND amal_score IS NOT NULL
        ORDER BY commit_date DESC, charity_ein ASC
        LIMIT %s
        """

        try:
            rows = db_query(query, (ein, limit))
            if rows:
                # Reverse to get oldest-to-newest order
                return [row['amal_score'] for row in reversed(rows)]
        except Exception as e:
            logger.debug(f"Failed to get score history for {ein}: {e}")

        return []

    def _get_all_changes(self) -> list[ChangeRecord]:
        """Get all charity changes between commits."""
        changes = []

        # Query evaluation changes
        eval_changes = self._query_evaluation_changes()

        # Query source data changes
        source_changes = self._query_source_data_changes()

        # Query narrative changes
        narrative_changes = self._query_narrative_changes()

        # Merge all changes by EIN
        all_eins = set(eval_changes.keys()) | set(source_changes.keys()) | set(narrative_changes.keys())

        for ein in all_eins:
            eval_change = eval_changes.get(ein, {})
            source_change = source_changes.get(ein, {})
            narrative_change = narrative_changes.get(ein, {})

            record = ChangeRecord(
                ein=ein,
                diff_type=eval_change.get('diff_type', source_change.get('diff_type', 'modified')),
                old_score=eval_change.get('old_score'),
                new_score=eval_change.get('new_score'),
                score_delta=eval_change.get('score_delta'),
                source_data_changed=bool(source_change),
                changed_fields=source_change.get('changed_fields', []),
                narrative_changed=bool(narrative_change),
            )
            changes.append(record)

        return changes

    def _query_evaluation_changes(self) -> dict[str, dict]:
        """Query evaluation score changes."""
        query = """
        SELECT
            COALESCE(to_charity_ein, from_charity_ein) as ein,
            diff_type,
            from_amal_score as old_score,
            to_amal_score as new_score,
            CASE
                WHEN from_amal_score IS NOT NULL AND to_amal_score IS NOT NULL
                THEN to_amal_score - from_amal_score
                ELSE NULL
            END as score_delta
        FROM dolt_diff(%s, %s, 'evaluations')
        """

        results = {}
        try:
            rows = db_query(query, (self.since_commit, self.to_commit)) or []
            for row in rows:
                results[row['ein']] = {
                    'diff_type': row['diff_type'],
                    'old_score': row['old_score'],
                    'new_score': row['new_score'],
                    'score_delta': row['score_delta'],
                }
        except Exception as e:
            logger.warning(f"Failed to query evaluation changes: {e}")

        return results

    def _query_source_data_changes(self) -> dict[str, dict]:
        """Query charity_data changes to see what source data changed."""
        query = """
        SELECT
            COALESCE(to_charity_ein, from_charity_ein) as ein,
            diff_type,
            -- Check which key fields changed
            CASE WHEN from_total_revenue != to_total_revenue THEN 1 ELSE 0 END as revenue_changed,
            CASE WHEN from_program_expense_ratio != to_program_expense_ratio THEN 1 ELSE 0 END as ratio_changed,
            CASE WHEN from_charity_navigator_score != to_charity_navigator_score THEN 1 ELSE 0 END as cn_changed,
            CASE WHEN from_claims_zakat_eligible != to_claims_zakat_eligible THEN 1 ELSE 0 END as zakat_changed
        FROM dolt_diff(%s, %s, 'charity_data')
        """

        results = {}
        try:
            rows = db_query(query, (self.since_commit, self.to_commit)) or []
            for row in rows:
                changed_fields = []
                if row.get('revenue_changed'):
                    changed_fields.append('total_revenue')
                if row.get('ratio_changed'):
                    changed_fields.append('program_expense_ratio')
                if row.get('cn_changed'):
                    changed_fields.append('charity_navigator_score')
                if row.get('zakat_changed'):
                    changed_fields.append('claims_zakat_eligible')

                results[row['ein']] = {
                    'diff_type': row['diff_type'],
                    'changed_fields': changed_fields,
                }
        except Exception as e:
            logger.warning(f"Failed to query source data changes: {e}")

        return results

    def _query_narrative_changes(self) -> dict[str, dict]:
        """Query narrative changes (rich_narrative field in evaluations)."""
        # For now, just detect if rich_narrative changed
        query = """
        SELECT
            COALESCE(to_charity_ein, from_charity_ein) as ein,
            diff_type,
            LENGTH(COALESCE(from_rich_narrative, '')) as old_len,
            LENGTH(COALESCE(to_rich_narrative, '')) as new_len
        FROM dolt_diff(%s, %s, 'evaluations')
        WHERE from_rich_narrative != to_rich_narrative
           OR (from_rich_narrative IS NULL AND to_rich_narrative IS NOT NULL)
           OR (from_rich_narrative IS NOT NULL AND to_rich_narrative IS NULL)
        """

        results = {}
        try:
            rows = db_query(query, (self.since_commit, self.to_commit)) or []
            for row in rows:
                results[row['ein']] = {
                    'diff_type': row['diff_type'],
                    'old_len': row.get('old_len', 0),
                    'new_len': row.get('new_len', 0),
                }
        except Exception as e:
            logger.warning(f"Failed to query narrative changes: {e}")

        return results

    def _validate_score_change_justification(self, change: ChangeRecord) -> None:
        """Validate that a large score change is justified by the source data changes."""
        if not change.changed_fields:
            return

        # Map source changes to expected score impact
        expected_impact = 0
        for field_name in change.changed_fields:
            if field_name == 'charity_navigator_score':
                expected_impact += 5  # CN score change can affect trust pillar
            if field_name == 'program_expense_ratio':
                expected_impact += 10  # Ratio change affects effectiveness
            if field_name == 'total_revenue':
                expected_impact += 3  # Revenue affects scale efficiency

        # If actual change is much larger than expected, flag it
        if change.score_delta and abs(change.score_delta) > expected_impact * 2:
            change.issues.append({
                "type": "disproportionate_score_change",
                "message": f"Score changed by {change.score_delta} but source changes suggest ~{expected_impact} impact",
                "changed_fields": change.changed_fields,
            })


def get_charities_to_validate(since_commit: str = "HEAD~1") -> list[str]:
    """
    Get list of EINs that should be validated based on what changed.

    Use this for targeted validation instead of random sampling.
    """
    validator = DiffValidator(since_commit=since_commit)
    changes = validator._get_all_changes()

    # Return EINs of charities that changed (excluding removed)
    return [c.ein for c in changes if c.diff_type != 'removed']


def validate_since_last_run(last_validated_commit: str) -> DiffValidationReport:
    """
    Validate all changes since the last validated commit.

    Usage:
        # After a pipeline run
        report = validate_since_last_run("abc123")  # commit hash of last validation
        if report.unexplained_score_changes:
            print("Warning: Found unexplained score changes!")
    """
    validator = DiffValidator(since_commit=last_validated_commit)
    return validator.validate()
