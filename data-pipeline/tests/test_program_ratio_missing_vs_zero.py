"""A program-expense ratio we do not have must not ship as a real 0%.

Two independent defects put "0%" on the browse page for charities that never
reported a program figure:

  * the aggregator built a ratio from a zero numerator, and accepted Charity
    Navigator's own 0.0000 when it held no components of its own;
  * the exporter serialized DoltDB's decimal(5,4) with `default=str`, so every
    populated ratio shipped as a JSON string against a `number | null` contract.
"""

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import export
from src.parsers.charity_metrics_aggregator import CharityMetricsAggregator

EIN = "12-3456789"


def _aggregate(grants=None, cn=None):
    return CharityMetricsAggregator.aggregate(
        charity_id=1,
        ein=EIN,
        grants_profile=grants,
        cn_profile=cn,
    )


def _irs(program, total, revenue=1_000_000):
    return {
        "tax_year": 2024,
        "total_revenue": revenue,
        "total_expenses": total,
        "program_expenses": program,
        "admin_expenses": None,
        "fundraising_expenses": None,
    }


class TestZeroNumerator:
    def test_zero_program_expenses_against_real_total_is_not_a_ratio(self):
        """47-1666091: $0 of $147,133. An absent figure, not 0% on programs."""
        m = _aggregate(grants=_irs(program=0, total=147_133))
        assert m.program_expense_ratio is None

    def test_a_real_split_still_produces_a_ratio(self):
        m = _aggregate(grants=_irs(program=800_000, total=1_000_000))
        assert m.program_expense_ratio == 0.8

    def test_null_program_expenses_is_still_not_a_ratio(self):
        """90-0327815 filed no program figure at all."""
        m = _aggregate(grants=_irs(program=None, total=69_600))
        assert m.program_expense_ratio is None


class TestCharityNavigatorFallback:
    def test_a_zero_cn_ratio_is_an_absent_statement(self):
        """The path that gave 90-0327815 its 0.0000 while holding no components."""
        m = _aggregate(cn={"program_expense_ratio": 0.0})
        assert m.program_expense_ratio is None

    def test_a_real_cn_ratio_still_fills_the_gap(self):
        """Al-Furqaan regressed 0.85 -> None -> impact 8/50; keep that path open."""
        m = _aggregate(cn={"program_expense_ratio": 0.85})
        assert m.program_expense_ratio == 0.85


class TestJsonDefault:
    def test_decimal_serializes_as_a_number_not_a_string(self):
        out = json.dumps({"r": Decimal("0.8696")}, default=export._json_default)
        assert out == '{"r": 0.8696}'
        assert isinstance(json.loads(out)["r"], float)

    def test_a_whole_ratio_still_round_trips(self):
        loaded = json.loads(json.dumps({"r": Decimal("1.0000")}, default=export._json_default))
        assert loaded["r"] == 1.0

    def test_non_decimal_values_still_fall_back_to_str(self):
        loaded = json.loads(json.dumps({"d": date(2026, 8, 24)}, default=export._json_default))
        assert loaded["d"] == "2026-08-24"
