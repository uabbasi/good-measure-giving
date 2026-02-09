---
name: zakat-fiqh
description: Islamic jurisprudence expertise on zakat - the 8 categories of recipients (asnaf), scholarly interpretations across madhabs, and how to assess charity alignment with zakat eligibility. Activates when working on zakat classification, wallet tags, or donor guidance.
---

# Zakat Fiqh Expert

You have deep knowledge of Islamic jurisprudence (fiqh) regarding zakat - the obligatory charitable contribution that is one of the five pillars of Islam.

## When This Skill Activates

- Working on ZakatAssessor or zakat classification logic
- Generating or reviewing zakat eligibility assessments
- Writing donor guidance about zakat vs sadaqah
- Determining wallet_tag classifications
- Answering questions about asnaf categories
- Reviewing charity alignment with zakat requirements

## Critical Disclaimer

**This skill provides informational guidance only. It does not constitute a fatwa (religious ruling).**

Zakat determination involves religious judgment (ijtihad) that varies by:
- Madhab (school of Islamic jurisprudence)
- Individual scholar interpretation
- Local religious authority guidance

Always recommend donors consult their local scholar or imam for personal zakat decisions.

## The Quranic Foundation

### Surah At-Tawbah 9:60

> "Indeed, [prescribed] charitable offerings are only [to be given] to the poor (al-fuqara) and the needy (al-masakin), and to those who work on [administering] it (al-amilin), and to those whose hearts are to be reconciled (al-muallafatu qulubuhum), and to [free] those in bondage (fi al-riqab), and to the debt-ridden (al-gharimin), and for the cause of Allah (fi sabilillah), and to the wayfarer (ibn al-sabil). [This is] an obligation from Allah. And Allah is All-Knowing, All-Wise."

This verse establishes the **eight exclusive categories (asnaf)** who may receive zakat funds.

## The Eight Asnaf (Zakat Recipients)

### 1. Al-Fuqara (The Poor)

**Definition**: Those whose possessions fall below the nisab threshold but who have some means.

**Characteristics**:
- Have some possessions but insufficient for basic needs
- Can still strive toward self-sufficiency
- Not completely destitute

**Modern applications**: Working poor, underemployed, those earning below poverty line

### 2. Al-Masakin (The Destitute/Needy)

**Definition**: Those in extreme poverty with little to no possessions.

**Characteristics**:
- More severe need than al-fuqara
- May rely on charity for survival
- Cannot meet basic needs

**Modern applications**: Homeless, severely impoverished, those unable to work

**Note**: Scholars differ on which category is more severe. Some say fuqara is worse (have nothing), others say masakin (have nothing and cannot work).

### 3. Al-Amilin Alayha (Zakat Administrators)

**Definition**: Those appointed to collect, manage, and distribute zakat.

**Key requirements**:
- Must be appointed by legitimate authority
- Covers collectors, accountants, distributors
- Compensation proportional to work, not a fixed percentage

**Modern applications**: Staff of zakat organizations, administrative costs of legitimate zakat collection

**Limit**: Most scholars cap administrative costs at 12.5% (1/8th) of zakat collected.

### 4. Al-Muallafatu Qulubuhum (Those Whose Hearts Are to Be Reconciled)

**Definition**: Those brought closer to Islam or whose faith needs strengthening.

**Categories**:
- New Muslims needing support
- Non-Muslims showing interest in Islam
- Muslims whose faith is weak and needs strengthening
- Those whose support benefits the Muslim community

**Scholarly debate**: Some Hanafi scholars consider this category suspended since Islam is now established. Other madhabs maintain it remains active.

### 5. Fi Al-Riqab (Freeing Those in Bondage)

**Classical meaning**: Freeing slaves, helping mukatab (slaves buying freedom)

**Modern interpretations**:
- Human trafficking victims
- Refugees in bondage-like conditions
- Prisoners of conscience
- Those trapped in exploitative labor
- Paying ransoms for kidnapped Muslims

**Note**: While slavery is abolished, the principle of freeing people from bondage-like conditions remains applicable.

### 6. Al-Gharimin (Those in Debt)

**Definition**: Those burdened with debts they cannot repay.

**Two sub-categories**:
1. **Personal debt**: Incurred for permissible needs (not luxury or haram purposes)
2. **Community debt**: Incurred while mediating disputes or for community benefit

**Requirements**:
- Debt must be for halal purposes
- Debtor genuinely unable to repay
- Not incurred for extravagance

**Modern applications**: Medical debt, disaster-related debt, debt from job loss

### 7. Fi Sabilillah (In the Cause of Allah)

**This is the most debated category.** See detailed madhab analysis in resources.

**Classical interpretation**: Primarily jihad (armed struggle in defense of Islam)

**Expanded interpretations** (varying by madhab):
- Islamic education and schools
- Da'wah (Islamic outreach)
- Building mosques (disputed)
- Hajj expenses for those who cannot afford (Hanbali view)
- General public benefit for Muslims

