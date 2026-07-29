"""Factual Judge - validates narrative claims match source data.

Uses span-level verification approach to:
1. Extract factual claims from narrative
2. Match claims to source data
3. Verify values are consistent
"""

import logging
import re
import time
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from .base_judge import BaseJudge, JudgeType
from .materiality import is_methodology_divergent
from .schemas.verdict import JudgeVerdict, Severity, ValidationIssue

logger = logging.getLogger(__name__)


# Only these two kinds of finding describe a defect in the narrative. The
# others describe the state of our evidence, which is not the charity's fault
# and must not block its publication.
BLOCKING_DISCREPANCY_KINDS = {"contradiction", "fabrication"}

# Whether the wallet tag agrees with the zakat claim is settled in code:
# _quick_checks compares evaluation.wallet_tag against a tag derived
# independently from claims_zakat_eligible (judge_phase._wallet_tag_from_zakat_claim).
# The model is handed both values anyway and sometimes rules on them a second
# time -- on 99-3032347 it read SADAQAH-ELIGIBLE (the tag meaning "does NOT
# claim zakat") as "zakat-eligible" and reported the agreeing pair as a
# contradiction, costing the charity its page. factual_judge.txt already names
# that exact pair as CORRECT, so the answer is not more prompt text. Where a
# deterministic check owns the question, the model's copy does not get to block.
_WALLET_TAG_AGREEMENT_RE = re.compile(r"wallet.{0,3}tag", re.IGNORECASE)


def _is_wallet_tag_agreement(field: str, message: str) -> bool:
    """Is this finding the wallet-tag/zakat-claim comparison _quick_checks owns?"""
    text = f"{field} {message}"
    return bool(_WALLET_TAG_AGREEMENT_RE.search(text)) and "zakat" in text.lower()


# A response the model cut off mid-token is a transient generation failure, the
# same class as a 429 -- retrying gets a clean one. Before this, a clipped
# response fell through to "Could not complete LLM verification", which fails
# closed and withheld the charity (01-0548371, "Invalid JSON: EOF while parsing
# a string"). Retrying is not ignoring: exhausting the retries still blocks.
_TRUNCATED_RESPONSE_MARKERS = ("invalid json", "json_invalid", "eof while parsing")

_NUMERIC_RE = re.compile(r"-?\d[\d,]*\.?\d*")

# Matches the prompt's stated tolerances: 1% relative for money, half a unit
# absolute for percentages and month counts.
_RELATIVE_TOLERANCE = 0.01
_ABSOLUTE_TOLERANCE = 0.5
_ABSOLUTE_TOLERANCE_MAX_MAGNITUDE = 100


