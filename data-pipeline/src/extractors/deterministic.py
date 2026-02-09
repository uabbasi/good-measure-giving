"""
Deterministic extractor for regex-based field extraction.

This module extracts factual data using pattern matching:
- EIN (Employer Identification Number)
- Contact information (email, phone, address)
- Social media URLs
- Donation URLs
"""

import re
from typing import Any

from ..utils.ein_utils import extract_ein_from_text


class DeterministicExtractor:
    """
    Regex-based extractor for factual charity data.

    Provides high-confidence extraction without LLM calls for:
    - EIN: XX-XXXXXXX or XXXXXXXXX format
    - Email: Standard email patterns
    - Phone: US and international formats
    - Social media: Platform-specific URL patterns
    - Donate URLs: Common donation page patterns
    """

    # EIN patterns
    EIN_PATTERN_HYPHENATED = r"\b\d{2}-\d{7}\b"
    EIN_PATTERN_PLAIN = r"\b\d{9}\b"

    # Email pattern (simplified)
    EMAIL_PATTERN = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"

    # Phone patterns (US and international)
    PHONE_PATTERNS = [
        r"\+?1?[-.\s]?\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})",  # US: (123) 456-7890
        r"\+\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}",  # International
    ]

    # Social media platforms
    SOCIAL_MEDIA_PATTERNS = {
        "facebook": r"(?:https?://)?(?:www\.)?facebook\.com/[\w.-]+",
        "twitter": r"(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/[\w.-]+",
        "instagram": r"(?:https?://)?(?:www\.)?instagram\.com/[\w.-]+",
        "linkedin": r"(?:https?://)?(?:www\.)?linkedin\.com/(?:company|in)/[\w.-]+",
        "youtube": r"(?:https?://)?(?:www\.)?youtube\.com/(?:c|channel|user)/[\w.-]+",
    }

    # Donate URL patterns (path-based)
    DONATE_PATH_PATTERNS = [
        r"/donate",
        r"/donation",
        r"/give",
        r"/support",
        r"/contribute",
        r"/giving",
    ]

    def extract_ein(self, text: str) -> str | None:
        """
        Extract EIN from text using regex patterns.

        Searches for both hyphenated (XX-XXXXXXX) and plain (XXXXXXXXX) formats.
        Uses centralized EIN utilities for consistent normalization.

        Args:
            text: Text to search for EIN

        Returns:
            Normalized EIN in XX-XXXXXXX format, or None if not found

        Examples:
            >>> extractor = DeterministicExtractor()
            >>> extractor.extract_ein("Our EIN is 95-4453134")
            '95-4453134'
            >>> extractor.extract_ein("Tax ID: 954453134")
            '95-4453134'
        """
        # Use centralized EIN extraction with normalization
        return extract_ein_from_text(text)

    def extract_contact_info(self, html: str) -> dict[str, Any]:
        """
        Extract contact information (email, phone, address) from HTML.

        Args:
            html: HTML content to search

        Returns:
            Dict with keys: email, phone (may be None if not found)
        """
        # Extract email - filter out image filenames and prioritize org contacts
        email = None
        email_matches = re.findall(self.EMAIL_PATTERN, html, re.IGNORECASE)
        # Filter out image filenames
        valid_emails = [
            m for m in email_matches
            if not any(ext in m.lower() for ext in [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"])
        ]
        # E-002: Prioritize organizational contact emails over personal ones
        org_prefixes = ("info@", "contact@", "support@", "donate@", "help@", "zakat@", "general@")
        org_emails = [e for e in valid_emails if e.lower().startswith(org_prefixes)]
        email = org_emails[0] if org_emails else (valid_emails[0] if valid_emails else None)

        # Extract phone (try multiple patterns)
        phone = None
        for pattern in self.PHONE_PATTERNS:
            phone_match = re.search(pattern, html)
            if phone_match:
                phone = phone_match.group(0)
                break

        return {"email": email, "phone": phone}

    def extract_social_media(self, html: str) -> dict[str, str]:
        """
        Extract social media URLs using platform-specific patterns.

        Args:
            html: HTML content to search

        Returns:
            Dict mapping platform name to URL

        Example:
            {
                "facebook": "https://facebook.com/charity",
                "twitter": "https://twitter.com/charity",
                "instagram": "https://instagram.com/charity"
            }
        """
        social_urls = {}

        for platform, pattern in self.SOCIAL_MEDIA_PATTERNS.items():
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                url = match.group(0)
                # Ensure https://
                if not url.startswith("http"):
                    url = f"https://{url}"
                social_urls[platform] = url

        return social_urls

    def extract_donate_urls(self, html: str, base_url: str) -> list[str]:
        """
        Extract donation page URLs using path patterns.

        Searches for common donation paths like /donate, /give, /support.

        Args:
            html: HTML content to search
            base_url: Base URL for resolving relative paths

        Returns:
            List of full donation URLs
        """
        from urllib.parse import urljoin

        donate_urls = []

        # Find all <a href="..."> links
        link_pattern = r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>'
        links = re.findall(link_pattern, html, re.IGNORECASE)

        for link in links:
            # Check if link matches any donate pattern
            for pattern in self.DONATE_PATH_PATTERNS:
                if re.search(pattern, link, re.IGNORECASE):
                    # Resolve relative URL
                    full_url = urljoin(base_url, link)
                    if full_url not in donate_urls:
                        donate_urls.append(full_url)
                    break

        return donate_urls
