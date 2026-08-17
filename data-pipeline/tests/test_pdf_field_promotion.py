"""More fields AnnualReportParser extracts per PDF that never reached the
top-level website_profile dict CharityMetricsAggregator reads -- found by
auditing every field to_dict() (src/parsers/annual_report_parser.py) returns
against what WebsiteCollector._extract_pdf_data() actually promotes, after
finding the same bug for theory_of_change (test_pdf_theory_of_change_merge.py).

mission had a DIFFERENT defect: to_dict() names the field "mission_statement",
but the promotion check read result.get("mission") -- a key that has never
existed in that dict, so the check has never once matched.

beneficiaries_served and impact_metrics were never promoted at all, not even
a wrong-key attempt. CharityMetricsAggregator uses both as fallback sources
for the beneficiary count that drives Cost Per Beneficiary scoring (see
charity_metrics_aggregator.py's four-tier beneficiary resolution: Candid,
then website_profile.beneficiaries_served, then ummah_gap_data, then
impact_metrics.metrics pattern-matching) -- real corpus audit found 21 of 94
Cost-Per-Beneficiary-gap charities (including Doctors Without Borders,
Natural Resources Defense Council, Earthjustice) had a real beneficiary count
sitting in a downloaded PDF's extraction, invisible to the scorer.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.web_collector import WebsiteCollector  # noqa: E402


def _extract(tmp_path, per_pdf_results):
    fake_self = MagicMock()
    fake_self.logger = None
    fake_self.annual_report_parser.parse_pdf.side_effect = [
        (MagicMock(), 0.01) for _ in per_pdf_results
    ]
    fake_self.annual_report_parser.to_dict.side_effect = per_pdf_results

    pdf_documents = []
    for i, _ in enumerate(per_pdf_results):
        p = tmp_path / f"doc_{i}.pdf"
        p.write_bytes(b"%PDF-1.4 fake")
        pdf_documents.append({
            "downloaded": True,
            "file_path": str(p),
            "document_type": "program_report",
            "url": f"https://example.org/doc_{i}.pdf",
        })

    return WebsiteCollector._extract_pdf_data(fake_self, pdf_documents)


def _result(**overrides):
    base = {
        "mission_statement": None,
        "theory_of_change": None,
        "beneficiaries_served": None,
        "impact_metrics": None,
        "programs": None,
        "financials": None,
        "organization_name": "Test Org",
        "year": 2024,
        "outcomes_summary": {},
    }
    base.update(overrides)
    return base


class TestMissionPromotionUsesTheRealKeyName:
    def test_mission_statement_reaches_the_top_level_as_mission(self, tmp_path):
        pdf_data, _cost = _extract(tmp_path, [_result(mission_statement="MSF delivers emergency medical relief.")])
        assert pdf_data["mission"] == "MSF delivers emergency medical relief."

    def test_the_old_wrong_key_never_matched_anything(self, tmp_path):
        """Regression guard: a dict that ONLY has the old, never-checked
        'mission' key (not 'mission_statement') must not promote -- proves
        the fix reads mission_statement, not a key AnnualReportParser
        never emits."""
        fabricated_old_shape = _result()
        fabricated_old_shape["mission"] = "This key doesn't really exist in to_dict() output"
        pdf_data, _cost = _extract(tmp_path, [fabricated_old_shape])
        assert pdf_data["mission"] is None


class TestBeneficiariesServedPromotion:
    def test_beneficiary_count_from_a_pdf_reaches_the_top_level(self, tmp_path):
        pdf_data, _cost = _extract(tmp_path, [_result(beneficiaries_served=53000)])
        assert pdf_data["beneficiaries_served"] == 53000

    def test_zero_is_falsy_and_does_not_promote(self, tmp_path):
        """0 beneficiaries is indistinguishable from 'not extracted' here --
        matches the existing mission/programs/financial_data pattern this
        promotion block already uses (truthiness, not is-not-None)."""
        pdf_data, _cost = _extract(tmp_path, [_result(beneficiaries_served=0)])
        assert pdf_data["beneficiaries_served"] is None

    def test_no_pdf_mentions_it_stays_none(self, tmp_path):
        pdf_data, _cost = _extract(tmp_path, [_result(), _result()])
        assert pdf_data["beneficiaries_served"] is None


class TestImpactMetricsPromotion:
    def test_impact_metrics_from_a_pdf_reaches_the_top_level(self, tmp_path):
        metrics = {"metrics": {"people_served_annually": 12000}}
        pdf_data, _cost = _extract(tmp_path, [_result(impact_metrics=metrics)])
        assert pdf_data["impact_metrics"] == metrics


class TestGeographicCoveragePromotion:
    def test_countries_and_regions_combine_into_geographic_coverage(self, tmp_path):
        pdf_data, _cost = _extract(
            tmp_path,
            [_result(countries_served=["Haiti", "Kenya"], regions_served=["Port-au-Prince"])],
        )
        assert pdf_data["geographic_coverage"] == ["Haiti", "Kenya", "Port-au-Prince"]

    def test_only_countries_still_promotes(self, tmp_path):
        pdf_data, _cost = _extract(tmp_path, [_result(countries_served=["Haiti"])])
        assert pdf_data["geographic_coverage"] == ["Haiti"]

    def test_neither_stays_empty(self, tmp_path):
        pdf_data, _cost = _extract(tmp_path, [_result()])
        assert pdf_data["geographic_coverage"] == []


class TestAllFourPromoteIndependently:
    def test_mission_toc_beneficiaries_and_impact_metrics_all_promote_together(self, tmp_path):
        pdf_data, _cost = _extract(
            tmp_path,
            [
                _result(
                    mission_statement="Our mission.",
                    theory_of_change="Our theory.",
                    beneficiaries_served=1000,
                    impact_metrics={"metrics": {"x": 1}},
                )
            ],
        )
        assert pdf_data["mission"] == "Our mission."
        assert pdf_data["theory_of_change"] == "Our theory."
        assert pdf_data["beneficiaries_served"] == 1000
        assert pdf_data["impact_metrics"] == {"metrics": {"x": 1}}
