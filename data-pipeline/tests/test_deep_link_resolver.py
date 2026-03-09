from src.llm.schemas.rich_v2 import SourceType
from src.parsers.charity_metrics_aggregator import CharityMetricsAggregator
from src.services.citation_service import CitationRegistry, CitationService, CitationSource
from src.utils.deep_link_resolver import choose_website_evidence_url, upgrade_source_url


def test_upgrade_source_url_prefers_deep_impact_links_for_beneficiary_claims():
    context = {
        "url": "https://example.org",
        "donate_url": "https://example.org/donate",
        "llm_extractions": [
            {"url": "https://example.org/impact-report-2025", "llm_data": {"outcomes_summary": {"total_beneficiaries": 12000}}}
        ],
        "outcomes_data": [
            {"source_url": "https://example.org/s/annual-impact-report.pdf"},
        ],
    }

    resolved = upgrade_source_url(
        "https://example.org",
        source_name="Charity Website",
        claim="Beneficiaries served annually",
        source_path="website_profile.beneficiaries_served",
        context=context,
    )

    assert resolved in {"https://example.org/impact-report-2025", "https://example.org/s/annual-impact-report.pdf"}


def test_upgrade_source_url_adds_charity_navigator_section_anchors():
    financial = upgrade_source_url(
        "https://www.charitynavigator.org/ein/470946122",
        source_name="Charity Navigator",
        claim="Program expense ratio and working capital",
    )
    ratings = upgrade_source_url(
        "https://www.charitynavigator.org/ein/470946122",
        source_name="Charity Navigator",
        claim="Overall score and rating",
    )

    assert financial == "https://www.charitynavigator.org/ein/470946122#financials"
    assert ratings == "https://www.charitynavigator.org/ein/470946122#ratings"


def test_upgrade_source_url_adds_ratings_anchor_for_governance_claims():
    governance = upgrade_source_url(
        "https://www.charitynavigator.org/ein/470946122",
        source_name="Charity Navigator",
        claim="independent board with 100% independence",
    )
    assert governance == "https://www.charitynavigator.org/ein/470946122#ratings"


def test_upgrade_source_url_maps_guidestar_homepage_to_candid_profile():
    context = [
        {"source_name": "Candid", "source_url": "https://www.guidestar.org/", "claim": "seal and transparency"},
        {"source_name": "Candid Profile", "source_url": "https://app.candid.org/profile/7699007", "claim": "profile"},
    ]
    upgraded = upgrade_source_url(
        "https://www.guidestar.org/",
        source_name="Candid",
        claim="Platinum Seal of Transparency",
        context=context,
    )
    assert upgraded == "https://app.candid.org/profile/7699007"


def test_upgrade_source_url_maps_candid_claim_from_wrong_domain_to_candid_profile():
    context = [
        {"source_name": "Candid Profile", "source_url": "https://app.candid.org/profile/7699007", "claim": "profile"},
        {
            "source_name": "Charity Navigator",
            "source_url": "https://www.charitynavigator.org/ein/470946122#ratings",
            "claim": "rating",
        },
    ]
    upgraded = upgrade_source_url(
        "https://www.charitynavigator.org/ein/470946122",
        source_name="Candid",
        claim="Platinum Seal of Transparency",
        context=context,
    )
    assert upgraded == "https://app.candid.org/profile/7699007"


def test_choose_website_evidence_url_uses_nested_page_urls():
    website_profile = {
        "url": "https://charity.org",
        "page_extractions": [
            {"url": "https://charity.org/programs", "extracted_fields": ["llm_data", "programs"]},
            {"url": "https://charity.org/impact", "extracted_fields": ["llm_data", "impact_metrics"]},
        ],
    }
    resolved = choose_website_evidence_url(
        website_profile,
        "https://charity.org",
        source_name="Charity Website",
        claim="Beneficiaries served annually",
    )

    assert resolved == "https://charity.org/impact"


def test_aggregator_sets_beneficiary_source_to_deep_link():
    website_profile = {
        "url": "https://obathelpers.org",
        "beneficiaries_served": 13000,
        "donate_url": "https://obathelpers.org/donate",
        "llm_extractions": [
            {"url": "https://obathelpers.org/impact-report", "llm_data": {"outcomes_summary": {"total_beneficiaries": 13000}}}
        ],
        "outcomes_data": [
            {"source_url": "https://obathelpers.org/s/OBAT-Helpers-Audit-Report-2022-1.pdf"},
        ],
    }

    metrics = CharityMetricsAggregator.aggregate(
        charity_id=0,
        ein="47-0946122",
        cn_profile={"name": "Obat Helpers"},
        website_profile=website_profile,
    )

    assert metrics.beneficiaries_served_annually == 13000
    source = metrics.source_attribution.get("beneficiaries_served_annually", {})
    assert source.get("source_url")
    assert source.get("source_url") != "https://obathelpers.org"


def test_aggregator_uses_full_website_context_for_page_extraction_deep_links():
    website_profile = {
        "url": "https://obathelpers.org",
        "beneficiaries_served": 13000,
    }
    website_context = {
        "website_profile": website_profile,
        "page_extractions": [
            {"url": "https://obathelpers.org/impact/annual-results", "extracted_fields": ["llm_data", "impact_metrics"]}
        ],
    }

    metrics = CharityMetricsAggregator.aggregate(
        charity_id=0,
        ein="47-0946122",
        cn_profile={"name": "Obat Helpers"},
        website_profile=website_profile,
        website_context=website_context,
    )

    source = metrics.source_attribution.get("beneficiaries_served_annually", {})
    assert source.get("source_url") == "https://obathelpers.org/impact/annual-results"


def test_citation_registry_canonicalization_upgrades_homepage_sources():
    registry = CitationRegistry()
    registry.add_source(
        CitationSource(
            source_name="Charity Website",
            source_url="https://example.org",
            source_type=SourceType.WEBSITE,
            claim_topic="beneficiaries served annually",
        )
    )
    registry.add_source(
        CitationSource(
            source_name="Annual Report",
            source_url="https://example.org/s/annual-report.pdf",
            source_type=SourceType.WEBSITE,
            claim_topic="outcomes and impact metrics",
        )
    )

    CitationService._canonicalize_registry_urls(registry)
    urls = [s.source_url for s in registry.sources]
    assert "https://example.org/s/annual-report.pdf" in urls
    assert all(url != "https://example.org" for url in urls if url)