def _parse_number(v: Any) -> Optional[float]:
    """First numeric token in a value, commas and currency stripped."""
    if v is None:
        return None
    m = _NUMERIC_RE.search(str(v).replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def numeric_agreement(claim_value: Any, source_value: Any) -> Optional[bool]:
    """Do two reported values agree once rounding is allowed?

    Returns True/False when both parse as numbers, None when either does not
    (a prose claim -- the model's judgement is all we have).

    This exists because the prompt's tolerance rules were routinely ignored:
    "50.3% vs 50.29%" and even "$205,225 vs $205,225" came back as blocking
    errors. A deterministic check does not have moods.
    """
    a, b = _parse_number(claim_value), _parse_number(source_value)
    if a is None or b is None:
        return None
    if a == b:
        return True
    diff = abs(a - b)
    if diff <= _RELATIVE_TOLERANCE * max(abs(a), abs(b)):
        return True
    # Percentages and month counts live on a small scale where a relative test
    # is too strict: 1.3 vs 1.32 months is rounding, not a discrepancy.
    if max(abs(a), abs(b)) <= _ABSOLUTE_TOLERANCE_MAX_MAGNITUDE and diff <= _ABSOLUTE_TOLERANCE:
        return True
    return False


# How far two same-concept figures may diverge and still be "the same story".
# Sized to the real basis gaps: $0.09 vs $0.04 per $1 raised is the widest
# observed (0.56), and 10.7 vs 12.84 months is 0.17.
_SAME_STORY_MAX_DIVERGENCE = 0.6


def _same_story(claim_value: Any, source_value: Any) -> bool:
    """Would a donor read these two figures as saying the same thing?

    Bounds the methodology tolerance below. Two sources computing the same
    concept on different bases land near each other; they do not land on
    opposite sides of zero or an order of magnitude apart. 4.3 months of
    working capital versus -6.1 is solvent versus burning reserves, and 1.2
    versus 14.0 is a tenfold error -- neither is a basis gap, and a donor
    would want both flagged.

    Unparseable values fall back to True: with no numbers to compare, the
    field-scoped judgement is all we have.
    """
    a = _parse_number(claim_value)
    b = _parse_number(source_value)
    if a is None or b is None:
        return True
    if (a < 0) != (b < 0):
        return False
    widest = max(abs(a), abs(b))
    if widest == 0:
        return True
    return abs(a - b) / widest <= _SAME_STORY_MAX_DIVERGENCE


class FactualIssue(BaseModel):
    """Schema for a factual discrepancy from LLM."""

    field: str = Field(description="The field with the discrepancy")
    severity: str = Field(description="error, warning, or info")
    discrepancy_kind: str = Field(
        "unverifiable",
        description=(
            "contradiction = the source reports a different value; "
            "fabrication = the narrative states a number no source reports; "
            "unverifiable = the source data does not cover this claim; "
            "rounding = the values agree once rounding is allowed"
        ),
    )
    message: str = Field(description="Description of the discrepancy")
    claim_text: Optional[str] = Field(None, description="The narrative claim")
    claim_value: Optional[str] = Field(None, description="Value stated in claim")
    source_value: Optional[str] = Field(None, description="Value from source data")
    evidence: Optional[str] = Field(None, description="Why this is a problem")

    @field_validator("claim_value", "source_value", mode="before")
    @classmethod
    def convert_to_str(cls, v: Any) -> Optional[str]:
        """Convert numeric values to strings."""
        if v is None:
            return None
        return str(v)


class FactualVerificationResult(BaseModel):
    """Schema for factual verification LLM response."""

    issues: list[FactualIssue] = Field(default_factory=list)
    claims_checked: int = Field(0, description="Number of claims checked")
    claims_verified: int = Field(0, description="Number of claims verified as accurate")
    summary: str = Field("", description="Brief summary of results")


class FactualJudge(BaseJudge):
    """Validates that narrative claims match source data.

    Extracts factual claims (numbers, dates, names) from the narrative
    and verifies they match the provided source data.
    """

    @property
    def name(self) -> str:
        return "factual"

    @property
    def judge_type(self) -> JudgeType:
        return JudgeType.LLM

    def validate(
        self, output: dict[str, Any], context: dict[str, Any]
    ) -> JudgeVerdict:
        """Validate factual claims in the narrative.

        Args:
            output: Exported charity data with narrative
            context: Source data (Form 990, metrics, etc.)

        Returns:
            JudgeVerdict with any factual issues found
        """
        issues: list[ValidationIssue] = []
        cost_usd = 0.0
        metadata: dict[str, Any] = {}

        narrative = output.get("narrative", {})
        if not narrative:
            return self.create_verdict(
                passed=True,
                metadata={"note": "No narrative to validate"},
            )

        # Step 1: Quick deterministic checks for common issues
        quick_issues = self._quick_checks(output, context)
        issues.extend(quick_issues)

        # Step 2: LLM-based claim extraction and verification (with retry for rate limits)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                llm_result = self._verify_claims_with_llm(output, context)
                if llm_result:
                    issues.extend(llm_result.issues)
                    cost_usd = llm_result.cost
                    metadata["claims_checked"] = llm_result.claims_checked
                    metadata["claims_verified"] = llm_result.claims_verified
                break  # Success, exit retry loop
            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = "rate" in error_str or "429" in error_str or "quota" in error_str
                is_truncated = any(m in error_str for m in _TRUNCATED_RESPONSE_MARKERS)

                if (is_rate_limit or is_truncated) and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 5  # 5s, 10s, 20s
                    cause = "Truncated response" if is_truncated else "Rate limit hit"
                    logger.warning(f"{cause}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue

                logger.error(f"Factual judge LLM verification failed: {e}")
                self.add_issue(
                    issues,
                    Severity.ERROR,
                    "llm_verification",
                    f"Could not complete LLM verification: {str(e)[:100]}",
                )
                metadata["llm_failed"] = True
                break

        # Determine pass/fail
        error_count = len([i for i in issues if i.severity == Severity.ERROR])
        passed = error_count == 0

        return self.create_verdict(
            passed=passed,
            issues=issues,
            cost_usd=cost_usd,
            metadata=metadata,
        )

    def _quick_checks(
        self, output: dict[str, Any], context: dict[str, Any]
    ) -> list[ValidationIssue]:
        """Perform quick deterministic checks without LLM.

        Checks obvious mismatches between output and context.
        """
        issues: list[ValidationIssue] = []

        # Check key financial metrics if both exist
        evaluation = output.get("evaluation", {})
        financials = output.get("financials", {})
        source_metrics = context.get("metrics", {})

        # Check AMAL score consistency
        if "amal_score" in evaluation and "amal_score" in source_metrics:
            if evaluation["amal_score"] != source_metrics["amal_score"]:
                self.add_issue(
                    issues,
                    Severity.ERROR,
                    "amal_score",
                    f"AMAL score mismatch: output={evaluation['amal_score']}, source={source_metrics['amal_score']}",
                )

        # Check wallet tag consistency
        if "wallet_tag" in evaluation and "wallet_tag" in source_metrics:
            if evaluation["wallet_tag"] != source_metrics["wallet_tag"]:
                self.add_issue(
                    issues,
                    Severity.ERROR,
                    "wallet_tag",
                    f"Wallet tag mismatch: output={evaluation['wallet_tag']}, source={source_metrics['wallet_tag']}",
                )

        # Check program expense ratio bounds
        ratio = financials.get("program_expense_ratio")
        if ratio is not None:
            if ratio < 0 or ratio > 1.0:
                self.add_issue(
                    issues,
                    Severity.ERROR,
                    "program_expense_ratio",
                    f"Program expense ratio out of bounds: {ratio}",
                )

        # Strategic evaluation consistency checks
        # (only run when evaluation contains strategic keys — i.e., strategic variant)
        if "total_score" in evaluation and "strategic_score" in source_metrics:
            if evaluation["total_score"] != source_metrics["strategic_score"]:
                self.add_issue(
                    issues,
                    Severity.ERROR,
                    "strategic_score",
                    f"Strategic score mismatch: output={evaluation['total_score']}, "
                    f"source={source_metrics['strategic_score']}",
                )

        if "archetype" in evaluation and "archetype" in source_metrics:
            if evaluation["archetype"] != source_metrics["archetype"]:
                self.add_issue(
                    issues,
                    Severity.ERROR,
                    "archetype",
                    f"Archetype mismatch: output={evaluation['archetype']}, "
                    f"source={source_metrics['archetype']}",
                )

        # Check strategic dimension score consistency
        if "dimensions" in evaluation and "strategic_dimensions" in source_metrics:
            output_dims = evaluation["dimensions"]
            source_dims = source_metrics["strategic_dimensions"]
            for dim_name in ["resilience", "leverage", "future_proofing", "competence"]:
                out_val = output_dims.get(dim_name)
                src_val = source_dims.get(dim_name)
                if out_val is not None and src_val is not None and out_val != src_val:
                    self.add_issue(
                        issues,
                        Severity.ERROR,
                        f"strategic_dimension_{dim_name}",
                        f"Strategic {dim_name} mismatch: output={out_val}, source={src_val}",
                    )

        return issues

    def _verify_claims_with_llm(
        self, output: dict[str, Any], context: dict[str, Any]
    ) -> Optional["LLMFactualResult"]:
        """Use LLM to extract and verify factual claims.

        Returns structured result with issues and cost.
        """
        try:
            prompt = self.format_prompt(output, context)

            client = self.get_llm_client()
            # temperature=0 for reproducibility: a publication gate must not
            # change its mind on identical input. Measured at the client
            # default of 0.1, the same stored narrative judged three times
            # returned [1, 1, 0] errors -- the charity published or not on
            # a dice roll. Long structured outputs amplify this: one
            # divergent token early re-rolls the whole issue list.
            response = client.generate(
                prompt=prompt,
                json_mode=True,
                json_schema=FactualVerificationResult.model_json_schema(),
                temperature=0.0,
            )

            # Strip markdown if present
            json_text = self.strip_markdown_json(response.text)
            result = FactualVerificationResult.model_validate_json(json_text)

            # Convert to ValidationIssues
            issues = []
            for issue in result.issues:
                try:
                    severity = Severity(issue.severity.lower())
                except ValueError:
                    # The model put something else in the field -- it has been
                    # seen echoing a discrepancy_kind here. Do not let a typo
                    # in OUR schema abandon the whole verification and surface
                    # as a blocking "could not complete" against the charity.
                    logger.warning(
                        "factual judge returned an unrecognised severity %r for field %r; "
                        "treating as warning",
                        issue.severity,
                        issue.field,
                    )
                    severity = Severity.WARNING
                # Three gates, all because prompt guidance alone did not hold.
                # First: numbers that agree once rounding is allowed are never
                # a defect, whatever the model concluded. Second: only a
                # contradiction or a fabrication describes a fault in the
                # narrative -- "the source data does not cover this" is a
                # statement about our evidence and must not block publication.
                # Third: a real disagreement on a field where we and Charity
                # Navigator compute the same concept on different bases is
                # not a fault either -- see _METHODOLOGY_DIVERGENT_FIELD_RE.
                # Fourth: the wallet-tag/zakat-claim comparison is already
                # settled deterministically above, so the model's second
                # opinion on it never blocks -- see _is_wallet_tag_agreement.
                if severity == Severity.ERROR:
                    if numeric_agreement(issue.claim_value, issue.source_value) is True:
                        severity = Severity.INFO
                    elif issue.discrepancy_kind not in BLOCKING_DISCREPANCY_KINDS:
                        severity = Severity.WARNING
                    elif is_methodology_divergent(
                        f"{issue.field} {issue.message}"
                    ) and _same_story(issue.claim_value, issue.source_value):
                        severity = Severity.WARNING
                    elif _is_wallet_tag_agreement(issue.field, issue.message):
                        severity = Severity.WARNING
                details = {}
                if issue.claim_value:
                    details["claim_value"] = issue.claim_value
                if issue.source_value:
                    details["source_value"] = issue.source_value

                issues.append(
                    ValidationIssue(
                        severity=severity,
                        field=issue.field,
                        message=issue.message,
                        details=details if details else None,
                        evidence=issue.evidence,
                    )
                )

            return LLMFactualResult(
                issues=issues,
                claims_checked=result.claims_checked,
                claims_verified=result.claims_verified,
                cost=response.cost_usd or 0.0,
            )

        except Exception as e:
            logger.error(f"LLM factual verification failed: {e}")
            raise


class LLMFactualResult:
    """Result from LLM factual verification."""

    def __init__(
        self,
        issues: list[ValidationIssue],
        claims_checked: int,
        claims_verified: int,
        cost: float,
    ):
        self.issues = issues
        self.claims_checked = claims_checked
        self.claims_verified = claims_verified
        self.cost = cost
