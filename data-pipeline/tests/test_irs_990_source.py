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


def _build_test_batch() -> bytes:
    """A miniature stand-in for an IRS bundle, built here rather than stored.

    This was a checked-in fixture, tests/fixtures/irs_test_batch.zip, and
    .gitignore's blanket `*.zip` silently kept it out of every commit. It
    existed only in the worktree that wrote it, so the five tests below passed
    there and failed with FileNotFoundError for everyone else -- the suite
    reported green on a fixture no clone had. Generating it removes both the
    binary and the need for a gitignore exception, and the archive is small
    enough that building it costs nothing.

    Two members on purpose: one deflated (the shape real bundles use) and one
    stored, so a reader that only handles compressed entries still fails.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "202600939349201205_public.xml",
            '<?xml version="1.0"?><Return xmlns="http://www.irs.gov/efile">'
            "<ReturnHeader><TaxYr>2025</TaxYr></ReturnHeader></Return>",
            compress_type=zipfile.ZIP_DEFLATED,
        )
        zf.writestr("999_public.xml", "stub\n", compress_type=zipfile.ZIP_STORED)
    return buf.getvalue()


TEST_BATCH_ZIP = _build_test_batch()

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
        return HttpRangeReader("http://x/test.zip", session=self._FakeSession(TEST_BATCH_ZIP))

    def test_zipfile_can_list_members_through_it(self):
        zf = zipfile.ZipFile(self._reader())
        assert "202600939349201205_public.xml" in zf.namelist()

    def test_a_single_member_extracts_correctly(self):
        zf = zipfile.ZipFile(self._reader())
        xml = zf.read("202600939349201205_public.xml").decode()
        assert "<TaxYr>2025</TaxYr>" in xml

    def test_it_does_not_download_the_whole_archive(self):
        raw = TEST_BATCH_ZIP
        session = self._FakeSession(raw)
        zf = zipfile.ZipFile(HttpRangeReader("http://x/test.zip", session=session))
        zf.read("202600939349201205_public.xml")
        # The real bundles are 260MB; reading them whole per filing is the
        # thing this class exists to avoid.
        assert session.requests < 10

    def test_reports_its_size_without_reading_the_body(self):
        r = self._reader()
        assert r.size == len(TEST_BATCH_ZIP)
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


def _volume_zip(members: dict[str, str]) -> bytes:
    """A bundle holding exactly the members given, name -> body."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, body in members.items():
            zf.writestr(name, body, compress_type=zipfile.ZIP_DEFLATED)
    return buf.getvalue()


