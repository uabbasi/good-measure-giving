# Infrastructure Upgrades: Three Phases

Implementation order: Phase 3 (LiteLLM Router) → Phase 1 (Crawl4AI) → Phase 2 (Dagster)

No Docker. All three phases run as in-process Python libraries.

---

## Phase 3: LiteLLM Router Integration

**Goal**: Replace direct `litellm.completion()` calls with LiteLLM Router for cross-thread rate limiting, API key rotation, budget controls, and centralized retry logic.

**Key decision**: Router (in-process library), NOT Proxy (separate server). Router runs inside the same Python process, is thread-safe, and provides all the features we need without operational overhead.

### What Changes

| Current | After |
|---------|-------|
| `litellm.completion(**kwargs)` in LLMClient | `router.completion(**kwargs)` via singleton Router |
| Manual `for model in [primary, *fallbacks]` loop | Router handles fallback via `model_list` deployments |
| `_is_transient_error()` / `_is_permanent_error()` | Router's `RetryPolicy` + `AllowedFailsPolicy` |
| Per-thread independent retries (rate limit storms) | Router queues across all 20 workers |
| No budget enforcement | `--budget` flag with callback-based enforcement |
| Single API key per provider | Multiple keys as separate deployments |

### What Stays Unchanged

- `LLMResponse` dataclass and all tracking metadata
- Task-based model selection (`LLMTask` enum → primary + fallbacks)
- Provider-specific kwargs (Google safety_settings, GPT-5 temperature)
- Prompt versioning and hash tracking
- JSON mode / schema handling
- All call sites (`baseline.py`, `synthesize.py`, etc.) — they use `LLMClient`, not `litellm` directly

### Files

| Action | File | What |
|--------|------|------|
| CREATE | `data-pipeline/src/llm/router_config.py` | Router singleton, builds `model_list` from existing `MODEL_REGISTRY` + `TASK_MODELS` |
| CREATE | `data-pipeline/src/llm/budget_tracker.py` | LiteLLM callback for per-run budget enforcement |
| MODIFY | `data-pipeline/src/llm/llm_client.py` | Swap `completion()` → `router.completion()`, remove manual fallback loop, keep everything else |
| MODIFY | `data-pipeline/streaming_runner.py` | Add `--budget` CLI flag |

### Implementation Steps

1. **`router_config.py`**: Build `model_list` from `TASK_MODELS` — each task's primary + fallbacks become deployments under `model_name=task.value`. Support multiple API keys per provider via `GEMINI_API_KEY`, `GEMINI_API_KEY_2`, etc.

2. **`budget_tracker.py`**: LiteLLM `success_callback` that accumulates cost (thread-safe) and raises `BudgetExceededError` when limit hit.

3. **`llm_client.py` changes**:
   - `generate()`: Replace the `for model_name in models_to_try` loop with single `router.completion(model=task.value, **kwargs)` call
   - `_generate_with_model()`: Keep for response parsing → `LLMResponse`, but remove retry/fallback responsibility
   - Remove `_is_transient_error()` and `_is_permanent_error()` (Router handles this)
   - Keep `MODEL_REGISTRY` for provider-specific kwargs lookup and display costs
   - For direct-model callers (`LLMClient(model="gemini-3-flash")`), call `router.completion(model=config["litellm_name"])` directly

4. **`streaming_runner.py`**: Add `--budget` flag, initialize `budget_tracker` before processing.

### Implementation Notes (from initial attempt)

- Budget enforcement via LiteLLM callbacks doesn't work — LiteLLM swallows exceptions raised in callbacks. Instead, check budget *before* each call in `LLMClient.generate()`.
- The Router singleton uses double-checked locking for thread safety.
- 50 deployments are generated across 20 model groups (8 task-based + 12 direct-model).

### Verify

```bash
# Single charity test
uv run python streaming_runner.py --ein 95-4453134 --budget 1.0 2>&1 | tee /tmp/router-test.log

# Budget enforcement
uv run python streaming_runner.py --ein 95-4453134 --budget 0.001  # should fail fast

# Full pilot (compare costs with previous runs via dolt diff)
uv run python streaming_runner.py --charities pilot_charities.txt --limit 5 --budget 5.0 2>&1 | tee /tmp/router-pilot.log
```

---

## Phase 1: Crawl4AI Integration

**Goal**: Replace requests+BeautifulSoup+Playwright website crawling with Crawl4AI for cleaner markdown output, reducing LLM extraction token usage (~30% of total cost).

### What Changes

| Current | After |
|---------|-------|
| `_fetch_url()` → raw HTML → LLM parses HTML | Crawl4AI → clean markdown → LLM parses markdown |
| Custom BFS with `_crawl_with_bfs_async()` | Crawl4AI's `BFSDeepCrawlStrategy` |
| Playwright as JS fallback | Crawl4AI handles JS rendering natively |
| `PRIORITY_PATTERNS` for URL scoring | Crawl4AI's `KeywordRelevanceScorer` |

### What Stays Unchanged

- Pydantic `WebsiteProfile` validation
- `DeterministicExtractor` and `StructuredDataExtractor`
- PDF download/extraction pipeline
- All downstream phases (synthesize, baseline, etc.)
- V1 path as fallback if Crawl4AI returns empty results

### Files

| Action | File | What |
|--------|------|------|
| CREATE | `data-pipeline/src/collectors/crawl4ai_fetcher.py` | Crawl4AI wrapper: BFS crawl → markdown pages |
| MODIFY | `data-pipeline/src/collectors/web_collector.py` | Add `collect_multi_page_v2()` using Crawl4AI, auto-fallback to V1 |
| MODIFY | `data-pipeline/src/llm/website_extractor.py` | Add `extract_from_markdown()` with adapted prompt |
| CREATE | `data-pipeline/src/collectors/ab_test_crawler.py` | A/B test: run V1 and V2 on same charities, compare fields + cost |
| MODIFY | `data-pipeline/streaming_runner.py` | Add `--crawler v1|v2` flag |
| MODIFY | `pyproject.toml` | Add `crawl4ai>=0.6.0` |

