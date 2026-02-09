"""
Text cleaner for extracting main content from HTML.

This module uses Trafilatura (primary) with readability-lxml (fallback)
to extract clean, LLM-ready text from web pages.
"""


class TextCleaner:
    """
    Wrapper for Trafilatura text extraction with fallback.

    Trafilatura provides:
    - Highest F1 score (0.937) and precision (0.978)
    - Boilerplate removal
    - Markdown output for LLM
    - Table preservation

    Fallback to readability-lxml if Trafilatura returns empty.
    """

    def extract(self, html: str, favor_precision: bool = True) -> str | None:
        """
        Extract main content from HTML using Trafilatura.

        Args:
            html: HTML content
            favor_precision: Whether to favor precision over recall

        Returns:
            Extracted text, or None if extraction failed
        """
        import trafilatura

        try:
            text = trafilatura.extract(
                html,
                include_tables=True,  # Impact metrics often in tables
                output_format="txt",  # Plain text for now
                favor_precision=favor_precision,
            )
            return text
        except Exception:
            return None

    def clean_for_llm(self, html: str, favor_precision: bool = True) -> str | None:
        """
        Extract and clean text in markdown format for LLM processing.

        Args:
            html: HTML content
            favor_precision: Whether to favor precision over recall

        Returns:
            Clean markdown text, or None if extraction failed
        """
        import trafilatura

        try:
            # Try Trafilatura first with markdown output
            text = trafilatura.extract(
                html,
                include_tables=True,
                output_format="markdown",
                favor_precision=favor_precision,
            )

            # If Trafilatura returns empty or very short, try readability-lxml fallback
            if not text or len(text) < 100:
                return self._fallback_extract(html)

            return text
        except Exception:
            # Fallback on any error
            return self._fallback_extract(html)

    def _fallback_extract(self, html: str) -> str | None:
        """
        Fallback extraction using readability-lxml.

        Args:
            html: HTML content

        Returns:
            Extracted text, or None if extraction failed
        """
        try:
            from readability import Document

            doc = Document(html)
            summary_html = doc.summary()

            # Convert HTML to plain text (basic approach)
            import re

            # Remove HTML tags
            text = re.sub(r"<[^>]+>", " ", summary_html)
            # Clean up whitespace
            text = re.sub(r"\s+", " ", text).strip()

            return text if len(text) >= 100 else None
        except Exception:
            return None
