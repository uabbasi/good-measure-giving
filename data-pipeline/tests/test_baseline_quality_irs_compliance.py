"""Tests for the IRS compliance checks (B-J-013/014) in BaselineQualityJudge.

B-J-013 ERROR   : BMF exempt-organization status code present and not '01'.
B-J-014 WARNING : revocation-reinstatement signature — ruling year >= 2011,
                  8+ years after founding, with a 3+ year filing gap
                  (the Al-Furqaan pattern: founded 2003, ruling 2021, last
                  filing FY2020).
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.judges.baseline_quality_judge import BaselineQualityJudge
from src.judges.schemas.config import JudgeConfig
from src.judges.schemas.verdict import Severity

_THIS_YEAR = date.today().year


def _run(metrics: dict):
    judge = BaselineQualityJudge(JudgeConfig())
    return judge._check_irs_compliance("00-0000000", {"charity_data": {"metrics_json": metrics}})


class TestExemptStatus:
    def test_status_01_passes(self):
        assert _run({"irs_exempt_status_code": "01"}) == []

    def test_status_1_unpadded_passes(self):
        assert _run({"irs_exempt_status_code": "1"}) == []

    def test_non_exempt_status_is_error(self):
        issues = _run({"irs_exempt_status_code": "22"})
        assert len(issues) == 1
        assert issues[0].severity == Severity.ERROR
        assert issues[0].issue_key == "irs_exempt_status_not_current"

    def test_missing_status_is_noop(self):
        assert _run({}) == []


class TestReinstatementSignature:
    def _al_furqaan(self, **overrides):
        m = {
            "founded_year": 2003,
            "irs_ruling_year": 2021,
            "financial_data_tax_year": _THIS_YEAR - 6,  # FY2020-in-2026 shape
        }
        m.update(overrides)
        return m

    def test_al_furqaan_pattern_warns(self):
        issues = _run(self._al_furqaan())
        assert len(issues) == 1
        assert issues[0].severity == Severity.WARNING
        assert issues[0].issue_key == "irs_reinstatement_signature"
        assert "2021" in issues[0].message

    def test_fresh_filings_no_warning(self):
        # Same ruling gap but current filings — no signature.
        assert _run(self._al_furqaan(financial_data_tax_year=_THIS_YEAR - 2)) == []

    def test_pre_autorevocation_era_ruling_no_warning(self):
        assert _run(self._al_furqaan(irs_ruling_year=2005, founded_year=1990)) == []

    def test_small_ruling_gap_no_warning(self):
        # Org founded shortly before ruling — normal 501c3 application lag.
        assert _run(self._al_furqaan(founded_year=2019)) == []

    def test_missing_founded_year_is_noop(self):
        assert _run({"irs_ruling_year": 2021, "financial_data_tax_year": _THIS_YEAR - 6}) == []


class TestCombined:
    def test_bad_status_and_signature_both_reported(self):
        issues = _run(
            {
                "irs_exempt_status_code": "22",
                "founded_year": 2003,
                "irs_ruling_year": 2021,
                "financial_data_tax_year": _THIS_YEAR - 6,
            }
        )
        assert len(issues) == 2
        assert {i.issue_key for i in issues} == {"irs_exempt_status_not_current", "irs_reinstatement_signature"}
