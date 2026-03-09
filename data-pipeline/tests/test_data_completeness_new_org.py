from src.judges.schemas.config import JudgeConfig
from unittest.mock import patch

from src.judges.data_completeness_judge import DataCompletenessJudge


def test_new_org_without_form_990_is_info_not_error():
    judge = DataCompletenessJudge(JudgeConfig())
    judge._get_source_status = lambda ein: {
        "website": {"success": True},
        "propublica": {"success": True},
        "candid": {"success": True},
        "charity_navigator": {"success": True},
    }

    with patch("src.db.client.execute_query") as mock_execute:
        mock_execute.side_effect = [
            None,
            {
                "parsed_json": None,
                "filings": None,
                "ntee_code": None,
                "no_filings": True,
                "org_name": "Albarr Inc.",
                "irs_ruling_year": "2021",
            },
        ]

        verdict = judge.validate({"ein": "85-3964369"}, {})

    assert verdict.passed is True
    assert not verdict.errors
    assert any(issue.field == "financial.new_org" for issue in verdict.issues)
