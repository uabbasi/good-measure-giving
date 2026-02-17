"""Data access repositories for DoltDB.

Simple CRUD operations for each table.
Audit logging is handled natively by Dolt's versioning.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from .client import execute_query


def _json_default(obj: Any) -> Any:
    """Handle non-serializable objects for JSON encoding."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _serialize_json(value: Any) -> str | None:
    """Serialize a value to JSON string for storage."""
    if value is None:
        return None
    return json.dumps(value, default=_json_default)


def _deserialize_json(value: str | bytes | None) -> Any:
    """Deserialize a JSON string from storage."""
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if isinstance(value, str):
        return json.loads(value)
    return value  # Already parsed by driver


def _generate_uuid() -> str:
    """Generate a UUID string."""
    return str(uuid.uuid4())


@dataclass
class Charity:
    """Charity record."""

    ein: str
    name: str
    mission: str | None = None
    website: str | None = None
    category: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None


@dataclass
class CharityData:
    """Synthesized charity data."""

    charity_ein: str
    # Muslim classification (deterministic keyword-based)
    has_islamic_identity: bool | None = None
    serves_muslim_populations: bool | None = None
    muslim_charity_fit: str | None = None  # 'high', 'medium', 'low'
    # Financial metrics
    total_revenue: int | None = None
    program_expenses: int | None = None
    admin_expenses: int | None = None
    fundraising_expenses: int | None = None
    program_expense_ratio: float | None = None
    charity_navigator_score: float | None = None
    transparency_score: float | None = None
    nonprofit_size_tier: str | None = None  # 'large_nonprofit', 'mid_nonprofit', 'small_nonprofit'
    # Financial health (balance sheet data)
    total_assets: int | None = None
    total_liabilities: int | None = None
    net_assets: int | None = None
    # Additional fields from aggregator
    detected_cause_area: str | None = None
    claims_zakat_eligible: bool | None = None
    beneficiaries_served_annually: int | None = None
    has_annual_report: bool | None = None
    has_audited_financials: bool | None = None
    candid_seal: str | None = None
    # Source attribution - maps field name to {source_name, source_url, value, timestamp}
    source_attribution: dict | None = None
    # Cause area fields (from synthesize spec)
    cause_tags: list[str] | None = None
    ntee_code: str | None = None
    cause_detection_source: str | None = None  # 'internal_signals' or 'unknown'
    # Derived fields
    is_conflict_zone: bool | None = None
    working_capital_months: float | None = None
    # Category fields (from charity_categories.yaml or detected_cause_area)
    primary_category: str | None = None  # MECE category for donor discovery
    category_importance: str | None = None  # HIGH/MEDIUM/LOW
    category_neglectedness: str | None = None  # HIGH/MEDIUM/LOW
    # Evaluation track (for alternative scoring rubrics)
    evaluation_track: str | None = None  # 'STANDARD', 'NEW_ORG', 'RESEARCH_POLICY'
    founded_year: int | None = None  # Year the organization was founded
    # Policy influence data (for RESEARCH_POLICY track organizations)
    policy_influence: dict | None = None  # JSONB: publications, policy_wins, govt_citations, etc.
    # Governance fields
    board_size: int | None = None
    independent_board_members: int | None = None
    ceo_compensation: int | None = None
    # Form 990 status
    form_990_exempt: bool | None = None
    form_990_exempt_reason: str | None = None
    # Targeting fields
    populations_served: list[str] | None = None
    geographic_coverage: list[str] | None = None
    # Website evidence signals (used in scoring, now persisted for audit trail)
    website_evidence_signals: dict | None = None
    # Program focus tags (LLM-extracted from mission/programs for similarity matching)
    program_focus_tags: list[str] | None = None
    # Strategic classification (LLM-classified archetype + scores for Strategic Believer lens)
    strategic_classification: dict | None = None
    # Zakat metadata (asnaf categories, policy URLs, verification, islamic identity signals)
    zakat_metadata: dict | None = None
    # Strategic evidence (deterministic signals for strategic narrative grounding)
    strategic_evidence: dict | None = None
    # Theory of change (extracted from website/PDFs)
    theory_of_change: str | None = None
    # Grants made (from Form 990 Schedule I/F)
    grants_made: list[dict] | None = None
    # Full CharityMetrics blob (single source of truth for baseline phase)
    metrics_json: dict | None = None
    # Scorer-critical fields (individual columns for queryability)
    total_expenses: int | None = None
    cn_overall_score: float | None = None
    cn_financial_score: float | None = None
    cn_accountability_score: float | None = None
    employees_count: int | None = None
    volunteers_count: int | None = None
    has_theory_of_change: bool | None = None
    reports_outcomes: bool | None = None
    has_outcome_methodology: bool | None = None
    has_multi_year_metrics: bool | None = None
    third_party_evaluated: bool | None = None
    evaluation_sources: list[str] | None = None
    receives_foundation_grants: bool | None = None
    candid_metrics_count: int | None = None
    candid_max_years_tracked: int | None = None
    no_filings: bool | None = None
    zakat_claim_evidence: str | None = None


@dataclass
class Evaluation:
    """Evaluation and narrative."""

    charity_ein: str
    amal_score: int | None = None
    wallet_tag: str | None = None
    confidence_tier: str | None = None
    impact_tier: str | None = None
    zakat_classification: str | None = None
    confidence_scores: dict | None = None
    score_details: dict | None = None  # Full scorer output (all assessments)
    impact_scores: dict | None = None
    baseline_narrative: dict | None = None
    rich_narrative: dict | None = None
    # Multi-lens scoring
    strategic_score: int | None = None
    zakat_score: int | None = None
    score_profiles: dict | None = None  # Full dimension breakdowns for all 3 lenses
    strategic_narrative: dict | None = None
    rich_strategic_narrative: dict | None = None
    zakat_narrative: dict | None = None
    judge_score: int | None = None
    information_density: float | None = None
    rubric_version: str | None = None
    state: str = "pending"


