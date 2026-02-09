"""
URL helper utilities for smart crawler.

This module provides functions for URL normalization and validation.
"""

from urllib.parse import urljoin, urlparse


def normalize_url(url: str, base_url: str | None = None) -> str:
    """
    Normalize URL by adding scheme if missing and resolving relative URLs.

    Args:
        url: URL to normalize
        base_url: Base URL for resolving relative URLs (optional)

    Returns:
        Normalized absolute URL with scheme

    Examples:
        >>> normalize_url("charity.org")
        'https://charity.org'
        >>> normalize_url("http://charity.org")
        'http://charity.org'
        >>> normalize_url("/about", "https://charity.org")
        'https://charity.org/about'
    """
    # Strip whitespace
    url = url.strip()

    # If base_url provided and url is relative, resolve it
    if base_url and not url.startswith(("http://", "https://", "//")):
        url = urljoin(base_url, url)

    # Add https:// if no scheme present
    if not url.startswith(("http://", "https://", "//")):
        url = f"https://{url}"

    # Handle protocol-relative URLs
    if url.startswith("//"):
        url = f"https:{url}"

    return url


def is_same_domain(url1: str, url2: str) -> bool:
    """
    Check if two URLs belong to the same domain.

    Args:
        url1: First URL
        url2: Second URL

    Returns:
        True if both URLs have the same domain

    Examples:
        >>> is_same_domain("https://charity.org/about", "https://charity.org/programs")
        True
        >>> is_same_domain("https://charity.org", "https://other.org")
        False
    """
    domain1 = urlparse(normalize_url(url1)).netloc
    domain2 = urlparse(normalize_url(url2)).netloc
    return domain1 == domain2


def get_url_depth(url: str) -> int:
    """
    Get the depth of a URL (number of path segments).

    Args:
        url: URL to analyze

    Returns:
        Number of path segments

    Examples:
        >>> get_url_depth("https://charity.org")
        0
        >>> get_url_depth("https://charity.org/about")
        1
        >>> get_url_depth("https://charity.org/programs/education")
        2
    """
    parsed = urlparse(normalize_url(url))
    path = parsed.path.strip("/")
    if not path:
        return 0
    return len(path.split("/"))
