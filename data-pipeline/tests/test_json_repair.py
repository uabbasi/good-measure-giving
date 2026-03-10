"""Tests for JSON extraction and repair from LLM responses."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.gemini_search import extract_json_from_response, _repair_truncated_json


class TestExtractJsonFromResponse:
    def test_plain_json(self):
        text = '{"key": "value", "num": 42}'
        result = extract_json_from_response(text)
        assert json.loads(result) == {"key": "value", "num": 42}

    def test_markdown_wrapped(self):
        text = '```json\n{"key": "value"}\n```'
        result = extract_json_from_response(text)
        assert json.loads(result) == {"key": "value"}

    def test_markdown_with_preamble(self):
        text = 'Here is the result:\n```json\n{"key": "value"}\n```\nDone.'
        result = extract_json_from_response(text)
        assert json.loads(result) == {"key": "value"}

    def test_json_with_trailing_text(self):
        text = '{"key": "value"} some trailing text'
        result = extract_json_from_response(text)
        assert json.loads(result) == {"key": "value"}

    def test_no_json(self):
        assert extract_json_from_response("no json here") is None

    def test_empty_string(self):
        assert extract_json_from_response("") is None


class TestRepairTruncatedJson:
    """Test repair of JSON truncated at various points."""

    def test_truncated_mid_string_value(self):
        """Truncation inside a string value — should keep complete items."""
        text = '{"has_outcomes": true, "metrics": [{"metric": "scholarships", "value": "2000+", "year": "2023"}, {"metric": "students supp'
        result = _repair_truncated_json(text)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["has_outcomes"] is True
        assert len(parsed["metrics"]) == 1
        assert parsed["metrics"][0]["metric"] == "scholarships"

    def test_truncated_mid_second_array_item(self):
        """Truncation inside second array element — first element preserved."""
        text = '{"has_awards": true, "awards": [{"name": "4-star", "source": "CN"}, {"name": "Plat'
        result = _repair_truncated_json(text)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["has_awards"] is True
        assert len(parsed["awards"]) == 1
        assert parsed["awards"][0]["name"] == "4-star"

    def test_truncated_mid_url(self):
        """Truncation inside a URL string."""
        text = '{"evaluated": true, "evaluators": [{"name": "CN", "url": "https://charitynavigator.org/ein/123'
        result = _repair_truncated_json(text)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["evaluated"] is True
        # May or may not preserve the evaluator depending on cut point
        assert "evaluators" in parsed

    def test_truncated_after_first_field(self):
        """Truncation after only the boolean — still useful."""
        text = '{"third_party_evaluated": true, "evaluators": [{"name'
        result = _repair_truncated_json(text)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["third_party_evaluated"] is True

    def test_truncated_after_complete_array(self):
        """Truncation after a complete array, mid next field."""
        text = '{"has_awards": true, "awards": [{"name": "4-star", "source": "CN"}], "confid'
        result = _repair_truncated_json(text)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["has_awards"] is True
        assert len(parsed["awards"]) == 1

    def test_truncated_after_complete_object(self):
        """Truncation just after a closing brace in an array."""
        text = '{"has_outcomes": true, "metrics": [{"metric": "lives", "value": "500"}'
        result = _repair_truncated_json(text)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["metrics"][0]["value"] == "500"

    def test_deeply_nested_truncation(self):
        """Truncation deep in nested structure — last element without comma is ambiguous."""
        text = '{"a": {"b": {"c": [1, 2, 3'
        result = _repair_truncated_json(text)
        assert result is not None
        parsed = json.loads(result)
        # 3 has no comma/bracket after it, so repair truncates to last safe comma
        assert parsed["a"]["b"]["c"] == [1, 2]

    def test_empty_string(self):
        assert _repair_truncated_json("") is None

    def test_not_json(self):
        assert _repair_truncated_json("hello world") is None

    def test_already_valid(self):
        """Already-valid JSON should pass through."""
        text = '{"key": "value"}'
        result = _repair_truncated_json(text)
        # May return None since it's not actually truncated (has matching braces)
        # but extract_json_from_response handles this case before calling repair
        # Either returning the valid JSON or None is acceptable
        if result is not None:
            assert json.loads(result) == {"key": "value"}

    def test_escaped_quotes_in_string(self):
        """Strings with escaped quotes don't confuse the parser."""
        text = '{"text": "he said \\"hello\\"", "more": "trun'
        result = _repair_truncated_json(text)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["text"] == 'he said "hello"'

    def test_preserves_maximum_data(self):
        """Repair should keep as much complete data as possible."""
        text = '{"a": 1, "b": 2, "c": 3, "d": "trunc'
        result = _repair_truncated_json(text)
        assert result is not None
        parsed = json.loads(result)
        assert parsed == {"a": 1, "b": 2, "c": 3}
