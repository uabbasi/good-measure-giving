"""
Logging infrastructure for the charity evaluation pipeline.

Provides:
- Structured logging with timestamps
- Different log levels (DEBUG, INFO, WARNING, ERROR)
- File and console output
- Error tracking and reporting
"""

import logging
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional


class MillisecondsFormatter(logging.Formatter):
    """Custom formatter that includes milliseconds and aligns log levels."""

    def formatTime(self, record, datefmt=None):  # noqa: N802 - must match parent class method name
        """Override formatTime to include milliseconds."""
        ct = datetime.fromtimestamp(record.created)
        if datefmt and "%f" in datefmt:
            # Replace %f with milliseconds (3 digits)
            # First format without %f
            s = ct.strftime(datefmt.replace(",%f", ""))
            # Then append milliseconds
            return s + f",{int(record.msecs):03d}"
        elif datefmt:
            return ct.strftime(datefmt)
        else:
            return ct.strftime("%Y-%m-%d %H:%M:%S") + f",{int(record.msecs):03d}"


class PipelineLogger:
    """
    Centralized logger for the pipeline with structured output.
    """

    def __init__(
        self,
        name: str = "charity_pipeline",
        log_level: str = "INFO",
        log_file: Optional[str] = None,
        log_dir: Optional[Path] = None,
        phase: Optional[str] = None,
    ):
        """
        Initialize the pipeline logger.

        Args:
            name: Logger name
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            log_file: Optional log file name
            log_dir: Directory for log files (defaults to logs/)
            phase: Optional pipeline phase name (e.g., "P1:Collect", "P2:Eval")
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        self.phase = phase

        # Prevent propagation to root logger to avoid duplicate logs
        self.logger.propagate = False

        # Prevent duplicate handlers
        if self.logger.handlers:
            self.logger.handlers.clear()

        # Build format string with optional phase prefix
        if phase:
            fmt_str = f"%(asctime)s | %(levelname)-8s | {phase} | %(filename)s:%(lineno)d | %(message)s"
        else:
            fmt_str = "%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s"

        # Console handler with formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_formatter = MillisecondsFormatter(fmt_str, datefmt="%Y-%m-%d %H:%M:%S,%f")
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # File handler if log_file specified
        if log_file:
            if log_dir is None:
                # Default to pipeline root/logs directory
                log_dir = Path(__file__).parent.parent.parent / "logs"

            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / log_file

            file_handler = logging.FileHandler(log_path)
            file_handler.setLevel(logging.DEBUG)  # Log everything to file
            file_formatter = MillisecondsFormatter(fmt_str, datefmt="%Y-%m-%d %H:%M:%S,%f")
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

            self.info(f"Logging to file: {log_path}")

        # Configure root logger and third-party library loggers to use unified format
        self._configure_external_loggers(log_level, console_formatter)

        # Track errors for summary reporting
        self.errors = []
        self.warnings = []

        # Track cache statistics
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_details = []  # List of dicts with hit/miss details

    def _configure_external_loggers(self, log_level: str, formatter: logging.Formatter):
        """
        Configure external library loggers to use our unified format.

        This ensures all logs (including from third-party libraries like sitemaps, trafilatura)
        use the same aligned format.
        """
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper()))

        # Clear existing handlers from root logger
        root_logger.handlers.clear()

        # Add our formatted handler to root logger
        root_handler = logging.StreamHandler(sys.stdout)
        root_handler.setLevel(getattr(logging, log_level.upper()))
        root_handler.setFormatter(formatter)
        root_logger.addHandler(root_handler)

        # Configure specific third-party library loggers
        for lib_name in ["sitemaps", "trafilatura", "readability", "urllib3", "requests"]:
            lib_logger = logging.getLogger(lib_name)
            lib_logger.handlers.clear()
            lib_logger.propagate = True  # Let root logger handle it
            lib_logger.setLevel(getattr(logging, log_level.upper()))

        # Suppress noisy pdfminer warnings (color parsing errors, etc.)
        for pdfminer_module in ["pdfminer", "pdfminer.pdfinterp", "pdfminer.pdfpage", "pdfminer.converter"]:
            pdf_logger = logging.getLogger(pdfminer_module)
            pdf_logger.setLevel(logging.ERROR)  # Only show errors, not warnings

    def debug(self, message: str, **kwargs):
        """Log debug message with optional structured data."""
        if kwargs:
            # Format key-value pairs more cleanly: key=value separated by spaces
            formatted_data = " ".join(f"{k}={v}" for k, v in kwargs.items())
            message = f"{message} [{formatted_data}]"
        self.logger.debug(message, stacklevel=2)

    def info(self, message: str, **kwargs):
        """Log info message with optional structured data."""
        if kwargs:
            # Format key-value pairs more cleanly: key=value separated by spaces
            formatted_data = " ".join(f"{k}={v}" for k, v in kwargs.items())
            message = f"{message} [{formatted_data}]"
        self.logger.info(message, stacklevel=2)

    def warning(self, message: str, **kwargs):
        """Log warning message and track for reporting."""
        if kwargs:
            # Format key-value pairs more cleanly: key=value separated by spaces
            formatted_data = " ".join(f"{k}={v}" for k, v in kwargs.items())
            message = f"{message} [{formatted_data}]"
        self.logger.warning(message, stacklevel=2)
        self.warnings.append(
            {
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "data": kwargs,
            }
        )

    def error(self, message: str, exception: Optional[Exception] = None, **kwargs):
        """Log error message and track for reporting."""
        if exception:
            message = f"{message} | Exception: {str(exception)}"
        if kwargs:
            # Format key-value pairs more cleanly: key=value separated by spaces
            formatted_data = " ".join(f"{k}={v}" for k, v in kwargs.items())
            message = f"{message} [{formatted_data}]"

        self.logger.error(message, exc_info=exception is not None, stacklevel=2)
        self.errors.append(
            {
                "message": message,
                "exception": str(exception) if exception else None,
                "timestamp": datetime.now().isoformat(),
                "data": kwargs,
            }
        )

    def log_data_source_fetch(
        self,
        charity_id: int,
        ein: str,
        source: str,
        success: bool,
        error: Optional[str] = None,
    ):
        """Log data source fetch attempt."""
        if success:
            message = f"Successfully fetched {source} data [charity_id={charity_id} ein={ein} source={source}]"
            self.logger.info(message, stacklevel=2)
        else:
            message = f"Failed to fetch {source} data [charity_id={charity_id} ein={ein} source={source} error={error}]"
            self.logger.error(message, stacklevel=2)
            self.errors.append(
                {
                    "message": message,
                    "exception": None,
                    "timestamp": datetime.now().isoformat(),
                    "data": {"charity_id": charity_id, "ein": ein, "source": source, "error": error},
                }
            )

    def log_evaluation_start(self, charity_id: int, ein: str):
        """Log start of charity evaluation (debug level to reduce noise in parallel execution)."""
        message = f"Starting charity evaluation [charity_id={charity_id} ein={ein}]"
        self.logger.debug(message, stacklevel=2)

    def log_evaluation_complete(
        self,
        charity_id: int,
        ein: str,
        impact_tier: str,
        confidence_tier: str,
        duration_seconds: float,
    ):
        """Log completion of charity evaluation."""
        message = f"Completed charity evaluation [charity_id={charity_id} ein={ein} impact_tier={impact_tier} confidence_tier={confidence_tier} duration_seconds={round(duration_seconds, 2)}]"
        self.logger.info(message, stacklevel=2)

    def log_llm_call(
        self,
        narrative_type: str,
        charity_id: int,
        tokens_used: int,
        cost_usd: float,
    ):
        """Log LLM API call for cost tracking."""
        message = f"LLM call for {narrative_type} narrative [charity_id={charity_id} tokens={tokens_used} cost_usd={round(cost_usd, 4)}]"
        self.logger.debug(message, stacklevel=2)

    def log_pipeline_start(self, num_charities: int):
        """Log start of pipeline run."""
        self.info(
            "=" * 60,
        )
        self.info(
            f"Pipeline started - processing {num_charities} charities",
            num_charities=num_charities,
        )
        self.info(
            "=" * 60,
        )

    def log_pipeline_complete(
        self,
        succeeded: int,
        failed: int,
        duration_seconds: float,
        total_cost_usd: float,
    ):
        """Log completion of pipeline run."""
        self.info(
            "=" * 60,
        )
        self.info(
            "Pipeline completed",
            succeeded=succeeded,
            failed=failed,
            total=succeeded + failed,
            duration_seconds=round(duration_seconds, 2),
            total_cost_usd=round(total_cost_usd, 4),
        )
        self.info(
            "=" * 60,
        )

    @contextmanager
    def time_charity(self, charity_id: int, ein: str, operation: str):
        """
        Context manager to time and log individual charity operations.

        Args:
            charity_id: Database charity ID
            ein: Charity EIN
            operation: Description of operation (e.g., "data collection", "evaluation")

        Usage:
            with logger.time_charity(123, "12-3456789", "data collection"):
                # ... perform operation ...
        """
        start_time = datetime.now()
        self.info(
            f"Starting {operation}",
            charity_id=charity_id,
            ein=ein,
            operation=operation,
        )

        try:
            yield
            duration = (datetime.now() - start_time).total_seconds()
            self.info(
                f"Completed {operation}",
                charity_id=charity_id,
                ein=ein,
                operation=operation,
                duration_seconds=round(duration, 2),
            )
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.error(
                f"Failed {operation}",
                exception=e,
                charity_id=charity_id,
                ein=ein,
                operation=operation,
                duration_seconds=round(duration, 2),
            )
            raise

    def log_cache_hit(self, charity_id: int, ein: str, cache_type: str, age_days: float = None):
        """
        Log cache hit for a charity data source or evaluation.

        Args:
            charity_id: Database charity ID
            ein: Charity EIN
            cache_type: Type of cached data (e.g., "propublica", "evaluation", "website")
            age_days: Optional age of cached data in days
        """
        self.cache_hits += 1
        detail = {
            "charity_id": charity_id,
            "ein": ein,
            "cache_type": cache_type,
            "hit": True,
            "timestamp": datetime.now().isoformat(),
        }
        if age_days is not None:
            detail["age_days"] = round(age_days, 1)

        self.cache_details.append(detail)

        msg = f"Cache HIT for {cache_type}"
        if age_days is not None:
            msg += f" (age: {round(age_days, 1)} days)"

        self.info(
            msg,
            charity_id=charity_id,
            ein=ein,
            cache_type=cache_type,
        )

    def log_cache_miss(self, charity_id: int, ein: str, cache_type: str, reason: str = None):
        """
        Log cache miss for a charity data source or evaluation.

        Args:
            charity_id: Database charity ID
            ein: Charity EIN
            cache_type: Type of data being requested (e.g., "propublica", "evaluation")
            reason: Optional reason for cache miss (e.g., "no data", "stale", "failed scrape")
        """
        self.cache_misses += 1
        detail = {
            "charity_id": charity_id,
            "ein": ein,
            "cache_type": cache_type,
            "hit": False,
            "timestamp": datetime.now().isoformat(),
        }
        if reason:
            detail["reason"] = reason

        self.cache_details.append(detail)

        msg = f"Cache MISS for {cache_type}"
        if reason:
            msg += f" (reason: {reason})"

        self.debug(
            msg,
            charity_id=charity_id,
            ein=ein,
            cache_type=cache_type,
        )

    def get_error_summary(self) -> dict:
        """Get summary of errors and warnings for reporting."""
        return {
            "total_errors": len(self.errors),
            "total_warnings": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
        }

    def generate_summary(self) -> dict:
        """
        Generate comprehensive aggregate statistics for pipeline run.

        Returns:
            dict with cache stats, error stats, and detailed breakdowns
        """
        total_cache_checks = self.cache_hits + self.cache_misses
        cache_hit_rate = (self.cache_hits / total_cache_checks * 100) if total_cache_checks > 0 else 0.0

        # Group cache details by type
        cache_by_type = {}
        for detail in self.cache_details:
            cache_type = detail["cache_type"]
            if cache_type not in cache_by_type:
                cache_by_type[cache_type] = {"hits": 0, "misses": 0, "total": 0}

            cache_by_type[cache_type]["total"] += 1
            if detail["hit"]:
                cache_by_type[cache_type]["hits"] += 1
            else:
                cache_by_type[cache_type]["misses"] += 1

        # Calculate hit rates by type
        for cache_type in cache_by_type:
            stats = cache_by_type[cache_type]
            if stats["total"] > 0:
                stats["hit_rate"] = round(stats["hits"] / stats["total"] * 100, 1)
            else:
                stats["hit_rate"] = 0.0

        return {
            "cache": {
                "total_checks": total_cache_checks,
                "hits": self.cache_hits,
                "misses": self.cache_misses,
                "hit_rate_percent": round(cache_hit_rate, 1),
                "by_type": cache_by_type,
            },
            "errors": {
                "total": len(self.errors),
                "details": self.errors,
            },
            "warnings": {
                "total": len(self.warnings),
                "details": self.warnings,
            },
            "timestamp": datetime.now().isoformat(),
        }

    def clear_tracking(self):
        """Clear tracked errors, warnings, and cache stats (useful between pipeline runs)."""
        self.errors = []
        self.warnings = []
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_details = []


# ============================================================================
# Global Logger Instance
# ============================================================================

# Default logger instance for convenience
_default_logger: Optional[PipelineLogger] = None


def get_logger(
    name: str = "charity_pipeline",
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    phase: Optional[str] = None,
) -> PipelineLogger:
    """
    Get or create the default pipeline logger.

    Args:
        name: Logger name
        log_level: Logging level
        log_file: Optional log file
        phase: Optional pipeline phase name (e.g., "P1:Collect")

    Returns:
        PipelineLogger instance
    """
    global _default_logger

    if _default_logger is None:
        _default_logger = PipelineLogger(
            name=name,
            log_level=log_level,
            log_file=log_file,
            phase=phase,
        )

    return _default_logger


# ============================================================================
# Context Manager for Pipeline Runs
# ============================================================================


class PipelineRunContext:
    """
    Context manager for pipeline runs with automatic logging.

    Usage:
        with PipelineRunContext(logger, num_charities=10) as ctx:
            # ... process charities ...
            ctx.increment_success()  # or ctx.increment_failure()
    """

    def __init__(self, logger: PipelineLogger, num_charities: int):
        self.logger = logger
        self.num_charities = num_charities
        self.start_time = None
        self.succeeded = 0
        self.failed = 0

    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.log_pipeline_start(self.num_charities)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds()
        # Note: Total cost would be tracked separately via LLM cost tracking
        self.logger.log_pipeline_complete(
            succeeded=self.succeeded,
            failed=self.failed,
            duration_seconds=duration,
            total_cost_usd=0.0,  # Will be updated by actual LLM tracking
        )

        # Don't suppress exceptions
        return False

    def increment_success(self):
        """Increment successful charity count."""
        self.succeeded += 1

    def increment_failure(self):
        """Increment failed charity count."""
        self.failed += 1


# ============================================================================
# Global Logging Configuration
# ============================================================================


def configure_global_logging(log_level: str = "INFO", phase: Optional[str] = None):
    """
    Configure all logging (root + third-party libraries) with unified format.

    Call this early in application startup to ensure all logs are consistently formatted.

    Args:
        log_level: Logging level to apply globally (DEBUG, INFO, WARNING, ERROR)
        phase: Optional pipeline phase name (e.g., "P1:Collect")
    """
    # Build format string with optional phase prefix
    if phase:
        fmt_str = f"%(asctime)s | %(levelname)-8s | {phase} | %(filename)s:%(lineno)d | %(message)s"
    else:
        fmt_str = "%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s"

    # Create unified formatter
    formatter = MillisecondsFormatter(fmt_str, datefmt="%Y-%m-%d %H:%M:%S,%f")

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    root_logger.handlers.clear()

    # Add formatted handler to root logger
    root_handler = logging.StreamHandler(sys.stdout)
    root_handler.setLevel(getattr(logging, log_level.upper()))
    root_handler.setFormatter(formatter)
    root_logger.addHandler(root_handler)

    # Configure third-party library loggers to propagate to root
    for lib_name in ["sitemaps", "trafilatura", "readability", "urllib3", "requests", "httpx"]:
        lib_logger = logging.getLogger(lib_name)
        lib_logger.handlers.clear()
        lib_logger.propagate = True
        lib_logger.setLevel(getattr(logging, log_level.upper()))
