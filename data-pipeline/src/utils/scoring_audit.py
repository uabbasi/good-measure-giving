"""
Scoring Audit Trail - Captures scoring decisions for debugging and transparency.

When scores are affected by potentially unreliable data, this module logs:
- Which fields affected scores
- Their verification/corroboration status
- The score impact of each field usage

This enables:
1. Debugging of unexpected scores
2. Transparency about data reliability
3. Detection of systematic data quality issues
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CorroborationStatus(Enum):
    """Status of field corroboration across sources."""

    CORROBORATED = "corroborated"  # Multiple sources agree
    SINGLE_SOURCE = "single_source"  # Only one source, but authoritative
    UNCORROBORATED = "uncorroborated"  # Website claim without third-party backup
    CONFLICTING = "conflicting"  # Sources disagree
    UNKNOWN = "unknown"  # Status cannot be determined


class ScoreImpact(Enum):
    """How much a field affects the final score."""

    HIGH = "high"  # Field directly contributes 5+ points
    MEDIUM = "medium"  # Field contributes 2-4 points
    LOW = "low"  # Field contributes 1-2 points
    INDIRECT = "indirect"  # Field affects other calculations


@dataclass
class ScoringAuditEntry:
    """A single audit entry for field usage in scoring.

    Captures when a field is used in scoring and whether
    the data is reliable or potentially problematic.
    """

    ein: str
    field_name: str
    value_used: Any
    sources_consulted: list[str]
    corroboration_status: CorroborationStatus
    score_impact: ScoreImpact
    timestamp: datetime = field(default_factory=datetime.now)
    scorer_name: str = ""
    score_component: str = ""  # e.g., "verification_tier", "counterfactual"
    points_affected: int = 0
    warning_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "ein": self.ein,
            "field_name": self.field_name,
            "value_used": self._serialize_value(self.value_used),
            "sources_consulted": self.sources_consulted,
            "corroboration_status": self.corroboration_status.value,
            "score_impact": self.score_impact.value,
            "timestamp": self.timestamp.isoformat(),
            "scorer_name": self.scorer_name,
            "score_component": self.score_component,
            "points_affected": self.points_affected,
            "warning_message": self.warning_message,
        }

    def _serialize_value(self, value: Any) -> Any:
        """Serialize value for JSON output."""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (list, tuple)):
            return [self._serialize_value(v) for v in value]
        if isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        return str(value)


class ScoringAuditLog:
    """Collects audit entries during scoring for a batch of charities.

    Usage:
        audit_log = ScoringAuditLog()

        # During scoring
        audit_log.log_field_usage(
            ein="12-3456789",
            field_name="third_party_evaluated",
            value=True,
            sources=["website_claims"],
            corroborated=False,
            impact=ScoreImpact.HIGH,
            scorer="TrustScorer",
            component="verification_tier",
            points=10
        )

        # Get warnings for problematic data usage
        warnings = audit_log.get_warnings()

        # Export for debugging
        audit_log.export_to_json("/tmp/scoring_audit.json")
    """

    def __init__(self):
        self._entries: list[ScoringAuditEntry] = []
        self._warnings: list[ScoringAuditEntry] = []

    def log_field_usage(
        self,
        ein: str,
        field_name: str,
        value: Any,
        sources: list[str],
        corroborated: bool,
        impact: ScoreImpact,
        scorer: str = "",
        component: str = "",
        points: int = 0,
        warning: Optional[str] = None,
    ) -> ScoringAuditEntry:
        """Log a field usage during scoring.

        Args:
            ein: Charity EIN
            field_name: Name of the field used (e.g., "third_party_evaluated")
            value: The value that was used in scoring
            sources: List of data sources consulted
            corroborated: Whether the field value was corroborated
            impact: Score impact level (HIGH, MEDIUM, LOW, INDIRECT)
            scorer: Name of the scorer class (e.g., "TrustScorer")
            component: Score component affected (e.g., "verification_tier")
            points: Number of points affected
            warning: Optional warning message for problematic usage

        Returns:
            The created audit entry
        """
        # Determine corroboration status
        # Priority: corroborated flag takes precedence over source count
        if not corroborated:
            status = CorroborationStatus.UNCORROBORATED
        elif len(sources) >= 2:
            status = CorroborationStatus.CORROBORATED
        elif len(sources) == 1:
            status = CorroborationStatus.SINGLE_SOURCE
        else:
            status = CorroborationStatus.UNKNOWN

        entry = ScoringAuditEntry(
            ein=ein,
            field_name=field_name,
            value_used=value,
            sources_consulted=sources,
            corroboration_status=status,
            score_impact=impact,
            scorer_name=scorer,
            score_component=component,
            points_affected=points,
            warning_message=warning,
        )

        self._entries.append(entry)

        # Track warnings for uncorroborated high-impact fields
        if warning or (
            status == CorroborationStatus.UNCORROBORATED
            and impact in (ScoreImpact.HIGH, ScoreImpact.MEDIUM)
        ):
            if not warning:
                entry.warning_message = (
                    f"AUDIT WARNING: EIN {ein}: {field_name}={value} used for {component} score "
                    f"but corroboration_status shows {status.value} ({', '.join(sources)})"
                )
            self._warnings.append(entry)
            logger.warning(entry.warning_message)

        return entry

    def get_warnings(self) -> list[ScoringAuditEntry]:
        """Get entries where corroboration failed but field was used for scoring.

        Returns:
            List of audit entries with warnings
        """
        return self._warnings.copy()

    def get_all_entries(self) -> list[ScoringAuditEntry]:
        """Get all audit entries.

        Returns:
            List of all audit entries
        """
        return self._entries.copy()

    def get_summary_for_ein(self, ein: str) -> dict:
        """Get all audit entries for a specific charity.

        Args:
            ein: Charity EIN

        Returns:
            Dictionary with summary and entries for the charity
        """
        entries = [e for e in self._entries if e.ein == ein]
        warnings = [e for e in entries if e.warning_message]

        # Categorize by corroboration status
        by_status: dict[str, list[dict]] = {}
        for entry in entries:
            status = entry.corroboration_status.value
            if status not in by_status:
                by_status[status] = []
            by_status[status].append(entry.to_dict())

        return {
            "ein": ein,
            "total_entries": len(entries),
            "warnings_count": len(warnings),
            "entries_by_status": by_status,
            "warnings": [e.to_dict() for e in warnings],
            "all_entries": [e.to_dict() for e in entries],
        }

    def export_to_json(self, filepath: str | Path) -> None:
        """Export audit log to JSON file.

        Args:
            filepath: Path to output JSON file
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "generated_at": datetime.now().isoformat(),
            "total_entries": len(self._entries),
            "total_warnings": len(self._warnings),
            "entries": [e.to_dict() for e in self._entries],
            "warnings": [e.to_dict() for e in self._warnings],
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported {len(self._entries)} audit entries to {filepath}")

    def clear(self) -> None:
        """Clear all entries (for reuse between batches)."""
        self._entries.clear()
        self._warnings.clear()

    def __len__(self) -> int:
        return len(self._entries)


# Global audit log instance for convenient access
_global_audit_log: Optional[ScoringAuditLog] = None


def get_audit_log() -> ScoringAuditLog:
    """Get the global audit log instance.

    Creates a new instance if one doesn't exist.

    Returns:
        The global ScoringAuditLog instance
    """
    global _global_audit_log
    if _global_audit_log is None:
        _global_audit_log = ScoringAuditLog()
    return _global_audit_log


def reset_audit_log() -> ScoringAuditLog:
    """Reset the global audit log (for testing or new batch runs).

    Returns:
        A fresh ScoringAuditLog instance
    """
    global _global_audit_log
    _global_audit_log = ScoringAuditLog()
    return _global_audit_log