class TestTheIndexDoesNotAlwaysNameTheBundleThatHoldsTheFiling:
    """XML_BATCH_ID is not a reliable address, in three separate ways.

    Measured against the live IRS on 2026-07-31, chasing EIN 36-4476244
    (Zakat Foundation of America) failing its crawl with "Failed to download
    any XML filings":

    1. OVERFLOW VOLUMES. index_2026 assigns 168,344 rows to
       2026_TEOS_XML_05A. That bundle holds 84,172 members and stops at
       object_id 202621329349203217. 2026_TEOS_XML_05B holds the next 84,172,
       starting at 202621329349203222 -- and is named by no index row at all.
       Half of the batch was therefore unreachable, and a sample of twelve
       arbitrary 05A rows found only five of them present.

    2. CASE. index_2024 writes the volume letter lowercase
       ("2024_TEOS_XML_05a"); the server has 05A.zip and 302-redirects the
       lowercase URL to irs.gov/404. zipfile then reports "File is not a zip
       file", which reads like corruption rather than a wrong address.

    3. NESTED MEMBERS. The 2024 bundles store members under a directory
       ("2024_TEOS_XML_05A/<object_id>_public.xml"); 2025 and 2026 store them
       flat. An exact-name lookup misses the nested ones entirely.

    All three surfaced as the same thing -- a filing we could not address
    reported as a filing that does not exist.
    """

    OID = "202631349349308303"
    MEMBER = f"{OID}_public.xml"
    XML = '<?xml version="1.0"?><Return><ReturnHeader><TaxYr>2025</TaxYr></ReturnHeader></Return>'

    def _ref(self, batch_id="2026_TEOS_XML_05A"):
        return FilingRef(
            ein="364476244", tax_period="202506", object_id=self.OID,
            batch_id=batch_id, return_type="990",
        )

    def _serving(self, bundles: dict[str, bytes]):
        """Patch HttpRangeReader so each bundle URL serves its own bytes.

        A URL with no entry raises OSError, which is what a 404 looks like
        once the reader checks its responses.
        """
        from unittest.mock import patch

        from src.collectors import irs_990_source

        def reader(url, session=None, timeout=120):
            for name, data in bundles.items():
                if url.endswith(f"/{name}.zip"):
                    return io.BytesIO(data)
            raise OSError(f"404 for {url}")

        return patch.object(irs_990_source, "HttpRangeReader", side_effect=reader)

    def test_candidates_start_with_the_bundle_the_index_named(self):
        from src.collectors.irs_990_source import bundle_candidates

        assert next(iter(bundle_candidates("2026_TEOS_XML_05A"))) == "2026_TEOS_XML_05A"

    def test_candidates_continue_into_the_overflow_volumes(self):
        from src.collectors.irs_990_source import bundle_candidates

        got = list(bundle_candidates("2026_TEOS_XML_05A"))
        assert got[:3] == ["2026_TEOS_XML_05A", "2026_TEOS_XML_05B", "2026_TEOS_XML_05C"]

    def test_a_lowercase_volume_letter_is_normalised(self):
        from src.collectors.irs_990_source import bundle_candidates

        got = list(bundle_candidates("2024_TEOS_XML_05a"))
        assert got[0] == "2024_TEOS_XML_05A"
        assert "2024_TEOS_XML_05a" not in got

    def test_a_filing_in_the_overflow_volume_is_found(self):
        from src.collectors import irs_990_source

        bundles = {
            "2026_TEOS_XML_05A": _volume_zip({"202600000000000001_public.xml": "<other/>"}),
            "2026_TEOS_XML_05B": _volume_zip({self.MEMBER: self.XML}),
        }
        with self._serving(bundles):
            got = irs_990_source.fetch_filing_xml(self._ref(), session=object())
        assert got is not None and "<TaxYr>2025</TaxYr>" in got

    def test_a_member_stored_under_a_directory_is_found(self):
        from src.collectors import irs_990_source

        bundles = {
            "2024_TEOS_XML_05A": _volume_zip(
                {f"2024_TEOS_XML_05A/{self.MEMBER}": self.XML}
            )
        }
        with self._serving(bundles):
            got = irs_990_source.fetch_filing_xml(
                self._ref("2024_TEOS_XML_05a"), session=object()
            )
        assert got is not None and "<TaxYr>2025</TaxYr>" in got

    def test_a_filing_in_no_volume_is_still_none(self):
        """Widening where we look must not turn absence into an exception."""
        from src.collectors import irs_990_source

        bundles = {"2026_TEOS_XML_05A": _volume_zip({"202600000000000001_public.xml": "<o/>"})}
        with self._serving(bundles):
            assert irs_990_source.fetch_filing_xml(self._ref(), session=object()) is None

    def test_the_search_stops_at_the_first_absent_volume(self):
        """Volumes are contiguous, so probing past a gap is wasted downloads
        of 3.5 MB central directories -- against a bundle that does not exist.
        """
        from unittest.mock import patch

        from src.collectors import irs_990_source

        seen = []

        def reader(url, session=None, timeout=120):
            seen.append(url)
            if url.endswith("/2026_TEOS_XML_05A.zip"):
                return io.BytesIO(_volume_zip({"202600000000000001_public.xml": "<o/>"}))
            raise OSError("404")

        with patch.object(irs_990_source, "HttpRangeReader", side_effect=reader):
            assert irs_990_source.fetch_filing_xml(self._ref(), session=object()) is None
        assert len(seen) == 2, seen


