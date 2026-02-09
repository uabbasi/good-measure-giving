"""DoltDB database client, repositories, and version control.

Provides:
- Connection pool for DoltDB (MySQL-compatible protocol)
- Repository classes for data access
- Git-like version control operations (commit, branch, merge, diff)
"""

from .client import check_connection, execute_query, get_client, get_connection, get_cursor
from .dolt_client import Commit, DoltVersionControl, dolt, get_dolt
from .repository import (
    AgentDiscovery,
    AgentDiscoveryRepository,
    Charity,
    CharityData,
    CharityDataRepository,
    CharityRepository,
    Citation,
    CitationRepository,
    Evaluation,
    EvaluationRepository,
    PhaseCache,
    PhaseCacheRepository,
    RawDataRepository,
)

__all__ = [
    # Client
    "get_client",
    "get_connection",
    "get_cursor",
    "execute_query",
    "check_connection",
    # Version control
    "dolt",
    "get_dolt",
    "DoltVersionControl",
    "Commit",
    # Dataclasses
    "AgentDiscovery",
    "Charity",
    "CharityData",
    "Citation",
    "Evaluation",
    "PhaseCache",
    # Repositories
    "AgentDiscoveryRepository",
    "CharityDataRepository",
    "CharityRepository",
    "CitationRepository",
    "EvaluationRepository",
    "PhaseCacheRepository",
    "RawDataRepository",
]
