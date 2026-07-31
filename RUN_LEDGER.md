# 40-Charity End-to-End Pipeline Run — Ledger

**Started:** 2026-07-29 21:55 local (CST-0600)
**Worktree:** `.claude/worktrees/pipeline-40-charity-run` on branch `worktree-pipeline-40-charity-run`
**Base commit:** `e7f88e6` (local main HEAD, 1 ahead of origin/main `2987205`)
**Dolt snapshot before run:** `1gm59qfhe71kqu4qavn68057m8aqcfbc` ("Snapshot: before 40-charity end-to-end run (2026-07-29)")
**Dolt exclusion watermark:** `2026-07-29 20:54:32` (Dolt server tz = PDT/UTC-7; system local is -0600)

Resume protocol if the session dies: read this file top to bottom, then run
`uv run python /private/tmp/.../scratchpad/status.py batchNN.txt` to get live state
before re-running anything. Batch files are committed in `data-pipeline/`.

---

## Environment preflight (done)

- Primary checkout `~/dev/good-measure-giving` clean, on `main`. Other worktree
  (`zakat-motif-theme`) clean. No `streaming_runner`/`export`/`judge` processes running.
  → No concurrent session competing for DoltDB or `website/data`.
- Dolt sql-server running (pid 3398). Only `phase_cache` was dirty pre-run (1 row
  added / 1 deleted); folded into the snapshot commit above.
- `uv sync` done in worktree (separate .venv).

## Key facts established before spending anything

1. **Cache is fully cold.** `--cache-status` shows every phase `RUN` for all 40,
   reason `Code changed (d9e55491→bdec1581)` / `(8265e620→bdec1581)` on `crawl`,
   which cascades to all downstream phases. So batch05 gets **zero** cache benefit
   and pays full price. Corollary: **any pipeline code fix I make re-invalidates the
   cache**, so fixes must be weighed against re-paying for the phases they touch.
2. **`export_exclusions` is append-only** (`ExportExclusionRepository` docstring:
   "Audit trail … one row per gate event", PK `(charity_ein, excluded_at)`). It had
   **29 pre-existing rows**, including 5 of my 40 (see below). It therefore will
   never be literally "empty" for those EINs unless I delete audit rows, which I
   will not do. **Evidence #2 will be reported as: no new exclusion events for any
   of the 40 after the watermark above.** Flagging this as a definitional
   deviation from the literal ask, not a workaround.
3. **File mtime is a useless freshness signal here.** `git worktree add` just
   checked out all 166 `website/data/charities/charity-*.json`, so every mtime reads
   as minutes old. Freshness is instead read from the JSON's embedded
   `lastUpdated` field, plus narrative-text comparison for the spot-checks.
4. Export filename convention is `charity-{EIN}.json` (not `{EIN}.json`).
5. All 40 currently have `judge_error_count = 0` and a non-null `judge_content_hash`,
   but the gate also requires the hash to **match a recomputation over current
   content** — and content is about to change, so these hashes will go stale and
   must be refreshed by a re-judge.

### Pre-existing exclusion rows among the 40 (historical, before this run)

| # | EIN | Name | Pre-existing reason | When |
|---|-----|------|--------------------|------|
| 1 | 20-2714426 | UNRWA | judge errors: 11 | 2026-07-26 22:49 |
| 7 | 27-3175543 | United Muslim Relief | judge errors: 1 | 2026-07-23 15:30 |
| 11 | 88-2980325 | Friends of KDSP | judge errors: 2 | 2026-07-26 22:52 |
| 23 | 20-8540050 | Islamic Scholarship Fund | judge errors: 7 | 2026-07-26 22:47 |
| 34 | 92-3079413 | Humaniti | judge errors: 4 | 2026-07-26 22:44 |

These 5 are the judge-gate risk list. UNRWA (11 errors) is both the worst offender
and a mega org, so it is the single most likely charity to block batch05.

## Batch construction (done, validated)

Built by script (not by hand) from `pilot_charities.txt`, copying each full
pipe-delimited line verbatim in the user's specified order. Validation enforced:
each EIN found **exactly once**, **not** in the `HARD DATA CHARITIES` section,
**not** `HIDE:TRUE`, and the source line's name matches the expected name.
All 40 passed. Loader `load_charity_entries()` parses 5/10/25/40 respectively.

Section spread of the 40: 12 international relief/development, 13 mosques/Islamic
centers, 5 advocacy/civil rights, 5 education/scholarship, 3 health/wellness,
2 active-testing.

---

## Per-batch log

### batch05 — #1-5 (UNRWA, Rahima, Noor Project, Amoud, American Imam Academy)

- **Cost estimate before running:** cache fully cold, so full price. Prior Dolt
  commit recorded a run at `$1.89 / 34 attempted ($0.0555/charity)` but that run had
  21 failures, and failures cost far less than successes — so that number is a floor,
  not a per-success estimate. Estimating ~$0.25-0.35 per normal charity for all 8
  phases including rich narratives, and ~2-3x for UNRWA (mega, $51M filer):
  **~$2.00 expected, ~$2.50 worst case.**
- **Budget set:** `--budget 6.0`. Headroom over the $2.50 worst case because the
  per-charity cost is genuinely unknown on a cold cache, and a budget-truncated run
  wastes the spend already made while looking like a data failure. `--checkpoint 2`.
#### Run 1 — 2 of 5. FAILED the batch rule.

Ended because it FINISHED (exit 0), not budget-capped: `$0.2316 spent of $6.00 cap`.

| # | EIN | Name | Run 1 | Cost | Notes |
|---|-----|------|-------|------|-------|
| 1 | 20-2714426 | UNRWA | ✓ exported | $0.1409 | A:78 |
| 2 | 77-0442850 | Rahima Foundation | ✗ crawl failed | — | bbb required-source failure |
| 3 | 45-5637293 | The Noor Project | ✗ crawl failed | — | website terminal captcha |
| 4 | 75-2882187 | Amoud Foundation | ✓ exported | $0.0779 | A:65 |
| 5 | 82-1150290 | American Imam Academy | ✗ crawl failed | — | bbb required-source failure |

**Real per-charity cost (supersedes the estimate):** mega $0.141, mid $0.078.
Failures cost ~$0.013 combined because they die at crawl before the LLM phases.
My $0.25-0.35/charity estimate was ~3x too high.

---

## Failures, root causes, fixes, commits

### Failure A — bbb required-source failure (Rahima #2, American Imam Academy #5)

**Symptom:** `Crawl incomplete: required sources failed/missing:
{'bbb': 'empty or failed to store content'}` — dies at crawl, before extract.

**Root cause (confirmed empirically, not by inspection).** Chain:
1. `BBBCollector.fetch()` correctly reports "not in the BBB registry" as
   `success=True` with sentinel `{"bbb_not_reviewed": true, "ein": ...}` — the H12 fix.
2. That payload is **47 bytes**; `_has_content_substance`'s floor for `bbb` is
   **200**. Verified directly: `has_substance=False` for all three EINs tested.
3. No prior *successful* bbb row exists (all 5 batch05 rows are `success=0`,
   `raw_content` NULL), so `_guard_against_content_downgrade` doesn't fire —
   it returns early on `not existing.get("success")`. Falls through to reject.
4. `_store_raw_content_only` returns False → orchestrator sets
   `sources_failed["bbb"] = "empty or failed to store content"`.
5. `_is_bbb_not_found()` — the escape hatch that strips bbb from
   `required_sources` — only matches the **legacy** text `"not found on BBB"`.
6. bbb stays required → `missing_sources` non-empty → whole crawl returns False.

**Why it looked random / why review missed it.** UNRWA and Amoud hit the *same*
47-byte rejection but survived, because their rows still carry the legacy string
`"Charity not found on BBB WGA"`, so step 5 rescued them. Rahima and Imam Academy
had theirs reset to `"reset: failure TTL expired"` and had nothing to match.
Whether a charity crawls at all came down to which error text it happened to have
on file. `_is_bbb_not_found`'s docstring asserts the `sources_failed` branch "is
already dead" for freshly-crawled charities — provably false; the substance floor
resurrects it.

