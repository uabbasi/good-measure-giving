"""Worker pool with exception handling for parallel processing.

This module provides a ThreadPoolExecutor wrapper that implements graceful
exception handling for charity processing tasks.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


class WorkerPool:
    """ThreadPoolExecutor wrapper with exception handling for pipeline tasks."""

    def __init__(self, max_workers: int = 10, logger=None):
        """
        Initialize worker pool.

        Args:
            max_workers: Maximum number of concurrent worker threads (default: 10)
            logger: Optional logger instance for logging
        """
        self.max_workers = max_workers
        self.logger = logger or logging.getLogger(__name__)
        self.executor = None
        self._stats_lock = threading.Lock()  # Thread-safe stats updates
        self.stats = {
            "max_workers": max_workers,
            "total_submitted": 0,
            "total_completed": 0,
            "total_successful": 0,
            "total_failed": 0,
        }

    def map(self, func: callable, items: list, desc: str = "Processing") -> list:
        """
        Process items in parallel with exception handling.

        Args:
            func: Worker function to execute
            items: List of items to process
            desc: Description for progress reporting

        Returns:
            List of tuples: (success: bool, item: any, result_or_error: any)
        """
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all items
            future_to_item = {executor.submit(func, item): item for item in items}
            with self._stats_lock:
                self.stats["total_submitted"] += len(items)

            # Collect results as they complete
            for future in as_completed(future_to_item):
                item = future_to_item[future]
                with self._stats_lock:
                    self.stats["total_completed"] += 1

                try:
                    result = future.result()
                    with self._stats_lock:
                        self.stats["total_successful"] += 1
                    results.append((True, item, result))
                    self.logger.debug(f"{desc}: Success for item {item}")

                except Exception as e:
                    with self._stats_lock:
                        self.stats["total_failed"] += 1
                    results.append((False, item, e))
                    self.logger.error(f"{desc}: Failed for item {item}: {e}", exc_info=True)

        self.logger.info(
            f"{desc} complete: {self.stats['total_successful']} successful, {self.stats['total_failed']} failed"
        )

        return results

    def submit(self, func: callable, *args, **kwargs):
        """
        Submit single task for execution.

        Args:
            func: Callable to execute
            *args: Positional arguments to func
            **kwargs: Keyword arguments to func

        Returns:
            Future object representing the pending execution
        """
        if self.executor is None:
            self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

        with self._stats_lock:
            self.stats["total_submitted"] += 1
        future = self.executor.submit(func, *args, **kwargs)

        # Add callback to track completion
        def _track_completion(f):
            with self._stats_lock:
                self.stats["total_completed"] += 1
            try:
                f.result()  # Will raise exception if task failed
                with self._stats_lock:
                    self.stats["total_successful"] += 1
            except Exception:
                with self._stats_lock:
                    self.stats["total_failed"] += 1
                self.logger.error(f"Task failed: {func.__name__}", exc_info=True)

        future.add_done_callback(_track_completion)
        return future

    def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown worker pool.

        Args:
            wait: If True, block until all submitted tasks complete
        """
        if self.executor is not None:
            self.logger.info(f"Shutting down worker pool (wait={wait})...")
            self.executor.shutdown(wait=wait)
            self.logger.info(
                f"Worker pool shutdown complete. Stats: "
                f"{self.stats['total_successful']} successful, "
                f"{self.stats['total_failed']} failed"
            )
            self.executor = None

    def get_stats(self) -> dict:
        """Get worker pool statistics."""
        return dict(self.stats)
