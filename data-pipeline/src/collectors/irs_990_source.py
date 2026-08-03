"""Fetch Form 990 XML from the IRS, the primary source.

ProPublica mirrors IRS e-file XML at /nonprofits/download-xml, and in July
2026 put a Cloudflare managed challenge in front of it: HTTP 403 with
``cf-mitigated: challenge`` and a "Security Check — ProPublica" body. The org
page still serves 200, so only the XML download is affected. Cookies from the
org page carry no clearance, and headless Chromium is fingerprinted and never
clears the interstitial. Passing it would mean defeating an access control the
publisher installed on purpose, so this module goes upstream instead.

The IRS publishes the same filings itself, for bulk use:

  index_YYYY.csv        EIN -> OBJECT_ID, TAX_PERIOD, XML_BATCH_ID
  {XML_BATCH_ID}.zip    the bundle holding {OBJECT_ID}_public.xml

YYYY is the SUBMISSION year, not the tax year -- a return for tax period
202512 appears in index_2026. Callers wanting recent filings must therefore
consult the most recent index years, not the tax years they want.

The bundles are 150-260 MB with ~48,000 members, far too large to download per
filing. They serve ``accept-ranges: bytes``, so ``HttpRangeReader`` gives
``zipfile`` a seekable view over HTTP and only the central directory plus the
wanted member are transferred. Measured against 2026_TEOS_XML_04A: 3.58 MB of
261.9 MB for one filing.

Being upstream, this is never staler than the mirror. For EIN 83-1794093 it
returns TaxYr 2025 where the stored ProPublica copy had 2024.
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

IRS_BASE_URL = "https://apps.irs.gov/pub/epostcard/990/xml"
IRS_INDEX_URL_TEMPLATE = IRS_BASE_URL + "/{year}/index_{year}.csv"

# Columns we require from index_YYYY.csv. RETURN_ID is deliberately not among
# them: the IRS leaves it blank on many rows and those rows are otherwise fine.
_REQUIRED_COLUMNS = ("EIN", "TAX_PERIOD", "OBJECT_ID", "XML_BATCH_ID")


@dataclass(frozen=True)
class FilingRef:
    """Everything needed to locate one filing's XML inside a bundle."""

    ein: str
    tax_period: str
    object_id: str
    batch_id: str
    return_type: str = ""


def zip_member_url(batch_id: str) -> str:
    """URL of the bundle named by an index row's XML_BATCH_ID.

    The batch id leads with its submission year ("2026_TEOS_XML_04A"), which
    is also the directory it lives under.
    """
    year = batch_id.split("_", 1)[0]
    return f"{IRS_BASE_URL}/{year}/{batch_id}.zip"


# How far past the named volume to look. Six is well beyond anything observed
# (2026 batch 05 runs to B) and bounded so a wrong batch id cannot start an
# unbounded walk.
_MAX_VOLUMES = 6


def bundle_candidates(batch_id: str) -> list[str]:
    """The bundles that may hold a filing the index assigns to batch_id.

    XML_BATCH_ID is not a reliable address. When a batch outgrows one zip the
    IRS publishes lettered volumes and keeps naming only the first: on
    2026-07-31, index_2026 assigned 168,344 rows to 2026_TEOS_XML_05A, which
    holds 84,172 members and stops at object_id 202621329349203217.
    2026_TEOS_XML_05B holds the next 84,172, starting at 202621329349203222,
    and appears in no index row at all. Half the batch was unaddressable.

    The trailing letter is also written in whichever case the IRS pleases --
    index_2024 says "05a" where the server has 05A.zip and 302-redirects the
    lowercase to irs.gov/404 -- so it is normalised here.
    """
    prefix, sep, tail = batch_id.rpartition("_")
    if not sep or not tail or not tail[-1].isalpha():
        return [batch_id]
    stem, letter = tail[:-1], tail[-1].upper()
    return [f"{prefix}_{stem}{chr(ord(letter) + i)}" for i in range(_MAX_VOLUMES)]


ZIP_DEFLATED64 = 9


def _read_member(zf: Any, name: str) -> bytes:
    """The member's bytes, including the ones zipfile cannot decompress.

    The oversized batch is packed with Deflate64 (method 9), which Python's
    zipfile refuses: on 2026-07-31 every member of 2026_TEOS_XML_05A/05B and
    2025_TEOS_XML_05B was method 9, against ordinary deflate everywhere else.
    Since that batch carries 168,344 of index_2026's 353,651 rows, nearly half
    the submission year was unreadable, and each of those charities silently
    fell back to whatever older filing happened to be cached.

    Deflate64 members are located from their local header and inflated
    directly; everything else goes through zipfile unchanged.
    """
    import struct
    import zipfile

    info = zf.getinfo(name)
    if info.compress_type != ZIP_DEFLATED64:
        return zf.read(name)

    import binascii

    import inflate64

    fp = zf.fp
    fp.seek(info.header_offset)
    header = fp.read(30)
    if header[:4] != b"PK\x03\x04":
        raise zipfile.BadZipFile(f"no local header for {name}")
    name_len, extra_len = struct.unpack("<HH", header[26:30])

    fp.seek(info.header_offset + 30 + name_len + extra_len)
    data = b""
    while len(data) < info.compress_size:
        chunk = fp.read(info.compress_size - len(data))
        if not chunk:
            break
        data += chunk

    body = inflate64.Inflater().inflate(data)
    if binascii.crc32(body) & 0xFFFFFFFF != info.CRC:
        raise zipfile.BadZipFile(f"CRC mismatch for {name}")
    return body