class CharityRepository:
    """Charity table operations."""

    # Columns that can be inserted/updated
    COLUMNS = ["ein", "name", "mission", "website", "category", "address", "city", "state", "zip"]

    def upsert(self, charity: Charity | dict) -> None:
        """Insert or update charity."""
        data = charity.__dict__ if isinstance(charity, Charity) else charity
        # Filter to known columns only (prevents SQL injection via dict keys)
        data = {k: v for k, v in data.items() if v is not None and k in self.COLUMNS}

        if not data.get("ein"):
            raise ValueError("EIN is required for charity upsert")

        columns = list(data.keys())
        placeholders = ", ".join(["%s"] * len(columns))
        update_clause = ", ".join([f"`{col}` = VALUES(`{col}`)" for col in columns if col != "ein"])

        sql = f"""
            INSERT INTO charities ({", ".join(f"`{c}`" for c in columns)})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE {update_clause}
        """
        execute_query(sql, tuple(data.values()), fetch="none")

    def get(self, ein: str) -> dict | None:
        """Get charity by EIN."""
        return execute_query(
            "SELECT * FROM charities WHERE ein = %s",
            (ein,),
            fetch="one",
        )

    def get_all(self, eins: list[str] | None = None) -> list[dict]:
        """Get all charities, optionally filtered by EINs."""
        if eins:
            placeholders = ", ".join(["%s"] * len(eins))
            return (
                execute_query(
                    f"SELECT * FROM charities WHERE ein IN ({placeholders})",
                    tuple(eins),
                )
                or []
            )
        return execute_query("SELECT * FROM charities") or []

    def exists(self, ein: str) -> bool:
        """Check if charity exists."""
        result = execute_query(
            "SELECT 1 FROM charities WHERE ein = %s LIMIT 1",
            (ein,),
            fetch="one",
        )
        return result is not None


class RawDataRepository:
    """Raw scraped data operations."""

    # JSON columns that need serialization
    JSON_COLUMNS = {"parsed_json"}

    def upsert(
        self,
        charity_ein: str,
        source: str,
        parsed_json: dict,
        success: bool = True,
        error_message: str | None = None,
        raw_content: str | None = None,
        reset_retry: bool = True,
    ) -> None:
        """Insert or update raw data for a source."""
        data = {
            "charity_ein": charity_ein,
            "source": source,
            "parsed_json": _serialize_json(parsed_json),
            "success": success,
            "error_message": error_message,
        }
        if raw_content:
            data["raw_content"] = raw_content
        if success and reset_retry:
            data["retry_count"] = 0

        # Check if row exists
        existing = self.get_by_source(charity_ein, source)

        if existing:
            # Update existing row
            set_clause = ", ".join([f"{k} = %s" for k in data.keys() if k not in ("charity_ein", "source")])
            values = [v for k, v in data.items() if k not in ("charity_ein", "source")]
            values.extend([charity_ein, source])

            execute_query(
                f"UPDATE raw_scraped_data SET {set_clause}, scraped_at = CURRENT_TIMESTAMP WHERE charity_ein = %s AND source = %s",
                tuple(values),
                fetch="none",
            )
        else:
            # Insert new row
            data["id"] = _generate_uuid()
            columns = list(data.keys())
            placeholders = ", ".join(["%s"] * len(columns))

            execute_query(
                f"INSERT INTO raw_scraped_data ({', '.join(columns)}) VALUES ({placeholders})",
                tuple(data.values()),
                fetch="none",
            )

    def increment_retry_count(self, ein: str, source: str, error_message: str) -> int:
        """Increment retry count for a failed source and return new count."""
        existing = self.get_by_source(ein, source)
        current_count = existing.get("retry_count", 0) if existing else 0
        new_count = current_count + 1

        if existing:
            execute_query(
                "UPDATE raw_scraped_data SET retry_count = %s, success = FALSE, error_message = %s WHERE charity_ein = %s AND source = %s",
                (new_count, error_message, ein, source),
                fetch="none",
            )
        else:
            execute_query(
                "INSERT INTO raw_scraped_data (id, charity_ein, source, success, error_message, retry_count, parsed_json) VALUES (%s, %s, %s, FALSE, %s, %s, %s)",
                (_generate_uuid(), ein, source, error_message, new_count, "{}"),
                fetch="none",
            )

        return new_count

    def reset_retry_count(self, ein: str, source: str) -> None:
        """Reset retry count for a source, allowing re-fetch after failure TTL expiry."""
        execute_query(
            "UPDATE raw_scraped_data SET retry_count = 0, success = FALSE, error_message = 'reset: failure TTL expired' WHERE charity_ein = %s AND source = %s",
            (ein, source),
            fetch="none",
        )

    def store_raw(
        self,
        charity_ein: str,
        source: str,
        raw_content: str,
        success: bool = True,
        error_message: str | None = None,
    ) -> None:
        """Store raw fetched content (fetch phase only)."""
        existing = self.get_by_source(charity_ein, source)

        if existing:
            update_parts = ["raw_content = %s", "success = %s", "scraped_at = CURRENT_TIMESTAMP"]
            values = [raw_content, success]

            if error_message is not None:
                update_parts.append("error_message = %s")
                values.append(error_message)
            if success:
                update_parts.append("retry_count = 0")

            values.extend([charity_ein, source])
            execute_query(
                f"UPDATE raw_scraped_data SET {', '.join(update_parts)} WHERE charity_ein = %s AND source = %s",
                tuple(values),
                fetch="none",
            )
        else:
            execute_query(
                "INSERT INTO raw_scraped_data (id, charity_ein, source, raw_content, success, error_message, retry_count) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (_generate_uuid(), charity_ein, source, raw_content, success, error_message, 0 if success else None),
                fetch="none",
            )

    def get_unparsed(self, eins: list[str] | None = None) -> list[dict]:
        """Get rows with raw_content but no parsed_json (need extraction)."""
        sql = "SELECT * FROM raw_scraped_data WHERE success = TRUE AND raw_content IS NOT NULL AND parsed_json IS NULL"
        params: tuple = ()

        if eins:
            placeholders = ", ".join(["%s"] * len(eins))
            sql += f" AND charity_ein IN ({placeholders})"
            params = tuple(eins)

        rows = execute_query(sql, params) or []
        return [self._deserialize_row(r) for r in rows]

    def get_all(self, eins: list[str] | None = None) -> list[dict]:
        """Get all rows with raw_content (for force re-extraction)."""
        sql = "SELECT * FROM raw_scraped_data WHERE success = TRUE AND raw_content IS NOT NULL"
        params: tuple = ()

        if eins:
            placeholders = ", ".join(["%s"] * len(eins))
            sql += f" AND charity_ein IN ({placeholders})"
            params = tuple(eins)

        rows = execute_query(sql, params) or []
        return [self._deserialize_row(r) for r in rows]

    def invalidate(self, ein: str, source: str, reason: str) -> bool:
        """Mark a source as stale so the next crawl re-fetches it.

        Sets success=FALSE and stores the reason. The orchestrator's
        _is_data_fresh() returns False for rows with success=FALSE,
        triggering a re-crawl on the next pipeline run.

        Args:
            ein: Charity EIN
            source: Source name (e.g. 'website', 'charity_navigator')
            reason: Why the data is being invalidated

        Returns:
            True if a row was invalidated, False if no row existed
        """
        existing = self.get_by_source(ein, source)
        if not existing:
            return False

        execute_query(
            "UPDATE raw_scraped_data SET success = FALSE, error_message = %s WHERE charity_ein = %s AND source = %s",
            (f"invalidated: {reason}", ein, source),
            fetch="none",
        )
        return True

    def get_for_charity(self, ein: str) -> list[dict]:
        """Get all raw data for a charity."""
        rows = (
            execute_query(
                "SELECT * FROM raw_scraped_data WHERE charity_ein = %s",
                (ein,),
            )
            or []
        )
        return [self._deserialize_row(r) for r in rows]

    def get_by_source(self, ein: str, source: str) -> dict | None:
        """Get raw data for specific source."""
        row = execute_query(
            "SELECT * FROM raw_scraped_data WHERE charity_ein = %s AND source = %s",
            (ein, source),
            fetch="one",
        )
        return self._deserialize_row(row) if row else None

    def get_successful_sources(self, ein: str) -> list[str]:
        """Get list of sources that succeeded for a charity."""
        rows = (
            execute_query(
                "SELECT source FROM raw_scraped_data WHERE charity_ein = %s AND success = TRUE",
                (ein,),
            )
            or []
        )
        return [r["source"] for r in rows]

    def _deserialize_row(self, row: dict) -> dict:
        """Deserialize JSON columns in a row."""
        if row and "parsed_json" in row:
            row["parsed_json"] = _deserialize_json(row["parsed_json"])
        return row


