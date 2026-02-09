---
name: analytics
description: Run GA4 analytics report - realtime snapshot, engagement metrics, and funnel analysis
user-invocable: true
---

# Analytics Report

Run a comprehensive GA4 analytics report for Good Measure Giving.

## Instructions

Use the GA4 MCP tools to pull data and create a summary report. Get the GA4 Property ID from the `GA4_PROPERTY_ID` environment variable or `.env` file.

### Report Sections

**1. Realtime Snapshot**
- Run `mcp__analytics-mcp__run_realtime_report` with dimensions `["eventName"]` and metrics `["eventCount"]`
- Show what's happening right now

**2. Last 7 Days Overview**
- Run `mcp__analytics-mcp__run_report` for engagement metrics:
  - dimensions: `["date"]`
  - metrics: `["activeUsers", "sessions", "averageSessionDuration", "engagedSessions"]`
  - date_ranges: `[{"start_date": "7daysAgo", "end_date": "yesterday"}]`

**3. Top Charities (by card clicks)**
- Run report with:
  - dimensions: `["customEvent:charity_name"]`
  - metrics: `["eventCount"]`
  - dimension_filter for eventName = "charity_card_click"
  - limit: 10

**4. Search Terms**
- Run report with:
  - dimensions: `["customEvent:search_term"]`
  - metrics: `["eventCount"]`
  - dimension_filter for eventName = "search"
  - limit: 10

**5. Conversion Events**
- Count of: sign_in_start, donate_click, hero_cta_click

### Output Format

Present results as a clean summary with:
- Key metrics with week-over-week context if available
- Tables for top charities and search terms
- Actionable insights (e.g., "Users searching for X but we don't have it")
- Any red flags (high bounce, low engagement)

### Goals Tracking

Highlight progress toward:
1. **Primary Goal:** Logins (sign_in_start events)
2. **Secondary Goal:** Time on site (averageSessionDuration trend)