def _member_named(zf: Any, object_id: str) -> Optional[str]:
    """The archive entry for this filing, however the bundle stores it.

    2025 and 2026 bundles store members flat; 2024 nests them under a
    directory named for the bundle, so an exact-name lookup misses them.
    """
    wanted = f"{object_id}_public.xml"
    for name in zf.namelist():
        if name == wanted or name.endswith("/" + wanted):
            return name
    return None


def build_index_map(lines: Iterable[str]) -> dict[str, list[FilingRef]]:
    """Parse index_YYYY.csv rows into EIN -> filings, newest tax period first.

    Rows missing any required column are skipped rather than raising: these
    files are ~93 MB of third-party CSV and one bad line must not cost us the
    other 400,000.
    """
    by_ein: dict[str, list[FilingRef]] = {}

    for row in csv.DictReader(lines):
        try:
            if not all(row.get(c) for c in _REQUIRED_COLUMNS):
                continue
            ref = FilingRef(
                ein=row["EIN"].strip(),
                tax_period=row["TAX_PERIOD"].strip(),
                object_id=row["OBJECT_ID"].strip(),
                batch_id=row["XML_BATCH_ID"].strip(),
                return_type=(row.get("RETURN_TYPE") or "").strip(),
            )
        except (AttributeError, TypeError):
            continue
        by_ein.setdefault(ref.ein, []).append(ref)

    for refs in by_ein.values():
        refs.sort(key=lambda r: r.tax_period, reverse=True)
    return by_ein


class HttpRangeReader(io.RawIOBase):
    """A seekable, read-only file over HTTP range requests.

    Exists so ``zipfile`` can open a 260 MB remote bundle and pull one member
    without transferring the rest. Only the methods zipfile actually uses are
    implemented.
    """

    def __init__(self, url: str, session: Any = None, timeout: int = 120):
        self.url = url
        self.timeout = timeout
        self._pos = 0
        if session is None:
            import requests

            session = requests.Session()
        self._session = session
        head = self._session.head(url, timeout=self.timeout, allow_redirects=True)
        # An absent volume 302s to irs.gov/404, which has a content-length like
        # any other page. Without this the reader would hand zipfile an HTML
        # error page and the caller would see "File is not a zip file" -- a
        # wrong address reported as a corrupt archive.
        status = getattr(head, "status_code", 200)
        if status >= 400:
            raise OSError(f"HTTP {status} for {url}")
        try:
            self.size = int(head.headers["content-length"])
        except (KeyError, TypeError, ValueError) as e:
            raise OSError(f"No content-length for {url}; cannot range-read") from e

    # -- io.RawIOBase contract -------------------------------------------
    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            self._pos = offset
        elif whence == io.SEEK_CUR:
            self._pos += offset
        elif whence == io.SEEK_END:
            self._pos = self.size + offset
        else:
            raise ValueError(f"invalid whence: {whence}")
        self._pos = max(0, min(self._pos, self.size))
        return self._pos

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = self.size - self._pos
        if size == 0 or self._pos >= self.size:
            return b""
        end = min(self._pos + size - 1, self.size - 1)
        resp = self._session.get(
            self.url,
            headers={"Range": f"bytes={self._pos}-{end}"},
            timeout=self.timeout,
        )
        data = resp.content
        self._pos += len(data)
        return data

    def readinto(self, b) -> int:  # pragma: no cover - exercised via zipfile
        data = self.read(len(b))
        b[: len(data)] = data
        return len(data)


def fetch_filing_xml(ref: FilingRef, session: Any = None) -> Optional[str]:
    """Pull one filing's XML out of its IRS bundle.

    Returns None (rather than raising) when the bundle or member is missing,
    so a single unavailable filing degrades that charity's grants data instead
    of failing the run.
    """
    import zipfile

    for batch_id in bundle_candidates(ref.batch_id):
        url = zip_member_url(batch_id)
        try:
            zf = zipfile.ZipFile(HttpRangeReader(url, session=session))
        except (OSError, zipfile.BadZipFile, NotImplementedError) as e:
            # Volumes are contiguous, so the first one that is not published
            # ends the chain; probing past it costs a central directory read
            # per absent bundle and can find nothing.
            #
            # NotImplementedError is zipfile's "That compression method is not
            # supported" -- some IRS bundles carry members compressed outside
            # the set it handles. Without it here the error escaped this
            # function's contract, failed form990_grants as a required source,
            # and aborted the entire crawl for the charity rather than costing
            # it its grants data.
            logger.warning("Could not open IRS bundle %s: %s", url, e)
            return None

        member = _member_named(zf, ref.object_id)
        if member is None:
            continue
        try:
            return _read_member(zf, member).decode("utf-8", "replace")
        except (KeyError, OSError, zipfile.BadZipFile, NotImplementedError) as e:
            logger.warning("Could not read %s from %s: %s", member, url, e)
            return None

    logger.warning(
        "No volume of IRS batch %s holds %s", ref.batch_id, ref.object_id
    )
    return None
