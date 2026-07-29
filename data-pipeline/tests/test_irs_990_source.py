"""Fetching 990 XML from the IRS instead of ProPublica's mirror.

ProPublica put a Cloudflare managed challenge on /nonprofits/download-xml
(HTTP 403, `cf-mitigated: challenge`, "Security Check — ProPublica"). Cookies
from the org page carry no clearance and headless Chromium is detected and
never clears. Getting through would mean defeating an access control the
publisher installed deliberately, so we go to the primary source instead:

  index_YYYY.csv   EIN -> OBJECT_ID, TAX_PERIOD, XML_BATCH_ID
  {batch}.zip      bundles that support HTTP range requests

The bundles are 150-260 MB with ~48k members each, so they are read via range
requests: the ZIP central directory plus the one member wanted. Measured on
2026_TEOS_XML_04A: 3.58 MB fetched out of 261.9 MB for one filing.

The IRS is upstream of ProPublica, so this is never staler -- for EIN
83-1794093 it returns TaxYr 2025 where our stored ProPublica copy had 2024.
"""

import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.irs_990_source import (
    IRS_INDEX_URL_TEMPLATE,
    FilingRef,
    HttpRangeReader,
    build_index_map,
    zip_member_url,
)

FIXTURE_ZIP = Path(__file__).parent / "fixtures" / "irs_test_batch.zip"

INDEX_CSV = """RETURN_ID,FILING_TYPE,EIN,TAX_PERIOD,SUB_DATE,TAXPAYER_NAME,RETURN_TYPE,DLN,OBJECT_ID,XML_BATCH_ID
24007824,EFILE,831794093,202412,2026,HIKMA HEALTH INC,990,93493044016096,202640449349301609,2026_TEOS_XML_02A
,EFILE,831794093,202512,2026,HIKMA HEALTH INC,990EZ,93492093012056,202600939349201205,2026_TEOS_XML_04A
24028343,EFILE,882454707,202412,2026,HEAL PALESTINE INC,990,93493071014146,202640719349301414,2026_TEOS_XML_03A
"""


class TestIndexParsing:
    def test_maps_ein_to_its_filings(self):
        m = build_index_map(INDEX_CSV.splitlines())
        assert "831794093" in m
        assert len(m["831794093"]) == 2

    def test_filings_are_most_recent_tax_period_first(self):
        m = build_index_map(INDEX_CSV.splitlines())
        periods = [f.tax_period for f in m["831794093"]]
        assert periods == ["202512", "202412"], (
            "callers take the first N filings as 'most recent'"
        )

    def test_carries_the_fields_needed_to_locate_the_xml(self):
        f = build_index_map(INDEX_CSV.splitlines())["882454707"][0]
        assert f == FilingRef(
            ein="882454707",
            tax_period="202412",
            object_id="202640719349301414",
            batch_id="2026_TEOS_XML_03A",
            return_type="990",
        )

    def test_a_blank_return_id_row_is_still_usable(self):
        """The IRS leaves RETURN_ID empty on many rows; the columns we need
        are populated regardless and the row must not be dropped."""
        m = build_index_map(INDEX_CSV.splitlines())
        assert any(f.object_id == "202600939349201205" for f in m["831794093"])

    def test_unknown_ein_is_absent_not_an_error(self):
        assert "000000000" not in build_index_map(INDEX_CSV.splitlines())

    def test_a_malformed_row_is_skipped_not_fatal(self):
        lines = INDEX_CSV.splitlines() + ["garbage,row"]
        m = build_index_map(lines)
        assert len(m) == 2


class TestUrls:
    def test_index_url_is_per_submission_year(self):
        assert IRS_INDEX_URL_TEMPLATE.format(year=2026).endswith("/2026/index_2026.csv")

    def test_batch_url_is_derived_from_the_batch_id(self):
        url = zip_member_url("2026_TEOS_XML_04A")
        assert url.endswith("/2026/2026_TEOS_XML_04A.zip"), url


