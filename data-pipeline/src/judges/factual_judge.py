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
from src.llm.llm_client import TASK_MODELS, LLMClient, LLMTask
from src.utils.source_trust import field_group, published_column_for

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


# Financial figures whose value legitimately differs year to year. Founding year
# and similar identity fields are excluded: for those, two years IS the finding.
_YEAR_VARYING_FINANCIAL_FIELD_RE = re.compile(
    r"revenue|expense|contribution|asset|liabilit|net_assets|working.?capital",
    re.IGNORECASE,
)
# A bare four-digit year, not part of a larger number ("$2,024" / "$2024500").
# The trailing guard rejects a comma only when digits follow it, so an ordinary
# prose comma ("for FY2024, which matches...") still leaves the year visible.
_FISCAL_YEAR_RE = re.compile(r"(?<![\d,$.])(20[1-3]\d)(?!,?\d)")


def _is_cross_fiscal_year_comparison(field: str, message: str) -> bool:
    """Is this finding just two different fiscal years being compared?

    ProPublica's latest filing routinely lags Charity Navigator by a year, so the
    same charity legitimately reports different revenue for FY2023 and FY2024, and a
    narrative citing the newer year is correct. The judge kept reading that gap as a
    contradiction across three separate charities (27-3175543, 75-2882187,
    77-0442850) even while naming the gap itself ("the narrative's figure appears to
    be from FY2024 data"), and prompt guidance did not stop it.

    Deterministic marker: the message names two or more DISTINCT fiscal years on a
    field whose value varies by year. Same-year disagreements, year-free messages,
    and identity fields like founded_year are untouched.
    """
    if not _YEAR_VARYING_FINANCIAL_FIELD_RE.search(field or ""):
        return False
    return len(set(_FISCAL_YEAR_RE.findall(message or ""))) >= 2


def _is_wallet_tag_agreement(field: str, message: str) -> bool:
    """Is this finding the wallet-tag/zakat-claim comparison _quick_checks owns?"""
    text = f"{field} {message}"
    return bool(_WALLET_TAG_AGREEMENT_RE.search(text)) and "zakat" in text.lower()


# A response that will not parse fell through to "Could not complete LLM
# verification", which fails closed and withheld the charity (01-0548371).
# Two distinct causes, so two responses:
#   - a genuinely clipped generation is transient, the same class as a 429,
#     and a retry gets a clean one;
#   - a degeneration loop is not. On 01-0548371 the model emitted 64,000+
#     literal '0' characters inside one JSON string -- 67,719 chars,
#     byte-identical across three attempts at temperature 0, from a prompt
#     containing no such run. The same model cannot answer differently, so
#     the retry escalates to the stronger tier. score_judge.py already
#     escalates for the same class of flash-lite failure (see its
#     judge_model_override).
# Retrying is not ignoring: exhausting the retries still blocks.
_TRUNCATED_RESPONSE_MARKERS = ("invalid json", "json_invalid", "eof while parsing")

_ESCALATION_MODEL = "gemini-2.5-flash"

# Independent LLM rolls for the error-consensus vote (odd number → clean majority).
# Mirrors score_judge: this judge gates publication on interpretive prose, which
# flips roll to roll even at temperature 0.
CONSENSUS_ROLLS = 3

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


def _normalized_text(value: Any) -> str:
    """Lowercased, whitespace-collapsed text, or "" when the value is absent."""
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def _published_value(field: Any, published: Any) -> Optional[float]:
    """What we actually published for this field, as a number."""
    if not isinstance(published, dict):
        return None
    if field_group(field) is None:
        return None
    column = published_column_for(field)
    if column is None:
        return None
    metrics = published.get("metrics_json")
    metrics = metrics if isinstance(metrics, dict) else {}
    for holder in (published, metrics):
        if isinstance(holder, dict) and holder.get(column) is not None:
            return _parse_number(holder[column])
    return None


# The model frequently leaves claim_value null and states both figures in prose:
# "The narrative claims FY2025 revenue of $3,145,617, but the source data shows
# $3,572,587." Only the first of those is the narrative's claim, so matching any
# number in the message would also match the figure the judge is citing AGAINST
# it — which would wave through real fabrications. This picks out the number the
# sentence attributes to the narrative, and nothing else.
_NARRATIVE_CLAIM_RE = re.compile(
    r"(?:narrative|report|page|it)\s+(?:claims?|states?|says?|reports?|indicates?)"
    r"[^.;]{0,80}?(-?\$?\s?\d[\d,]*\.?\d*)\s*%?",
    re.IGNORECASE,
)


# "The narrative claims FY2025 revenue of $3,145,617" — the first number after
# "claims" is the fiscal year, not the claim. Years are removed before matching.
_YEAR_TOKEN_RE = re.compile(r"\bFY\s*\d{4}\b|\b(?:19|20)\d{2}\b", re.IGNORECASE)


