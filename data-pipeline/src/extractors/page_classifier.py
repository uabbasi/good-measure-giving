"""
Page classifier for URL scoring and page type classification.

V2 Dimension-Aligned Scoring:
- TRUST (25 pts): verification, transparency, governance, audits, 990s
- EVIDENCE (25 pts): outcomes, research, theory of change, evaluation, metrics
- EFFECTIVENESS (25 pts): programs, costs, efficiency, what-we-do
- FIT (25 pts): mission, beneficiaries, zakat, Islamic alignment
- PENALTY (-15 pts): blog, news, events (low signal-to-noise)

Total possible: 100 points

This module provides functionality to:
- Score URLs based on V2 dimension keywords in URL path, anchor text, title, and h1
- Classify pages into types (homepage, trust, evidence, effectiveness, fit, etc.)
- Select top-priority pages for crawling with dimension diversity
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

# Page types aligned with V2 dimensions
V2PageType = Literal[
    "homepage",
    "trust",        # financials, 990, transparency, governance
    "evidence",     # outcomes, research, evaluation, theory-of-change
    "effectiveness", # programs, what-we-do, services
    "fit",          # about, mission, zakat, beneficiaries
    "donate",       # donation pages (zakat claim detection)
    "other",
]


class PageScore(BaseModel):
    """URL scoring result for crawl prioritization - V2 dimension-aligned."""

    url: HttpUrl
    raw_score: int = Field(..., ge=0, le=100)
    page_type: V2PageType
    primary_dimension: Literal["trust", "evidence", "effectiveness", "fit", "none"] = "none"

    # Matched context sources for debugging
    matched_keywords: list[str] = Field(default_factory=list)
    matched_context: list[Literal["url", "link_text", "title", "h1", "content"]] = Field(default_factory=list)

    # V2 dimension breakdown
    breakdown: dict[str, int] = Field(default_factory=dict)  # {dimension: points}

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "url": "https://irusa.org/annual-report",
                "raw_score": 75,
                "page_type": "trust",
                "primary_dimension": "trust",
                "matched_keywords": ["annual-report", "financials"],
                "matched_context": ["url", "title"],
                "breakdown": {"trust": 25, "evidence": 10},
            }
        }
    )

    def is_high_priority(self) -> bool:
        """Check if score meets high-priority threshold (50+)."""
        return self.raw_score >= 50


class PageClassification(BaseModel):
    """Classification result for crawled page - V2 dimension-aligned."""

    url: HttpUrl
    classified_type: V2PageType
    confidence: Literal["high", "medium", "low"]
    keywords_matched: list[str] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "url": "https://irusa.org/annual-report",
                "classified_type": "trust",
                "confidence": "high",
                "keywords_matched": ["annual-report", "financials"],
            }
        }
    )

    def get_prompt_key(self) -> str:
        """Get YAML key for LLM prompt from classified type."""
        return f"{self.classified_type}_prompt"


class PageClassifier:
    """
    V2 Dimension-Aligned Classifier for charity website pages.

    Scoring aligned with V2 5-dimension evaluation framework:
    - TRUST (25 pts): verification, transparency, governance, audits
    - EVIDENCE (25 pts): outcomes, research, theory of change, evaluation
    - EFFECTIVENESS (25 pts): programs, costs, efficiency
    - FIT (25 pts): mission, beneficiaries, zakat alignment
    - PENALTY (-15 pts): blog, news, events (low signal-to-noise)

    URL patterns are grouped by dimension to ensure we capture data
    for each scoring category in the V2 evaluation.
    """

    # TRUST dimension (25 pts max) - verification, transparency, governance
    # Critical for: 990 data, audits, board oversight, Candid seals
    TRUST_KEYWORDS = {
        # Financial verification (highest priority)
        "990",
        "form-990",
        "form990",
        "annual-report",
        "annual-reports",
        "annualreport",
        "financials",
        "financial-statements",
        "financial-report",
        "audit",
        "audited",
        "auditor",
        # Transparency
        "transparency",
        "accountability",
        "disclosure",
        "open-data",
        # Governance
        "governance",
        "board",
        "board-of-directors",
        "trustees",
        "leadership",
        "executive-team",
        "officers",
        # Verification
        "candid",
        "guidestar",
        "platinum-seal",
        "gold-seal",
    }

    # EVIDENCE dimension (25 pts max) - outcomes, research, theory of change
    # Critical for: impact data, evaluation reports, methodology
    EVIDENCE_KEYWORDS = {
        # Outcomes and impact
        "impact",
        "outcomes",
        "results",
        "achievements",
        "success-stories",
        "our-impact",
        # Evaluation and research
        "evaluation",
        "evaluations",
        "research",
        "studies",
        "data",
        "metrics",
        "measurement",
        "monitoring",
        # Theory of change
        "theory-of-change",
        "logic-model",
        "methodology",
        "approach",
        "how-we-work",
        # Reports
        "impact-report",
        "impact-reports",
        "annual-review",
        "progress-report",
    }

    # EFFECTIVENESS dimension (25 pts max) - programs, costs, efficiency
    # Critical for: program expense ratio, cost per beneficiary
    EFFECTIVENESS_KEYWORDS = {
        # Programs
        "program",
        "programs",
        "programme",
        "programmes",
        "what-we-do",
        "our-work",
        "our-programs",
        "services",
        "initiatives",
        "projects",
        # Sectors
        "education",
        "health",
        "healthcare",
        "welfare",
        "relief",
        "humanitarian",
        "development",
        "emergency",
        # Efficiency
        "efficiency",
        "overhead",
        "cost",
        "where-money-goes",
        "how-we-spend",
    }

    # FIT dimension (25 pts max) - mission, beneficiaries, zakat alignment
    # Critical for: mission clarity, target populations, Islamic compliance
    FIT_KEYWORDS = {
        # Mission and identity
        "about",
        "about-us",
        "mission",
        "our-mission",
        "vision",
        "values",
        "who-we-are",
        "our-story",
        "history",
        # Beneficiaries
        "who-we-serve",
        "beneficiaries",
        "communities",
        "populations",
        "recipients",
        # Islamic alignment
        "zakat",
        "zakaat",
        "sadaqah",
        "sadaqa",
        "islamic",
        "shariah",
        "sharia",
        "fiqh",
        "halal",
        "muslim",
        "ummah",
    }

    # DONATION keywords - for zakat claim detection
    DONATION_KEYWORDS = {
        "donate",
        "donation",
        "donations",
        "give",
        "giving",
        "ways-to-give",
        "how-to-give",
        "ways-to-help",
        "support-us",
        "contribute",
        "stocks",
        "securities",
        "matching",
        "planned-giving",
        "legacy",
    }

    # Penalty keywords (low signal-to-noise ratio)
    PENALTY_KEYWORDS = {
        "blog",
        "blogs",
        "news",
        "newsroom",
        "event",
        "events",
        "press",
        "press-release",
        "media",
        "stories",
        "update",
        "updates",
        "newsletter",
        "subscribe",
        "careers",
        "jobs",
        "employment",
        "login",
        "signin",
        "cart",
        "checkout",
    }

    # Canonical core pages - short paths that get bonus (+30 pts)
    # These are the high-value pages that should always be in top 10
    CANONICAL_PAGES = {
        "/donate/",
        "/donate",
        "/zakat/",
        "/zakat",
        "/about/",
        "/about",
        "/about-us/",
        "/about-us",
        "/impact/",
        "/impact",
        "/our-work/",
        "/our-work",
        "/programs/",
        "/programs",
        "/financials/",
        "/financials",
        "/ways-to-give/",
        "/ways-to-give",
        "/annual-report/",
        "/annual-report",
        "/transparency/",
        "/transparency",
    }

    # Content-based boost keywords (+50 pts)
    # These indicate high-value content regardless of URL pattern
    # Used during content-aware crawling to find pages like /dhul-hijjah-2022/
    CONTENT_BOOST_KEYWORDS = {
        # Zakat eligibility indicators (highest priority)
        "zakat eligible",
        "zakat-eligible",
        "accepts zakat",
        "accept zakat",
        "give zakat",
        "give your zakat",
        "donate zakat",
        "pay zakat",
        "zakat donation",
        "zakat fund",
        "your zakat",
        "zakaat eligible",
        "zakah eligible",
        # Islamic giving campaigns
        "tax deductible and zakat",
        "zakat and sadaqah",
        "fidya",
        "kaffarah",
        "sadaqat al-fitr",
        "zakat al-fitr",
        "zakat ul-fitr",
    }

    # Content boost amount - high enough to override URL-based penalties
    CONTENT_BOOST_POINTS = 50

    def score_url(
        self,
        url: str,
        anchor_text: str | None = None,
        page_title: str | None = None,
        page_h1: str | None = None,
    ) -> PageScore:
        """
        Score a URL based on V2 dimension keywords.

        V2 Scoring Algorithm:
        - TRUST (25 pts): 990s, audits, transparency, governance
        - EVIDENCE (25 pts): outcomes, research, evaluation, theory-of-change
        - EFFECTIVENESS (25 pts): programs, costs, efficiency
        - FIT (25 pts): mission, beneficiaries, zakat alignment
        - DONATION (15 pts): donation pages for zakat claim detection
        - PENALTY (-15 pts): blog, news, events

        Args:
            url: The URL to score
            anchor_text: Link text pointing to this URL
            page_title: Page title (if available)
            page_h1: Page h1 heading (if available)

        Returns:
            PageScore with V2 dimension breakdown
        """
        from urllib.parse import urlparse

        breakdown: dict[str, int] = {}
        matched_keywords: list[str] = []
        matched_context: list[str] = []

        url_path = urlparse(url).path.lower()

        # Homepage gets automatic high score (covers all dimensions)
        if url_path in ["/", ""]:
            return PageScore(
                url=url,
                raw_score=70,
                page_type="homepage",
                primary_dimension="none",
                matched_keywords=["homepage"],
                matched_context=["url"],
                breakdown={"homepage_baseline": 70},
            )

        # Combine context for keyword matching
        all_text = " ".join(
            filter(
                None,
                [
                    url_path,
                    anchor_text.lower() if anchor_text else "",
                    page_title.lower() if page_title else "",
                    page_h1.lower() if page_h1 else "",
                ],
            )
        )

        # Score each V2 dimension
        dimension_scores = {
            "trust": 0,
            "evidence": 0,
            "effectiveness": 0,
            "fit": 0,
        }

        # TRUST dimension (25 pts max)
        trust_matches = self._match_keywords(url_path, all_text, self.TRUST_KEYWORDS)
        if trust_matches:
            # Base 20 pts for URL match, +5 for context match
            dimension_scores["trust"] = 20 if any(kw in url_path for kw in trust_matches) else 15
            if len(trust_matches) > 1:
                dimension_scores["trust"] = min(25, dimension_scores["trust"] + 5)
            matched_keywords.extend(trust_matches)
            matched_context.append("url")
            breakdown["trust"] = dimension_scores["trust"]

        # EVIDENCE dimension (25 pts max)
        evidence_matches = self._match_keywords(url_path, all_text, self.EVIDENCE_KEYWORDS)
        if evidence_matches:
            dimension_scores["evidence"] = 20 if any(kw in url_path for kw in evidence_matches) else 15
            if len(evidence_matches) > 1:
                dimension_scores["evidence"] = min(25, dimension_scores["evidence"] + 5)
            matched_keywords.extend(evidence_matches)
            matched_context.append("url")
            breakdown["evidence"] = dimension_scores["evidence"]

        # EFFECTIVENESS dimension (25 pts max)
        effectiveness_matches = self._match_keywords(url_path, all_text, self.EFFECTIVENESS_KEYWORDS)
        if effectiveness_matches:
            dimension_scores["effectiveness"] = 20 if any(kw in url_path for kw in effectiveness_matches) else 15
            if len(effectiveness_matches) > 1:
                dimension_scores["effectiveness"] = min(25, dimension_scores["effectiveness"] + 5)
            matched_keywords.extend(effectiveness_matches)
            matched_context.append("url")
            breakdown["effectiveness"] = dimension_scores["effectiveness"]

        # FIT dimension (25 pts max)
        fit_matches = self._match_keywords(url_path, all_text, self.FIT_KEYWORDS)
        if fit_matches:
            dimension_scores["fit"] = 20 if any(kw in url_path for kw in fit_matches) else 15
            if len(fit_matches) > 1:
                dimension_scores["fit"] = min(25, dimension_scores["fit"] + 5)
            matched_keywords.extend(fit_matches)
            matched_context.append("url")
            breakdown["fit"] = dimension_scores["fit"]

        # DONATION bonus (15 pts) - important for zakat claim detection
        donation_matches = self._match_keywords(url_path, all_text, self.DONATION_KEYWORDS)
        if donation_matches:
            breakdown["donation"] = 15
            matched_keywords.extend(donation_matches)
            matched_context.append("url")

        # Calculate total score
        total = sum(breakdown.values())

        # PENALTY for low-value pages (-15 pts)
        for keyword in self.PENALTY_KEYWORDS:
            if keyword in url_path:
                total -= 15
                breakdown["penalty"] = -15
                break

        # BONUS for canonical core pages (+30 pts)
        # These are high-value pages that should always be prioritized
        if url_path in self.CANONICAL_PAGES:
            total += 30
            breakdown["canonical_bonus"] = 30

        # PENALTY for long URLs (-20 pts)
        # News/blog articles tend to have long descriptive URLs
        # Core pages have short paths (/donate/, /about/, etc.)
        path_segments = [s for s in url_path.split("/") if s]
        if len(path_segments) == 1 and len(path_segments[0]) > 50:
            # Single segment but very long (e.g., news-article-title-here)
            total -= 20
            breakdown["long_url_penalty"] = -20

        # Clamp to 0-100
        total = max(0, min(100, total))

        # Determine primary dimension and page type
        has_dimension_match = any(dimension_scores.values())
        if has_dimension_match:
            primary_dimension = max(dimension_scores, key=dimension_scores.get)
        else:
            primary_dimension = "none"

        page_type = self._classify_from_url_v2(url_path, primary_dimension)

        return PageScore(
            url=url,
            raw_score=total,
            page_type=page_type,
            primary_dimension=primary_dimension,
            matched_keywords=list(set(matched_keywords)),
            matched_context=list(set(matched_context)),
            breakdown=breakdown,
        )

    def _match_keywords(self, url_path: str, all_text: str, keywords: set[str]) -> list[str]:
        """Find matching keywords in URL path and combined text.

        E-006: Use word boundary matching to avoid false positives like
        'art' matching 'cart' or 'smart'.
        """
        import re
        matches = []
        for keyword in keywords:
            # URL paths: simple substring is fine (segments are already word-bounded by /)
            if keyword in url_path:
                matches.append(keyword)
            # Text content: use word boundary to avoid partial matches
            elif re.search(rf'\b{re.escape(keyword)}\b', all_text, re.IGNORECASE):
                matches.append(keyword)
        return matches

    def check_content_boost(self, content: str) -> tuple[int, list[str]]:
        """
        Check page content for high-value keywords that indicate important pages.

        This enables content-aware crawling - pages like /dhul-hijjah-2022/ that
        contain "zakat eligible" will get boosted even though their URL doesn't
        match any patterns.

        Args:
            content: Page HTML or text content (will be lowercased)

        Returns:
            Tuple of (boost_points, matched_keywords)
            - boost_points: Points to add to URL score (0 or CONTENT_BOOST_POINTS)
            - matched_keywords: List of keywords found in content
        """
        content_lower = content.lower()
        matched = []

        for keyword in self.CONTENT_BOOST_KEYWORDS:
            if keyword in content_lower:
                matched.append(keyword)

        if matched:
            return self.CONTENT_BOOST_POINTS, matched
        return 0, []

    def apply_content_boost(self, page_score: PageScore, content: str) -> PageScore:
        """
        Apply content-based boost to an existing PageScore.

        Use this after fetching page content to re-score based on actual content.
        Pages with zakat keywords get boosted to ensure they're included in crawl.

        Args:
            page_score: Existing URL-based PageScore
            content: Page HTML or text content

        Returns:
            New PageScore with content boost applied (if any)
        """
        boost, matched_keywords = self.check_content_boost(content)

        if boost == 0:
            return page_score

        # Create new score with content boost
        new_breakdown = dict(page_score.breakdown)
        new_breakdown["content_boost"] = boost

        new_matched = list(page_score.matched_keywords) + matched_keywords
        new_context = list(page_score.matched_context)
        if "content" not in new_context:
            new_context.append("content")

        # Boost the score, clamping to 100
        new_score = min(100, page_score.raw_score + boost)

        # If content has zakat keywords, classify as "fit" dimension
        new_dimension = page_score.primary_dimension
        new_type = page_score.page_type
        if any("zakat" in kw for kw in matched_keywords):
            new_dimension = "fit"
            new_type = "fit"

        return PageScore(
            url=page_score.url,
            raw_score=new_score,
            page_type=new_type,
            primary_dimension=new_dimension,
            matched_keywords=list(set(new_matched)),
            matched_context=new_context,
            breakdown=new_breakdown,
        )

    def _classify_from_url_v2(self, url_path: str, primary_dimension: str) -> str:
        """Classify page type using V2 dimensions."""
        if url_path in ["/", ""]:
            return "homepage"

        # Check for donation pages first (important for zakat claim)
        if any(kw in url_path for kw in self.DONATION_KEYWORDS):
            return "donate"

        # Map primary dimension to page type
        dimension_to_type = {
            "trust": "trust",
            "evidence": "evidence",
            "effectiveness": "effectiveness",
            "fit": "fit",
        }

        return dimension_to_type.get(primary_dimension, "other")

    def classify_page_type(
        self,
        url: str,
        anchor_text: str | None = None,
        page_title: str | None = None,
        page_h1: str | None = None,
    ) -> PageClassification:
        """
        Classify page type based on V2 dimensions.

        Args:
            url: The URL to classify
            anchor_text: Link text pointing to this URL
            page_title: Page title (if available)
            page_h1: Page h1 heading (if available)

        Returns:
            PageClassification with V2 dimension-based type and confidence
        """
        from urllib.parse import urlparse

        url_path = urlparse(url).path.lower()
        keywords_matched = []
        confidence = "low"

        # Collect all matching keywords across V2 dimensions
        all_keywords = (
            self.TRUST_KEYWORDS
            | self.EVIDENCE_KEYWORDS
            | self.EFFECTIVENESS_KEYWORDS
            | self.FIT_KEYWORDS
            | self.DONATION_KEYWORDS
        )

        for keyword in all_keywords:
            if keyword in url_path:
                keywords_matched.append(keyword)

        # Score the URL to get primary dimension
        score = self.score_url(url, anchor_text, page_title, page_h1)

        # Determine confidence based on matches and dimension clarity
        if len(keywords_matched) >= 2:
            confidence = "high"
        elif len(keywords_matched) == 1:
            confidence = "medium"
        elif score.page_type == "homepage":
            confidence = "high"

        return PageClassification(
            url=url, classified_type=score.page_type, confidence=confidence, keywords_matched=keywords_matched
        )

    def select_top_pages(self, page_scores: list[PageScore], max_pages: int = 12) -> list[PageScore]:
        """
        Select top N pages with V2 dimension diversity.

        Selection strategy:
        1. Ensure at least 1-2 pages per V2 dimension (trust, evidence, effectiveness, fit)
        2. Include donation pages for zakat claim detection
        3. Fill remaining slots by score

        Args:
            page_scores: List of scored pages
            max_pages: Maximum number of pages to select

        Returns:
            List of pages optimized for V2 dimension coverage
        """
        from urllib.parse import urlparse

        def get_url_depth(url: str) -> int:
            """Get URL depth (number of path segments)."""
            parsed = urlparse(url)
            path = parsed.path.strip("/")
            if not path:
                return 0
            return len(path.split("/"))

        # Group pages by V2 dimension
        dimension_pages: dict[str, list[PageScore]] = {
            "trust": [],
            "evidence": [],
            "effectiveness": [],
            "fit": [],
            "donate": [],
            "homepage": [],
            "other": [],
        }

        for ps in page_scores:
            if ps.page_type == "homepage":
                dimension_pages["homepage"].append(ps)
            elif ps.page_type == "donate":
                dimension_pages["donate"].append(ps)
            elif ps.primary_dimension in dimension_pages:
                dimension_pages[ps.primary_dimension].append(ps)
            else:
                dimension_pages["other"].append(ps)

        # Sort each group by score
        for dim in dimension_pages:
            dimension_pages[dim].sort(
                key=lambda ps: (-ps.raw_score, get_url_depth(str(ps.url)), str(ps.url))
            )

        # Build selection with dimension diversity
        selected: list[PageScore] = []
        seen_urls: set[str] = set()

        def add_page(ps: PageScore) -> bool:
            if str(ps.url) not in seen_urls:
                selected.append(ps)
                seen_urls.add(str(ps.url))
                return True
            return False

        # 1. Always include homepage if available
        for ps in dimension_pages["homepage"][:1]:
            add_page(ps)

        # 2. Ensure minimum coverage per V2 dimension (2 pages each)
        min_per_dimension = 2
        for dim in ["trust", "evidence", "effectiveness", "fit"]:
            for ps in dimension_pages[dim][:min_per_dimension]:
                if len(selected) < max_pages:
                    add_page(ps)

        # 3. Include donation pages for zakat claim detection (1-2)
        for ps in dimension_pages["donate"][:2]:
            if len(selected) < max_pages:
                add_page(ps)

        # 4. Fill remaining slots by overall score
        remaining = sorted(
            [ps for ps in page_scores if str(ps.url) not in seen_urls],
            key=lambda ps: (-ps.raw_score, get_url_depth(str(ps.url)), str(ps.url)),
        )

        for ps in remaining:
            if len(selected) >= max_pages:
                break
            add_page(ps)

        return selected
