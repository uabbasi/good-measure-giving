"""Cloudflare analytics collector for Good Measure Giving.

Queries Cloudflare GraphQL API for zone analytics (HTTP-level) and
Web Analytics RUM data (beacon-based, real browser visits).
Outputs structured JSON to stdout for consumption by the /analytics command.

Dependencies: Python stdlib only.

Environment variables:
  CLOUDFLARE_API_TOKEN  - API token with Analytics:Read permission
  CLOUDFLARE_ZONE_ID    - Zone ID for goodmeasuregiving.org
  CLOUDFLARE_ACCOUNT_ID - Account ID for RUM/Web Analytics queries
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

GRAPHQL_URL = "https://api.cloudflare.com/client/v4/graphql"

# Defaults (overridable via env vars)
ZONE_ID = os.environ.get("CLOUDFLARE_ZONE_ID", "6d49d809995ae89d1eb99078f5480ce1")
ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "eac7b9a0b69e8c12d9222c6bfaade506")


def get_api_token() -> str:
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if not token:
        print("Error: CLOUDFLARE_API_TOKEN not set. Source ~/.secrets/api_keys.sh", file=sys.stderr)
        sys.exit(1)
    return token


def graphql_query(token: str, query: str) -> dict:
    data = json.dumps({"query": query}).encode()
    req = urllib.request.Request(GRAPHQL_URL, data=data, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"Error: Cloudflare API {e.code}: {body[:300]}", file=sys.stderr)
        return {}
    if result.get("errors"):
        print(f"GraphQL errors: {json.dumps(result['errors'], indent=2)}", file=sys.stderr)
    return result.get("data") or {}


def get_date_range(days: int = 7) -> tuple[str, str]:
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    return start.isoformat(), end.isoformat()


def fetch_zone_analytics(token: str, start: str, end: str) -> list:
    """HTTP-level analytics: requests, page views, unique IPs, threats."""
    query = f"""{{
  viewer {{
    zones(filter: {{zoneTag: "{ZONE_ID}"}}) {{
      httpRequests1dGroups(
        limit: 30
        orderBy: [date_DESC]
        filter: {{date_geq: "{start}", date_leq: "{end}"}}
      ) {{
        dimensions {{ date }}
        sum {{
          requests
          pageViews
          threats
          bytes
        }}
        uniq {{
          uniques
        }}
      }}
    }}
  }}
}}"""
    data = graphql_query(token, query)
    zones = data.get("viewer", {}).get("zones", [])
    if not zones:
        return []
    return zones[0].get("httpRequests1dGroups", [])


def fetch_zone_top_paths(token: str, limit: int = 15) -> list:
    """Top requested paths (last 24h only — free plan limit)."""
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    today = datetime.now(timezone.utc).date().isoformat()
    query = f"""{{
  viewer {{
    zones(filter: {{zoneTag: "{ZONE_ID}"}}) {{
      httpRequestsAdaptiveGroups(
        limit: {limit}
        orderBy: [count_DESC]
        filter: {{
          date_geq: "{yesterday}"
          date_leq: "{today}"
          requestSource: "eyeball"
        }}
      ) {{
        count
        dimensions {{
          clientRequestPath
        }}
      }}
    }}
  }}
}}"""
    data = graphql_query(token, query)
    zones = data.get("viewer", {}).get("zones", [])
    if not zones:
        return []
    return zones[0].get("httpRequestsAdaptiveGroups", [])


def fetch_zone_top_countries(token: str, limit: int = 10) -> list:
    """Top countries (last 24h only — free plan limit)."""
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    today = datetime.now(timezone.utc).date().isoformat()
    query = f"""{{
  viewer {{
    zones(filter: {{zoneTag: "{ZONE_ID}"}}) {{
      httpRequestsAdaptiveGroups(
        limit: {limit}
        orderBy: [count_DESC]
        filter: {{
          date_geq: "{yesterday}"
          date_leq: "{today}"
          requestSource: "eyeball"
        }}
      ) {{
        count
        dimensions {{
          clientCountryName
        }}
      }}
    }}
  }}
}}"""
    data = graphql_query(token, query)
    zones = data.get("viewer", {}).get("zones", [])
    if not zones:
        return []
    return zones[0].get("httpRequestsAdaptiveGroups", [])


def fetch_rum_pageloads(token: str, start: str, end: str) -> list:
    """Web Analytics (RUM beacon) data: real browser visits, page load counts."""
    query = f"""{{
  viewer {{
    accounts(filter: {{accountTag: "{ACCOUNT_ID}"}}) {{
      rumPageloadEventsAdaptiveGroups(
        limit: 30
        orderBy: [date_DESC]
        filter: {{date_geq: "{start}", date_leq: "{end}"}}
      ) {{
        count
        dimensions {{
          date
        }}
        sum {{
          visits
        }}
      }}
    }}
  }}
}}"""
    data = graphql_query(token, query)
    accounts = data.get("viewer", {}).get("accounts", [])
    if not accounts:
        return []
    return accounts[0].get("rumPageloadEventsAdaptiveGroups", [])


def fetch_rum_top_paths(token: str, start: str, end: str, limit: int = 15) -> list:
    """Web Analytics top paths by visit count."""
    query = f"""{{
  viewer {{
    accounts(filter: {{accountTag: "{ACCOUNT_ID}"}}) {{
      rumPageloadEventsAdaptiveGroups(
        limit: {limit}
        orderBy: [sum_visits_DESC]
        filter: {{date_geq: "{start}", date_leq: "{end}"}}
      ) {{
        count
        dimensions {{
          requestPath
        }}
        sum {{
          visits
        }}
      }}
    }}
  }}
}}"""
    data = graphql_query(token, query)
    accounts = data.get("viewer", {}).get("accounts", [])
    if not accounts:
        return []
    return accounts[0].get("rumPageloadEventsAdaptiveGroups", [])


def fetch_rum_top_countries(token: str, start: str, end: str, limit: int = 10) -> list:
    """Web Analytics top countries by visit count."""
    query = f"""{{
  viewer {{
    accounts(filter: {{accountTag: "{ACCOUNT_ID}"}}) {{
      rumPageloadEventsAdaptiveGroups(
        limit: {limit}
        orderBy: [sum_visits_DESC]
        filter: {{date_geq: "{start}", date_leq: "{end}"}}
      ) {{
        count
        dimensions {{
          countryName
        }}
        sum {{
          visits
        }}
      }}
    }}
  }}
}}"""
    data = graphql_query(token, query)
    accounts = data.get("viewer", {}).get("accounts", [])
    if not accounts:
        return []
    return accounts[0].get("rumPageloadEventsAdaptiveGroups", [])


def fetch_rum_browsers(token: str, start: str, end: str, limit: int = 10) -> list:
    """Web Analytics browser breakdown."""
    query = f"""{{
  viewer {{
    accounts(filter: {{accountTag: "{ACCOUNT_ID}"}}) {{
      rumPageloadEventsAdaptiveGroups(
        limit: {limit}
        orderBy: [sum_visits_DESC]
        filter: {{date_geq: "{start}", date_leq: "{end}"}}
      ) {{
        count
        dimensions {{
          userAgentBrowser
        }}
        sum {{
          visits
        }}
      }}
    }}
  }}
}}"""
    data = graphql_query(token, query)
    accounts = data.get("viewer", {}).get("accounts", [])
    if not accounts:
        return []
    return accounts[0].get("rumPageloadEventsAdaptiveGroups", [])


def build_daily_table(zone_data: list, rum_data: list) -> list:
    """Merge zone and RUM data into a daily cross-reference table."""
    zone_by_date = {}
    for row in zone_data:
        d = row["dimensions"]["date"]
        zone_by_date[d] = {
            "requests": row["sum"]["requests"],
            "page_views": row["sum"]["pageViews"],
            "unique_ips": row["uniq"]["uniques"],
            "bytes": row["sum"]["bytes"],
            "threats": row["sum"]["threats"],
        }

    rum_by_date = {}
    for row in rum_data:
        d = row["dimensions"]["date"]
        rum_by_date[d] = {
            "pageloads": row["count"],
            "visits": row["sum"]["visits"],
        }

    all_dates = sorted(set(zone_by_date) | set(rum_by_date), reverse=True)
    table = []
    for d in all_dates:
        entry = {"date": d}
        entry.update(zone_by_date.get(d, {}))
        entry.update(rum_by_date.get(d, {}))
        table.append(entry)
    return table


def main():
    print("Fetching Cloudflare analytics...", file=sys.stderr)
    token = get_api_token()

    start, end = get_date_range(7)
    print(f"Date range: {start} to {end}", file=sys.stderr)

    # Fetch all data
    zone_daily = fetch_zone_analytics(token, start, end)
    zone_paths = fetch_zone_top_paths(token)
    zone_countries = fetch_zone_top_countries(token)
    rum_daily = fetch_rum_pageloads(token, start, end)
    rum_paths = fetch_rum_top_paths(token, start, end)
    rum_countries = fetch_rum_top_countries(token, start, end)
    rum_browsers = fetch_rum_browsers(token, start, end)

    print(f"Zone: {len(zone_daily)} days, RUM: {len(rum_daily)} days", file=sys.stderr)

    # Build report
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date_range": {"start": start, "end": end},
        "daily": build_daily_table(zone_daily, rum_daily),
        "totals": {
            "zone": {
                "requests": sum(r["sum"]["requests"] for r in zone_daily),
                "page_views": sum(r["sum"]["pageViews"] for r in zone_daily),
                "unique_ips": sum(r["uniq"]["uniques"] for r in zone_daily),
                "bytes": sum(r["sum"]["bytes"] for r in zone_daily),
            },
            "rum": {
                "pageloads": sum(r["count"] for r in rum_daily),
                "visits": sum(r["sum"]["visits"] for r in rum_daily),
            },
        },
        "top_paths": {
            "zone": [
                {"path": r["dimensions"]["clientRequestPath"], "requests": r["count"]}
                for r in zone_paths
            ],
            "rum": [
                {"path": r["dimensions"]["requestPath"], "visits": r["sum"]["visits"], "pageloads": r["count"]}
                for r in rum_paths
            ],
        },
        "top_countries": {
            "zone": [
                {"country": r["dimensions"]["clientCountryName"], "requests": r["count"]}
                for r in zone_countries
            ],
            "rum": [
                {"country": r["dimensions"]["countryName"], "visits": r["sum"]["visits"]}
                for r in rum_countries
            ],
        },
        "browsers": [
            {"browser": r["dimensions"]["userAgentBrowser"], "visits": r["sum"]["visits"], "pageloads": r["count"]}
            for r in rum_browsers
        ],
    }

    json.dump(report, sys.stdout, indent=2)
    print(file=sys.stdout)


if __name__ == "__main__":
    main()
