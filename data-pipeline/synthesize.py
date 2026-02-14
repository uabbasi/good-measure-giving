"""
Phase 3: Synthesize - Compute derived fields from raw scraped data.

Takes raw data from raw_scraped_data table and computes synthesized metrics
for the charity_data table:
- has_islamic_identity, serves_muslim_populations, muslim_charity_fit: Deterministic keyword-based
- Financial metrics: total_revenue, program_expenses, admin_expenses, etc.
- program_expense_ratio: Calculated or from Charity Navigator
- charity_navigator_score: From CN data
- transparency_score: From Candid seal level
- source_attribution: Maps each field to its source URL and timestamp

Usage:
    uv run python synthesize.py --ein 95-4453134
    uv run python synthesize.py --charities pilot_charities.txt
"""

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent))

from src.db import CharityData, CharityDataRepository, CharityRepository, PhaseCacheRepository, RawDataRepository
from src.db.dolt_client import dolt
from src.llm.category_classifier import get_category_info, get_charity_category
from src.llm.llm_client import LLMClient, LLMTask
from src.parsers.charity_metrics_aggregator import CharityMetricsAggregator
from src.scorers.strategic_classifier import classification_to_dict, classify_charity
from src.scorers.strategic_evidence import compute_strategic_evidence
from src.utils.logger import PipelineLogger
from src.utils.phase_cache_helper import check_phase_cache, update_phase_cache

# Muslim charity classification keywords (deterministic, no LLM)
ISLAMIC_IDENTITY_KEYWORDS = {
    # Primary religious terms
    "islamic",
    "muslim",
    "masjid",
    "mosque",
    "quran",
    "sunnah",
    "shariah",
    "sharia",
    "imam",
    "ummah",
    "deen",
    "dawah",
    "halal",
    # Islamic giving terms
    "zakat",
    "sadaqah",
    "lillah",
    "waqf",
    "fidya",
    "kaffarah",
    # Religious events/campaigns
    "ramadan",
    "eid",
    "hajj",
    "umrah",
    "jummah",
    "qurbani",
    "udhiyah",
    "iftar",
    # Arabic greetings/phrases (transliterated)
    "assalamu",
    "bismillah",
    "inshallah",
    "insha'allah",
    "alhamdulillah",
    "subhanallah",
    # Leadership/scholarly titles
    "sheikh",
    "shaykh",
    "mufti",
    "ustadh",
    "alim",
    "ulama",
}

# Organization name patterns that indicate Islamic identity
# These are checked as substrings in the org name (case-insensitive)
ISLAMIC_ORG_PATTERNS = {
    "icna",  # Islamic Circle of North America
    "isna",  # Islamic Society of North America
    "cair",  # Council on American-Islamic Relations
    "mas ",  # Muslim American Society (with space to avoid false matches)
    " mas",  # Muslim American Society
    "msa ",  # Muslim Students Association
    " msa",
    "hhrd",  # Helping Hand for Relief and Development
    "irusa",  # Islamic Relief USA
    "penny appeal",  # Known Muslim charity
    "human appeal",  # Known Muslim charity
    "muslim aid",
    "baitulmaal",
    "hidaya",
}

MUSLIM_REGION_KEYWORDS = {
    "palestine",
    "gaza",
    "west bank",
    "yemen",
    "syria",
    "afghanistan",
    "somalia",
    "rohingya",
    "kashmir",
    "uyghur",
    "bangladesh",
    "pakistan",
    "indonesia",
    "malaysia",
    "egypt",
    "jordan",
    "lebanon",
    "iraq",
}

# Active conflict zones (reviewed annually per UN OCHA, ICRC watchlists)
# Used for cost-effectiveness 1.5x threshold adjustment
CONFLICT_ZONES = {
    "syria",
    "yemen",
    "sudan",
    "gaza",
    "palestine",
    "west bank",
    "afghanistan",
    "drc",
    "congo",
    "somalia",
    "myanmar",
    "ukraine",
    "south sudan",
    "central african republic",
    "libya",
    "iraq",
    "ethiopia",
    "tigray",
    "haiti",
    "burkina faso",
    "mali",
    "niger",
}

# ============================================================================
# Cause Tags Detection (Non-MECE, multiple allowed per spec)
# ============================================================================

# Geographic scope tags - country-level specificity for donor discovery
# Use specific countries as tags, not broad regions
GEOGRAPHIC_TAG_KEYWORDS: dict[str, set[str]] = {
    # Domestic
    "usa": {"united states", "usa", "america", "domestic", "u.s."},
    # Middle East
    "palestine": {"palestine", "palestinian", "gaza", "west bank"},
    "syria": {"syria", "syrian"},
    "yemen": {"yemen", "yemeni"},
    "iraq": {"iraq", "iraqi"},
    "lebanon": {"lebanon", "lebanese"},
    "jordan": {"jordan", "jordanian"},
    "egypt": {"egypt", "egyptian"},
    # South Asia
    "pakistan": {"pakistan", "pakistani"},
    "india": {"india", "indian"},
    "bangladesh": {"bangladesh", "bangladeshi"},
    "afghanistan": {"afghanistan", "afghan"},
    "kashmir": {"kashmir", "kashmiri"},
    # Southeast Asia
    "indonesia": {"indonesia", "indonesian"},
    "malaysia": {"malaysia", "malaysian"},
    "myanmar": {"myanmar", "rohingya", "burma"},
    # Africa
    "somalia": {"somalia", "somali"},
    "sudan": {"sudan", "sudanese"},
    "ethiopia": {"ethiopia", "ethiopian"},
    "kenya": {"kenya", "kenyan"},
    "nigeria": {"nigeria", "nigerian"},
    "south-africa": {"south africa"},
    # Central Asia
    "turkey": {"turkey", "turkish", "türkiye"},
    "uyghur": {"uyghur", "xinjiang", "east turkestan"},
    # Other
    "ukraine": {"ukraine", "ukrainian"},
    "haiti": {"haiti", "haitian"},
    # Broad scope (only if no specific country detected)
    "international": {"international", "global", "worldwide", "overseas"},
}

# Population served tags
POPULATION_TAG_KEYWORDS: dict[str, set[str]] = {
    "refugees": {"refugee", "displaced", "idp", "asylum", "migrant"},
    "orphans": {"orphan", "yateem", "vulnerable children", "parentless"},
    "women": {"women", "girls", "female", "mothers", "maternal"},
    "youth": {"youth", "young", "adolescent", "teen", "children"},
    "elderly": {"elderly", "senior", "aged", "older adults"},
    "disabled": {"disabled", "disability", "handicapped", "special needs"},
    "prisoners": {"prisoner", "incarcerated", "detention", "jail"},
    "homeless": {"homeless", "unhoused", "street"},
    "low-income": {"low-income", "poverty", "poor", "underserved"},
    "widows": {"widow", "single mother"},
    "converts": {"convert", "revert", "muallaf", "new muslim"},
}

# Intervention type tags
INTERVENTION_TAG_KEYWORDS: dict[str, set[str]] = {
    "emergency-response": {"emergency", "disaster", "crisis", "urgent", "immediate"},
    # More specific phrases to avoid false positives like "Cemetery Development"
    "long-term-development": {
        "community development",
        "economic development",
        "rural development",
        "international development",
        "sustainable development",
        "human development",
        "long-term",
        "long term",
        "sustainable livelihoods",
        "poverty alleviation",
    },
    "direct-service": {"direct service", "service delivery", "providing"},
    "capacity-building": {"capacity building", "training", "empowerment"},
    "grantmaking": {"grant", "funding", "donor", "foundation"},
    "advocacy": {"advocacy", "policy", "lobbying", "rights"},
    "research": {"research", "study", "academic"},
}

# Service domain tags
SERVICE_TAG_KEYWORDS: dict[str, set[str]] = {
    "water-sanitation": {"water", "wash", "sanitation", "hygiene", "well", "clean water"},
    "medical": {"medical", "health", "clinic", "hospital", "doctor", "healthcare"},
    "educational": {"education", "school", "scholarship", "literacy", "teacher"},
    "vocational": {"vocational", "job training", "skills", "employment"},
    "microfinance": {"microfinance", "microloan", "financial inclusion"},
    "shelter": {"shelter", "housing", "home"},
    "food": {"food", "meal", "nutrition", "hunger", "feeding"},
    "clothing": {"clothing", "clothes", "garment"},
    "legal-aid": {"legal", "lawyer", "attorney", "court"},
    "psychosocial": {"mental health", "counseling", "psychosocial", "trauma"},
}