def _claim_stated_in_message(message: Any) -> Optional[float]:
    """The figure a judge's prose attributes to the narrative itself."""
    text = _YEAR_TOKEN_RE.sub(" ", str(message or ""))
    match = _NARRATIVE_CLAIM_RE.search(text)
    return _parse_number(match.group(1)) if match else None


def claim_matches_published_value(
    field: Any, claim_value: Any, published: Any, message: Any = None
) -> bool:
    """Is the narrative faithfully reporting the figure we published?

    This is the whole answer to "the sources disagree". Which source a field
    comes from is settled before the judge runs, by src/utils/source_trust.py,
    and the disagreement is published as a discrepancy rather than hidden. So a
    narrative that reports our published figure is correct BY CONSTRUCTION, and
    a judge citing the source that lost the election is describing our
    provenance, not a defect in the page.

    EIN 45-5637293 is the case: ProPublica reported FY2023 revenue of
    $1,759,964 and Charity Navigator $100,000 for the same year. The election
    picked the filing, correctly, and the page was then withheld for
    "revenue diverges >80% across sources - likely wrong org".

    A claim that does NOT match what we published still blocks. That is
    fabrication, and no hierarchy excuses it.
    """
    claimed = _parse_number(claim_value)
    if claimed is None:
        claimed = _claim_stated_in_message(message)
    if claimed is None:
        return False
    ours = _published_value(field, published)
    if ours is None:
        return False
    # Ratios are published as fractions and written as percentages.
    return (
        numeric_agreement(claimed, ours) is True
        or numeric_agreement(claimed, ours * 100) is True
    )


# The program ratio carries two legitimate values since this run's GIK fix: the
# filed ratio Charity Navigator reports, and the cash-adjusted ratio we publish and
# score when gifts-in-kind inflate the filed one.
_RATIO_FIELD_RE = re.compile(r"program.{0,3}(?:expense.{0,3})?ratio", re.IGNORECASE)
# Measured in PERCENTAGE POINTS. _same_story's 60% relative bound would swallow
# 96.5% vs 47.5%, which is precisely the gap donors must see.
_RATIO_BASIS_GAP_MAX_POINTS = 10.0


def _as_percentage_points(value: Any) -> Optional[float]:
    """A ratio on a 0-100 scale, whether it arrived as 0.475 or as 47.5%.

    Both spellings occur for the same field in the same judge output. Anything
    within [-1, 1] is read as a fraction; a program ratio of literally 1% does not
    occur for these organizations, while 1.0 meaning 100% is common.
    """
    number = _parse_number(value)
    if number is None:
        return None
    return number * 100 if abs(number) <= 1 else number


def _is_ratio_basis_gap(field: str, claim_value: Any, source_value: Any) -> bool:
    """Two program-ratio figures close enough to be the same story told two ways.

    Justice Defenders' 58.5% against CN's 65.13% is a basis difference. UMR's
    96.48% against its 47.5% cash-adjusted ratio is not — that is "nearly all
    spending reaches programs" versus "less than half", the gap that earned it 0/5
    on Program Ratio, and it must keep blocking.
    """
    if not _RATIO_FIELD_RE.search(field or ""):
        return False
    a, b = _as_percentage_points(claim_value), _as_percentage_points(source_value)
    if a is None or b is None:
        return False
    if (a < 0) != (b < 0):
        return False
    return abs(a - b) <= _RATIO_BASIS_GAP_MAX_POINTS


def _currency_claim_against_a_percentage(message: str, claim_value: Any, source_value: Any) -> bool:
    """The two compared figures are a dollar amount and a percentage.

    Those are different quantities, so their difference is not a discrepancy. On
    EIN 27-3175543 the judge set claim='7.44' against source='47.5%' and wrote "the
    narrative claims a low cost per beneficiary of $7.44 ... but the cash-adjusted
    program expense ratio is only 47.5%" — a cost per person measured against a
    ratio. The prompt's "CRITICAL: Working Capital Units" section shows unit
    confusion is a known failure mode here; this is its deterministic form.

    Requires BOTH that the source is a percentage and that the claim actually
    appears as currency in the message, so two percentages or two dollar amounts
    (a real disagreement) are untouched.
    """
    if "%" not in str(source_value or ""):
        return False
    if "%" in str(claim_value or ""):
        return False
    number = _parse_number(claim_value)
    if number is None:
        return False
    rendered = f"{number:g}"
    return bool(re.search(rf"\$\s*{re.escape(rendered)}", message or ""))