class TestHttpRangeReader:
    """zipfile drives this through seek/read; it must behave like a file."""

    class _FakeSession:
        def __init__(self, data):
            self.data = data
            self.requests = 0

        def head(self, url, **kw):
            class R:
                headers = {"content-length": str(len(self.data))}
            return R()

        def get(self, url, headers=None, **kw):
            self.requests += 1
            rng = headers["Range"].split("=")[1]
            start, end = (int(x) for x in rng.split("-"))
            payload = self.data[start : end + 1]

            class R:
                content = payload
                status_code = 206
            return R()

    def _reader(self):
        return HttpRangeReader("http://x/test.zip", session=self._FakeSession(FIXTURE_ZIP.read_bytes()))

    def test_zipfile_can_list_members_through_it(self):
        zf = zipfile.ZipFile(self._reader())
        assert "202600939349201205_public.xml" in zf.namelist()

    def test_a_single_member_extracts_correctly(self):
        zf = zipfile.ZipFile(self._reader())
        xml = zf.read("202600939349201205_public.xml").decode()
        assert "<TaxYr>2025</TaxYr>" in xml

    def test_it_does_not_download_the_whole_archive(self):
        raw = FIXTURE_ZIP.read_bytes()
        session = self._FakeSession(raw)
        zf = zipfile.ZipFile(HttpRangeReader("http://x/test.zip", session=session))
        zf.read("202600939349201205_public.xml")
        # The real bundles are 260MB; reading them whole per filing is the
        # thing this class exists to avoid.
        assert session.requests < 10

    def test_reports_its_size_without_reading_the_body(self):
        r = self._reader()
        assert r.size == len(FIXTURE_ZIP.read_bytes())
        assert r.seekable() and r.readable()

    def test_seek_from_end_works(self):
        r = self._reader()
        r.seek(-4, io.SEEK_END)
        assert len(r.read(4)) == 4


class TestAnUnreadableMemberDegradesInsteadOfFailingTheRun:
    """fetch_filing_xml promises to return None when a filing cannot be read,
    so one unavailable filing costs that charity its grants data and nothing
    more. NotImplementedError escaped that promise.

    Python's zipfile raises NotImplementedError("That compression method is
    not supported") for members compressed with anything outside its
    supported set. Some IRS bundles carry such members, and because the
    except clause listed only OSError and BadZipFile, the error propagated
    out of the collector, failed form990_grants as a required source, and
    aborted the whole crawl for that charity. Observed on the 2026-07-28
    cohort run: 26-3342933, 36-4476244 and one other lost their entire crawl
    to it -- the same shape as every other bug this pass, a limit on what we
    could read reported as something worse.
    """

    def _ref(self):
        return FilingRef(
            ein="831794093",
            object_id="202600939349201205",
            batch_id="2026_TEOS_XML_04A",
            tax_period="202512",
            return_type="990EZ",
        )

    def _fetch_raising(self, exc):
        from unittest.mock import patch

        from src.collectors import irs_990_source

        with patch.object(irs_990_source, "HttpRangeReader", side_effect=exc):
            return irs_990_source.fetch_filing_xml(self._ref(), session=object())

    def test_unsupported_compression_returns_none(self):
        assert (
            self._fetch_raising(
                NotImplementedError("That compression method is not supported")
            )
            is None
        )

    def test_a_bad_archive_still_returns_none(self):
        assert self._fetch_raising(zipfile.BadZipFile("File is not a zip file")) is None

    def test_a_network_error_still_returns_none(self):
        assert self._fetch_raising(OSError("connection reset")) is None

    def test_an_unexpected_error_still_propagates(self):
        """Narrowness guard: this widens the contract for unreadable archives,
        not into a bare except that hides real defects."""
        import pytest

        with pytest.raises(ValueError):
            self._fetch_raising(ValueError("a genuine bug"))
