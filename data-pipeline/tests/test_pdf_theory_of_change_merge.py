"""Theory of change extracted from a downloaded PDF never reached the top-level
website_profile field the scorer reads.

AnnualReportParser.parse_pdf() extracts theory_of_change for every non-990 PDF
(src/parsers/annual_report_parser.py), and it landed correctly inside each
entry of website_profile["llm_extracted_pdfs"][i]["extracted_data"] -- but
WebsiteCollector._extract_pdf_data()'s "use first available data for
top-level fields" block only promoted mission/programs/financial_data, never
theory_of_change. So has_theory_of_change read False for any charity whose
own site had no separate, literally-labeled "Theory of Change" page, even
when a downloaded annual/program report described one in detail (confirmed
on real data: Doctors Without Borders, EIN 13-3433452, 5/5 downloaded PDFs
had a real theory_of_change string, all invisible to the scorer).
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.web_collector import WebsiteCollector  # noqa: E402


def _extract(tmp_path, per_pdf_results):
    """Call _extract_pdf_data unbound against a lightweight fake self.

    per_pdf_results: list of dicts, one per simulated downloaded PDF, in the
    exact shape AnnualReportParser.to_dict() returns.
    """
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


def _result(theory_of_change=None, mission=None, programs=None, financials=None):
    return {
        "theory_of_change": theory_of_change,
        # AnnualReportParser.to_dict() names this "mission_statement", not
        # "mission" -- see test_pdf_field_promotion.py for that bug.
        "mission_statement": mission,
        "programs": programs,
        "financials": financials,
        "organization_name": "Test Org",
        "year": 2024,
        "outcomes_summary": {},
    }


class TestTheoryOfChangePromotedToTopLevel:
    def test_theory_of_change_from_a_single_pdf_reaches_the_top_level(self, tmp_path):
        pdf_data, _cost = _extract(tmp_path, [_result(theory_of_change="Vaccines prevent disease.")])
        assert pdf_data["theory_of_change"] == "Vaccines prevent disease."

    def test_first_non_empty_theory_of_change_wins_across_multiple_pdfs(self, tmp_path):
        pdf_data, _cost = _extract(
            tmp_path,
            [_result(theory_of_change=None), _result(theory_of_change="Second PDF's ToC.")],
        )
        assert pdf_data["theory_of_change"] == "Second PDF's ToC."

    def test_no_pdf_mentions_it_stays_none_not_a_placeholder(self, tmp_path):
        pdf_data, _cost = _extract(tmp_path, [_result(), _result()])
        assert pdf_data["theory_of_change"] is None

    def test_mission_and_theory_of_change_promote_independently(self, tmp_path):
        """Regression guard: the fix must not disturb the existing mission/
        programs/financial_data promotion it sits next to."""
        pdf_data, _cost = _extract(
            tmp_path,
            [_result(theory_of_change="ToC text.", mission="Mission text.")],
        )
        assert pdf_data["theory_of_change"] == "ToC text."
        assert pdf_data["mission"] == "Mission text."
