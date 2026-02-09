---
name: analytics
description: GA4 analytics reporting and funnel analysis. Pull realtime data, analyze user journeys, and track key metrics (logins, engagement). Use when checking site performance or understanding user behavior.
---

# GA4 Analytics for Good Measure Giving

Analyze user behavior, track conversions, and understand engagement patterns using Google Analytics 4 data.

---

## When This Skill Activates

- Checking site traffic and engagement
- Analyzing user funnels (browse → view → convert)
- Reviewing search behavior and popular charities
- Tracking login/signup conversions
- Understanding time on site and engagement metrics

---

## Project Context

**GA4 Property ID:** Set via `GA4_PROPERTY_ID` environment variable or configure in `.env`

**Custom Events Tracked:**

| Event | Parameters | Purpose |
|-------|------------|---------|
| `page_view` | page_path, page_title, flow_* | Navigation tracking |
| `charity_view` | charity_id, charity_name, view_type, flow_* | Detail page opens |
| `charity_card_click` | charity_id, charity_name, charity_tier, list_position, flow_* | Browse engagement |
| `search` | search_term, result_count, flow_* | Search behavior |
| `donate_click` | charity_id, charity_name, destination_url, flow_* | Donation intent |
| `outbound_click` | charity_id, charity_name, destination_url | External links |
| `sign_in_start` | method, flow_* | Login funnel start |
| `sign_in_success` | method, auth_type, flow_* | Login funnel complete (auth_type: 'signup' or 'login') |
| `hero_cta_click` | cta_name, destination_path | Landing engagement |

**Flow Tracking Parameters (on all major events):**

| Parameter | Example | Purpose |
|-----------|---------|---------|
| `flow_id` | `1706234567890-abc123` | Unique session identifier |
| `flow_path` | `landing>browse>card_click>charity_view` | User journey sequence |
| `flow_step` | `4` | Step number in journey |

**Key Goals:**
1. **Primary:** Login conversions (sign_in_start events)
2. **Secondary:** Time on site / engagement

---

## Analytics Queries

### Realtime Overview

```
Use mcp__analytics-mcp__run_realtime_report with:
- property_id: (use GA4_PROPERTY_ID from .env)
- dimensions: ["eventName"]
- metrics: ["eventCount"]
```

### Top Charities by Card Clicks (Last 7 Days)

```
Use mcp__analytics-mcp__run_report with:
- property_id: (use GA4_PROPERTY_ID from .env)
- date_ranges: [{"start_date": "7daysAgo", "end_date": "yesterday"}]
- dimensions: ["customEvent:charity_name"]
- metrics: ["eventCount"]
- dimension_filter: {"filter": {"field_name": "eventName", "string_filter": {"match_type": 1, "value": "charity_card_click"}}}
- order_bys: [{"metric": {"metric_name": "eventCount"}, "desc": true}]
- limit: 20
```

### Search Terms Analysis

```
Use mcp__analytics-mcp__run_report with:
- property_id: (use GA4_PROPERTY_ID from .env)
- date_ranges: [{"start_date": "7daysAgo", "end_date": "yesterday"}]
- dimensions: ["customEvent:search_term"]
- metrics: ["eventCount"]
- dimension_filter: {"filter": {"field_name": "eventName", "string_filter": {"match_type": 1, "value": "search"}}}
- order_bys: [{"metric": {"metric_name": "eventCount"}, "desc": true}]
- limit: 20
```

### Engagement Metrics (Time on Site)

```
Use mcp__analytics-mcp__run_report with:
- property_id: (use GA4_PROPERTY_ID from .env)
- date_ranges: [{"start_date": "7daysAgo", "end_date": "yesterday"}]
- dimensions: ["date"]
- metrics: ["averageSessionDuration", "engagedSessions", "sessions", "activeUsers"]
- order_bys: [{"dimension": {"dimension_name": "date"}, "desc": false}]
```

### Login Funnel Analysis

```
Use mcp__analytics-mcp__run_report with:
- property_id: (use GA4_PROPERTY_ID from .env)
- date_ranges: [{"start_date": "7daysAgo", "end_date": "yesterday"}]
- dimensions: ["eventName"]
- metrics: ["eventCount"]
- dimension_filter: {"filter": {"field_name": "eventName", "in_list_filter": {"values": ["sign_in_start", "page_view"], "case_sensitive": true}}}
```

---

## Funnel Analysis Pattern

GA4 doesn't have a direct funnel API, but you can simulate it by running sequential queries:

### Browse → Card Click → Charity View → Donate Funnel

**Step 1: Count users who visited /browse**
```
dimensions: ["pagePath"]
metrics: ["activeUsers"]
dimension_filter: pagePath contains "/browse"
```

**Step 2: Count charity_card_click events**
```
dimensions: ["eventName"]
metrics: ["eventCount"]
dimension_filter: eventName = "charity_card_click"
```

**Step 3: Count charity_view events**
```
dimensions: ["eventName"]
metrics: ["eventCount"]
dimension_filter: eventName = "charity_view"
```

**Step 4: Count donate_click events**
```
dimensions: ["eventName"]
metrics: ["eventCount"]
dimension_filter: eventName = "donate_click"
```

Calculate drop-off rates between each step.

---

## Standard Reports to Run

### Daily Health Check

Run these queries and summarize:

1. **Traffic:** Total sessions, active users (vs previous period)
2. **Engagement:** Avg session duration, bounce rate
3. **Top Pages:** Most viewed pages
4. **Top Charities:** Most clicked charity cards
5. **Conversions:** sign_in_start count

### Weekly Deep Dive

1. **Search Analysis:** What are users searching for? Are there charities we don't have?
2. **Funnel Metrics:** Browse → Card Click → View → Donate conversion rates
3. **Device Split:** Mobile vs Desktop engagement differences
4. **Geographic:** Where are users coming from?

---

## Interpreting Results

### Engagement Benchmarks

| Metric | Poor | Average | Good |
|--------|------|---------|------|
| Avg Session Duration | <1 min | 1-3 min | >3 min |
| Pages per Session | <2 | 2-4 | >4 |
| Bounce Rate | >70% | 40-70% | <40% |
| Card Click Rate | <5% | 5-15% | >15% |

### Red Flags to Watch

- High bounce rate on /browse → cards may not be compelling
- Low charity_view after card_click → page load issues?
- Zero search events → search feature not discoverable
- sign_in_start with no sign_in_success → auth issues (note: sign_in_success not yet implemented)

---

## Flow Path Analysis

Query common user journeys:

```
Use mcp__analytics-mcp__run_report with:
- property_id: (use GA4_PROPERTY_ID from .env)
- date_ranges: [{"start_date": "7daysAgo", "end_date": "yesterday"}]
- dimensions: ["customEvent:flow_path"]
- metrics: ["eventCount"]
- dimension_filter: {"filter": {"field_name": "eventName", "string_filter": {"match_type": 1, "value": "donate_click"}}}
- limit: 20
```

This shows what paths lead to donations.

---

## Future Improvements

| Event | Purpose | Priority |
|-------|---------|----------|
| `filter_used` | Which browse filters are popular | Medium |
| `view_type_switch` | Terminal vs Editorial preference | Low |
| `scroll_depth` | Content engagement depth | Low |

---

## Quick Commands

**Realtime snapshot:**
> "What's happening on the site right now?"

**Weekly report:**
> "Give me a weekly analytics summary"

**Search insights:**
> "What are users searching for?"

**Charity performance:**
> "Which charities get the most clicks?"

**Engagement check:**
> "How's our time on site trending?"