**Blast radius across the 40 (surveyed, not guessed):** 29 of 40 have failed bbb
rows. 6 carry `reset: failure TTL expired` with no legacy string to save them —
Rahima #2, Imam Academy #5, **Citizens Foundation #10, Anera #22, SAMS #27,
Sadagaat #39**. The latter 4 would have failed in batch10/25/40. This is very
likely also what produced the pre-run Dolt commit's "9 ok, 21 failed of 34".

**Fix:** `_has_content_substance` recognizes the not-reviewed sentinel as
substantive, mirroring the existing `Form990GrantsCollector.NO_XML_SENTINEL`
precedent. Sentinel knowledge centralized as `BBBCollector.NOT_REVIEWED_KEY` +
`is_not_reviewed_sentinel()`. Deliberately narrow: only a JSON object with a
truthy `bbb_not_reviewed` qualifies.

**Tests:** 4 new in `tests/test_bbb_not_reviewed.py` (class
`TestTheVerifiedNegativeSurvivesTheSubstanceGate`) — 2 reproduced the bug (RED
confirmed before the fix), 2 are regression guards proving the fix recognizes the
sentinel rather than lowering the floor (both passed pre-fix, so not vacuous).
Full suite **1909 passed**.

**Commit:** `e504436`

### Failure B — website terminal captcha lockout (The Noor Project #3)

**Symptom:** `required sources failed/missing:
{'website': 'terminal failure (captcha_blocked), TTL 180d'}` — source never even attempted.

**Root cause.** On 2026-07-23 a real attempt got HTTP 202 and was recorded
`CAPTCHA_BLOCKED: challenge page (HTTP 202)`. `classify_failure` matches
`captcha_blocked`/`challenge page` in `TERMINAL_FAILURE_MARKERS` →
`_should_skip_failed_source` applies `TERMINAL_FAILURE_TTL_DAYS = 180` from
`last_attempt_at` → blocked until ~2027-01-19.

**That verdict was wrong.** Fetching the site now: **HTTP 200, 298,249 bytes**,
title "The Noor Project", "Donate" ×13, "Zakat" ×5, exactly one line mentioning a
challenge — a Turnstile widget on a donate form, not an interstitial.

**Design gap found.** Two detectors disagree. The careful one,
`_is_bot_challenge_html`, has a proper co-occurrence gate (a vendor marker or a
`<title>` match is required). The path that produced this verdict
(`web_collector.py:1221-1238`) does **not** use it: HTTP 202/403 sets
`CAPTCHA_BLOCKED` unconditionally, then a naive first-5KB substring sniff for
`"captcha"`/`"challenge"` upgrades it to "challenge page". Worse,
`force_sources` — the only thing that bypasses the 180d skip — is wired into
`crawl.py` only and **never passed by `streaming_runner.py`**, so the canonical
runner has no way to retry a source pinned by a transient verdict.

**Resolution used: data-level, via the pipeline's own designed escape hatch** —
`crawl.py --ein 45-5637293 --refresh-stale`, documented as exactly "what lets the
mode re-crawl a terminally-failed (e.g. captcha) website row instead of respecting
its 180-day skip". Result: **success=1, 38 pages found, 38 with data**, content
refreshed 2026-07-29 21:08. This is not a gate bypass in the `--no-judge-gate`
sense: it re-attempts a skipped fetch and the fetch genuinely succeeded with real
current data.

**No pipeline code change made for B, deliberately.** Changing terminal-failure
backoff policy or the 202/403 detector would affect every charity in the fleet,
which the run instructions say to check in about first. Surveyed the other 39:
**no other terminal website failure exists among the 40**, so B was a single case
and needs no fleet-wide change to finish this run. Raised as a recommendation
instead — see "Open recommendations".

**Commit:** none (data-level remedy only)

### Failure G resolution — factual judge now uses k=3 majority consensus

