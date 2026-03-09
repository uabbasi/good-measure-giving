from src.collectors.base import FetchResult
from src.collectors.form990_grants import Form990GrantsCollector
from src.collectors.orchestrator import DataCollectionOrchestrator


def test_parse_no_xml_sentinel_returns_empty_profile():
    collector = Form990GrantsCollector()

    result = collector.parse(collector.NO_XML_SENTINEL, "85-3964369")

    assert result.success is True
    profile = result.parsed_data["grants_profile"]
    assert profile["ein"] == "85-3964369"
    assert profile["domestic_grants"] == []
    assert profile["foreign_grants"] == []
    assert profile["total_grants"] == 0


def test_fetch_treats_no_xml_filings_as_success(monkeypatch):
    collector = Form990GrantsCollector()

    monkeypatch.setattr(collector, "_get_filing_object_ids", lambda _ein, max_filings=3: [])

    result = collector.fetch("85-3964369")

    assert result.success is True
    assert result.raw_data == collector.NO_XML_SENTINEL
    assert result.error is None


def test_collect_treats_no_xml_filings_as_empty_success(monkeypatch):
    collector = Form990GrantsCollector()

    def fake_fetch(_ein: str):
        return FetchResult(
            success=False,
            raw_data=None,
            content_type="xml",
            error="No XML filings found for EIN 85-3964369",
        )

    monkeypatch.setattr(collector, "fetch", fake_fetch)

    success, data, error = collector.collect("85-3964369")

    assert success is True
    assert error is None
    assert data["grants_profile"]["ein"] == "85-3964369"
    assert data["grants_profile"]["total_grants"] == 0
    assert data["raw_xml_object_id"] is None


def test_orchestrator_accepts_form990_no_xml_sentinel_as_substantive_content():
    orchestrator = DataCollectionOrchestrator()

    assert orchestrator._has_content_substance(Form990GrantsCollector.NO_XML_SENTINEL, "form990_grants") is True