class CharityDataRepository:
    """Synthesized charity data operations."""

    # JSON columns that need serialization
    JSON_COLUMNS = {
        "source_attribution",
        "cause_tags",
        "policy_influence",
        "populations_served",
        "geographic_coverage",
        "website_evidence_signals",
        "program_focus_tags",
        "strategic_classification",
        "zakat_metadata",
        "strategic_evidence",
        "grants_made",
        "metrics_json",
        "evaluation_sources",
    }

    # All known columns
    KNOWN_COLUMNS = {
        "charity_ein",
        "synthesized_at",
        "has_islamic_identity",
        "serves_muslim_populations",
        "muslim_charity_fit",
        "total_revenue",
        "program_expenses",
        "admin_expenses",
        "fundraising_expenses",
        "program_expense_ratio",
        "charity_navigator_score",
        "transparency_score",
        "nonprofit_size_tier",
        # Financial health (balance sheet)
        "total_assets",
        "total_liabilities",
        "net_assets",
        "detected_cause_area",
        "claims_zakat_eligible",
        "beneficiaries_served_annually",
        "has_annual_report",
        "has_audited_financials",
        "candid_seal",
        "source_attribution",
        "cause_tags",
        "ntee_code",
        "cause_detection_source",
        "is_conflict_zone",
        "working_capital_months",
        "primary_category",
        "category_importance",
        "category_neglectedness",
        "evaluation_track",
        "founded_year",
        "policy_influence",
        # Governance fields
        "board_size",
        "independent_board_members",
        "ceo_compensation",
        # Form 990 status
        "form_990_exempt",
        "form_990_exempt_reason",
        # Targeting fields
        "populations_served",
        "geographic_coverage",
        # Website evidence signals
        "website_evidence_signals",
        # Program focus tags (for similarity matching)
        "program_focus_tags",
        # Strategic classification (for Strategic Believer lens)
        "strategic_classification",
        # Zakat metadata (asnaf, policy, verification, islamic signals)
        "zakat_metadata",
        # Strategic evidence (deterministic signals)
        "strategic_evidence",
        # Theory of change and grants
        "theory_of_change",
        "grants_made",
        # Full CharityMetrics blob (single source of truth for baseline)
        "metrics_json",
        # Scorer-critical fields (individual columns)
        "total_expenses",
        "cn_overall_score",
        "cn_financial_score",
        "cn_accountability_score",
        "employees_count",
        "volunteers_count",
        "has_theory_of_change",
        "reports_outcomes",
        "has_outcome_methodology",
        "has_multi_year_metrics",
        "third_party_evaluated",
        "evaluation_sources",
        "receives_foundation_grants",
        "candid_metrics_count",
        "candid_max_years_tracked",
        "no_filings",
        "zakat_claim_evidence",
    }

    # Columns managed by the DB itself — skip these on upsert so defaults apply.
    DB_MANAGED_COLUMNS = {
        "synthesized_at",  # Set via CURRENT_TIMESTAMP in ON DUPLICATE KEY UPDATE
    }

    def upsert(self, data: CharityData | dict) -> None:
        """Insert or update synthesized data.

        Writes all fields including None — this ensures stale values get
        cleared when upstream data changes. All callers (synthesize.py,
        streaming_runner.py) do full writes, so partial-update protection
        is unnecessary.
        """
        record = data.__dict__ if isinstance(data, CharityData) else data
        # Filter to known columns, skip DB-managed ones
        record = {k: v for k, v in record.items() if k in self.KNOWN_COLUMNS and k not in self.DB_MANAGED_COLUMNS}

        if not record.get("charity_ein"):
            raise ValueError("charity_ein is required for charity_data upsert")

        # Serialize JSON columns
        for col in self.JSON_COLUMNS:
            if col in record:
                record[col] = _serialize_json(record[col])

        columns = list(record.keys())
        placeholders = ", ".join(["%s"] * len(columns))
        update_clause = ", ".join([f"`{col}` = VALUES(`{col}`)" for col in columns if col != "charity_ein"])

        sql = f"""
            INSERT INTO charity_data ({", ".join(f"`{c}`" for c in columns)})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE {update_clause}, synthesized_at = CURRENT_TIMESTAMP
        """
        execute_query(sql, tuple(record.values()), fetch="none")

    def get(self, ein: str) -> dict | None:
        """Get synthesized data for charity."""
        row = execute_query(
            "SELECT * FROM charity_data WHERE charity_ein = %s",
            (ein,),
            fetch="one",
        )
        return self._deserialize_row(row) if row else None

    def _deserialize_row(self, row: dict) -> dict:
        """Deserialize JSON columns in a row."""
        if row:
            for col in self.JSON_COLUMNS:
                if col in row:
                    row[col] = _deserialize_json(row[col])
        return row


