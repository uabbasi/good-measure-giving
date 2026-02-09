---
name: llm-prompting
description: Expert guidance on LLM prompting patterns used in this project. Covers versioned prompts, schema enforcement, category calibration, multi-provider fallback, and narrative generation. Activates when working on prompts, LLM integration, or evaluation logic.
---

# LLM Prompting Expert

Deep expertise on the prompting infrastructure, patterns, and conventions used in this codebase.

---

## When This Skill Activates

- Writing or modifying prompts in `data-pipeline/src/llm/prompts/`
- Working on `NarrativeEvaluator`, `NarrativeJudge`, or scoring evaluators
- Debugging LLM outputs or schema validation
- Adding new LLM-powered features
- Optimizing prompt performance or cost

---

## Prompt Infrastructure

### Versioned Prompt System

**Location**: `data-pipeline/src/llm/prompts/`

**Format**: All prompts use frontmatter with version tracking:

```
# PROMPT: prompt_name
# VERSION: 1.0.0
# LAST_UPDATED: 2025-11-27
# DESCRIPTION: Brief description
# ---PROMPT_START---
[actual prompt content]
```

**Key features**:
- **SHA256 content hashing** (16-char truncated) detects unintended changes
- **Version check modes**: `warn`, `strict`, or `off`
- **Loader**: `prompt_loader.py` provides `load_prompt()`, `load_prompt_raw()`, `list_prompts()`

**Rule**: Content changes without version bumps trigger warnings/errors.

### Prompt Files

| File | Version | Purpose |
|------|---------|---------|
| `baseline_narrative.txt` | v3.0.0 | 150-200 word summaries |
| `rich_narrative.txt` | v1.3.0 | 500-800 word deep dives |
| `zakat_alignment.txt` | v1.0.0 | Zakat classification |
| `categories/*.txt` | varies | 16 category calibrations |

---

## LLM Client Architecture

### File: `data-pipeline/src/llm/llm_client.py`

**Multi-provider via LiteLLM**:
- Primary: Gemini 3.0 Pro/Flash
- Fallback: Claude 3.5 Sonnet, GPT-4

**Task-based model selection** (`LLMTask` enum):

| Task | Model | Reason |
|------|-------|--------|
| `NARRATIVE_GENERATION` | Gemini 3 Flash | Best quality/cost |
| `WEBSITE_EXTRACTION` | Gemini 3 Flash | Fast, cheap |
| `PDF_EXTRACTION` | Gemini 3 Flash | Document handling |
| `PREMIUM_NARRATIVE` | Gemini 3 Flash | Top charities |
| `EVALUATION_SCORING` | Gemini 3 Flash | LLM-as-judge |

**Fallback logic**:
- Transient errors (429, 503, rate limits): Try fallback model
- Permanent errors (auth, schema validation): Fail immediately
- Max 3 attempts per chain

**Safety settings disabled** (charity content is not harmful):
```python
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    ...
]
```

---

## Schema Enforcement

### Location: `data-pipeline/src/llm/schemas/`

All LLM outputs use **Pydantic models** with Gemini JSON schema enforcement:

```python
# In narrative_evaluator.py
response = llm_client.generate(
    prompt=formatted_prompt,
    json_schema={
        "name": "baseline_narrative",
        "schema": BaselineNarrative.model_json_schema()
    }
)
```

### Key Schemas

**BaselineNarrative** (150-200 words):
```python
class BaselineNarrative(BaseModel):
    charity_name: str
    summary: str  # 2-3 sentences
    tier_1_strategic_fit: Tier1StrategicFit
    tier_2_execution: Tier2Execution
    overall_score: int  # 0-100
    strengths: List[Strength]
    improvement_areas: List[ImprovementArea]
    zakat_guidance: ZakatGuidance
    confidence: Confidence
```

**Sub-score models**:
```python
class SubScore(BaseModel):
    score: int
    narrative: str  # Explain reasoning

class UmmahGapSubScores(BaseModel):
    replaceability: SubScore  # 0-8
    ummah_relevance: SubScore  # 0-6
    funding_gap: SubScore  # 0-6
```

**Validation**: Pydantic ensures type safety + sub-score sums match totals.

---

## Scoring Framework: AMAL Impact Matrix

### Embedded in prompts as calibration tables

