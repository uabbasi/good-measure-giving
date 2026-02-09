"""
NTEE (National Taxonomy of Exempt Entities) Code Mapper.

Maps NTEE codes to human-readable categories for charities.
NTEE is the standard classification system used by the IRS and nonprofit databases.
"""

from typing import Optional

# Major NTEE categories (first letter)
NTEE_MAJOR_CATEGORIES = {
    "A": "Arts, Culture & Humanities",
    "B": "Education",
    "C": "Environment",
    "D": "Animal-Related",
    "E": "Health Care",
    "F": "Mental Health & Crisis Intervention",
    "G": "Diseases, Disorders & Medical Disciplines",
    "H": "Medical Research",
    "I": "Crime & Legal-Related",
    "J": "Employment",
    "K": "Food, Agriculture & Nutrition",
    "L": "Housing & Shelter",
    "M": "Public Safety, Disaster Preparedness & Relief",
    "N": "Recreation & Sports",
    "O": "Youth Development",
    "P": "Human Services",
    "Q": "International, Foreign Affairs & National Security",
    "R": "Civil Rights, Social Action & Advocacy",
    "S": "Community Improvement & Capacity Building",
    "T": "Philanthropy, Voluntarism & Grantmaking Foundations",
    "U": "Science & Technology",
    "V": "Social Science",
    "W": "Public & Societal Benefit",
    "X": "Religion-Related",
    "Y": "Mutual & Membership Benefit",
    "Z": "Unknown",
}


# Detailed NTEE subcategories for common codes
NTEE_DETAILED_CATEGORIES = {
    # Religion-Related (X)
    "X20": "Christian",
    "X21": "Protestant",
    "X22": "Roman Catholic",
    "X30": "Jewish",
    "X40": "Islamic",
    "X50": "Buddhist",
    "X70": "Hindu",
    "X80": "Religious Media & Communications",
    "X90": "Interfaith Issues",
    # International (Q)
    "Q20": "Promotion of International Understanding",
    "Q30": "International Development",
    "Q33": "International Relief",
    "Q40": "International Peace & Security",
    "Q50": "International Human Rights",
    "Q70": "International Migration & Refugee Issues",
    # Human Services (P)
    "P20": "Human Service Organizations",
    "P30": "Children & Youth Services",
    "P40": "Family Services",
    "P50": "Personal Social Services",
    "P60": "Emergency Assistance",
    "P70": "Residential & Adult Care",
    "P80": "Services to Promote Independence",
    "P99": "Human Services (Other)",
    # Philanthropy (T)
    "T20": "Private Grantmaking Foundations",
    "T30": "Public Foundations",
    "T40": "Voluntarism Promotion",
    "T50": "Philanthropy, Charity & Voluntarism Promotion",
    "T70": "Federated Giving Programs",
    "T90": "Named Trusts",
    # Health (E)
    "E20": "Hospitals & Primary Medical Care",
    "E30": "Ambulatory Health Centers & Clinics",
    "E40": "Reproductive Health Care",
    "E50": "Rehabilitative Care",
    "E60": "Health Support Services",
    "E70": "Public Health",
    "E80": "Health (General & Financing)",
    # Education (B)
    "B20": "Elementary & Secondary Education",
    "B24": "Primary & Elementary Schools",
    "B25": "Secondary & High Schools",
    "B28": "Special Education",
    "B29": "Charter Schools",
    "B30": "Vocational & Technical Schools",
    "B40": "Higher Education",
    "B42": "Undergraduate Colleges",
    "B43": "Universities",
    "B50": "Graduate & Professional Schools",
    "B60": "Adult Education",
    "B70": "Libraries",
    "B80": "Student Services",
    "B82": "Scholarships & Student Financial Aid",
    "B90": "Educational Services",
    # Community Improvement (S)
    "S20": "Community & Neighborhood Development",
    "S30": "Economic Development",
    "S40": "Business & Industry",
    "S50": "Nonprofit Management",
    # Unknown/Unclassified
    "Z99": "Unknown",
}


def get_ntee_category(ntee_code: Optional[str]) -> Optional[str]:
    """
    Get human-readable category from NTEE code.

    Priority:
    1. Exact match in detailed categories (e.g., "X40" -> "Islamic")
    2. Major category match (e.g., "X99" -> "Religion-Related")
    3. None if code is invalid or missing

    Args:
        ntee_code: NTEE code (e.g., "X40", "T50", "P30")

    Returns:
        Human-readable category string or None

    Examples:
        >>> get_ntee_category("X40")
        "Islamic"
        >>> get_ntee_category("T50")
        "Philanthropy, Charity & Voluntarism Promotion"
        >>> get_ntee_category("X99")
        "Religion-Related"
        >>> get_ntee_category("Z99")
        "Unknown"
    """
    if not ntee_code:
        return None

    ntee_code = ntee_code.strip().upper()

    # Check for exact detailed match first
    if ntee_code in NTEE_DETAILED_CATEGORIES:
        return NTEE_DETAILED_CATEGORIES[ntee_code]

    # Fall back to major category (first letter)
    major_code = ntee_code[0] if ntee_code else None
    if major_code and major_code in NTEE_MAJOR_CATEGORIES:
        return NTEE_MAJOR_CATEGORIES[major_code]

    return None


def get_ntee_description(ntee_code: Optional[str]) -> Optional[str]:
    """
    Get detailed description including both major and subcategory.

    Args:
        ntee_code: NTEE code (e.g., "X40", "T50")

    Returns:
        Description like "Religion-Related: Islamic" or just "Islamic"

    Examples:
        >>> get_ntee_description("X40")
        "Religion-Related: Islamic"
        >>> get_ntee_description("T50")
        "Philanthropy, Voluntarism & Grantmaking Foundations: Philanthropy, Charity & Voluntarism Promotion"
    """
    if not ntee_code:
        return None

    ntee_code = ntee_code.strip().upper()

    # Get subcategory if available
    subcategory = NTEE_DETAILED_CATEGORIES.get(ntee_code)

    # Get major category
    major_code = ntee_code[0] if ntee_code else None
    major_category = NTEE_MAJOR_CATEGORIES.get(major_code) if major_code else None

    if subcategory and major_category:
        # Return both if they're different
        if subcategory != major_category:
            return f"{major_category}: {subcategory}"
        return subcategory
    elif subcategory:
        return subcategory
    elif major_category:
        return major_category

    return None