# Layer 3: Change type tags (systemic leverage / theory of change)
# These help donors understand HOW the charity creates change
# NOTE: scalable-model and systemic-change are NOT keyword-based - they require
# explicit program_type_classification from website extraction (see detect_cause_tags)
CHANGE_TYPE_TAG_KEYWORDS: dict[str, set[str]] = {
    # Capacity building - empowers people/orgs to help themselves
    "capacity-building": {
        "capacity building",
        "training",
        "empowerment",
        "skill building",
        "leadership development",
        "organizational development",
        "mentorship",
        "technical assistance",
        "institutional strengthening",
    },
    # Direct relief - immediate aid, consumptive (one-time goods/services)
    "direct-relief": {
        "emergency relief",
        "distribution",
        "one-time",
        "immediate relief",
        "food basket",
        "qurbani",
        "food pack",
        "aid distribution",
        "handout",
        "emergency response",
        "disaster relief",
        "humanitarian aid",
    },
}

# Mapping from extracted program_type_classification to tags
# NOTE: scalable-model and systemic-change have stricter criteria in detect_cause_tags()
# and are NOT assigned via this mapping anymore
PROGRAM_TYPE_TO_TAG: dict[str, str] = {
    "CONSUMPTIVE": "direct-relief",
    # GENERATIVE and SCALABLE have stricter requirements - handled explicitly below
    # MIXED gets no automatic tag
}

# Zakat asnaf categories (from discovered data)
ZAKAT_ASNAF_TAGS = {
    "fuqara",
    "masakin",
    "gharimeen",
    "fisabilillah",
    "ibn-sabil",
    "muallaf",
    "amileen",
}

# Candid seal level to transparency score mapping
CANDID_SEAL_SCORES = {
    "platinum": 100,
    "gold": 85,
    "silver": 70,
    "bronze": 50,
}

# ============================================================================
# Program Focus Tags (for similarity matching)
# ============================================================================

# Program focus tag taxonomy - describes WHAT the organization actually DOES
# Used for finding functionally similar organizations across category boundaries
PROGRAM_FOCUS_TAGS = {
    "arts-culture-media": "Arts, storytelling, cultural representation, film, media production",
    "advocacy-legal": "Civil rights, legal aid, policy advocacy, litigation",
    "humanitarian-relief": "Emergency relief, food aid, disaster response, immediate assistance",
    "water-sanitation": "Clean water, infrastructure, sanitation, wells",
    "education-k12": "Schools, youth education, K-12 programs",
    "education-higher": "Universities, scholarships, fellowships, higher education",
    "healthcare-direct": "Clinics, medical services, health programs",
    "economic-empowerment": "Job training, microfinance, livelihood, entrepreneurship",
    "community-services": "Family services, social support, local community programs",
    "research-policy": "Think tanks, research, policy development, studies",
    "religious-services": "Mosques, religious education, dawah, spiritual services",
    "orphan-care": "Orphan sponsorship, child welfare, vulnerable children",
    "refugee-services": "Refugee support, resettlement, displaced persons",
}

# Fallback mapping from detected_cause_area to primary_category
# Used when charity is not manually mapped in charity_categories.yaml
# These map keyword-detected causes to our MECE taxonomy
CAUSE_AREA_TO_CATEGORY: dict[str, str] = {
    # Humanitarian and relief
    "humanitarian": "HUMANITARIAN",
    "relief": "HUMANITARIAN",
    "disaster": "HUMANITARIAN",
    "refugee": "HUMANITARIAN",
    "emergency": "HUMANITARIAN",
    # Health and medical
    "health": "MEDICAL_HEALTH",
    "medical": "MEDICAL_HEALTH",
    "healthcare": "MEDICAL_HEALTH",
    "mental health": "MEDICAL_HEALTH",
    # Basic needs
    "food": "BASIC_NEEDS",
    "water": "BASIC_NEEDS",
    "shelter": "BASIC_NEEDS",
    "orphan": "BASIC_NEEDS",
    "extreme_poverty": "BASIC_NEEDS",
    "extreme poverty": "BASIC_NEEDS",
    "domestic_poverty": "BASIC_NEEDS",
    "domestic poverty": "BASIC_NEEDS",
    "poverty": "BASIC_NEEDS",
    "hunger": "BASIC_NEEDS",
    "housing": "BASIC_NEEDS",
    # Civil rights and legal
    "civil rights": "CIVIL_RIGHTS_LEGAL",
    "legal": "CIVIL_RIGHTS_LEGAL",
    "advocacy": "CIVIL_RIGHTS_LEGAL",
    "justice": "CIVIL_RIGHTS_LEGAL",
    # Research and policy
    "research": "RESEARCH_POLICY",
    "policy": "RESEARCH_POLICY",
    "think tank": "RESEARCH_POLICY",
    # Environment
    "environment": "ENVIRONMENT_CLIMATE",
    "climate": "ENVIRONMENT_CLIMATE",
    "conservation": "ENVIRONMENT_CLIMATE",
    # Women's services
    "women": "WOMENS_SERVICES",
    "domestic violence": "WOMENS_SERVICES",
    "maternal": "WOMENS_SERVICES",
    # Education - international development focus
    "education": "EDUCATION_INTERNATIONAL",
    "literacy": "EDUCATION_INTERNATIONAL",
    "scholarship": "EDUCATION_INTERNATIONAL",
    # Religious outreach/education
    "dawah": "RELIGIOUS_OUTREACH",
    "interfaith": "RELIGIOUS_OUTREACH",
    # Religious congregation
    "mosque": "RELIGIOUS_CONGREGATION",
    "masjid": "RELIGIOUS_CONGREGATION",
    "congregation": "RELIGIOUS_CONGREGATION",
    "community center": "RELIGIOUS_CONGREGATION",
    # Philanthropy
    "grantmaking": "PHILANTHROPY_GRANTMAKING",
    "foundation": "PHILANTHROPY_GRANTMAKING",
    # Media
    "media": "MEDIA_JOURNALISM",
    "journalism": "MEDIA_JOURNALISM",
    "film": "MEDIA_JOURNALISM",
    # Social services (catch-all for community programs)
    "social services": "SOCIAL_SERVICES",
    "youth": "SOCIAL_SERVICES",
    "community": "SOCIAL_SERVICES",
}


CATEGORY_DISPLAY_NAMES: dict[str, str] = {
    "HUMANITARIAN": "Humanitarian Relief",
    "MEDICAL_HEALTH": "Medical & Health",
    "BASIC_NEEDS": "Basic Needs",
    "CIVIL_RIGHTS_LEGAL": "Civil Rights & Legal",
    "RESEARCH_POLICY": "Research & Policy",
    "ADVOCACY_CIVIC": "Advocacy & Civic",
    "ENVIRONMENT_CLIMATE": "Environment & Climate",
    "WOMENS_SERVICES": "Women's Services",
    "EDUCATION_INTERNATIONAL": "International Education",
    "EDUCATION_HIGHER_RELIGIOUS": "Higher Education",
    "EDUCATION_K12_RELIGIOUS": "K-12 Education",
    "RELIGIOUS_OUTREACH": "Religious Outreach",
    "RELIGIOUS_CONGREGATION": "Religious Congregation",
    "PHILANTHROPY_GRANTMAKING": "Philanthropy & Grantmaking",
    "MEDIA_JOURNALISM": "Media & Journalism",
    "SOCIAL_SERVICES": "Social Services",
}


def map_cause_to_category(detected_cause_area: str | None) -> str | None:
    """Map detected_cause_area to a primary_category.

    Used as fallback when charity is not manually mapped in charity_categories.yaml.
    Returns None if no mapping found (charity will have no category).
    """
    if not detected_cause_area:
        return None

    cause_lower = detected_cause_area.lower()

    # Direct match first
    if cause_lower in CAUSE_AREA_TO_CATEGORY:
        return CAUSE_AREA_TO_CATEGORY[cause_lower]

    # Substring match (e.g., "humanitarian aid" matches "humanitarian")
    for keyword, category in CAUSE_AREA_TO_CATEGORY.items():
        if keyword in cause_lower:
            return category

    return None


# ============================================================================
# Source Attribution Helpers
# ============================================================================


def build_source_url(
    source_name: str,
    ein: str,
    section: str | None = None,
    candid_url: str | None = None,
    website_url: str | None = None,
) -> str | None:
    """Build the canonical URL for a data source.

    Args:
        source_name: The source (propublica, charity_navigator, candid, website)
        ein: The charity EIN
        section: Optional section anchor (e.g., 'financials', 'ratings')
        candid_url: Candid profile URL extracted during crawl (required for candid source)
        website_url: Charity website URL from charities table (required for website source)

    Returns:
        The source URL or None if no URL available
    """
    def _normalize_website_evidence_url(url: str | None, fallback: str | None = None) -> str | None:
        if not url:
            return fallback
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                return fallback
            if "vertexaisearch.cloud.google.com" in parsed.netloc and "grounding-api-redirect" in parsed.path:
                return fallback
            return url
        except Exception:
            return fallback

    ein_clean = ein.replace("-", "")

    if source_name == "propublica":
        return f"https://projects.propublica.org/nonprofits/organizations/{ein_clean}"
    elif source_name == "charity_navigator":
        base = f"https://www.charitynavigator.org/ein/{ein_clean}"
        return f"{base}#{section}" if section else base
    elif source_name == "candid":
        # Candid URL must come from candid_profile.candid_url (extracted during crawl)
        return candid_url
    elif source_name == "website":
        # Website URL comes from charities.website
        return _normalize_website_evidence_url(website_url)
    elif source_name == "form990_grants":
        # Form 990 grants come from ProPublica XML - link to main ProPublica page
        return f"https://projects.propublica.org/nonprofits/organizations/{ein_clean}"
    return None


