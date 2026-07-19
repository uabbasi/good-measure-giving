# Crawl Hardening (Spec B) — Design

**Status:** Approved-scope design (brainstorm 2026-07-19). Spec B of the two-part
crawl-reliability effort; Spec A (non-destructive synthesize) is implemented on this
branch and makes a bad crawl non-corrupting, so hardening can iterate safely.

**Branch:** `worktree-pipeline-review-v53-prep`.

**Goal:** A periodic fleet refresh (169 charities) that is robust — doesn't blacklist
sites on transient errors, doesn't self-block at scale, re-attempts stale/failed
sites, recovers client-rendered pages, and never leaves a half-committed run.

**Scope decisions (locked with user, 2026-07-19):**
- Fleet concurrency: **conservative (~4–6 concurrent outbound from one IP)** → a global
  QPS ceiling is IN scope.
- Proxy / residential-IP support: **non-goal for v1**.
- SPA / Playwright rendering: **wire it now**.
- Interrupt resilience: **re-run / phase-cache self-heals** — no SIGINT handler; but the
  final-commit fix (component 7) is in.

---

## Motivation

Live state (2026-07-19): all non-website sources were re-crawled fleet-wide yesterday,
but the fleet run used `--skip website`, so 149 website sources are stale (back to
February) and 10 are failed. The per-request fetch path is already resilient
(curl_cffi impersonation, challenge detection, per-host throttle) after
`cee8ce5..cc37669`. The weak axes are **failure classification, freshness/selection,
run transactionality, and one dead code path** — not the fetch itself. An 8-agent code
investigation confirmed the root causes below against the live DB.

**The critical defect (must fix before any fleet run):** a transient HTTP 429 is written
as `CAPTCHA_BLOCKED: HTTP 429` (`web_collector.py:1059-1062`); its substring matches
`TERMINAL_FAILURE_MARKERS` (`constants.py:64`), so `_should_skip_failed_source`
(`orchestrator.py:436-437`) skips that website for **180 days**. At fleet scale you earn
429s, and each one blacklists a charity's website for 6 months. Crawling the fleet today
would poison sites as it runs.

The 10 current failures (confirmed): **6 = CAPTCHA-202 from 2026-03-09**, terminal-frozen
180d so the post-March impersonation hardening is never re-tried against them (unblock
~Sept 5); **4 = "no data found"** — 2 are client-rendered SPAs that hit dead Playwright
code, 2 are stale.

---

## Components

Each is a targeted change at an investigation-confirmed location. Effort: S/M.

### 1. Reclassify 429/503 as transient (S) — THE poison fix, first
`web_collector.py:1059-1062` currently lumps `202/403/429/503` into `is_captcha` →
`CAPTCHA_BLOCKED: HTTP <code>`. Emit `RATE_LIMITED: HTTP 429` (and `HTTP 503`) instead,
and keep those two out of `TERMINAL_FAILURE_MARKERS` (`constants.py:64`) so they take the
graduated transient path (`RETRY_BACKOFF_HOURS {1:1,2:4,3:24}`). Keep genuine
CAPTCHA/challenge (200-with-challenge, 202 Cloudflare) terminal. This is the one change
that must land before re-crawling anything.

### 2. Global QPS ceiling (~4–6 concurrent) (M)
`_fetch_url_async` (`web_collector.py:1004-1104`) enforces only a per-domain
`Semaphore(2)` + jitter and never consults a process-wide limiter; with
`ThreadPoolExecutor(max_workers=20)` (`streaming_runner.py:1566`) that is ~40 unbounded
outbound sockets from one IP. Add a **process-wide async semaphore / QPS cap** (config
default **5**, in `constants.py`) that every outbound website request acquires, so the
conservative posture is actually enforced regardless of worker count. Per-domain
`Semaphore(2)` stays as the inner bound.

### 3. Honor Crawl-delay as a real delay (S)
`web_collector.py:2369-2373` reads `robots Crawl-delay` but only toggles a
`polite_concurrency` number that the inner `Semaphore(2)` overrides — the delay is never
applied. Apply the advertised delay as an actual inter-request sleep for that host.
Reinforces the polite posture.

