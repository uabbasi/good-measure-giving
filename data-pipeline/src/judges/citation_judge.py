"""Citation Judge - validates that citations exist and support claims.

Verifies:
1. All citation markers [N] have corresponding entries
2. Citation URLs are reachable (with caching)
3. Fetched content actually supports the cited claim
"""

import logging
import re
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from .base_judge import BaseJudge, JudgeType
from .schemas.config import JudgeConfig
from .schemas.verdict import JudgeVerdict, Severity, ValidationIssue
from .url_verifier import URLVerifier

logger = logging.getLogger(__name__)


class CitationIssue(BaseModel):
    """Schema for citation verification issue from LLM."""

    citation_index: int = Field(description="The citation number (1-indexed)")
    field: str = Field(description="Field identifier for the issue")
    severity: str = Field(description="error, warning, or info")
    message: str = Field(description="Description of the issue")
    claim: Optional[str] = Field(None, description="The specific claim with the issue")
    evidence: Optional[str] = Field(None, description="Why this is an issue")


class CitationVerificationResult(BaseModel):
    """Schema for citation verification LLM response."""

    issues: list[CitationIssue] = Field(default_factory=list)
    verified_count: int = Field(0, description="Number of citations verified")
    failed_count: int = Field(0, description="Number of citations that failed")
    summary: str = Field("", description="Brief summary of results")


