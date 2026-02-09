"""
Central configuration for data paths.

This module provides consistent paths across all pipeline scripts.
Local files (PDFs, cache) are stored in ~/.amal-metric-data/.

Database: DoltDB (version-controlled, MySQL-compatible). Configure via environment variables:
  - DOLT_HOST (default: 127.0.0.1)
  - DOLT_PORT (default: 3306)
  - DOLT_USER (default: root)
  - DOLT_DATABASE (default: zakaat)
"""

import os
from pathlib import Path


def get_data_dir() -> Path:
    """
    Get the local data directory path for PDFs and cache.

    Uses AMAL_DATA_DIR environment variable if set, otherwise defaults
    to ~/.amal-metric-data/

    Returns:
        Path to data directory
    """
    env_path = os.environ.get("AMAL_DATA_DIR")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return Path.home() / ".amal-metric-data"


def get_pdf_dir() -> Path:
    """Get the PDF storage directory."""
    return get_data_dir() / "pdfs"


def get_cache_dir() -> Path:
    """Get the crawler cache directory."""
    return get_data_dir() / "crawler_cache"


def ensure_data_dir():
    """Ensure the data directory exists."""
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
