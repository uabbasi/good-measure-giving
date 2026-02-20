---
name: analytics
description: Unified analytics report - Firestore user/feature data + GA4 traffic/engagement
user-invocable: true
---

# Unified Analytics Report

Run a comprehensive analytics report combining Firestore user data with GA4 traffic data.

## Step 1: Firestore Data

Run the Firestore analytics script and parse the JSON output:

```bash
uv run python scripts/firestore_analytics.py 2>/tmp/firestore_analytics.err
```

Parse the JSON stdout. If the script fails, show the stderr from `/tmp/firestore_analytics.err` and continue with GA4-only.

## Step 2: GA4 Data

Get the GA4 Property ID from the `GA4_PROPERTY_ID` environment variable or `.env` file.

### 2a. Realtime Snapshot
- Run `mcp__analytics-mcp__run_realtime_report` with dimensions `["eventName"]` and metrics `["eventCount"]`

### 2b. Last 7 Days Engagement
- Run `mcp__analytics-mcp__run_report` with:
  - dimensions: `["date"]`
  - metrics: `["activeUsers", "sessions", "averageSessionDuration", "engagedSessions"]`
  - date_ranges: `[{"start_date": "7daysAgo", "end_date": "yesterday"}]`

### 2c. Top Charities (by card clicks)
- dimensions: `["customEvent:charity_name"]`
- metrics: `["eventCount"]`
- dimension_filter for eventName = "charity_card_click"
- limit: 10

### 2d. Search Terms
- dimensions: `["customEvent:search_term"]`
- metrics: `["eventCount"]`
- dimension_filter for eventName = "search"
- limit: 10

### 2e. Conversion Events
- Count of: sign_in_start, sign_in_success, donate_click, hero_cta_click

### 2f. Auth Funnel (signups vs logins)
- dimensions: `["customEvent:auth_type"]`
- metrics: `["eventCount"]`
- dimension_filter for eventName = "sign_in_success"

## Step 3: Unified Report

Combine both data sources into a single report with these sections:

### Section 1: User Base & Signups (Firestore)
- Total registered users
- Signup timeline (table by day)
- Growth trend

### Section 2: Feature Adoption (Firestore)
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

### Section 3: Traffic & Engagement (GA4)
- Realtime activity
- Daily metrics table (users, sessions, avg duration, engaged sessions)
- Week-over-week trends if data supports it

### Section 4: Content Performance (GA4 + Firestore)
- Top clicked charities (GA4) alongside top bookmarked charities (Firestore)
- Cross-reference: are the most clicked charities also the most bookmarked?
- Search terms analysis

### Section 5: Conversion Funnel (GA4 -> Firestore)
Build a funnel from GA4 events to Firestore feature adoption:
1. Site visits (GA4 sessions)
2. Sign-in starts (GA4 sign_in_start)
3. Sign-in completions (GA4 sign_in_success)
4. Registered users (Firestore user count)
5. Feature users (Firestore: users with any feature activity)

Show drop-off rates between each step.

### Section 6: Giving Activity (Firestore)
- Total donations tracked, total amount
- Breakdown by category (zakat/sadaqah/other)
- Top charities by donation amount

### Section 7: Data Quality / Reported Issues (Firestore)
- Count of reported issues by type
- If zero, note that the feature exists but hasn't been used yet

### Section 8: Insights & Recommendations
Synthesize actionable insights from both data sources:
- Which features need better onboarding? (low adoption rates)
- Are popular browsed charities being bookmarked/donated to?
- What's the conversion rate from visitor to registered user to active user?
- Any gaps between search terms and available charities?

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