### Implementation Steps

1. **Add dependency**: `crawl4ai` to pyproject.toml, `uv sync`

2. **`crawl4ai_fetcher.py`**: Async wrapper around `AsyncWebCrawler` with `BFSDeepCrawlStrategy`. Map existing `PRIORITY_PATTERNS` keywords to `KeywordRelevanceScorer`. Returns `list[CrawlPage(url, markdown, depth)]`.

3. **`web_collector.py`**: New `collect_multi_page_v2()` that:
   - Calls `Crawl4AIFetcher.crawl_site()`
   - Falls back to `collect_multi_page()` if no pages returned
   - Passes markdown (not HTML) to LLM extractor
   - Keeps PDF extraction unchanged

4. **`website_extractor.py`**: New `extract_from_markdown()` method — same schema output, adapted prompt that expects markdown input instead of HTML. Should use significantly fewer tokens.

5. **A/B test harness**: Script that runs both V1 and V2 on N charities and compares field coverage, token usage, cost, and output quality.

6. **Wire into runner**: `--crawler v2` flag in streaming_runner.py.

### Verify

```bash
# A/B test on 5 charities
uv run python src/collectors/ab_test_crawler.py --limit 5 2>&1 | tee /tmp/ab-crawl.log

# Compare: field coverage, token counts, costs
# Then full pipeline with V2
uv run python streaming_runner.py --charities pilot_charities.txt --limit 10 --crawler v2 2>&1 | tee /tmp/crawl4ai-pilot.log

# Diff against previous run
cd ~/.amal-metric-data/dolt/zakaat && dolt diff HEAD~1 HEAD
```

---

## Phase 2: Dagster Migration

**Goal**: Replace `streaming_runner.py` (~1400 lines) with Dagster for asset-based orchestration, built-in memoization, UI observability, and per-charity partition management.

### Architecture Mapping

| streaming_runner.py | Dagster |
|---------------------|---------|
| 7 phases (crawl→export) | 8 assets with declared dependencies |
| Each EIN processed through all phases | Each EIN is a partition across all assets |
| `check_phase_cache()` with fingerprint+TTL | `code_version` (fingerprint) + `FreshnessPolicy` (TTL) |
| `ThreadPoolExecutor(max_workers=20)` | Dagster executor config |
| `--checkpoint N` DoltDB commits | `run_status_sensor` for DoltDB commits |
| Console progress bars | Dagster UI dashboard |
| `process_charity_full()` | Asset materialization per partition |

### Files

| Action | File | What |
|--------|------|------|
| CREATE | `data-pipeline/dagster/__init__.py` | Package init |
| CREATE | `data-pipeline/dagster/assets.py` | 8 phase assets wrapping existing phase functions |
| CREATE | `data-pipeline/dagster/partitions.py` | `StaticPartitionsDefinition` from pilot_charities.txt |
| CREATE | `data-pipeline/dagster/io_managers.py` | DoltDB I/O manager (passthrough — phases write directly) |
| CREATE | `data-pipeline/dagster/resources.py` | Shared resources (repos, LLM client, scorer) |
| CREATE | `data-pipeline/dagster/definitions.py` | Dagster entry point |
| CREATE | `data-pipeline/dagster/sensors.py` | DoltDB commit sensor on run success |
| MODIFY | `pyproject.toml` | Add `dagster>=1.9.0`, `dagster-webserver>=1.9.0` as optional deps |
| KEEP | `streaming_runner.py` | Unchanged during transition, deprecated after validation |

### Implementation Steps

1. **Dependencies**: Add dagster as optional dependency group: `uv sync --extra dagster`

2. **Partitions**: Build `StaticPartitionsDefinition` from `pilot_charities.txt`

3. **Assets**: Wrap each existing phase function as a Dagster asset. The phase scripts (`crawl.py`, `baseline.py`, etc.) already have per-EIN functions — Dagster assets call those directly. Asset dependency graph:
   ```
   crawl_data
   ├── extract_data ──┐
   └── discover_data ─┤
                      synthesize_data
                      └── baseline_data
                          ├── rich_data
                          └── judge_data
                              └── export_data
   ```

4. **I/O Manager**: Passthrough pattern — phase functions already write to DoltDB. The I/O manager records metadata (what was materialized) but doesn't handle the actual DB writes.

5. **Memoization**: Use `code_version=compute_code_fingerprint("phase_name")` on each asset. Combined with `FreshnessPolicy` for time-based TTLs. Maps directly to existing `PHASE_CODE_FILES` and `DEFAULT_TTLS`.

6. **DoltDB commits**: `run_status_sensor` triggers `dolt.commit()` after successful runs.

7. **Resources**: Shared `ConfigurableResource` for repos, LLM client, scorer — initialized once, shared across assets.

### Migration Strategy

- Both `streaming_runner.py` and Dagster read/write the same DoltDB tables
- Run both on same charities, compare outputs via `dolt diff`
- Dagster runs alongside, not instead of, until validated
- Deprecate `streaming_runner.py` only after full pilot validation

### Verify

```bash
# Launch Dagster UI
cd data-pipeline && uv run dagster dev -m dagster.definitions

# Materialize single charity via UI, then:
cd ~/.amal-metric-data/dolt/zakaat && dolt diff HEAD~1 HEAD

# Compare with streaming_runner output
uv run python streaming_runner.py --ein 95-4453134 2>&1 | tee /tmp/runner-baseline.log
# Then run same EIN through Dagster and diff
```
