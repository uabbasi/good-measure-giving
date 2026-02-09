"""
Global rate limiter for thread-safe API request throttling.

Problem: When using parallel workers, each collector instance has its own
rate limiter, causing N workers to make N simultaneous requests.

Solution: A shared, thread-safe rate limiter keyed by domain/API name.

Usage:
    from src.utils.rate_limiter import global_rate_limiter

    # In collector:
    global_rate_limiter.wait("propublica", delay=0.5)
    response = requests.get(url)
"""

import threading
import time
from typing import Dict


class GlobalRateLimiter:
    """
    Thread-safe global rate limiter for API requests.

    Maintains per-domain rate limiting across all threads/workers.
    """

    def __init__(self):
        self._locks: Dict[str, threading.Lock] = {}
        self._last_request: Dict[str, float] = {}
        self._master_lock = threading.Lock()

    def _get_domain_lock(self, domain: str) -> threading.Lock:
        """Get or create a lock for a domain."""
        with self._master_lock:
            if domain not in self._locks:
                self._locks[domain] = threading.Lock()
                self._last_request[domain] = 0.0
            return self._locks[domain]

    def wait(self, domain: str, delay: float) -> float:
        """
        Wait until it's safe to make a request to the given domain.

        Args:
            domain: API/domain identifier (e.g., "propublica", "candid")
            delay: Minimum seconds between requests

        Returns:
            Actual time waited (0 if no wait needed)
        """
        lock = self._get_domain_lock(domain)

        with lock:
            now = time.time()
            elapsed = now - self._last_request[domain]

            if elapsed < delay:
                wait_time = delay - elapsed
                time.sleep(wait_time)
            else:
                wait_time = 0.0

            self._last_request[domain] = time.time()
            return wait_time

    def reset(self, domain: str = None):
        """
        Reset rate limiter state.

        Args:
            domain: Specific domain to reset, or None to reset all
        """
        with self._master_lock:
            if domain:
                self._last_request[domain] = 0.0
            else:
                self._last_request = {k: 0.0 for k in self._last_request}


# Singleton instance - shared across all collectors
global_rate_limiter = GlobalRateLimiter()