**User approved the fleet-wide fix** (mirror `score_judge`'s precedent).

`CONSENSUS_ROLLS = 3` added to `factual_judge`. An ERROR stands only when a
majority of completed rolls report one; warnings/info (non-gating) come from the
first roll; deterministic `_quick_checks` stay OUTSIDE the vote because arithmetic
doesn't flip and a majority requirement would only dilute it. The per-roll
rate-limit/truncation retry was extracted to `_verify_claims_with_rate_limit_retry`,
so one rate-limited roll no longer blocks a charity by itself.

**The gate got STRONGER, not weaker, in two ways:**
1. A real error found by 2+ rolls still blocks — only lone dissenters are dropped.
2. **Found a second, latent fail-OPEN bug while fixing this.** The old
   `if llm_result:` path returned `passed=True` whenever verification came back
   `None` rather than raising — i.e. an *unverified* narrative opened the
   publication gate. `score_judge`'s own comment asserts "factual_judge.py does the
   same on this path" (fails closed); it did not. Now it does.

**Commit `c3737a4`.** Suite **1928 passed**. One pre-existing test
(`test_a_clipped_response_is_retried`) asserted `call_count == 2`, which encoded the
single-roll shape; updated to `CONSENSUS_ROLLS + 1` with its intent (a truncated
response must not cost the charity its page) unchanged and still asserted.

## Pipeline code changes made during this run

| Commit | Files | What |
|--------|-------|------|
| `e504436` | `src/collectors/bbb_collector.py`, `src/collectors/orchestrator.py`, `tests/test_bbb_not_reviewed.py` | BBB verified-negative sentinel recognized by the substance gate |
| `ede5e3d` | `src/collectors/charity_navigator.py`, `tests/test_cn_llm_placeholder_financials.py` | Reject LLM-invented placeholder financials (3+ money fields identical) |
| `e60549b` | `baseline.py`, `tests/test_gik_program_ratio_consistency.py` | Narrative uses the cash-adjusted program ratio the scorer actually credited |
| `0bbc3bb` | `rich_phase.py`, `tests/test_rich_reentrancy_staleness.py` | Rich re-entrancy check compares embedded score, not mere existence |
| `c3737a4` | `src/judges/factual_judge.py`, `tests/test_factual_judge_consensus.py`, `tests/test_factual_judge_blockers.py` | k=3 majority consensus + fail-closed on zero completed rolls |

### batch10 runs 4-9 — the long tail, and how it converged

Nine runs. Blockers per run: 2, 2, 3, 2, 1, 1, 1, 1, **0**. Every one was
root-caused; none was waved through. The pattern was a rotating single charity, which
is why the "re-run the whole batch" rule mattered — a fix verified only on the
charity it targeted would have hidden each new one.

| Run | Result | Blocker(s) | Disposition |
|-----|--------|-----------|-------------|
| 4 | 7/10 | Rahima, Noor, UMR | consensus now active; surviving errors were real |
| 5 | 8/10 | Amoud, Clinic | UMR/Rahima/Noor cleared by the ratio-label fix |
| 6 | 9/10 | Noor | zakat non-finding |
| 7 | 9/10 | Amoud | CN overall score cited as transparency |
| 8 | 9/10 | UMR | cross-fiscal-year, again |
| 9 | **10/10** | none | zero new exclusions after watermark `00:37:38` |

Fixes landed in this stretch, each with its own root cause and commit:

- **`f0b7764` — the cash-adjusted ratio needed its LABEL, not just its value.** My
  own earlier fix was half-right: swapping 96.5%→47.5% while still calling it
  "Program Expense Ratio" just relocated the misstatement, and the judge caught it
  ("presenting the cash-adjusted ratio as the general 'program expense ratio'
  without qualification is misleading"). Label is now a prompt placeholder.
- **`00448b0` — the noncash signal named the wrong denominator.** `noncash_ratio` is
  noncash / total CONTRIBUTIONS but the signal headline said "of reported revenue".
  UMR clamps to 100% of contributions while noncash is 95.4% of revenue, so the
  narrative asserted "100% of revenue". Wording only.
- **`40241d0` — fiscal-year prompt rule.** Necessary but NOT sufficient.
- **`2782801` — an empty zakat search asserted zakat is refused.** Noor stored
  `accepts_zakat: false` with 0 sources, 0 confidence, no evidence, no URL. Same
  shape as the BBB bug at the start of this run: a non-finding readable as a
  negative. Now stores None; logic-neutral downstream (None and False are both
  falsy, and `web_collector` already used None for this field).
- **`85f9851` — CN overall score cited as a transparency score.** Amoud claimed "high
  level of transparency with a 80.0/100 score from Charity Navigator" while our own
  transparency signal was NONE. 80.0 is CN's *overall* rating.
- **`71d49e8` — cross-fiscal-year comparison suppressed deterministically.** The
  prompt rule failed: the judge named the year gap itself ("the narrative's figure
  appears to be from FY2024 data") and still returned ERROR, across three charities in
  three runs. Consensus can't filter it because every roll makes the same error. This
  is exactly the case the file already documents for the wallet tag — "the answer is
  not more prompt text. Where a deterministic check owns the question, the model's
  copy does not get to block." Downgraded to WARNING (not dropped), consistent with
  the four existing rules in that chain, so it still reaches the editorial queue.

### batch25 run 1 — 22 of 25

`--budget 5.0 --checkpoint 5`. FINISHED: `$1.5962 spent of $5.00 cap`.
The mega end held: Second Harvest ($286M) A:67, Anera ($204M) A:72, PCRF A:71.

Three blocked, and they are three DIFFERENT kinds of problem:

**#20 Islamic Services Foundation (75-2352043) — GENUINELY UNCRAWLABLE.**
Crawl failed on a live fetch: `website: CAPTCHA_BLOCKED: challenge page (HTTP 202)`.
Verified independently, twice, with a browser user-agent: the site returns a
**169-byte HTTP 202** whose entire body is
`<meta http-equiv="refresh" content="0;/.well-known/sgcaptcha/?r=%2F...">` — a
ShieldSquare/Radware bot-management interstitial. This is a TRUE positive, unlike
The Noor Project (298KB of real content misread as a challenge). `sgcaptcha` is
already one of `_is_bot_challenge_html`'s `strong_markers`, and the codebase itself
documents that such pages "render fine under Playwright" while still being challenge
screens — so the Playwright rescue cannot get through either. `website` is a required
source and H5 deliberately made CAPTCHA *not* demote it.
**Not bypassed. Escalated — this is the "legitimately cannot pass" case.**

**#24 The Morocco Foundation (90-0327815) — REAL data defect, judge was right.**
Narrative reported $147,814; the judge cited Form 990 (FY2023) $134,320. Per source:
CN `fiscal_year 2022 → $147,814`; ProPublica `tax_year 2023 → $134,320`;
form990_grants `tax_year 2023 → $134,320`. **The narrative published the OLDER year.**
Cause is the same CN-vs-ProPublica selection path as Yateem
(`charity_metrics_aggregator` ~L1694): when years differ and PP has <3 income fields
while CN has ≥3, CN's ENTIRE income statement wins **on field count, with no regard
for which year is newer**. So a charity can publish stale-year financials while a
newer filing sits in the DB. Fixing this changes published financials fleet-wide →
NOT acted on, see recommendations.

**#15 Islamic Society of Greater Houston (23-7065716) — judge false positive.**
`board_size`: "the narrative states the board is too small with only two members
listed, **but Candid data shows 2 board members**." The judge flagged an *agreement*
as a contradiction. The existing `numeric_agreement(claim_value, source_value)`
downgrade can't catch it because the two numbers appear only in the prose, not in the
structured claim/source fields. Second error (`financial_filings_availability`) is
arguable at best: it objects to "filings are several years old" by citing FY2022 data,
which in 2026 is four years old.

## Open recommendations (NOT acted on — need user sign-off, fleet-wide)

1. `web_collector.py:1221-1238` should call `_is_bot_challenge_html` instead of
   its own naive first-5KB `"captcha"`/`"challenge"` substring sniff. As written it
   brands any HTTP 202/403 page containing those words a terminal challenge page.
2. A transient block earns a **180-day** terminal TTL, and `streaming_runner.py`
   cannot override it (`force_sources` is `crawl.py`-only). One bad response locks
   a charity out of the canonical pipeline for half a year. Either plumb a force
   flag through `streaming_runner`, or require corroboration//shorten the TTL
   before treating a captcha as terminal.

---

### batch05 run 2 — 5 of 5. PASSED.

`--budget 2.0 --checkpoint 2`. Ended FINISHED: `$0.5807 spent of $2.00 cap`.
All 5 verified exported with fresh `lastUpdated` (2026-07-29 21:12-21:13 Dolt/PDT),
`judge_error_count = 0`, refreshed content hashes, **zero new exclusion events**
after the watermark. Scores shifted slightly vs run 1 (UNRWA 78→80, Amoud 65→69)
because the underlying data was refreshed.

### batch10 run 1 — 8 of 10. FAILED the batch rule.

`--budget 2.0 --checkpoint 5`. Ended FINISHED: `$0.4367 spent of $2.00 cap`.
Cache behaved correctly — batch05's 5 charities cost **$0.0000** each
(`[cache:crawl,extract,discover,synthesize,baseline,judge]`); only the 5 new ones cost.

**The runner printed `Completed: 10, Failed: 0` — that was MISLEADING.** It counts
pipeline completion, not publication. Two charities were excluded by the judge gate
at export and their files on disk are STALE from earlier runs:

| # | EIN | Name | judge errors | file lastUpdated | verdict |
|---|-----|------|--------------|------------------|---------|
| 7 | 27-3175543 | United Muslim Relief | 5 | 2026-07-28 21:26 (stale) | BLOCKED |
| 9 | 99-3373484 | Yateem Foundation | 3 | 2026-07-23 17:56 (stale) | BLOCKED |

A "does the file exist?" check would have falsely reported 10/10 here. Only the
embedded-`lastUpdated` check caught it. Confirms the decision in fact #3 above.

The other 8 exported fresh, including the three risk cases batch10 was meant to
probe: null-financials clinic #6 (A:40), Citizens Foundation #10 (A:83 — one of the
4 charities the BBB fix saved), and IIIT #8.

### Failure C — UMR narrative contradicts the scorer on the program ratio (SYSTEMATIC)

**Not stochastic.** Forced `baseline`+`rich`+`judge` regeneration (`$0.2119`):
UMR 5→4 errors, Yateem 3→2. Same defects recurred. Regeneration is not the fix.

**Root cause.** UMR is ~95% Gifts-in-Kind. Three layers disagree:
- The **scorer** deliberately and correctly scores on the **48% cash-adjusted**
  program ratio. `_compute_cash_adjusted_ratio`'s docstring names UMR by EIN as a
  live case that "must keep scoring on its measured 48% cash-adjusted ratio rather
  than falling back to its 96% filed ratio, which would swing its published score."
  Program Ratio component scored **0/5**.
- The **reconciliation layer** already DETECTS this: `check_gik_inflated_ratio`
  fires HIGH severity at ≥80% noncash and carries the cash-adjusted figure. The run
  logged `United Muslim Relief - Reconcile: 2 signals, 0 patched`.
- The **narrative prompt** (`src/llm/prompts/rich_narrative_v2.txt`) is never told
  any of it. `grep cash_adjusted` on that prompt returns **nothing**. It receives
  the filed `program_expense_ratio` and actively encourages touting it
  ("DO use real financial data: ... '80% program ratio'", "Compare to sector norms:
  '80% program ratio beats the 75% sector average'").

So the LLM dutifully headlines 96.5% as a strength in `amal_score_rationale`,
`strengths`, `summary`, and `dimension_explanations.impact`, and the judge correctly
refuses to publish it. **The judge is right and the narrative is wrong.** Secondary:
narrative says "100% of revenue from non-cash gifts"; actual 95.4%.

**Fix NOT applied — needs sign-off.** Feeding the cash-adjusted ratio + GIK signal
into the narrative prompt changes generated narratives fleet-wide and invalidates
baseline/rich cache for all 169. **55 of 169 charities have a filed program ratio
≥90%**, so that bounds the affected population. This is squarely the "pipeline
change that affects charities outside these 40" case the instructions say to stop on.

### Failure D — Yateem synthesized financials are implausible (DIFFERENT cause)

Not a prompt problem. Synthesized data reads
`total_revenue = program_expenses = total_expenses = exactly $100,000`, ratio
`1.0000` — three identical suspiciously-round values for a real filer. The 990
source shows **$47,893** for TY2024. The narrative faithfully reports the bad
synthesized values (`100.0%` appears 9× in the exported JSON), and the `factual`
judge correctly flags narrative-vs-source contradiction. Root cause is in the
synthesize/aggregation layer for sparse micro orgs, not narrative generation —
exactly the micro-org sparse-data failure mode the run brief predicted.

---

### batch10 run 2 — 8 of 10. Two fixed, two newly broken.

`--budget 3.0`. FINISHED: `$1.0641 spent of $3.00 cap`. No cache hits (extract +
baseline code changed), so everything re-ran.

- **UMR #7 → 0 errors, exported.** GIK fix worked.
- **Yateem #9 → 0 errors, exported.** CN placeholder fix worked.
- **Rahima #2 newly blocked** (1 error) and **IIIT #8 newly blocked** (3 errors).
  This is exactly why the brief requires re-running the whole batch after a fix.

### Failure E — IIIT rich narrative embedded a stale score (REAL, fixed)

`rich_narrative.amal_scores.amal_score = 47` against `evaluations.amal_score = 58`
(and `impact_tier` "BELOW_AVERAGE" vs "AVERAGE"). 47 was IIIT's **pre-run** score.

`rich_content["amal_scores"]` is stamped deterministically from the evaluation row,
not LLM-written, so once baseline re-scores, the stored narrative keeps the old
score. `generate_rich_for_pipeline`'s re-entrancy check asked only whether a rich
narrative **exists**, never whether it is **current**, and short-circuited.
streaming_runner's phase gate *had* correctly decided rich must re-run, but it only
passes `force=True` for `--force-all`/`--force-phase`, so the inner check silently
overrode the dependency-aware decision.

**Fix:** the re-entrancy check now compares the embedded `amal_score` against the
evaluation's current score and regenerates on mismatch. Fixed in the check, not the
call site, so `rich_phase.py`'s standalone entry point benefits too. Genuine
re-entrancy preserved (matching score still short-circuits at zero cost).
**Commit `0bbc3bb`.** Suite 1921.

### Failure F — Rahima revenue error was a JUDGE FALSE POSITIVE (no fix needed)

Judge: "narrative states $4,100,385 but Form 990 (2023) reports $4,006,022."
Per-source check: CN (FY2024) $4,100,385 and form990_grants (tax_year 2024)
$4,100,385 **agree**; ProPublica is tax_year **2023** at $4,006,022. The narrative's
figure is correct and corroborated by two sources for FY2024 — the judge compared it
against the prior fiscal year. It cleared on the next run without any change.

### batch10 run 3 — 8 of 10 again, but a DIFFERENT two.

`--budget 3.0`. FINISHED: `$0.3614 spent of $3.00 cap`. Cache worked (5 charities
$0.0000).

Rahima #2 ✓ and IIIT #8 ✓ (staleness fix confirmed). But clinic #6 and UMR #7 —
both of which had passed in run 2 — each newly reported exactly 1 `factual` error.

### Failure G — THE JUDGE IS NONDETERMINISTIC (structural; NOT yet fixed)

`judge_content_hash` is the pipeline's own hash over the judged content. Across
runs 2 and 3, the hash is **byte-identical** and the verdict **flipped**:

| EIN | judge_content_hash | run 2 | run 3 |
|-----|--------------------|-------|-------|
| 27-3175543 UMR | `13aad00e94299cfc` | 0 errors | **1 error** |
| 77-0442850 Rahima | `5f54d69843b4f4b9` | 1 error | **0 errors** |
| 93-2136609 Clinic | `e1912686657e7fca` | 0 errors | **1 error** |

Same content, same code, different publication decision. The flipping errors are
interpretive, not factual contradictions — both run-3 errors are phrased as what the
narrative *"implies"* ("implies revenue is primarily cash-based"; "implies the
organization accepts sadaqah"), and the second conflates sadaqah with zakat
eligibility when `SADAQAH-ELIGIBLE` is the documented default for every charity.

**The codebase already diagnosed this class for a different judge.** `score_judge`
carries `CONSENSUS_ROLLS = 3` with an explicit comment: "The rationale/score-
consistency check is nondeterministic — identical content flip-flops between 0 and N
errors across rolls. **Gating on a single roll produced spurious publication
blocks.**" It takes an ERROR only on a majority of rolls, and fails closed if no
roll completes.

`factual_judge` emits publication-gating `Severity.ERROR` from a **single roll** and
has no consensus mechanism at all. That is the gap.

**Consequence for this run:** with a ~10-20% per-charity single-roll false-positive
rate, "all 40 clean in one run" is improbable by construction — and grinding
re-runs until green would be gate-shopping, not engineering. Escalated to the user
rather than papered over.

---

### batch40 — FINAL: 34 of 40 exported with current data and current narratives

Two runs. Run 1: 39 completed / 1 crawl-failed, 4 judge-gated → 35/40.
Run 2 (after the cross-year regex fix): 39 completed / 1 crawl-failed, 5 judge-gated
→ **34/40**. Neither run was budget-truncated ($1.5785 / $6.00 and $3.3693 / $6.00).

**The 6 not exported this run, by cause — none bypassed:**

| # | EIN | Name | jerr | Cause | Class |
|---|-----|------|------|-------|-------|
| 20 | 75-2352043 | Islamic Services Foundation | 0 | site serves a 169-byte HTTP 202 `sgcaptcha` interstitial; never reached judge | **hard block, genuinely uncrawlable** |
| 15 | 23-7065716 | Islamic Society of Greater Houston | 7 | incl. "board too small with only two members … but Candid shows 2 board members" | judge false positive |
| 28 | 20-1799252 | MAS Boston Society | 1 | citation judge: "citation states … Zakat eligible, but the claim states it is recognized as zakat-eligible" — semantically identical | judge false positive |
| 35 | 36-4787320 | Justice Defenders | 5 | narrative matches Charity Navigator (judge says so) but is compared against the charity's own scraped Annual Report PDF | cross-source, unresolved |
| 7 | 27-3175543 | United Muslim Relief | 2 | rotating residual | judge, rotating |
| 34 | 92-3079413 | Humaniti | 1 | rotating residual | judge, rotating |

Files for these 6 exist on disk but are STALE — #15/#20/#28/#35 from 2026-07-23/24,
#7 from 00:39 and #34 from 00:53 earlier in this session. **The exporter leaves a
gated charity's previous file in place**, so "the file exists" is never evidence of a
current export; only the embedded `lastUpdated` is.

**Honest read of the residual:** at 40-charity scale roughly 4-6 charities are gated
per run and *which* ones rotates. Consensus (k=3) removed the purely random flips;
what remains are several distinct judge *reasoning* errors — every roll makes the same
mistake, so a majority agrees on a wrong answer. Each is individually fixable in the
same style as the six already fixed, but it is a long tail, not one more fix. I did
not re-roll runs hoping for a clean 40: that would be gate-shopping, which the brief
explicitly rules out.

### Spot-checks on the local dev site (deliverable 6) — all three PASS

`npm install` was required first (fresh worktree has no node_modules). Dev server on
**port 3000**.

| Size | Charity | Verified on the rendered page |
|------|---------|-------------------------------|
| MEGA | UNRWA (20-2714426) | new headline "…critical humanitarian aid and education to Palestine refugees…" **and** fresh `$51,495,126`; the stale `96.5%` string is absent |
| MID | Al-maghrib Institute (27-0091991) | new headline "…Islamic education with high program spending…" and `$2,959,388` |
| MICRO | The Noor Project (45-5637293) | "ACCEPTS ZAKAT" badge now present (the zakat non-finding fix reaching the UI); every rendered phrase — `1,759,964`, `29.6`, "lifting marginalized families out of poverty in Pakistan", "perfect program expense ratio" — confirmed present in the export written at 00:58:57 |

Note on method: the micro page renders the RICH narrative, not the baseline headline,
so an initial grep for the baseline headline returned false. Verified against the
exported JSON instead of assuming. Also confirmed the dev server serves the fresh
`lastUpdated` for all three at `/data/charities/charity-{EIN}.json`.

## Cumulative LLM spend

| Batch | Run | Reported cost | Ended because |
|-------|-----|---------------|---------------|
| batch05 | 1 | $0.2316 | FINISHED (cap $6.00) |
| batch05 | 2 | $0.5807 | FINISHED (cap $2.00) |
| batch10 | 1 | $0.4367 | FINISHED (cap $2.00) |
| UMR+Yateem regen probe | 1 | $0.2119 | FINISHED (cap $1.00) |
| batch10 | 2 | $1.0641 | FINISHED (cap $3.00) |
| batch10 | 3 | $0.3614 | FINISHED (cap $3.00) |
| **Total so far** | | **$2.8864** | no run was ever budget-truncated |

| batch05 | 1 | $0.2316 | FINISHED |
| batch05 | 2 | $0.5807 | FINISHED |
| batch10 | 1 | $0.4367 | FINISHED |
| UMR+Yateem probe | 1 | $0.2119 | FINISHED |
| batch10 | 2 | $1.0641 | FINISHED |
| batch10 | 3 | $0.3614 | FINISHED |
| batch10 | 4 | $1.0049 | FINISHED |
| batch10 | 5 | $0.7718 | FINISHED |
| batch10 | 6 | $0.6593 | FINISHED |
| batch10 | 7 | $0.9984 | FINISHED |
| batch10 | 8 | $0.8380 | FINISHED |
| batch10 | 9 | $0.6712 | FINISHED |
| batch25 | 1 | $1.5962 | FINISHED |
| batch40 | 1 | $1.5785 | FINISHED |
| batch40 | 2 | $3.3693 | FINISHED |
| **TOTAL** | **15 runs** | **$14.3740** | **no run was ever budget-truncated** |

Plus one uncaptured amount: `crawl.py --ein 45-5637293 --refresh-stale` (the Noor
Project website unblock). `crawl.py` prints no budget line, so its website-extraction
LLM cost is not in the $14.3740. Comparable crawl-phase costs elsewhere in this run
were cents.

**Every run ended because it FINISHED, never because it hit the cap.** Highest
utilisation was batch40 run 2 at $3.3693 of $6.00 (56%).

## Final test suite

`uv run pytest -q` → **1949 passed**, 0 failed. `ruff check` clean on every file
touched. Started from 1909 passing; the 40 added tests are the ones written for the
fixes below (RED confirmed before each fix, with non-vacuous regression guards).

---

## Follow-up session: judge self-consistency + ratio basis gap

Three more fixes after the main run, at the user's direction.

| Commit | What | Effect |
|--------|------|--------|
| `c8c4a91` | An ERROR must be self-consistent to gate: identical values → INFO; unnamed claim against a present source → WARNING; prose claim vs bare number → WARNING | Greater Houston 7→0, Humaniti 1→0, Justice Defenders 5→1, UMR 2→1 |
| `dda51e2` | Filed vs cash-adjusted program ratio is a basis gap, bounded in percentage points | Justice Defenders 1→0 |

**Two mistakes caught and corrected mid-implementation, both by existing tests:**
1. Rule 2's first draft downgraded whenever NEITHER value was present, which gutted
   fabrication findings — `test_an_unrelated_zakat_claim_still_blocks` failed.
   Narrowed to one direction (claim unnamed, source present). The mirror shape is
   what a fabrication looks like and still blocks.
2. I nearly added the program ratio to the SHARED `METHODOLOGY_DIVERGENT_FIELD_RE`.
   The score judge defers on that list **unbounded**, so it would have stopped
   blocking narratives that tout the filed 96.5% as an efficiency strength — undoing
   `e60549b`/`f0b7764` from earlier in this run. Kept factual-judge-local, with a
   regression test asserting the shared list still excludes it.

**I also over-claimed once:** I said these rules would fix MAS Boston. They don't —
that error is from the **citation** judge, a different chain entirely.

### State now

Only **2 of 40 are judge-blocked**, down from 5:

| # | EIN | Name | Cause |
|---|-----|------|-------|
| 7 | 27-3175543 | United Muslim Relief | judge compares `claim='7.44'` (cost per beneficiary, **dollars**) against `source='47.5%'` (a **ratio**) — unrelated quantities |
| 28 | 20-1799252 | MAS Boston Society | **citation** judge asserts "Zakat eligible" contradicts "recognized as zakat-eligible"; its own `not contradicted` guard doesn't fire because the model claims it observed one |

Plus **#20 Islamic Services Foundation**, which is not judge-blocked (jerr=0) but
cannot crawl at all — its published file is a week old and would stay that way.

Files written today: **38 of 40**. UMR's file is from 00:39 today but predates its
current (blocked) content. #20 and #28 are from 2026-07-23.

**Not yet verified end-to-end:** no full batch40 run since `c8c4a91`/`dda51e2`. The
other 35 charities' content is unchanged so their hashes still match and they remain
exportable, but a confirming run (~$3, re-judges all 40) has not been done.

Suite: **1974 passed**. Total spend now **$15.29**.

---

## Session 3: #7 and #28 fixed; #20 re-examined; data issues traced

### #7 and #28 — FIXED (`33319d2`), verified 1→0 errors each

Both were category errors, not data problems.
- **UMR**: judge compared `claim='7.44'` (cost per beneficiary, dollars) against
  `source='47.5%'` (a ratio). Deterministic rule: a currency claim against a
  percentage source is not a discrepancy. Requires BOTH that the source is a
  percentage AND that the claim appears as currency in the message, so two
  percentages (a real ratio disagreement) or two dollar amounts still block.
- **MAS Boston**: citation judge blocked over "the citation states the organization
  is Zakat eligible, but the claim states it is recognized as zakat-eligible" — the
  same assertion twice. Zakat eligibility is settled in code by `_quick_checks`, and
  `factual_judge` already refuses the model's second opinion via
  `_is_wallet_tag_agreement`; the citation judge had no equivalent. Claimed zakat
  AMOUNTS are excluded and keep blocking.

**State: 0 of 40 judge-blocked. 39 of 40 files written today.**

### #20 Islamic Services Foundation — my earlier read was WRONG, corrected

The user pushed back that it "used to work." The history says they were right, and
in a way that matters:

```
raw_scraped_data.scraped_at = 2026-03-07   (320,485 bytes of real content)
crawl_attempts 2026-07-23 22:35  success=1  pages_found=1  pages_with_data=0
              reason: "website re-observation thinner than last-good; preserved"
crawl_attempts 2026-07-30 00:43  success=0  CAPTCHA_BLOCKED (HTTP 202)
```

So the last REAL content is from **March 7**. On Jul 23 the crawl was already
returning a page with **zero data**; it only counted as success because the
non-downgrade guard preserved March's content. The failure mode then escalated to a
hard challenge during this run's repeated crawling.

Re-tested ~13 hours later, twice: still `HTTP 202`, 169 bytes,
`/.well-known/sgcaptcha/`. The token is IP-keyed and its prefix changed between
attempts (`ipc:189.204.104.71` → `ipr:189.204.104.71`), i.e. a reputation/IP-scoped
block on our crawler — plausibly aggravated by our own crawl volume.

**Not routed around.** Rotating IPs or solving the challenge is bot-protection
evasion. Options are: accept it, let a verified terminal bot-block demote `website`
to optional (a policy call), or approach the org / another data source.

Adjacent bug worth noting: a reputational block earns the full **180-day** terminal
TTL, and `streaming_runner` still has no way to force a source retry.

### DATA ISSUE — much larger than expected, NOT acted on

`working_capital_months` is computed in `synthesize.py` **exclusively from
ProPublica** (`pp_profile.get("total_expenses")`), while the PUBLISHED
`total_expenses` often comes from Charity Navigator via the aggregator's field-count
selection. The two are frequently different fiscal years.

Humaniti (92-3079413):
```
ProPublica  tax_year 2023  expenses   474,737  assets 306,342  liabilities 548,013
CharityNav  fiscal   2024  expenses 12,707,276  (no balance sheet)
stored working_capital_months = -6.10   (= net assets / PP FY2023 monthly expenses)
recomputed from PUBLISHED figures = -0.2   <- what the judge said, and it was right
```

**Blast radius measured: 128 of 156 charities (82%)** have a `working_capital_months`
that does not reconcile with their own published balance-sheet and expense figures.
Some are extreme (stored 124 months vs 3,149 recomputed). "RESERVES x mo" is
displayed on every charity page.

Same root cause as **The Morocco Foundation** (published CN's FY2022 $147,814 while
FY2023's $134,320 sat in the DB): the income statement may come from CN while other
fields and derived stats come from ProPublica, with nothing requiring a consistent
fiscal year.

Held for a decision because any fix changes a displayed statistic for most of the
site. Options recorded in the summary to the user.

Suite: **1984 passed**. Spend this session: +$0.63 (total ~$15.92).

---

## DATA ISSUE — RESOLVED in code (2026-07-30). NOT yet regenerated.

Decision taken (user): *"where things diverge, we should pick one to be canonical,
whichever one is most trustworthy, and then note the discrepancy."*

### What trustworthiness actually turned out to be

Not one answer per source — it splits by field group. Measured, not assumed:

| probe | result |
|---|---|
| PP income-statement completeness | exactly **2 of 5** fields for 158/169 charities, 0 for 11 |
| fiscal-year recency | CN newer than PP on **134/168**, older on 6, same on 15 |
| same-year agreement (same filing, so a gap is a transcription error) | agree within 1% on **13 of 15**; the 2 misses are CN round numbers ($5,400,000 vs PP's $11,189,635; $900,000 vs $102,250) |
| balance sheets, where both carry one (123) | **18 of CN's visibly corrupt vs 2 of PP's** — `$100,000`/`$500,000` assets appearing 4x, magnitudes lost (11-3013369: CN $113,404 vs 990's $27,427,805; 47-1313957: CN 0 vs $1M) |

So: **CN is canonical for the income statement** (PP simply does not have the
functional-expense breakdown, and CN is a year newer). **PP is canonical for the
balance sheet** (CN's is unreliable). Ties and same-year conflicts go to PP — it is
the filing.

### Defects fixed

1. **Cross-source splicing inside the income statement.** 83-1171525 Link Outside
   published CN's `program_expenses` 800,000 against PP's `total_expenses` 102,250 —
   7.8x its own total, live. 92-1198452 The Intercept published a 40% program ratio
   whose numerator was CN's and denominator PP's. The income statement is now elected
   **whole**.
2. **Election ignored recency.** Chose on field count, so 5 charities published a
   staler statement than the one already held (83-1794093 Hikma Health showed CN's
   **FY2019** over PP's FY2023; also Morocco, BASMAH, Saylani, Rohingya).
3. **Working capital divided across two filings.** Now pairs the balance sheet with
   its OWN expenses and carries the fiscal year it describes.
4. **Balance sheets spliced field-by-field.** Now taken whole or not at all.

### Measured effect (real aggregator over all 169, in memory, nothing written)

```
program_expenses > total_expenses     1 -> 0
income-statement source               134 unchanged; 7 -> propublica; 6 mixed -> charity_navigator
fiscal year corrected                 5  (2019->2023, 2021->2023, 2022->2023 x3)
working capital                       156 unchanged, 5 newly available, 0 withheld,
                                      134 now stamped with the year they describe
discrepancies recorded                9 across 7 charities
```

Working-capital **values barely move** — that was the conservative choice. The
figure was never wrong about the year it came from; it was unlabelled and sat beside
a different year's expenses. Adopting CN's balance sheet instead would have made
pages self-consistent at the cost of publishing 3,694 months of reserves for The
Mecca Center (CN reports $13,034 of annual expenses against $7,038,771 of assets).

### Where the discrepancy is noted

`financial_source_discrepancies` (new field on `CharityMetrics`) rides `metrics_json`
into `keyConcerns`; `source_attribution.working_capital_months` now carries
`fiscal_year`. **Caveat: `keyConcerns` is exported and typed but rendered nowhere in
the website** (`website/types.ts:1144` is its only reference) — so today the note
lands in the data, not in front of a donor. Making it visible is a website change,
not done.

Commits `80434e3` (fix) and `bb2a581` (export tests). Suite **2029 passed**
(was 1984). No LLM spend. Nothing regenerated — the change takes effect only on a
re-run of synthesize onward, which is a pending decision.

---

## Regeneration of the 40 under the canonical rule (2026-07-30 evening)

Dolt rollback point: `83namf2q` ("Snapshot: before canonical-financial-source
regeneration of the 40").

| run | scope | spend | exported | judge-blocked |
|---|---|---|---|---|
| probe | UNRWA only | $0.0900 | 1 | 0 |
| batch40 #3 | synthesize-onward | $3.6895 of $8.00 | 36 | 3 |
| blocked3 | ISGH/MAS/TMWF, `--force-phase extract` | $0.3357 of $2.00 | 3 | 0 |
| batch40 #4 | all 40, `--force-phase extract` | $3.9297 of $10.00 | 32 | 7 |

No run was budget-truncated. Session spend ~$8.05; total ~$24.

**Current state: 33 of the 40 are in the site index (155 total, down from 162).**
All 40 detail files exist; the 7 blocked ones are delisted, carrying earlier
copies from today. 39 of 40 were regenerated today; 75-2352043 is still on
Jul 23 data.

Clean on the canonical rule itself: 0 charities with program_expenses exceeding
total_expenses, and 0 reserves figures that mismatch without the keyConcern
explaining the year.

### The three original blocks: root-caused and fixed (`6bfef6a`, `bdd3fe3`)

1. CN states working capital in YEARS, we read months; the LLM path never
   converted. 6 charities. ISGH's "3.25" is 39.0 months — the judge compared
   ours against theirs and called it a contradiction.
2. Judges had no current date, so age arithmetic ran against whatever year the
   model assumed. MAS Boston was blocked for correctly calling FY2018 data 8
   years old.
3. Candid board sizes came from a split landing inside people's names
   (`{"name": "Ayman", "title": "Khalil"}`). 10 charities; 6 published it and
   took -2 through `board_under_3` for a parser bug.
4. Zakat corroboration checked for "zakat" inside a string the keyword scanner
   itself wrote, so one unverified hit passed on its own say-so, and the
   discovery agent's explicit denial was never consulted. **Texas Muslim
   Women's Foundation was tagged ZAKAT-ELIGIBLE on live data** from a phrase
   that appears zero times in the 182KB of site content we hold; the agent had
   reported it belongs to a different org in Garland, TX. Now corrected.
5. A CN working capital figure larger than the net assets behind it is refused
   (EIN 20-1799252 returned 39 against a ceiling of 3.2).

All three re-ran clean afterwards.

### The 7 that appeared after `--force-phase extract`

Not caused by the fixes above — re-extraction regenerates narratives from fresh
LLM output, and each regeneration surfaces a different subset. That instability
is itself the finding.

The dominant cause is one thing: **the canonical rule adjudicates a same-year
source disagreement and records it, and the judges then re-litigate the raw
divergence because nothing tells them it was settled.**

  45-5637293 Noor Project   PP FY2023 rev 1,759,964 vs CN FY2023 rev 100,000
                            (a round-number LLM fabrication). We correctly
                            published PP whole. `crawl_quality` blocks on
                            "revenue diverges >80% across sources".
  81-3451645 Poligon        PP 32,150 vs CN 142,345, same year. We published
                            PP; `factual` blocks citing CN. NOTE: PP's figures
                            imply spending 4x revenue — worth a look before
                            assuming the filing is right.
  92-3079413 Humaniti       reserves -6.1 (FY2023 basis, disclosed) against the
                            judge's -0.23 recomputed from FY2024 expenses.

Two are judge self-contradictions:

  81-2822877 Yaqeen         the message says "The narrative's claim of 96.0/100
                            is accurate" and is filed severity=error.
  56-2620244 Muslim Academy the judge computed the program ratio as program /
                            REVENUE rather than program / expenses.

Two are genuine narrative-consistency problems (score judge, prose):

  41-2046295 Citizens Fdn   rationale says "clear theory of change"; the score
                            details say DEVELOPING/IMPLICIT.
  86-1226156 Qalam          narrative says large savings imply a lower funding
                            gap while Funding Gap scores 5/5.

### 75-2352043 — the crawl gate, not the charity

`website` row: `success=0`, `last_failure_reason=CAPTCHA_BLOCKED`, **and
`scraped_at=2026-03-07` with 320,485 bytes still stored and parsed into 45
usable fields**. Every other source is fresh. The required-source gate reads the
`success` flag rather than whether we hold usable content, so a blocked
re-fetch discards a charity we have data for — while the non-downgrade design
exists specifically to preserve that content. Changing the gate affects every
charity, so it is not done: it needs a decision.

---

## Source disagreement made non-blocking (2026-07-30 late)

Design change, at the user's direction: *"instead of blocking on disagreement we
should have canonical sources and hierarchy of trustworthiness and then publish
discrepancy. i.e. it becomes nonblocking."*

`src/utils/source_trust.py` states the hierarchy in one place, with the
measurement behind each ranking rather than an assertion. Charity Navigator
leads the income statement (PP supplies 2 of 5 fields for 158 of 169 and is a
year behind on 134 of 168); ProPublica leads the balance sheet (18 of CN's 123
are visibly corrupt against 2 of PP's); same-year ties go to the filing; CN
leads board size; zakat is ordered conservatively.

The governing judge rule, ahead of the eight ad-hoc downgrades that had
accumulated: **a narrative reporting the figure we published is correct by
construction.** Which source supplies a field is settled deterministically
before the judge runs and the disagreement is published, so re-litigating it can
only withhold a page over our own provenance. A claim that does NOT match what
we published still blocks — that is fabrication.

`crawl_quality`'s same-year revenue divergence stopped gating for the same
reason: it withheld EIN 45-5637293 for "likely wrong org" when CN had returned a
round $100,000 against the 990's $1,759,964.

Also fixed: claim_value is null on most findings, with both figures in prose.
Only the number the sentence attributes to the NARRATIVE counts — matching any
number would wave through a fabrication whenever the judge quotes our value as
the correct one. Fiscal-year tokens are stripped first, or "claims FY2025
revenue of $3,145,617" yields 2025.

| step | spend | result |
|---|---|---|
| re-judge the 7 | $0.5300 | 4 cleared, index 155 -> 159 |
| re-judge the 3 | $0.2505 | 2 cleared, index 159 -> 161 |
| regenerate 41-2046295 | $0.1354 | still blocked |

**Final: 39 of 40 in the index (161 total).**

  - 38 regenerated today and passing
  - 75-2352043 in the index but STALE (Jul 23) — blocked at the crawl gate,
    see the section above; the gate reads the `success` flag while 320,485
    bytes from Mar 7 sit parsed and usable in the same row. Needs a decision,
    since changing it affects all 169.
  - 41-2046295 The Citizens Foundation USA — genuinely blocked, and correctly.
    Not a source disagreement: the narrative contradicts our OWN score
    ("a clear theory of change" against a Theory of Change component of
    DEVELOPING 5/7), and after regeneration it instead miscited its evidence
    (citation [1] is a financial citation, attached to three non-financial
    claims). The defect changes shape on every regeneration, which is the
    narrative generator being nondeterministic rather than the gate.

Clean on the canonical rule across all 40: no program_expenses exceeding
total_expenses, no reserves figure mismatching without the keyConcern that
explains its year.

Suite 2091 green. Session spend ~$9. Nothing pushed.

### Models in use (asked 2026-07-30)

| stage | model |
|---|---|
| narratives, website + PDF extraction | `gemini-3-flash-preview` (→ 3.1-pro, 2.5-flash) |
| rich strategic narrative | `gpt-5.2` (→ claude-sonnet-4-5, gemini-3-flash) |
| **all LLM judges — the publication gate** | **`gemini-2.5-flash-lite`** |
| score_judge only | `gemini-2.5-flash` (explicit override) |

The gate deciding what ships runs on the cheapest model in the stack. It is the
same judge that filed "the claim of 96.0/100 is accurate" as an error, read
Charity Navigator's years as months, and anchored its date arithmetic to 2024.

---

## Current-generation Gemini models, tested on the 5 hardest charities

Model IDs live-verified against the models endpoint and each probed with the
judges' real request shape (json_mode + response schema at temperature 0).
Pricing from litellm's live cost map — the copy vendored in the installed
litellm predates all three new models and lists none of them.

  narratives, extraction   gemini-3-flash-preview  -> gemini-3.6-flash    (GA)
  judges                   gemini-2.5-flash-lite   -> gemini-3.5-flash-lite
  score_judge override     gemini-2.5-flash        -> gemini-3.5-flash
  factual escalation       gemini-2.5-flash        -> gemini-3.5-flash
  pro tier                 gemini-3.1-pro-preview  unchanged (newest there is)

Hardest five, chosen by how often they actually blocked since 2026-07-29:

  8x  27-3175543  United Muslim Relief          GIK ratio; dollars vs percentage
  5x  20-1799252  MAS Boston Society            date anchor; zakat restatement
  4x  41-2046295  The Citizens Foundation USA   narrative vs our own score
  4x  23-7065716  Islamic Society of Gtr Houston years-vs-months; board misparse
  3x  45-5637293  The Noor Project              source divergence (CN's $100,000)

**Both passes: 0 errors, 5 of 5 exported.** Including Citizens Foundation, which
had survived every previous fix.

Run twice against identical data to test stability:

| EIN | pass 1 err/warn | pass 2 err/warn | per-judge identical |
|---|---|---|---|
| 27-3175543 | 0 / 2 | 0 / 2 | yes |
| 20-1799252 | 0 / 0 | 0 / 3 | no |
| 41-2046295 | 0 / 1 | 0 / 0 | no |
| 23-7065716 | 0 / 3 | 0 / 5 | no |
| 45-5637293 | 0 / 3 | 0 / 3 | yes |

**Read this carefully: the model upgrade did NOT fix nondeterminism.** The
warning sets still move run to run on 3 of 5 — the model finds different things
each roll, exactly as before. What is now stable is the GATE: errors are 0 on
both passes everywhere, because whether a finding blocks is decided by
deterministic rules and the trust hierarchy rather than left to the model.

That attribution matters for the cost decision below: the stability was bought
by the deterministic classification, not by the newer model. Separating the two
cleanly would need an A/B re-judging the same five on 2.5-flash-lite; not done.

Cost: **$0.2277 per charity**, against ~$0.09 before — 2.5x, in line with the
pricing. Judging is 96.7% of it. Extrapolated: ~$9 for the 40, ~$34 for all 150+.

**All 40 of batch40 are in the index (162 total).** 39 regenerated today;
75-2352043 remains in the index but stale (Jul 23), still blocked at the crawl
gate pending the decision recorded above.

Session spend ~$11. Suite 2093 green. Nothing pushed.

---

## gemini-3.1-flash-lite trialled for the judge, and rejected

Cheaper per token — $0.25/$1.50 against 3.5-flash-lite's $0.30/$2.50, so 17%
less input and 40% less output. It is nonetheless worse on both axes.

Same five charities, judge-only, identical data:

| judge model | pass 1 | pass 2 | cost/pass |
|---|---|---|---|
| gemini-3.5-flash-lite | 0 errors, 5/5 exported | 0 errors, 5/5 | $0.68 |
| gemini-3.1-flash-lite | **1 blocked** | **1 blocked** | $1.05, $1.39 |
| gemini-3.5-flash-lite (confirm) | 0 errors, 5/5 | — | $0.81 |

**Cheaper per token, more expensive per charity.** 3.1-flash-lite is markedly
more verbose — roughly twice the warnings (ISGH 8-10 against 3-5, MAS Boston
5-6 against 0-3) — and output tokens plus the extra consensus work more than
erase the lower rate.

The block reproduced on both passes, so it is not roll variance. It objects to
United Muslim Relief's cost per beneficiary:

    "The narrative claims a cost per beneficiary of $7.44, but this figure is
     not found in the provided source data."

Which is literally true and beside the point: $7.44 is DERIVED, not copied from
a source, as is every ratio we compute. Worth noting as a real gap — the
governing published-value rule covers fields in the trust hierarchy, and derived
metrics like cost_per_beneficiary sit outside it, so a sufficiently literal
judge can still block on one. Not patched here, because tuning the rules to
accommodate the weaker model is the wrong direction when the stronger one is
also cheaper in practice.

Reverted to gemini-3.5-flash-lite, with 3.1-flash-lite kept as first fallback.
Confirmation pass after reverting: 0 errors, 5 of 5, index back to 162.

Suite 2093 green.

---

# BATCH 80 — the next 40 charities (2026-07-31)

## Selection

86 charities remained after batch40, once the HARD DATA section and the
HIDE:TRUE benchmark orgs (American Red Cross, GiveDirectly, ACLU and the rest —
hidden from the curated list on purpose) are removed.

Four were missing from the index or currently blocked, so all four are in;
excluding them would flatter the result. The other 36 are stratified across
sections rather than taken in source order — source order alone would have made
the batch 31/40 international relief and 2/40 mosques, which says nothing about
the 33 mosque-and-community orgs still queued behind it, the largest remaining
group and the one whose small filers have the thinnest source coverage.

Final spread: 16 mosque/community, 14 relief, 4 education, 2 advocacy,
2 health, 2 active-testing. Reproducible via `data-pipeline/select_batch80.py`
— "blocked" means an export_exclusions row with nothing successful after it,
since that table is append-only and a bare row proves nothing.

Must-include four: 46-3973114 International Aid Charity, 13-3626299 Imran Khan
Cancer Appeal USA, 56-2392452 Rebuilding Alliance, 83-0919620 Humanity for
Relief and Development.

## What the first 5 turned up: the IRS was never readable

`b80_05` run 1: 4 of 5. Zakat Foundation of America (36-4476244) failed its
crawl — "Failed to download any XML filings", which reads like the IRS has
nothing for it. The IRS has three filings for it. Three separate defects, each
reporting a filing we could not ADDRESS as a filing that does not EXIST:

| # | defect | evidence |
|---|---|---|
| 1 | **Overflow volumes.** The index names one bundle per filing; when a batch outgrows one zip the IRS publishes lettered volumes and keeps naming only the first. | index_2026 assigns 168,344 rows to `2026_TEOS_XML_05A`, which holds 84,172 members and stops at object_id 202621329349203217. `05B` holds the next 84,172, starts at 202621329349203222, and is named by **no index row at all**. 12 arbitrary 05A rows sampled: 5 present. |
| 2 | **Case.** | index_2024 writes `2024_TEOS_XML_05a`; the server has `05A.zip` and 302s the lowercase to irs.gov/404. zipfile then said "File is not a zip file" — corruption, for a wrong URL. |
| 3 | **Deflate64.** Python's zipfile will not decompress method 9. | Every member of 2026_TEOS_XML_05A/05B and 2025_TEOS_XML_05B is method 9; batches 01–04 and all of 2024 are ordinary deflate. It is the oversized batch that gets packed past deflate's limits — the same size that forces the split. |

Plus a fourth, in the filing picker: it kept one filing per tax period by first
arrival, so the CSV's row order chose the return. Orgs that file a 990-T file
it for the same period as the real 990, and index_2025 and index_2024 list the
990-T first — so two of this charity's three slots went to returns carrying no
Schedule I. That is how a run logs "Extracted 0 domestic + 0 foreign grants".

**Scale: batch 05 carries 168,344 of index_2026's 353,651 rows — 48% of the
submission year was silently unreadable**, and every charity among them quietly
kept whatever older filing was already cached. Fix verified against the live
IRS, not fixtures: 36-4476244 went from zero readable filings to three.

Added dependency `inflate64` (wheels available; `zipfile-deflate64` fails to
build against the current toolchain).

## The backoff outlived the fix

Run 2 still failed the same charity: "within backoff window (2.7h remaining)".
The failure from run 1 had armed a 4-hour retry backoff, and a code fix cannot
invalidate that record — every charity a broken collector touched keeps serving
its sentence. `--force-phase crawl` now clears the window and the retry count,
deliberately BELOW the terminal check so CAPTCHA and not-found stay skipped.
**EIN 75-2352043 stays frozen, by test.**

**Separate defect found there and NOT fixed** (not blocking, and it changes
crawl politeness for all 169): the backoff clock is wrong. `last_attempt_at` is
written by the Dolt server as CURRENT_TIMESTAMP in the SERVER's zone (PDT),
read back naive, then compared against `datetime.now(None)` — the HOST's clock.
A 23-minute-old failure measured as 1h23m, and the 4h window reported 2.7h left
instead of 3.6h. Both age helpers do `datetime.now(dt.tzinfo) - dt` with
`dt.tzinfo` always None, so freshness.py's "Tz-aware age" docstring describes an
intent the code does not deliver. It errs toward retrying too SOON, which is why
it never surfaced as a failure; from a UTC host the gap would be 7h and the 1h
and 4h windows would be defeated outright.

## The primary source is ahead of both mirrors

With the XML readable, it turned out to be newer than what we publish. For
36-4476244 the two mirrors agreed with each other to the dollar and were both
a year behind the filing they are copies of:

| source | fiscal year | revenue |
|---|---|---|
| ProPublica | 2023 | $29,498,054 |
| Charity Navigator | 2023 | $29,498,054 |
| **IRS e-file (primary)** | **2024** | **$34,923,926** |

Measured across the 40 from the index CSVs (free): **the filing is ahead on 6,
level on 32**. The gap appears where a fiscal year ends mid-calendar.

User approved adding it before running the 40, so the 6 are regenerated once
rather than twice. Three parts:

- **Parse.** The 990 carries the whole statement in one group that reconciles
  to the dollar (34,365,532 + 1,198,626 + 1,253,842 = 36,818,000). We read two
  fields. `program_expenses` was looked up at `CYProgramServiceExpenseAmt` —
  not a tag in this schema, so None for every charity, a path that never
  matched anything. Admin/fundraising XPaths are scoped to
  `TotalFunctionalExpensesGrp` on purpose: every Part IX line repeats those tag
  names and an unscoped search returns the first row, which would publish
  $38,852 of legal fees as an org's entire administrative expense.
- **Elect.** Supersedes only when strictly newer AND at least as complete. A
  990-EZ has no Part IX; taking it whole would trade a stale complete statement
  for a current mutilated one and delete the split that
  `program_expense_ratio` and Financial Health are computed from.
- **Ratio.** Found while verifying: the aggregator's values overwrite the
  financial columns, but that list omits `program_expense_ratio`, which kept
  Charity Navigator's precomputed quotient. First run published 34,365,532 over
  36,818,000 (0.9334) beside a ratio of **0.9159** from another year and
  another source — the numerator-over-a-foreign-denominator defect the
  canonical-source work exists to prevent, arriving already divided.

`b80_05` run 3: **5 of 5**, FINISHED at $3.06 of $5.00.

## Cost

$0.60/charity against batch40's $0.23 — judging is 97.9% of it, and every
charity here needs full regeneration (`Code changed`). Estimated ~$24 for the
40 against an earlier ~$10, so 2.4x; **checked in with the user before
proceeding** per the standing rule, approved at a $30 cap.

## Run log

| run | scope | result |
|---|---|---|
| b80_05 #1 | 5, force crawl+extract | 4/5 — IRS bundle failure |
| b80_05 #2 | 5, force crawl+extract | 4/5 — stale backoff |
| b80_05 #3 | 5, force crawl+extract | **5/5**, $3.06 of $5.00, FINISHED |
| 36-4476244 | single, IRS election | FY2024 published, ratio consistent |
| batch80 #1 | 40, force crawl+extract | killed at ~29/40 by the 10-min tool cap, not by budget |
| batch80 #2 | 40, resumed on cache | in progress |
