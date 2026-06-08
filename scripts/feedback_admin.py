#!/usr/bin/env python3
"""
Admin CLI for charity feedback / reported issues.

Lists items in the `reported_issues` Firestore collection and marks them
completed (or reopens them). Status lives on the document itself:

    status: 'open' (implicit when absent) | 'completed'
    resolvedAt: ISO timestamp set on completion
    resolutionNote: optional free text ("added to pilot", "duplicate", ...)

Usage:
    uv run python scripts/feedback_admin.py                 # list open
    uv run python scripts/feedback_admin.py --all           # list everything
    uv run python scripts/feedback_admin.py complete <id> [--note "added to pilot_charities.txt"]
    uv run python scripts/feedback_admin.py reopen <id>

Auth: gcloud user credentials (same as firestore_analytics.py).
"""

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

PROJECT_ID = "good-measure-giving"
DATABASE = "(default)"
BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/{DATABASE}/documents"


def get_auth_token() -> str:
    result = subprocess.run(
        ["gcloud", "auth", "print-access-token"], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _request(token: str, url: str, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"Firestore {method} failed ({e.code}): {e.read().decode()[:300]}")


def unwrap(field: dict):
    for kind, value in field.items():
        if kind == "timestampValue":
            return value
        if kind == "nullValue":
            return None
        if kind == "integerValue":
            return int(value)
        return value
    return None


def list_issues(token: str, include_completed: bool) -> None:
    resp = _request(token, f"{BASE_URL}/reported_issues?pageSize=300")
    docs = resp.get("documents", [])
    if not docs:
        print("No reported issues.")
        return
    rows = []
    for doc in docs:
        doc_id = doc["name"].rsplit("/", 1)[-1]
        f = {k: unwrap(v) for k, v in doc.get("fields", {}).items()}
        status = f.get("status") or "open"
        if status == "completed" and not include_completed:
            continue
        rows.append(
            {
                "id": doc_id,
                "status": status,
                "created": str(f.get("createdAt") or "")[:10],
                "type": f.get("issueType") or "unknown",
                "from": f.get("reporterEmail") or f.get("reporterUserId") or "?",
                "role": f.get("submitterRole") or "?",
                "description": str(f.get("description") or "")[:70],
                "resolution": f.get("resolutionNote") or "",
            }
        )
    if not rows:
        print("No open issues. (--all to include completed)")
        return
    rows.sort(key=lambda r: r["created"])
    for r in rows:
        flag = "✓" if r["status"] == "completed" else "•"
        line = f"{flag} {r['id']}  {r['created']}  [{r['type']}/{r['role']}]  {r['from']}\n    {r['description']}"
        if r["resolution"]:
            line += f"\n    ↳ {r['resolution']}"
        print(line)
    open_n = sum(1 for r in rows if r["status"] == "open")
    done_n = sum(1 for r in rows if r["status"] == "completed")
    print(f"\n{open_n} open · {done_n} completed shown")


def set_status(token: str, issue_id: str, status: str, note: str | None) -> None:
    fields: dict = {"status": {"stringValue": status}}
    mask = ["status"]
    if status == "completed":
        fields["resolvedAt"] = {"timestampValue": datetime.now(timezone.utc).isoformat()}
        mask.append("resolvedAt")
        if note:
            fields["resolutionNote"] = {"stringValue": note}
            mask.append("resolutionNote")
    url = (
        f"{BASE_URL}/reported_issues/{issue_id}?"
        + "&".join(f"updateMask.fieldPaths={m}" for m in mask)
        + "&currentDocument.exists=true"
    )
    _request(token, url, method="PATCH", body={"fields": fields})
    print(f"{issue_id} → {status}" + (f" ({note})" if note else ""))


def main() -> None:
    parser = argparse.ArgumentParser(description="Charity feedback admin")
    parser.add_argument("action", nargs="?", default="list", choices=["list", "complete", "reopen"])
    parser.add_argument("issue_id", nargs="?", help="Document id (from list output)")
    parser.add_argument("--note", help="Resolution note (with complete)")
    parser.add_argument("--all", action="store_true", help="Include completed issues in list")
    args = parser.parse_args()

    token = get_auth_token()
    if args.action == "list":
        list_issues(token, include_completed=args.all)
    else:
        if not args.issue_id:
            sys.exit(f"{args.action} requires an issue id (run list first)")
        set_status(token, args.issue_id, "completed" if args.action == "complete" else "open", args.note)


if __name__ == "__main__":
    main()