class EvaluationRepository:
    """Evaluation and narrative operations."""

    # JSON columns that need serialization (zakat_classification is a plain string, not JSON)
    JSON_COLUMNS = {
        "confidence_scores",
        "score_details",
        "impact_scores",
        "baseline_narrative",
        "rich_narrative",
        "score_profiles",
        "strategic_narrative",
        "rich_strategic_narrative",
        "zakat_narrative",
    }

    # All columns
    COLUMNS = {
        "charity_ein",
        "amal_score",
        "wallet_tag",
        "confidence_tier",
        "impact_tier",
        "zakat_classification",
        "confidence_scores",
        "score_details",
        "impact_scores",
        "baseline_narrative",
        "rich_narrative",
        # Multi-lens scoring
        "strategic_score",
        "zakat_score",
        "score_profiles",
        "strategic_narrative",
        "rich_strategic_narrative",
        "zakat_narrative",
        "judge_score",
        "information_density",
        "rubric_version",
        "state",
        "llm_cost_usd",  # Total LLM cost per charity across all phases
    }

    def upsert(self, evaluation: Evaluation | dict) -> None:
        """Insert or update evaluation."""
        data = evaluation.__dict__ if isinstance(evaluation, Evaluation) else evaluation
        # Filter to known columns only (prevents SQL injection via dict keys)
        data = {k: v for k, v in data.items() if k in self.COLUMNS and v is not None}

        # Baseline and rich are serial: whenever baseline_narrative is updated,
        # clear stale rich fields unless this write explicitly provides them.
        if "baseline_narrative" in data:
            data.setdefault("rich_narrative", None)
            data.setdefault("rich_strategic_narrative", None)

        if not data.get("charity_ein"):
            raise ValueError("charity_ein is required for evaluation upsert")

        # Serialize JSON columns
        for col in self.JSON_COLUMNS:
            if col in data:
                data[col] = _serialize_json(data[col])

        columns = list(data.keys())
        placeholders = ", ".join(["%s"] * len(columns))
        update_clause = ", ".join([f"`{col}` = VALUES(`{col}`)" for col in columns if col != "charity_ein"])

        sql = f"""
            INSERT INTO evaluations ({", ".join(f"`{c}`" for c in columns)})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE {update_clause}, updated_at = CURRENT_TIMESTAMP
        """
        execute_query(sql, tuple(data.values()), fetch="none")

    def get(self, ein: str) -> dict | None:
        """Get evaluation for charity."""
        row = execute_query(
            "SELECT * FROM evaluations WHERE charity_ein = %s",
            (ein,),
            fetch="one",
        )
        return self._deserialize_row(row) if row else None

    def get_by_state(self, state: str) -> list[dict]:
        """Get all evaluations in a given state."""
        rows = (
            execute_query(
                "SELECT * FROM evaluations WHERE state = %s",
                (state,),
            )
            or []
        )
        return [self._deserialize_row(r) for r in rows]

    def set_state(self, ein: str, state: str) -> None:
        """Update evaluation state."""
        execute_query(
            "UPDATE evaluations SET state = %s, updated_at = CURRENT_TIMESTAMP WHERE charity_ein = %s",
            (state, ein),
            fetch="none",
        )

    def set_narrative(
        self, ein: str, narrative: dict, judge_score: int | None = None, density: float | None = None
    ) -> None:
        """Set baseline narrative and quality metrics."""
        parts = ["baseline_narrative = %s"]
        values: list[Any] = [_serialize_json(narrative)]

        if judge_score is not None:
            parts.append("judge_score = %s")
            values.append(judge_score)
        if density is not None:
            parts.append("information_density = %s")
            values.append(density)

        parts.append("updated_at = CURRENT_TIMESTAMP")
        values.append(ein)

        execute_query(
            f"UPDATE evaluations SET {', '.join(parts)} WHERE charity_ein = %s",
            tuple(values),
            fetch="none",
        )

    def get_stats(self) -> dict[str, int]:
        """Get count of evaluations by state."""
        rows = execute_query("SELECT state, COUNT(*) as count FROM evaluations GROUP BY state") or []
        return {row["state"]: row["count"] for row in rows}

    def get_approved(self) -> list[dict]:
        """Get all approved evaluations."""
        return self.get_by_state("approved")

    def update_judge_result(self, ein: str, judge_score: int, judge_issues: list[dict] | None = None) -> None:
        """Update judge validation results for an evaluation.

        Args:
            ein: Charity EIN
            judge_score: Judge score (0-100, higher = fewer issues)
            judge_issues: List of validation issues found by judges
        """
        parts = ["judge_score = %s", "updated_at = CURRENT_TIMESTAMP"]
        values: list = [judge_score]

        # Store judge_issues in score_details.judge_issues (extend existing JSON)
        if judge_issues is not None:
            # Get existing score_details and merge
            existing = self.get(ein)
            if existing and existing.get("score_details"):
                score_details = existing["score_details"]
            else:
                score_details = {}
            score_details["judge_issues"] = judge_issues
            parts.append("score_details = %s")
            values.append(_serialize_json(score_details))

        values.append(ein)
        execute_query(
            f"UPDATE evaluations SET {', '.join(parts)} WHERE charity_ein = %s",
            tuple(values),
            fetch="none",
        )

    def update_llm_cost(self, ein: str, cost_usd: float) -> None:
        """Update total LLM cost for a charity.

        Args:
            ein: Charity EIN
            cost_usd: Total LLM cost in USD across all pipeline phases
        """
        execute_query(
            "UPDATE evaluations SET llm_cost_usd = %s, updated_at = CURRENT_TIMESTAMP WHERE charity_ein = %s",
            (cost_usd, ein),
            fetch="none",
        )

    def clear_rich_narrative(self, ein: str) -> None:
        """Clear rich narrative fields.

        Used when rich generation fails validation so stale rich content
        cannot be treated as current.
        """
        execute_query(
            """
            UPDATE evaluations
            SET rich_narrative = NULL,
                rich_strategic_narrative = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE charity_ein = %s
            """,
            (ein,),
            fetch="none",
        )

    def _deserialize_row(self, row: dict) -> dict:
        """Deserialize JSON columns in a row."""
        if row:
            for col in self.JSON_COLUMNS:
                if col in row:
                    row[col] = _deserialize_json(row[col])
        return row


