# Non-Destructive Synthesize Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the crawl→synthesize→persist path non-destructive so a transient/degraded data source or a recompute gap can never overwrite a previously-good value in the `charity_data` working row.

**Architecture:** Two guards plus a recovery tool. (1) **Raw-layer content non-downgrade** — `RawDataRepository`/orchestrator refuse to replace stored substantive content with a materially thinner/empty re-crawl, within a 2-year freshness bound, so the aggregator always recomputes from last-good inputs. (2) **Synthesize regression guard** — for a fixed set of required-source-derived scalar fields, a non-null→null recompute is restored from the prior row and flagged (the Al-Furqaan recompute-gap class). (3) **Dolt-history reconciliation** — a script that finds and optionally restores already-damaged rows. The `charity_data` upsert stays a dumb full-writer; all correctness lives upstream.

**Tech Stack:** Python 3.13, `uv`, DoltDB (MySQL-compatible, version-controlled), pytest.

> **Note — this plan refines the committed spec (`docs/superpowers/specs/2026-07-19-non-destructive-synthesize-design.md`).** Recon found the C1 last-good preservation already lives in `RawDataRepository.upsert`, so carry-forward is implemented there as a non-downgrade extension (spec §2 framed it at synthesize; the raw-layer realization is the same invariant with less new code). And because `form990_grants` is a required source, the empty-grants case is handled by *preservation only when prior exists*, never by fail-marking.

## Global Constraints

- **Persist stays a dumb writer.** Do NOT add COALESCE or partial-update logic to `CharityDataRepository.upsert`. All correctness lives in the raw layer and synthesize.
- **`form990_grants` stays a required source.** Never mark an empty/sentinel grants observation `success=False` — it must keep passing the completeness gate (`orchestrator.py:784`).
- **One staleness constant.** The 2-year full-confidence window is a single named constant reused by the recency scorer and the raw-layer guard.
- **Valid nulls are preserved.** An observed source whose value is genuinely absent writes null; only *unobserved/thin* sources are carried forward, and only within 2 years.
- **Match existing conventions:** modern union type hints (`str | None`), `logging.getLogger(__name__)` in library code, repos via `execute_query(sql, params, fetch=...)`, tests call deterministic helpers on dict inputs (`tests/test_synthesize.py` / `tests/test_export_gating.py` patterns), fakes duck-type `.get(ein)`/`.get_by_source(...)`.
- **Run tests from `data-pipeline/`:** `uv run pytest`. Lint: `ruff check . --fix`.

---

### Task 1: Unify the 2-year staleness constant

**Files:**
- Modify: `data-pipeline/src/constants.py` (add constant after `CACHE_MAX_AGE_DAYS`, ~line 9)
- Modify: `data-pipeline/src/scorers/v2_scorers.py:2735-2745` (`_recency_factor` uses the constant)
- Test: `data-pipeline/tests/test_write_safety.py` (new file)

**Interfaces:**
- Produces: `DATA_FULL_CONFIDENCE_MAX_AGE_YEARS: int = 2` in `src.constants`.

- [ ] **Step 1: Write the failing test**

Create `data-pipeline/tests/test_write_safety.py`:
```python
"""Tests for the non-destructive-synthesize write-safety guards."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestStalenessConstant:
    def test_constant_is_two_years(self):
        from src.constants import DATA_FULL_CONFIDENCE_MAX_AGE_YEARS

        assert DATA_FULL_CONFIDENCE_MAX_AGE_YEARS == 2

    def test_recency_factor_uses_constant(self):
        # Age exactly at the boundary keeps full weight; one past it decays.
        from src.constants import DATA_FULL_CONFIDENCE_MAX_AGE_YEARS
        from src.scorers.v2_scorers import V2Scorer

        boundary = DATA_FULL_CONFIDENCE_MAX_AGE_YEARS
        assert V2Scorer._recency_factor(boundary) == 1.0
        assert V2Scorer._recency_factor(boundary + 1) < 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd data-pipeline && uv run pytest tests/test_write_safety.py::TestStalenessConstant -v`
Expected: FAIL — `ImportError: cannot import name 'DATA_FULL_CONFIDENCE_MAX_AGE_YEARS'`.

- [ ] **Step 3: Add the constant**

In `data-pipeline/src/constants.py`, after line 9 (`DATA_TOLERANCE_PERCENT = ...`), add:
```python
# Data freshness — the window during which data keeps full confidence and a
# missing/thin re-observation is carried forward from last-good rather than
# dropped. Beyond this, unobserved data is aged-out to null. Matches the
# 990 annual filing cycle plus one year of leeway; the -2 in _recency_factor
# and the raw-layer carry-forward guard both key off this single value.
DATA_FULL_CONFIDENCE_MAX_AGE_YEARS = 2
```

- [ ] **Step 4: Rewire `_recency_factor` to the constant**

In `data-pipeline/src/scorers/v2_scorers.py`, add the import near the top of the module (with the other `from src...` imports) and replace the two inline `2`s in `_recency_factor` (lines 2743-2745):
```python
from src.constants import DATA_FULL_CONFIDENCE_MAX_AGE_YEARS
```
```python
        if data_age_years is None or data_age_years <= DATA_FULL_CONFIDENCE_MAX_AGE_YEARS:
            return 1.0
        return max(0.40, round(1.0 - 0.15 * (data_age_years - DATA_FULL_CONFIDENCE_MAX_AGE_YEARS), 2))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd data-pipeline && uv run pytest tests/test_write_safety.py::TestStalenessConstant tests/test_v2_scorers.py -v`
