"""Strategic Evidence - Deterministic signal extraction for the Strategic Believer lens.

Pure Python (no LLM). Scans CharityMetrics text corpus for keyword signals and
computes institutional maturity from structured fields.

Output is stored as charity_data.strategic_evidence (JSON column) and optionally
fed into the strategic classifier prompt for grounded context.

Signal categories match the strategic archetypes:
- leverage_signals: Training cascades, policy advocacy, match funding, research
- asset_signals: Schools, wells, hospitals, endowments, waqf, infrastructure
- sovereignty_signals: Local leadership, community governance, cooperative models
- resilience_signals: Job training, vocational, microfinance, livelihood programs
- institutional_maturity: 0-10 composite from age, staff, governance, audit, seal
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.parsers.charity_metrics_aggregator import CharityMetrics

# ============================================================================
# Keyword dictionaries for each signal category
# ============================================================================

LEVERAGE_KEYWORDS: dict[str, list[str]] = {
    "training cascade": ["train the trainer", "training of trainers", "training cascade", "peer educator"],
    "policy advocacy": ["policy advocacy", "legislative", "lobbying", "policy change", "systemic reform"],
    "match funding": ["matching gift", "match fund", "matched donation", "dollar-for-dollar"],
    "research impact": ["research", "evidence-based", "randomized", "rct", "peer-reviewed"],
    "curriculum": ["curriculum", "textbook", "open-source", "replicable model"],
    "technology platform": ["platform", "app", "digital tool", "open source", "scalable technology"],
}

ASSET_KEYWORDS: dict[str, list[str]] = {
    "school building": ["school", "classroom", "learning center", "education facility"],
    "water infrastructure": ["well", "borehole", "water system", "filtration", "water point"],
    "healthcare facility": ["hospital", "clinic", "health center", "medical facility"],
    "endowment": ["endowment", "waqf", "trust fund", "perpetual fund"],
    "housing": ["housing", "shelter construction", "permanent home", "building homes"],
    "agricultural asset": ["farm", "irrigation", "greenhouse", "livestock", "orchard"],
}

SOVEREIGNTY_KEYWORDS: dict[str, list[str]] = {
    "local leadership": ["local leadership", "community leader", "indigenous leader", "locally led"],
    "community governance": ["community governance", "village council", "community committee", "self-govern"],
    "cooperative model": ["cooperative", "co-op", "community-owned", "collective ownership"],
    "institutional building": ["institution building", "local organization", "community organization", "civic"],
    "capacity transfer": ["capacity building", "knowledge transfer", "skill transfer", "empowerment"],
}

RESILIENCE_KEYWORDS: dict[str, list[str]] = {
    "job training": ["job training", "vocational", "workforce development", "career training"],
    "microfinance": ["microfinance", "microloan", "micro-credit", "small business loan"],
    "livelihood": ["livelihood", "income generation", "self-employment", "entrepreneurship"],
    "education pathway": ["scholarship", "higher education", "degree program", "literacy"],
    "addiction recovery": ["recovery", "rehabilitation", "substance abuse", "addiction"],
    "financial literacy": ["financial literacy", "savings program", "financial education", "banking"],
}


def _scan_text_for_signals(text: str, keyword_dict: dict[str, list[str]]) -> list[str]:
    """Scan text corpus for keyword matches, returning matched signal labels."""
    text_lower = text.lower()
    signals = []
    for label, keywords in keyword_dict.items():
        if any(kw in text_lower for kw in keywords):
            signals.append(label)
    return signals


def _build_text_corpus(metrics: CharityMetrics) -> str:
    """Build searchable text from CharityMetrics text fields."""
    parts = [
        metrics.mission or "",
        " ".join(metrics.program_descriptions or []),
        " ".join(metrics.outcomes or []),
        metrics.theory_of_change or "",
        " ".join(metrics.programs or []),
    ]
    return " ".join(parts)


def _compute_institutional_maturity(metrics: CharityMetrics) -> tuple[int, list[str]]:
    """Compute institutional maturity score (0-10) from structured fields.

    Factors (each contributes points):
    - Organization age: 0-3 pts (0-5y=0, 5-15y=1, 15-30y=2, 30y+=3)
    - Employee count: 0-2 pts (0=0, 1-50=1, 50+=2)
    - Board independence: 0-2 pts (no board info=0, board exists=1, >50% independent=2)
    - Financial audit: 0-1 pt
    - Candid seal: 0-2 pts (none=0, bronze/silver=1, gold/platinum=2)
    """
    score = 0
    factors: list[str] = []

    # Organization age (0-3 pts)
    if metrics.founded_year:
        age = datetime.now(timezone.utc).year - metrics.founded_year
        if age >= 30:
            score += 3
            factors.append(f"Established {age} years (3/3)")
        elif age >= 15:
            score += 2
            factors.append(f"Mature {age} years (2/3)")
        elif age >= 5:
            score += 1
            factors.append(f"Growing {age} years (1/3)")
        else:
            factors.append(f"Young {age} years (0/3)")

    # Employee count (0-2 pts)
    if metrics.employees_count:
        if metrics.employees_count >= 50:
            score += 2
            factors.append(f"{metrics.employees_count} employees (2/2)")
        elif metrics.employees_count >= 1:
            score += 1
            factors.append(f"{metrics.employees_count} employees (1/2)")
    else:
        factors.append("Employee count unknown (0/2)")

    # Board independence (0-2 pts)
    if metrics.board_size and metrics.board_size > 0:
        score += 1
        if metrics.independent_board_members and metrics.board_size > 0:
            independence_ratio = metrics.independent_board_members / metrics.board_size
            if independence_ratio > 0.5:
                score += 1
                factors.append(f"Board: {metrics.independent_board_members}/{metrics.board_size} independent (2/2)")
            else:
                factors.append(f"Board: {metrics.independent_board_members}/{metrics.board_size} independent (1/2)")
        else:
            factors.append(f"Board size {metrics.board_size}, independence unknown (1/2)")
    else:
        factors.append("No board info (0/2)")

    # Financial audit (0-1 pt)
    if metrics.has_financial_audit:
        score += 1
        factors.append("Financial audit (1/1)")
    else:
        factors.append("No audit info (0/1)")

    # Candid seal (0-2 pts)
    seal = (metrics.candid_seal or "").lower()
    if seal in ("gold", "platinum"):
        score += 2
        factors.append(f"Candid {metrics.candid_seal} seal (2/2)")
    elif seal in ("bronze", "silver"):
        score += 1
        factors.append(f"Candid {metrics.candid_seal} seal (1/2)")
    else:
        factors.append("No Candid seal (0/2)")

    return min(score, 10), factors


@dataclass
class StrategicEvidence:
    """Deterministic strategic signals extracted from CharityMetrics.

    Stored as JSON in charity_data.strategic_evidence.
    Consumed by strategic classifier (optional) and rich strategic narrative.
    """

    leverage_signals: list[str] = field(default_factory=list)
    asset_signals: list[str] = field(default_factory=list)
    sovereignty_signals: list[str] = field(default_factory=list)
    resilience_signals: list[str] = field(default_factory=list)
    institutional_maturity: int = 0
    maturity_factors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize for JSON storage."""
        return {
            "leverage_signals": self.leverage_signals,
            "asset_signals": self.asset_signals,
            "sovereignty_signals": self.sovereignty_signals,
            "resilience_signals": self.resilience_signals,
            "institutional_maturity": self.institutional_maturity,
            "maturity_factors": self.maturity_factors,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> StrategicEvidence | None:
        """Reconstruct from stored dict."""
        if not data:
            return None
        try:
            return cls(**data)
        except (TypeError, KeyError):
            return None

    @property
    def total_signal_count(self) -> int:
        """Total number of signals detected across all categories."""
        return (
            len(self.leverage_signals)
            + len(self.asset_signals)
            + len(self.sovereignty_signals)
            + len(self.resilience_signals)
        )

    def format_for_prompt(self) -> str:
        """Format evidence for inclusion in LLM prompts."""
        parts = []
        if self.leverage_signals:
            parts.append(f"Leverage signals: {', '.join(self.leverage_signals)}")
        if self.asset_signals:
            parts.append(f"Asset signals: {', '.join(self.asset_signals)}")
        if self.sovereignty_signals:
            parts.append(f"Sovereignty signals: {', '.join(self.sovereignty_signals)}")
        if self.resilience_signals:
            parts.append(f"Resilience signals: {', '.join(self.resilience_signals)}")
        parts.append(f"Institutional maturity: {self.institutional_maturity}/10")
        return "\n".join(parts) if parts else "No strategic signals detected"


def compute_strategic_evidence(metrics: CharityMetrics) -> StrategicEvidence:
    """Extract deterministic strategic signals from CharityMetrics.

    Pure Python — no LLM calls. Scans text corpus for keyword signals
    and computes institutional maturity from structured fields.

    Args:
        metrics: Aggregated charity metrics

    Returns:
        StrategicEvidence with detected signals and maturity score
    """
    corpus = _build_text_corpus(metrics)

    leverage = _scan_text_for_signals(corpus, LEVERAGE_KEYWORDS)
    assets = _scan_text_for_signals(corpus, ASSET_KEYWORDS)
    sovereignty = _scan_text_for_signals(corpus, SOVEREIGNTY_KEYWORDS)
    resilience = _scan_text_for_signals(corpus, RESILIENCE_KEYWORDS)
    maturity, factors = _compute_institutional_maturity(metrics)

    return StrategicEvidence(
        leverage_signals=leverage,
        asset_signals=assets,
        sovereignty_signals=sovereignty,
        resilience_signals=resilience,
        institutional_maturity=maturity,
        maturity_factors=factors,
    )
