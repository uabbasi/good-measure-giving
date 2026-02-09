"""
Benchmark Service - Compute peer benchmarks, find similar orgs, extract filing trends.

Provides comparative context for rich narratives by:
1. Parsing pilot_charities.txt (including commented lines) for benchmark pool
2. Computing cause-area benchmarks from pilot cohort
3. Finding similar organizations by cause + revenue tier
4. Extracting 3-year filing trends from ProPublica data
"""

import logging
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..db.client import execute_query
from ..db.repository import CharityRepository, RawDataRepository

logger = logging.getLogger(__name__)

# Industry standard benchmarks (fallback when peer group is too small)
INDUSTRY_BENCHMARKS = {
    "program_expense_ratio": 0.75,
    "admin_ratio": 0.15,
    "fundraising_ratio": 0.10,
}


@dataclass
class PilotCharity:
    """Charity from pilot_charities.txt."""

    name: str
    ein: str
    url: Optional[str]
    cn_rating: Optional[int]  # Extracted from comments like "100% CN"
    is_commented: bool  # True if line was commented out


@dataclass
class CauseBenchmarks:
    """Benchmarks for a cause area."""

    cause_area: str
    peer_count: int
    program_expense_ratio_median: Optional[float]
    program_expense_ratio_industry: float
    revenue_median: Optional[float]
    cn_score_median: Optional[float]


@dataclass
class SimilarOrg:
    """A similar organization for comparison."""

    ein: str
    name: str
    revenue: Optional[float]
    program_expense_ratio: Optional[float]
    differentiator: str  # Factual description (e.g., "Same category, shares tags: youth, usa")
    similarity_score: int = 0  # 0-100 score for ranking


@dataclass
class FilingTrends:
    """3-year filing trend data."""

    years: list[int]
    revenue: list[Optional[float]]
    expenses: list[Optional[float]]
    net_assets: list[Optional[float]]
    revenue_cagr_3yr: Optional[float]


