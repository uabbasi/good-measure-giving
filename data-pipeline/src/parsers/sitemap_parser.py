"""
Sitemap parser for intelligent URL discovery.

This module parses sitemap.xml files and extracts URLs for prioritized crawling.
Uses requests + lxml (no scrapy dependency).
"""

import gzip
from typing import List
from xml.etree import ElementTree as ET

import requests


class SitemapParser:
    """
    Parser for sitemap.xml files.

    Handles:
    - Single sitemaps
    - Sitemap indexes (nested sitemaps)
    - Gzipped sitemaps (.xml.gz)
    - Large sitemaps with pagination
    """

    # XML namespaces used in sitemaps
    NAMESPACES = {
        "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
        "": "http://www.sitemaps.org/schemas/sitemap/0.9",  # Default namespace
    }

    def __init__(self, timeout: int = 30):
        """
        Initialize parser.

        Args:
            timeout: Request timeout in seconds (default 30)
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; CharityBot/1.0; +https://amal.charity)"
        })

    def _fetch_xml(self, url: str) -> ET.Element | None:
        """
        Fetch and parse XML from URL, handling gzip compression.

        Returns:
            ElementTree root element, or None on error
        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            content = response.content

            # Handle gzipped content
            if url.endswith(".gz") or response.headers.get("Content-Encoding") == "gzip":
                try:
                    content = gzip.decompress(content)
                except gzip.BadGzipFile:
                    pass  # Not actually gzipped, use raw content

            # Parse XML
            return ET.fromstring(content)

        except (requests.RequestException, ET.ParseError):
            return None

    def _extract_urls(self, root: ET.Element) -> List[str]:
        """Extract URL locations from sitemap XML."""
        urls = []

        # Try with namespace
        for loc in root.findall(".//sm:loc", self.NAMESPACES):
            if loc.text:
                urls.append(loc.text.strip())

        # Try without namespace (some sitemaps don't use it)
        if not urls:
            for loc in root.findall(".//loc"):
                if loc.text:
                    urls.append(loc.text.strip())

        return urls

    def _is_sitemap_index(self, root: ET.Element) -> bool:
        """Check if this is a sitemap index (contains other sitemaps)."""
        # Sitemap indexes use <sitemapindex> as root or contain <sitemap> elements
        if root.tag.endswith("sitemapindex"):
            return True

        # Check for sitemap elements
        sitemaps = root.findall(".//sm:sitemap", self.NAMESPACES)
        if not sitemaps:
            sitemaps = root.findall(".//sitemap")

        return len(sitemaps) > 0

    def _get_nested_sitemap_urls(self, root: ET.Element) -> List[str]:
        """Extract sitemap URLs from a sitemap index."""
        sitemap_urls = []

        # Try with namespace
        for sitemap in root.findall(".//sm:sitemap", self.NAMESPACES):
            loc = sitemap.find("sm:loc", self.NAMESPACES)
            if loc is not None and loc.text:
                sitemap_urls.append(loc.text.strip())

        # Try without namespace
        if not sitemap_urls:
            for sitemap in root.findall(".//sitemap"):
                loc = sitemap.find("loc")
                if loc is not None and loc.text:
                    sitemap_urls.append(loc.text.strip())

        return sitemap_urls

    def fetch_sitemap(self, url: str, recursive: bool = True) -> List[str]:
        """
        Fetch and parse sitemap.xml to extract all URLs.

        Args:
            url: Sitemap URL (e.g., https://charity.org/sitemap.xml)
            recursive: Whether to recursively fetch sitemap indexes (default True)
                      Set to False for large sites to check structure first

        Returns:
            List of URLs found in sitemap

        Example:
            >>> parser = SitemapParser()
            >>> urls = parser.fetch_sitemap('https://charity.org/sitemap.xml')
            >>> print(f'Found {len(urls)} URLs')
        """
        root = self._fetch_xml(url)
        if root is None:
            return []

        # Check if this is a sitemap index
        if self._is_sitemap_index(root):
            if recursive:
                # Fetch all nested sitemaps
                all_urls = []
                nested_urls = self._get_nested_sitemap_urls(root)
                for nested_url in nested_urls:
                    nested_root = self._fetch_xml(nested_url)
                    if nested_root is not None:
                        all_urls.extend(self._extract_urls(nested_root))
                return all_urls
            else:
                # Return nested sitemap URLs themselves
                return self._get_nested_sitemap_urls(root)
        else:
            # Regular sitemap - extract URLs
            return self._extract_urls(root)

    def parse_sitemap_index(self, url: str) -> List[str]:
        """
        Parse sitemap index to get list of sitemap URLs.

        Sitemap indexes contain references to other sitemaps rather than actual page URLs.

        Args:
            url: Sitemap index URL

        Returns:
            List of sitemap URLs (not page URLs)

        Example:
            >>> parser = SitemapParser()
            >>> sitemaps = parser.parse_sitemap_index('https://charity.org/sitemap_index.xml')
            >>> for sitemap_url in sitemaps:
            ...     urls = parser.fetch_sitemap(sitemap_url)
        """
        root = self._fetch_xml(url)
        if root is None:
            return []

        # If it's a sitemap index, return nested sitemap URLs
        if self._is_sitemap_index(root):
            return self._get_nested_sitemap_urls(root)

        # If it's a regular sitemap, check for URLs that look like sitemaps
        urls = self._extract_urls(root)
        return [u for u in urls if "sitemap" in u.lower()]

    def fetch_with_limit(self, url: str, max_urls: int = 10000) -> List[str]:
        """
        Fetch sitemap with URL limit for large sites.

        For very large sitemaps (>10k URLs), this prevents memory issues
        by returning only the first N URLs.

        Args:
            url: Sitemap URL
            max_urls: Maximum number of URLs to return (default 10000)

        Returns:
            List of URLs (limited to max_urls)
        """
        urls = self.fetch_sitemap(url, recursive=False)

        if len(urls) > max_urls:
            return urls[:max_urls]
        else:
            return urls
