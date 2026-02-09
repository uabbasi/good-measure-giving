"""Abstract base classes for validation judges.

Two judge types:
- **Deterministic judges**: Pure Python, rule-based validation (bounds checking,
  cross-referencing, data integrity). No LLM calls. Fully reproducible.
- **LLM judges**: Use LLM for semantic validation that requires natural language
  understanding (claim verification, rationale-score alignment, cross-narrative
  consistency). Non-deterministic by nature.

Both types are first-class and run in every validation pass.
"""

import hashlib
import json
import logging
import re
from abc import ABC, abstractmethod
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from src.llm.llm_client import LLMClient, LLMTask

from .schemas.config import JudgeConfig
from .schemas.verdict import JudgeVerdict, Severity, ValidationIssue


class JudgeType(Enum):
    """Classification of judge validation approach.

    DETERMINISTIC: Pure Python rules — no LLM calls, fully reproducible.
    LLM: Uses LLM for semantic understanding — non-deterministic, has cost.
    """

    DETERMINISTIC = "deterministic"
    LLM = "llm"


class SafeJSONEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal and datetime types from DoltDB."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if hasattr(obj, "isoformat"):  # datetime, date, time
            return obj.isoformat()
        return super().default(obj)

logger = logging.getLogger(__name__)

# Prompts directory relative to this file
PROMPTS_DIR = Path(__file__).parent / "prompts"


class BaseJudge(ABC):
    """Abstract base class for validation judges.

    Each judge focuses on a specific validation concern (citations, facts,
    scores, data integrity, etc.). Judges run independently and can be
    executed in parallel.

    Subclasses must implement:
        - validate(): Core validation logic
        - name: Property returning the judge's name
        - judge_type: Property returning JudgeType.DETERMINISTIC or JudgeType.LLM
    """

    def __init__(self, config: JudgeConfig):
        """Initialize the judge with configuration.

        Args:
            config: Judge configuration with model, thresholds, etc.
        """
        self.config = config
        self._llm_client: Optional[LLMClient] = None
        self._prompt_template: Optional[str] = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the judge's name (e.g., 'citation', 'factual')."""
        pass

    @property
    @abstractmethod
    def judge_type(self) -> JudgeType:
        """Return the judge's type: DETERMINISTIC or LLM."""
        pass

    @property
    def prompt_file(self) -> Path:
        """Path to the prompt template file for this judge."""
        return PROMPTS_DIR / f"{self.name}_judge.txt"

    def get_llm_client(self) -> LLMClient:
        """Get or create the LLM client for this judge."""
        if self._llm_client is None:
            self._llm_client = LLMClient(
                task=LLMTask.LLM_JUDGE,
                model=self.config.judge_model,
            )
        return self._llm_client

    def load_prompt_template(self) -> str:
        """Load the prompt template from file."""
        if self._prompt_template is None:
            if self.prompt_file.exists():
                self._prompt_template = self.prompt_file.read_text()
            else:
                logger.warning(f"Prompt file not found: {self.prompt_file}")
                self._prompt_template = ""
        return self._prompt_template

    def format_prompt(self, output: dict[str, Any], context: dict[str, Any]) -> str:
        """Format the prompt template with charity data.

        Args:
            output: The exported charity data (narrative, scores, etc.)
            context: Additional context (metrics, source data, etc.)

        Returns:
            Formatted prompt string ready for LLM
        """
        template = self.load_prompt_template()

        # Build substitution dict (use SafeJSONEncoder for DoltDB Decimal values)
        substitutions = {
            "charity_name": output.get("name", "Unknown"),
            "ein": output.get("ein", "Unknown"),
            "narrative": json.dumps(output.get("narrative", {}), indent=2, cls=SafeJSONEncoder),
            "scores": json.dumps(output.get("evaluation", {}), indent=2, cls=SafeJSONEncoder),
            "citations": json.dumps(output.get("citations", []), indent=2, cls=SafeJSONEncoder),
            "context": json.dumps(context, indent=2, cls=SafeJSONEncoder),
        }

        # Simple string substitution
        result = template
        for key, value in substitutions.items():
            result = result.replace(f"{{{key}}}", str(value))

        return result

    @abstractmethod
    def validate(
        self, output: dict[str, Any], context: dict[str, Any]
    ) -> JudgeVerdict:
        """Validate the exported charity data.

        Args:
            output: The exported charity data (narrative, scores, citations)
            context: Additional context (source metrics, Form 990 data, etc.)

        Returns:
            JudgeVerdict with pass/fail status and any issues found
        """
        pass

    def create_verdict(
        self,
        passed: bool,
        issues: Optional[list[ValidationIssue]] = None,
        skipped: bool = False,
        skip_reason: Optional[str] = None,
        cost_usd: float = 0.0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> JudgeVerdict:
        """Create a verdict with this judge's name.

        Helper method to construct JudgeVerdict with common fields.
        """
        return JudgeVerdict(
            passed=passed,
            judge_name=self.name,
            issues=issues or [],
            skipped=skipped,
            skip_reason=skip_reason,
            cost_usd=cost_usd,
            metadata=metadata or {},
        )

    def add_issue(
        self,
        issues: list[ValidationIssue],
        severity: Severity,
        field: str,
        message: str,
        details: Optional[dict[str, Any]] = None,
        evidence: Optional[str] = None,
    ) -> None:
        """Add a validation issue to the list.

        Helper method for building issue lists during validation.
        """
        issues.append(
            ValidationIssue(
                severity=severity,
                field=field,
                message=message,
                details=details,
                evidence=evidence,
            )
        )

    def compute_prompt_hash(self, prompt: str) -> str:
        """Compute a hash of the prompt for tracking/caching."""
        return hashlib.sha256(prompt.encode()).hexdigest()[:12]

    @staticmethod
    def strip_markdown_json(text: str) -> str:
        """Strip markdown code blocks from LLM response.

        Gemini often wraps JSON in ```json ... ``` blocks.
        """
        # Try to extract JSON from markdown code block
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()
