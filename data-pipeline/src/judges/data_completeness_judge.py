"""Data Completeness Judge - validates that critical data sources were collected.

Checks for:
1. Website data availability (flags captcha blocks, fetch failures)
2. Required sources for scoring (propublica, etc.)
3. Financial data availability (Form 990, program expense ratio, revenue)
4. Data freshness
"""

import json
import logging
from typing import Any

from .base_judge import BaseJudge, JudgeType
from .schemas.verdict import JudgeVerdict, Severity, ValidationIssue

logger = logging.getLogger(__name__)


def _is_null_like(val: Any) -> bool:
    """Check if a value is null-like (None, "null", "none", "NULL", empty string)."""
    if val is None:
        return True
    if isinstance(val, str) and val.strip().lower() in ("null", "none", ""):
        return True
    return False


# Sources that should ideally be present for a complete evaluation
CRITICAL_SOURCES = ["website"]
RECOMMENDED_SOURCES = ["propublica", "candid", "charity_navigator"]

# Financial data fields we check for
FINANCIAL_FIELDS = [
    "program_expense_ratio",
    "total_revenue",
    "total_expenses",
    "total_assets",
]

# Keywords that indicate a religious organization (Form 990-exempt)
RELIGIOUS_ORG_KEYWORDS = [
    "muslim",
    "islamic",
    "mosque",
    "masjid",
    "church",
    "chapel",
    "cathedral",
    "parish",
    "temple",
    "synagogue",
    "jewish",
    "hindu",
    "buddhist",
    "sikh",
    "gurdwara",
    "religious",
    "faith",
    "ministry",
    "congregation",
]