Expected: PASS (new tests pass, existing scorer tests unbroken).

- [ ] **Step 6: Commit**

```bash
git add data-pipeline/src/constants.py data-pipeline/src/scorers/v2_scorers.py data-pipeline/tests/test_write_safety.py
git commit -m "feat(constants): unify 2-year full-confidence window (DATA_FULL_CONFIDENCE_MAX_AGE_YEARS)"
```

---

### Task 2: Raw-layer age helper + content-substance predicates (pure functions)

**Files:**
- Modify: `data-pipeline/src/collectors/orchestrator.py` (add module-level helpers near `is_optional_website_failure`, ~line 149)
- Test: `data-pipeline/tests/test_write_safety.py`

**Interfaces:**
- Produces (module-level in `src.collectors.orchestrator`):
  - `data_age_years(scraped_at, now=None) -> int | None`
  - `grants_has_filings(parsed_json: dict | None) -> bool`
  - `parsed_json_is_meaningful(parsed_json: dict | None) -> bool`
  - `is_content_downgrade(source: str, new_parsed_json: dict | None, new_raw_content: str | None, prior_parsed_json: dict | None) -> bool`

- [ ] **Step 1: Write the failing tests**

Append to `data-pipeline/tests/test_write_safety.py`:
```python
from datetime import datetime


class TestRawLayerPredicates:
    def test_data_age_years_from_datetime(self):
        from src.collectors.orchestrator import data_age_years

        now = datetime(2026, 7, 19)
        assert data_age_years(datetime(2024, 7, 19), now=now) == 2
        assert data_age_years(datetime(2023, 1, 1), now=now) == 3
        assert data_age_years(None, now=now) is None

    def test_data_age_years_from_iso_string(self):
        from src.collectors.orchestrator import data_age_years

        now = datetime(2026, 7, 19)
        assert data_age_years("2024-07-19 00:00:00", now=now) == 2

    def test_grants_has_filings(self):
        from src.collectors.orchestrator import grants_has_filings

        empty = {"grants_profile": {"name": "Unknown (12-3456789)", "ein": "12-3456789"}}
        real = {"grants_profile": {"ein": "12-3456789", "filing_years": [2022], "total_grants": 5000}}
        assert grants_has_filings(empty) is False
        assert grants_has_filings(real) is True
        assert grants_has_filings(None) is False

    def test_website_downgrade_thin_replaces_rich(self):
        from src.collectors.orchestrator import is_content_downgrade

        prior = {"crawl_stats": {"pages_crawled": 25}}
        thin = {"crawl_stats": {"pages_crawled": 1}}
        assert is_content_downgrade("website", thin, "x" * 600, prior) is True

    def test_website_no_downgrade_when_similar(self):
        from src.collectors.orchestrator import is_content_downgrade

        prior = {"crawl_stats": {"pages_crawled": 8}}
        fresh = {"crawl_stats": {"pages_crawled": 9}}
        assert is_content_downgrade("website", fresh, "x" * 5000, prior) is False

    def test_website_downgrade_empty_raw(self):
        from src.collectors.orchestrator import is_content_downgrade

        prior = {"crawl_stats": {"pages_crawled": 10}}
        assert is_content_downgrade("website", {"crawl_stats": {"pages_crawled": 2}}, "", prior) is True

    def test_grants_downgrade_empty_replaces_filings(self):
        from src.collectors.orchestrator import is_content_downgrade

        prior = {"grants_profile": {"filing_years": [2022], "total_grants": 9000}}
        empty = {"grants_profile": {"name": "Unknown", "ein": "12-3456789"}}
        assert is_content_downgrade("form990_grants", empty, None, prior) is True

    def test_no_downgrade_without_prior(self):
        from src.collectors.orchestrator import is_content_downgrade

        assert is_content_downgrade("website", {"crawl_stats": {"pages_crawled": 1}}, "x", {}) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd data-pipeline && uv run pytest tests/test_write_safety.py::TestRawLayerPredicates -v`
Expected: FAIL — `ImportError: cannot import name 'data_age_years'`.

- [ ] **Step 3: Implement the helpers**