@dataclass
class AgentDiscovery:
    """Agent discovery record."""

    charity_ein: str
    agent_type: str
    source_name: str
    discovery_method: str
    source_url: str | None = None
    search_query: str | None = None
    raw_html: str | None = None
    parsed_data: dict | None = None
    grounding_metadata: dict | None = None
    confidence: float = 1.0
    relevance_score: float | None = None


class AgentDiscoveryRepository:
    """Agent discovery operations."""

    # JSON columns
    JSON_COLUMNS = {"parsed_data", "grounding_metadata"}

    def upsert(self, discovery: AgentDiscovery | dict) -> None:
        """Insert or update an agent discovery."""
        data = discovery.__dict__ if isinstance(discovery, AgentDiscovery) else discovery
        data = {k: v for k, v in data.items() if v is not None}

        # Serialize JSON columns
        for col in self.JSON_COLUMNS:
            if col in data:
                data[col] = _serialize_json(data[col])

        # Check if exists by unique key
        existing = execute_query(
            "SELECT id FROM agent_discoveries WHERE charity_ein = %s AND agent_type = %s AND source_url = %s",
            (data.get("charity_ein"), data.get("agent_type"), data.get("source_url")),
            fetch="one",
        )

        if existing:
            # Update
            set_parts = [f"{k} = %s" for k in data.keys() if k not in ("charity_ein", "agent_type", "source_url")]
            values = [v for k, v in data.items() if k not in ("charity_ein", "agent_type", "source_url")]
            values.extend([data["charity_ein"], data["agent_type"], data.get("source_url")])

            if set_parts:
                execute_query(
                    f"UPDATE agent_discoveries SET {', '.join(set_parts)} WHERE charity_ein = %s AND agent_type = %s AND source_url = %s",
                    tuple(values),
                    fetch="none",
                )
        else:
            # Insert
            data["id"] = _generate_uuid()
            columns = list(data.keys())
            placeholders = ", ".join(["%s"] * len(columns))

            execute_query(
                f"INSERT INTO agent_discoveries ({', '.join(columns)}) VALUES ({placeholders})",
                tuple(data.values()),
                fetch="none",
            )

    def upsert_batch(self, discoveries: list[AgentDiscovery | dict]) -> None:
        """Insert or update multiple discoveries."""
        for d in discoveries:
            self.upsert(d)

    def get_for_charity(self, ein: str, agent_type: str | None = None) -> list[dict]:
        """Get discoveries for a charity, optionally filtered by agent type."""
        if agent_type:
            rows = (
                execute_query(
                    "SELECT * FROM agent_discoveries WHERE charity_ein = %s AND agent_type = %s ORDER BY discovered_at DESC",
                    (ein, agent_type),
                )
                or []
            )
        else:
            rows = (
                execute_query(
                    "SELECT * FROM agent_discoveries WHERE charity_ein = %s ORDER BY discovered_at DESC",
                    (ein,),
                )
                or []
            )

        return [self._deserialize_row(r) for r in rows]

    def get_by_agent_type(self, agent_type: str) -> list[dict]:
        """Get all discoveries for an agent type."""
        rows = (
            execute_query(
                "SELECT * FROM agent_discoveries WHERE agent_type = %s",
                (agent_type,),
            )
            or []
        )
        return [self._deserialize_row(r) for r in rows]

    def get_search_discoveries(self, ein: str) -> list[dict]:
        """Get discoveries made via search (not known sources)."""
        rows = (
            execute_query(
                "SELECT * FROM agent_discoveries WHERE charity_ein = %s AND discovery_method = 'search'",
                (ein,),
            )
            or []
        )
        return [self._deserialize_row(r) for r in rows]

    def get_stats(self) -> dict[str, int]:
        """Get discovery counts by agent type."""
        rows = execute_query("SELECT agent_type, COUNT(*) as count FROM agent_discoveries GROUP BY agent_type") or []
        return {row["agent_type"]: row["count"] for row in rows}

    def _deserialize_row(self, row: dict) -> dict:
        """Deserialize JSON columns in a row."""
        if row:
            for col in self.JSON_COLUMNS:
                if col in row:
                    row[col] = _deserialize_json(row[col])
        return row


