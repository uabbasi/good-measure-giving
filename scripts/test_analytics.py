"""Regression checks for the analytics collectors; no live credentials needed."""

import io
import json
import unittest
from contextlib import ExitStack, redirect_stdout
from datetime import date, timedelta
from unittest.mock import patch

from scripts import cloudflare_analytics as cf
from scripts import pmf_analysis as pmf


class AnalyticsTest(unittest.TestCase):
    def test_cloudflare_uses_seven_complete_days_and_one_day_rankings(self):
        start, end = map(date.fromisoformat, cf.get_date_range(7))
        self.assertEqual((end - start).days + 1, 7)
        self.assertEqual(end, cf.datetime.now(cf.timezone.utc).date() - timedelta(days=1))
        with patch.object(cf, "graphql_query", return_value={}) as query:
            cf.fetch_zone_top_paths("token")
            cf.fetch_zone_top_countries("token")
        for call in query.call_args_list:
            self.assertIn(f'date_geq: "{end}"', call.args[1])
            self.assertIn(f'date_leq: "{end}"', call.args[1])

    def test_rum_rankings_use_page_loads_scoped_to_production(self):
        with patch.object(cf, "graphql_query", return_value={}) as query:
            for fetch in [cf.fetch_rum_top_paths, cf.fetch_rum_top_countries, cf.fetch_rum_browsers]:
                fetch("token", "2026-09-04", "2026-09-10")
        for call in query.call_args_list:
            self.assertIn("count_DESC", call.args[1])
            self.assertIn('requestHost_in: ["goodmeasuregiving.org", "www.goodmeasuregiving.org"]', call.args[1])
            self.assertIn("bot: 0", call.args[1])

    def test_graphql_errors_are_not_empty_successes(self):
        with patch.object(cf.urllib.request, "urlopen") as request:
            request.return_value.__enter__.return_value.read.return_value = json.dumps({"errors": [{"message": "query time range exceeds limit"}], "data": None}).encode()
            with self.assertRaisesRegex(RuntimeError, "time range"):
                cf.graphql_query("token", "{}")

    def test_partial_report_marks_a_failed_source_unavailable(self):
        output = io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch.object(cf, "get_api_token", return_value="token"))
            for name in ["fetch_zone_analytics", "fetch_zone_top_paths", "fetch_zone_top_countries", "fetch_rum_pageloads", "fetch_rum_top_paths", "fetch_rum_top_countries", "fetch_rum_browsers"]:
                stack.enter_context(patch.object(cf, name, return_value=[]))
            stack.enter_context(patch.object(cf, "fetch_rum_pageloads", side_effect=RuntimeError("unavailable")))
            with redirect_stdout(output):
                cf.main()
        report = json.loads(output.getvalue())
        self.assertIsNone(report["totals"]["rum"])
        self.assertEqual(report["totals"]["zone"]["requests"], 0)
        self.assertEqual(report["errors"]["rum_daily"], "unavailable")

    def test_ga4_reports_are_production_scoped(self):
        with patch.object(pmf.urllib.request, "urlopen") as request:
            request.return_value.__enter__.return_value.read.return_value = b'{}'
            self.assertEqual(pmf.run_ga4_report("token", ["eventName"], ["eventCount"]), [])
        body = json.loads(request.call_args.args[0].data)
        self.assertEqual(body["dimensionFilter"]["filter"], {
            "fieldName": "hostName",
            "inListFilter": {"values": ["goodmeasuregiving.org", "www.goodmeasuregiving.org"]},
        })

    def test_event_totals_are_not_reported_as_a_conversion_funnel(self):
        output = io.StringIO()
        with redirect_stdout(output):
            pmf.build_report([], [], [], [], {"funnel": {
                "sign_in_start": {"users": 17, "count": 17},
                "sign_in_success": {"users": 19, "count": 19},
            }})
        self.assertNotIn("111.8%", output.getvalue())
        self.assertNotIn("Active last", output.getvalue())
        self.assertIn("not a cohort funnel", output.getvalue())


if __name__ == "__main__":
    unittest.main()
