---
name: analytics
description: Unified Good Measure Giving analytics from Cloudflare, Firestore, GA4, and PMF engagement tiers. Use for site traffic, user behavior, conversions, feature adoption, giving activity, or a full analytics report.
---

# Analytics for Codex

Read the maintained [.claude/skills/analytics/SKILL.md](../../../.claude/skills/analytics/SKILL.md) from the repository root before analyzing data. Resolve its relative references from the original Claude skill directory. Run its scripts from the repository root.

For `$analytics` without a narrower question, or a request for the full report, also read [.claude/commands/analytics.md](../../../.claude/commands/analytics.md) and follow that report workflow, including PMF analysis. A narrower question only needs the relevant sources.

Claude's files remain the maintained source. Apply these Codex tool adaptations:

- The project `.codex/config.toml` configures the existing `analytics-mcp` server with the same GA4 property and credential file as Claude. It exposes `get_ga4_data`, not the `run_report` tool named in the source. Discover the server's available tools before calling them.
- For historical reports, use `get_ga4_data`: keep `dimensions`, `metrics`, `dimension_filter`, and `limit`; translate the date range to `date_range_start` and `date_range_end`. The server supplies the property ID and sorting, so omit `property_id` and `order_bys`. Use `search_schema` to check custom dimensions if a query fails.
- The installed server has no realtime tool. Use the existing GA4 authentication helper and the read-only REST endpoint from the repository root:

```bash
uv run python - <<'PY'
import json
from urllib.request import Request, urlopen
from scripts.pmf_analysis import GA4_API_BASE, get_ga4_token

token = get_ga4_token()
if not token:
    raise SystemExit("GA4 authentication failed")
request = Request(
    f"{GA4_API_BASE}:runRealtimeReport",
    data=json.dumps({"dimensions": [{"name": "eventName"}], "metrics": [{"name": "eventCount"}]}).encode(),
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
)
with urlopen(request, timeout=30) as response:
    print(json.dumps(json.load(response), indent=2))
PY
```

Keep unavailable sources marked unavailable and continue with the others as the report command specifies. Treat the source's historical ad-blocker percentages as estimates, not current measurements. Use matching date ranges for comparisons; lifetime Firestore totals are not a cohort funnel with this week's traffic.

For production historical GA4 reports, restrict `hostName` to `goodmeasuregiving.org` and `www.goodmeasuregiving.org`. Combine this with any event filter using AND; do not replace the event filter. Realtime reports are property-wide unless the API supports the requested scope, so label them accordingly.

Use Cloudflare's `pageloads` for RUM rankings. Its `visits` field is not unique people or GA4 sessions; even `bot=0` can include unclassified automation. Read the collector's `errors` and `notes`, and keep failed sections unavailable rather than converting them to zero.

The tracking repair and required GA4 admin settings are documented in [website/DEPLOYMENT.md](../../../website/DEPLOYMENT.md). Until the custom dimensions are registered, report charity/auth/search breakdowns as unavailable. Historical `sign_in_success` events included restored Firebase sessions, and historical page views could be duplicated; do not calculate conversion rates by dividing independent event-user totals.