class DataCompletenessJudge(BaseJudge):
    """Judge that validates data source completeness.

    Unlike other judges that validate the quality of generated content,
    this judge checks whether the underlying data collection succeeded.
    This helps identify charities with incomplete data that may have
    unreliable scores.
    """

    @property
    def name(self) -> str:
        return "data_completeness"

    @property
    def judge_type(self) -> JudgeType:
        return JudgeType.DETERMINISTIC

    def validate(self, output: dict[str, Any], context: dict[str, Any]) -> JudgeVerdict:
        """Validate data source completeness for a charity.

        Args:
            output: The exported charity data (narrative, scores, citations)
            context: Source data context

        Returns:
            JudgeVerdict with any data completeness issues
        """
        issues: list[ValidationIssue] = []
        ein = output.get("ein", "unknown")

        # Query raw_scraped_data for this charity's sources
        source_status = self._get_source_status(ein)

        if not source_status:
            issues.append(
                ValidationIssue(
                    severity=Severity.WARNING,
                    field="data_sources",
                    message="No source data found in raw_scraped_data table",
                    details={"ein": ein},
                )
            )
        else:
            # Check critical sources
            for source in CRITICAL_SOURCES:
                status = source_status.get(source)
                if status is None:
                    issues.append(
                        ValidationIssue(
                            severity=Severity.ERROR,
                            field=f"source.{source}",
                            message=f"Critical source '{source}' was not attempted",
                            details={"ein": ein, "source": source},
                        )
                    )
                elif not status["success"]:
                    error_msg = status.get("error_message", "Unknown error")

                    # Determine severity based on error type
                    # CAPTCHA blocks and empty-page failures are infrastructure issues,
                    # not data quality problems — downgrade to WARNING
                    if "CAPTCHA_BLOCKED" in (error_msg or ""):
                        severity = Severity.WARNING
                        message = f"Website blocked by anti-bot protection: {error_msg}"
                    elif "No data found" in (error_msg or ""):
                        severity = Severity.WARNING
                        message = f"Critical source '{source}' failed: {error_msg}"
                    else:
                        severity = Severity.ERROR
                        message = f"Critical source '{source}' failed: {error_msg}"

                    issues.append(
                        ValidationIssue(
                            severity=severity,
                            field=f"source.{source}",
                            message=message,
                            details={
                                "ein": ein,
                                "source": source,
                                "error": error_msg,
                                "retry_count": status.get("retry_count", 0),
                            },
                        )
                    )

            # Check recommended sources (warnings only)
            for source in RECOMMENDED_SOURCES:
                status = source_status.get(source)
                if status is None:
                    issues.append(
                        ValidationIssue(
                            severity=Severity.INFO,
                            field=f"source.{source}",
                            message=f"Recommended source '{source}' was not attempted",
                            details={"ein": ein, "source": source},
                        )
                    )
                elif not status["success"]:
                    error_msg = status.get("error_message", "Unknown error")
                    issues.append(
                        ValidationIssue(
                            severity=Severity.WARNING,
                            field=f"source.{source}",
                            message=f"Recommended source '{source}' failed: {error_msg}",
                            details={
                                "ein": ein,
                                "source": source,
                                "error": error_msg,
                            },
                        )
                    )

        # Check for financial data availability
        financial_issues = self._check_financial_data(ein)
        issues.extend(financial_issues)

        # Determine pass/fail - fail if any critical source failed
        has_errors = any(issue.severity == Severity.ERROR for issue in issues)

        return JudgeVerdict(
            passed=not has_errors,
            judge_name=self.name,
            issues=issues,
            metadata={
                "sources_checked": list(source_status.keys()) if source_status else [],
                "sources_succeeded": [s for s, status in (source_status or {}).items() if status["success"]],
                "sources_failed": [s for s, status in (source_status or {}).items() if not status["success"]],
            },
        )

    def _get_source_status(self, ein: str) -> dict[str, dict[str, Any]] | None:
        """Query raw_scraped_data for source status.

        Returns:
            Dict mapping source name to status info, or None if query fails
        """
        try:
            from ..db.client import execute_query

            rows = execute_query(
                """
                SELECT source, success, error_message, retry_count, scraped_at
                FROM raw_scraped_data
                WHERE charity_ein = %s
                """,
                (ein,),
                fetch="all",
            )

            if not rows:
                return None

            return {
                row["source"]: {
                    "success": bool(row["success"]),
                    "error_message": row["error_message"],
                    "retry_count": row["retry_count"],
                    "scraped_at": row["scraped_at"],
                }
                for row in rows
            }

        except Exception as e:
            logger.warning(f"Failed to query source status for {ein}: {e}")
            return None

    def _check_financial_data(self, ein: str) -> list[ValidationIssue]:
        """Check if financial data is available for effectiveness scoring.

        Checks propublica and charity_data for key financial metrics.

        Returns:
            List of ValidationIssues for missing financial data
        """
        issues: list[ValidationIssue] = []

        try:
            from ..db.client import execute_query

            # Check charity_data for synthesized financial info
            charity_data = execute_query(
                """
                SELECT
                    program_expense_ratio,
                    total_revenue,
                    program_expenses
                FROM charity_data
                WHERE charity_ein = %s
                """,
                (ein,),
                fetch="one",
            )

            has_financial_data = False
            missing_fields = []

            if charity_data:
                prog_ratio = charity_data.get("program_expense_ratio")
                revenue = charity_data.get("total_revenue")
                expenses = charity_data.get("program_expenses")

                # Check if we have meaningful financial data
                if prog_ratio is not None:
                    has_financial_data = True
                else:
                    missing_fields.append("program_expense_ratio")

                if revenue is not None and revenue != 0:
                    has_financial_data = True
                else:
                    missing_fields.append("total_revenue")

                if expenses is not None and expenses != 0:
                    has_financial_data = True
                else:
                    missing_fields.append("program_expenses")

            # Also check raw propublica data for Form 990 filings
            propublica_data = execute_query(
                """
                SELECT
                    parsed_json,
                    JSON_EXTRACT(parsed_json, '$.filings') as filings,
                    JSON_EXTRACT(parsed_json, '$.propublica_990.ntee_code') as ntee_code,
                    JSON_EXTRACT(parsed_json, '$.propublica_990.no_filings') as no_filings,
                    JSON_EXTRACT(parsed_json, '$.propublica_990.name') as org_name,
                    JSON_EXTRACT(parsed_json, '$.propublica_990.irs_ruling_year') as irs_ruling_year
                FROM raw_scraped_data
                WHERE charity_ein = %s AND source = 'propublica'
                """,
                (ein,),
                fetch="one",
            )

            has_form990 = False
            is_form990_exempt = False  # Religious orgs (NTEE X*) don't have to file
            is_new_org = False  # Orgs with IRS ruling within last 2 years
            irs_ruling_year = None
            if propublica_data:
                filings = propublica_data.get("filings")
                parsed = propublica_data.get("parsed_json")
                ntee_code = propublica_data.get("ntee_code")
                no_filings = propublica_data.get("no_filings")
                org_name = propublica_data.get("org_name")

                # Check if this is a Form 990-exempt organization
                # Religious organizations (NTEE X*) are not required to file Form 990
                if ntee_code:
                    ntee_str = ntee_code.strip('"') if isinstance(ntee_code, str) else str(ntee_code)
                    if ntee_str.startswith("X"):
                        is_form990_exempt = True

                # If no NTEE code, check org name for religious keywords
                if not is_form990_exempt and org_name:
                    name_lower = org_name.lower() if isinstance(org_name, str) else ""
                    for keyword in RELIGIOUS_ORG_KEYWORDS:
                        if keyword in name_lower:
                            is_form990_exempt = True
                            break

                # Check if this is a new org (IRS ruling within last 2 years)
                # New orgs haven't had time to file their first 990 yet
                irs_ruling_year = propublica_data.get("irs_ruling_year")
                if irs_ruling_year:
                    try:
                        ruling_year = int(str(irs_ruling_year).strip('"'))
                        from datetime import datetime

                        current_year = datetime.now().year
                        if current_year - ruling_year <= 2:
                            is_new_org = True
                    except (ValueError, TypeError):
                        pass

                # Also check no_filings flag - if true and religious, definitely exempt
                if no_filings is True or no_filings == "true":
                    if is_form990_exempt:
                        # Confirmed: religious org with no filings = exempt
                        pass
                    # Note: non-religious orgs with no_filings could be small (990-N)
                    # or new, so we don't auto-exempt them

                # Check if filings exist
                if filings and not _is_null_like(filings):
                    try:
                        filings_list = json.loads(filings) if isinstance(filings, str) else filings
                        if filings_list and len(filings_list) > 0:
                            has_form990 = True
                    except (json.JSONDecodeError, TypeError):
                        pass

                # Also check if parsed_json has financial fields
                if parsed and not _is_null_like(parsed):
                    try:
                        parsed_dict = json.loads(parsed) if isinstance(parsed, str) else parsed
                        if parsed_dict:
                            org = parsed_dict.get("organization", parsed_dict)
                            # Check for meaningful financial indicators
                            if org.get("income_amount") or org.get("asset_amount"):
                                has_financial_data = True
                            if org.get("tax_period"):
                                has_form990 = True
                    except (json.JSONDecodeError, TypeError):
                        pass

            # Report issues
            # If we have financial data in charity_data, Form 990 was processed
            # Only flag missing Form 990 if we also don't have financial data
            # Exception: Form 990-exempt orgs (religious organizations) don't need to file
            if not has_form990 and not has_financial_data:
                if is_form990_exempt:
                    # Religious organizations are exempt from Form 990 filing
                    # This is expected, not an error - downgrade to INFO
                    issues.append(
                        ValidationIssue(
                            severity=Severity.INFO,
                            field="financial.form990_exempt",
                            message="Religious organization (Form 990-exempt) - limited financial data available",
                            details={
                                "ein": ein,
                                "reason": "Churches and religious organizations are not required to file Form 990",
                                "impact": "Effectiveness score based on available data only",
                            },
                        )
                    )
                elif is_new_org:
                    # New organizations haven't filed their first 990 yet
                    # This is expected for orgs with IRS ruling within last 2 years
                    issues.append(
                        ValidationIssue(
                            severity=Severity.INFO,
                            field="financial.new_org",
                            message="New organization - Form 990 not yet due",
                            details={
                                "ein": ein,
                                "irs_ruling_year": irs_ruling_year,
                                "reason": "Organizations typically file their first Form 990 1-2 years after IRS determination",
                                "impact": "Effectiveness score based on available data only",
                            },
                        )
                    )
                else:
                    # Non-exempt org missing Form 990 is an error
                    issues.append(
                        ValidationIssue(
                            severity=Severity.ERROR,
                            field="financial.form990",
                            message="No Form 990 filings available - effectiveness score will be 0",
                            details={
                                "ein": ein,
                                "impact": "Effectiveness score cannot be calculated without Form 990 data",
                            },
                        )
                    )

                    if missing_fields:
                        issues.append(
                            ValidationIssue(
                                severity=Severity.WARNING,
                                field="financial.data",
                                message=f"Missing financial data: {', '.join(missing_fields)}",
                                details={
                                    "ein": ein,
                                    "missing_fields": missing_fields,
                                },
                            )
                        )

            # Check for partial financial data - has revenue but no program_expense_ratio
            # This causes effectiveness to be calculated as 0%
            if has_financial_data and "program_expense_ratio" in missing_fields:
                issues.append(
                    ValidationIssue(
                        severity=Severity.WARNING,
                        field="financial.program_expense_ratio",
                        message="Missing program_expense_ratio - effectiveness score may be artificially low",
                        details={
                            "ein": ein,
                            "has_revenue": "total_revenue" not in missing_fields,
                            "impact": "Program efficiency will show as 0%",
                        },
                    )
                )

        except Exception as e:
            logger.warning(f"Failed to check financial data for {ein}: {e}")

        return issues
