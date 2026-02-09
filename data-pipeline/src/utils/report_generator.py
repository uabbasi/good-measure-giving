"""
Pipeline report generator for admin monitoring.

Generates comprehensive reports including:
- Success/failure rates per charity and per source
- Data freshness summary
- Tier distributions (Impact/Confidence/Zakat)
- Missing data issues
- LLM token usage and costs
- Execution time tracking
"""

import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional


class PipelineReport:
    """
    Generate admin reports for pipeline runs.
    """

    def __init__(self, run_id: str, methodology_version: str = "1.0"):
        """
        Initialize report generator.

        Args:
            run_id: Unique identifier for this pipeline run
            methodology_version: Version of methodology used
        """
        self.run_id = run_id
        self.methodology_version = methodology_version
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None

        # Tracking data
        self.charities_processed: List[Dict[str, Any]] = []
        self.source_failures: Dict[str, List[Dict]] = defaultdict(list)
        self.tier_distributions: Dict[str, Counter] = {
            "impact": Counter(),
            "confidence": Counter(),
            "zakat": Counter(),
        }
        self.data_freshness: Dict[str, List[int]] = defaultdict(list)
        self.missing_data_issues: List[Dict[str, Any]] = []
        self.llm_costs: List[Dict[str, Any]] = []

    def record_charity_result(
        self,
        charity_id: int,
        ein: str,
        name: str,
        success: bool,
        impact_tier: Optional[str] = None,
        confidence_tier: Optional[str] = None,
        zakat_classification: Optional[str] = None,
        data_completeness_pct: Optional[float] = None,
        sources_succeeded: Optional[List[str]] = None,
        sources_failed: Optional[List[str]] = None,
        duration_seconds: Optional[float] = None,
    ):
        """
        Record the result of processing a charity.

        Args:
            charity_id: Database ID
            ein: EIN
            name: Charity name
            success: Whether evaluation succeeded
            impact_tier: Impact tier if successful
            confidence_tier: Confidence tier if successful
            zakat_classification: Zakat classification if successful
            data_completeness_pct: Percentage of data available
            sources_succeeded: List of successful data sources
            sources_failed: List of failed data sources
            duration_seconds: Processing time
        """
        result = {
            "charity_id": charity_id,
            "ein": ein,
            "name": name,
            "success": success,
            "impact_tier": impact_tier,
            "confidence_tier": confidence_tier,
            "zakat_classification": zakat_classification,
            "data_completeness_pct": data_completeness_pct,
            "sources_succeeded": sources_succeeded or [],
            "sources_failed": sources_failed or [],
            "duration_seconds": duration_seconds,
        }

        self.charities_processed.append(result)

        # Update tier distributions
        if success and impact_tier:
            self.tier_distributions["impact"][impact_tier] += 1
        if success and confidence_tier:
            self.tier_distributions["confidence"][confidence_tier] += 1
        if success and zakat_classification:
            self.tier_distributions["zakat"][zakat_classification] += 1

        # Track missing data
        if data_completeness_pct is not None and data_completeness_pct < 100:
            self.missing_data_issues.append(
                {
                    "ein": ein,
                    "name": name,
                    "completeness_pct": data_completeness_pct,
                }
            )

    def record_source_failure(
        self,
        charity_id: int,
        ein: str,
        source: str,
        error_message: str,
    ):
        """
        Record a data source failure.

        Args:
            charity_id: Charity database ID
            ein: EIN
            source: Data source name
            error_message: Error details
        """
        self.source_failures[source].append(
            {
                "charity_id": charity_id,
                "ein": ein,
                "error": error_message,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def record_data_freshness(self, source: str, age_days: int):
        """
        Record data freshness for a source.

        Args:
            source: Data source name
            age_days: Age of data in days
        """
        self.data_freshness[source].append(age_days)

    def record_llm_cost(
        self,
        charity_id: int,
        ein: str,
        narrative_type: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
    ):
        """
        Record LLM API usage and cost.

        Args:
            charity_id: Charity database ID
            ein: EIN
            narrative_type: Type of narrative generated
            prompt_tokens: Input tokens used
            completion_tokens: Output tokens used
            cost_usd: Estimated cost in USD
        """
        self.llm_costs.append(
            {
                "charity_id": charity_id,
                "ein": ein,
                "narrative_type": narrative_type,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost_usd": cost_usd,
            }
        )

    def finalize(self):
        """Mark the pipeline run as complete."""
        self.end_time = datetime.now()

    def generate_summary(self) -> Dict[str, Any]:
        """
        Generate summary statistics for the pipeline run.

        Returns:
            Dictionary with summary stats
        """
        if not self.end_time:
            self.finalize()

        total_charities = len(self.charities_processed)
        succeeded = sum(1 for c in self.charities_processed if c["success"])
        failed = total_charities - succeeded

        success_rate = (succeeded / total_charities * 100) if total_charities > 0 else 0

        # Calculate total LLM costs
        total_llm_cost = sum(c["cost_usd"] for c in self.llm_costs)
        total_prompt_tokens = sum(c["prompt_tokens"] for c in self.llm_costs)
        total_completion_tokens = sum(c["completion_tokens"] for c in self.llm_costs)

        # Calculate average processing time
        processing_times = [
            c["duration_seconds"] for c in self.charities_processed if c["duration_seconds"] is not None
        ]
        avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0

        # Data source success rates
        source_stats = {}
        for source in ["charity_navigator", "propublica", "candid", "website"]:
            source_successes = sum(1 for c in self.charities_processed if source in c.get("sources_succeeded", []))
            source_failures_count = len(self.source_failures.get(source, []))
            total_attempts = source_successes + source_failures_count

            source_stats[source] = {
                "successes": source_successes,
                "failures": source_failures_count,
                "total_attempts": total_attempts,
                "success_rate": ((source_successes / total_attempts * 100) if total_attempts > 0 else 0),
            }

        return {
            "run_id": self.run_id,
            "methodology_version": self.methodology_version,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": (self.end_time - self.start_time).total_seconds(),
            "charities": {
                "total": total_charities,
                "succeeded": succeeded,
                "failed": failed,
                "success_rate_pct": round(success_rate, 2),
            },
            "tier_distributions": {
                "impact": dict(self.tier_distributions["impact"]),
                "confidence": dict(self.tier_distributions["confidence"]),
                "zakat": dict(self.tier_distributions["zakat"]),
            },
            "data_sources": source_stats,
            "llm_costs": {
                "total_cost_usd": round(total_llm_cost, 4),
                "total_prompt_tokens": total_prompt_tokens,
                "total_completion_tokens": total_completion_tokens,
                "total_tokens": total_prompt_tokens + total_completion_tokens,
                "narratives_generated": len(self.llm_costs),
            },
            "performance": {
                "avg_processing_time_sec": round(avg_processing_time, 2),
                "total_duration_sec": round((self.end_time - self.start_time).total_seconds(), 2),
            },
            "data_quality": {
                "charities_with_missing_data": len(self.missing_data_issues),
                "avg_completeness_pct": round(
                    sum(
                        c.get("data_completeness_pct", 0)
                        for c in self.charities_processed
                        if c.get("data_completeness_pct") is not None
                    )
                    / max(len(self.charities_processed), 1),
                    2,
                ),
            },
        }

    def generate_detailed_report(self) -> str:
        """
        Generate human-readable detailed report.

        Returns:
            Formatted report string
        """
        summary = self.generate_summary()

        report_lines = [
            "=" * 80,
            "CHARITY EVALUATION PIPELINE - ADMIN REPORT",
            "=" * 80,
            "",
            f"Run ID: {summary['run_id']}",
            f"Methodology Version: {summary['methodology_version']}",
            f"Started: {summary['start_time']}",
            f"Completed: {summary['end_time']}",
            f"Duration: {summary['duration_seconds']:.2f} seconds",
            "",
            "=" * 80,
            "CHARITY PROCESSING SUMMARY",
            "=" * 80,
            "",
            f"Total Charities: {summary['charities']['total']}",
            f"Succeeded: {summary['charities']['succeeded']}",
            f"Failed: {summary['charities']['failed']}",
            f"Success Rate: {summary['charities']['success_rate_pct']:.2f}%",
            "",
            "=" * 80,
            "TIER DISTRIBUTIONS",
            "=" * 80,
            "",
            "Impact Tiers:",
        ]

        for tier, count in summary["tier_distributions"]["impact"].items():
            report_lines.append(f"  {tier}: {count}")

        report_lines.extend(
            [
                "",
                "Confidence Tiers:",
            ]
        )

        for tier, count in summary["tier_distributions"]["confidence"].items():
            report_lines.append(f"  {tier}: {count}")

        report_lines.extend(
            [
                "",
                "Zakat Classifications:",
            ]
        )

        for classification, count in summary["tier_distributions"]["zakat"].items():
            report_lines.append(f"  {classification}: {count}")

        report_lines.extend(
            [
                "",
                "=" * 80,
                "DATA SOURCE PERFORMANCE",
                "=" * 80,
                "",
            ]
        )

        for source, stats in summary["data_sources"].items():
            report_lines.append(f"{source}:")
            report_lines.append(f"  Successes: {stats['successes']}")
            report_lines.append(f"  Failures: {stats['failures']}")
            report_lines.append(f"  Success Rate: {stats['success_rate']:.2f}%")
            report_lines.append("")

        report_lines.extend(
            [
                "=" * 80,
                "LLM COSTS & TOKEN USAGE",
                "=" * 80,
                "",
                f"Total Cost: ${summary['llm_costs']['total_cost_usd']:.4f}",
                f"Narratives Generated: {summary['llm_costs']['narratives_generated']}",
                f"Prompt Tokens: {summary['llm_costs']['total_prompt_tokens']:,}",
                f"Completion Tokens: {summary['llm_costs']['total_completion_tokens']:,}",
                f"Total Tokens: {summary['llm_costs']['total_tokens']:,}",
                "",
                "=" * 80,
                "PERFORMANCE METRICS",
                "=" * 80,
                "",
                f"Average Processing Time: {summary['performance']['avg_processing_time_sec']:.2f} sec/charity",
                f"Total Duration: {summary['performance']['total_duration_sec']:.2f} seconds",
                "",
                "=" * 80,
                "DATA QUALITY",
                "=" * 80,
                "",
                f"Charities with Missing Data: {summary['data_quality']['charities_with_missing_data']}",
                f"Average Data Completeness: {summary['data_quality']['avg_completeness_pct']:.2f}%",
                "",
            ]
        )

        if self.missing_data_issues:
            report_lines.extend(
                [
                    "Charities with <100% Data:",
                    "",
                ]
            )
            for issue in self.missing_data_issues[:10]:  # Show top 10
                report_lines.append(f"  {issue['ein']} - {issue['name']}: {issue['completeness_pct']:.1f}%")
            if len(self.missing_data_issues) > 10:
                report_lines.append(f"  ... and {len(self.missing_data_issues) - 10} more")
            report_lines.append("")

        if self.source_failures:
            report_lines.extend(
                [
                    "=" * 80,
                    "DATA SOURCE FAILURES (Details)",
                    "=" * 80,
                    "",
                ]
            )
            for source, failures in self.source_failures.items():
                if failures:
                    report_lines.append(f"{source} failures ({len(failures)}):")
                    for failure in failures[:5]:  # Show first 5 per source
                        report_lines.append(f"  EIN {failure['ein']}: {failure['error']}")
                    if len(failures) > 5:
                        report_lines.append(f"  ... and {len(failures) - 5} more")
                    report_lines.append("")

        report_lines.extend(
            [
                "=" * 80,
                "END OF REPORT",
                "=" * 80,
            ]
        )

        return "\n".join(report_lines)

    def save_json_report(self, filepath: str):
        """
        Save detailed report as JSON file.

        Args:
            filepath: Path to save JSON report
        """
        summary = self.generate_summary()

        # Add detailed data
        full_report = {
            **summary,
            "charities_processed": self.charities_processed,
            "source_failures": dict(self.source_failures),
            "missing_data_issues": self.missing_data_issues,
            "llm_cost_details": self.llm_costs,
        }

        with open(filepath, "w") as f:
            json.dump(full_report, f, indent=2)

    def save_text_report(self, filepath: str):
        """
        Save detailed report as text file.

        Args:
            filepath: Path to save text report
        """
        report_text = self.generate_detailed_report()

        with open(filepath, "w") as f:
            f.write(report_text)
