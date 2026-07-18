"""H11 (minimal): CN format drift becomes a hard, non-destructive failure."""

from src.collectors.charity_navigator import CharityNavigatorCollector


def _collector():
    # use_llm_extraction=False keeps parse deterministic/offline
    return CharityNavigatorCollector(use_llm_extraction=False)


def test_check_format_integrity_returns_missing_critical_markers():
    collector = _collector()
    html_ok = "<script>self.__next_f.push([1, 'data'])</script>"
    assert collector._check_format_integrity(html_ok, "95-4453134") == []
    assert collector._check_format_integrity("<html><body>redesign</body></html>", "95-4453134") == ["nextjs_push"]


def test_parse_flags_drift_and_fails_closed():
    result = _collector().parse("<html><body><h1>New CN layout</h1></body></html>", "95-4453134")
    assert result.success is False
    assert result.error.startswith("cn_format_drift")
    assert result.parsed_data["cn_profile"]["quality_flag"] == "format_drift"
    assert result.parsed_data["cn_profile"]["ein"] == "95-4453134"


def test_parse_proceeds_when_critical_markers_present():
    # Critical marker present but page otherwise junk: must NOT be classified as drift
    html = "<script>self.__next_f.push([1,'x'])</script><html><body></body></html>"
    result = _collector().parse(html, "95-4453134")
    assert result.error is None or not result.error.startswith("cn_format_drift")
