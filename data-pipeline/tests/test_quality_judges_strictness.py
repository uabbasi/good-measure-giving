from src.judges.crawl_quality_judge import CrawlQualityJudge
from src.judges.extract_quality_judge import ExtractQualityJudge
from src.judges.narrative_quality_judge import NarrativeQualityJudge
from src.judges.schemas.config import JudgeConfig
from src.judges.schemas.verdict import Severity
from src.judges.synthesize_quality_judge import SynthesizeQualityJudge
import streaming_runner


def _crawl_judge() -> CrawlQualityJudge:
    return CrawlQualityJudge(JudgeConfig(sample_rate=1.0))


def _synth_judge() -> SynthesizeQualityJudge:
    return SynthesizeQualityJudge(JudgeConfig(sample_rate=1.0))


def _narrative_judge() -> NarrativeQualityJudge:
    return NarrativeQualityJudge(JudgeConfig(sample_rate=1.0))


def _extract_judge() -> ExtractQualityJudge:
    return ExtractQualityJudge(JudgeConfig(sample_rate=1.0))


def test_crawl_quality_handles_none_source_payloads_without_crashing():
    judge = _crawl_judge()
    verdict = judge.validate(
        output={"ein": "47-0946122"},
        context={
            "source_data": {
                "propublica": None,
                "charity_navigator": None,
                "candid": None,
                "form990_grants": None,
            }
        },
    )

    assert verdict.passed is True
    assert verdict.issues == []


def test_crawl_quality_flags_missing_required_form990_source():
    judge = _crawl_judge()
    verdict = judge.validate(
        output={"ein": "47-0946122"},
        context={"source_data": {"propublica": {}, "charity_navigator": {}, "candid": {}}},
    )

    assert verdict.passed is False
    assert any(i.field == "crawl.required_sources" for i in verdict.issues)
    missing_issue = next(i for i in verdict.issues if i.field == "crawl.required_sources")
    assert "form990_grants" in (missing_issue.details or {}).get("missing_sources", [])
    assert missing_issue.severity == Severity.ERROR


def test_crawl_quality_skips_bbb_name_warning_when_ein_matches():
    judge = _crawl_judge()
    verdict = judge.validate(
        output={"ein": "80-0508709", "name": "ICNA Council for Social Justice"},
        context={
            "source_data": {
                "bbb": {"bbb_profile": {"ein": "80-0508709", "name": "Black Veterans For Social Justice"}},
                "propublica": {},
                "charity_navigator": {},
                "candid": {},
                "form990_grants": {},
            }
        },
    )

    assert not any(i.field == "bbb.name_match" for i in verdict.issues)


def test_crawl_quality_accepts_discovered_zakat_evidence_when_website_missing():
    judge = _crawl_judge()
    verdict = judge.validate(
        output={"ein": "47-1365228", "evaluation": {"wallet_tag": "ZAKAT-ELIGIBLE"}},
        context={
            "source_data": {
                "website": {},
                "discovered": {
                    "discovered_profile": {
                        "zakat": {
                            "accepts_zakat": True,
                            "accepts_zakat_evidence": "LaunchGood campaign explicitly lists Give your Zakat.",
                            "accepts_zakat_url": "https://example.org/zakat",
                            "direct_page_verified": False,
                        }
                    }
                },
                "propublica": {},
                "charity_navigator": {},
                "candid": {},
                "form990_grants": {},
            },
            "charity_data": {},
        },
    )

    assert not any(i.field == "zakat.evidence" for i in verdict.issues)


def test_crawl_quality_downgrades_adjacent_year_revenue_divergence_to_info():
    judge = _crawl_judge()
    verdict = judge.validate(
        output={"ein": "85-3547280"},
        context={
            "source_data": {
                "propublica": {"propublica_990": {"total_revenue": 181050, "tax_year": 2023}},
                "charity_navigator": {"cn_profile": {"total_revenue": 4559370, "fiscal_year": 2024}},
                "candid": {},
                "form990_grants": {},
            }
        },
    )

    issue = next(i for i in verdict.issues if i.field == "multi_source.revenue_divergence")
    assert issue.severity == Severity.INFO


def test_synthesize_quality_records_homepage_only_website_citation_as_info():
    judge = _synth_judge()
    verdict = judge.validate(
        output={
            "ein": "47-0946122",
            "charity_data": {
                "beneficiaries_served_annually": 13000,
                "source_attribution": {
                    "beneficiaries_served_annually": {
                        "source_name": "Charity Website",
                        "source_url": "https://obathelpers.org/",
                    }
                },
            },
        },
        context={},
    )

    assert verdict.passed is True
    assert any(
        i.field == "source_attribution.beneficiaries_served_annually.source_url" and i.severity == Severity.INFO
        for i in verdict.issues
    )


def test_synthesize_quality_notes_uncited_beneficiary_claim_without_failing():
    judge = _synth_judge()
    verdict = judge.validate(
        output={
            "ein": "47-0946122",
            "charity_data": {
                "beneficiaries_served_annually": 13000,
                "source_attribution": {},
            },
        },
        context={},
    )

    assert verdict.passed is True
    assert any(
        i.field == "beneficiaries_served_annually" and i.severity == Severity.INFO for i in verdict.issues
    )