### 4. Targeted stale/failed-website selector + per-source force override (M) — the operational lever
The entrypoint the whole periodic-refresh goal depends on. `crawl.py --sources website
--refresh-stale [--older-than N]` selects EINs whose website row is **missing OR
success=0 OR `scraped_at` > N days** (default N = `SOURCE_TTL_DAYS['website']` = 30) and
re-crawls **only** the website source. Drive it with a **per-source force override**
threaded through `orchestrator.fetch_charity_data(..., force_sources={'website'})` that
bypasses **both** `_is_data_fresh` (`orchestrator.py:367-399`) **and**
`_should_skip_failed_source` (`orchestrator.py:401-485`) for the named source (call sites
`orchestrator.py:742, 823, 827`). One lever re-attempts the 149 stale + 6 frozen CAPTCHAs
(bypassing the 180d TTL now that they'd be re-tried with post-March hardening) + 4
no-data — and nothing else. Subsumes a separate `--retry-terminal` flag.

### 5. Source-granular crawl-cache freshness (S)
`_phase_artifacts_exist` for the crawl phase passes on `any(row.get('success'))`
(`streaming_runner.py:249-254`), so a fresh ProPublica row satisfies "crawl artifacts
exist" and the whole crawl phase skips — the website branch (`orchestrator.py:822`) is
never reached even when the website is months stale. Make the crawl artifact check
**website-aware**: a website that is missing / `success=0` past its backoff / `scraped_at`
> `SOURCE_TTL_DAYS['website']` counts as a missing artifact, so the normal streaming path
stops masking stale websites going forward.

### 6. Per-source freshness report at run end (S)
Run-end output only surfaces CAPTCHA `blocked_sites` (`crawl.py:342-347`); nothing prints
staleness, which is why 149-stale went unnoticed. Add a per-source summary: for each
source, count fresh / stale (>TTL) / failed, and list the failed website EINs with their
classified reason. Print in `crawl.py` and the streaming run summary.

### 7. Unconditional final Dolt commit (S)
The final Dolt commit is gated on `success_count > 0` (`streaming_runner.py:1834-1835`),
so a budget-capped or all-failed run leaves crawl/extract writes uncommitted, and the
next run stamps `source_commit=NULL` (`dolt_client.py:380-384`). Commit any dirty
`STREAMING_RUN_TABLES` unconditionally (labeled distinctly, e.g. "partial run"); keep the
export publication guard unchanged.

### 8. Wire Playwright into the async production path (M + S prereq)
`collect_multi_page` (`web_collector.py:2377-2394`) calls only the async crawlers; the
`PlaywrightRenderer` is invoked solely from the **sync** crawlers (`948-962`, `1466-1478`)
that production never reaches, so client-rendered SPAs return `{}` → "no data found".
- **Prereq (S):** hoist the `js_rendering_needed` computation out of the
  `if use_llm and self.llm_extractor:` block (`web_collector.py:2896-2920`) so the no-LLM
  async sitemap path (`use_llm=False`, `1367`) can flag a page as needing JS at all.
- **Fix (M):** when the async crawl yields empty/thin AND pages were flagged JS-needed,
  escalate those URLs through the `PlaywrightRenderer` once, then re-extract. Recovers the
  2 confirmed SPA failures (77-0412815, 20-3069841) + any similar.

---

## Explicit non-goals (v1)
- **Proxy / residential-IP support** — a hard IP-ban stays unrecoverable; revisit only if
  one actually appears. (Large; touches every request + secrets.)
- **Graceful SIGINT drain + resume** — re-run and let the phase cache self-heal; component
  7 guarantees a clean commit boundary.
- **Cloudflare Turnstile / JS-interstitial solving.**
- **Checkpoint cross-charity quiescence** — checkpoints stay progress-markers-only;
  phase_cache is the correctness mechanism (document, don't build).
- **Thin-success detection** and **conditional-GET on the fresh path** — reconsider only
  if the component-6 freshness report shows they matter.

---

## Testing
- **429 reclassification:** a fetch returning 429 → `RATE_LIMITED` message, `classify_failure`
  returns transient, `_should_skip_failed_source` applies the graduated backoff (not 180d).
  Fixture asserting `captcha_blocked`/`RATE_LIMITED` string routing.
- **Global QPS ceiling:** the process-wide semaphore is acquired by concurrent async
  fetches; a unit test with a stubbed limiter asserts no more than N in flight.
- **Selector:** given a raw-data table state (missing / success=0 / stale / fresh website
  rows), `--refresh-stale` selects exactly the missing+failed+stale EINs.
- **Force override:** `force_sources={'website'}` makes `_is_data_fresh` and
  `_should_skip_failed_source` both return "proceed" for website while leaving other
  sources' gating intact.
- **Source-granular freshness:** a fresh-propublica / stale-website charity is reported as
  "crawl artifacts incomplete" (website re-attempted), not skipped.
- **Unconditional commit:** an all-failed run still produces a Dolt commit; no dirty
  working set.
- **Playwright escalation:** an SPA fixture (empty async result + js-needed flag) triggers
  one Playwright render and yields extracted content; the js-needed flag is now set on the
  no-LLM path.
- Full pipeline suite stays green.

## Affected files (anchors for the plan)
| File | Components |
|---|---|
| `src/collectors/web_collector.py` | 1 (1059-1062), 2 (1004-1104), 3 (2369-2373), 8 (2377-2394, 2896-2920, 948-962/1466-1478) |
| `src/constants.py` | 1 (TERMINAL_FAILURE_MARKERS:64), 2 (new QPS constant) |
| `src/collectors/orchestrator.py` | 4 (fetch_charity_data + _is_data_fresh 367-399 + _should_skip_failed_source 401-485, call sites 742/823/827) |
| `crawl.py` | 4 (`--refresh-stale`/`--older-than` selector), 6 (report 306-352) |
| `streaming_runner.py` | 5 (_phase_artifacts_exist 249-254), 6 (summary), 7 (final commit 1833-1846) |
| `src/db/dolt_client.py` | 7 (source_commit 380-384) |

## Sequencing
Build 1 → 7/8 (1 first, non-negotiable), then **re-crawl the 20 validated EINs' websites**
via `crawl.py --sources website --refresh-stale --charities <the 20>`, confirm the
component-6 report shows them fresh, then run the fleet refresh.

## Success criteria
- A 429 during a run does NOT terminally block the site (graduated backoff instead).
- Fleet outbound concurrency never exceeds the configured ceiling (~5).
- `--refresh-stale` re-crawls exactly the stale+failed+missing websites, including the 6
  previously-frozen CAPTCHA sites, and leaves fresh sources untouched.
- The normal streaming path re-attempts a stale website instead of masking it.
- Run end prints per-source fresh/stale/failed counts.
- An interrupted/failed run leaves a clean Dolt commit boundary (re-runnable).
- The 2 confirmed SPA sites yield content via Playwright escalation.
- Full test suite green.
