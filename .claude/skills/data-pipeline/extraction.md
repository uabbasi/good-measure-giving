# Data Extraction

Capture broadly, filter later. Re-crawling is expensive.

---

## Data Source Hierarchy

### Tier 1: Authoritative (Highest Trust)
| Source | Contains | Freshness |
|--------|----------|-----------|
| IRS Form 990 | Financials, officers, programs | 12-24 month lag |
| Audited financials | Verified numbers | Annual |
| State registrations | Legal filings | Varies |

### Tier 2: Official Charity Sources
| Source | Contains | Freshness |
|--------|----------|-----------|
| Annual reports | Narrative + metrics | Annual |
| Website - About | Mission, leadership | Irregular |
| Website - Programs | Service descriptions | Moderate |

### Tier 3: Aggregators
| Source | Contains | Notes |
|--------|----------|-------|
| Charity Navigator | Ratings, accountability | Derived from 990s |
| GuideStar/Candid | Profiles, seals | Self-reported |
| ProPublica | 990 data, searchable | 990 lag |

---

## 5 Pipeline Collectors

| Source | File | Location |
|--------|------|----------|
| Charity Navigator | `charity_navigator.py` | `src/collectors/` |
| ProPublica | `propublica.py` | `src/collectors/` |
| Candid | `candid_beautifulsoup.py` | `src/collectors/` |
| CauseIQ | `causeiq.py` | `src/collectors/` |
| Website | `web_collector.py` | `src/collectors/` |

**Architecture**: `DataCollectionOrchestrator` → ThreadPoolExecutor (10 workers) → per-source isolation.

---

## What to Extract

### Always Extract (Current Needs)

**Identity**: Legal name, EIN, founding date, NTEE code, geographic scope

**Financial**: Revenue/expenses (3-year trend), program/admin/fundraising ratios, net assets, revenue breakdown

**Programs**: All programs (not just top 3), descriptions, expenses per program, target populations

**Impact**: Beneficiary counts (annual + cumulative), cost per beneficiary, outcome metrics

**People**: Board members, executives, compensation, staff count

### Also Extract (Future-Proofing)

Strategic plans, partnerships, accreditations, office locations, donation options, social media presence, compliance policies

---

## Website Anatomy

```
/about, /about-us, /who-we-are
├── /mission, /history, /team, /board
/programs, /what-we-do
├── /[program-name], /where-we-work
/impact, /results
├── /annual-report, /financials, /stories
/donate, /give
├── /monthly-giving, /planned-giving
```

---

## Extraction Patterns

### Numeric Data - Capture Context

```python
# Bad
"50,000"

# Good
{
    "value": 50000,
    "unit": "meals",
    "time_period": "FY2023",
    "cumulative": False,
    "source": "Annual Report p.12"
}
```

### Handling Missing Data

```python
{
    "beneficiaries_served": None,
    "beneficiaries_served_available": False,
    "beneficiaries_served_notes": "Not disclosed"
}
```

Never fabricate. Distinguish "zero" from "not reported".

---

## Red Flags to Note

### Financial
- Program expense ratio < 65%
- Fundraising > 35%
- Related party transactions
- Loans to officers

### Governance
- Board < 5 members
- No independent directors
- Family-dominated board
- Missing audit (if >$500k revenue)

### Transparency
- No 990 on website
- Vague program descriptions
- No impact metrics
- Outdated website (>2 years)

**Extract but flag** - don't skip charities with red flags.

---

## Source-Specific Tips

**Charity Navigator**: Overall score, financial score, advisories, Beacon designation

**GuideStar/Candid**: Seal level (Bronze→Platinum), last update date

**BBB Wise Giving**: 20 standards checklist

**Websites**: Check meta tags, schema.org data, robots.txt, Archive.org for history
