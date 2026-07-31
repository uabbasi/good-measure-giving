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


class TestA990TDoesNotDisplaceTheRealReturn:
    """Form 990-T is the unrelated-business-income return. It carries no
    Schedule I and no functional expenses -- nothing this collector parses.

    Organisations that file one file it for the SAME tax period as their
    informational 990, so the index holds two rows per period. The picker kept
    one row per period by first arrival, which means the CSV's row order chose
    the return. For EIN 36-4476244 (Zakat Foundation of America) index_2025
    and index_2024 both list the 990-T first, so two of its three filing slots
    went to returns with no grants in them, and the run logged "Extracted 0
    domestic + 0 foreign grants" from filings that could never have had any.
    """

    EIN = "364476244"

    def _index(self):
        # Row order as the IRS actually publishes it: the 990-T leads.
        return {
            self.EIN: [
                FilingRef(self.EIN, "202406", "obj-2025-990T", "2025_TEOS_XML_05A", "990T"),
                FilingRef(self.EIN, "202406", "obj-2025-990", "2025_TEOS_XML_05A", "990"),
                FilingRef(self.EIN, "202306", "obj-2024-990T", "2024_TEOS_XML_05a", "990T"),
                FilingRef(self.EIN, "202306", "obj-2024-990", "2024_TEOS_XML_05a", "990"),
            ]
        }

    def _picked(self, tmp_path):
        c = _collector(tmp_path)
        with patch.object(c, "_load_index_year", return_value=self._index()):
            return c._irs_filings(self.EIN)

    def test_the_informational_return_wins_its_tax_period(self, tmp_path):
        picked = self._picked(tmp_path)
        assert [f.object_id for f in picked] == ["obj-2025-990", "obj-2024-990"]

    def test_one_filing_per_tax_period_still_holds(self, tmp_path):
        periods = [f.tax_period for f in self._picked(tmp_path)]
        assert len(periods) == len(set(periods))

    def test_a_period_with_only_a_990t_is_still_kept(self, tmp_path):
        """Ranking the 990-T last must not throw the period away -- for a
        period we have nothing else for, it is still the only evidence the
        organisation filed at all."""
        only_t = {self.EIN: [
            FilingRef(self.EIN, "202306", "obj-only-990T", "2024_TEOS_XML_05A", "990T")
        ]}
        c = _collector(tmp_path)
        with patch.object(c, "_load_index_year", return_value=only_t):
            assert [f.object_id for f in c._irs_filings(self.EIN)] == ["obj-only-990T"]