def test_synthesize_quality_skips_homepage_warning_for_false_website_claim():
    judge = _synth_judge()
    verdict = judge.validate(
        output={
            "ein": "47-0946122",
            "charity_data": {
                "claims_zakat_eligible": False,
                "source_attribution": {
                    "claims_zakat_eligible": {
                        "source_name": "Charity Website",
                        "source_url": "https://example.org/",
                    }
                },
            },
        },
        context={},
    )

    assert verdict.passed is True
    assert not any(i.field == "source_attribution.claims_zakat_eligible.source_url" for i in verdict.issues)


def test_synthesize_quality_downgrades_uncorroborated_populations_served_to_info():
    judge = _synth_judge()
    verdict = judge.validate(
        output={
            "ein": "47-0946122",
            "charity_data": {
                "populations_served": ["refugees"],
                "corroboration_status": {},
            },
        },
        context={},
    )

    assert verdict.passed is True
    assert any(
        i.field == "hallucination_denylist.populations_served" and i.severity == Severity.INFO
        for i in verdict.issues
    )


def test_synthesize_quality_ignores_false_third_party_evaluated():
    judge = _synth_judge()
    verdict = judge.validate(
        output={
            "ein": "47-0946122",
            "charity_data": {
                "third_party_evaluated": False,
                "corroboration_status": {},
            },
        },
        context={},
    )

    assert verdict.passed is True
    assert not any(i.field == "hallucination_denylist.third_party_evaluated" for i in verdict.issues)


def test_extract_quality_checks_website_bounds_for_combined_mode_data():
    judge = _extract_judge()
    verdict = judge.validate(
        output={"ein": "47-0946122"},
        context={
            "source_data": {
                "website": {
                    "website_profile": {
                        "beneficiaries_served_annually": 500_000_000,
                    }
                }
            }
        },
    )

    assert any(
        i.field == "website.website_profile.beneficiaries_served_annually" and i.severity == Severity.WARNING
        for i in verdict.issues
    )


def test_streaming_cache_skip_rejects_synthesize_artifact_without_metrics_json():
    class RawRepo:
        def get_for_charity(self, _ein):
            return []

        def get_by_source(self, _ein, _source):
            return None

    class DataRepo:
        def get(self, _ein):
            return {"charity_ein": "47-0946122"}

    class EvalRepo:
        def get(self, _ein):
            return None

    artifacts_ok, reason = streaming_runner._phase_artifacts_exist(
        "47-0946122",
        "synthesize",
        RawRepo(),
        DataRepo(),
        EvalRepo(),
    )

    assert artifacts_ok is False
    assert "metrics_json" in reason


def test_streaming_cache_skip_rejects_baseline_artifact_without_narrative():
    class RawRepo:
        def get_for_charity(self, _ein):
            return []

        def get_by_source(self, _ein, _source):
            return None

    class DataRepo:
        def get(self, _ein):
            return None

    class EvalRepo:
        def get(self, _ein):
            return {"charity_ein": "47-0946122", "amal_score": 82}

    artifacts_ok, reason = streaming_runner._phase_artifacts_exist(
        "47-0946122",
        "baseline",
        RawRepo(),
        DataRepo(),
        EvalRepo(),
    )

    assert artifacts_ok is False
    assert "baseline_narrative" in reason


def test_narrative_quality_does_not_apply_zakat_jargon_rules_to_baseline():
    judge = _narrative_judge()
    verdict = judge.validate(
        output={
            "evaluation": {
                "baseline_narrative": {
                    "summary": "The charity serves asnaf categories through local distribution.",
                    "headline": "Baseline headline",
                    "all_citations": [],
                }
            }
        },
        context={},
    )

    assert not any(i.field == "baseline_narrative.jargon" for i in verdict.issues)


def test_narrative_quality_still_flags_zakat_jargon_in_zakat_narrative():
    judge = _narrative_judge()
    verdict = judge.validate(
        output={
            "evaluation": {
                "zakat_narrative": {
                    "summary": "This donor option emphasizes asnaf categories for distribution.",
                    "headline": "Zakat headline",
                    "all_citations": [],
                }
            }
        },
        context={},
    )

    assert any(i.field == "zakat_narrative.jargon" for i in verdict.issues)


def test_streaming_inline_quality_fails_closed_when_judge_crashes(monkeypatch):
    class ExplodingJudge:
        def __init__(self, _config):
            pass

        def validate(self, _output, _context):
            raise RuntimeError("boom")

    monkeypatch.setitem(streaming_runner.PHASE_QUALITY_JUDGES, "crawl", ExplodingJudge)
    passed, issues = streaming_runner.run_inline_quality_check(
        "crawl",
        "47-0946122",
        {"ein": "47-0946122"},
        {"source_data": {}},
    )

    assert passed is False
    assert issues
    assert issues[0]["severity"] == "error"
    assert issues[0]["field"] == "judge_execution"
