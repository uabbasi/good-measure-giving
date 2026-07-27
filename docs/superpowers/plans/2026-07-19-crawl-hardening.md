# Crawl Hardening (Spec B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A robust periodic fleet refresh — transient errors don't blacklist sites, the crawler doesn't self-block at scale, stale/failed sites get re-attempted, client-rendered pages are recovered, and an interrupted run leaves a clean commit boundary.

**Architecture:** Nine surgical changes at investigation-confirmed locations across `web_collector.py`, `orchestrator.py`, `crawl.py`, `streaming_runner.py`, `constants.py`, `dolt_client.py`. Spec: `docs/superpowers/specs/2026-07-19-crawl-hardening-design.md`.

**Tech Stack:** Python 3.13, `uv`, httpx + curl_cffi async crawl, DoltDB, pytest.

**Verbatim current-code recon (read the relevant file for your task's current code):**
- `/private/tmp/claude-501/-Users-uabbasi-dev-good-measure-giving--claude-worktrees-pipeline-review-v53-prep/9957b786-2d2b-4d84-bd51-b3872b26c866/scratchpad/recon-webcol.md` (components 1,2,3,8)
- `.../scratchpad/recon-orch.md` (component 4 orchestrator force-override — paste-ready)
- `.../scratchpad/recon-constCrawl.md` (constants + crawl.py selector/report)
- `.../scratchpad/recon-streamDolt.md` (streaming_runner + dolt_client + test patterns)

## Global Constraints
- **Match existing conventions:** collector logging is guarded `if self.logger:`; orchestrator uses `self.logger.debug/info/warning`; `typing` `Optional/Dict/Tuple` in web_collector/orchestrator, modern `str | None` in streaming_runner; constants are `UPPER_SNAKE` with inline `#` comments.
- **Tests are pure-function/unit style** (`tests/test_crawl_politeness.py`): bypass `__init__` via `Cls.__new__(Cls)`, hand-set only touched attrs, fakes via `unittest.mock.MagicMock`, assert on call recording. No live DB/network in unit tests. Run from `data-pipeline/`: `uv run pytest`.
- **The write-safety layer already protects the DB** — a bad crawl preserves last-good. Do NOT weaken it.
- **`form990_grants` stays a required source; the non-downgrade guard stays intact.**
- Source keys are lowercase (`website`, `propublica`, …) matching `raw_scraped_data.source` + `SOURCE_TTL_DAYS`.

---

### Task 1: 429/503 → transient (the poison fix) — LAND FIRST

**Files:** Modify `data-pipeline/src/collectors/web_collector.py:1055-1075`. Test: `data-pipeline/tests/test_crawl_politeness.py`.

**Why:** A transient HTTP 429 is written as `CAPTCHA_BLOCKED: HTTP 429`; the substring `captcha_blocked` matches `TERMINAL_FAILURE_MARKERS`, so `_should_skip_failed_source` skips the site for **180 days**. The fix is at the classification site: emit `RATE_LIMITED` (which matches no terminal marker → graduated `RETRY_BACKOFF_HOURS` backoff) for 429/503, keep 202/403 as CAPTCHA. Do NOT touch `TERMINAL_FAILURE_MARKERS` (429/503 are not in it; the *string* is the bug).

**Interfaces:** Produces: no new symbols; changes the error string a 429/503 fetch returns.

- [ ] **Step 1: Write the failing test.** Append to `test_crawl_politeness.py` a class testing `classify_failure` + the string contract:
```python
class TestRateLimitNotTerminal:
    def test_rate_limited_string_is_transient(self):
        from src.collectors.orchestrator import classify_failure
        # 429/503 must NOT classify as terminal (no 180d skip)
        assert classify_failure("RATE_LIMITED: HTTP 429") is None
        assert classify_failure("RATE_LIMITED: HTTP 503") is None
        # genuine captcha stays terminal
        assert classify_failure("CAPTCHA_BLOCKED: challenge page (HTTP 200)") == "captcha_blocked"
```
Then, if feasible with the existing async-fetch test harness, add a test that a 429 response yields a `RATE_LIMITED`-prefixed error (see recon-webcol.md for the `_fetch_url_async` seam; if the async path is impractical to unit-test in isolation, the `classify_failure` contract above is the load-bearing assertion — note that in the report).

- [ ] **Step 2: Run test to verify it fails/passes appropriately.** `cd data-pipeline && uv run pytest tests/test_crawl_politeness.py::TestRateLimitNotTerminal -v` — the classify_failure test passes already (RATE_LIMITED isn't a marker); it locks the contract. The behavior change is in Step 3.

- [ ] **Step 3: Implement.** In `web_collector.py` replace the `if response.status_code in (202, 403, 429, 503):` block (lines ~1059-1075) so 429/503 emit `RATE_LIMITED` and skip the cf-ray/header sniff (cf-ray is on ALL Cloudflare traffic and would re-poison), while 202/403 keep the existing header+body challenge sniff:
```python
                    error_msg = f"HTTP {response.status_code}"
                    is_captcha = False
                    if response.status_code in (429, 503):
                        # Transient rate-limit / overload → graduated backoff, NOT a
                        # 180d terminal block. Still worth a curl_cffi fingerprint retry,
                        # but never emit the CAPTCHA_BLOCKED string (which is terminal).
                        is_captcha = True
                        error_msg = f"RATE_LIMITED: HTTP {response.status_code}"
                    elif response.status_code in (202, 403):
                        is_captcha = True
                        error_msg = f"CAPTCHA_BLOCKED: HTTP {response.status_code}"
                        captcha_headers = ["sg-captcha", "cf-ray", "x-captcha"]
                        for header in captcha_headers:
                            if header in [h.lower() for h in response.headers.keys()]:
                                error_msg = f"CAPTCHA_BLOCKED: {header} (HTTP {response.status_code})"
                                break
                        body_lower = (
                            response.text.lower() if len(response.text) < 5000 else response.text[:5000].lower()
                        )
                        if "captcha" in body_lower or "challenge" in body_lower or "verify you are human" in body_lower:
                            error_msg = f"CAPTCHA_BLOCKED: challenge page (HTTP {response.status_code})"
```
(The `if is_captcha and HAS_CURL_CFFI:` curl_cffi block and the bare-404 block below it are unchanged — a 429/503 still attempts the impersonation bypass.)

- [ ] **Step 4: Run tests.** `cd data-pipeline && uv run pytest tests/test_crawl_politeness.py -v` — green.
- [ ] **Step 5: Commit.** `git add -A && git commit -m "fix(crawl): 429/503 are transient rate-limits, not 180d terminal blocks (poison fix)"`

---

### Task 2: Per-source force override in the orchestrator

**Files:** Modify `data-pipeline/src/collectors/orchestrator.py` (`fetch_charity_data` sig + the two non-website gates + the two website gates). Test: `test_crawl_politeness.py`.

**Full paste-ready current code + exact edit points: read `.../scratchpad/recon-orch.md` (§"Summary of exact edit points").**

**Interfaces:** Produces: `fetch_charity_data(self, ein, website_url=None, charity_name=None, force_sources: Optional[set[str]] = None)` — when a source name is in `force_sources`, BOTH `_is_data_fresh` and `_should_skip_failed_source` are bypassed for it (other sources' gating unchanged).

- [ ] **Step 1: Write the failing test.** Add a test using the `_make_orchestrator()` `__new__`+MagicMock pattern (recon-streamDolt.md shows it): set `raw_data_repo.get_by_source` to return a FRESH successful website row (would normally skip) and assert that with `force_sources={"website"}` the website `collect_multi_page` IS called, and without it is NOT. Also assert a terminal-failed website row (`success=False`, `last_failure_reason="CAPTCHA_BLOCKED..."`, recent) is still crawled when forced.
- [ ] **Step 2: Run to verify it fails.** `uv run pytest tests/test_crawl_politeness.py -k force -v` → FAIL (param doesn't exist).
- [ ] **Step 3: Implement** per recon-orch.md: add the param + `force_sources = set(force_sources or ())` after EIN validation; guard the non-website freshness gate with `source_name not in force_sources` (line ~742); short-circuit the non-website failure gate when `source_name in force_sources` (line ~750); in the website branch compute `force_site = "website" in force_sources` and rewrite the two conditions to `(False, "") if force_site else self._should_skip_failed_source(...)` and `elif force_site or not self._is_data_fresh(...)`.
- [ ] **Step 4: Run tests.** green.
- [ ] **Step 5: Commit.** `git commit -m "feat(crawl): per-source force override bypasses freshness + failure-skip gates"`

---

### Task 3: `--refresh-stale` website selector + `--force-sources` in crawl.py

**Files:** Modify `data-pipeline/crawl.py`. Test: `data-pipeline/tests/test_refresh_stale.py` (new).

**Full current code: read `.../scratchpad/recon-constCrawl.md` (FILE 2 + "Supporting code").**

**Interfaces:** Consumes Task 2's `force_sources`. Produces:
- CLI: `--refresh-stale` (in the mutually-exclusive group with `--charities`/`--ein`) + `--older-than N` (int, optional).
- A pure selector `select_stale_website_eins(charity_repo, raw_repo, older_than_days) -> list[dict]` (`[{"name","ein","website"}]`) picking EINs whose `website` raw row is **missing OR success=0 OR `scraped_at` older than `older_than_days` (default `SOURCE_TTL_DAYS["website"]`=30)**, mirroring `_is_data_fresh`.
- `--refresh-stale` runs implies `force_sources={"website"}` threaded to the worker's `fetch_charity_data` call, and bypasses the `PhaseCacheRepository` gate.

- [ ] **Step 1: Write the failing test** (`test_refresh_stale.py`, pure — fake repos): given charity rows + website raw rows in states {missing, success=0, stale-40d, fresh-5d}, `select_stale_website_eins` returns exactly the missing+failed+stale EINs, not the fresh one; `--older-than 7` widens selection.
- [ ] **Step 2: Run to verify it fails.** ImportError.
- [ ] **Step 3: Implement:** add `from src.db.repository import RawDataRepository, CharityRepository` (currently absent, recon-constCrawl.md); write `select_stale_website_eins` (loop `CharityRepository.get_all()` → `raw_repo.get_by_source(ein,"website")`, apply the staleness probe reusing the `_is_data_fresh` age math); add the argparse flags (into the mutually-exclusive group); add the third selection branch (both the early guard ~168-178 and the late load ~202-213); force-bypass the phase-cache gate for refresh-stale; thread `force_sources={"website"}` through the `crawl.py:47` worker signature + the `fetch_charity_data` call.
- [ ] **Step 4: Run tests.** green.
- [ ] **Step 5: Commit.** `git commit -m "feat(crawl): --refresh-stale website selector + --older-than (re-crawls stale/failed/missing)"`

---

### Task 4: Per-source freshness report at run end

**Files:** Modify `data-pipeline/crawl.py` (after the blocked-sites block, ~line 347). Test: `test_refresh_stale.py`.

**Interfaces:** Produces `crawl_freshness_summary(raw_repo, eins) -> dict[str, dict]` → per source (the 6 lowercase keys): `{fresh, stale, failed, missing}` counts, plus the failed-website EIN list with classified reason. Printed in `crawl.py`'s summary (glyph/banner style per recon-constCrawl.md convention notes).

- [ ] **Step 1: Write the failing test:** given a set of raw rows across sources/states, `crawl_freshness_summary` returns the correct per-source counts and lists failed website EINs.
- [ ] **Step 2: Run to verify it fails.** ImportError.
- [ ] **Step 3: Implement** the pure summary fn + wire a print block after the blocked-sites report (before the frozen-sources note). Reuse `SOURCE_TTL_DAYS` + the `_is_data_fresh` age math + `classify_failure` for the reason.
- [ ] **Step 4: Run tests.** green.
- [ ] **Step 5: Commit.** `git commit -m "feat(crawl): per-source freshness report at run end (fresh/stale/failed/missing)"`

---

### Task 5: Source-granular crawl-cache freshness

**Files:** Modify `data-pipeline/streaming_runner.py` (`_phase_artifacts_exist` crawl branch, lines 249-254). Test: `data-pipeline/tests/test_streaming_freshness.py` (new).

**Why:** The crawl branch passes on `any(row.get('success'))`, so a fresh ProPublica row masks a months-stale website and the crawl phase skips (website never re-attempted). Make the crawl artifact check website-aware: a website row that is missing / `success=0` past backoff / `scraped_at` older than `SOURCE_TTL_DAYS['website']` counts as a missing artifact → phase re-runs.

**Interfaces:** Changes `_phase_artifacts_exist(...)` crawl branch only. Extract the website-staleness test into a small pure helper (e.g. `_website_needs_recrawl(rows) -> bool`) so it's unit-testable without a DB.

- [ ] **Step 1: Write the failing test** (`test_streaming_freshness.py`, pure): rows with fresh-propublica + stale-website → `_website_needs_recrawl` True (→ artifacts "missing"); fresh-propublica + fresh-website → False.
- [ ] **Step 2: Run to verify it fails.** ImportError/assertion.
- [ ] **Step 3: Implement** the helper + call it in the crawl branch: keep the existing `has_successful_raw` requirement, but ALSO return `(False, "website stale/failed — re-crawl")`... wait: `_phase_artifacts_exist` returning `(False, reason)` means "artifacts exist, skip". To FORCE a re-run, it must return `(False, "")` from the wrapper's perspective? Re-read recon-streamDolt.md `should_run_phase_with_artifact_validation`: `artifacts_ok True → return (False, reason)` (skip); `artifacts_ok False → delete cache + return (True, ...)` (run). So make `_phase_artifacts_exist` return `(False, "website stale/failed")` when the website needs re-crawl, so the wrapper deletes the cache and re-runs. Implement accordingly.
- [ ] **Step 4: Run tests.** green (+ `uv run pytest tests/ -k phase_artifacts` if any existing coverage).
- [ ] **Step 5: Commit.** `git commit -m "feat(crawl): source-granular crawl freshness — stale website re-crawls instead of being masked"`

---

### Task 6: Unconditional final Dolt commit

**Files:** Modify `data-pipeline/streaming_runner.py` (final commit block, lines 1833-1846). Test: `test_streaming_freshness.py` or a focused new test.

**Why:** The final commit is gated on `success_count > 0`; an all-failed/budget-capped run leaves crawl/extract writes uncommitted and the next run stamps `source_commit=NULL`. Commit any dirty `STREAMING_RUN_TABLES` unconditionally (labeled "partial run" when `success_count==0`); the export publication guard elsewhere is unchanged. `dolt.commit` already no-ops on a clean working set (returns None), so an unconditional call is safe.

**Interfaces:** No new symbols; the `if success_count > 0:` guard around the final `dolt.commit(...)` is removed (message varies by success_count).

- [ ] **Step 1: Write the failing test:** hard to unit-test the runner directly (no streaming tests exist — recon-streamDolt.md). Extract the commit-message/label decision into a pure helper `final_commit_message(success_count, total, total_cost, checkpoint_count) -> str` and test it returns a "partial run" label when `success_count==0`. Assert the runner calls `dolt.commit` regardless of success_count (via a small refactor that's unit-checkable, or document this as an integration-verified step in the report).
- [ ] **Step 2: Run to verify it fails.** ImportError.
- [ ] **Step 3: Implement:** remove the `if success_count > 0:` gate around the final commit; build the message via the helper; keep the tag logic gated as-is if tagging a failed run is undesirable (tag only when success_count>0).
- [ ] **Step 4: Run tests.** green.
- [ ] **Step 5: Commit.** `git commit -m "fix(crawl): commit the working set unconditionally at run end (no orphaned partial writes)"`

---

### Task 7: Global QPS ceiling (~5 concurrent)

**Files:** Modify `data-pipeline/src/constants.py` (+1 constant) and `data-pipeline/src/collectors/web_collector.py` (shared limiter). Test: `test_crawl_politeness.py`.

**Full current code: read `.../scratchpad/recon-webcol.md` component (2).**

**Why:** `_fetch_url_async` enforces only a per-domain `Semaphore(2)`, never a process-wide bound; with 20 workers that's ~40 unbounded sockets from one IP — the 429-earning condition. Add a process-wide async semaphore acquired by every outbound website request.

**Interfaces:** Produces `CRAWL_GLOBAL_CONCURRENCY = 5` in constants.py. A single shared `asyncio.Semaphore(CRAWL_GLOBAL_CONCURRENCY)` on the collector, acquired inside `_fetch_url_async` (in addition to the per-domain semaphore). Because httpx crawls run under `asyncio.run` per charity across threads, the ceiling is per-event-loop; document that it bounds one charity's fan-out — if a truly cross-charity cap is needed, note it (a process-global via a module-level limiter keyed by loop) as a follow-up. For v1 the per-charity ceiling + reduced worker count is the conservative posture; ALSO lower the streaming default `--workers` from 20 toward the conservative target (coordinate with the per-domain cap) — set `--workers` default to 6 (constants or argparse) so fleet fan-out stays ~conservative.

- [ ] **Step 1: Write the failing test:** assert `CRAWL_GLOBAL_CONCURRENCY` exists and is small (<=6); a unit test that the collector acquires the shared semaphore (inject a tracking semaphore, drive N concurrent `_fetch_url_async` stubs, assert max-in-flight <= ceiling). Follow the `__new__`+MagicMock collector pattern.
- [ ] **Step 2: Run to verify it fails.** ImportError.
- [ ] **Step 3: Implement:** add the constant; create the shared semaphore on the collector (lazily, per running loop, to avoid binding a semaphore to the wrong loop); `async with self._global_semaphore:` around the request in `_fetch_url_async`; lower `--workers` default to 6.
- [ ] **Step 4: Run tests.** green.
- [ ] **Step 5: Commit.** `git commit -m "feat(crawl): global QPS ceiling (~5) + conservative worker default (fleet politeness)"`

---

### Task 8: Honor Crawl-delay as a real inter-request delay

**Files:** Modify `data-pipeline/src/collectors/web_collector.py` (~2369-2373 and the fetch path). Test: `test_crawl_politeness.py`.

**Why:** `crawl_delay` is read but only toggles a `polite_concurrency` number the inner `Semaphore(2)` overrides — the advertised delay is never applied. Apply it as an actual per-host inter-request sleep.

**Interfaces:** When robots advertises a Crawl-delay for a host, `_fetch_url_async` sleeps at least that long between requests to that host (in addition to jitter).

- [ ] **Step 1: Write the failing test:** extend the existing `test_crawl_delay_lowers_concurrency` pattern — assert that when `get_crawl_delay` returns a value, an inter-request delay of at least that value is applied for that host (drive two requests, assert the recorded gap; use a monkeypatched sleep recorder rather than real time).
- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3: Implement:** thread the host's crawl_delay into `_fetch_url_async` and enforce a per-host last-request timestamp → sleep `max(0, crawl_delay - since_last)` before the request. Keep the existing jitter.
- [ ] **Step 4: Run tests.** green.
- [ ] **Step 5: Commit.** `git commit -m "feat(crawl): honor robots Crawl-delay as a real per-host inter-request delay"`

---

### Task 9: Wire Playwright into the async production path (SPA recovery)

**Files:** Modify `data-pipeline/src/collectors/web_collector.py` (hoist js flag ~2896-2920; escalate in `collect_multi_page`/async crawlers ~2377-2394). Test: `test_crawl_politeness.py`.

**Full current code: read `.../scratchpad/recon-webcol.md` component (4).**

**Why:** `collect_multi_page` only calls the async crawlers; the `PlaywrightRenderer` is invoked solely from the sync crawlers (dead in production), so client-rendered SPAs return `{}` → "no data found". Two of the 4 failing sites are this class.

**Interfaces:** (a) hoist the `js_rendering_needed` computation out of the `if use_llm and self.llm_extractor:` block so the no-LLM async path can flag a page. (b) When the async crawl yields empty/thin AND pages were flagged js-needed, escalate those URLs through `PlaywrightRenderer` once, then re-extract.

- [ ] **Step 1: Write the failing test:** a collector with a fake async crawl returning `{}` + a js-needed flag set, and a MagicMock `PlaywrightRenderer` returning HTML → assert Playwright is invoked and content is extracted; and that the js-needed flag is now set on the no-LLM path.
- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3: Implement** the hoist + the escalation (read recon-webcol.md component (4) for the exact `collect_multi_page`/async-crawler/PlaywrightRenderer interfaces). Escalate at most once per crawl; guard on `HAS_PLAYWRIGHT`/renderer availability.
- [ ] **Step 4: Run tests.** green.
- [ ] **Step 5: Commit.** `git commit -m "feat(crawl): wire Playwright SPA escalation into the async production path"`

---

## Self-Review
**Spec coverage:** Task 1↔component 1; Tasks 2-3↔component 4; Task 4↔component 6; Task 5↔component 5; Task 6↔component 7; Task 7↔component 2; Task 8↔component 3; Task 9↔component 8. All eight components covered.
**Ordering:** Task 1 first (poison fix, before any re-crawl). Tasks 2-5 build the refresh lever + freshness correctness. Tasks 6-8 harden the fleet run. Task 9 recovers SPAs.
**Placeholder scan:** the trickiest current-code lives in the recon files (referenced per task); new code + tests are inline. Tasks 6/7 note where a pure helper extraction enables unit testing vs integration verification (streaming_runner has no existing unit tests).
**After all tasks:** re-crawl the 20's websites via `crawl.py --sources website --refresh-stale --charities <the 20>`, confirm the Task-4 freshness report shows them fresh, then run the fleet.