def create_attribution(
    field_name: str,
    value: Any,
    source_name: str,
    ein: str,
    scraped_at: str | None = None,
    section: str | None = None,
    display_name: str | None = None,
    candid_url: str | None = None,
    website_url: str | None = None,
) -> dict:
    """Create a source attribution record for a field.

    Args:
        field_name: The field being attributed
        value: The value extracted
        source_name: The data source (propublica, charity_navigator, etc.)
        ein: The charity EIN
        scraped_at: When the data was scraped
        section: Optional URL section anchor
        display_name: Human-readable source name
        candid_url: Candid profile URL (for candid source)
        website_url: Charity website URL (for website source)

    Returns:
        Attribution dict with source_name, source_url, value, timestamp
    """
    source_url = build_source_url(source_name, ein, section, candid_url, website_url)

    # Human-readable display names
    display_names = {
        "propublica": "ProPublica Form 990",
        "charity_navigator": "Charity Navigator",
        "candid": "Candid",
        "form990_grants": "Form 990 Grants",
        "website": "Charity Website",
    }

    return {
        "source_name": display_name or display_names.get(source_name, source_name),
        "source_url": source_url,
        "value": value,
        "timestamp": scraped_at or datetime.now(timezone.utc).isoformat(),
    }


def has_islamic_identity(name: str, mission: str | None, website_profile: dict | None = None) -> bool:
    """Check if charity explicitly identifies as Islamic/Muslim.

    Deterministic detection from HIGH-CONFIDENCE signals only:
    1. Keywords in name/mission text (religious terms, giving terms, events)
    2. Organization name patterns (ICNA, ISNA, CAIR, etc.)
    3. High-confidence website signals (shariah_board, fidya_kaffarah - NOT accepts_zakat alone)

    IMPORTANT: accepts_zakat alone is NOT sufficient - LLMs hallucinate this field.
    Zakat claims require separate two-source verification in the aggregator.

    No LLM required.
    """
    name_lower = (name or "").lower()
    mission_lower = (mission or "").lower()
    text = f"{name_lower} {mission_lower}"

    # 1. Check keywords in name/mission (high confidence - from actual text)
    if any(kw in text for kw in ISLAMIC_IDENTITY_KEYWORDS):
        return True

    # 2. Check organization name patterns (handles acronyms like ICNA, HHRD)
    if any(pattern in name_lower for pattern in ISLAMIC_ORG_PATTERNS):
        return True

    # 3. Check HIGH-CONFIDENCE website signals only
    # NOTE: accepts_zakat, zakat_categories_served are NOT used here
    # because LLMs frequently hallucinate these for secular charities.
    # These are verified separately with two-source corroboration.
    if website_profile:
        # Shariah board is very specific - secular orgs don't have these
        if website_profile.get("shariah_board"):
            return True
        # Fidya/kaffarah are Islamic-specific payment types
        if website_profile.get("fidya_kaffarah_accepted"):
            return True
        # Islamic finance compliance is specific
        if website_profile.get("islamic_finance_compliant"):
            return True
        # Ramadan campaign URL (if present, indicates Islamic org)
        if website_profile.get("ramadan_campaign_url"):
            return True

        # Check programs for HIGHLY SPECIFIC Islamic services only
        # (removed 'orphan', 'water well' - too generic)
        programs = website_profile.get("programs") or []
        program_text = " ".join(programs).lower() if programs else ""
        islamic_program_keywords = {"qurbani", "udhiyah", "iftar", "fidya", "kaffarah", "lillah"}
        if any(kw in program_text for kw in islamic_program_keywords):
            return True

    return False


def _collect_islamic_identity_signals(
    name: str, mission: str | None, website_profile: dict | None = None
) -> dict | None:
    """Collect which Islamic identity signals matched (mirrors has_islamic_identity logic).

    Returns a dict of signal names → values, or None if no signals found.
    Deterministic, no LLM.
    """
    signals: dict = {}
    name_lower = (name or "").lower()
    mission_lower = (mission or "").lower()
    text = f"{name_lower} {mission_lower}"

    # 1. Keywords in name/mission
    matched_keywords = [kw for kw in ISLAMIC_IDENTITY_KEYWORDS if kw in text]
    if matched_keywords:
        signals["name_mission_keywords"] = matched_keywords

    # 2. Org name patterns
    matched_patterns = [p.strip() for p in ISLAMIC_ORG_PATTERNS if p in name_lower]
    if matched_patterns:
        signals["org_name_patterns"] = matched_patterns

    # 3. Website signals
    if website_profile:
        if website_profile.get("shariah_board"):
            signals["shariah_board"] = True
        if website_profile.get("fidya_kaffarah_accepted"):
            signals["fidya_kaffarah_accepted"] = True
        if website_profile.get("islamic_finance_compliant"):
            signals["islamic_finance_compliant"] = True
        if website_profile.get("ramadan_campaign_url"):
            signals["ramadan_campaign"] = True

        programs = website_profile.get("programs") or []
        program_text = " ".join(programs).lower() if programs else ""
        islamic_program_kws = {"qurbani", "udhiyah", "iftar", "fidya", "kaffarah", "lillah"}
        matched_program_kws = [kw for kw in islamic_program_kws if kw in program_text]
        if matched_program_kws:
            signals["islamic_program_keywords"] = matched_program_kws

    return signals if signals else None


def serves_muslim_populations(mission: str | None, geographic_coverage: list[str] | None) -> bool:
    """Check if charity primarily serves Muslim-majority regions.

    Deterministic keyword-based detection. No LLM required.
    """
    coverage = geographic_coverage or []
    text = f"{mission or ''} {' '.join(coverage)}".lower()
    return any(region in text for region in MUSLIM_REGION_KEYWORDS)


def compute_muslim_charity_fit(has_identity: bool, serves_muslims: bool) -> str:
    """Derive muslim_charity_fit from the two component signals.

    Truth table from spec:
    - has_islamic_identity=TRUE, serves_muslim_populations=TRUE  -> 'high'
    - has_islamic_identity=TRUE, serves_muslim_populations=FALSE -> 'high'
    - has_islamic_identity=FALSE, serves_muslim_populations=TRUE -> 'medium'
    - has_islamic_identity=FALSE, serves_muslim_populations=FALSE -> 'low'
    """
    if has_identity:
        return "high"
    elif serves_muslims:
        return "medium"
    else:
        return "low"


def detect_conflict_zone(geographic_coverage: list[str] | None) -> bool:
    """Check if >50% of geographic coverage is in active conflict zones.

    Used for cost-effectiveness 1.5x threshold adjustment per spec.
    """
    if not geographic_coverage:
        return False
    conflict_count = sum(1 for region in geographic_coverage if any(zone in region.lower() for zone in CONFLICT_ZONES))
    return conflict_count / len(geographic_coverage) > 0.5


def calculate_working_capital_months(
    total_assets: int | None,
    total_liabilities: int | None,
    total_expenses: int | None,
) -> float | None:
    """Calculate working capital in months.

    Formula: (total_assets - total_liabilities) / (total_expenses / 12)
    Returns None if expenses are zero or missing.
    """
    if not total_expenses or total_expenses <= 0:
        return None
    monthly_expenses = total_expenses / 12
    net_assets = (total_assets or 0) - (total_liabilities or 0)
    return round(net_assets / monthly_expenses, 1)


