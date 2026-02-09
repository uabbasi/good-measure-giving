"""
Conflict Resolver - Detects and logs data conflicts between sources.

This service implements conflict detection logic to identify when multiple
sources provide different values for the same field, and logs these conflicts
for audit purposes.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.models.reconciled_profile import ConflictRecord

logger = logging.getLogger(__name__)


class ConflictResolver:
    """Detects and logs conflicts between data sources."""

    def detect_conflicts(self, field_name: str, source_values: Dict[str, Any]) -> bool:
        """
        Check if multiple source values represent a conflict.

        Args:
            field_name: Name of the field being checked
            source_values: Map of source_name -> value

        Returns:
            True if conflicting values exist, False otherwise
        """
        # Filter out None/null values
        non_null_values = {
            source: value for source, value in source_values.items() if value is not None and value != ""
        }

        if len(non_null_values) <= 1:
            # No conflict if only one source has data
            return False

        # Check if all non-null values are the same
        unique_values = set()
        for value in non_null_values.values():
            # Normalize for comparison
            if isinstance(value, str):
                normalized = value.strip().lower()
            elif isinstance(value, list):
                # For lists, sort and convert to tuple for hashing
                normalized = tuple(sorted(str(v).strip().lower() for v in value))
            elif isinstance(value, (int, float)):
                # For numbers, use the value directly
                normalized = value
            else:
                normalized = str(value)

            unique_values.add(str(normalized))

        # Conflict exists if we have multiple unique normalized values
        has_conflict = len(unique_values) > 1

        if has_conflict:
            logger.debug(f"Conflict detected for field '{field_name}': {len(unique_values)} unique values")

        return has_conflict

    def log_conflict(
        self,
        ein: str,
        field_name: str,
        source_values: Dict[str, Any],
        selected_source: str,
        selection_reason: str,
        db_conn=None,
    ) -> ConflictRecord:
        """
        Store conflict record for audit purposes.

        Args:
            ein: Charity EIN
            field_name: Field with conflicting values
            source_values: Map of source_name -> conflicting_value
            selected_source: Which source was chosen
            selection_reason: Why this source was selected
            db_conn: Optional database connection to store in charities table

        Returns:
            ConflictRecord object
        """
        conflict = ConflictRecord(
            field_name=field_name,
            source_values=source_values,
            selected_source=selected_source,
            selection_reason=selection_reason,
            timestamp=datetime.now(timezone.utc),  # Use timezone-aware UTC instead of deprecated utcnow()
        )

        logger.info(
            f"Conflict resolved for EIN {ein}, field '{field_name}': selected {selected_source} ({selection_reason})"
        )

        if db_conn:
            self._store_conflict_in_db(ein, conflict, db_conn)

        return conflict

    def _store_conflict_in_db(self, ein: str, conflict: ConflictRecord, db_conn):
        """
        Append conflict to charities.reconciliation_conflicts JSON field.

        Args:
            ein: Charity EIN
            conflict: ConflictRecord to store
            db_conn: SQLite database connection
        """
        cursor = db_conn.cursor()

        # Get existing conflicts
        cursor.execute("SELECT reconciliation_conflicts FROM charities WHERE ein = ?", (ein,))
        row = cursor.fetchone()

        if row and row[0]:
            try:
                existing_conflicts = json.loads(row[0])
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in reconciliation_conflicts for EIN {ein}, resetting")
                existing_conflicts = []
        else:
            existing_conflicts = []

        # Append new conflict
        existing_conflicts.append(conflict.model_dump(mode="json"))

        # Update database
        cursor.execute(
            "UPDATE charities SET reconciliation_conflicts = ? WHERE ein = ?", (json.dumps(existing_conflicts), ein)
        )

        logger.debug(f"Stored conflict in database for EIN {ein}")

    def get_selection_reason(
        self, field_name: str, source_values: Dict[str, Any], selected_source: str, priority_order: list[str]
    ) -> str:
        """
        Generate a human-readable reason for source selection.

        Args:
            field_name: Name of the field
            source_values: Map of source -> value
            selected_source: Source that was chosen
            priority_order: Priority order of sources for this field

        Returns:
            Reason string explaining the selection
        """
        source_values[selected_source]

        # Check if selection was due to data quality factors
        completeness_scores = {}
        for source, value in source_values.items():
            if value is None or value == "":
                completeness_scores[source] = 0
            elif isinstance(value, str):
                completeness_scores[source] = len(value.strip())
            elif isinstance(value, list):
                completeness_scores[source] = len(value)
            else:
                completeness_scores[source] = 1

        max_completeness = max(completeness_scores.values()) if completeness_scores else 0
        selected_completeness = completeness_scores.get(selected_source, 0)

        # Determine reason
        if selected_completeness == max_completeness and selected_completeness > 0:
            # Check if selected source is highest priority (with safety check for empty list)
            if priority_order and selected_source == priority_order[0]:
                return f"Highest priority source with data (priority order: {', '.join(priority_order)})"
            else:
                other_complete = [
                    s for s, score in completeness_scores.items() if score == max_completeness and s != selected_source
                ]
                if other_complete:
                    # Safe access to other_complete[0] since we checked it's not empty
                    return f"More complete data ({selected_completeness} vs {completeness_scores.get(other_complete[0], 0)})"
                else:
                    return f"Only source with complete data (completeness: {selected_completeness})"
        else:
            if priority_order:
                return f"Selected by priority hierarchy: {', '.join(priority_order)}"
            else:
                return "Selected by default (no priority order defined)"
