"""Deterministic causeArea derivation from the pipeline's primary_category.

Maps the 16 category keys in config/charity_categories.yaml onto the site's
committed causeArea display vocabulary (see website/data/charities.json).
Labels are chosen for display consistency with that vocabulary where a
dominant form exists; where no dominant/clean form exists (ENVIRONMENT_CLIMATE,
WOMENS_SERVICES, SOCIAL_SERVICES) the label is an editorial canonical choice,
overridable per-EIN via config/curation_overrides.yaml.
Hand-curated exceptions live in config/curation_overrides.yaml (contract #1);
this module is the generated-value side of that overlay (contract #3).
"""

DEFAULT_CAUSE_AREA = "GENERAL"

# Literal 16-entry map: charity_categories.yaml category -> display label.
# Labels follow the dominant committed causeArea where one exists; see the
# module docstring for the editorial-choice categories.
CATEGORY_TO_CAUSE_AREA: dict[str, str] = {
    "HUMANITARIAN": "HUMANITARIAN",
    "MEDICAL_HEALTH": "GLOBAL HEALTH",
    "BASIC_NEEDS": "HUMANITARIAN",
    "CIVIL_RIGHTS_LEGAL": "ADVOCACY",
    "RESEARCH_POLICY": "RESEARCH & EDUCATION",
    "ADVOCACY_CIVIC": "ADVOCACY",
    "ENVIRONMENT_CLIMATE": "ENVIRONMENTAL ADVOCACY",
    "WOMENS_SERVICES": "WOMEN'S SERVICES",
    "EDUCATION_INTERNATIONAL": "EDUCATION_GLOBAL",
    "EDUCATION_HIGHER_RELIGIOUS": "EDUCATION",
    "EDUCATION_K12_RELIGIOUS": "EDUCATION",
    "RELIGIOUS_OUTREACH": "RELIGIOUS_CULTURAL",
    "RELIGIOUS_CONGREGATION": "RELIGIOUS_CULTURAL",
    "PHILANTHROPY_GRANTMAKING": "HUMANITARIAN",
    "MEDIA_JOURNALISM": "ADVOCACY & MEDIA",
    "SOCIAL_SERVICES": "SOCIAL SERVICES",
}

_EXTREME_POVERTY = "EXTREME_POVERTY"


def derive_cause_area(primary_category: str | None, detected_cause_area: str | None) -> str:
    """Derive the exported causeArea label from the primary category.

    detected_cause_area refines ONLY the HUMANITARIAN -> EXTREME_POVERTY split;
    every other category maps straight through. Unknown/None -> "GENERAL".
    """
    if not primary_category:
        return DEFAULT_CAUSE_AREA
    key = primary_category.strip().upper()
    label = CATEGORY_TO_CAUSE_AREA.get(key)
    if label is None:
        return DEFAULT_CAUSE_AREA
    detected = detected_cause_area.strip().upper() if detected_cause_area else None
    if key == "HUMANITARIAN" and detected == _EXTREME_POVERTY:
        return _EXTREME_POVERTY
    return label