def parse_pilot_charities(include_commented: bool = True) -> list[PilotCharity]:
    """
    Parse pilot_charities.txt and extract all charities.

    Args:
        include_commented: If True, include commented-out charities (for benchmarks)

    Returns:
        List of PilotCharity objects
    """
    pilot_file = Path(__file__).parent.parent.parent / "pilot_charities.txt"
    if not pilot_file.exists():
        logger.warning(f"pilot_charities.txt not found at {pilot_file}")
        return []

    charities = []
    cn_pattern = re.compile(r"(\d+)%\s*CN")  # Match "100% CN", "85% CN", etc.

    with open(pilot_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # Check if commented
            is_commented = line.startswith("#")
            if is_commented:
                if not include_commented:
                    continue
                # Remove leading # and whitespace
                line = line.lstrip("#").strip()
                # Skip pure comment lines (no pipe delimiter)
                if "|" not in line:
                    continue

            # Parse: Name | EIN | URL | Comments
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 2:
                continue

            name = parts[0]
            ein = parts[1] if len(parts) > 1 else ""
            url = parts[2] if len(parts) > 2 and parts[2] else None

            # Extract CN rating from comments
            cn_rating = None
            if len(parts) > 4:
                cn_match = cn_pattern.search(parts[4])
                if cn_match:
                    cn_rating = int(cn_match.group(1))

            # Skip if no valid EIN
            if not ein or not re.match(r"\d{2}-\d{7}", ein):
                continue

            charities.append(
                PilotCharity(
                    name=name,
                    ein=ein,
                    url=url,
                    cn_rating=cn_rating,
                    is_commented=is_commented,
                )
            )

    logger.info(f"Parsed {len(charities)} charities from pilot_charities.txt")
    return charities


def compute_cause_benchmarks(cause_area: str) -> CauseBenchmarks:
    """
    Compute benchmarks for a cause area from pilot cohort.

    Args:
        cause_area: Cause area to compute benchmarks for (e.g., "HUMANITARIAN")

    Returns:
        CauseBenchmarks with peer median and industry standard
    """
    # Query all charities with this cause area using DoltDB
    peers = (
        execute_query(
            """
        SELECT charity_ein, detected_cause_area, program_expense_ratio,
               total_revenue, charity_navigator_score
        FROM charity_data
        WHERE detected_cause_area = %s
        """,
            (cause_area,),
            fetch="all",
        )
        or []
    )

    peer_count = len(peers)

    # Extract values for median calculation
    program_ratios = [p["program_expense_ratio"] for p in peers if p.get("program_expense_ratio")]
    revenues = [p["total_revenue"] for p in peers if p.get("total_revenue")]
    cn_scores = [p["charity_navigator_score"] for p in peers if p.get("charity_navigator_score")]

    # Compute medians (require at least 3 peers)
    program_median = statistics.median(program_ratios) if len(program_ratios) >= 3 else None
    revenue_median = statistics.median(revenues) if len(revenues) >= 3 else None
    cn_median = statistics.median(cn_scores) if len(cn_scores) >= 3 else None

    return CauseBenchmarks(
        cause_area=cause_area,
        peer_count=peer_count,
        program_expense_ratio_median=program_median,
        program_expense_ratio_industry=INDUSTRY_BENCHMARKS["program_expense_ratio"],
        revenue_median=revenue_median,
        cn_score_median=cn_median,
    )


# Minimum similarity score threshold - below this, matches aren't meaningful
MIN_SIMILARITY_SCORE = 50


def find_similar_orgs(
    ein: str,
    cause_area: str,
    revenue: Optional[float],
    limit: int = 3,
    primary_category: Optional[str] = None,
    size_tier: Optional[str] = None,
    cause_tags: Optional[list[str]] = None,
    program_focus_tags: Optional[list[str]] = None,
) -> list[SimilarOrg]:
    """
    Find similar organizations using multi-factor similarity scoring.

    Similarity is computed deterministically based on:
    - Primary category match (25 pts)
    - Program focus tags (15 pts per shared tag, max 30)
    - Shared cause tags (10 pts per tag, max 20)
    - Same size tier (10 pts)
    - Revenue proximity within 2x (15 pts)

    Cross-category matching: Organizations with matching program_focus_tags
    can be matched even if their primary_category differs, enabling discovery
    of functionally similar orgs across category boundaries.

    Args:
        ein: EIN of the target charity (to exclude from results)
        cause_area: Fallback cause area if primary_category not available
        revenue: Target charity revenue (for proximity scoring)
        limit: Max number of similar orgs to return
        primary_category: More granular category (e.g., BASIC_NEEDS, EDUCATION_HIGHER)
        size_tier: Nonprofit size tier (small_nonprofit, mid_nonprofit, large_nonprofit)
        cause_tags: List of tags like ["faith-based", "muslim-led", "youth"]
        program_focus_tags: List of program focus tags like ["arts-culture-media", "advocacy-legal"]

    Returns:
        List of SimilarOrg objects sorted by similarity score.
        Empty list if no matches above MIN_SIMILARITY_SCORE threshold.
    """
    charity_names_repo = CharityRepository()

    # Query peers using DoltDB
    # If we have program_focus_tags, include broader matches (cross-category)
    if program_focus_tags and len(program_focus_tags) > 0:
        # Include charities that share program_focus_tags OR category
        peers = (
            execute_query(
                """
            SELECT charity_ein, detected_cause_area, primary_category,
                   nonprofit_size_tier, cause_tags, program_focus_tags,
                   program_expense_ratio, total_revenue
            FROM charity_data
            WHERE charity_ein != %s
            """,
                (ein,),
                fetch="all",
            )
            or []
        )
    elif primary_category:
        peers = (
            execute_query(
                """
            SELECT charity_ein, detected_cause_area, primary_category,
                   nonprofit_size_tier, cause_tags, program_focus_tags,
                   program_expense_ratio, total_revenue
            FROM charity_data
            WHERE primary_category = %s AND charity_ein != %s
            """,
                (primary_category, ein),
                fetch="all",
            )
            or []
        )
    else:
        peers = (
            execute_query(
                """
            SELECT charity_ein, detected_cause_area, primary_category,
                   nonprofit_size_tier, cause_tags, program_focus_tags,
                   program_expense_ratio, total_revenue
            FROM charity_data
            WHERE detected_cause_area = %s AND charity_ein != %s
            """,
                (cause_area, ein),
                fetch="all",
            )
            or []
        )

    if not peers:
        return []

    # Score each peer
    scored_peers = []
    for peer in peers:
        score, shared_tags, shared_focus = _compute_similarity_score(
            peer=peer,
            target_revenue=revenue,
            target_size_tier=size_tier,
            target_tags=cause_tags or [],
            target_category=primary_category,
            target_program_focus_tags=program_focus_tags or [],
        )
        # Only include peers above minimum threshold
        if score >= MIN_SIMILARITY_SCORE:
            scored_peers.append((peer, score, shared_tags, shared_focus))

    # Sort by similarity score (highest first)
    scored_peers.sort(key=lambda x: x[1], reverse=True)

    # Build results with factual differentiators
    similar = []
    for peer, score, shared_tags, shared_focus in scored_peers[:limit]:
        peer_ein = peer["charity_ein"]

        # Get name from charities table
        charity_info = charity_names_repo.get(peer_ein)
        name = charity_info["name"] if charity_info else peer_ein

        # Build factual differentiator
        differentiator = _build_factual_differentiator(
            peer=peer,
            target_revenue=revenue,
            target_size_tier=size_tier,
            shared_tags=shared_tags,
            shared_focus_tags=shared_focus,
        )

        similar.append(
            SimilarOrg(
                ein=peer_ein,
                name=name,
                revenue=peer.get("total_revenue"),
                program_expense_ratio=peer.get("program_expense_ratio"),
                differentiator=differentiator,
                similarity_score=score,
            )
        )

    return similar


def _compute_similarity_score(
    peer: dict,
    target_revenue: Optional[float],
    target_size_tier: Optional[str],
    target_tags: list[str],
    target_category: Optional[str] = None,
    target_program_focus_tags: Optional[list[str]] = None,
) -> tuple[int, list[str], list[str]]:
    """
    Compute similarity score (0-100) for a peer organization.

    New scoring (100 pts total):
    - Primary category match: 25 pts (down from 40)
    - Program focus tags: 15 pts per shared tag (max 30) - NEW
    - Shared cause tags: 10 pts per tag (max 20, down from 30)
    - Same size tier: 10 pts (down from 15)
    - Revenue proximity (within 2x): 15 pts (unchanged)

    Cross-category matching:
    - If program_focus_tags match, orgs can score well even without
      category match, enabling discovery of functionally similar orgs.

    Returns:
        Tuple of (score, list of shared cause_tags, list of shared program_focus_tags)
    """
    score = 0
    shared_tags = []
    shared_focus_tags = []

    # Primary category match (25 pts)
    peer_category = peer.get("primary_category")
    if peer_category and target_category and peer_category == target_category:
        score += 25

    # Program focus tags (15 pts each, max 30) - NEW
    # This enables cross-category matching for functionally similar orgs
    peer_focus_tags = peer.get("program_focus_tags") or []
    target_focus = target_program_focus_tags or []

    # Handle JSON deserialization (might be string)
    if isinstance(peer_focus_tags, str):
        import json

        try:
            peer_focus_tags = json.loads(peer_focus_tags)
        except (json.JSONDecodeError, TypeError):
            peer_focus_tags = []

    if peer_focus_tags and target_focus:
        shared_focus_tags = [t for t in target_focus if t in peer_focus_tags]
        focus_score = min(len(shared_focus_tags) * 15, 30)
        score += focus_score

    # Shared cause tags (10 pts each, max 20)
    peer_tags = peer.get("cause_tags") or []

    # Handle JSON deserialization (might be string)
    if isinstance(peer_tags, str):
        import json

        try:
            peer_tags = json.loads(peer_tags)
        except (json.JSONDecodeError, TypeError):
            peer_tags = []

    if peer_tags and target_tags:
        shared_tags = [t for t in target_tags if t in peer_tags]
        tag_score = min(len(shared_tags) * 10, 20)
        score += tag_score

    # Same size tier (10 pts)
    peer_tier = peer.get("nonprofit_size_tier")
    if peer_tier and target_size_tier and peer_tier == target_size_tier:
        score += 10

    # Revenue proximity (15 pts if within 2x)
    peer_revenue = peer.get("total_revenue")
    if peer_revenue and target_revenue and target_revenue > 0:
        ratio = peer_revenue / target_revenue
        if 0.5 <= ratio <= 2.0:
            score += 15

    return score, shared_tags, shared_focus_tags


def _build_factual_differentiator(
    peer: dict,
    target_revenue: Optional[float],
    target_size_tier: Optional[str],
    shared_tags: list[str],
    shared_focus_tags: Optional[list[str]] = None,
) -> str:
    """
    Build a factual differentiator string describing the similarity.

    Examples:
    - "Same size, shares: youth, usa"
    - "Larger organization in same category"
    - "Similar focus and revenue"
    - "Similar program focus: arts-culture-media"
    """
    parts = []

    # Program focus (most important - put first if present)
    if shared_focus_tags:
        displayed_focus = shared_focus_tags[:2]
        # Make tags more readable (replace hyphens with spaces)
        readable_tags = [t.replace("-", " ") for t in displayed_focus]
        parts.append(f"Similar focus: {', '.join(readable_tags)}")

    # Size comparison
    peer_tier = peer.get("nonprofit_size_tier")
    peer_revenue = peer.get("total_revenue")

    if peer_tier and target_size_tier:
        if peer_tier == target_size_tier:
            parts.append("same size")
        elif peer_tier == "large_nonprofit" and target_size_tier != "large_nonprofit":
            parts.append("larger organization")
        elif peer_tier == "small_nonprofit" and target_size_tier != "small_nonprofit":
            parts.append("smaller organization")

    # Revenue comparison (if no size tier comparison made and no focus tags)
    if len(parts) < 2 and peer_revenue and target_revenue:
        ratio = peer_revenue / target_revenue if target_revenue > 0 else 1
        if ratio > 1.5:
            parts.append("larger scale")
        elif ratio < 0.67:
            parts.append("smaller scale")
        elif not shared_focus_tags:  # Only add if no focus tags shown
            parts.append("similar size")

    # Shared cause tags (show up to 2, only if no focus tags)
    if shared_tags and not shared_focus_tags:
        displayed_tags = shared_tags[:2]
        parts.append(f"shares: {', '.join(displayed_tags)}")

    # Fallback
    if not parts:
        parts.append("Same category")

    result = ", ".join(parts)
    # Capitalize first letter only
    return result[0].upper() + result[1:] if result else "Same category"


def extract_filing_trends(filing_history: list[dict]) -> FilingTrends:
    """
    Extract 3-year filing trends from ProPublica filing_history.

    Args:
        filing_history: List of filing records from ProPublica

    Returns:
        FilingTrends with yearly data and CAGR
    """
    if not filing_history:
        return FilingTrends(
            years=[],
            revenue=[],
            expenses=[],
            net_assets=[],
            revenue_cagr_3yr=None,
        )

    # Sort by tax year descending
    sorted_filings = sorted(filing_history, key=lambda f: f.get("tax_year", 0), reverse=True)

    # Take up to 3 most recent years
    recent = sorted_filings[:3]

    # Reverse to chronological order (oldest first)
    recent.reverse()

    years = [f.get("tax_year") for f in recent]
    revenue = [f.get("total_revenue") for f in recent]
    expenses = [f.get("total_expenses") for f in recent]
    net_assets = [f.get("net_assets") for f in recent]

    # Compute 3-year CAGR if we have at least 2 years of revenue
    revenue_cagr = None
    valid_revenues = [(y, r) for y, r in zip(years, revenue) if r and r > 0]
    if len(valid_revenues) >= 2:
        first_year, first_rev = valid_revenues[0]
        last_year, last_rev = valid_revenues[-1]
        years_diff = last_year - first_year
        if years_diff > 0 and first_rev > 0:
            revenue_cagr = ((last_rev / first_rev) ** (1 / years_diff) - 1) * 100

    return FilingTrends(
        years=years,
        revenue=revenue,
        expenses=expenses,
        net_assets=net_assets,
        revenue_cagr_3yr=round(revenue_cagr, 1) if revenue_cagr else None,
    )


def get_filing_history(ein: str) -> list[dict]:
    """
    Get filing history from ProPublica raw data.

    Args:
        ein: Charity EIN

    Returns:
        List of filing records
    """
    raw_repo = RawDataRepository()

    # Get ProPublica data using DoltDB repository method
    result = raw_repo.get_by_source(ein, "propublica")

    if not result:
        return []

    parsed = result.get("parsed_json") or {}
    propublica = parsed.get("propublica_990") or {}

    return propublica.get("filing_history", [])
