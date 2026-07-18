"""H6 end-to-end: verified ensemble output must reach WebsiteProfile field names.

The ensemble prompt's vocabulary (e.g. "beneficiaries") differs from the
WebsiteProfile schema's vocabulary (e.g. "populations_served"). The rename is
reconciled at exactly one point: WebsiteCollector._merge_llm_data.
"""

from src.collectors.web_collector import WebsiteCollector


def _merge(regex_data, llm_data):
    # _merge_llm_data uses no instance state; call it unbound to avoid the
    # heavyweight collector __init__ (cache dirs, parsers, LLM clients).
    return WebsiteCollector._merge_llm_data(object(), regex_data, llm_data)


def test_verified_beneficiaries_lands_as_populations_served():
    """The audit's acceptance metric: populations_served must be populated."""
    merged = _merge(
        {"ein": None},
        {"beneficiaries": ["refugees", "children"], "contact_email": "info@x.org"},
    )
    assert merged["populations_served"] == ["refugees", "children"]


def test_mission_statement_lands_as_mission():
    merged = _merge(
        {"mission": "regex-scraped mission"},
        {"mission_statement": "Verified LLM mission."},
    )
    # Prefer the LLM value, consistent with the other rich fields
    assert merged["mission"] == "Verified LLM mission."


def test_schema_named_key_wins_over_prompt_alias():
    merged = _merge(
        {},
        {"beneficiaries": ["prompt-alias"], "populations_served": ["schema-name"]},
    )
    assert merged["populations_served"] == ["schema-name"]


def test_schema_homed_ensemble_keys_survive_merge():
    """Same-name prompt keys with a WebsiteProfile home must not be dropped."""
    llm_data = {
        "beneficiaries_served": 50000,
        "donation_page_url": "https://x.org/give",
        "ein_mentioned": "12-3456789",
        "volunteer_page_url": "https://x.org/volunteer",
        "annual_report_url": "https://x.org/annual.pdf",
        "transparency_info": "Audited annually by CPA firm",
    }
    merged = _merge({}, llm_data)
    for key, value in llm_data.items():
        assert merged.get(key) == value, key