**Tier 1: Strategic Fit (50 points)**

| Dimension | Range | Levels |
|-----------|-------|--------|
| Systemic Leverage | 0-30 | World-class → National → Regional → Local → Consumptive |
| Ummah Gap | 0-20 | 3 sub-scores: replaceability (0-8), ummah_relevance (0-6), funding_gap (0-6) |

**Tier 2: Execution (50 points)**

| Dimension | Range | Sub-scores |
|-----------|-------|------------|
| Operational Capability | 0-25 | governance (0-8), program_efficiency (0-8), deployment_capacity (0-6), track_record (0-3) |
| Mission Delivery | 0-25 | delivery_evidence (0-12), cost_effectiveness (0-8), learning_adaptation (0-5) |

**Key pattern**: Every score level has specific criteria with examples embedded in prompt.

---

## Category-Specific Calibration

### Location: `data-pipeline/src/llm/prompts/categories/`

16 category-specific guides inject **world-class benchmarks**:

**Example: HUMANITARIAN.txt**
```
## WORLD-CLASS BENCHMARKS
- MSF (Doctors Without Borders)
- ICRC (International Committee of the Red Cross)
- UNHCR
- World Food Programme
- Partners in Health

## SCORING CALIBRATION FOR HUMANITARIAN ORGS

### Systemic Leverage (0-30)
26-30: International treaty influence, paradigm-shifting models
20-25: Operating at scale ($100M+), policy influence
...
```

**How it works**:
1. `category_classifier.py` maps EIN → category via `config/charity_categories.yaml`
2. `NarrativeEvaluator` inserts category prompt before charity data
3. LLM calibrates scores against domain-specific benchmarks

**Categories** (16 total):
- HUMANITARIAN, BASIC_NEEDS, MEDICAL_HEALTH
- EDUCATION_K12_RELIGIOUS, EDUCATION_HIGHER_RELIGIOUS, EDUCATION_INTERNATIONAL
- RELIGIOUS_CONGREGATION, RELIGIOUS_OUTREACH
- CIVIL_RIGHTS_LEGAL, WOMEN'S_SERVICES, ADVOCACY_CIVIC
- ENVIRONMENT_CLIMATE, RESEARCH_POLICY, MEDIA_JOURNALISM
- PHILANTHROPY_GRANTMAKING, SOCIAL_SERVICES

---

## Prompt Templating

### Variable substitution pattern:

```python
prompt_template = load_prompt_raw("baseline_narrative")

formatted_prompt = prompt_template.format(
    charity_data=self._format_charity_data(charity),
    deterministic_scores=self._format_deterministic_scores(charity),
    category_section=self._get_category_section(charity)
)
```

### Variables:
- `{charity_data}`: Name, EIN, mission, financials, raw scraped data
- `{deterministic_scores}`: Pre-calculated Tier 2 sub-scores (LLM cannot change these)
- `{category_section}`: Category-specific benchmarks and calibration

### Intentional exclusions:
- Does NOT include: `amal_score`, `amal_rating`, `wallet_tag`
- Reason: Prevent anchoring; let LLM score fresh

---

## Deterministic Score Override

**Critical pattern**: Some scores are calculated deterministically, not by LLM.

```python
# In narrative_evaluator.py after LLM generation:

# Override LLM scores with deterministic values
narrative.tier_2_execution.operational_capability.governance = deterministic_governance
narrative.tier_2_execution.operational_capability.program_efficiency = deterministic_efficiency
narrative.tier_2_execution.operational_capability.deployment_capacity = deterministic_capacity
narrative.tier_2_execution.operational_capability.track_record = deterministic_track_record

# Recalculate all subtotals deterministically
narrative.recalculate_totals()
```

**Why**: Ensures reproducibility independent of LLM behavior. LLM provides rationales; code provides numbers.

---

## Zakat Classification: Self-Assertion

### Prompt: `zakat_alignment.txt`

**Pattern**: Trust what the charity claims, don't make independent rulings.

```
ZAKAT_ELIGIBLE: Charity explicitly claims zakat eligibility on website
SADAQAH_STRATEGIC: No zakat claim BUT tier_1_strategic_fit.subtotal > 35
SADAQAH_ONLY: No zakat claim AND tier_1_strategic_fit.subtotal <= 35
```

