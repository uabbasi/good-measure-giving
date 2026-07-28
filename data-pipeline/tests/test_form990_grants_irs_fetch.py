"""Form990GrantsCollector fetches from the IRS, not ProPublica's mirror.

The parse side is untouched -- ProPublica served the same IRS e-file XML, so
only where the bytes come from changes.

The on-disk XML cache is deliberately reused as-is: it is keyed by object_id,
and the 482 filings cached before ProPublica's Cloudflare challenge went up
remain valid (990s do not change once filed).
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.form990_grants import Form990GrantsCollector
from src.collectors.irs_990_source import FilingRef

XML = (
    '<?xml version="1.0"?><Return xmlns="http://www.irs.gov/efile">'
    "<ReturnHeader><TaxYr>2025</TaxYr><Filer><EIN>831794093</EIN>"
    "<BusinessNameLine1Txt>HIKMA HEALTH INC</BusinessNameLine1Txt></Filer></ReturnHeader>"
    "<ReturnData><IRS990><CYTotalRevenueAmt>136348</CYTotalRevenueAmt></IRS990></ReturnData></Return>"
)

REFS = [
    FilingRef("831794093", "202512", "obj-2025", "2026_TEOS_XML_04A", "990EZ"),
    FilingRef("831794093", "202412", "obj-2024", "2026_TEOS_XML_02A", "990"),
]


def _collector(tmp_path):
    return Form990GrantsCollector(cache_dir=tmp_path / "xml")


class TestFetchUsesTheIrs:
    def test_it_never_touches_propublica_download_xml(self, tmp_path):
        c = _collector(tmp_path)
        with patch.object(c, "_irs_filings", return_value=REFS), patch(
            "src.collectors.form990_grants.fetch_filing_xml", return_value=XML
        ), patch("requests.get") as direct:
            result = c.fetch("83-1794093")
        assert result.success
        assert not direct.called, "still hitting ProPublica"

    def test_the_result_still_parses_into_a_grants_profile(self, tmp_path):
        """The packing format fetch() produces must stay readable by parse();
        they are only ever used as a pair."""
        c = _collector(tmp_path)
        with patch.object(c, "_irs_filings", return_value=REFS), patch(
            "src.collectors.form990_grants.fetch_filing_xml", return_value=XML
        ):
            fetched = c.fetch("83-1794093")
        parsed = c.parse(fetched.raw_data, "83-1794093")
        assert parsed.success, parsed.error
        profile = parsed.parsed_data["grants_profile"]
        assert profile["name"] == "HIKMA HEALTH INC"
        assert profile["tax_year"] == 2025

    def test_no_filings_is_a_verified_negative_not_a_failure(self, tmp_path):
        """A charity the IRS has no e-filed return for is a fact about that
        charity, not a fetch failure -- same distinction BBB needed."""
        c = _collector(tmp_path)
        with patch.object(c, "_irs_filings", return_value=[]):
            result = c.fetch("83-1794093")
        assert result.success is True
        assert result.raw_data == c.NO_XML_SENTINEL

    def test_an_unreachable_bundle_fails_rather_than_inventing_emptiness(self, tmp_path):
        c = _collector(tmp_path)
        with patch.object(c, "_irs_filings", return_value=REFS), patch(
            "src.collectors.form990_grants.fetch_filing_xml", return_value=None
        ):
            result = c.fetch("83-1794093")
        assert result.success is False
        assert result.raw_data is None


class TestTheExistingXmlCacheStillCounts:
    def test_a_cached_filing_is_not_refetched(self, tmp_path):
        c = _collector(tmp_path)
        c._cache_xml("obj-2025", XML)
        c._cache_xml("obj-2024", XML)
        with patch.object(c, "_irs_filings", return_value=REFS), patch(
            "src.collectors.form990_grants.fetch_filing_xml"
        ) as net:
            result = c.fetch("83-1794093")
        assert result.success
        assert not net.called, "re-downloaded a filing already on disk"

    def test_a_newly_fetched_filing_is_written_to_the_cache(self, tmp_path):
        c = _collector(tmp_path)
        with patch.object(c, "_irs_filings", return_value=REFS[:1]), patch(
            "src.collectors.form990_grants.fetch_filing_xml", return_value=XML
        ):
            c.fetch("83-1794093")
        assert c._get_cached_xml("obj-2025") == XML