def _deflate64_zip(member: str, body: bytes) -> bytes:
    """A real single-member archive compressed with Deflate64 (method 9).

    Built by hand because nothing in the standard library can write method 9 --
    which is the whole reason this case exists. Fields the reader does not
    consult (times, versions) are left at zero.
    """
    import binascii
    import struct

    import inflate64

    d = inflate64.Deflater()
    data = d.deflate(body) + d.flush()
    crc = binascii.crc32(body) & 0xFFFFFFFF
    name = member.encode()

    # version, flags, method=9, time, date, crc, csize, usize, namelen, extralen
    local = b"PK\x03\x04" + struct.pack(
        "<HHHHHIIIHH", 20, 0, 9, 0, 0, crc, len(data), len(body), len(name), 0
    ) + name
    central = b"PK\x01\x02" + struct.pack(
        "<HHHHHHIIIHHHHHII",
        20, 20, 0, 9, 0, 0, crc, len(data), len(body), len(name), 0, 0, 0, 0, 0, 0,
    ) + name
    eocd = struct.pack(
        "<4sHHHHIIH", b"PK\x05\x06", 0, 0, 1, 1,
        len(central), len(local) + len(data), 0,
    )
    return local + data + central + eocd


class TestTheBigBundlesAreDeflate64:
    """Python's zipfile cannot decompress method 9, and batch 05 is all of it.

    Measured on 2026-07-31: every one of the 84,172 members of
    2026_TEOS_XML_05A, its 84,172 in 05B, and the 81,770 in 2025_TEOS_XML_05B
    is Deflate64. Batches 01-04 are ordinary Deflate, and so is all of 2024 --
    it is the oversized batch that gets packed past deflate's limits.

    zipfile raises NotImplementedError("That compression method is not
    supported") for those, which fetch_filing_xml caught and turned into "no
    filing available". So the 168,344 filings that index_2026 assigns to batch
    05 -- 48% of the submission year -- were silently unreadable, and every
    charity among them quietly kept whatever older filing was already cached.
    """

    OID = "202631349349308303"
    XML = b'<?xml version="1.0"?><Return><ReturnHeader><TaxYr>2025</TaxYr></ReturnHeader></Return>'

    def _ref(self):
        return FilingRef(
            ein="364476244", tax_period="202506", object_id=self.OID,
            batch_id="2026_TEOS_XML_05A", return_type="990",
        )

    def test_the_fixture_really_is_method_9(self):
        """Guard: if this ever compresses as plain deflate the test below
        proves nothing."""
        zf = zipfile.ZipFile(io.BytesIO(_deflate64_zip(f"{self.OID}_public.xml", self.XML)))
        assert [i.compress_type for i in zf.infolist()] == [9]

    def test_stock_zipfile_cannot_read_it(self):
        """The defect itself, so the fix below is not testing a no-op."""
        import pytest

        zf = zipfile.ZipFile(io.BytesIO(_deflate64_zip(f"{self.OID}_public.xml", self.XML)))
        with pytest.raises(NotImplementedError):
            zf.read(f"{self.OID}_public.xml")

    def test_a_deflate64_filing_is_read(self):
        from unittest.mock import patch

        from src.collectors import irs_990_source

        blob = _deflate64_zip(f"{self.OID}_public.xml", self.XML)
        with patch.object(
            irs_990_source, "HttpRangeReader", side_effect=lambda url, **kw: io.BytesIO(blob)
        ):
            got = irs_990_source.fetch_filing_xml(self._ref(), session=object())
        assert got is not None and "<TaxYr>2025</TaxYr>" in got

    def test_ordinary_deflate_members_still_read(self):
        """2024's bundles are plain deflate and must not regress."""
        from unittest.mock import patch

        from src.collectors import irs_990_source

        ref = FilingRef("831794093", "202512", "202600939349201205",
                        "2026_TEOS_XML_04A", "990EZ")
        with patch.object(
            irs_990_source, "HttpRangeReader",
            side_effect=lambda url, **kw: io.BytesIO(TEST_BATCH_ZIP),
        ):
            got = irs_990_source.fetch_filing_xml(ref, session=object())
        assert got is not None and "<TaxYr>2025</TaxYr>" in got
