"""
Reconciliation Reporter - Generates readable summary reports for reconciliation results.

Provides clear BEFORE → AFTER views showing:
- Source data conflicts
- Selection rationale
- Field changes
- Data quality indicators
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class FieldReconciliation:
    """Tracks reconciliation decision for a single field."""

    field_name: str
    field_type: str
    source_values: Dict[str, Any]
    selected_value: Any
    selected_source: Optional[str]
    rationale: str
    is_conflict: bool
    is_merged: bool
    old_value: Any = None
    is_new: bool = False
    is_changed: bool = False


@dataclass
class ReconciliationReport:
    """Complete reconciliation report for a charity."""

    ein: str
    charity_name: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sources_found: List[str] = field(default_factory=list)
    fields_reconciled: List[FieldReconciliation] = field(default_factory=list)
    success: bool = True
    error_message: Optional[str] = None


class ReconciliationReporter:
    """Generates human-readable reconciliation reports."""

    def __init__(self):
        self.reports: Dict[str, ReconciliationReport] = {}

    def start_charity_report(self, ein: str, charity_name: str, sources: List[str]):
        """Initialize a new charity reconciliation report."""
        self.reports[ein] = ReconciliationReport(ein=ein, charity_name=charity_name, sources_found=sources)

    def add_field_reconciliation(self, ein: str, field_recon: FieldReconciliation):
        """Add a field reconciliation to the report."""
        if ein in self.reports:
            self.reports[ein].fields_reconciled.append(field_recon)

    def mark_error(self, ein: str, error_message: str):
        """Mark report as failed with error."""
        if ein in self.reports:
            self.reports[ein].success = False
            self.reports[ein].error_message = error_message

    def generate_summary(self, ein: str) -> str:
        """
        Generate a readable summary report for a charity.

        Returns formatted text with BEFORE → AFTER view.
        """
        if ein not in self.reports:
            return f"No report found for EIN {ein}"

        report = self.reports[ein]
        lines = []

        # Header
        lines.append("")
        lines.append("=" * 80)
        lines.append(f"RECONCILIATION REPORT: {report.charity_name} (EIN: {ein})")
        lines.append("=" * 80)
        lines.append(f"Timestamp: {report.timestamp}")
        lines.append(f"Sources: {', '.join(report.sources_found)} ({len(report.sources_found)} total)")
        lines.append(f"Fields Reconciled: {len(report.fields_reconciled)}")
        lines.append("")

        if not report.success:
            lines.append(f"❌ ERROR: {report.error_message}")
            lines.append("")
            return "\n".join(lines)

        # Group fields by category
        categories = {"Financial": [], "Ratings": [], "Mission & Programs": [], "Contact": [], "Other": []}

        for field_rec in report.fields_reconciled:
            if field_rec.field_name in [
                "total_revenue",
                "total_expenses",
                "program_expenses",
                "admin_expenses",
                "fundraising_expenses",
                "program_expense_ratio",
                "admin_expense_ratio",
                "fundraising_expense_ratio",
                "total_assets",
                "total_liabilities",
                "net_assets",
                "fiscal_year_end",
            ]:
                categories["Financial"].append(field_rec)
            elif field_rec.field_name in [
                "overall_score",
                "financial_score",
                "accountability_score",
                "impact_score",
                "leadership_score",
                "culture_score",
            ]:
                categories["Ratings"].append(field_rec)
            elif field_rec.field_name in ["mission", "programs", "populations_served", "geographic_coverage"]:
                categories["Mission & Programs"].append(field_rec)
            elif field_rec.field_name in ["website", "email", "phone", "address"]:
                categories["Contact"].append(field_rec)
            else:
                categories["Other"].append(field_rec)

        # Generate sections for each category
        for category_name, fields in categories.items():
            if not fields:
                continue

            lines.append(f"─── {category_name} ({'─' * (72 - len(category_name))})")
            lines.append("")

            for field_rec in fields:
                lines.extend(self._format_field_reconciliation(field_rec))
                lines.append("")

        # Summary statistics
        lines.append("=" * 80)
        lines.append("SUMMARY")
        lines.append("=" * 80)

        new_count = sum(1 for f in report.fields_reconciled if f.is_new)
        changed_count = sum(1 for f in report.fields_reconciled if f.is_changed)
        unchanged_count = len(report.fields_reconciled) - new_count - changed_count
        conflict_count = sum(1 for f in report.fields_reconciled if f.is_conflict)
        merged_count = sum(1 for f in report.fields_reconciled if f.is_merged)

        lines.append(f"  New fields:       {new_count}")
        lines.append(f"  Changed fields:   {changed_count}")
        lines.append(f"  Unchanged fields: {unchanged_count}")
        lines.append(f"  Conflicts resolved: {conflict_count}")
        lines.append(f"  Lists merged:     {merged_count}")
        lines.append("")

        return "\n".join(lines)

    def _format_field_reconciliation(self, field_rec: FieldReconciliation) -> List[str]:
        """Format a single field reconciliation as readable text."""
        lines = []

        # Field header with status indicator
        status = "🆕 NEW" if field_rec.is_new else "✏️  CHANGED" if field_rec.is_changed else "✓ UNCHANGED"
        lines.append(f"  {field_rec.field_name} ({field_rec.field_type}) [{status}]")

        # BEFORE section - show all source values
        if len(field_rec.source_values) > 1:
            lines.append(f"    BEFORE: {len(field_rec.source_values)} sources")
            for source, value in field_rec.source_values.items():
                formatted_value = self._format_value(value, max_len=60)
                lines.append(f"      • [{source}] {formatted_value}")
        else:
            source = list(field_rec.source_values.keys())[0]
            value = field_rec.source_values[source]
            formatted_value = self._format_value(value, max_len=60)
            lines.append(f"    BEFORE: [{source}] {formatted_value}")

        # AFTER section - show selected/merged result
        formatted_result = self._format_value(field_rec.selected_value, max_len=60)

        if field_rec.is_merged:
            lines.append(f"    AFTER:  {formatted_result}")
            lines.append(f"    ℹ️  {field_rec.rationale}")
        elif field_rec.is_conflict:
            lines.append(f"    AFTER:  {formatted_result}")
            lines.append(f"    ⚠️  {field_rec.rationale}")
        elif field_rec.selected_source:
            lines.append(f"    AFTER:  {formatted_result}")
            lines.append(f"    ℹ️  {field_rec.rationale}")
        else:
            lines.append(f"    AFTER:  {formatted_result}")

        return lines

    def _format_value(self, value: Any, max_len: int = 60) -> str:
        """Format a value for display."""
        if value is None:
            return "NULL"
        elif isinstance(value, list):
            if not value:
                return "[]"
            if len(value) <= 3:
                items = ", ".join(str(v)[:30] for v in value)
                return f"[{items}]"
            else:
                items = ", ".join(str(v)[:30] for v in value[:3])
                return f"[{items}, ... +{len(value) - 3} more]"
        elif isinstance(value, (int, float)):
            if abs(value) >= 1000:
                return f"${value:,.2f}" if isinstance(value, float) else f"${value:,}"
            else:
                return f"{value:.2f}" if isinstance(value, float) else str(value)
        elif isinstance(value, str):
            if len(value) > max_len:
                return f"{value[:max_len]}..."
            return value
        else:
            return str(value)[:max_len]

    def generate_batch_summary(self, eins: List[str]) -> str:
        """Generate summary for batch reconciliation."""
        lines = []
        lines.append("")
        lines.append("=" * 80)
        lines.append("BATCH RECONCILIATION SUMMARY")
        lines.append("=" * 80)
        lines.append(f"Total Charities: {len(eins)}")
        lines.append("")

        successful = sum(1 for ein in eins if ein in self.reports and self.reports[ein].success)
        failed = sum(1 for ein in eins if ein in self.reports and not self.reports[ein].success)

        lines.append(f"  Successful: {successful}")
        lines.append(f"  Failed:     {failed}")
        lines.append("")

        if successful > 0:
            total_fields = sum(
                len(self.reports[ein].fields_reconciled)
                for ein in eins
                if ein in self.reports and self.reports[ein].success
            )
            # Safe division with check (successful is already > 0 from if condition)
            avg_fields = total_fields / successful if successful > 0 else 0

            lines.append(f"  Average fields per charity: {avg_fields:.1f}")

        return "\n".join(lines)
