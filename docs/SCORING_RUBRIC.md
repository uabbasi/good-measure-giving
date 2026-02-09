# How AMAL Scores Charities

AMAL evaluates charities across four dimensions, weighted equally, with deductions for red flags.

**Score = Trust + Evidence + Effectiveness + Fit + Risk**

| Dimension | Points | The Question |
|-----------|--------|-------------|
| Trust | 0–25 | Can we believe what they claim? |
| Evidence | 0–25 | Does the program actually work? |
| Effectiveness | 0–25 | How much good does each dollar do? |
| Fit | 0–25 | Is this the right choice for Muslim donors? |
| Risk | −10 to 0 | Red flag deductions |

| Score | Meaning |
|-------|---------|
| 85–100 | Exceptional |
| 70–84 | Strong |
| 55–69 | Good |
| 40–54 | Fair |
| Below 40 | Caution |

---

## Trust (25 pts)

Trust is foundational. Without reliable information, nothing else can be evaluated.

**Verification (10 pts)** — Has this charity been independently vetted? We check Charity Navigator, Candid/GuideStar, and the BBB Wise Giving Alliance. Two or more strong signals = 10 pts. One = 7. Listed anywhere = 4. Nothing = 0.

**Data Quality (8 pts)** — How many independent sources confirm what we know? Four or more = 8 pts. Two to three = 5. One = 2. Conflicting sources = 0.

**Transparency (7 pts)** — Does the charity proactively share information? Based on Candid seal level: Platinum (7), Gold (5), Silver (4), Bronze (2), None (0). Charities without a Candid seal but with rich website disclosure can earn Bronze-equivalent credit.

> **Known limitation:** Candid seals and Charity Navigator ratings correlate with organizational size and professionalization. Smaller charities may score lower on Trust due to limited reporting infrastructure, not untrustworthiness. Narratives flag when this is likely the case.

## Evidence (25 pts)

Evidence separates charities that *assert* impact from those that *demonstrate* it.

**Evidence Grade (10 pts)** — How strong is the proof? Ranges from Grade A (third-party evaluation with published methodology, 10 pts) down to Grade F (no outcome data, 2 pts). We don't require RCTs — longitudinal studies, pre/post comparisons, and other rigorous methods all count. New organizations and research/advocacy orgs use adapted rubrics.

**Outcome Measurement (10 pts)** — Does the charity track whether lives actually improve? Comprehensive tracking (3+ years, documented methods, third-party verified) earns 10. No structured tracking earns 2.

**Theory of Change (5 pts)** — Can the charity articulate *how* its work leads to impact? A published theory of change earns 5. No explanation earns 0.

**Bonuses** — Up to +2 for outcome data extracted from annual report PDFs, and +1 if Candid shows 3+ years of consistent tracking. Total capped at 25.

> **Known limitation:** Evidence grades favor organizations with monitoring & evaluation capacity. A small charity doing excellent work in a refugee camp may lack the resources to hire evaluators or publish outcome reports. Low evidence scores reflect limited documentation infrastructure, not necessarily weak programs. When this applies, charity narratives include a "Capacity-limited evidence" flag.

## Effectiveness (25 pts)

Two charities might both work, but if one achieves the same results at half the cost, donors help twice as many people.

**Cost Per Beneficiary (up to 15 pts)** — How much does it cost to help one person? Because feeding someone a meal costs less than performing surgery, we use cause-adjusted benchmarks — different standards for different types of work. When cause-specific data isn't available, we fall back to general benchmarks (max 12 pts) or an efficiency proxy (max 9 pts). Charities in active conflict zones get a 1.5x threshold multiplier — serving people in war zones is inherently more expensive. See [Appendix: Cost Benchmarks](#appendix-cost-benchmarks) for the full table.

**Financial Health (5 pts)** — Does the charity have stable finances? The sweet spot is 1–6 months of reserves (5 pts). Under 1 month is risky (3 pts). Over 12 months suggests hoarding (2 pts).

**Program Expense Ratio (5 pts, floor only)** — What percentage of spending goes directly to programs? This is a floor check, not a quality signal. 65%+ = 5 pts (neutral — meets baseline). 50–64% = 3. Under 50% = 0. High program ratios earn no bonus; they are expected, not rewarded.

> **Methodology note:** Program expense ratio is used as a risk indicator only, not a positive signal of effectiveness. This aligns with GiveWell's cost-per-outcome modeling and Charity Navigator's shift toward Impact & Measurement beacons over financial ratios. High overhead can signal healthy investment in staff, M&E, scaling, and talent — not waste. The "overhead myth" penalizes charities that invest in organizational capacity.

## Fit (25 pts)

AMAL's audience is Muslim donors, many fulfilling zakat. Fit ensures we're not just recommending "generically good" charities.

**Counterfactual Impact (10 pts)** — Would this charity get funded without you? Zakat-accepting charities serve a donor base underrepresented in mainstream philanthropy (10 pts). Large mainstream charities will get funded regardless (2 pts).

**Cause Importance (9 pts)** — How urgent is the problem? Global health, humanitarian crises, and extreme poverty score highest (9). Religious/cultural programs score lowest (2) — not because they're unimportant, but because this dimension measures urgency of suffering.

**Neglectedness (6 pts)** — Is this an underfunded space? Muslim-focused charities (6 pts) are underserved by mainstream philanthropy. Large organizations with $10M+ revenue (2 pts) already attract broad donor support.

