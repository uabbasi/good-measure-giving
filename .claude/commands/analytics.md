---
name: analytics
description: Unified analytics report - Cloudflare + Firestore + GA4
user-invocable: true
---

# Unified Analytics Report

Run a comprehensive analytics report combining three data sources:
1. **Cloudflare** — server-side traffic (zone) + real browser visits (RUM beacon)
2. **Firestore** — user signups, feature adoption, giving activity
3. **GA4** — event-level engagement tracking (note: blocked by ~80%+ of visitors with ad blockers)

## Step 1: Cloudflare Data (primary traffic source)

Run the Cloudflare analytics script and parse the JSON output:

```bash
source ~/.secrets/api_keys.sh && uv run python scripts/cloudflare_analytics.py 2>/tmp/cf_analytics.err
```

Parse the JSON stdout. If the script fails, show the stderr from `/tmp/cf_analytics.err` and continue.

Key fields:
- `daily[]` — merged zone + RUM daily metrics (requests, page_views, unique_ips, pageloads, visits)
- `totals.zone` — HTTP-level totals (includes bots/crawlers)
- `totals.rum` — Real browser visits (beacon-based, most accurate traffic count)
- `top_paths.rum[]` — Top pages by visit count
- `top_countries.rum[]` — Geographic breakdown
- `browsers[]` — Browser/device breakdown

**Important context for interpreting Cloudflare data:**
- `zone.unique_ips` includes bots, crawlers, and scanners — NOT real visitors
- `rum.visits` is the true human visitor count (beacon-based, like GA4 but harder to block)
- Compare `rum.visits` vs GA4 sessions to estimate ad blocker rate

## Step 2: Firestore Data

Run the Firestore analytics script and parse the JSON output:

```bash
uv run python scripts/firestore_analytics.py 2>/tmp/firestore_analytics.err
```

Parse the JSON stdout. If the script fails, show the stderr from `/tmp/firestore_analytics.err` and continue.

## Step 3: GA4 Data

Get the GA4 Property ID from the `GA4_PROPERTY_ID` environment variable or `.env` file.

### 3a. Realtime Snapshot
- Run `mcp__analytics-mcp__run_realtime_report` with dimensions `["eventName"]` and metrics `["eventCount"]`

### 3b. Last 7 Days Engagement
- Run `mcp__analytics-mcp__run_report` with:
  - dimensions: `["date"]`
  - metrics: `["activeUsers", "sessions", "averageSessionDuration", "engagedSessions"]`
  - date_ranges: `[{"start_date": "7daysAgo", "end_date": "yesterday"}]`

### 3c. Top Charities (by card clicks)
- dimensions: `["customEvent:charity_name"]`
- metrics: `["eventCount"]`
- dimension_filter for eventName = "charity_card_click"
- limit: 10

### 3d. Search Terms
- dimensions: `["customEvent:search_term"]`
- metrics: `["eventCount"]`
- dimension_filter for eventName = "search"
- limit: 10

### 3e. Conversion Events
- Count of: sign_in_start, sign_in_success, donate_click, hero_cta_click

### 3f. Auth Funnel (signups vs logins)
- dimensions: `["customEvent:auth_type"]`
- metrics: `["eventCount"]`
- dimension_filter for eventName = "sign_in_success"

## Step 4: Unified Report

Combine all three data sources into a single report with these sections:

### Section 1: Traffic Overview (Cloudflare — primary)

Show a daily cross-reference table combining zone + RUM data:

| Date | HTTP Reqs | Zone Page Views | Zone Unique IPs | RUM Pageloads | RUM Visits | GA4 Sessions |
|------|-----------|-----------------|-----------------|---------------|------------|--------------|

Below the table, show:
- **Total real visitors** (RUM visits) vs **total unique IPs** (zone) — the gap = bot traffic
- **Ad blocker rate estimate**: `1 - (GA4 sessions / RUM visits)`
- Top pages by RUM visits
- Geographic breakdown (RUM countries)
- Browser/device split

### Section 2: User Base & Signups (Firestore)
- Total registered users
- Signup timeline (table by day)
- Growth trend

### Section 3: Feature Adoption (Firestore)
Show a table with feature name, users using it, and adoption rate (% of total users):

| Feature | Users | Adoption |
|---------|-------|----------|
| Bookmarks | X | X% |
| Giving History (donations tracked) | X | X% |
| Zakat Target Amount | X | X% |
| Giving Buckets | X | X% |
| Bucket Assignments | X | X% |
| Geographic Preferences | X | X% |
| Fiqh Preferences | X | X% |
| Zakat Anniversary | X | X% |

### Section 4: Engagement Deep Dive (GA4)
- Realtime activity
- Daily GA4 metrics table (users, sessions, avg duration, engaged sessions)
- Note: GA4 captures ~15-20% of real traffic due to ad blockers; use for event-level insights, not traffic counts

### Section 5: Content Performance (GA4 + Cloudflare + Firestore)
- Top visited pages (Cloudflare RUM) alongside top clicked charities (GA4) alongside top bookmarked (Firestore)
- Cross-reference: are the most visited pages also the most bookmarked?
- Search terms analysis (GA4)

### Section 6: Conversion Funnel (Cloudflare → GA4 → Firestore)
Build a funnel from all three sources:
1. Real site visitors (Cloudflare RUM visits)
2. GA4-tracked visitors (GA4 sessions) — shows ad blocker drop-off
3. Sign-in starts (GA4 sign_in_start)
4. Sign-in completions (GA4 sign_in_success)
5. Registered users (Firestore user count)
6. Feature users (Firestore: users with any feature activity)

Show drop-off rates between each step.

### Section 7: Giving Activity (Firestore)
- Total donations tracked, total amount
- Breakdown by category (zakat/sadaqah/other)
- Top charities by donation amount

### Section 8: Data Quality / Reported Issues (Firestore)
- Count of reported issues by type
- If zero, note that the feature exists but hasn't been used yet

### Section 9: Insights & Recommendations
Synthesize actionable insights from all three data sources:
- What's the real traffic level? (Cloudflare RUM)
- How much traffic does GA4 miss? (ad blocker rate)
- Which features need better onboarding? (low adoption rates)
- Are popular browsed charities being bookmarked/donated to?
- What's the conversion rate from visitor to registered user to active user?
- Any gaps between search terms and available charities?
- Geographic/device insights for targeting

## Output Format

Present as a clean markdown report with:
- Clear section headers
- Tables for structured data
- Key metrics highlighted
- Actionable recommendations at the end

### Goals Tracking

Highlight progress toward:
1. **Primary Goal:** User signups & logins
2. **Secondary Goal:** Feature adoption (bookmarks, giving plans)
3. **Tertiary Goal:** Time on site / engagement depth