class CitationJudge(BaseJudge):
    """Validates that citations exist and support the claims they reference.

    Performs:
    1. Structural validation - all [N] markers have citation entries
    2. URL verification - fetches URLs to verify they're reachable
    3. Content verification - LLM checks if content supports claims
    """

    def __init__(self, config: JudgeConfig, url_verifier: Optional[URLVerifier] = None):
        """Initialize the citation judge.

        Args:
            config: Judge configuration
            url_verifier: Optional URL verifier (creates one if not provided)
        """
        super().__init__(config)
        self._url_verifier = url_verifier

    @property
    def name(self) -> str:
        return "citation"

    @property
    def judge_type(self) -> JudgeType:
        return JudgeType.LLM

    def get_url_verifier(self) -> URLVerifier:
        """Get or create URL verifier."""
        if self._url_verifier is None:
            # cache_dir is set in __post_init__ if None
            cache_dir = self.config.cache_dir or Path.home() / ".amal-metric-data" / "judge_cache"
            self._url_verifier = URLVerifier(
                cache_dir=cache_dir / "url_cache",
                timeout=self.config.url_fetch_timeout,
                ttl_days=self.config.url_cache_ttl_days,
                max_content_chars=self.config.max_content_chars,
            )
        return self._url_verifier

    def validate(
        self, output: dict[str, Any], context: dict[str, Any]
    ) -> JudgeVerdict:
        """Validate citations in the charity output.

        Args:
            output: Exported charity data with narrative and citations
            context: Additional context (source data)

        Returns:
            JudgeVerdict with any citation issues found
        """
        issues: list[ValidationIssue] = []
        cost_usd = 0.0
        metadata: dict[str, Any] = {}

        # Extract citations from output - they're nested in narrative.all_citations
        narrative = output.get("narrative", {})
        citations = narrative.get("all_citations", [])

        # If no citations, nothing to validate
        if not citations:
            return self.create_verdict(
                passed=True,
                metadata={"note": "No citations to validate"},
            )

        # Step 1: Structural validation
        structural_issues = self._validate_structure(narrative, citations)
        issues.extend(structural_issues)

        # Step 2: Fetch and verify URLs
        url_content = {}
        verifier = self.get_url_verifier()

        for i, citation in enumerate(citations):
            url = citation.get("source_url", "") or citation.get("url", "")
            if not url:
                self.add_issue(
                    issues,
                    Severity.ERROR,
                    f"citation_{i+1}",
                    f"Citation {i+1} has no URL",
                )
                continue

            # Check if URL should be skipped (trusted source)
            should_skip, skip_reason = verifier.should_skip(url)
            if should_skip:
                url_content[i+1] = f"[Trusted source - {skip_reason}]"
                continue

            # Fetch URL
            result = verifier.fetch(url)
            if result.success:
                url_content[i+1] = result.content
            else:
                # URL fetch failed - this is a warning since URL might be temporarily down
                self.add_issue(
                    issues,
                    Severity.WARNING,
                    f"citation_{i+1}",
                    f"URL unreachable: {result.error}",
                    details={"url": url, "error": result.error},
                )

        metadata["urls_fetched"] = len(url_content)
        metadata["urls_failed"] = len(citations) - len(url_content)

        # Step 3: LLM verification of claims against content
        if url_content and self.config.verify_all_citations:
            llm_result = self._verify_claims_with_llm(
                output, citations, url_content, context
            )
            if llm_result:
                issues.extend(llm_result.issues)
                cost_usd = llm_result.cost
                metadata["llm_verified_count"] = llm_result.verified_count
                metadata["llm_failed_count"] = llm_result.failed_count

        # Determine pass/fail
        error_count = len([i for i in issues if i.severity == Severity.ERROR])
        passed = error_count == 0

        return self.create_verdict(
            passed=passed,
            issues=issues,
            cost_usd=cost_usd,
            metadata=metadata,
        )

    def _validate_structure(
        self, narrative: dict[str, Any], citations: list[dict[str, Any]]
    ) -> list[ValidationIssue]:
        """Validate that all citation markers have corresponding entries.

        Finds [1], [2], etc. in narrative text and checks they're in citations.
        """
        issues: list[ValidationIssue] = []

        # Collect all narrative text
        text_parts = []
        for key, value in narrative.items():
            if isinstance(value, str):
                text_parts.append(value)
            elif isinstance(value, dict):
                for subvalue in value.values():
                    if isinstance(subvalue, str):
                        text_parts.append(subvalue)

        full_text = " ".join(text_parts)

        # Find all citation markers [N]
        markers = re.findall(r"\[(\d+)\]", full_text)
        referenced = set(int(m) for m in markers)

        # Build set of defined citation IDs (citations may have non-sequential IDs)
        defined_ids = set()
        for cit in citations:
            cit_id = cit.get("id", "")
            # Extract number from "[N]" format
            match = re.match(r"\[(\d+)\]", str(cit_id))
            if match:
                defined_ids.add(int(match.group(1)))

        # Check each referenced citation exists in defined IDs
        for ref in referenced:
            if ref not in defined_ids:
                self.add_issue(
                    issues,
                    Severity.ERROR,
                    f"citation_{ref}",
                    f"Citation marker [{ref}] has no corresponding entry",
                    details={"defined_ids": sorted(defined_ids)},
                )

        # Check for orphaned citations (defined but not referenced)
        for cit_id in defined_ids:
            if cit_id not in referenced:
                self.add_issue(
                    issues,
                    Severity.INFO,
                    f"citation_{cit_id}",
                    f"Citation {cit_id} defined but not referenced in narrative",
                )

        return issues

    def _verify_claims_with_llm(
        self,
        output: dict[str, Any],
        citations: list[dict[str, Any]],
        url_content: dict[int, str],
        context: dict[str, Any],
    ) -> Optional["LLMVerificationResult"]:
        """Use LLM to verify that URL content supports the claims.

        Returns structured result with issues and cost.
        """
        try:
            # Build prompt with URL content
            prompt = self.format_prompt(output, context)

            # Add URL content section
            url_section = "\n## Fetched URL Content\n"
            for idx, content in url_content.items():
                url_section += f"\n### Citation {idx}\n{content[:2000]}...\n"

            prompt = prompt.replace("{url_content}", url_section)

            # Call LLM
            client = self.get_llm_client()
            response = client.generate(
                prompt=prompt,
                json_schema=CitationVerificationResult.model_json_schema(),
            )

            # Parse response (strip markdown if present)
            json_text = self.strip_markdown_json(response.text)
            result = CitationVerificationResult.model_validate_json(json_text)

            # Convert to ValidationIssues
            issues = []
            for issue in result.issues:
                severity = Severity(issue.severity.lower())
                issues.append(
                    ValidationIssue(
                        severity=severity,
                        field=issue.field,
                        message=issue.message,
                        details={"claim": issue.claim} if issue.claim else None,
                        evidence=issue.evidence,
                    )
                )

            return LLMVerificationResult(
                issues=issues,
                verified_count=result.verified_count,
                failed_count=result.failed_count,
                cost=response.cost_usd or 0.0,
            )

        except Exception as e:
            logger.error(f"LLM citation verification failed: {e}")
            return None


class LLMVerificationResult:
    """Result from LLM verification."""

    def __init__(
        self,
        issues: list[ValidationIssue],
        verified_count: int,
        failed_count: int,
        cost: float,
    ):
        self.issues = issues
        self.verified_count = verified_count
        self.failed_count = failed_count
        self.cost = cost