@dataclass
class Citation:
    """Citation record for narratives."""

    id: str
    charity_ein: str
    narrative_type: str
    claim: str
    source_name: str
    source_type: str
    source_url: str | None = None
    quote: str | None = None
    confidence: float = 1.0


class CitationRepository:
    """Citation operations."""

    def upsert(self, citation: Citation | dict) -> None:
        """Insert or update a citation."""
        data = citation.__dict__ if isinstance(citation, Citation) else citation
        data = {k: v for k, v in data.items() if v is not None}

        # Ensure id exists
        if "id" not in data:
            data["id"] = _generate_uuid()

        columns = list(data.keys())
        placeholders = ", ".join(["%s"] * len(columns))
        update_clause = ", ".join([f"{col} = VALUES({col})" for col in columns if col != "id"])

        sql = f"""
            INSERT INTO citations ({", ".join(columns)})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE {update_clause}
        """
        execute_query(sql, tuple(data.values()), fetch="none")

    def upsert_batch(self, citations: list[Citation | dict]) -> None:
        """Insert or update multiple citations."""
        for c in citations:
            self.upsert(c)

    def get_for_charity(self, ein: str, narrative_type: str | None = None) -> list[dict]:
        """Get citations for a charity."""
        if narrative_type:
            return (
                execute_query(
                    "SELECT * FROM citations WHERE charity_ein = %s AND narrative_type = %s",
                    (ein, narrative_type),
                )
                or []
            )
        return (
            execute_query(
                "SELECT * FROM citations WHERE charity_ein = %s",
                (ein,),
            )
            or []
        )

    def get_for_narrative(self, ein: str, narrative_type: str) -> list[dict]:
        """Get all citations for a specific narrative."""
        return (
            execute_query(
                "SELECT * FROM citations WHERE charity_ein = %s AND narrative_type = %s ORDER BY id",
                (ein, narrative_type),
            )
            or []
        )


@dataclass
class JudgeVerdict:
    """Judge verdict record for tracking validation history."""

    charity_ein: str
    commit_hash: str
    judge_name: str
    passed: bool
    error_count: int = 0
    warning_count: int = 0
    issues: list[dict] | None = None
    cost_usd: float = 0.0