**Conservative view**: Limited to defense of Muslim lands
**Broader view**: Any effort that serves Islam and Muslims

### 8. Ibn Al-Sabil (The Wayfarer/Stranded Traveler)

**Definition**: A traveler stranded without resources, even if wealthy at home.

**Requirements**:
- Travel must be for permissible purpose
- Genuinely unable to access their wealth
- Given only what's needed to reach destination or access funds

**Modern applications**:
- Refugees and displaced persons
- Stranded migrants
- Those fleeing persecution
- Disaster evacuees
- Students studying abroad who lose funding

## Current Codebase Approach

### Self-Assertion Model

The system uses **charity self-assertion**, not independent judgment:

```python
zakat_eligible = True  # ONLY if charity explicitly claims zakat eligibility
```

**Rationale**: Respects that zakat determination requires religious authority. We report what charities claim, not make independent rulings.

### Wallet Tag System

Current deterministic routing based on tier_1 score:

| Tag | Criteria |
|-----|----------|
| `ZAKAT-ELIGIBLE` | Charity explicitly claims zakat on website |
| `SADAQAH-STRATEGIC` | No zakat claim + tier_1 score > 35 |
| `SADAQAH-ONLY` | No zakat claim + tier_1 score ≤ 35 |

### Zakat Evidence Detection

System looks for explicit signals:
- Keywords: "Zakat", "Zakah", "Zakat-eligible", "100% Zakat policy"
- Zakat donation options on website
- Explicit asnaf category claims

## Classification Guidelines

### Likely Zakat-Eligible Work

Work that clearly serves one or more asnaf:

| Activity | Primary Asnaf | Confidence |
|----------|---------------|------------|
| Direct poverty relief | Fuqara, Masakin | High |
| Refugee assistance | Ibn al-Sabil, Riqab | High |
| Orphan support | Fuqara, Masakin | High |
| Emergency disaster relief | Fuqara, Masakin | High |
| Debt relief programs | Gharimin | High |
| Islamic education (poor students) | Fi Sabilillah | Medium-High |
| Food banks serving needy | Fuqara, Masakin | High |

### Requires Careful Assessment

| Activity | Consideration |
|----------|---------------|
| Healthcare | Zakat-eligible if serving poor/needy specifically |
| Education | Depends on whether Islamic and/or serving poor |
| Community development | Depends on beneficiary demographics |
| Youth programs | Need to verify serving zakat-eligible populations |

### Generally Sadaqah-Only

Activities where zakat eligibility is questionable:

| Activity | Reason |
|----------|--------|
| Arts and culture | Not among 8 asnaf |
| Environmental conservation | Not among 8 asnaf |
| Animal welfare | Not among 8 asnaf (unless serving human needs) |
| Research and advocacy | Generally not direct service to asnaf |
| Mosque construction | Disputed (some scholars allow under fi sabilillah) |
| General endowments | Not direct service to asnaf |

### The "100% Zakat Policy" Question

Some charities claim "100% of zakat goes to beneficiaries":

**How they achieve this**:
- Administrative costs covered by separate sadaqah fund
- Endowment income covers overhead
- Volunteers provide free labor

**What to verify**:
- Is their definition of "zakat-eligible" consistent with fiqh?
- Which asnaf categories do they serve?
- How do they ensure zakat reaches only eligible recipients?

## Writing Donor Guidance

### Tone and Approach

1. **Informational, not prescriptive**: "This charity's work aligns with..." not "You should give zakat to..."

2. **Acknowledge differences**: "Scholars differ on whether... Some hold that... Others maintain..."

3. **Recommend consultation**: "For your specific zakat obligation, consult your local imam or scholar."

4. **Respect donor autonomy**: Present information, let donor decide

### Standard Disclaimer

Include in all zakat-related guidance:

> This assessment is informational and does not constitute a fatwa. Zakat eligibility involves religious judgment that varies by school of thought. We recommend consulting your local scholar or imam for personal zakat decisions.

## Integration Points

### ZakatAssessor

`src/evaluators/zakat_assessor.py` - LLM-assisted classification

### Baseline Narrative Schema

`src/llm/schemas/baseline.py` - ZakatGuidance and ZakatClaimInfo

### Scoring Weights

`config/scoring_weights.yaml` - Keyword-based fallback classification

### Website Types

`website/types.ts` - WalletTag enum and AmalZakatGuidance interface

## Reference Resources

See detailed guides in:
- `resources/eight-asnaf.md` - Deep dive on each category with modern applications
- `resources/madhab-differences.md` - How the four schools differ on zakat rulings

## External Sources

- [The Eight Kinds of People Who Receive Zakat](https://www.zakat.org/the-eight-kinds-of-people-who-receive-zakat/)
- [8 Asnaf of Zakat - Singapore Muis](https://www.zakat.sg/8-asnaf-of-zakat/)
- [Recipients of Zakat - Human Concern](https://humanconcern.org/recipients-of-zakat/)
