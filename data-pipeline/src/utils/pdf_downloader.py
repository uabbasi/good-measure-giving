"""
PDF document discovery and download utility.

This module provides functionality to:
- Identify PDF links on charity web pages
- Classify document types (annual reports, financials, Form 990s, etc.)
- Download and store PDFs with metadata
- Extract fiscal year from document context
- Calculate file hashes for deduplication
"""

import hashlib
import re
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests

from ..validators.charity_profile import PDFDocumentReference

# Local lock for thread-safe operations
_global_conn_lock = RLock()

# Try to import curl_cffi for bot protection bypass
try:
    from curl_cffi import requests as curl_requests

    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False


class PDFDownloader:
    """
    Discover and download PDF documents from charity websites.

    Handles:
    - PDF link identification from HTML
    - Document type classification
    - File download and storage
    - Metadata extraction (fiscal year, etc.)
    - Deduplication via file hashing
    """

    # Document type patterns (anchor text, URL path, page context)
    # Aligned with V2 dimensions: Trust, Evidence, Effectiveness, Fit
    DOCUMENT_PATTERNS = {
        # TRUST dimension - verification, financial transparency
        "form_990": [
            r"form\s*990",
            r"990\s+form",
            r"990[-_]?pf",
            r"tax\s+form",
            r"irs\s+form",
            r"tax\s+return",
            r"exempt\s+organization",
        ],
        "audit_report": [
            r"audit(?:ed)?\s+(?:financial\s+)?report",
            r"independent\s+audit",
            r"auditor['']?s?\s+report",
            r"financial\s+audit",
            r"cpa\s+report",
        ],
        "financial_statement": [
            r"financial\s+statement",
            r"financials?",
            r"audited?\s+statement",
            r"statement\s+of\s+financial",
            r"/financial",
            r"consolidated\s+financial",
        ],
        # EVIDENCE dimension - outcomes, research, theory of change
        "impact_report": [
            r"impact\s+report",
            r"outcome[s]?\s+report",
            r"results?\s+report",
            r"progress\s+report",
            r"/impact",
            r"metrics\s+report",
        ],
        "evaluation_report": [
            r"evaluation\s+report",
            r"program\s+evaluation",
            r"external\s+evaluation",
            r"third[- ]party\s+evaluation",
            r"monitoring\s+(?:and\s+)?evaluation",
            r"m&e\s+report",
        ],
        "theory_of_change": [
            r"theory\s+of\s+change",
            r"logic\s+model",
            r"strategic\s+framework",
            r"program\s+theory",
        ],
        # EFFECTIVENESS dimension - programs, operations
        "annual_report": [
            r"annual\s+report",
            r"yearly\s+report",
            r"annual[-_]report",
            r"/annual",
            r"year\s+in\s+review",
        ],
        "program_report": [
            r"program\s+report",
            r"project\s+report",
            r"activity\s+report",
            r"operational\s+report",
        ],
        # FIT dimension - strategy, governance
        "strategic_plan": [
            r"strategic\s+plan",
            r"strategy\s+document",
            r"multi[- ]year\s+plan",
            r"organizational\s+strategy",
        ],
        "governance": [
            r"governance\s+report",
            r"board\s+report",
            r"transparency\s+report",
            r"accountability\s+report",
        ],
    }

    # Conservative exclusion patterns for Layer 1 filtering
    # Only exclude clearly irrelevant documents (confidential, privileged, third-party agreements)
    # Legal case documents where the org is a party are allowed through for validation in Layer 3
    EXCLUDED_DOCUMENT_PATTERNS = {
        "confidential": [
            r"\bconfidential\b",
            r"\bprivileged\b",
            r"attorney[.\s-]client",
        ],
        "third_party_agreements": [
            r"settlement\s+agreement",
            r"\bnda\b",
            r"non[.\s-]disclosure",
            r"\bcontract\b",
        ],
    }

    # Fiscal year patterns
    FISCAL_YEAR_PATTERNS = [
        r"(?:FY|fiscal\s+year)\s*(\d{4})",
        r"(\d{4})\s*annual\s+report",
        r"(\d{4})\s*financial",
        r"(\d{4})[-_](\d{4})",  # 2022-2023
        r"year\s+ending?\s+.*?(\d{4})",
    ]

    def __init__(self, storage_dir: Path, logger=None):
        """
        Initialize PDF downloader.

        Args:
            storage_dir: Base directory for PDF storage (e.g., shared/pdfs/)
            logger: Logger instance
        """
        self.storage_dir = Path(storage_dir)
        self.logger = logger

        # Create storage directory if it doesn't exist
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def identify_pdfs(self, html: str, base_url: str) -> List[dict]:
        """
        Identify PDF links on a web page (T067).

        Finds PDFs by:
        - Links with .pdf extension
        - Links with PDF-related anchor text
        - Links with PDF MIME type hints

        Args:
            html: HTML content of the page
            base_url: Base URL for resolving relative links

        Returns:
            List of dicts with {url, anchor_text, context}
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        pdf_links = []

        # Find all links
        for link in soup.find_all("a", href=True):
            href = link["href"]
            anchor_text = link.get_text(strip=True)

            # Resolve relative URLs
            absolute_url = urljoin(base_url, href)

            # Check if it's a PDF
            is_pdf = False

            # Method 1: .pdf extension in URL
            if href.lower().endswith(".pdf") or ".pdf?" in href.lower():
                is_pdf = True

            # Method 2: PDF mentioned in anchor text
            if re.search(r"\bpdf\b", anchor_text, re.IGNORECASE):
                is_pdf = True

            # Method 3: type="application/pdf" attribute
            if link.get("type", "").lower() == "application/pdf":
                is_pdf = True

            if is_pdf:
                # Get surrounding context (parent element text)
                context = ""
                if link.parent:
                    context = link.parent.get_text(strip=True)[:200]

                pdf_links.append({"url": absolute_url, "anchor_text": anchor_text, "context": context})

        if self.logger and pdf_links:
            self.logger.debug(f"Found {len(pdf_links)} PDF links on page")

        return pdf_links

    def should_exclude_document(self, pdf_info: dict) -> tuple[bool, str | None]:
        """
        Check if document should be excluded (Layer 1 filtering).

        Conservative exclusion - only filters truly irrelevant documents:
        - Confidential/privileged documents
        - Settlement agreements, NDAs, contracts

        Legal case documents are allowed through for validation in Layer 3.

        Args:
            pdf_info: Dict with url, anchor_text, context

        Returns:
            Tuple of (should_exclude, reason)
        """
        # Combine all text for matching
        combined_text = f"{pdf_info.get('anchor_text', '')} {pdf_info.get('context', '')} {pdf_info['url']}".lower()

        for exclusion_type, patterns in self.EXCLUDED_DOCUMENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    if self.logger:
                        self.logger.info(
                            f"Excluding PDF (type={exclusion_type}, pattern={pattern}): {pdf_info['url'][:50]}..."
                        )
                    return True, f"Excluded: {exclusion_type}"

        return False, None

    def classify_document_type(self, pdf_info: dict) -> str:
        """
        Classify PDF document type from anchor text and context (T068).

        Args:
            pdf_info: Dict with url, anchor_text, context

        Returns:
            Document type: annual_report, financial_statement, form_990, impact_report, or other
        """
        # Combine anchor text and context for matching
        text_to_match = f"{pdf_info.get('anchor_text', '')} {pdf_info.get('context', '')}".lower()
        url_path = urlparse(pdf_info["url"]).path.lower()

        # Check each document type pattern
        for doc_type, patterns in self.DOCUMENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_to_match, re.IGNORECASE) or re.search(pattern, url_path, re.IGNORECASE):
                    return doc_type

        return "other"

    def extract_fiscal_year(self, pdf_info: dict) -> Optional[int]:
        """
        Extract fiscal year from PDF anchor text or context (T071).

        Args:
            pdf_info: Dict with url, anchor_text, context

        Returns:
            Fiscal year as integer, or None if not found
        """
        text_to_search = f"{pdf_info.get('anchor_text', '')} {pdf_info.get('context', '')}"

        for pattern in self.FISCAL_YEAR_PATTERNS:
            match = re.search(pattern, text_to_search, re.IGNORECASE)
            if match:
                # Get the last matched group (handles both single year and year ranges)
                year_str = match.group(match.lastindex if match.lastindex else 1)
                try:
                    year = int(year_str)
                    # Validate year is reasonable (1990-2100)
                    if 1990 <= year <= 2100:
                        return year
                except ValueError:
                    continue

        return None

    def download_pdf(self, url: str, output_path: Path, timeout: int = 30) -> Tuple[bool, Optional[str]]:
        """
        Download PDF file from URL (T069).

        Args:
            url: URL of PDF to download
            output_path: Path where PDF should be saved
            timeout: Request timeout in seconds

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Create parent directories
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Try regular requests first
            response = requests.get(url, timeout=timeout, stream=True)

            # If we get 403, try curl_cffi with browser impersonation
            if response.status_code == 403 and HAS_CURL_CFFI:
                if self.logger:
                    self.logger.debug(f"PDF download got 403, retrying with curl_cffi: {url}")

                # Try safari15_5 profile (works best for bot-protected sites)
                # Enable stream=True for large PDFs
                response = curl_requests.get(url, timeout=timeout, impersonate="safari15_5", stream=True)

            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"

            # Check content type
            content_type = response.headers.get("content-type", "").lower()
            if "pdf" not in content_type and "application/octet-stream" not in content_type:
                # Some servers don't set content-type correctly, so we'll allow it
                if self.logger:
                    self.logger.warning(f"PDF has unexpected content-type: {content_type}")

            # Write file - handle both requests and curl_cffi responses
            with open(output_path, "wb") as f:
                if hasattr(response, "iter_content"):
                    # Both requests and curl_cffi support iter_content when stream=True
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                else:
                    # Fallback to full content if not streaming
                    f.write(response.content)

            # Validate the downloaded file
            file_size = output_path.stat().st_size

            # Check for empty file
            if file_size == 0:
                output_path.unlink(missing_ok=True)
                return False, "Downloaded file is empty (0 bytes)"

            # Check for PDF magic bytes (%PDF)
            with open(output_path, "rb") as f:
                magic_bytes = f.read(8)

            if not magic_bytes.startswith(b"%PDF"):
                # Check if it's HTML (common error page response)
                if (
                    magic_bytes.startswith(b"<!DOCTYPE")
                    or magic_bytes.startswith(b"<html")
                    or magic_bytes.startswith(b"<HTML")
                ):
                    output_path.unlink(missing_ok=True)
                    return False, "Server returned HTML instead of PDF (likely error page)"
                # Allow other binary formats that might be PDFs with unusual headers
                if self.logger:
                    self.logger.warning(f"PDF missing magic bytes, may be corrupted: {output_path.name}")

            if self.logger:
                self.logger.debug(f"Downloaded PDF: {output_path.name} ({file_size} bytes)")

            return True, None

        except requests.Timeout:
            return False, f"Download timeout after {timeout}s"
        except requests.RequestException as e:
            return False, f"Download failed: {str(e)}"
        except IOError as e:
            return False, f"File write failed: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

    def calculate_file_hash(self, file_path: Path) -> str:
        """
        Calculate SHA256 hash of file for deduplication (T072).

        Args:
            file_path: Path to file

        Returns:
            SHA256 hash as hexadecimal string
        """
        sha256_hash = hashlib.sha256()

        with open(file_path, "rb") as f:
            # Read in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        return sha256_hash.hexdigest()

    def create_pdf_reference(
        self,
        charity_id: int,
        pdf_info: dict,
        file_path: Optional[Path] = None,
        file_hash: Optional[str] = None,
        page_url: str = "",
    ) -> PDFDocumentReference:
        """
        Create PDFDocumentReference instance with metadata (T073).

        Args:
            charity_id: Database ID of charity
            pdf_info: Dict with url, anchor_text, context
            file_path: Path where PDF was saved (if downloaded)
            file_hash: SHA256 hash of file (if downloaded)
            page_url: URL of the page where PDF link was found

        Returns:
            PDFDocumentReference Pydantic model
        """
        doc_type = self.classify_document_type(pdf_info)
        fiscal_year = self.extract_fiscal_year(pdf_info)

        # Get file metadata if downloaded
        file_size = None
        page_count = None
        if file_path and file_path.exists():
            file_size = file_path.stat().st_size

        return PDFDocumentReference(
            charity_id=charity_id,
            document_type=doc_type,
            fiscal_year=fiscal_year,
            title=pdf_info.get("anchor_text", "Untitled Document"),
            source_url=pdf_info["url"],
            source_page_url=page_url,
            anchor_text=pdf_info.get("anchor_text"),
            file_path=str(file_path) if file_path else None,
            file_size_bytes=file_size,
            file_hash=file_hash,
            page_count=page_count,
            download_status="completed" if file_path and file_path.exists() else "pending",
        )

    def get_storage_path(
        self, charity_id: int, document_type: str, fiscal_year: Optional[int] = None, url: str = ""
    ) -> Path:
        """
        Get storage path for PDF file (T070).

        Format: shared/pdfs/{charity_id}/{fiscal_year}_{document_type}.pdf
        or:     shared/pdfs/{charity_id}/{document_type}_{hash_suffix}.pdf

        Args:
            charity_id: Database ID of charity
            document_type: Type of document
            fiscal_year: Fiscal year (if known)
            url: PDF URL (used to generate unique suffix if no fiscal year)

        Returns:
            Path object for PDF storage
        """
        charity_dir = self.storage_dir / str(charity_id)
        charity_dir.mkdir(parents=True, exist_ok=True)

        # C-008: Sanitize document_type to prevent path traversal
        # Remove any path separators or parent directory references
        safe_doc_type = re.sub(r'[/\\]', '_', document_type)
        safe_doc_type = safe_doc_type.replace('..', '_')
        safe_doc_type = re.sub(r'[^\w\-]', '_', safe_doc_type)  # Only allow word chars, hyphens

        if fiscal_year:
            # Also sanitize fiscal_year in case it comes from untrusted source
            safe_fy = re.sub(r'[^\d]', '', str(fiscal_year))[:4]  # Only digits, max 4 chars
            filename = f"{safe_fy}_{safe_doc_type}.pdf"
        else:
            # Use hash of URL as unique suffix
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            filename = f"{safe_doc_type}_{url_hash}.pdf"

        return charity_dir / filename

    # =========================================================================
    # Database persistence methods (for pdf_documents table)
    # =========================================================================

    def persist_pdf_to_db(
        self,
        db_conn,
        charity_id: int,
        pdf_info: dict,
        file_path: Optional[Path] = None,
        file_hash: Optional[str] = None,
        page_url: str = "",
        download_status: str = "pending",
        error_message: Optional[str] = None,
    ) -> Optional[int]:
        """
        Persist PDF metadata to pdf_documents table.

        Args:
            db_conn: SQLite database connection
            charity_id: Database ID of charity
            pdf_info: Dict with url, anchor_text, context
            file_path: Path where PDF was saved (if downloaded)
            file_hash: SHA256 hash of file (if downloaded)
            page_url: URL of the page where PDF link was found
            download_status: Status of download (pending, downloading, completed, failed)
            error_message: Error message if download failed

        Returns:
            Database row ID of inserted/updated record, or None on failure
        """
        doc_type = self.classify_document_type(pdf_info)
        fiscal_year = self.extract_fiscal_year(pdf_info)

        # Get file metadata if downloaded
        file_size = None
        if file_path and file_path.exists():
            file_size = file_path.stat().st_size

        # Use lock for thread-safe database writes
        with _global_conn_lock:
            try:
                cursor = db_conn.cursor()

                # Check if PDF with same hash already exists (deduplication)
                if file_hash:
                    cursor.execute(
                        """
                        SELECT id FROM pdf_documents
                        WHERE charity_id = ? AND file_hash = ?
                    """,
                        (charity_id, file_hash),
                    )
                    existing = cursor.fetchone()
                    if existing:
                        if self.logger:
                            self.logger.debug(f"PDF already exists in DB (dedup by hash): {pdf_info['url']}")
                        return existing[0]

                # Get next ID
                result = cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM pdf_documents").fetchone()
                next_id = result[0]

                # Insert new record (deduplication check above handles existing records)
                cursor.execute(
                    """
                    INSERT INTO pdf_documents (
                        id,
                        charity_id,
                        document_type,
                        fiscal_year,
                        title,
                        source_url,
                        source_page_url,
                        anchor_text,
                        file_path,
                        file_size_bytes,
                        file_hash,
                        download_status,
                        download_date,
                        extraction_status,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        next_id,
                        charity_id,
                        doc_type,
                        fiscal_year,
                        pdf_info.get("anchor_text", "Untitled Document")[:255],  # Limit title length
                        pdf_info["url"],
                        page_url,
                        pdf_info.get("anchor_text"),
                        str(file_path) if file_path else None,
                        file_size,
                        file_hash,
                        download_status,
                        datetime.now().isoformat() if download_status == "completed" else None,
                        "pending",  # extraction_status always starts as pending
                        datetime.now().isoformat(),  # created_at
                    ),
                )

                db_conn.commit()
                row_id = next_id

                if self.logger:
                    self.logger.debug(f"Persisted PDF to DB: {doc_type} ({pdf_info['url'][:50]}...)")

                return row_id

            except Exception as e:
                if self.logger:
                    self.logger.error(f"Failed to persist PDF to DB: {e}")
                return None

    def update_pdf_extraction_status(
        self,
        db_conn,
        pdf_id: int,
        extraction_status: str,
        extracted_data: Optional[dict] = None,
        page_count: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Update extraction status for a PDF document.

        Args:
            db_conn: SQLite database connection
            pdf_id: Database ID of PDF document
            extraction_status: New status (pending, in_progress, completed, failed)
            extracted_data: JSON-serializable dict of extracted data
            page_count: Number of pages in PDF
            error_message: Error message if extraction failed

        Returns:
            True on success, False on failure
        """
        import json

        # Use lock for thread-safe database writes
        with _global_conn_lock:
            try:
                cursor = db_conn.cursor()

                cursor.execute(
                    """
                    UPDATE pdf_documents
                    SET extraction_status = ?,
                        extracted_data = ?,
                        page_count = ?,
                        error_message = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """,
                    (
                        extraction_status,
                        json.dumps(extracted_data) if extracted_data else None,
                        page_count,
                        error_message,
                        pdf_id,
                    ),
                )

                db_conn.commit()

                if self.logger:
                    self.logger.debug(f"Updated PDF extraction status: {pdf_id} -> {extraction_status}")

                return True

            except Exception as e:
                if self.logger:
                    self.logger.error(f"Failed to update PDF extraction status: {e}")
                return False

    def get_pending_pdfs(self, db_conn, charity_id: Optional[int] = None, status_type: str = "download") -> List[dict]:
        """
        Get PDFs with pending download or extraction status.

        Args:
            db_conn: SQLite database connection
            charity_id: Optional charity ID to filter by
            status_type: "download" or "extraction"

        Returns:
            List of PDF records as dicts
        """
        try:
            cursor = db_conn.cursor()

            status_column = "download_status" if status_type == "download" else "extraction_status"

            if charity_id:
                cursor.execute(
                    f"""
                    SELECT * FROM pdf_documents
                    WHERE charity_id = ? AND {status_column} = 'pending'
                    ORDER BY fiscal_year DESC NULLS LAST
                """,
                    (charity_id,),
                )
            else:
                cursor.execute(f"""
                    SELECT * FROM pdf_documents
                    WHERE {status_column} = 'pending'
                    ORDER BY charity_id, fiscal_year DESC NULLS LAST
                """)

            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]

            return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to get pending PDFs: {e}")
            return []

    def is_pdf_already_downloaded(self, db_conn, charity_id: int, source_url: str) -> bool:
        """
        Check if a PDF has already been downloaded for this charity.

        Args:
            db_conn: SQLite database connection
            charity_id: Charity ID
            source_url: Source URL of the PDF

        Returns:
            True if PDF already exists and is downloaded
        """
        try:
            cursor = db_conn.cursor()
            cursor.execute(
                """
                SELECT id FROM pdf_documents
                WHERE charity_id = ? AND source_url = ? AND download_status = 'completed'
            """,
                (charity_id, source_url),
            )
            return cursor.fetchone() is not None
        except Exception:
            return False

    def download_and_persist(
        self, db_conn, charity_id: int, pdf_info: dict, page_url: str = ""
    ) -> Tuple[bool, Optional[int]]:
        """
        Download PDF and persist to database in one operation.

        This is the main method to use for downloading PDFs.

        Args:
            db_conn: SQLite database connection
            charity_id: Database ID of charity
            pdf_info: Dict with url, anchor_text, context
            page_url: URL of the page where PDF link was found

        Returns:
            Tuple of (success, pdf_db_id)
        """
        # Check if already downloaded
        if self.is_pdf_already_downloaded(db_conn, charity_id, pdf_info["url"]):
            if self.logger:
                self.logger.debug(f"PDF already downloaded, skipping: {pdf_info['url'][:50]}...")
            return True, None

        # Classify and get storage path
        doc_type = self.classify_document_type(pdf_info)
        fiscal_year = self.extract_fiscal_year(pdf_info)
        file_path = self.get_storage_path(charity_id, doc_type, fiscal_year, pdf_info["url"])

        # Persist as "downloading" status first
        pdf_id = self.persist_pdf_to_db(
            db_conn, charity_id, pdf_info, None, None, page_url, download_status="downloading"
        )

        # Download the file
        success, error = self.download_pdf(pdf_info["url"], file_path)

        if success:
            # Calculate hash and update record
            file_hash = self.calculate_file_hash(file_path)
            self.persist_pdf_to_db(
                db_conn, charity_id, pdf_info, file_path, file_hash, page_url, download_status="completed"
            )
            return True, pdf_id
        else:
            # Update with failure status
            self.persist_pdf_to_db(
                db_conn, charity_id, pdf_info, None, None, page_url, download_status="failed", error_message=error
            )
            return False, pdf_id
