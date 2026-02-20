"""Firestore analytics collector for Good Measure Giving.

Queries Firestore via REST API using gcloud auth token.
Uses collection group queries to access subcollections (bookmarks, giving_history, charity_targets).
Outputs structured JSON to stdout for consumption by the /analytics command.

Dependencies: Python stdlib only.
"""

import json
import subprocess
import sys
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime, timezone

PROJECT_ID = "good-measure-giving"
DATABASE = "(default)"
BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/{DATABASE}/documents"


def get_auth_token() -> str:
    """Get OAuth2 bearer token from gcloud."""
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            print(f"Error: gcloud auth failed: {result.stderr.strip()}", file=sys.stderr)
            sys.exit(1)
        return result.stdout.strip()
    except FileNotFoundError:
        print("Error: gcloud CLI not found. Install it or authenticate.", file=sys.stderr)
        sys.exit(1)


def unwrap_value(val):
    """Convert Firestore type-wrapped value to plain Python value.

    Firestore REST API returns values like {"stringValue": "x"}, {"integerValue": "123"}, etc.
    """
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
    url = f"{BASE_URL}:runQuery"
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


def analyze_users(users: list) -> dict:
    """Analyze user signups and profile completeness."""
    signups_by_day = defaultdict(int)
    features = {
        "has_zakat_target": 0,
        "has_giving_buckets": 0,
        "has_bucket_assignments": 0,
        "has_geo_preferences": 0,
        "has_fiqh_preferences": 0,
        "has_zakat_anniversary": 0,
    }

    for user in users:
        # Signup timeline
        created = user.get("createdAt")
        if created:
            day = created[:10]  # YYYY-MM-DD
            signups_by_day[day] += 1

        # Feature adoption from user profile fields
        if user.get("targetZakatAmount"):
            features["has_zakat_target"] += 1
        if user.get("givingBuckets"):
            features["has_giving_buckets"] += 1
        if user.get("charityBucketAssignments"):
            features["has_bucket_assignments"] += 1
        if user.get("geographicPreferences"):
            features["has_geo_preferences"] += 1
        if user.get("fiqhPreferences") and any(user["fiqhPreferences"].values()):
            features["has_fiqh_preferences"] += 1
        if user.get("zakatAnniversary"):
            features["has_zakat_anniversary"] += 1

    return {
        "total_users": len(users),
        "signups_by_day": dict(sorted(signups_by_day.items())),
        "profile_features": features,
    }


def analyze_bookmarks(bookmarks: list) -> dict:
    """Analyze bookmark activity."""
    by_charity = defaultdict(int)
    users_with_bookmarks = set()

    for bm in bookmarks:
        ein = bm.get("charityEin", "unknown")
        by_charity[ein] += 1
        # Extract user ID from path: users/{uid}/bookmarks/{ein}
        path = bm.get("__path__", "")
        parts = path.split("/")
        if len(parts) >= 2:
            users_with_bookmarks.add(parts[1])

    top_bookmarked = sorted(by_charity.items(), key=lambda x: -x[1])[:10]

    return {
        "total_bookmarks": len(bookmarks),
        "unique_users": len(users_with_bookmarks),
        "top_charities": [{"ein": ein, "count": count} for ein, count in top_bookmarked],
    }


def analyze_giving(giving_history: list) -> dict:
    """Analyze giving/donation activity."""
    by_category: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "total": 0})
    by_charity: dict[str, dict] = defaultdict(lambda: {"count": 0, "total": 0, "name": ""})
    users_with_donations = set()

    for entry in giving_history:
        category = entry.get("category", "other")
        amount = entry.get("amount", 0) or 0
        ein = entry.get("charityEin", "unknown")
        name = entry.get("charityName", "")

        by_category[category]["count"] += 1
        by_category[category]["total"] += amount

        by_charity[ein]["count"] += 1
        by_charity[ein]["total"] += amount
        if name:
            by_charity[ein]["name"] = name

        path = entry.get("__path__", "")
        parts = path.split("/")
        if len(parts) >= 2:
            users_with_donations.add(parts[1])

    top_charities = sorted(by_charity.items(), key=lambda x: -x[1]["total"])[:10]

    return {
        "total_donations": len(giving_history),
        "unique_donors": len(users_with_donations),
        "total_amount": sum(c["total"] for c in by_category.values()),
        "by_category": {k: dict(v) for k, v in by_category.items()},
        "top_charities": [
            {"ein": ein, "name": d["name"], "count": d["count"], "total": d["total"]}
            for ein, d in top_charities
        ],
    }


def analyze_issues(issues: list) -> dict:
    """Analyze reported issues."""
    by_type = defaultdict(int)
    for issue in issues:
        issue_type = issue.get("type", "unknown")
        by_type[issue_type] += 1

    return {
        "total_issues": len(issues),
        "by_type": dict(by_type),
    }


def main():
    print("Fetching gcloud auth token...", file=sys.stderr)
    token = get_auth_token()

    print("Querying Firestore...", file=sys.stderr)

    # Top-level collections
    users = run_query(token, "users")
    reported_issues = run_query(token, "reported_issues")

    # Subcollections via collection group queries
    bookmarks = run_query(token, "bookmarks", all_descendants=True)
    giving_history = run_query(token, "giving_history", all_descendants=True)
    charity_targets = run_query(token, "charity_targets", all_descendants=True)

    print(f"Found: {len(users)} users, {len(bookmarks)} bookmarks, "
          f"{len(giving_history)} donations, {len(charity_targets)} targets, "
          f"{len(reported_issues)} issues", file=sys.stderr)

    # Aggregate
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "users": analyze_users(users),
        "bookmarks": analyze_bookmarks(bookmarks),
        "giving": analyze_giving(giving_history),
        "charity_targets": {
            "total": len(charity_targets),
            "unique_users": len({
                doc["__path__"].split("/")[1]
                for doc in charity_targets
                if len(doc.get("__path__", "").split("/")) >= 2
            }),
        },
        "reported_issues": analyze_issues(reported_issues),
        "feature_adoption": {
            "bookmarks": len({
                doc["__path__"].split("/")[1]
                for doc in bookmarks
                if len(doc.get("__path__", "").split("/")) >= 2
            }),
            "giving_history": len({
                doc["__path__"].split("/")[1]
                for doc in giving_history
                if len(doc.get("__path__", "").split("/")) >= 2
            }),
            "charity_targets": len({
                doc["__path__"].split("/")[1]
                for doc in charity_targets
                if len(doc.get("__path__", "").split("/")) >= 2
            }),
        },
    }

    # Merge in profile-level feature counts
    report["feature_adoption"].update(report["users"]["profile_features"])

    json.dump(report, sys.stdout, indent=2)
    print(file=sys.stdout)  # trailing newline


if __name__ == "__main__":
    main()
