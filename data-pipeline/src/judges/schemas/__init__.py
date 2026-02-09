"""Judge system schemas - configuration and verdict types."""

from .config import JudgeConfig
from .verdict import JudgeVerdict, Severity, ValidationIssue

__all__ = ["JudgeConfig", "JudgeVerdict", "ValidationIssue", "Severity"]