def detect_cause_tags(
    mission: str | None,
    programs: list[str] | None,
    geographic_coverage: list[str] | None,
    zakat_categories: list[str] | None,
    name: str | None,
    website_profile: dict | None = None,
) -> list[str]:
    """Detect non-MECE cause tags based on keywords.

    Returns list of applicable tags from all categories.

    IMPORTANT: Geographic tags only match on geographic_coverage field,
    not the org name or mission. This prevents "Islamic Relief USA" from
    being tagged as serving US communities when they actually serve overseas.
    """
    tags: set[str] = set()

    # Build searchable text - separate sources for different tag types
    programs_text = " ".join(programs or [])
    geo_text = " ".join(geographic_coverage or [])

    # Full text for non-geographic tags (population, intervention, service)
    full_text = f"{name or ''} {mission or ''} {programs_text} {geo_text}".lower()

    # Geographic text ONLY uses geographic_coverage field (areas_served from Candid)
    # NOT programs (which describe activities, not locations)
    # NOT name/mission (which often contain "USA" for US chapters of international orgs)
    # This prevents false positives like:
    #   - "Islamic Relief USA" → not serving US communities
    #   - "US Campaigning" (program name) → not a service area
    geo_only_text = geo_text.lower()

    # Check geographic tags - only match on geographic_coverage
    for tag, keywords in GEOGRAPHIC_TAG_KEYWORDS.items():
        if any(kw in geo_only_text for kw in keywords):
            tags.add(tag)

    # Check non-geographic tags on full text
    non_geo_keywords = {
        **POPULATION_TAG_KEYWORDS,
        **INTERVENTION_TAG_KEYWORDS,
        **SERVICE_TAG_KEYWORDS,
        **CHANGE_TYPE_TAG_KEYWORDS,
    }

    for tag, keywords in non_geo_keywords.items():
        if any(kw in full_text for kw in keywords):
            tags.add(tag)

    # Layer 3: Check extracted program_type_classification from website
    # STRICT CRITERIA for scalable-model and systemic-change tags
    if website_profile:
        systemic_data = website_profile.get("systemic_leverage_data", {})
        if systemic_data:
            program_type = (systemic_data.get("program_type_classification") or "").upper()

            # Add direct-relief for CONSUMPTIVE classification
            if program_type and program_type in PROGRAM_TYPE_TO_TAG:
                tags.add(PROGRAM_TYPE_TO_TAG[program_type])

            # SCALABLE-MODEL: Only if explicitly classified as SCALABLE
            # This is a high bar - means LLM determined their primary approach is replicable
            if program_type == "SCALABLE":
                tags.add("scalable-model")

            # SYSTEMIC-CHANGE: Requires GENERATIVE classification AND evidence
            # Just having policy_wins or legal_aid alone is not enough
            if program_type == "GENERATIVE":
                has_policy_wins = bool(systemic_data.get("policy_wins"))
                has_legal_aid = bool(systemic_data.get("legal_aid_services"))
                if has_policy_wins or has_legal_aid:
                    tags.add("systemic-change")

    # Add conflict-zone tag if applicable
    if detect_conflict_zone(geographic_coverage):
        tags.add("conflict-zone")

    # Add identity tags based on Islamic classification (now uses website signals)
    if has_islamic_identity(name or "", mission, website_profile):
        tags.add("muslim-led")
        tags.add("faith-based")

    # Add zakat asnaf tags from discovered data
    if zakat_categories:
        for cat in zakat_categories:
            if cat.lower() in ZAKAT_ASNAF_TAGS:
                tags.add(cat.lower())

    return sorted(tags)


def detect_evaluation_track(
    founded_year: int | None,
    primary_category: str | None,
    cause_tags: list[str] | None,
) -> str:
    """Determine which evaluation track applies to a charity.

    Phase 1: Detection only (no scoring changes yet).
    Returns 'STANDARD', 'NEW_ORG', or 'RESEARCH_POLICY'.

    Args:
        founded_year: Year the organization was founded (from Candid/website)
        primary_category: The charity's MECE category
        cause_tags: List of cause tags detected for the charity

    Returns:
        The evaluation track string
    """
    current_year = datetime.now(timezone.utc).year

    # Track 1: New Organization (< 3 years old)
    if founded_year and (current_year - founded_year) < 3:
        return "NEW_ORG"

    # Track 2: Research/Policy/Advocacy
    research_policy_categories = {
        "RESEARCH_POLICY",
        "CIVIL_RIGHTS_LEGAL",
        "MEDIA_JOURNALISM",
    }
    research_policy_tags = {"advocacy", "research", "systemic-change"}

    if primary_category in research_policy_categories:
        # Confirm with cause tags if available
        if cause_tags and any(t in research_policy_tags for t in cause_tags):
            return "RESEARCH_POLICY"
        # Category alone is sufficient for civil rights/legal
        if primary_category == "CIVIL_RIGHTS_LEGAL":
            return "RESEARCH_POLICY"

    # Check cause tags even without matching category
    if cause_tags and any(t in research_policy_tags for t in cause_tags):
        return "RESEARCH_POLICY"

    # Track 3: Standard (default)
    return "STANDARD"


def detect_program_focus_tags(
    mission: str | None,
    programs: list[str] | None,
    name: str | None,
    logger: PipelineLogger | None = None,
) -> tuple[list[str], float]:
    """Extract program focus tags using LLM analysis of mission and programs.

    Program focus tags describe WHAT the organization actually DOES, enabling
    similarity matching across category boundaries (e.g., connecting arts/media
    orgs regardless of whether they're classified as PHILANTHROPY or MEDIA).

    Args:
        mission: Organization mission statement
        programs: List of program names/descriptions
        name: Organization name
        logger: Optional logger

    Returns:
        Tuple of (list of program focus tags, LLM cost in USD)
    """
    # Build context for LLM
    context_parts = []
    if name:
        context_parts.append(f"Organization: {name}")
    if mission:
        context_parts.append(f"Mission: {mission}")
    if programs:
        programs_text = ", ".join(programs[:10])  # Limit to avoid token explosion
        context_parts.append(f"Programs: {programs_text}")

    if not context_parts:
        return [], 0.0

    context = "\n".join(context_parts)

    # Build taxonomy description for prompt
    taxonomy = "\n".join([f"- {tag}: {desc}" for tag, desc in PROGRAM_FOCUS_TAGS.items()])

    prompt = f"""Analyze this nonprofit organization and identify which program focus tags best describe their PRIMARY activities.

{context}

Available program focus tags:
{taxonomy}

STRICT RULES:
1. Select 1-2 tags that describe the organization's CORE MISSION
2. Only tag what they PRIMARILY do, not secondary activities
3. "arts-culture-media" is ONLY for organizations whose PRIMARY mission is creating art, films, storytelling, or cultural content production. Do NOT use this tag for:
   - Advocacy organizations that use media for outreach
   - Research orgs that publish reports
   - Religious orgs that produce educational content
4. "advocacy-legal" is for civil rights litigation, legal aid, policy advocacy
5. "research-policy" is for think tanks, academic research, policy analysis
6. "religious-services" is for mosques, religious education, spiritual services
7. When in doubt, use fewer tags - quality over quantity

Return ONLY a JSON array of tag names, e.g.: ["advocacy-legal", "research-policy"]
Return an empty array [] if no tags clearly apply."""

    try:
        client = LLMClient(task=LLMTask.WEBSITE_EXTRACTION, logger=logger)
        response = client.generate(
            prompt=prompt,
            json_mode=True,
            temperature=0.0,  # Deterministic
        )

        # Parse response
        import json

        text = response.text.strip()

        # Handle markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        tags = json.loads(text)

        # Validate tags are in our taxonomy
        valid_tags = [t for t in tags if t in PROGRAM_FOCUS_TAGS]

        return valid_tags, response.cost_usd

    except Exception as e:
        if logger:
            logger.warning(f"Failed to extract program focus tags: {e}")
        return [], 0.0


def compute_transparency_score(candid_data: dict | None) -> float | None:
    """Map Candid seal level to transparency score (0-100)."""
    if not candid_data:
        return None

    profile = candid_data.get("candid_profile", candid_data)
    seal = profile.get("candid_seal") or profile.get("seal_level")

    if seal:
        return CANDID_SEAL_SCORES.get(seal.lower().strip(), 0)
    return None


