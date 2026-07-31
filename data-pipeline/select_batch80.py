#!/usr/bin/env python3
"""Pick the next 40 (batch80.txt) out of the 86 eligible charities.

Selection, in order:
  1. Every charity currently missing from the index or blocked. These are the
     ones the run has to actually beat; excluding them would flatter the result.
  2. The rest stratified across sections in proportion to what remains, taken
     in source order within each section. Source order alone would make the
     batch 31/40 international relief and 2/40 mosques, which says nothing
     about the 33 mosque-and-community orgs still queued behind it — the
     largest remaining group and the one with the thinnest source coverage.

An exclusion row proves nothing on its own: export_exclusions is append-only,
so a charity is only blocked NOW if nothing successful happened after it.
"""
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

WT = Path("/Users/uabbasi/dev/good-measure-giving/.claude/worktrees/pipeline-40-charity-run")
PIPELINE = WT / "data-pipeline"
SRC = PIPELINE / "pilot_charities.txt"
DETAIL = WT / "website" / "data" / "charities"
INDEX = WT / "website" / "public" / "data" / "charities.json"

done = {
    line.split("|")[1].strip()
    for line in (PIPELINE / "batch40.txt").read_text().splitlines()
    if "|" in line
}


def dsql(q):
    r = subprocess.run(["dolt", "sql", "-r", "json", "-q", q],
                       cwd=Path.home() / ".amal-metric-data/dolt/zakaat",
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("SQL ERROR: " + r.stderr[:800])
    return json.loads(r.stdout).get("rows", [])


rows, section = [], None
for i, raw in enumerate(SRC.read_text().splitlines(), 1):
    s = raw.strip()
    if s.startswith("#"):
        h = s.lstrip("#").strip()
        if h and set(h) != {"="} and "|" not in h:
            section = h
        continue
    if "|" not in s:
        continue
    p = [x.strip() for x in s.split("|")]
    if len(p) < 2 or not p[1]:
        continue
    if p[1] in done or ("HIDE" in raw.upper() and "TRUE" in raw.upper()):
        continue
    if section and "HARD DATA" in section:
        continue
    rows.append({"line": i, "name": p[0], "ein": p[1], "section": section,
                 "raw": raw.rstrip()})

index = {c["ein"] for c in json.loads(INDEX.read_text())["charities"]}
inlist = ",".join(f"'{r['ein']}'" for r in rows)

latest_excl = {}
for r in dsql("SELECT charity_ein, reason, excluded_at FROM export_exclusions "
              f"WHERE charity_ein IN ({inlist}) ORDER BY excluded_at"):
    latest_excl[r["charity_ein"]] = r
evals = {r["charity_ein"]: r for r in dsql(
    "SELECT charity_ein, judge_error_count, amal_score FROM evaluations "
    f"WHERE charity_ein IN ({inlist})")}

for r in rows:
    f = DETAIL / f"charity-{r['ein']}.json"
    r["upd"] = json.loads(f.read_text()).get("lastUpdated", "")[:19] if f.exists() else ""
    ex = latest_excl.get(r["ein"])
    r["excl_at"] = str(ex["excluded_at"])[:19] if ex else ""
    r["excl"] = ex["reason"] if ex else ""
    r["in_index"] = r["ein"] in index
    # dolt's JSON writer returns numbers as strings; "0" is truthy.
    raw_jerr = evals.get(r["ein"], {}).get("judge_error_count")
    r["jerr"] = None if raw_jerr in (None, "") else int(raw_jerr)
    r["blocked_now"] = bool(r["excl_at"]) and r["excl_at"] > (r["upd"] or "")
    r["hard"] = (not r["in_index"]) or r["blocked_now"] or bool(r["jerr"])

SHORT = {
    "Organizations focused on international relief and development": "relief",
    "Mosques, Islamic centers, community organizations": "mosque",
    "MUSLIM EDUCATION & SCHOLARSHIP": "education",
    "MUSLIM ADVOCACY & CIVIL RIGHTS": "advocacy",
    "MUSLIM HEALTH & WELLNESS": "health",
    "ACTIVE TESTING CHARITIES": "active",
}
for r in rows:
    r["sec"] = SHORT.get(r["section"], r["section"] or "?")

hard = [r for r in rows if r["hard"]]
rest = [r for r in rows if not r["hard"]]

print(f"eligible pool {len(rows)}  |  must-include (missing/blocked) {len(hard)}  |  clean {len(rest)}\n")
print("MUST INCLUDE:")
for r in hard:
    why = []
    if not r["in_index"]:
        why.append("not in index")
    if r["blocked_now"]:
        why.append(f"blocked {r['excl_at'][:10]}")
    if r["jerr"]:
        why.append(f"judge_error_count={r['jerr']}")
    print(f"  {r['ein']:<11} {r['name'][:36]:<36} {r['sec']:<10} {', '.join(why)}")

# Stratify the remaining slots across sections in proportion to the pool.
need = 40 - len(hard)
by_sec = defaultdict(list)
for r in rest:
    by_sec[r["sec"]].append(r)
pool_counts = Counter(r["sec"] for r in rows)
already = Counter(r["sec"] for r in hard)

quota, total = {}, sum(pool_counts.values())
for sec, n in pool_counts.items():
    quota[sec] = max(0, round(40 * n / total) - already.get(sec, 0))
# reconcile rounding against the exact number of slots left
while sum(quota.values()) > need:
    sec = max(quota, key=lambda s: (quota[s], pool_counts[s]))
    quota[sec] -= 1
while sum(quota.values()) < need:
    sec = max(quota, key=lambda s: pool_counts[s] - quota[s] - already.get(s, 0))
    quota[sec] += 1

fill = []
for sec, k in sorted(quota.items(), key=lambda kv: -kv[1]):
    take = by_sec[sec][:k]
    if len(take) < k:
        raise SystemExit(f"section {sec} has only {len(take)} clean, wanted {k}")
    fill.extend(take)

print(f"\nSTRATIFIED FILL ({need}):")
for sec in sorted(quota, key=lambda s: -quota[s]):
    names = [r["name"][:28] for r in fill if r["sec"] == sec]
    print(f"  {sec:<10} {quota[sec]:>2} of {pool_counts[sec]:>2} in pool: {', '.join(names)}")

batch = sorted(hard + fill, key=lambda r: r["line"])
assert len(batch) == 40 and len({r["ein"] for r in batch}) == 40
assert not ({r["ein"] for r in batch} & done)
out = PIPELINE / "batch80.txt"
out.write_text("\n".join(r["raw"] for r in batch) + "\n")
print(f"\nwrote {out.name}: {len(batch)} charities, "
      f"{sum(1 for r in batch if r['hard'])} known-hard")
print("final section spread:", dict(Counter(r["sec"] for r in batch)))
