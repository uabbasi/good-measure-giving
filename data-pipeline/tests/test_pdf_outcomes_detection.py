"""reports_outcomes must reflect the outcomes we actually extracted from PDFs.

CharityMetricsAggregator.aggregate() sets metrics_data["pdf_outcomes"] from
website_profile["outcomes_data"] -- populated by web_collector.py only when
an LLM extraction of a charity's own PDF (Impact Report, Annual Report)
actually found an outcomes_summary. That's real evidence, not a placeholder.

But reports_outcomes -- the boolean the narrative prompt actually reads to
decide whether to say a charity "lacks outcome metrics" -- was only ever
derived from candid_profile/website_profile's own reports_outcomes flag (a
page-crawl signal) or discovered_profile's outcomes section. It never looked
at pdf_outcomes at all.

Real occurrence: 87-2410117 (Human Appeal) has an Impact Report (2024) and an
Annual Report (2025) we hold, both with detailed outcome metrics, but no
page-crawl flag set reports_outcomes -- so metrics_data["reports_outcomes"]
stayed None and the narrative said the charity "lacks outcome metrics".
Donor-material: it wrongly disparages a charity whose own PDFs we already
extracted real outcomes from.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers.charity_metrics_aggregator import CharityMetricsAggregator


class TestPdfOutcomesSetReportsOutcomes:
    def test_pdf_extracted_outcomes_set_reports_outcomes_true(self):
        """87-2410117 shape: no page-crawl reports_outcomes flag, but a real
        outcomes_summary was extracted from an Impact Report PDF."""
        metrics = CharityMetricsAggregator.aggregate(
            charity_id=1,
            ein="87-2410117",
            website_profile={
                "outcomes_data": [
                    {
                        "source": "impact-report-2024.pdf",
                        "type": "impact_report",
                        "organization_name": "Human Appeal",
                        "outcomes": {"total_beneficiaries": 500000},
                    }
                ],
            },
        )
        assert metrics.reports_outcomes is True
        assert metrics.pdf_outcomes  # sanity: the data really is there

    def test_no_pdf_outcomes_and_no_flag_stays_unknown(self):
        """Regression guard: must not start claiming outcomes for every
        charity -- only when we actually extracted some from a PDF."""
        metrics = CharityMetricsAggregator.aggregate(
            charity_id=1,
            ein="12-3456789",
            website_profile={"outcomes_data": []},
        )
        assert metrics.reports_outcomes is None

    def test_existing_positive_flag_is_not_overridden(self):
        metrics = CharityMetricsAggregator.aggregate(
            charity_id=1,
            ein="12-3456789",
            candid_profile={"reports_outcomes": True},
            website_profile={"outcomes_data": []},
        )
        assert metrics.reports_outcomes is True

    def test_existing_negative_flag_is_overridden_by_real_pdf_evidence(self):
        """A page-crawl flag saying "no" must not outrank an actual
        extracted outcomes_summary from the charity's own PDF."""
        metrics = CharityMetricsAggregator.aggregate(
            charity_id=1,
            ein="87-2410117",
            candid_profile={"reports_outcomes": False},
            website_profile={
                "outcomes_data": [
                    {"source": "annual-report-2025.pdf", "outcomes": {"programs_delivered": 40}}
                ],
            },
        )
        assert metrics.reports_outcomes is True