def _values_are_textually_identical(claim_value: Any, source_value: Any) -> bool:
    """Both sides present and the same string once case/spacing are normalized.

    numeric_agreement covers this for numbers; it returns None for prose, so
    `claim='two members'` against `source='two members'` reached the gate as a
    blocking contradiction on EIN 23-7065716 — in a message that itself ended
    "which is not a contradiction".
    """
    a, b = _normalized_text(claim_value), _normalized_text(source_value)
    return bool(a) and a == b


def _unnamed_claim_against_a_source(claim_value: Any, source_value: Any) -> bool:
    """The judge produced a source value but never named what the narrative claimed.

    Without a claim there is no stated pair to contradict — on EIN 27-3175543 the
    judge blocked on `claim=None, source='0.475'` while the message objected to the
    narrative "mentioning a low cost per beneficiary and strong program outcomes",
    which is framing, not a competing figure.

    Deliberately one-directional. The MIRROR shape — a claim with no source — is
    what a fabrication looks like ("the narrative states $4.2M was distributed as
    zakat; the Form 990 reports no such program") and must keep blocking, as must
    a finding that names neither side, since the model states real contradictions
    in prose without filling the structured fields.
    """
    return not _normalized_text(claim_value) and bool(_normalized_text(source_value))


def _prose_claim_against_a_number(claim_value: Any, source_value: Any) -> bool:
    """Both sides present, but exactly one of them is a number.

    A qualitative claim cannot be numerically falsified without interpretation,
    and interpretation is the part that is unreliable: on EIN 27-3175543 the judge
    set claim='much of which is non-cash' against source='143021451' and called it
    an error in a sentence reading "which is supported by the source data".

    Two numbers are left to numeric_agreement, which can actually adjudicate them;
    two prose values are left alone, since those can genuinely contradict.
    """
    if not _normalized_text(claim_value) or not _normalized_text(source_value):
        return False
    claim_is_number = _parse_number(claim_value) is not None
    source_is_number = _parse_number(source_value) is not None
    return claim_is_number != source_is_number


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

        # Step 2: LLM verification, k=3 majority consensus on ERRORS.
        # temperature=0 was already set here for reproducibility ("a publication
        # gate must not change its mind on identical input") and it is not
        # sufficient: across two consecutive runs with a byte-identical
        # judge_content_hash, UMR (27-3175543) went 0 -> 1 errors, Rahima
        # (77-0442850) 1 -> 0, and the Muslim clinics association (93-2136609)
        # 0 -> 1. Same content, same code, different publication decision, and the
        # flipping errors were interpretive ("the narrative *implies* revenue is
        # primarily cash-based"). So gate on a majority instead of a single roll,
        # exactly as score_judge already does for the same reason. Warnings and
        # info never gate, so they come from the first completed roll.
        roll_results: list["LLMFactualResult"] = []
        for _ in range(CONSENSUS_ROLLS):
            roll = self._verify_claims_with_rate_limit_retry(output, context)
            if roll is not None:
                roll_results.append(roll)

        if roll_results:
            metadata["consensus_rolls"] = len(roll_results)
            metadata["claims_checked"] = roll_results[0].claims_checked
            metadata["claims_verified"] = roll_results[0].claims_verified
            cost_usd = sum(r.cost for r in roll_results)

            error_roll_count = sum(
                1 for r in roll_results if any(i.severity == Severity.ERROR for i in r.issues)
            )
            metadata["error_roll_count"] = error_roll_count
            majority = (len(roll_results) // 2) + 1
            if error_roll_count >= majority:
                # Errors are real — surface them from the roll that found the most.
                worst = max(
                    roll_results,
                    key=lambda r: sum(1 for i in r.issues if i.severity == Severity.ERROR),
                )
                issues.extend([i for i in worst.issues if i.severity == Severity.ERROR])
            issues.extend([i for i in roll_results[0].issues if i.severity != Severity.ERROR])
        else:
            # Fail CLOSED. A judge that completed no roll verified nothing, and
            # reporting error_count == 0 opened the publication gate on an
            # unchecked narrative — which is what the old `if llm_result:` path
            # did when verification returned None rather than raising.
            logger.error("Factual judge: all consensus rolls failed")
            self.add_issue(
                issues,
                Severity.ERROR,
                "llm_verification",
                "Could not complete LLM verification (no consensus roll completed)",
            )
            metadata["llm_failed"] = True

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

    def _escalated_client(self) -> "LLMClient":
        """A client on the stronger tier, for when the default judge model
        cannot produce a parseable response at all.

        Built fresh rather than replacing self._llm_client: judges are reused
        across charities, and one charity's degeneration must not silently
        move every later charity onto the more expensive model.
        """
        default_primary, default_fallbacks = TASK_MODELS[LLMTask.LLM_JUDGE]
        client = LLMClient(task=LLMTask.LLM_JUDGE, model=_ESCALATION_MODEL)
        client.fallback_models = [
            m for m in [default_primary, *default_fallbacks] if m != _ESCALATION_MODEL
        ]
        return client

    def _verify_claims_with_rate_limit_retry(
        self, output: dict[str, Any], context: dict[str, Any]
    ) -> Optional["LLMFactualResult"]:
        """One consensus roll, with the rate-limit/truncation retry around it.

        Returns None when this roll could not complete. A single failed roll is
        not an error on its own — `validate` only fails closed when EVERY roll
        fails, so one rate-limited roll no longer blocks a charity by itself.
        """
        max_retries = 3
        escalated: Optional[LLMClient] = None
        for attempt in range(max_retries):
            try:
                return self._verify_claims_with_llm(output, context, client=escalated)
            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = "rate" in error_str or "429" in error_str or "quota" in error_str
                is_truncated = any(m in error_str for m in _TRUNCATED_RESPONSE_MARKERS)

                if (is_rate_limit or is_truncated) and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 5  # 5s, 10s, 20s
                    if is_truncated and escalated is None:
                        # The same model at temperature 0 will return the same
                        # unparseable bytes, so change the model, not just the
                        # timing.
                        escalated = self._escalated_client()
                        cause = f"Unparseable response, escalating to {_ESCALATION_MODEL}"
                    else:
                        cause = "Truncated response" if is_truncated else "Rate limit hit"
                    logger.warning(f"{cause}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue

                logger.error(f"Factual judge LLM verification failed: {e}")
                return None
        return None

    def _verify_claims_with_llm(
        self,
        output: dict[str, Any],
        context: dict[str, Any],
        client: Optional["LLMClient"] = None,
    ) -> Optional["LLMFactualResult"]:
        """Use LLM to extract and verify factual claims.

        Returns structured result with issues and cost.
        """
        try:
            prompt = self.format_prompt(output, context)

            client = client or self.get_llm_client()
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
                    # Governing rule, ahead of everything below: a narrative
                    # reporting the figure we published is correct, whatever a
                    # source that lost the election says. Which source supplies
                    # a field is settled deterministically before the judge runs
                    # (src/utils/source_trust.py) and the disagreement is
                    # published as a discrepancy, so re-litigating it here can
                    # only withhold a page over our own provenance. The rules
                    # after this one are narrower shapes of the same mistake,
                    # each added after a regeneration surfaced it.
                    if claim_matches_published_value(
                        issue.field,
                        issue.claim_value,
                        context.get("charity_data"),
                        issue.message,
                    ):
                        severity = Severity.WARNING
                    elif numeric_agreement(issue.claim_value, issue.source_value) is True:
                        severity = Severity.INFO
                    elif issue.discrepancy_kind not in BLOCKING_DISCREPANCY_KINDS:
                        severity = Severity.WARNING
                    elif is_methodology_divergent(
                        f"{issue.field} {issue.message}"
                    ) and _same_story(issue.claim_value, issue.source_value):
                        severity = Severity.WARNING
                    elif _is_wallet_tag_agreement(issue.field, issue.message):
                        severity = Severity.WARNING
                    # Fifth: two different fiscal years being compared is not a
                    # narrative fault -- our sources cover different years and the
                    # narrative citing the newer one is correct.
                    elif _is_cross_fiscal_year_comparison(issue.field, issue.message):
                        severity = Severity.WARNING
                    # Sixth: an ERROR must be self-consistent to gate. The model
                    # routinely files verification NOTES as errors -- severity
                    # contradicting its own message ("which is not a
                    # contradiction", "which is supported by the source data") and
                    # its own claim/source pair. numeric_agreement above already
                    # catches the numeric form; these are the same failure in
                    # prose, which it cannot see.
                    elif _values_are_textually_identical(issue.claim_value, issue.source_value):
                        # Provable agreement, exactly like the numeric case.
                        severity = Severity.INFO
                    elif _unnamed_claim_against_a_source(issue.claim_value, issue.source_value):
                        severity = Severity.WARNING
                    elif _prose_claim_against_a_number(issue.claim_value, issue.source_value):
                        severity = Severity.WARNING
                    # Seventh: the filed and cash-adjusted program ratios are both
                    # ours and both legitimate, so a basis-sized gap between them
                    # is not a fault. Bounded in percentage points so the GIK gap
                    # donors must see (96.5% vs 47.5%) still blocks.
                    elif _is_ratio_basis_gap(issue.field, issue.claim_value, issue.source_value):
                        severity = Severity.WARNING
                    # Eighth: a dollar amount and a percentage are different
                    # quantities, so their difference is not a discrepancy.
                    elif _currency_claim_against_a_percentage(
                        issue.message, issue.claim_value, issue.source_value
                    ):
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
