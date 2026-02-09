"""
Simple robots.txt checker for web crawler.

Checks if URLs are allowed by robots.txt directives.
Lightweight implementation for basic compliance with FR-018.
"""

import time
from typing import Dict, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests


class RobotsChecker:
    """
    Check robots.txt compliance for crawling.

    Caches robots.txt per domain to avoid repeated fetches.
    """

    def __init__(self, user_agent: str = "GoodMeasureGivingBot/1.0", logger=None):
        """
        Initialize robots checker.

        Args:
            user_agent: User agent string to identify crawler
            logger: Logger instance
        """
        self.user_agent = user_agent
        self.logger = logger
        self._cache: Dict[str, RobotFileParser] = {}  # domain -> parser
        self._cache_timestamp: Dict[str, float] = {}  # domain -> timestamp
        self.cache_ttl = 3600  # 1 hour cache

    def can_fetch(self, url: str) -> bool:
        """
        Check if URL can be fetched according to robots.txt.

        Args:
            url: URL to check

        Returns:
            True if allowed, False if disallowed
        """
        try:
            parsed = urlparse(url)
            domain = f"{parsed.scheme}://{parsed.netloc}"

            # Get or fetch robots.txt parser for this domain
            parser = self._get_parser(domain)

            if parser is None:
                # No robots.txt or failed to fetch - allow crawling
                return True

            # Check if URL is allowed
            allowed = parser.can_fetch(self.user_agent, url)

            if not allowed and self.logger:
                self.logger.debug(f"robots.txt disallows: {url}")

            return allowed

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Error checking robots.txt for {url}: {e}")
            # On error, allow (fail open rather than fail closed)
            return True

    def _get_parser(self, domain: str) -> Optional[RobotFileParser]:
        """
        Get cached or fetch robots.txt parser for domain.

        Args:
            domain: Domain URL (e.g., https://example.org)

        Returns:
            RobotFileParser or None if not available
        """
        # Check cache
        if domain in self._cache:
            # Check if cache is still valid
            if time.time() - self._cache_timestamp[domain] < self.cache_ttl:
                return self._cache[domain]
            else:
                # Cache expired, remove it
                del self._cache[domain]
                del self._cache_timestamp[domain]

        # Fetch robots.txt
        robots_url = urljoin(domain, "/robots.txt")

        try:
            response = requests.get(robots_url, timeout=10)

            if response.status_code == 404:
                # No robots.txt - cache None
                self._cache[domain] = None
                self._cache_timestamp[domain] = time.time()
                return None

            if response.status_code != 200:
                # Failed to fetch - cache None
                if self.logger:
                    self.logger.debug(f"robots.txt fetch failed (HTTP {response.status_code}): {robots_url}")
                self._cache[domain] = None
                self._cache_timestamp[domain] = time.time()
                return None

            # Parse robots.txt
            parser = RobotFileParser()
            parser.parse(response.text.splitlines())

            # Cache the parser
            self._cache[domain] = parser
            self._cache_timestamp[domain] = time.time()

            if self.logger:
                self.logger.debug(f"Loaded robots.txt: {robots_url}")

            return parser

        except requests.RequestException as e:
            if self.logger:
                self.logger.debug(f"Failed to fetch robots.txt: {robots_url} ({e})")
            # Cache None to avoid repeated failures
            self._cache[domain] = None
            self._cache_timestamp[domain] = time.time()
            return None

    def get_crawl_delay(self, url: str) -> Optional[float]:
        """
        Get crawl delay from robots.txt if specified.

        Args:
            url: URL to check

        Returns:
            Crawl delay in seconds, or None if not specified
        """
        try:
            parsed = urlparse(url)
            domain = f"{parsed.scheme}://{parsed.netloc}"

            parser = self._get_parser(domain)

            if parser is None:
                return None

            # Get crawl delay for our user agent
            delay = parser.crawl_delay(self.user_agent)

            return float(delay) if delay else None

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Error getting crawl delay for {url}: {e}")
            return None