## Risk (up to −10 pts)

Risk factors are deductions, not a positive dimension. The baseline expectation is zero red flags.

| Red Flag | Deduction |
|----------|-----------|
| Program spending <50% | −5 |
| Reserves <1 month | −2 |
| Board <3 members | −5 |
| No outcome tracking | −2 |
| No theory of change | −1 |

Total deductions are capped at −10. Conflict zone operations are never penalized.

## Wallet Tags

Separate from the score. Every charity gets one:

- **ZAKAT-ELIGIBLE** — Claims to accept and distribute zakat per Islamic guidelines
- **SADAQAH-ELIGIBLE** — Appropriate for voluntary charity; doesn't claim zakat compliance

A charity can be ZAKAT-ELIGIBLE with a low score, or high-scoring but SADAQAH-ELIGIBLE. Wallet tags are determined by explicit zakat acceptance (dedicated zakat page, zakat calculator, or specific zakat fund) — not by Islamic-sounding names or generic donation buttons. A denylist of 60+ organizations prevents misclassification.

---

# Appendix: Cost Benchmarks

When we know a charity's cost per beneficiary and its cause area, we compare against cause-specific benchmarks. This is the most precise comparison — a food charity is judged against other food charities, not against surgery programs.

These benchmarks are anchored to sector-leading programs (referenced below). Actual cost-effectiveness varies significantly by context, geography, and program maturity. Thresholds carry approximately ±30% uncertainty and should be read as comparative guides, not absolute verdicts. As our dataset grows, we will layer in percentile ranking within cause areas as a primary signal.

> **Important distinction:** These benchmarks measure operational cost per direct beneficiary served. This is different from modeled cost per marginal life saved (as used by GiveWell), which includes counterfactual adjustment and all indirect costs. Both are useful measures; they answer different questions.

| Cause Area | Excellent (15) | Good (12) | Average (8) | Below Avg (3) | Reference Programs |
|------------|---------------|----------|-------------|---------------|-------------------|
| Food & Hunger (per meal) | <$0.25 | $0.25–0.50 | $0.50–1.00 | >$1.00 | Feeding America, WFP, Global FoodBanking Network |
| Education (per student/yr) | <$100 | $100–300 | $300–750 | >$750 | Pratham (~$10–100), BRAC (~$30–50), Room to Read |
| Healthcare — Primary (per patient) | <$25 | $25–75 | $75–150 | >$150 | Against Malaria Foundation (~$6), Helen Keller Intl (~$2) |
| Healthcare — Surgery (per patient) | <$500 | $500–1,500 | $1,500–4,000 | >$4,000 | Mercy Ships (~$300–1,500), remote cataract programs (~$25–100) |
| Humanitarian (per beneficiary) | <$75 | $75–175 | $175–400 | >$400 | UNHCR (~$50/person), Islamic Relief (~$50–150) |
| Extreme Poverty / Global South | <$50 | $50–150 | $150–400 | >$400 | GiveDirectly, BRAC Ultra-Poor Graduation |
| Domestic Poverty / US & Europe | <$200 | $200–500 | $500–1,200 | >$1,200 | Regional food banks, housing-first programs |
| Religious/Cultural | <$50 | $50–125 | $125–300 | >$300 | Community education programs |

**Conflict zone adjustment:** Charities operating in active conflict zones (Syria, Yemen, Gaza, Sudan, Afghanistan, DRC, Somalia, Myanmar, Ukraine) get a 1.5x threshold multiplier — serving people in war zones is inherently more expensive.

**Fallback methods** when cause-specific benchmarks can't be applied:

| Method | When Used | Max Pts |
|--------|-----------|---------|
| General benchmarks | Know cost but not cause area | 12 |
| Efficiency proxy | No cost data; use program expense ratio | 9 |
| Unknown | No financial data at all | 0 |

---

# Appendix: Known Limitations & Methodology Choices

**Transparency metrics correlate with organizational size.** Candid seals, Charity Navigator ratings, and audited financials require resources that smaller organizations may not have. A low Trust score can reflect limited reporting capacity rather than untrustworthiness. We flag this in charity narratives when detected.

**Evidence grades favor M&E capacity.** Third-party evaluations cost $10K–$50K+. Small charities doing effective work may score lower on Evidence simply because they can't afford evaluators. Track-specific rubrics partially address this (new organizations with a published theory of change and pilot data can earn Grade A), but the bias toward documented impact remains.

**Cost benchmarks are comparative, not absolute.** Thresholds are anchored to sector-leading programs and carry ±30% uncertainty. They measure operational cost per direct beneficiary — not modeled cost per life saved (which would require counterfactual analysis beyond our current scope). As the dataset grows past ~300 charities, percentile ranking within cause areas will supplement absolute benchmarks.

**LLM-assisted extraction has safeguards but isn't perfect.** Website content is extracted using AI models with a hallucination denylist covering 8 high-risk fields (zakat eligibility, cost per beneficiary, external evaluations, scholarly endorsements, third-party evaluation status, impact multiplier, evidence quality, populations served). These fields require corroboration from non-website sources before being accepted. Conflicting data across sources is flagged for review.

**Program expense ratio is not a quality signal.** We use it as a floor check only. High overhead can reflect healthy investment in talent, monitoring, and organizational capacity. This aligns with the broader shift among evaluators (GiveWell, Charity Navigator's Impact beacon) away from the "overhead myth."
