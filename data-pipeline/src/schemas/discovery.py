"""Shared TypedDict contract between discovery producers and consumers.

Producers (5 discovery services) emit dicts via to_dict().
Consumers (judges, aggregator, narrative generator, citation service)
read those dicts with .get().

This module is the single source of truth for key names, preventing
the class of bugs where consumers guess a key that doesn't exist.
"""

from typing import TypedDict

# ── Section key constants ──────────────────────────────────────────
# Used by streaming_runner to assemble discovered_profile,
# and by consumers to look up sections.
SECTION_ZAKAT = "zakat"
SECTION_EVALUATIONS = "evaluations"
SECTION_OUTCOMES = "outcomes"
SECTION_THEORY_OF_CHANGE = "theory_of_change"
SECTION_AWARDS = "awards"


# ── Per-section TypedDicts ─────────────────────────────────────────
# Keys match the current to_dict() output of each discovery service.
# total=False because producers may omit optional fields.


class ZakatDict(TypedDict, total=False):
    accepts_zakat: bool
    accepts_zakat_evidence: str | None
    accepts_zakat_url: str | None
    zakat_categories_served: list[str]
    zakat_verification_confidence: float
    zakat_verification_sources: int
    direct_page_verified: bool


class EvaluationsDict(TypedDict, total=False):
    third_party_evaluated: bool
    evaluators: list[dict]  # [{name, rating, year, url, firm}]
    evidence: str | None
    confidence: float


class OutcomesDict(TypedDict, total=False):
    has_reported_outcomes: bool
    metrics: list[dict]  # [{metric, value, year}]
    evidence: str | None
    confidence: float


class TheoryOfChangeDict(TypedDict, total=False):
    has_theory_of_change: bool
    url: str | None
    type: str | None  # "theory_of_change", "logic_model", "impact_framework"
    evidence: str | None
    confidence: float


class AwardsDict(TypedDict, total=False):
    has_awards: bool
    awards: list[dict]  # [{name, issuer, year}]
    evidence: str | None
    confidence: float


# ── Envelope ───────────────────────────────────────────────────────


class DiscoveredProfileDict(TypedDict, total=False):
    ein: str
    charity_name: str
    website_url: str | None
    discovered_at: str
    zakat: ZakatDict | None
    evaluations: EvaluationsDict | None
    outcomes: OutcomesDict | None
    theory_of_change: TheoryOfChangeDict | None
    awards: AwardsDict | None