In `data-pipeline/src/collectors/orchestrator.py`, after the `is_optional_website_failure` function (~line 155), add:
```python
def data_age_years(scraped_at, now=None) -> int | None:
    """Whole years since a raw source was last successfully observed.

    Accepts a datetime or an ISO-ish string (as the DB driver returns
    `scraped_at`). Returns None when the timestamp is missing/unparseable so
    callers treat unknown age as "not aged out" (absence is penalized elsewhere).
    """
    from datetime import datetime

    if scraped_at is None:
        return None
    if now is None:
        now = datetime.now()
    if isinstance(scraped_at, str):
        try:
            scraped_at = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
        except ValueError:
            try:
                scraped_at = datetime.strptime(scraped_at[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None
    if scraped_at.tzinfo is not None:
        scraped_at = scraped_at.replace(tzinfo=None)
    return (now - scraped_at).days // 365


def parsed_json_is_meaningful(parsed_json: dict | None) -> bool:
    """True if any top-level value is a non-empty dict/list (mirrors
    DataCollectionOrchestrator._is_meaningful_data as a module-level pure fn)."""
    if not parsed_json:
        return False
    for value in parsed_json.values():
        if isinstance(value, dict) and len(value) > 0:
            return True
        if isinstance(value, list) and len(value) > 0:
            return True
    return False


def grants_has_filings(parsed_json: dict | None) -> bool:
    """True if a grants observation carries real filing/financial data (not the
    empty NO_XML sentinel profile that only has name+ein)."""
    gp = (parsed_json or {}).get("grants_profile") or {}
    return bool(
        gp.get("filing_years")
        or gp.get("domestic_grants")
        or gp.get("foreign_grants")
        or gp.get("total_grants")
        or gp.get("total_revenue")
        or gp.get("total_expenses")
    )


def is_content_downgrade(
    source: str,
    new_parsed_json: dict | None,
    new_raw_content: str | None,
    prior_parsed_json: dict | None,
) -> bool:
    """True when the new observation is materially thinner than stored prior
    content — the signal to preserve last-good instead of overwriting.

    Only meaningful when a substantive prior exists; returns False otherwise
    (a first/no-prior observation is never a downgrade).
    """
    new_parsed_json = new_parsed_json or {}
    prior_parsed_json = prior_parsed_json or {}

    if source == "website":
        prior_pages = (prior_parsed_json.get("crawl_stats") or {}).get("pages_crawled") or 0
        new_pages = (new_parsed_json.get("crawl_stats") or {}).get("pages_crawled") or 0
        if prior_pages <= 0:
            return False
        thin_raw = not new_raw_content or len(new_raw_content.strip()) < 500
        lost_pages = prior_pages >= 3 and new_pages <= max(1, prior_pages // 3)
        return thin_raw or lost_pages

    if source == "form990_grants":
        return grants_has_filings(prior_parsed_json) and not grants_has_filings(new_parsed_json)

    return parsed_json_is_meaningful(prior_parsed_json) and not parsed_json_is_meaningful(new_parsed_json)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd data-pipeline && uv run pytest tests/test_write_safety.py::TestRawLayerPredicates -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add data-pipeline/src/collectors/orchestrator.py data-pipeline/tests/test_write_safety.py
git commit -m "feat(crawl): raw-layer age + content-downgrade predicates (pure)"
```

---

### Task 3: `RawDataRepository.record_soft_fail` + preserve `scraped_at` on content preservation

