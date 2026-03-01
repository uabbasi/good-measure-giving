"""PMF Engagement Tier Analysis for Good Measure Giving.

Applies the Superhuman PMF framework (Sean Ellis's "very disappointed" test)
using behavioral proxies from Firestore user data and GA4 analytics.

Segments users into three engagement tiers:
  Tier 1 (Champions):  Embedded in a real workflow (donations, targets, buckets)
  Tier 2 (Interested): Sees value but hasn't committed (bookmarks, preferences)
  Tier 3 (Passive):    Signed up but minimal engagement

Data sources:
  - Firestore REST API (users, bookmarks, giving_history, charity_targets)
  - GA4 Data API (acquisition funnel, engagement metrics)

Dependencies: Python stdlib only.
"""

import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime, timezone, timedelta

PROJECT_ID = "good-measure-giving"
DATABASE = "(default)"
FIRESTORE_BASE = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/{DATABASE}/documents"

GA4_PROPERTY_ID = "518369044"
GA4_API_BASE = f"https://analyticsdata.googleapis.com/v1beta/properties/{GA4_PROPERTY_ID}"
GA4_CREDENTIALS_PATH = os.environ.get(
    "GOOGLE_APPLICATION_CREDENTIALS",
    os.path.expanduser("~/.secrets/Roshni-3eada2766db6.json"),
)
GA4_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]


# ─── Auth helpers ───


def get_ga4_token() -> str | None:
    """Get an OAuth2 token for GA4 using service account credentials."""
    try:
        from google.oauth2 import service_account
        import google.auth.transport.requests

        creds = service_account.Credentials.from_service_account_file(
            GA4_CREDENTIALS_PATH, scopes=GA4_SCOPES,
        )
        creds.refresh(google.auth.transport.requests.Request())
        return creds.token
    except Exception as e:
        print(f"Warning: GA4 service account auth failed: {e}", file=sys.stderr)
        return None


# ─── Firestore helpers (same pattern as firestore_analytics.py) ───


def get_auth_token() -> str:
    """Get OAuth2 bearer token from gcloud."""
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            print(f"Error: gcloud auth failed: {result.stderr.strip()}", file=sys.stderr)
            sys.exit(1)
        return result.stdout.strip()
    except FileNotFoundError:
        print("Error: gcloud CLI not found.", file=sys.stderr)
        sys.exit(1)


def unwrap_value(val):
    """Convert Firestore type-wrapped value to plain Python value."""
    if val is None:
        return None
    if "stringValue" in val:
        return val["stringValue"]
    if "integerValue" in val:
        return int(val["integerValue"])
    if "doubleValue" in val:
        return float(val["doubleValue"])
    if "booleanValue" in val:
        return val["booleanValue"]
    if "nullValue" in val:
        return None
    if "timestampValue" in val:
        return val["timestampValue"]
    if "arrayValue" in val:
        elements = val["arrayValue"].get("values", [])
        return [unwrap_value(e) for e in elements]
    if "mapValue" in val:
        fields = val["mapValue"].get("fields", {})
        return {k: unwrap_value(v) for k, v in fields.items()}
    return val


def unwrap_document(doc: dict) -> dict:
    """Convert a Firestore document to a plain dict with path info."""
    fields = doc.get("fields", {})
    result = {k: unwrap_value(v) for k, v in fields.items()}
    result["__path__"] = doc.get("name", "").split("/documents/", 1)[-1]
    return result


def run_query(token: str, collection_id: str, all_descendants: bool = False, limit: int = 500) -> list:
    """Run a Firestore structured query."""
    url = f"{FIRESTORE_BASE}:runQuery"
    body = {
        "structuredQuery": {
            "from": [{"collectionId": collection_id, "allDescendants": all_descendants}],
            "limit": limit,
        }
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req) as resp:
            results = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode() if e.fp else ""
        print(f"Error querying {collection_id}: {e.code} {body_text[:200]}", file=sys.stderr)
        return []

    docs = []
    for item in results:
        if "document" in item:
            docs.append(unwrap_document(item["document"]))
    return docs


# ─── GA4 helpers ───