class JudgeVerdictRepository:
    """Judge verdict operations - tracks validation results across commits.

    This repository enables:
    - Persisting judge verdicts per charity per commit
    - Querying verdict history for trend analysis
    - Detecting regressions (passed -> failed transitions)
    """

    # JSON columns
    JSON_COLUMNS = {"issues"}

    def save_verdict(
        self, verdict: JudgeVerdict | dict, charity_ein: str | None = None, commit_hash: str | None = None
    ) -> None:
        """Save a judge verdict.

        Args:
            verdict: JudgeVerdict dataclass or dict with verdict data
            charity_ein: Override charity EIN (for dict input)
            commit_hash: Override commit hash (for dict input)
        """
        data = verdict.__dict__ if isinstance(verdict, JudgeVerdict) else dict(verdict)

        # Allow overrides for flexibility
        if charity_ein:
            data["charity_ein"] = charity_ein
        if commit_hash:
            data["commit_hash"] = commit_hash

        if not data.get("charity_ein") or not data.get("commit_hash") or not data.get("judge_name"):
            raise ValueError("charity_ein, commit_hash, and judge_name are required")

        # Serialize JSON columns
        for col in self.JSON_COLUMNS:
            if col in data and data[col] is not None:
                data[col] = _serialize_json(data[col])

        # Generate ID if not provided
        if "id" not in data:
            data["id"] = _generate_uuid()

        columns = list(data.keys())
        placeholders = ", ".join(["%s"] * len(columns))
        update_clause = ", ".join(
            [
                f"{col} = VALUES({col})"
                for col in columns
                if col not in ("id", "charity_ein", "commit_hash", "judge_name")
            ]
        )

        sql = f"""
            INSERT INTO judge_verdicts ({", ".join(columns)})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE {update_clause}, validated_at = CURRENT_TIMESTAMP
        """
        execute_query(sql, tuple(data.values()), fetch="none")

    def save_verdicts_batch(self, verdicts: list[JudgeVerdict | dict], commit_hash: str) -> None:
        """Save multiple verdicts for the same commit.

        Args:
            verdicts: List of verdict data
            commit_hash: The commit hash for all verdicts
        """
        for v in verdicts:
            self.save_verdict(v, commit_hash=commit_hash)

    def get_verdict(self, ein: str, commit_hash: str, judge_name: str) -> dict | None:
        """Get a specific verdict.

        Args:
            ein: Charity EIN
            commit_hash: Commit hash
            judge_name: Name of the judge

        Returns:
            Verdict dict or None
        """
        row = execute_query(
            "SELECT * FROM judge_verdicts WHERE charity_ein = %s AND commit_hash = %s AND judge_name = %s",
            (ein, commit_hash, judge_name),
            fetch="one",
        )
        return self._deserialize_row(row) if row else None

    def get_verdict_history(self, ein: str, judge_name: str | None = None, limit: int = 10) -> list[dict]:
        """Get verdict history for a charity.

        Args:
            ein: Charity EIN
            judge_name: Optional filter by judge name
            limit: Max results to return

        Returns:
            List of verdicts ordered by validated_at DESC
        """
        if judge_name:
            rows = (
                execute_query(
                    """SELECT * FROM judge_verdicts
                   WHERE charity_ein = %s AND judge_name = %s
                   ORDER BY validated_at DESC LIMIT %s""",
                    (ein, judge_name, limit),
                )
                or []
            )
        else:
            rows = (
                execute_query(
                    """SELECT * FROM judge_verdicts
                   WHERE charity_ein = %s
                   ORDER BY validated_at DESC LIMIT %s""",
                    (ein, limit),
                )
                or []
            )

        return [self._deserialize_row(r) for r in rows]

    def get_regressions(self, since_commit: str, to_commit: str = "HEAD") -> list[dict]:
        """Find charities that regressed (passed -> failed) between commits.

        Args:
            since_commit: The older commit to compare from
            to_commit: The newer commit to compare to (default: HEAD)

        Returns:
            List of regression records with charity_ein, judge_name, and details
        """
        # Resolve HEAD to actual commit hash if needed
        if to_commit == "HEAD":
            head_row = execute_query(
                "SELECT commit_hash FROM dolt_log LIMIT 1",
                fetch="one",
            )
            if head_row:
                to_commit = head_row["commit_hash"]
            else:
                return []

        query = """
        SELECT
            v_old.charity_ein,
            v_old.judge_name,
            v_old.passed as was_passing,
            v_new.passed as now_passing,
            v_old.error_count as old_errors,
            v_new.error_count as new_errors,
            v_new.issues as new_issues
        FROM judge_verdicts v_old
        JOIN judge_verdicts v_new
            ON v_old.charity_ein = v_new.charity_ein
            AND v_old.judge_name = v_new.judge_name
        WHERE v_old.commit_hash = %s
          AND v_new.commit_hash = %s
          AND v_old.passed = TRUE
          AND v_new.passed = FALSE
        """

        rows = execute_query(query, (since_commit, to_commit)) or []

        results = []
        for row in rows:
            result = dict(row)
            # Deserialize issues JSON
            if result.get("new_issues"):
                result["new_issues"] = _deserialize_json(result["new_issues"])
            results.append(result)

        return results

    def get_latest_commit_for_charity(self, ein: str) -> str | None:
        """Get the most recent commit hash with verdicts for a charity.

        Useful for determining the baseline for regression detection.
        """
        row = execute_query(
            """SELECT commit_hash FROM judge_verdicts
               WHERE charity_ein = %s
               ORDER BY validated_at DESC LIMIT 1""",
            (ein,),
            fetch="one",
        )
        return row["commit_hash"] if row else None

    def purge_stale_verdicts(self) -> int:
        """Delete old verdicts, keeping only the latest per (charity_ein, judge_name).

        Returns:
            Number of stale rows deleted.
        """
        before = execute_query("SELECT COUNT(*) as cnt FROM judge_verdicts", fetch="one")
        before_count = before["cnt"] if before else 0

        execute_query(
            """DELETE v FROM judge_verdicts v
               INNER JOIN (
                   SELECT charity_ein, judge_name, MAX(validated_at) as max_at
                   FROM judge_verdicts
                   GROUP BY charity_ein, judge_name
               ) latest
               ON v.charity_ein = latest.charity_ein
                  AND v.judge_name = latest.judge_name
               WHERE v.validated_at < latest.max_at""",
            fetch="none",
        )

        after = execute_query("SELECT COUNT(*) as cnt FROM judge_verdicts", fetch="one")
        after_count = after["cnt"] if after else 0
        return before_count - after_count

    def get_stats(self, commit_hash: str | None = None) -> dict[str, Any]:
        """Get aggregate statistics for verdicts.

        When no commit_hash is provided, only the latest verdict per
        (charity_ein, judge_name) is counted.

        Args:
            commit_hash: Optional filter to specific commit

        Returns:
            Dict with counts by judge, pass/fail rates, etc.
        """
        if commit_hash:
            rows = (
                execute_query(
                    """SELECT judge_name, passed, COUNT(*) as count
                   FROM judge_verdicts WHERE commit_hash = %s
                   GROUP BY judge_name, passed""",
                    (commit_hash,),
                )
                or []
            )
        else:
            rows = (
                execute_query(
                    """SELECT v.judge_name, v.passed, COUNT(*) as count
                   FROM judge_verdicts v
                   INNER JOIN (
                       SELECT charity_ein, judge_name, MAX(validated_at) as max_at
                       FROM judge_verdicts
                       GROUP BY charity_ein, judge_name
                   ) latest
                   ON v.charity_ein = latest.charity_ein
                      AND v.judge_name = latest.judge_name
                      AND v.validated_at = latest.max_at
                   GROUP BY v.judge_name, v.passed""",
                )
                or []
            )

        stats: dict[str, Any] = {"by_judge": {}}
        for row in rows:
            judge = row["judge_name"]
            if judge not in stats["by_judge"]:
                stats["by_judge"][judge] = {"passed": 0, "failed": 0}

            if row["passed"]:
                stats["by_judge"][judge]["passed"] = row["count"]
            else:
                stats["by_judge"][judge]["failed"] = row["count"]

        return stats

    def get_latest_failing(self, judge_name: str | None = None) -> list[dict]:
        """Get latest failing verdicts (one per charity/judge), with issues.

        Args:
            judge_name: Optional filter to a specific judge

        Returns:
            List of verdict dicts for the latest failing verdicts.
        """
        base = """
            SELECT v.* FROM judge_verdicts v
            INNER JOIN (
                SELECT charity_ein, judge_name, MAX(validated_at) as max_at
                FROM judge_verdicts
                GROUP BY charity_ein, judge_name
            ) latest
            ON v.charity_ein = latest.charity_ein
               AND v.judge_name = latest.judge_name
               AND v.validated_at = latest.max_at
            WHERE v.passed = FALSE
        """
        if judge_name:
            base += " AND v.judge_name = %s"
            rows = execute_query(base, (judge_name,)) or []
        else:
            rows = execute_query(base) or []

        return [self._deserialize_row(r) for r in rows]

    def _deserialize_row(self, row: dict) -> dict:
        """Deserialize JSON columns in a row."""
        if row:
            for col in self.JSON_COLUMNS:
                if col in row:
                    row[col] = _deserialize_json(row[col])
        return row