**8 Asnaf** embedded in prompt:
1. Al-Fuqara (the poor)
2. Al-Masakin (the destitute)
3. Al-Amileen (zakat administrators)
4. Al-Muallafatul Quloob (hearts to be reconciled)
5. Fi Al-Riqab (freeing from bondage)
6. Al-Gharimeen (those in debt)
7. Fi Sabilillah (in Allah's cause)
8. Ibn Al-Sabil (stranded travelers)

**Required disclaimer**: "This analysis is informational only and does NOT constitute a fatwa."

---

## LLM-as-Judge Quality Gating

### File: `narrative_judge.py`

**5 dimensions** (each 0-100):

| Dimension | Weight | What it checks |
|-----------|--------|----------------|
| Factual Accuracy | 30% | Claims match source data? |
| Completeness | 20% | Required fields populated? |
| Coherence | 20% | Internally consistent? |
| Tone/Style | 15% | Donor-facing voice? |
| Zakat Validity | 15% | Classification defensible? |

**Routing thresholds**:
- ≥ 85: Auto-approve
- 60-84: Human review
- < 60: Auto-reject

**Important**: Judge provides **quality metrics only**, not routing decisions.

---

## Evidence Citation Pattern

Every claim requires structured evidence:

```python
class Evidence(BaseModel):
    claim: str           # The claim being made
    source: str          # "Form 990", "Charity Navigator", "Website"
    source_year: int     # Year of data
    field: str           # Specific field from source
    value: str           # Actual value
    confidence: str      # "HIGH", "MEDIUM", "LOW"
```

**Prompt principle**: "Every claim MUST cite source and year."

---

## Retry & Validation

### Generation retry loop (max 3 attempts):

```python
for attempt in range(MAX_GENERATION_RETRIES):
    response = llm_client.generate(prompt, json_schema=schema)

    # Validation checks:
    narrative = BaselineNarrative.model_validate_json(response)
    validate_sub_score_sums(narrative)
    density = calculate_information_density(narrative)

    if density >= 0.80:
        return narrative

    # Retry with feedback
    prompt = add_density_feedback(prompt, density)
```

### Information density check:
- Counts populated fields vs total schema fields
- Threshold: 0.80 (80% of fields must be populated)
- Below threshold → human review or retry

---

## Cost Tracking

Every LLM call logs:
```python
class LLMResponse:
    model_version: str
    prompt_version: str
    prompt_hash: str
    db_snapshot_version: str
    timestamp: datetime
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
```

**Model registry** in `llm_client.py` includes pricing for 30+ models.

---

## Prompt Engineering Patterns

| Pattern | How It's Used |
|---------|---------------|
| Chain-of-thought | Each dimension has `narrative` field explaining reasoning |
| Scoring rubrics | Detailed 5-7 level tables embedded in prompts |
| Few-shot examples | Real org comparisons (MSF, Water.org, ACLU) |
| Low temperature | `temperature=0.3` for consistent output |
| Schema enforcement | JSON mode ensures exact structure |
| Category calibration | Domain-specific benchmarks injected |
| Self-assertion | Zakat based on charity's claim, not judgment |
| Deterministic fallback | Critical scores calculated outside LLM |

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `prompt_loader.py` | Load/validate/version prompts |
| `llm_client.py` | Unified LLM interface + model registry |
| `narrative_evaluator.py` | Generate narratives with schema enforcement |
| `narrative_judge.py` | Quality gating (metrics only) |
| `baseline_narrative.txt` | Main prompt (v3.0.0) |
| `categories/*.txt` | 16 category calibrations |
| `schemas/baseline.py` | BaselineNarrative Pydantic model |
| `schemas/judge.py` | JudgeResult model |

---

## Anti-Patterns

### Don't:
- Change prompt content without bumping version
- Let LLM determine scores that should be deterministic
- Skip schema validation
- Use high temperature for scoring tasks
- Embed specific charity data in prompt templates
- Make fatwa-like zakat rulings (use self-assertion)

### Do:
- Version all prompts with frontmatter
- Embed calibration tables directly in prompts
- Use category-specific benchmarks
- Validate sub-score sums match totals
- Log all LLM calls with full metadata
- Provide chain-of-thought fields for reasoning