**Files:**
- Modify: `data-pipeline/src/db/repository.py` (`RawDataRepository.upsert` ~248-311; add `record_soft_fail`)
- Test: `data-pipeline/tests/test_write_safety.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `RawDataRepository.record_soft_fail(self, charity_ein: str, source: str, reason: str) -> None` — bumps `retry_count`/`last_failure_reason`, leaves `parsed_json`/`raw_content`/`success`/`scraped_at` untouched. Also changes `upsert` so the C1 content-preservation branch no longer bumps `scraped_at`.

- [ ] **Step 1: Write the failing tests**

These use a lightweight monkeypatch of `execute_query` to capture SQL (matches the repo's `execute_query`-only IO; no live DB). Append to `data-pipeline/tests/test_write_safety.py`:
```python
class TestRawDataRepoSoftFail:
    def test_record_soft_fail_preserves_content_and_timestamp(self, monkeypatch):
        import src.db.repository as repo_mod

        captured = {}

        def fake_execute_query(sql, params=None, fetch="all"):
            if sql.strip().upper().startswith("SELECT"):
                return {"charity_ein": "12-3456789", "source": "website", "retry_count": 1, "success": 1}
            captured["sql"] = sql
            captured["params"] = params
            return None

        monkeypatch.setattr(repo_mod, "execute_query", fake_execute_query)
        repo_mod.RawDataRepository().record_soft_fail("12-3456789", "website", "thin re-crawl; preserved")

        assert "UPDATE raw_scraped_data" in captured["sql"]
        assert "retry_count" in captured["sql"]
        assert "last_failure_reason" in captured["sql"]
        # Must NOT touch content or the observation timestamp
        assert "parsed_json" not in captured["sql"]
        assert "raw_content" not in captured["sql"]
        assert "scraped_at" not in captured["sql"]
        assert captured["params"][0] == 2  # retry_count incremented from 1

    def test_c1_failure_write_no_longer_bumps_scraped_at(self, monkeypatch):
        import src.db.repository as repo_mod

        captured = {}

        def fake_execute_query(sql, params=None, fetch="all"):
            if sql.strip().upper().startswith("SELECT"):
                return {"charity_ein": "12-3456789", "source": "website", "retry_count": 0, "success": 1}
            captured["sql"] = sql
            return None

        monkeypatch.setattr(repo_mod, "execute_query", fake_execute_query)
        # A failure write against a previously-successful row (C1 path)
        repo_mod.RawDataRepository().upsert(
            "12-3456789", "website", parsed_json={}, success=False, error_message="throttled"
        )
        assert "UPDATE raw_scraped_data" in captured["sql"]
        assert "scraped_at = CURRENT_TIMESTAMP" not in captured["sql"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd data-pipeline && uv run pytest tests/test_write_safety.py::TestRawDataRepoSoftFail -v`
Expected: FAIL — `AttributeError: 'RawDataRepository' object has no attribute 'record_soft_fail'` (and the C1 test fails because `scraped_at = CURRENT_TIMESTAMP` is still emitted).

- [ ] **Step 3: Implement `record_soft_fail` and the C1 `scraped_at` fix**

In `data-pipeline/src/db/repository.py`, in `RawDataRepository.upsert`, change the existing-row UPDATE so `scraped_at` is only bumped when content is actually written. Replace the `if existing:` UPDATE block (currently ends with `... SET {set_clause}, scraped_at = CURRENT_TIMESTAMP WHERE ...`) with:
```python
        if existing:
            preserved_content = False
            if not success:
                data["retry_count"] = (existing.get("retry_count") or 0) + 1
                if existing.get("success"):
                    # Never clobber last-good content with a failure record (C1)
                    data.pop("parsed_json", None)
                    data.pop("raw_content", None)
                    preserved_content = True
            set_clause = ", ".join([f"{k} = %s" for k in data.keys() if k not in ("charity_ein", "source")])
            values = [v for k, v in data.items() if k not in ("charity_ein", "source")]
            values.extend([charity_ein, source])

            # Only advance the observation timestamp when we actually wrote new
            # content; preserving last-good keeps scraped_at at the last
            # successful observation so its age (carry-forward bound) stays true.
            scraped_clause = "" if preserved_content else ", scraped_at = CURRENT_TIMESTAMP"
            execute_query(
                f"UPDATE raw_scraped_data SET {set_clause}{scraped_clause} WHERE charity_ein = %s AND source = %s",
                tuple(values),
                fetch="none",
            )
```
Then add the new method (right after `upsert`):
```python
    def record_soft_fail(self, charity_ein: str, source: str, reason: str) -> None:
        """Record a thin/empty re-observation without downgrading last-good.

        Bumps retry_count and last_failure_reason but leaves parsed_json,
        raw_content, success, and scraped_at untouched — the stored last-good
        content stays authoritative and keeps its original observation age.
        Used by the orchestrator when a re-crawl returns materially less than
        the stored content and the stored content is still within the
        freshness window.
        """
        existing = self.get_by_source(charity_ein, source)
        if not existing:
            return
        retry = (existing.get("retry_count") or 0) + 1
        execute_query(
            "UPDATE raw_scraped_data SET retry_count = %s, last_failure_reason = %s "
            "WHERE charity_ein = %s AND source = %s",
            (retry, reason, charity_ein, source),
            fetch="none",
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd data-pipeline && uv run pytest tests/test_write_safety.py::TestRawDataRepoSoftFail -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add data-pipeline/src/db/repository.py data-pipeline/tests/test_write_safety.py
git commit -m "feat(db): record_soft_fail + preserve scraped_at on last-good preservation"
```

---

### Task 4: Wire the non-downgrade guard into `_store_raw_data`

**Files:**
- Modify: `data-pipeline/src/collectors/orchestrator.py` (`_store_raw_data` ~1210-1273)
- Test: `data-pipeline/tests/test_write_safety.py`

**Interfaces:**
- Consumes: `is_content_downgrade`, `data_age_years` (Task 2); `record_soft_fail`, `get_by_source` (Task 3); `DATA_FULL_CONFIDENCE_MAX_AGE_YEARS` (Task 1).
- Produces: `_store_raw_data` preserves last-good instead of overwriting when the new observation is a downgrade and the stored content is within the freshness window; returns `True` (source counts as succeeded on carried content).

- [ ] **Step 1: Write the failing test**

Append to `data-pipeline/tests/test_write_safety.py` (uses a fake `raw_data_repo` on a minimally-constructed collector via `object.__new__` to avoid heavy init):
```python
class TestStoreRawDataNonDowngrade:
    def _collector_with_fake_repo(self, existing_row):
        from src.collectors.orchestrator import DataCollectionOrchestrator

        calls = {"soft_fail": [], "upsert": []}

        class FakeRawRepo:
            def get_by_source(self, ein, source):
                return existing_row

            def record_soft_fail(self, ein, source, reason):
                calls["soft_fail"].append((ein, source, reason))

            def upsert(self, **kwargs):
                calls["upsert"].append(kwargs)

        col = object.__new__(DataCollectionOrchestrator)  # skip __init__
        col.raw_data_repo = FakeRawRepo()
        import logging

        col.logger = logging.getLogger("test")
        return col, calls

    def test_thin_recrawl_preserves_recent_last_good(self):
        from datetime import datetime

        recent = datetime.now().replace(microsecond=0).isoformat(sep=" ")
        existing = {
            "success": 1,
            "scraped_at": recent,
            "parsed_json": {"website_profile": {"url": "x"}, "crawl_stats": {"pages_crawled": 25}},
        }
        col, calls = self._collector_with_fake_repo(existing)
        thin = {
            "raw_content": "x" * 100,  # below the 500 floor
            "website_profile": {"url": "x", "ein": "12-3456789"},
            "page_extractions": [],
            "crawl_stats": {"pages_crawled": 1},
        }
        result = col._store_raw_data("12-3456789", "website", thin)
        assert result is True
        assert len(calls["soft_fail"]) == 1     # preserved
        assert len(calls["upsert"]) == 0        # no overwrite

    def test_thin_recrawl_aged_out_is_written(self):
        existing = {
            "success": 1,
            "scraped_at": "2019-01-01 00:00:00",  # > 2 years old
            "parsed_json": {"website_profile": {"url": "x"}, "crawl_stats": {"pages_crawled": 25}},
        }
        col, calls = self._collector_with_fake_repo(existing)
        thin = {"raw_content": "x" * 100, "website_profile": {"url": "x"}, "crawl_stats": {"pages_crawled": 1}}
        col._store_raw_data("12-3456789", "website", thin)
        assert len(calls["soft_fail"]) == 0     # aged-out: allow the drop
        assert len(calls["upsert"]) == 1

    def test_empty_grants_preserved_when_prior_has_filings(self):
        recent = "2026-01-01 00:00:00"
        existing = {
            "success": 1,
            "scraped_at": recent,
            "parsed_json": {"grants_profile": {"filing_years": [2022], "total_grants": 9000}},
        }
        col, calls = self._collector_with_fake_repo(existing)
        empty = {"grants_profile": {"name": "Unknown (12-3456789)", "ein": "12-3456789"}}
        result = col._store_raw_data("12-3456789", "form990_grants", empty)
        assert result is True
        assert len(calls["soft_fail"]) == 1
        assert len(calls["upsert"]) == 0
```
(Note: `test_empty_grants...` uses a near-current `scraped_at`; if the current year differs, keep it within 2 years of today.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd data-pipeline && uv run pytest tests/test_write_safety.py::TestStoreRawDataNonDowngrade -v`
Expected: FAIL — the current `_store_raw_data` always calls `upsert`, so `calls["soft_fail"]` is empty.

- [ ] **Step 3: Implement the guard in `_store_raw_data`**

In `data-pipeline/src/collectors/orchestrator.py`, add the imports at the top of the file (with the other `from src...` imports):
```python
from src.constants import DATA_FULL_CONFIDENCE_MAX_AGE_YEARS
```
Then in `_store_raw_data`, after the `parsed_json` is fully built and (for website) bounds-validated — i.e. immediately before the existing `is_meaningful = self._is_meaningful_data(parsed_json)` line — insert:
```python
        # Non-downgrade guard: never replace stored substantive content with a
        # materially thinner/empty re-observation while the stored content is
        # still within the freshness window. Preserves last-good (source keeps
        # counting as succeeded) so the aggregator recomputes from it. Beyond
        # the window, or with no prior, fall through and write normally.
        existing = self.raw_data_repo.get_by_source(ein, source)
        if existing and existing.get("success"):
            age = data_age_years(existing.get("scraped_at"))
            within_window = age is None or age <= DATA_FULL_CONFIDENCE_MAX_AGE_YEARS
            if within_window and is_content_downgrade(source, parsed_json, raw_content, existing.get("parsed_json")):
                reason = f"{source} re-observation thinner than last-good; preserved (age={age}y)"
                self.logger.warning(f"{ein}: {reason}")
                self.raw_data_repo.record_soft_fail(ein, source, reason)
                return True
```
`data_age_years` and `is_content_downgrade` are module-level in this file (Task 2), so no import needed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd data-pipeline && uv run pytest tests/test_write_safety.py::TestStoreRawDataNonDowngrade -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the collector regression tests**

Run: `cd data-pipeline && uv run pytest tests/test_crawl_politeness.py -v`
Expected: PASS (no regressions in the existing crawl-store behavior).

- [ ] **Step 6: Commit**

```bash
git add data-pipeline/src/collectors/orchestrator.py data-pipeline/tests/test_write_safety.py
git commit -m "feat(crawl): non-downgrade guard preserves last-good on thin re-crawl (Vectors 2/4/5)"
```

---

### Task 5: Synthesize regression guard (recompute-gap class, Vector 1)

**Files:**
- Modify: `data-pipeline/synthesize.py` (`synthesize_charity` signature ~1365; after `synthesized` is built ~post-1510; caller `main()` ~2147)
- Test: `data-pipeline/tests/test_write_safety.py`

**Interfaces:**
- Consumes: `CharityDataRepository.get(ein)` (returns `dict | None`).
- Produces:
  - Module-level `REGRESSION_GUARDED_FIELDS: frozenset[str]` in `synthesize.py`.
  - Module-level `apply_regression_guard(synthesized, prior_row) -> list[dict]` — restores guarded non-null→null fields from `prior_row`, returns flag dicts `{"charity_ein", "field", "prior_value"}`.
  - `synthesize_charity(..., data_repo: CharityDataRepository | None = None)` — reads the prior row, applies the guard, and puts flags on `result["regressions"]`.

- [ ] **Step 1: Write the failing tests**

Append to `data-pipeline/tests/test_write_safety.py`:
```python
class TestRegressionGuard:
    def test_guard_restores_nonnull_to_null(self):
        from synthesize import apply_regression_guard
        from src.db import CharityData

        prior = {"program_expense_ratio": 0.85, "total_revenue": 1_000_000}
        synthesized = CharityData(charity_ein="12-3456789")
        synthesized.total_revenue = 1_000_000
        # program_expense_ratio recomputed to None this run (the Al-Furqaan gap)
        flags = apply_regression_guard(synthesized, prior)

        assert synthesized.program_expense_ratio == 0.85  # restored
        assert flags == [{"charity_ein": "12-3456789", "field": "program_expense_ratio", "prior_value": 0.85}]

    def test_guard_allows_observed_absent_and_unguarded_fields(self):
        from synthesize import apply_regression_guard
        from src.db import CharityData

        prior = {"program_expense_ratio": 0.85, "theory_of_change": "old story"}
        synthesized = CharityData(charity_ein="12-3456789")
        synthesized.program_expense_ratio = 0.85  # unchanged
        # theory_of_change is NOT in the guarded set (website-derived, may legitimately drop)
        flags = apply_regression_guard(synthesized, prior)

        assert flags == []
        assert synthesized.theory_of_change is None  # not restored

    def test_guard_no_prior_row_is_noop(self):
        from synthesize import apply_regression_guard
        from src.db import CharityData

        synthesized = CharityData(charity_ein="12-3456789")
        assert apply_regression_guard(synthesized, None) == []

    def test_guarded_fields_are_required_source_derived(self):
        from synthesize import REGRESSION_GUARDED_FIELDS

        assert "program_expense_ratio" in REGRESSION_GUARDED_FIELDS
        assert "noncash_ratio" in REGRESSION_GUARDED_FIELDS
        # website-derived text fields must NOT be guarded (legit drops)
        assert "theory_of_change" not in REGRESSION_GUARDED_FIELDS
        assert "populations_served" not in REGRESSION_GUARDED_FIELDS
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd data-pipeline && uv run pytest tests/test_write_safety.py::TestRegressionGuard -v`
Expected: FAIL — `ImportError: cannot import name 'apply_regression_guard'`.

- [ ] **Step 3: Implement the guard**

In `data-pipeline/synthesize.py`, add near the module top (after imports, before `synthesize_charity`):
```python
# Scalar fields derived from REQUIRED sources (ProPublica / CN financials).
# These can only recompute to None via a computation gap (all their inputs are
# required, so a source loss would have aborted the charity before synthesize).
# A non-null -> null transition here is therefore always a bug, not a genuine
# drop, so we restore the prior value and flag it. Text/website-derived fields
# are deliberately excluded — those can legitimately go absent year to year.
REGRESSION_GUARDED_FIELDS = frozenset(
    {
        "program_expense_ratio",
        "noncash_ratio",
        "cash_adjusted_program_ratio",
        "domestic_burn_rate",
        "reserves_months",
        "working_capital_months",
        "total_revenue",
        "total_expenses",
        "program_expenses",
        "admin_expenses",
        "fundraising_expenses",
        "total_assets",
        "total_liabilities",
        "net_assets",
    }
)


def apply_regression_guard(synthesized, prior_row: dict | None) -> list[dict]:
    """Restore guarded scalar fields that recomputed non-null -> null this run.

    Returns a list of flag dicts for the editorial/regressions report. Mutates
    `synthesized` in place, restoring the prior value for each regressed field.
    """
    if not prior_row:
        return []
    flags: list[dict] = []
    for field in REGRESSION_GUARDED_FIELDS:
        prior_value = prior_row.get(field)
        if prior_value is not None and getattr(synthesized, field, None) is None:
            setattr(synthesized, field, prior_value)
            flags.append(
                {"charity_ein": synthesized.charity_ein, "field": field, "prior_value": prior_value}
            )
    return flags
```
Then thread it into `synthesize_charity`. Change the signature (line 1365) to add the optional repo:
```python
def synthesize_charity(
    ein: str,
    raw_repo: RawDataRepository,
    charity_repo: CharityRepository,
    pilot_name: str | None = None,
    data_repo: "CharityDataRepository | None" = None,
) -> dict[str, Any]:
```
Immediately before the success return (where `result["synthesized"] = synthesized` is set — find the block that sets `result["success"] = True`), add:
```python
        # Non-destructive write: never let a guarded scalar regress non-null -> null.
        if data_repo is None:
            data_repo = CharityDataRepository()
        prior_row = data_repo.get(ein)
        regression_flags = apply_regression_guard(synthesized, prior_row)
        if regression_flags:
            logging.getLogger(__name__).warning(
                f"{ein}: preserved {len(regression_flags)} regressed field(s): "
                f"{[f['field'] for f in regression_flags]}"
            )
        result["regressions"] = regression_flags
```
(Place this AFTER all `synthesized.<field> = ...` assignments and BEFORE `data_repo.upsert` runs in `main()`. If `result["synthesized"]` is assigned near the end of `synthesize_charity`, insert immediately before that assignment.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd data-pipeline && uv run pytest tests/test_write_safety.py::TestRegressionGuard -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Run the synthesize suite for regressions**

Run: `cd data-pipeline && uv run pytest tests/test_synthesize.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add data-pipeline/synthesize.py data-pipeline/tests/test_write_safety.py
git commit -m "feat(synthesize): regression guard restores non-null->null on required-source scalars (Vector 1)"
```

---

### Task 6: Persist regression flags to a report artifact

**Files:**
- Modify: `data-pipeline/synthesize.py` (`main()` ~2147-2190; aggregate `result["regressions"]` and write once)
- Modify: `data-pipeline/streaming_runner.py` (the synthesize phase call — thread the same `data_repo` and collect regressions)
- Test: `data-pipeline/tests/test_write_safety.py`

**Interfaces:**
- Consumes: `result["regressions"]` from `synthesize_charity`.
- Produces: `write_synthesize_regressions(rows: list[dict], reports_dir: Path = REPORTS_DIR) -> Path` in `synthesize.py`, writing `reports/synthesize-regressions.json`.

- [ ] **Step 1: Write the failing test**

Append to `data-pipeline/tests/test_write_safety.py`:
```python
class TestRegressionReport:
    def test_writes_regressions_json(self, tmp_path):
        from synthesize import write_synthesize_regressions
        import json

        rows = [{"charity_ein": "12-3456789", "field": "program_expense_ratio", "prior_value": 0.85}]
        path = write_synthesize_regressions(rows, reports_dir=tmp_path)
        assert path.name == "synthesize-regressions.json"
        written = json.loads(path.read_text())
        assert written == rows

    def test_empty_regressions_writes_empty_list(self, tmp_path):
        from synthesize import write_synthesize_regressions
        import json

        path = write_synthesize_regressions([], reports_dir=tmp_path)
        assert json.loads(path.read_text()) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd data-pipeline && uv run pytest tests/test_write_safety.py::TestRegressionReport -v`
Expected: FAIL — `ImportError: cannot import name 'write_synthesize_regressions'`.

- [ ] **Step 3: Implement the writer + wire it into `main()`**

In `data-pipeline/synthesize.py`, add near the other report helpers (mirror `export.write_editorial_queue`; define `REPORTS_DIR` if not already imported — reuse the same `reports/` dir the editorial queue uses):
```python
from pathlib import Path

REPORTS_DIR = Path(__file__).parent / "reports"


def write_synthesize_regressions(rows: list[dict], reports_dir: Path = REPORTS_DIR) -> Path:
    """Write preserved-regression flags to reports/synthesize-regressions.json.

    Each row: {charity_ein, field, prior_value}. Internal-only editorial signal
    — a human confirms bug vs genuine drop. Never gates anything.
    """
    import json

    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / "synthesize-regressions.json"
    with open(path, "w") as f:
        json.dump(rows, f, indent=2, default=str)
    print(f"  synthesize regressions: {len(rows)} field(s) preserved")
    return path
```
In `main()`, accumulate regressions across the loop and write once after the loop (next to the Dolt commit, ~line 2187). Where each charity's `result` is handled, add `all_regressions.extend(result.get("regressions") or [])` (initialize `all_regressions: list[dict] = []` before the loop), and after the loop:
```python
    write_synthesize_regressions(all_regressions)
```

- [ ] **Step 4: Wire the streaming runner**

In `data-pipeline/streaming_runner.py`, at the synthesize phase call site, pass the runner's existing `CharityDataRepository` instance as `data_repo=` to `synthesize_charity`, accumulate `result.get("regressions")`, and call `write_synthesize_regressions(...)` after the run (mirror how `write_editorial_queue` is already called at `streaming_runner.py:1978`). If the runner has no `CharityDataRepository` handy, construct one alongside the other repos.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd data-pipeline && uv run pytest tests/test_write_safety.py::TestRegressionReport -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add data-pipeline/synthesize.py data-pipeline/streaming_runner.py data-pipeline/tests/test_write_safety.py
git commit -m "feat(synthesize): write preserved-regression flags to reports/synthesize-regressions.json"
```

---

### Task 7: Dolt-history recovery/reconciliation script

**Files:**
- Create: `data-pipeline/bin/reconcile_charity_data.py`
- Test: `data-pipeline/tests/test_reconcile.py` (new)

**Interfaces:**
- Consumes: `get_dolt().history("charity_data", {"charity_ein": ein})`, `CharityDataRepository`, `REGRESSION_GUARDED_FIELDS`.
- Produces:
  - `find_regressions(current_row: dict, history_rows: list[dict], fields) -> list[dict]` — pure; returns `{"charity_ein", "field", "current_value", "last_good_value", "last_good_commit"}` for fields currently null with a non-null in history.
  - CLI: `uv run python bin/reconcile_charity_data.py [--apply] [--ein EIN]` — report-only by default; `--apply` restores last-good.

- [ ] **Step 1: Write the failing test (pure core)**

Create `data-pipeline/tests/test_reconcile.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestFindRegressions:
    def test_finds_currently_null_with_historical_value(self):
        from bin.reconcile_charity_data import find_regressions

        current = {"charity_ein": "12-3456789", "program_expense_ratio": None, "total_revenue": 1000}
        history = [
            {"program_expense_ratio": None, "total_revenue": 1000, "commit_hash": "c3"},
            {"program_expense_ratio": 0.85, "total_revenue": 1000, "commit_hash": "c2"},
        ]
        fields = {"program_expense_ratio", "total_revenue"}
        out = find_regressions(current, history, fields)
        assert out == [
            {
                "charity_ein": "12-3456789",
                "field": "program_expense_ratio",
                "current_value": None,
                "last_good_value": 0.85,
                "last_good_commit": "c2",
            }
        ]

    def test_no_regression_when_current_present(self):
        from bin.reconcile_charity_data import find_regressions

        current = {"charity_ein": "12-3456789", "program_expense_ratio": 0.9}
        history = [{"program_expense_ratio": 0.85, "commit_hash": "c2"}]
        assert find_regressions(current, history, {"program_expense_ratio"}) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd data-pipeline && uv run pytest tests/test_reconcile.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bin.reconcile_charity_data'`.

- [ ] **Step 3: Implement the script**

Create `data-pipeline/bin/__init__.py` if it does not exist (empty file), then `data-pipeline/bin/reconcile_charity_data.py`:
```python
"""Detect and optionally restore charity_data fields that regressed to NULL.

Report-only by default; --apply restores the most recent non-null historical
value for each guarded field that is currently NULL. Leans on Dolt history —
no new storage. Same preserve+flag philosophy: a human confirms bug vs drop.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import CharityDataRepository, CharityRepository  # noqa: E402
from src.db.dolt_client import get_dolt  # noqa: E402
from synthesize import REGRESSION_GUARDED_FIELDS  # noqa: E402


def find_regressions(current_row: dict, history_rows: list[dict], fields) -> list[dict]:
    """Pure: for each guarded field currently NULL, find the most recent
    non-null value in history (history_rows newest-first)."""
    out: list[dict] = []
    if not current_row:
        return out
    for field in fields:
        if current_row.get(field) is not None:
            continue
        for hrow in history_rows:
            val = hrow.get(field)
            if val is not None:
                out.append(
                    {
                        "charity_ein": current_row.get("charity_ein"),
                        "field": field,
                        "current_value": None,
                        "last_good_value": val,
                        "last_good_commit": hrow.get("commit_hash") or hrow.get("dolt_commit_hash"),
                    }
                )
                break
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile regressed charity_data fields from Dolt history.")
    parser.add_argument("--ein", help="Limit to one EIN.")
    parser.add_argument("--apply", action="store_true", help="Restore last-good values (default: report only).")
    args = parser.parse_args()

    data_repo = CharityDataRepository()
    charity_repo = CharityRepository()
    dolt = get_dolt()

    eins = [args.ein] if args.ein else [c["ein"] for c in charity_repo.get_all() if c.get("ein")]
    all_flags: list[dict] = []
    for ein in eins:
        current = data_repo.get(ein)
        if not current:
            continue
        history = dolt.history("charity_data", {"charity_ein": ein}, limit=20)
        flags = find_regressions(current, history, REGRESSION_GUARDED_FIELDS)
        for f in flags:
            all_flags.append(f)
            if args.apply:
                setattr_row = dict(current)
                setattr_row[f["field"]] = f["last_good_value"]
                data_repo.upsert(setattr_row)
                print(f"  restored {ein}.{f['field']} = {f['last_good_value']}")

    reports_dir = Path(__file__).parent.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / "data-recovery-candidates.json"
    path.write_text(json.dumps(all_flags, indent=2, default=str))
    verb = "restored" if args.apply else "candidates"
    print(f"reconcile: {len(all_flags)} {verb} across {len(eins)} charities → {path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd data-pipeline && uv run pytest tests/test_reconcile.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add data-pipeline/bin/reconcile_charity_data.py data-pipeline/bin/__init__.py data-pipeline/tests/test_reconcile.py
git commit -m "feat(recovery): Dolt-history reconciliation for regressed charity_data fields"
```

---

### Task 8: End-to-end validation

**Files:**
- No source changes (validation only). May add one integration test to `tests/test_write_safety.py`.

- [ ] **Step 1: Full suite green**

Run: `cd data-pipeline && uv run pytest`
Expected: PASS — the pre-existing count (≈819 tests) plus the new write-safety/reconcile tests, 0 failures.

- [ ] **Step 2: Lint**

Run: `cd data-pipeline && ruff check . --fix && ruff check .`
Expected: clean.

- [ ] **Step 3: Live re-synthesize a real charity twice, second run with a simulated soft-fail**

Pick a charity with a rich website + grants (e.g. an EIN from the validated 20). Ensure DoltDB server is running (`cd ~/.amal-metric-data/dolt/zakaat && dolt sql-server`). Run:
```bash
cd data-pipeline
uv run python synthesize.py --ein <EIN>
# capture a known scalar, e.g. program_expense_ratio + a website-derived field, from charity_data
```
Then simulate a soft-fail: temporarily point the charity's website source at a throttle/empty, or manually mark its raw `website` row thin, and re-run:
```bash
uv run python crawl.py --ein <EIN>     # produces a (possibly thin) re-crawl
uv run python synthesize.py --ein <EIN>
```
Expected: the scalar and website-derived fields are UNCHANGED (carried forward / preserved), `reports/synthesize-regressions.json` reflects any recompute-gap preserves, and `dolt diff` shows no non-null→null regression on guarded fields.

- [ ] **Step 4: Reconciliation dry run**

Run: `cd data-pipeline && uv run python bin/reconcile_charity_data.py`
Expected: writes `reports/data-recovery-candidates.json`; review it for any already-damaged rows (Al-Furqaan-class). Optionally `--apply --ein <EIN>` to restore a confirmed one.

- [ ] **Step 5: Final commit (if an integration test was added)**

```bash
git add -A
git commit -m "test(write-safety): end-to-end non-destructive synthesize validation"
```

---

## Self-Review

**Spec coverage:**
- Invariant "known-absent vs unknown" → Tasks 4 (carry-forward = unknown preserved) + 5 (recompute-gap preserved). Observed-absent writes null (no guard fires) ✓.
- Bounded 2-yr carry-forward → Tasks 1 (constant) + 4 (`data_age_years` window check) ✓.
- Aged-out drop → Task 4 `test_thin_recrawl_aged_out_is_written` ✓.
- Regression preserve + flag → Tasks 5 + 6 ✓.
- Recovery via Dolt history → Task 7 ✓.
- Persist stays dumb (no COALESCE) → no `charity_data` upsert change anywhere ✓.
- Grants required-source constraint honored → Task 4 preserves only when prior exists ✓.

**Placeholder scan:** all code blocks are concrete; the only English-only step is Task 6 Step 4 (streaming_runner wiring) and Task 8 (validation), which are inherently integration steps — each names the exact call site and the mirror pattern (`streaming_runner.py:1978`).

**Type consistency:** `apply_regression_guard(synthesized, prior_row)` and `REGRESSION_GUARDED_FIELDS` used identically in Tasks 5/7; `record_soft_fail(charity_ein, source, reason)` signature matches its Task 4 call; `data_age_years`/`is_content_downgrade`/`grants_has_filings` signatures match between Tasks 2 and 4.