def extract_financials(
    cn_data: dict | None,
    pp_data: dict | None,
    ein: str,
    source_timestamps: dict[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, dict]]:
    """Extract financial metrics from Charity Navigator and ProPublica data.

    Returns:
        Tuple of (financials dict, source_attribution dict)
    """
    financials: dict[str, Any] = {}
    attribution: dict[str, dict] = {}
    timestamps = source_timestamps or {}

    # Prefer ProPublica (IRS 990) for raw financials
    if pp_data:
        profile = pp_data.get("propublica_990", pp_data)
        pp_scraped = timestamps.get("propublica")
        tax_year = profile.get("tax_year")
        display_name = f"Form 990 ({tax_year})" if tax_year else "ProPublica Form 990"

        if profile.get("total_revenue"):
            financials["total_revenue"] = profile.get("total_revenue")
            attribution["total_revenue"] = create_attribution(
                "total_revenue", profile.get("total_revenue"), "propublica", ein, pp_scraped, display_name=display_name
            )
        if profile.get("program_expenses"):
            financials["program_expenses"] = profile.get("program_expenses")
            attribution["program_expenses"] = create_attribution(
                "program_expenses",
                profile.get("program_expenses"),
                "propublica",
                ein,
                pp_scraped,
                display_name=display_name,
            )
        if profile.get("admin_expenses"):
            financials["admin_expenses"] = profile.get("admin_expenses")
            attribution["admin_expenses"] = create_attribution(
                "admin_expenses",
                profile.get("admin_expenses"),
                "propublica",
                ein,
                pp_scraped,
                display_name=display_name,
            )
        if profile.get("fundraising_expenses"):
            financials["fundraising_expenses"] = profile.get("fundraising_expenses")
            attribution["fundraising_expenses"] = create_attribution(
                "fundraising_expenses",
                profile.get("fundraising_expenses"),
                "propublica",
                ein,
                pp_scraped,
                display_name=display_name,
            )

    # Fallback to CN for financials
    if cn_data:
        profile = cn_data.get("cn_profile", cn_data)
        cn_scraped = timestamps.get("charity_navigator")

        if not financials.get("total_revenue") and profile.get("total_revenue"):
            financials["total_revenue"] = profile.get("total_revenue")
            attribution["total_revenue"] = create_attribution(
                "total_revenue",
                profile.get("total_revenue"),
                "charity_navigator",
                ein,
                cn_scraped,
                section="financials",
            )
        if not financials.get("program_expenses") and profile.get("program_expenses"):
            financials["program_expenses"] = profile.get("program_expenses")
            attribution["program_expenses"] = create_attribution(
                "program_expenses",
                profile.get("program_expenses"),
                "charity_navigator",
                ein,
                cn_scraped,
                section="financials",
            )
        admin_exp = profile.get("admin_expenses") or profile.get("administrative_expenses")
        if not financials.get("admin_expenses") and admin_exp:
            financials["admin_expenses"] = admin_exp
            attribution["admin_expenses"] = create_attribution(
                "admin_expenses", admin_exp, "charity_navigator", ein, cn_scraped, section="financials"
            )
        if not financials.get("fundraising_expenses") and profile.get("fundraising_expenses"):
            financials["fundraising_expenses"] = profile.get("fundraising_expenses")
            attribution["fundraising_expenses"] = create_attribution(
                "fundraising_expenses",
                profile.get("fundraising_expenses"),
                "charity_navigator",
                ein,
                cn_scraped,
                section="financials",
            )

        # CN scores - only use if fully rated (not just Encompass Award)
        if profile.get("overall_score") and profile.get("cn_is_rated"):
            financials["charity_navigator_score"] = profile.get("overall_score")
            attribution["charity_navigator_score"] = create_attribution(
                "charity_navigator_score",
                profile.get("overall_score"),
                "charity_navigator",
                ein,
                cn_scraped,
                section="ratings",
            )

        # CN ratios (pre-calculated)
        if profile.get("program_expense_ratio"):
            financials["program_expense_ratio"] = profile.get("program_expense_ratio")
            attribution["program_expense_ratio"] = create_attribution(
                "program_expense_ratio",
                profile.get("program_expense_ratio"),
                "charity_navigator",
                ein,
                cn_scraped,
                section="financials",
            )

    # Calculate program_expense_ratio if not from CN
    if not financials.get("program_expense_ratio"):
        program = financials.get("program_expenses")
        total = financials.get("total_revenue") or financials.get("total_expenses")
        if program and total and total > 0:
            ratio = program / total
            financials["program_expense_ratio"] = ratio
            attribution["program_expense_ratio"] = {
                "source_name": "Calculated",
                "source_url": None,
                "value": ratio,
                "derived_from": ["program_expenses", "total_revenue"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    # NOTE: Expense ratio validation (rejecting ratios > 3x) is handled by
    # CharityMetricsAggregator.aggregate() - see charity_metrics_aggregator.py:1596-1607
    # No need to duplicate here.

    # Convert to int for storage (DoltDB schema uses int for financials)
    for key in ["total_revenue", "program_expenses", "admin_expenses", "fundraising_expenses"]:
        if financials.get(key):
            financials[key] = int(financials[key])

    return financials, attribution


class EmptyParsedJsonError(Exception):
    """Raised when parsed_json is empty but success=true (crawl bug)."""

    pass


def update_charities_table(
    ein: str,
    pp_data: dict | None,
    candid_data: dict | None,
    website_data: dict | None,
    charity_repo: CharityRepository,
    pilot_name: str | None = None,
) -> int:
    """Propagate basic fields from raw sources to charities table.

    Updates city/state/zip/mission fields that exist in charities table
    but were not being populated during synthesis.

    Args:
        ein: Charity EIN
        pp_data: ProPublica data (most authoritative for address fields)
        candid_data: Candid data (secondary source)
        website_data: Website data (for mission)
        charity_repo: Repository for charities table
        pilot_name: Name from pilot_charities.txt (fallback if ProPublica/Candid fail)

    Returns:
        Number of fields updated
    """
    updates: dict[str, Any] = {}

    # Name from ProPublica (most authoritative) - fix records where name==EIN
    existing = charity_repo.get(ein)
    existing_name = existing.get("name", "") if existing else ""
    ein_as_name = not existing_name or existing_name == ein or existing_name == f"EIN {ein}" or existing_name == "Unknown"
    if ein_as_name:
        # Try ProPublica first, then Candid
        name = None
        if pp_data:
            pp = pp_data.get("propublica_990", pp_data)
            name = pp.get("name")
        if not name and candid_data:
            cp = candid_data.get("candid_profile", candid_data)
            name = cp.get("name") or cp.get("organization_name")
        if not name and pilot_name:
            name = pilot_name
        if name and name != ein:
            updates["name"] = name

    # Address fields from ProPublica (most authoritative - IRS data)
    if pp_data:
        pp = pp_data.get("propublica_990", pp_data)
        if pp.get("address"):
            updates["address"] = pp.get("address")
        if pp.get("city"):
            updates["city"] = pp.get("city")
        if pp.get("state"):
            updates["state"] = pp.get("state")
        # ProPublica may use 'zipcode' or 'zip'
        zip_val = pp.get("zipcode") or pp.get("zip")
        if zip_val:
            updates["zip"] = str(zip_val)

    # Fallback to Candid for address fields
    if candid_data:
        cp = candid_data.get("candid_profile", candid_data)
        if not updates.get("city") and cp.get("city"):
            updates["city"] = cp.get("city")
        if not updates.get("state") and cp.get("state"):
            updates["state"] = cp.get("state")
        if not updates.get("zip") and cp.get("zip"):
            updates["zip"] = cp.get("zip")

    # Mission - Candid > Website (fallback chain)
    mission = None
    if candid_data:
        cp = candid_data.get("candid_profile", candid_data)
        mission = cp.get("mission")
    if not mission and website_data:
        wp = website_data.get("website_profile", website_data)
        mission = wp.get("mission")  # Use "mission", not "mission_statement"
    if mission:
        updates["mission"] = mission

    # Only update if we have fields to update
    if updates:
        # Use direct UPDATE since charity must already exist
        # (synthesize_charity checks this before calling us)
        from src.db.client import execute_query

        set_clause = ", ".join([f"{col} = %s" for col in updates.keys()])
        sql = f"UPDATE charities SET {set_clause} WHERE ein = %s"
        values = list(updates.values()) + [ein]
        execute_query(sql, tuple(values), fetch="none")

    return len(updates)


def synthesize_charity(
    ein: str,
    raw_repo: RawDataRepository,
    charity_repo: CharityRepository,
    pilot_name: str | None = None,
) -> dict[str, Any]:
    """Synthesize data for a single charity with source attribution.

    Uses deterministic keyword-based classification (no LLM).
    Returns cost_usd: 0.0 (no LLM calls in this phase).
    """
    result = {"ein": ein, "success": False, "fields_computed": 0, "attribution_count": 0, "cost_usd": 0.0}

    # Get charity info
    charity = charity_repo.get(ein)
    if not charity:
        result["error"] = "Charity not found"
        return result

    # Get raw data from all sources
    raw_data = raw_repo.get_for_charity(ein)
    if not raw_data:
        result["error"] = "No raw data found"
        return result

    # S-005: Check for empty parsed_json (pipeline bug - should abort)
    # Use falsy check to catch None, {}, and other empty values
    for rd in raw_data:
        if rd.get("success") and not rd.get("parsed_json"):
            source = rd.get("source")
            # Mark as failed in database
            from src.db.client import execute_query

            execute_query(
                "UPDATE raw_scraped_data SET success = %s, error_message = %s WHERE charity_ein = %s AND source = %s",
                (False, "Empty parsed_json detected - crawl bug", ein, source),
                fetch="none",
            )
            raise EmptyParsedJsonError(f"Empty parsed_json for {ein}/{source}")

    # Organize by source and collect timestamps
    sources: dict[str, dict] = {}
    source_timestamps: dict[str, str] = {}
    for rd in raw_data:
        source = rd.get("source")
        if rd.get("success") and rd.get("parsed_json"):
            sources[source] = rd["parsed_json"]
            if rd.get("scraped_at"):
                source_timestamps[source] = rd["scraped_at"]

    # Extract data from each source
    cn_data = sources.get("charity_navigator")
    pp_data = sources.get("propublica")
    candid_data = sources.get("candid")
    website_data = sources.get("website")
    grants_data = sources.get("form990_grants")
    discovered_data = sources.get("discovered")

    # Update charities table with basic fields (city/state/zip/mission)
    # This ensures these fields propagate from raw_scraped_data to charities table
    update_charities_table(ein, pp_data, candid_data, website_data, charity_repo, pilot_name=pilot_name)

    # Get name and mission for Muslim charity detection
    name = charity.get("name", "")
    mission = charity.get("mission")

    # Try to get mission from raw sources if not in charity record
    if not mission:
        if candid_data:
            profile = candid_data.get("candid_profile", candid_data)
            mission = profile.get("mission")
        if not mission and cn_data:
            profile = cn_data.get("cn_profile", cn_data)
            mission = profile.get("mission")
        if not mission and website_data:
            profile = website_data.get("website_profile", website_data)
            mission = profile.get("mission")  # Fixed: was "mission_statement"

    # Get geographic_coverage from Candid or website
    geographic_coverage: list[str] = []
    if candid_data:
        profile = candid_data.get("candid_profile", candid_data)
        geographic_coverage = profile.get("areas_served", [])
    if not geographic_coverage and website_data:
        profile = website_data.get("website_profile", website_data)
        geographic_coverage = profile.get("geographic_coverage", [])

    # Get source URLs for attribution (per spec: must come from crawled data)
    candid_url: str | None = None
    if candid_data:
        profile = candid_data.get("candid_profile", candid_data)
        candid_url = profile.get("candid_url")  # Extracted during crawl
    website_url: str | None = charity.get("website")  # From charities table

    # Use CharityMetricsAggregator for additional fields FIRST
    # If aggregator fails, we don't save anything (all-or-nothing)
    try:
        # Unwrap nested profile data (raw data has e.g. {"cn_profile": {...}})
        metrics = CharityMetricsAggregator.aggregate(
            charity_id=0,  # Not used for this purpose
            ein=ein,
            cn_profile=cn_data.get("cn_profile", cn_data) if cn_data else None,
            propublica_990=pp_data.get("propublica_990", pp_data) if pp_data else None,
            candid_profile=candid_data.get("candid_profile", candid_data) if candid_data else None,
            grants_profile=grants_data.get("grants_profile", grants_data) if grants_data else None,
            website_profile=website_data.get("website_profile", website_data) if website_data else None,
            discovered_profile=discovered_data.get("discovered_profile", discovered_data) if discovered_data else None,
        )
    except Exception as e:
        result["error"] = f"Aggregator failed: {e}"
        return result  # Don't save partial data

    # Flag hallucination-prone fields that lack cross-source verification
    from src.validators.hallucination_denylist import flag_unverified_fields

    verified_fields = {
        field_name for field_name, status in metrics.corroboration_status.items() if status.get("passed", False)
    }
    metrics_dict = metrics.model_dump()
    flagged = flag_unverified_fields(metrics_dict, verified_fields=verified_fields)
    flagged_names = [k for k in flagged if k.endswith("_unverified") and not k.startswith("zakat_verification")]
    if flagged_names:
        logging.getLogger(__name__).info(
            f"EIN {ein}: {len(flagged_names)} hallucination-prone fields flagged as unverified: {flagged_names}"
        )

    # Compute derived fields
    synthesized = CharityData(charity_ein=ein)

    # Collect all source attribution
    source_attribution: dict[str, dict] = {}

    # Extract website profile for identity detection
    website_profile = website_data.get("website_profile", website_data) if website_data else None

    # Muslim charity classification (deterministic, no LLM)
    # Uses keyword matching + website signals (accepts_zakat, shariah_board, etc.)
    identity = has_islamic_identity(name, mission, website_profile)
    serves_muslims = serves_muslim_populations(mission, geographic_coverage)
    fit = compute_muslim_charity_fit(identity, serves_muslims)

    synthesized.has_islamic_identity = identity
    synthesized.serves_muslim_populations = serves_muslims
    synthesized.muslim_charity_fit = fit

    # Collect which Islamic identity signals matched (for zakat_metadata)
    islamic_signals = _collect_islamic_identity_signals(name, mission, website_profile)

    # Financial metrics with attribution
    financials, fin_attribution = extract_financials(cn_data, pp_data, ein, source_timestamps)
    source_attribution.update(fin_attribution)

    synthesized.total_revenue = financials.get("total_revenue")
    synthesized.program_expenses = financials.get("program_expenses")
    synthesized.admin_expenses = financials.get("admin_expenses")
    synthesized.fundraising_expenses = financials.get("fundraising_expenses")
    synthesized.program_expense_ratio = financials.get("program_expense_ratio")
    synthesized.charity_navigator_score = financials.get("charity_navigator_score")

    # Transparency score with attribution
    synthesized.transparency_score = compute_transparency_score(candid_data)
    if synthesized.transparency_score and candid_data:
        candid_profile = candid_data.get("candid_profile", candid_data)
        seal = candid_profile.get("candid_seal") or candid_profile.get("seal_level")
        source_attribution["transparency_score"] = create_attribution(
            "transparency_score",
            synthesized.transparency_score,
            "candid",
            ein,
            source_timestamps.get("candid"),
            display_name=f"Candid {seal.title()} Seal" if seal else "Candid",
            candid_url=candid_url,
        )

    # Extract additional fields from aggregator with attribution
    synthesized.detected_cause_area = metrics.detected_cause_area
    synthesized.claims_zakat_eligible = metrics.zakat_claim_detected  # Fixed: was claims_zakat_eligible
    synthesized.beneficiaries_served_annually = metrics.beneficiaries_served_annually

    # Upgrade muslim_charity_fit if zakat was corroborated post-aggregation.
    # The initial has_islamic_identity check deliberately excludes accepts_zakat
    # (LLMs hallucinate it). But by this point, zakat_claim_detected has passed
    # two-source corroboration in the aggregator — safe to trust.
    if metrics.zakat_claim_detected and not identity:
        synthesized.has_islamic_identity = True
        synthesized.muslim_charity_fit = compute_muslim_charity_fit(True, serves_muslims)
    synthesized.has_annual_report = metrics.annual_report_published
    synthesized.has_audited_financials = metrics.has_financial_audit
    synthesized.candid_seal = metrics.candid_seal

    # =========================================================================
    # Previously missing fields - now persisted (see data pipeline audit)
    # =========================================================================

    # Financial health (balance sheet) - from ProPublica/CN
    synthesized.total_assets = int(metrics.total_assets) if metrics.total_assets else None
    synthesized.total_liabilities = int(metrics.total_liabilities) if metrics.total_liabilities else None
    synthesized.net_assets = int(metrics.net_assets) if metrics.net_assets else None

    # Governance fields - from CN/Candid/ProPublica
    synthesized.board_size = metrics.board_size
    synthesized.independent_board_members = metrics.independent_board_members
    synthesized.ceo_compensation = int(metrics.ceo_compensation) if metrics.ceo_compensation else None

    # Form 990 status - from ProPublica
    synthesized.form_990_exempt = metrics.form_990_exempt
    synthesized.form_990_exempt_reason = metrics.form_990_exempt_reason

    # Targeting fields - from Candid
    if metrics.populations_served:
        synthesized.populations_served = metrics.populations_served
    if metrics.geographic_coverage:
        synthesized.geographic_coverage = metrics.geographic_coverage

    # Website evidence signals - used in scoring, now persisted for audit trail
    website_evidence = {
        "reports_annual_report": metrics.website_reports_annual_report,
        "reports_methodology": metrics.website_reports_methodology,
        "reports_outcome_metrics": metrics.website_reports_outcome_metrics,
        "reports_board_info": metrics.website_reports_board_info,
        "disclosure_richness": metrics.website_disclosure_richness,
        "claims_rcts": metrics.website_claims_rcts,
        "claims_third_party_eval": metrics.website_claims_third_party_eval,
        "claims_longitudinal": metrics.website_claims_longitudinal,
    }
    # Only save if we have any signals
    if any(v for v in website_evidence.values()):
        synthesized.website_evidence_signals = website_evidence

    # Add attribution for aggregator fields
    website_scraped = source_timestamps.get("website")
    candid_scraped = source_timestamps.get("candid")

    if synthesized.claims_zakat_eligible is not None:
        # Use the specific zakat page URL if available from discovered profile
        zakat_url = None
        if discovered_data:
            discovered_profile = discovered_data.get("discovered_profile", discovered_data)
            zakat_info = discovered_profile.get("zakat", {}) if discovered_profile else {}
            zakat_url = zakat_info.get("accepts_zakat_url") if zakat_info else None
            if (
                isinstance(zakat_url, str)
                and "vertexaisearch.cloud.google.com" in zakat_url
                and "grounding-api-redirect" in zakat_url
            ):
                zakat_url = None
        source_attribution["claims_zakat_eligible"] = create_attribution(
            "claims_zakat_eligible",
            synthesized.claims_zakat_eligible,
            "website",
            ein,
            website_scraped,
            website_url=zakat_url or website_url,  # Prefer specific zakat URL
        )
    if synthesized.has_annual_report is not None:
        source_attribution["has_annual_report"] = create_attribution(
            "has_annual_report", synthesized.has_annual_report, "website", ein, website_scraped, website_url=website_url
        )
    if synthesized.has_audited_financials is not None:
        source_attribution["has_audited_financials"] = create_attribution(
            "has_audited_financials",
            synthesized.has_audited_financials,
            "website",
            ein,
            website_scraped,
            website_url=website_url,
        )
    if synthesized.candid_seal:
        source_attribution["candid_seal"] = create_attribution(
            "candid_seal", synthesized.candid_seal, "candid", ein, candid_scraped, candid_url=candid_url
        )

    # =========================================================================
    # New fields from spec (synthesize.md lines 106-119)
    # =========================================================================

    # Extract ntee_code from propublica
    if pp_data:
        pp_profile = pp_data.get("propublica_990", pp_data)
        ntee_code = pp_profile.get("ntee_code")
        if ntee_code:
            synthesized.ntee_code = ntee_code
            source_attribution["ntee_code"] = create_attribution(
                "ntee_code", ntee_code, "propublica", ein, source_timestamps.get("propublica")
            )

    # Compute is_conflict_zone (>50% of geographic coverage in conflict zones)
    synthesized.is_conflict_zone = detect_conflict_zone(geographic_coverage)

    # Compute working_capital_months from balance sheet data
    if pp_data:
        pp_profile = pp_data.get("propublica_990", pp_data)
        total_assets = pp_profile.get("total_assets")
        total_liabilities = pp_profile.get("total_liabilities")
        total_expenses = pp_profile.get("total_expenses")
        working_capital = calculate_working_capital_months(total_assets, total_liabilities, total_expenses)
        if working_capital is not None:
            synthesized.working_capital_months = working_capital
            source_attribution["working_capital_months"] = {
                "source_name": "Calculated from Form 990",
                "source_url": build_source_url("propublica", ein),
                "value": working_capital,
                "derived_from": ["total_assets", "total_liabilities", "total_expenses"],
                "timestamp": source_timestamps.get("propublica") or datetime.now(timezone.utc).isoformat(),
            }

    # S-003: Track cause_detection_source based on how detected_cause_area was set
    # Per spec: 'keywords', 'ntee_fallback', or 'unknown'
    if synthesized.detected_cause_area:
        # CharityMetricsAggregator detects cause area via keyword matching
        synthesized.cause_detection_source = "keywords"
    elif synthesized.ntee_code:
        # Cause area not detected via keywords, but NTEE code exists
        # Could potentially map NTEE to a cause area as fallback
        synthesized.cause_detection_source = "ntee_fallback"
    else:
        synthesized.cause_detection_source = "unknown"

    # Detect cause tags (non-MECE, multiple allowed)
    # Extract programs and zakat categories from source data
    programs: list[str] = []
    zakat_categories: list[str] | None = None

    if candid_data:
        candid_profile = candid_data.get("candid_profile", candid_data)
        programs = candid_profile.get("programs", []) or []
    if website_data:
        website_profile = website_data.get("website_profile", website_data)
        if not programs:
            programs = website_profile.get("programs", []) or []
    if discovered_data:
        discovered_profile = discovered_data.get("discovered_profile", discovered_data)
        zakat_info = discovered_profile.get("zakat", {}) if discovered_profile else {}
        zakat_categories = zakat_info.get("zakat_categories_served") if zakat_info else None

    cause_tags = detect_cause_tags(
        mission=mission,
        programs=programs,
        geographic_coverage=geographic_coverage,
        zakat_categories=zakat_categories,
        name=name,
        website_profile=website_profile,
    )
    if cause_tags:
        synthesized.cause_tags = cause_tags

    # =========================================================================
    # Program Focus Tags (LLM-extracted for similarity matching)
    # =========================================================================
    program_focus_tags, focus_cost = detect_program_focus_tags(
        mission=mission,
        programs=programs,
        name=name,
    )
    if program_focus_tags:
        synthesized.program_focus_tags = program_focus_tags
    result["cost_usd"] += focus_cost

    # =========================================================================
    # Strategic Evidence (deterministic signal extraction, no LLM)
    # =========================================================================
    strategic_evidence = compute_strategic_evidence(metrics)
    synthesized.strategic_evidence = strategic_evidence.to_dict()

    # =========================================================================
    # Strategic Classification (LLM-based, for Strategic Believer lens)
    # =========================================================================
    strategic_class, strategic_cost = classify_charity(
        metrics=metrics,
        cause_tags=cause_tags,
        strategic_evidence=strategic_evidence,
    )
    if strategic_class:
        synthesized.strategic_classification = classification_to_dict(strategic_class)
    result["cost_usd"] += strategic_cost

    # =========================================================================
    # Zakat Metadata (bundle rich zakat data into single JSON column)
    # =========================================================================
    zakat_metadata: dict = {}

    if zakat_categories:
        zakat_metadata["asnaf_categories_served"] = zakat_categories

    # Collect zakat info from discovered profile
    if discovered_data:
        discovered_profile = discovered_data.get("discovered_profile", discovered_data)
        zakat_info = discovered_profile.get("zakat", {}) if discovered_profile else {}
        if zakat_info:
            if zakat_info.get("accepts_zakat_url"):
                zakat_metadata["zakat_policy_url"] = zakat_info["accepts_zakat_url"]
            if zakat_info.get("zakat_distribution_details"):
                zakat_metadata["zakat_distribution_details"] = zakat_info["zakat_distribution_details"]
            if zakat_info.get("direct_page_verified") is not None:
                zakat_metadata["direct_page_verified"] = zakat_info["direct_page_verified"]
            if zakat_info.get("zakat_verification_confidence") is not None:
                zakat_metadata["verification_confidence"] = zakat_info["zakat_verification_confidence"]

    if islamic_signals:
        zakat_metadata["islamic_identity_signals"] = islamic_signals

    if zakat_metadata:
        synthesized.zakat_metadata = zakat_metadata

    # =========================================================================
    # Primary Category Assignment (MECE - for donor discovery)
    # Priority: Manual YAML mapping > Automatic detection from cause area
    # =========================================================================
    manual_category = get_charity_category(ein)
    if manual_category:
        # Use manually mapped category from charity_categories.yaml
        synthesized.primary_category = manual_category
        category_info = get_category_info(manual_category)
        if category_info:
            synthesized.category_importance = category_info.get("importance")
            synthesized.category_neglectedness = category_info.get("neglectedness")
    else:
        # Fallback: map detected_cause_area to primary_category
        auto_category = map_cause_to_category(synthesized.detected_cause_area)
        if auto_category:
            synthesized.primary_category = auto_category
            category_info = get_category_info(auto_category)
            if category_info:
                synthesized.category_importance = category_info.get("importance")
                synthesized.category_neglectedness = category_info.get("neglectedness")

    # Sync primary_category back to charities.category for frontend display
    if synthesized.primary_category:
        display_name = CATEGORY_DISPLAY_NAMES.get(synthesized.primary_category, synthesized.primary_category)
        from src.db.client import execute_query

        execute_query(
            "UPDATE charities SET category = %s WHERE ein = %s",
            (display_name, ein),
            fetch="none",
        )

    # =========================================================================
    # Evaluation Track Detection (Phase 1: Detection + Display only)
    # Determines NEW_ORG, RESEARCH_POLICY, or STANDARD track
    # =========================================================================

    # Extract founded_year from website, Candid, or ProPublica (IRS ruling year)
    founded_year: int | None = None
    founded_source: str | None = None
    if website_profile:
        founded_year = website_profile.get("founded_year")
        if founded_year:
            founded_source = "website"
    if not founded_year and candid_data:
        candid_profile = candid_data.get("candid_profile", candid_data)
        founded_year = candid_profile.get("founded_year")
        if founded_year:
            founded_source = "candid"
    # Fallback to ProPublica IRS ruling year (when org got 501c3 status)
    if not founded_year and pp_data:
        pp_profile = pp_data.get("propublica_990", pp_data)
        founded_year = pp_profile.get("irs_ruling_year")
        if founded_year:
            founded_source = "propublica"

    if founded_year and founded_source:
        synthesized.founded_year = founded_year
        source_attribution["founded_year"] = create_attribution(
            "founded_year", founded_year, founded_source, ein, source_timestamps.get(founded_source)
        )

    # Detect evaluation track based on age and category
    evaluation_track = detect_evaluation_track(
        founded_year=founded_year,
        primary_category=synthesized.primary_category,
        cause_tags=cause_tags,
    )
    synthesized.evaluation_track = evaluation_track

    # Theory of change and grants from aggregator
    if metrics.theory_of_change:
        synthesized.theory_of_change = metrics.theory_of_change
    if metrics.grants_made:
        synthesized.grants_made = metrics.grants_made

    # Store source attribution
    synthesized.source_attribution = source_attribution

    # =========================================================================
    # Persist full CharityMetrics blob (single source of truth for baseline)
    # Apply synthesis enrichments to metrics BEFORE serialization so baseline
    # can deserialize and score without re-aggregating.
    # =========================================================================
    metrics.is_muslim_focused = synthesized.muslim_charity_fit == "high"
    if synthesized.working_capital_months is not None:
        metrics.working_capital_ratio = synthesized.working_capital_months
    if synthesized.founded_year and not metrics.founded_year:
        metrics.founded_year = synthesized.founded_year

    # Serialize enriched metrics as JSON blob
    synthesized.metrics_json = metrics.model_dump(mode="json")

    # Persist individual scorer-critical columns (for DoltDB queryability)
    synthesized.total_expenses = int(metrics.total_expenses) if metrics.total_expenses else None
    synthesized.cn_overall_score = metrics.cn_overall_score
    synthesized.cn_financial_score = metrics.cn_financial_score
    synthesized.cn_accountability_score = metrics.cn_accountability_score
    synthesized.employees_count = metrics.employees_count
    synthesized.volunteers_count = metrics.volunteers_count
    synthesized.has_theory_of_change = metrics.has_theory_of_change
    synthesized.reports_outcomes = metrics.reports_outcomes
    synthesized.has_outcome_methodology = metrics.has_outcome_methodology
    synthesized.has_multi_year_metrics = metrics.has_multi_year_metrics
    synthesized.third_party_evaluated = metrics.third_party_evaluated
    synthesized.evaluation_sources = metrics.evaluation_sources if metrics.evaluation_sources else None
    synthesized.receives_foundation_grants = metrics.receives_foundation_grants
    synthesized.candid_metrics_count = metrics.candid_metrics_count if metrics.candid_metrics_count > 0 else None
    synthesized.candid_max_years_tracked = (
        metrics.candid_max_years_tracked if metrics.candid_max_years_tracked > 0 else None
    )
    synthesized.no_filings = metrics.no_filings
    synthesized.zakat_claim_evidence = metrics.zakat_claim_evidence

    # Determine nonprofit size tier
    if synthesized.total_revenue and synthesized.total_revenue > 10_000_000:
        synthesized.nonprofit_size_tier = "large_nonprofit"
    elif synthesized.total_revenue and synthesized.total_revenue > 1_000_000:
        synthesized.nonprofit_size_tier = "mid_nonprofit"
    else:
        synthesized.nonprofit_size_tier = "small_nonprofit"

    # Count non-None fields
    fields_computed = sum(
        1
        for v in [
            synthesized.has_islamic_identity,
            synthesized.serves_muslim_populations,
            synthesized.muslim_charity_fit,
            synthesized.total_revenue,
            synthesized.program_expenses,
            synthesized.admin_expenses,
            synthesized.fundraising_expenses,
            synthesized.program_expense_ratio,
            synthesized.charity_navigator_score,
            synthesized.transparency_score,
            synthesized.detected_cause_area,
            synthesized.claims_zakat_eligible,
            synthesized.beneficiaries_served_annually,
            synthesized.has_annual_report,
            synthesized.has_audited_financials,
            synthesized.candid_seal,
            # New fields from spec
            synthesized.ntee_code,
            synthesized.is_conflict_zone,
            synthesized.working_capital_months,
            synthesized.cause_detection_source,
            synthesized.cause_tags,
            synthesized.program_focus_tags,  # LLM-extracted for similarity
            # Category fields for donor discovery
            synthesized.primary_category,
            synthesized.category_importance,
            synthesized.category_neglectedness,
            # Evaluation track fields
            synthesized.evaluation_track,
            synthesized.founded_year,
        ]
        if v is not None
    )

    # Success requires at least one field computed
    if fields_computed == 0:
        result["error"] = "No fields computed"
        return result

    result["synthesized"] = synthesized
    result["fields_computed"] = fields_computed
    result["attribution_count"] = len(source_attribution)
    result["success"] = True
    return result


def load_pilot_charities(file_path: str) -> list[str]:
    """Load charities from pilot_charities.txt format (Name | EIN | URL | Comments)."""
    from src.utils.charity_loader import load_pilot_eins

    return load_pilot_eins(file_path)


def main():
    parser = argparse.ArgumentParser(description="Synthesize charity data from raw sources")
    parser.add_argument("--ein", type=str, help="Single charity EIN to process")
    parser.add_argument("--charities", type=str, help="Path to charities file")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")
    parser.add_argument("--force", action="store_true", help="Force re-synthesis even if cache is valid")
    args = parser.parse_args()

    # Setup logging
    logger = PipelineLogger("P2:Synthesize")

    # Determine which charities to process
    # pilot_names maps EIN -> name from pilot_charities.txt (fallback for missing names)
    pilot_names: dict[str, str] = {}
    if args.ein:
        eins = [args.ein]
    elif args.charities:
        from src.utils.charity_loader import load_charities_from_file

        charity_entries = load_charities_from_file(args.charities)
        eins = [c["ein"] for c in charity_entries]
        pilot_names = {c["ein"]: c["name"] for c in charity_entries}
    else:
        # Default: process all charities in database
        charity_repo = CharityRepository()
        all_charities = charity_repo.get_all()
        eins = [c["ein"] for c in all_charities]

    if not eins:
        print("No charities to process")
        return

    # Initialize repositories (no LLM needed - deterministic processing)
    charity_repo = CharityRepository()
    raw_repo = RawDataRepository()
    data_repo = CharityDataRepository()

    print(f"\n{'=' * 60}")
    print(f"SYNTHESIZE: {len(eins)} CHARITIES")
    print(f"{'=' * 60}\n")

    # Smart caching: skip charities with valid cache
    cache_repo = PhaseCacheRepository()

    # Process each charity
    success_count = 0
    skipped_count = 0
    total_fields = 0
    total_attributions = 0
    failed_charities: list[tuple[str, str]] = []
    successful_eins: list[str] = []

    for i, ein in enumerate(eins, 1):
        # Check cache
        should_run, cache_reason = check_phase_cache(ein, "synthesize", cache_repo, force=args.force)
        if not should_run:
            skipped_count += 1
            print(f"[{i}/{len(eins)}] ⊘ {ein}: Cache hit — {cache_reason}")
            continue

        try:
            result = synthesize_charity(ein, raw_repo, charity_repo, pilot_name=pilot_names.get(ein))
        except EmptyParsedJsonError as e:
            # Critical error - abort run per spec
            print(f"\n{'=' * 60}")
            print("CRITICAL: EMPTY PARSED_JSON DETECTED - ABORTING")
            print(f"{'=' * 60}")
            print(f"Error: {e}")
            print("\nThis indicates a crawl phase bug. Debug and fix before continuing.")
            sys.exit(1)

        if result["success"]:
            # Save to database
            try:
                data_repo.upsert(result["synthesized"])
            except Exception as e:
                # Database write failure - abort run per spec
                print(f"\n{'=' * 60}")
                print("DATABASE WRITE FAILED - ABORTING")
                print(f"{'=' * 60}")
                print(f"Error: {e}")
                sys.exit(1)

            success_count += 1
            successful_eins.append(ein)
            total_fields += result["fields_computed"]
            total_attributions += result.get("attribution_count", 0)
            update_phase_cache(ein, "synthesize", cache_repo)

            status = "✓"
            attr_count = result.get("attribution_count", 0)
            details = f"{result['fields_computed']} fields, {attr_count} attributed"
        else:
            status = "✗"
            details = result.get("error", "Unknown error")
            failed_charities.append((ein, details))

        if args.verbose or not result["success"]:
            print(f"[{i}/{len(eins)}] {status} {ein}: {details}")
        else:
            # Concise output
            print(f"[{i}/{len(eins)}] {status} {ein} ({result['fields_computed']} fields)")

    # ── Quality gate: run synthesize judge per charity ──
    from src.judges.inline_quality import run_quality_gate_batch

    quality_failed_eins = run_quality_gate_batch("synthesize", successful_eins)
    for failed_ein in quality_failed_eins:
        cache_repo.delete(failed_ein, "synthesize")

    # Commit changes to DoltDB
    if success_count > 0:
        commit_hash = dolt.commit(f"Synthesize: {success_count} charities, {total_fields} fields computed")
        if commit_hash:
            print(f"\n✓ Committed to DoltDB: {commit_hash[:8]}")

    # Summary
    print(f"\n{'=' * 60}")
    print("SYNTHESIS COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Success: {success_count}/{len(eins)}")
    if skipped_count > 0:
        print(f"  Cached: {skipped_count}/{len(eins)}")
    if failed_charities:
        print(f"  Failed: {len(failed_charities)}/{len(eins)}")
    print(f"  Total fields computed: {total_fields}")
    print(f"  Total source attributions: {total_attributions}")

    if quality_failed_eins:
        print(f"\n  ⛔ Quality gate failures: {len(quality_failed_eins)} charities")
        print("     These charities have data errors that must be fixed before proceeding.")

    if failed_charities:
        print("\n  ⛔ Processing failures:")
        for ein, error in failed_charities:
            print(f"     {ein}: {error}")

    print("\nNext: Run baseline scorer")
    print("  uv run python baseline.py")

    # Exit with error if quality gate failed
    if quality_failed_eins or failed_charities:
        if quality_failed_eins:
            print(f"\n⛔ Exiting with error: {len(quality_failed_eins)} charities failed quality gate")
        if failed_charities:
            print(f"⛔ Exiting with error: {len(failed_charities)} charities failed synthesis")
        sys.exit(1)


if __name__ == "__main__":
    main()
