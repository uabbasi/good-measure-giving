export type FaqCategory = 'general' | 'methodology' | 'ai' | 'zakat' | 'data';

export interface FaqItem {
  q: string;
  a: string;
  category: FaqCategory;
}

export const FAQ_ITEMS: FaqItem[] = [
  // General
  {
    category: 'general',
    q: "Why do you need a specific evaluator for Muslim charities?",
    a: "General charity evaluators often miss nuances important to our community. They usually don\u2019t track whether a charity publicly says it accepts Zakat, may unfairly penalize organizations working in conflict zones like Gaza or Syria, and often overlook smaller grassroots organizations that serve Muslim communities. We built this to fill that gap."
  },
  {
    category: 'general',
    q: "Is Good Measure Giving affiliated with any charity?",
    a: "No. We are completely independent. We do not accept payments from charities to be listed or to influence their scores. Our goal is to serve donors, not organizations."
  },
  {
    category: 'general',
    q: "How is this different from Charity Navigator or Candid?",
    a: "Those are excellent resources that we actually use as data sources. But they focus primarily on financial metrics like overhead ratios. We go further by evaluating two dimensions: Impact (how effectively does this charity use donations to create change?) and Alignment (is this the right charity for Muslim donors?). We also provide donation-routing guidance for Zakat vs. Sadaqah, plus a Data Confidence signal that other evaluators don\u2019t offer."
  },
  {
    category: 'general',
    q: "Can I request a charity to be evaluated?",
    a: "Yes! Use the \u2018Suggest a Charity\u2019 option in our feedback form, available in the footer or on the browse page. Include the organization\u2019s name and EIN if available. You can also email us at hello@goodmeasuregiving.org. Priority is given to registered 501(c)(3) organizations serving Muslim communities."
  },
  {
    category: 'general',
    q: "Do you evaluate mosques and Islamic centers?",
    a: "We primarily evaluate 501(c)(3) charitable organizations with standard public filings, but we do include some Islamic centers and mosque-like organizations when enough reliable data is available. Coverage is still strongest where Form 990 and third-party profile data are robust, so some congregational organizations remain harder to assess confidently."
  },

  // Methodology
  {
    category: 'methodology',
    q: "What is the GMG Score?",
    a: "The GMG Score is our 0-100 rating built from two dimensions, each worth 50 points: Impact (how effectively does this charity use donations to create measurable change?) and Alignment (is this the right charity for Muslim donors?). We also apply risk deductions (up to -10 points) for serious concerns like very low program spending or governance problems. Alongside the score, a Data Confidence signal (High, Medium, or Low) tells you how much public data supports the evaluation. Scores above 75 indicate exceptional performance, while many organizations cluster in the middle score bands."
  },
  {
    category: 'methodology',
    q: "Why do I see qualitative labels instead of a big number?",
    a: "We intentionally prioritize qualitative signals to avoid false precision. A charity now shows an archetype (what kind of organization it is), an evidence stage (Verified, Established, Building, or Limited Evidence), four signal states (Evidence, Financial Health, Donor Fit, Risk), and a recommendation cue (Maximum Alignment, Strong Alignment, Mixed Signals, or Needs Verification). The numeric score still exists and is available in collapsed methodology details, but it is no longer the primary cue for browsing."
  },
  {
    category: 'methodology',
    q: "What does \u201cSovereignty Builder\u201d mean?",
    a: "Sovereignty Builder is an archetype for organizations focused on Muslim civic power and representation. These groups typically work on voter engagement, policy influence, legal rights, or institution-building so communities can shape decisions that affect their lives."
  },
  {
    category: 'methodology',
    q: "What does \u2018Impact\u2019 measure?",
    a: "Impact (50 points) assesses organizational health indicators that research associates with effective programs. We score the same seven components for every charity (cost per beneficiary, directness, financial health, program ratio, evidence/outcomes, theory of change, governance), but the exact weights are archetype-adjusted by charity type. Most sub-components (financial health, governance, program ratio) are organizational health indicators rather than direct outcome measurements. Where charities provide verified outcome data through independent evaluation, we weight it more heavily. Evidence quality is assessed on a five-level scale: Verified (independent third-party evaluation), Tracked (3+ years of outcome data), Measured (1-2 years of data), Reported (basic output tracking only), and Unverified (no structured tracking)."
  },
  {
    category: 'methodology',
    q: "What does \u2018Alignment\u2019 measure?",
    a: "Alignment (50 points) measures whether this charity is the right match for Muslim donors. The largest component is Muslim donor fit (19 points), followed by cause urgency (13 points). We also evaluate underserved space (7 points) \u2014 is this need overlooked by mainstream philanthropy? \u2014 track record and organizational history (6 points), and funding gap (5 points) \u2014 would your donation make more difference here than elsewhere? Muslim-focused charities often score higher because they serve communities overlooked by mainstream funders."
  },
  {
    category: 'methodology',
    q: "Why don\u2019t you just use overhead ratios like other evaluators?",
    a: "Because overhead ratios can be misleading. An organization can have a 95% program expense ratio while doing something ineffective. Conversely, a legal advocacy organization might have higher administrative costs because lawyers are expensive \u2014 but still deliver major impact. We include program ratio as one part of Impact, but we also score cost-effectiveness, outcomes evidence, financial health, theory of change, and governance. In short: we evaluate whether programs work, not just how spending is labeled."
  },
  {
    category: 'methodology',
    q: "How do you handle charities working in conflict zones?",
    a: "We explicitly account for the higher costs of operating in places like Gaza, Syria, Yemen, or other difficult environments. Security, logistics, and compliance costs are legitimately higher in these areas. Our cost-per-beneficiary benchmarks are cause-adjusted and include conflict-zone adjustments, so organizations aren\u2019t penalized for necessary operating conditions."
  },

  // AI & Technology
  {
    category: 'ai',
    q: "Do you use AI to evaluate charities? How can I trust that?",
    a: "Yes, we use AI to process data consistently. Here\u2019s the division of labor: AI reads and extracts structured data from IRS 990 filings, rating agencies, and websites. Deterministic code calculates all scores \u2014 the AI never assigns point values. AI generates narrative summaries that cite specific sources. Automated validators flag conflicts between sources. What AI does NOT do: make scoring decisions (code handles that), issue religious rulings (our Zakat classifications are informational only), or invent data (every claim must cite a verifiable source)."
  },
  {
    category: 'ai',
    q: "How do you discover information about charities?",
    a: "We use a technique called \u2018Grounded Search\u2019 \u2014 instead of manually crawling thousands of web pages, we search for specific answers: \u2018Does this charity accept zakat?\u2019, \u2018Has this charity been independently evaluated?\u2019, \u2018What outcomes does this charity track?\u2019 This finds information from news articles, foundation databases, and academic papers that we\u2019d never find by just scraping the charity\u2019s website. It\u2019s much faster than traditional web crawling, and discovers things the charity might not advertise on their homepage."
  },
  {
    category: 'ai',
    q: "How do you prevent AI hallucinations?",
    a: "Multiple safeguards work together: (1) Every factual claim must cite a source you can verify yourself (IRS filings, Charity Navigator, etc.). (2) We maintain a \u2018denylist\u2019 of high-risk fields (public zakat-acceptance claims, cost-per-beneficiary) that get extra scrutiny. (3) After narratives are generated, specialized \u2018judge\u2019 AIs audit them \u2014 checking citations exist and support claims, testing that URLs work, verifying facts against source data. (4) If validation fails, the evaluation fails \u2014 we don\u2019t publish fallback narratives. (5) All scoring uses deterministic code, never AI judgment."
  },
  {
    category: 'ai',
    q: "What if the AI makes a mistake?",
    a: "We have several safeguards: every factual claim cites a source you can verify yourself (IRS filings, Charity Navigator profiles, etc.), automated validators check for conflicts between sources, all scoring uses deterministic code (same data = same score every time), and community members can report errors for investigation. If you find an error, please email us at hello@goodmeasuregiving.org with specifics \u2014 we\u2019ll investigate and update the evaluation if warranted. Our goal is accuracy, not defending AI-generated content."
  },
  {
    category: 'ai',
    q: "Why not just have humans do all the evaluations?",
    a: "Human evaluators have biases and limited capacity. A single human evaluator might be harsher in the afternoon, unconsciously favor certain types of organizations, or simply lack time to research 100+ charities thoroughly. Our approach uses AI to extract data consistently, then deterministic code to score every charity against identical criteria. This produces more consistent evaluations than human-only approaches. We\u2019re transparent that this is an automated system \u2014 the tradeoff is scale and consistency versus the nuanced judgment a human expert might provide. That\u2019s why we cite sources: so you can verify claims yourself."
  },
  {
    category: 'ai',
    q: "Can I see the actual prompts you use?",
    a: "Yes. We publish our core prompts and prompt annotations at /prompts \u2014 including data extraction, narrative generation, and quality validation flows. You can inspect how we instruct models and where additional prompt coverage is still being added. We currently list 14 active prompts and 16 planned category-specific calibration prompts."
  },

  // Zakat
  {
    category: 'zakat',
    q: "How do you determine if a charity \u2018Accepts Zakat\u2019?",
    a: "We use a self-assertion model: if a charity explicitly says on its website that it accepts Zakat, we label it \u2018Accepts Zakat.\u2019 We verify that this public claim appears on the charity\u2019s official website. We also note which of the eight asnaf categories (Zakat recipients) their work appears to target. We do not issue our own rulings on whether giving to that charity counts as valid Zakat for your madhab \u2014 that\u2019s for qualified scholars and the charity itself to address."
  },
  {
    category: 'zakat',
    q: "Can I give Zakat to non-Muslim beneficiaries?",
    a: "This is a matter of scholarly debate. The majority of classical scholars restrict Zakat to Muslim beneficiaries, though some contemporary scholars permit giving to non-Muslims in certain categories (like \u2018those whose hearts are to be reconciled\u2019). Our platform labels charities based on their stated policies, but we recommend consulting with a scholar for your specific madhab\u2019s ruling."
  },
  {
    category: 'zakat',
    q: "How do you verify a charity\u2019s Zakat fund segregation?",
    a: "We do not certify Zakat fund segregation or compliance. In some cases we may surface a charity\u2019s stated Zakat policy page or handling details if they publish them, but our main label only means the charity publicly says it accepts Zakat on its website. If you need assurance on segregation, compliance, or fiqh validity, review the charity\u2019s policy directly and consult a qualified scholar."
  },
  {
    category: 'zakat',
    q: "Is your Zakat classification a religious ruling (fatwa)?",
    a: "Absolutely not. Our labels are informational only, based on publicly available data about what an organization says on its website. We report what charities claim about themselves and provide context for donors. For definitive guidance on your specific situation, please consult a qualified Islamic scholar who can consider your madhab and circumstances."
  },
  {
    category: 'zakat',
    q: "What scholarly frameworks inform your Zakat approach?",
    a: "We don\u2019t issue religious rulings\u2014we label based on what charities publicly claim. Our understanding of the eight asnaf categories draws from classical sources (Quran 9:60, major tafsir works) and contemporary scholarship including guidelines from the Assembly of Muslim Jurists of America (AMJA), the European Council for Fatwa and Research, and individual scholars like Dr. Yusuf al-Qaradawi\u2019s \u2018Fiqh al-Zakah.\u2019 Where madhabs differ\u2014such as on giving to non-Muslim beneficiaries or the scope of \u2018fi sabilillah\u2019\u2014we note the existence of legitimate scholarly disagreement rather than adopting one position. Our role is to help you find charities that publicly say they accept Zakat; your scholar\u2019s role is to confirm whether giving there aligns with your madhab."
  },
  {
    category: 'zakat',
    q: "What are the eight Zakat categories (asnaf)?",
    a: "Islamic jurisprudence identifies eight categories eligible for Zakat (Quran 9:60): Al-Fuqara (the poor), Al-Masakin (the destitute), Al-Amileen (Zakat administrators), Al-Muallafatul Quloob (those being brought closer to Islam), Ar-Riqab (freeing captives \u2014 modernly interpreted as refugees and trafficking victims), Al-Gharimeen (those in debt), Fi Sabilillah (in Allah\u2019s path \u2014 Islamic education, humanitarian work), and Ibnus-Sabil (stranded travelers, displaced persons). When a charity publicly says it accepts Zakat, we note which categories its work serves."
  },
  {
    category: 'zakat',
    q: "Why is a high-scoring charity classified as \u2018Sadaqah\u2019 instead of \u2018Zakat\u2019?",
    a: "The GMG Score measures overall strength across impact and alignment, while the wallet label is a narrower routing cue about what the charity publicly says on its website. A medical research organization or civil rights group might score very high and still not publicly accept Zakat. This doesn\u2019t make it less worthy \u2014 it just means you should generally use Sadaqah funds unless the charity itself provides a Zakat pathway you are comfortable with."
  },
  {
    category: 'zakat',
    q: "Should I consult a scholar before giving Zakat?",
    a: "We recommend it, especially for: large Zakat payments where you want extra assurance, specific madhab requirements (Hanafi, Shafi\u2019i, etc. may differ on details), edge cases involving mixed-purpose organizations, and family situations like giving to relatives or calculating nisab. Our classifications help you narrow down which charities to consider, but a qualified scholar can address your specific situation."
  },
  {
    category: 'zakat',
    q: "What if a charity accepts Zakat but you classified them as Sadaqah?",
    a: "Our label is based on the data we have. If an organization has a page on its website saying it accepts Zakat and we missed it, please email us at hello@goodmeasuregiving.org and we\u2019ll update our records. We are not making a ruling on whether the charity is fully Zakat-compliant \u2014 only whether that public claim appears on its website."
  },

  // Data
  {
    category: 'data',
    q: "Where does your data come from?",
    a: "We aggregate data from 6 sources: IRS Form 990 filings including grant data (via ProPublica\u2019s API \u2014 official legal filings), Charity Navigator (scores, accountability), Candid/GuideStar (transparency seals, outcomes), BBB Wise Giving Alliance (standards compliance), charity websites (programs, mission, Zakat policies), and \u2018discovered\u2019 information via Grounded Search (finding zakat claims, evaluations, and awards from across the web). When sources conflict, official IRS filings take precedence over rating agencies, which take precedence over self-reported website content."
  },
  {
    category: 'data',
    q: "How do you ensure evaluations are reproducible?",
    a: "All our charity data lives in DoltDB \u2014 a database with Git-like version control. Every pipeline run creates a \u2018commit\u2019 with a timestamp and description of what changed. You can diff any two pipeline runs to see exactly what data changed and why. This means we can always explain why a score changed: was it new 990 data? A Charity Navigator rating update? A website change? We never lose history, and we can even \u2018time travel\u2019 to see what our data looked like at any previous point."
  },
  {
    category: 'data',
    q: "How often do you update evaluations?",
    a: "We re-evaluate organizations when new 990 filings become available (typically annually) or when significant changes occur. If you notice outdated information, please email us at hello@goodmeasuregiving.org and we\u2019ll prioritize an update."
  },
  {
    category: 'data',
    q: "What if I think an evaluation is wrong?",
    a: "We welcome feedback. Use the Report Issue button on any charity page to flag specific errors, or the feedback button to share general concerns. You can also email us at hello@goodmeasuregiving.org with specifics. We\u2019ll review the data and update our evaluation if warranted. Our goal is accuracy, not defending our initial assessments."
  },
  {
    category: 'data',
    q: "What if I represent a charity that\u2019s been evaluated?",
    a: "We welcome organization feedback. Use the \u2018Tell us more\u2019 link on your charity\u2019s page or the Report Issue button to share corrections, context, or updated information. Our process: we receive your submission, review it against our data sources, and update the evaluation when warranted. Organization submissions may be reviewed before publication."
  },
  {
    category: 'data',
    q: "Why is a charity I know listed as \u2018Insufficient Data\u2019?",
    a: "Some organizations, particularly newer or smaller ones, don\u2019t have enough publicly available information for us to make a confident assessment. This isn\u2019t a negative judgment \u2014 it just means we need more data. Often this improves as organizations file more 990s or achieve transparency seals from Candid."
  }
];