def run_ga4_report(token: str, dimensions: list[str], metrics: list[str],
                   start: str = "2025-01-01", end: str = "yesterday",
                   limit: int = 100) -> list[dict] | None:
    """Run a GA4 Data API report. Returns list of row dicts or None on failure."""
    url = f"{GA4_API_BASE}:runReport"
    body = {
        "dateRanges": [{"startDate": start, "endDate": end}],
        "dimensions": [{"name": d} for d in dimensions],
        "metrics": [{"name": m} for m in metrics],
        "limit": limit,
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode() if e.fp else ""
        print(f"Warning: GA4 query failed: {e.code} {body_text[:200]}", file=sys.stderr)
        return None

    dim_headers = [h["name"] for h in result.get("dimensionHeaders", [])]
    met_headers = [h["name"] for h in result.get("metricHeaders", [])]
    rows = []
    for row in result.get("rows", []):
        entry = {}
        for i, dv in enumerate(row.get("dimensionValues", [])):
            entry[dim_headers[i]] = dv["value"]
        for i, mv in enumerate(row.get("metricValues", [])):
            entry[met_headers[i]] = mv["value"]
        rows.append(entry)
    return rows


def fetch_ga4_funnel(token: str) -> dict | None:
    """Fetch the acquisition funnel: events that track visitor → signup → engagement."""
    rows = run_ga4_report(
        token,
        dimensions=["eventName"],
        metrics=["eventCount", "totalUsers"],
    )
    if rows is None:
        return None

    funnel = {}
    for row in rows:
        funnel[row["eventName"]] = {
            "count": int(row["eventCount"]),
            "users": int(row["totalUsers"]),
        }
    return funnel


def fetch_ga4_retention(token: str) -> dict | None:
    """Fetch new vs returning user breakdown."""
    rows = run_ga4_report(
        token,
        dimensions=["newVsReturning"],
        metrics=["totalUsers", "sessions", "userEngagementDuration", "screenPageViewsPerSession"],
    )
    if rows is None:
        return None

    result = {}
    for row in rows:
        segment = row["newVsReturning"]
        result[segment] = {
            "users": int(row["totalUsers"]),
            "sessions": int(row["sessions"]),
            "engagement_sec": int(row["userEngagementDuration"]),
            "pages_per_session": round(float(row["screenPageViewsPerSession"]), 1),
        }
    return result


def fetch_ga4_dau_trend(token: str, days: int = 30) -> list[dict] | None:
    """Fetch daily active user counts for the last N days."""
    return run_ga4_report(
        token,
        dimensions=["date"],
        metrics=["active1DayUsers", "active7DayUsers", "active28DayUsers", "newUsers"],
        start=f"{days}daysAgo",
        end="yesterday",
        limit=days,
    )


def fetch_ga4_top_pages(token: str, limit: int = 15) -> list[dict] | None:
    """Fetch top pages by views."""
    return run_ga4_report(
        token,
        dimensions=["pagePath"],
        metrics=["screenPageViews", "totalUsers", "userEngagementDuration"],
        limit=limit,
    )


# ─── User ID extraction from subcollection paths ───


def uid_from_path(path: str) -> str | None:
    """Extract user ID from a subcollection document path like users/{uid}/bookmarks/{id}."""
    parts = path.split("/")
    if len(parts) >= 2:
        return parts[1]
    return None


# ─── Tier classification ───


def classify_user(user: dict, user_bookmarks: list, user_donations: list,
                  user_targets: list) -> int:
    """Classify a user into engagement tier 1, 2, or 3."""
    # Tier 1: embedded in a real workflow
    has_donations = len(user_donations) > 0
    has_zakat_target = bool(user.get("targetZakatAmount"))
    has_giving_buckets = bool(user.get("givingBuckets"))
    has_charity_targets = len(user_targets) > 0

    if has_donations or has_zakat_target or has_giving_buckets or has_charity_targets:
        return 1

    # Tier 2: sees value, hasn't committed
    has_bookmarks = len(user_bookmarks) >= 2
    geo_prefs = user.get("geographicPreferences")
    has_geo = bool(geo_prefs) and (isinstance(geo_prefs, list) and len(geo_prefs) > 0)
    fiqh_prefs = user.get("fiqhPreferences")
    has_fiqh = bool(fiqh_prefs) and isinstance(fiqh_prefs, dict) and any(fiqh_prefs.values())

    if has_bookmarks or has_geo or has_fiqh:
        return 2

    # Tier 3: passive
    return 3


# ─── Report generation ───


def build_report(users: list, bookmarks: list, donations: list,
                 charity_targets: list, ga4: dict | None) -> None:
    """Build and print the PMF analysis report."""
    now = datetime.now(timezone.utc)

    # Index subcollections by user ID
    bookmarks_by_user: dict[str, list] = defaultdict(list)
    for bm in bookmarks:
        uid = uid_from_path(bm.get("__path__", ""))
        if uid:
            bookmarks_by_user[uid].append(bm)

    donations_by_user: dict[str, list] = defaultdict(list)
    for d in donations:
        uid = uid_from_path(d.get("__path__", ""))
        if uid:
            donations_by_user[uid].append(d)

    targets_by_user: dict[str, list] = defaultdict(list)
    for t in charity_targets:
        uid = uid_from_path(t.get("__path__", ""))
        if uid:
            targets_by_user[uid].append(t)

    # Classify each user
    tiers: dict[int, list] = {1: [], 2: [], 3: []}
    for user in users:
        path = user.get("__path__", "")
        uid = path.split("/")[-1] if "/" in path else path.replace("users/", "")
        tier = classify_user(
            user,
            bookmarks_by_user.get(uid, []),
            donations_by_user.get(uid, []),
            targets_by_user.get(uid, []),
        )
        tiers[tier].append((uid, user))

    total = len(users)

    # PMF proxy: % of users 30+ days old in Tier 1
    thirty_days_ago = (now - timedelta(days=30)).isoformat()
    mature_users = [u for u in users if (u.get("createdAt") or "") < thirty_days_ago]
    mature_tier1 = [
        (uid, u) for (uid, u) in tiers[1]
        if (u.get("createdAt") or "") < thirty_days_ago
    ]
    pmf_score = (len(mature_tier1) / len(mature_users) * 100) if mature_users else 0

    # ─── Print report ───

    print("=" * 50)
    print("  PMF ENGAGEMENT ANALYSIS")
    print("=" * 50)
    print(f"Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print()

    # Tier distribution
    print("TIER DISTRIBUTION")
    for t in [1, 2, 3]:
        label = {1: "Champions", 2: "Interested", 3: "Passive"}[t]
        count = len(tiers[t])
        pct = count / total * 100 if total else 0
        print(f"  Tier {t} ({label:>10}):  {count:3d} users ({pct:4.1f}%)")
    print(f"  {'Total signed-up users':>22}:  {total:3d}")
    print()

    print(f"PMF PROXY SCORE: {pmf_score:.1f}%")
    print(f"  (% of {len(mature_users)} users 30+ days old in Tier 1)")
    print()

    # ─── Tier 1 profile ("Nicole") ───

    print('TIER 1 PROFILE ("Nicole")')
    t1_users = [u for (_, u) in tiers[1]]
    t1_count = len(t1_users)
    if t1_count:
        # Feature adoption
        has_zakat = sum(1 for u in t1_users if u.get("targetZakatAmount"))
        has_buckets = sum(1 for u in t1_users if u.get("givingBuckets"))
        has_assignments = sum(1 for u in t1_users if u.get("charityBucketAssignments"))
        t1_uids = {uid for (uid, _) in tiers[1]}
        has_donations = sum(1 for uid in t1_uids if donations_by_user.get(uid))
        has_targets = sum(1 for uid in t1_uids if targets_by_user.get(uid))

        print("  Feature adoption:")
        print(f"    Has zakat target:        {has_zakat}/{t1_count}")
        print(f"    Has giving buckets:      {has_buckets}/{t1_count}")
        print(f"    Has bucket assignments:  {has_assignments}/{t1_count}")
        print(f"    Has logged donations:    {has_donations}/{t1_count}")
        print(f"    Has charity targets:     {has_targets}/{t1_count}")

        # Geographic preferences
        geo_counts: dict[str, int] = defaultdict(int)
        for u in t1_users:
            for g in (u.get("geographicPreferences") or []):
                if isinstance(g, str):
                    geo_counts[g] += 1
        if geo_counts:
            top_geo = sorted(geo_counts.items(), key=lambda x: -x[1])
            print(f"  Geographic preferences:    {', '.join(f'{g}({c})' for g, c in top_geo)}")
        else:
            print("  Geographic preferences:    (none set)")

        # Fiqh preferences
        madhab_counts: dict[str, int] = defaultdict(int)
        for u in t1_users:
            fiqh = u.get("fiqhPreferences") or {}
            if isinstance(fiqh, dict):
                m = fiqh.get("madhab")
                if m:
                    madhab_counts[m] += 1
        if madhab_counts:
            dist = ", ".join(f"{m}({c})" for m, c in sorted(madhab_counts.items(), key=lambda x: -x[1]))
            print(f"  Fiqh preferences:          {dist}")
        else:
            print("  Fiqh preferences:          (none set)")

        # Averages
        t1_bookmark_counts = [len(bookmarks_by_user.get(uid, [])) for uid in t1_uids]
        t1_donation_counts = [len(donations_by_user.get(uid, [])) for uid in t1_uids]
        avg_bm = sum(t1_bookmark_counts) / t1_count
        avg_don = sum(t1_donation_counts) / t1_count
        print(f"  Avg bookmarks:             {avg_bm:.1f}")
        print(f"  Avg donations logged:      {avg_don:.1f}")

        # Most bookmarked charities among Tier 1
        ein_counts: dict[str, int] = defaultdict(int)
        for uid in t1_uids:
            for bm in bookmarks_by_user.get(uid, []):
                ein = bm.get("charityEin", "unknown")
                ein_counts[ein] += 1
        if ein_counts:
            top5 = sorted(ein_counts.items(), key=lambda x: -x[1])[:5]
            print(f"  Most bookmarked charities: {', '.join(f'{ein}({c})' for ein, c in top5)}")
    else:
        print("  (no Tier 1 users)")
    print()

    # ─── Gap analysis ───

    print("TIER 2 → TIER 1 GAP ANALYSIS")
    # What features each tier has
    def tier_features(tier_list):
        user_ids = {uid for (uid, _) in tier_list}
        us = [u for (_, u) in tier_list]
        n = len(us) or 1
        return {
            "zakat_target": sum(1 for u in us if u.get("targetZakatAmount")) / n,
            "giving_buckets": sum(1 for u in us if u.get("givingBuckets")) / n,
            "bucket_assignments": sum(1 for u in us if u.get("charityBucketAssignments")) / n,
            "donations": sum(1 for uid in user_ids if donations_by_user.get(uid)) / n,
            "charity_targets": sum(1 for uid in user_ids if targets_by_user.get(uid)) / n,
            "bookmarks_2plus": sum(1 for uid in user_ids if len(bookmarks_by_user.get(uid, [])) >= 2) / n,
            "geo_prefs": sum(1 for u in us if u.get("geographicPreferences")) / n,
            "fiqh_prefs": sum(1 for u in us if u.get("fiqhPreferences") and isinstance(u["fiqhPreferences"], dict) and any(u["fiqhPreferences"].values())) / n,
        }

    f1 = tier_features(tiers[1])
    f2 = tier_features(tiers[2])
    f3 = tier_features(tiers[3])

    # What T2 has that T3 doesn't (> 20pp difference)
    t2_over_t3 = [(k, f2[k] - f3[k]) for k in f2 if f2[k] - f3[k] > 0.1]
    t2_over_t3.sort(key=lambda x: -x[1])
    print("  What Tier 2 has that Tier 3 doesn't:")
    if t2_over_t3:
        for feat, diff in t2_over_t3:
            print(f"    {feat:25s}  T2={f2[feat]*100:4.0f}%  T3={f3[feat]*100:4.0f}%  (+{diff*100:.0f}pp)")
    else:
        print("    (no significant differences)")

    # What T1 has that T2 doesn't — the activation gap
    t1_over_t2 = [(k, f1[k] - f2[k]) for k in f1 if f1[k] - f2[k] > 0.1]
    t1_over_t2.sort(key=lambda x: -x[1])
    print("  What Tier 1 has that Tier 2 doesn't (activation gap):")
    if t1_over_t2:
        for feat, diff in t1_over_t2:
            print(f"    {feat:25s}  T1={f1[feat]*100:4.0f}%  T2={f2[feat]*100:4.0f}%  (+{diff*100:.0f}pp)")
    else:
        print("    (no significant differences)")
    print()

    # ─── Recency (Firestore updatedAt) ───

    print("RECENCY (Firestore updatedAt)")
    seven_days_ago = (now - timedelta(days=7)).isoformat()
    active_30d = sum(1 for u in users if (u.get("updatedAt") or "") >= thirty_days_ago)
    active_7d = sum(1 for u in users if (u.get("updatedAt") or "") >= seven_days_ago)
    print(f"  Active last 30 days:  {active_30d} users")
    print(f"  Active last 7 days:   {active_7d} users")

    # updatedAt histogram (by month)
    month_counts: dict[str, int] = defaultdict(int)
    for u in users:
        updated = u.get("updatedAt") or u.get("createdAt") or ""
        if updated:
            month_counts[updated[:7]] += 1
    if month_counts:
        print("  Last activity distribution:")
        for month in sorted(month_counts.keys()):
            bar = "█" * month_counts[month]
            print(f"    {month}  {bar} {month_counts[month]}")
    print()

    # ─── GA4 section ───

    if ga4:
        print("=" * 50)
        print("  GA4 ANALYTICS CONTEXT")
        print("=" * 50)
        print()

        # Acquisition funnel
        if ga4.get("funnel"):
            funnel = ga4["funnel"]
            print("ACQUISITION FUNNEL (all-time)")
            steps = [
                ("first_visit", "First visits"),
                ("page_view", "Page views"),
                ("charity_view", "Charity detail views"),
                ("charity_card_click", "Charity card clicks"),
                ("hero_cta_click", "Hero CTA clicks"),
                ("sign_in_start", "Sign-in started"),
                ("sign_in_success", "Sign-in completed"),
            ]
            max_users = max((funnel.get(k, {}).get("users", 0) for k, _ in steps), default=1) or 1
            for key, label in steps:
                if key in funnel:
                    users_count = funnel[key]["users"]
                    events = funnel[key]["count"]
                    bar_len = int(users_count / max_users * 30)
                    bar = "█" * bar_len
                    print(f"  {label:25s}  {users_count:4d} users  ({events:6d} events)  {bar}")
            print(f"  {'Registered (Firestore)':25s}  {total:4d} users")

            # Conversion rates
            first_visit_users = funnel.get("first_visit", {}).get("users", 0)
            signin_start = funnel.get("sign_in_start", {}).get("users", 0)
            signin_success = funnel.get("sign_in_success", {}).get("users", 0)
            if first_visit_users:
                print(f"\n  Visitor → sign-in start:    {signin_start}/{first_visit_users} ({signin_start/first_visit_users*100:.1f}%)")
                print(f"  Visitor → sign-in success:  {signin_success}/{first_visit_users} ({signin_success/first_visit_users*100:.1f}%)")
            if signin_start:
                print(f"  Sign-in start → success:    {signin_success}/{signin_start} ({signin_success/signin_start*100:.1f}%)")

            # Post-signup engagement events
            post_signup_events = [
                ("search", "Used search"),
                ("donate_click", "Clicked donate"),
                ("filter_apply", "Applied filters"),
                ("tour_complete", "Completed tour"),
                ("feedback_submit", "Submitted feedback"),
            ]
            has_any = any(key in funnel for key, _ in post_signup_events)
            if has_any:
                print("\n  Post-signup engagement events:")
                for key, label in post_signup_events:
                    if key in funnel:
                        print(f"    {label:25s}  {funnel[key]['users']:3d} users  ({funnel[key]['count']} events)")
            print()

        # New vs returning
        if ga4.get("retention"):
            print("NEW vs RETURNING USERS")
            ret = ga4["retention"]
            for segment in ["new", "returning"]:
                if segment in ret:
                    s = ret[segment]
                    eng_min = s["engagement_sec"] / 60
                    print(f"  {segment.capitalize():10s}:  {s['users']:4d} users,  {s['sessions']:4d} sessions,  "
                          f"{eng_min:.0f}min total engagement,  {s['pages_per_session']:.1f} pages/session")
            print()

        # DAU trend
        if ga4.get("dau_trend"):
            print("DAILY ACTIVE USERS (last 30 days)")
            trend = sorted(ga4["dau_trend"], key=lambda r: r["date"], reverse=True)
            # Show recent 14 days in detail
            recent = trend[:14]
            for row in recent:
                date_str = row["date"]
                formatted = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
                dau = int(row["active1DayUsers"])
                wau = int(row["active7DayUsers"])
                mau = int(row["active28DayUsers"])
                new = int(row["newUsers"])
                bar = "█" * min(dau, 40)
                print(f"  {formatted}  DAU={dau:3d}  WAU={wau:3d}  MAU={mau:3d}  new={new:2d}  {bar}")

            # Stickiness: avg DAU / latest MAU (excludes spike days)
            if len(trend) >= 7:
                last_7 = trend[:7]
                avg_dau = sum(int(r["active1DayUsers"]) for r in last_7) / 7
                latest_mau = int(last_7[0]["active28DayUsers"])
                stickiness = avg_dau / latest_mau * 100 if latest_mau else 0
                print(f"\n  Stickiness (avg DAU last 7d / MAU): {stickiness:.1f}%  (avg DAU={avg_dau:.1f}, MAU={latest_mau})")
            print()

        # Top pages
        if ga4.get("top_pages"):
            print("TOP PAGES BY VIEWS")
            for row in ga4["top_pages"][:10]:
                path = row["pagePath"]
                views = int(row["screenPageViews"])
                users_count = int(row["totalUsers"])
                eng_sec = int(row["userEngagementDuration"])
                eng_min = eng_sec / 60
                print(f"  {path:40s}  {views:6d} views  {users_count:4d} users  {eng_min:6.1f}min")
            print()

    # ─── Per-user detail (optional, for debugging) ───

    if "--detail" in sys.argv:
        print()
        print("=" * 50)
        print("  PER-USER DETAIL")
        print("=" * 50)
        for tier_num in [1, 2, 3]:
            print(f"\n--- Tier {tier_num} ---")
            for uid, user in tiers[tier_num]:
                bm_count = len(bookmarks_by_user.get(uid, []))
                don_count = len(donations_by_user.get(uid, []))
                tgt_count = len(targets_by_user.get(uid, []))
                features = []
                if user.get("targetZakatAmount"):
                    features.append(f"zakat=${user['targetZakatAmount']}")
                if user.get("givingBuckets"):
                    features.append(f"buckets={len(user['givingBuckets'])}")
                if user.get("geographicPreferences"):
                    features.append(f"geo={user['geographicPreferences']}")
                if user.get("fiqhPreferences") and any((user["fiqhPreferences"] or {}).values()):
                    features.append("fiqh")
                created = (user.get("createdAt") or "")[:10]
                print(f"  {uid[:8]}..  created={created}  bm={bm_count}  don={don_count}  tgt={tgt_count}  {', '.join(features)}")


def main():
    print("Fetching gcloud auth token...", file=sys.stderr)
    token = get_auth_token()

    # ─── Firestore queries ───
    print("Querying Firestore...", file=sys.stderr)
    users = run_query(token, "users")
    bookmarks = run_query(token, "bookmarks", all_descendants=True)
    giving_history = run_query(token, "giving_history", all_descendants=True)
    charity_targets = run_query(token, "charity_targets", all_descendants=True)

    print(f"Firestore: {len(users)} users, {len(bookmarks)} bookmarks, "
          f"{len(giving_history)} donations, {len(charity_targets)} targets", file=sys.stderr)

    # ─── GA4 queries (separate service account auth) ───
    ga4 = {}
    print("Authenticating with GA4...", file=sys.stderr)
    ga4_token = get_ga4_token()

    if ga4_token:
        print("Querying GA4...", file=sys.stderr)
        funnel = fetch_ga4_funnel(ga4_token)
        if funnel is not None:
            ga4["funnel"] = funnel
            print(f"GA4: {len(funnel)} event types", file=sys.stderr)
            ga4["retention"] = fetch_ga4_retention(ga4_token)
            ga4["dau_trend"] = fetch_ga4_dau_trend(ga4_token)
            ga4["top_pages"] = fetch_ga4_top_pages(ga4_token)
        else:
            print("GA4: funnel query failed (skipping GA4 section)", file=sys.stderr)
    else:
        print("GA4: auth failed, skipping GA4 section", file=sys.stderr)

    # ─── Generate report ───
    print(file=sys.stderr)
    build_report(users, bookmarks, giving_history, charity_targets, ga4 or None)


if __name__ == "__main__":
    main()