@dataclass
class PhaseCache:
    """Phase cache record for smart caching."""

    charity_ein: str
    phase: str
    code_fingerprint: str
    ran_at: datetime | None = None
    cost_usd: float = 0.0


class PhaseCacheRepository:
    """Phase cache operations for smart caching.

    Tracks code fingerprints and run timestamps per charity/phase
    to determine if phases can be skipped.
    """

    def get(self, ein: str, phase: str) -> dict | None:
        """Get cache entry for a charity/phase.

        Args:
            ein: Charity EIN
            phase: Phase name

        Returns:
            Cache entry dict or None if not found
        """
        return execute_query(
            "SELECT * FROM phase_cache WHERE charity_ein = %s AND phase = %s",
            (ein, phase),
            fetch="one",
        )

    def upsert(
        self,
        ein: str,
        phase: str,
        code_fingerprint: str,
        cost_usd: float = 0.0,
    ) -> None:
        """Insert or update cache entry after running a phase.

        Args:
            ein: Charity EIN
            phase: Phase name
            code_fingerprint: SHA256 hash of code files
            cost_usd: LLM cost for this phase run
        """
        execute_query(
            """
            INSERT INTO phase_cache (charity_ein, phase, code_fingerprint, ran_at, cost_usd)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s)
            ON DUPLICATE KEY UPDATE
                code_fingerprint = VALUES(code_fingerprint),
                ran_at = CURRENT_TIMESTAMP,
                cost_usd = VALUES(cost_usd)
            """,
            (ein, phase, code_fingerprint, cost_usd),
            fetch="none",
        )

    def delete(self, ein: str, phase: str) -> None:
        """Delete cache entry for a charity/phase (for invalidation).

        Args:
            ein: Charity EIN
            phase: Phase name
        """
        execute_query(
            "DELETE FROM phase_cache WHERE charity_ein = %s AND phase = %s",
            (ein, phase),
            fetch="none",
        )

    def delete_for_charity(self, ein: str) -> int:
        """Delete all cache entries for a charity.

        Args:
            ein: Charity EIN

        Returns:
            Number of entries deleted
        """
        result = execute_query(
            "SELECT COUNT(*) as cnt FROM phase_cache WHERE charity_ein = %s",
            (ein,),
            fetch="one",
        )
        count = result["cnt"] if result else 0

        if count > 0:
            execute_query(
                "DELETE FROM phase_cache WHERE charity_ein = %s",
                (ein,),
                fetch="none",
            )

        return count

    def delete_downstream(self, ein: str, phase: str) -> list[str]:
        """Delete cache entries for all downstream phases (cascade invalidation).

        Args:
            ein: Charity EIN
            phase: The phase that ran (triggers invalidation of dependents)

        Returns:
            List of phases that were invalidated
        """
        from src.utils.phase_fingerprint import get_downstream_phases

        downstream = get_downstream_phases(phase)
        for p in downstream:
            self.delete(ein, p)
        return downstream

    def is_valid(
        self,
        ein: str,
        phase: str,
        current_fingerprint: str,
        ttl_days: float = float("inf"),
    ) -> tuple[bool, str]:
        """Check if cached data is still valid.

        Args:
            ein: Charity EIN
            phase: Phase name
            current_fingerprint: Current code fingerprint
            ttl_days: Max age in days (inf = no time limit)

        Returns:
            Tuple of (is_valid, reason)
        """
        cache_entry = self.get(ein, phase)

        if not cache_entry:
            return False, "No cache entry"

        # Check code change
        if cache_entry["code_fingerprint"] != current_fingerprint:
            old_fp = cache_entry["code_fingerprint"][:8]
            new_fp = current_fingerprint[:8]
            return False, f"Code changed ({old_fp}→{new_fp})"

        # Check TTL
        if ttl_days != float("inf"):
            ran_at = cache_entry["ran_at"]
            if ran_at:
                age_days = (datetime.now() - ran_at).days
                if age_days > ttl_days:
                    return False, f"TTL expired ({age_days}d > {ttl_days}d)"

        return True, "Cache valid"

    def get_all_for_charity(self, ein: str) -> list[dict]:
        """Get all cache entries for a charity.

        Args:
            ein: Charity EIN

        Returns:
            List of cache entries
        """
        return (
            execute_query(
                "SELECT * FROM phase_cache WHERE charity_ein = %s ORDER BY phase",
                (ein,),
            )
            or []
        )

    def get_stats(self) -> dict[str, int]:
        """Get aggregate stats for cache entries.

        Returns:
            Dict with counts by phase
        """
        rows = execute_query("SELECT phase, COUNT(*) as count FROM phase_cache GROUP BY phase") or []
        return {row["phase"]: row["count"] for row in rows}
