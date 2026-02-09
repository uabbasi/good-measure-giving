import React from 'react';
import { useLandingTheme } from '../contexts/LandingThemeContext';

interface FAQItem {
  q: string;
  a: string;
  category: 'general' | 'methodology' | 'ai' | 'zakat' | 'data';
}

export const FAQPage: React.FC = () => {
  const { isDark } = useLandingTheme();

  React.useEffect(() => {
    document.title = 'FAQ | Good Measure Giving';
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, []);

  const faqs: FAQItem[] = [
    // General
    {
      category: 'general',
      q: "Why do you need a specific evaluator for Muslim charities?",
      a: "General charity evaluators often miss nuances important to our community. They don\u2019t check for Zakat compliance, may unfairly penalize organizations working in conflict zones like Gaza or Syria, and often overlook smaller grassroots organizations that serve Muslim communities. We built this to fill that gap."
    },
    {
      category: 'general',
      q: "Is Good Measure Giving affiliated with any charity?",
      a: "No. We are completely independent. We do not accept payments from charities to be listed or to influence their scores. Our goal is to serve donors, not organizations."
    },
    {
      category: 'general',
      q: "How is this different from Charity Navigator or Candid?",
      a: "Those are excellent resources that we actually use as data sources. But they focus primarily on financial metrics like overhead ratios. We go further by evaluating two dimensions: Impact (how effectively does this charity use donations to create change?) and Alignment (is this the right charity for Muslim donors?). We also provide Zakat/Sadaqah classification and a Data Confidence signal that other evaluators don\u2019t offer."
    },
    {
      category: 'general',
      q: "Can I request a charity to be evaluated?",
      a: "Yes! We\u2019re actively expanding our database. Email us at hello@goodmeasuregiving.org with the organization\u2019s name and EIN, and we\u2019ll add it to our pipeline. Priority is given to registered 501(c)(3) organizations serving Muslim communities."
    },
    {
      category: 'general',
      q: "Do you evaluate mosques and Islamic centers?",
      a: "Currently, we focus on 501(c)(3) charitable organizations. Most mosques are religious organizations (501(c)(3) with religious exemptions) and have different reporting requirements \u2014 they\u2019re often not required to file Form 990s, which means we have less data to work with. We may expand to include mosques in the future, but our current methodology is optimized for charitable organizations with standard Form 990 filings."
    },

    // Methodology
    {
      category: 'methodology',
      q: "What is the GMG Score?",
      a: "The GMG Score is our 0-100 rating built from two dimensions, each worth 50 points: Impact (how effectively does this charity use donations to create measurable change?) and Alignment (is this the right charity for Muslim donors?). We also apply risk deductions (up to -10 points) for serious concerns like very low program spending or governance problems. Alongside the score, a Data Confidence signal (High, Medium, or Low) tells you how much public data supports the evaluation. Most charities score 50-70; scores above 75 indicate exceptional performance."
    },
    {
      category: 'methodology',
      q: "What does \u2018Impact\u2019 measure?",
      a: "Impact (50 points) measures how effectively a charity turns donations into real-world change. The largest component is cost per beneficiary (20 points), comparing each charity against cause-adjusted benchmarks for similar organizations. We also evaluate directness of service delivery (7 points), financial health and reserves (7 points), program expense ratio (6 points), evidence and outcome tracking (5 points), theory of change (3 points), and governance quality (2 points). Evidence quality is assessed on a five-level scale: Verified (independent third-party evaluation), Tracked (3+ years of outcome data), Measured (1-2 years of data), Reported (basic output tracking only), and Unverified (no structured tracking)."
    },
    {
      category: 'methodology',
      q: "What does \u2018Alignment\u2019 measure?",
      a: "Alignment (50 points) measures whether this charity is the right match for Muslim donors. The two largest components are Muslim donor fit (13 points) and cause urgency (13 points). We also evaluate underserved space (7 points) \u2014 is this need overlooked by mainstream philanthropy? \u2014 track record and organizational history (6 points), and funding gap (5 points) \u2014 would your donation make more difference here than elsewhere? Muslim-focused charities often score higher because they serve communities overlooked by mainstream funders."
    },
    {
      category: 'methodology',
      q: "Why don\u2019t you just use overhead ratios like other evaluators?",
      a: "Because overhead ratios can be misleading. An organization can have a 95% program expense ratio while doing something completely ineffective. Conversely, a legal advocacy organization might have higher administrative costs because lawyers are expensive \u2014 but win cases protecting millions of Muslims. Here\u2019s a real example: a food bank with 92% program spending might distribute food recipients don\u2019t need, while a civil rights organization with 75% program spending might achieve far greater impact. We include program ratio in our Impact dimension (6 of 50 points), but cost per beneficiary (20 points) and evidence of outcomes (5 points) matter far more."
    },
    {
      category: 'methodology',
      q: "How do you handle charities working in conflict zones?",
      a: "We explicitly account for the higher costs of operating in places like Gaza, Syria, Yemen, or other difficult environments. Security, logistics, and compliance costs are legitimately higher in these areas. Our cause-adjusted benchmarks automatically account for this context when evaluating cost per beneficiary \u2014 the single largest scoring component at 20 of 50 Impact points. We don\u2019t penalize organizations for these necessary expenses the way some general evaluators do."
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
      a: "Multiple safeguards work together: (1) Every factual claim must cite a source you can verify yourself (IRS filings, Charity Navigator, etc.). (2) We maintain a \u2018denylist\u2019 of high-risk fields (zakat eligibility, cost-per-beneficiary) that get extra scrutiny. (3) After narratives are generated, specialized \u2018judge\u2019 AIs audit them \u2014 checking citations exist and support claims, testing that URLs work, verifying facts against source data. (4) If validation fails, the evaluation fails \u2014 we don\u2019t publish fallback narratives. (5) All scoring uses deterministic code, never AI judgment."
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
      a: "Yes! We publish every prompt we use at /prompts — from data extraction to narrative generation to quality validation. You can see exactly what instructions we give to AI models, how we prevent hallucinations, and what safeguards ensure accuracy. We currently have 14 active prompts and 16 planned category-specific calibration prompts. This is part of our commitment to radical transparency."
    },

    // Zakat
    {
      category: 'zakat',
      q: "How do you determine if a charity is Zakat-eligible?",
      a: "We use a self-assertion model: if a charity explicitly claims Zakat eligibility on their website, we classify them as \u2018Zakat Eligible.\u2019 We verify this claim using search tools to find evidence on the charity\u2019s official website. We also note which of the eight asnaf categories (Zakat recipients) their work serves. We don\u2019t make our own independent rulings on Zakat eligibility \u2014 that\u2019s for scholars and the charity itself to determine."
    },
    {
      category: 'zakat',
      q: "Can I give Zakat to non-Muslim beneficiaries?",
      a: "This is a matter of scholarly debate. The majority of classical scholars restrict Zakat to Muslim beneficiaries, though some contemporary scholars permit giving to non-Muslims in certain categories (like \u2018those whose hearts are to be reconciled\u2019). Our platform labels charities based on their stated policies, but we recommend consulting with a scholar for your specific madhab\u2019s ruling."
    },
    {
      category: 'zakat',
      q: "How do you verify a charity\u2019s Zakat fund segregation?",
      a: "We check for explicit statements on the charity\u2019s website about Zakat fund handling. A strong Zakat policy should include: (1) separate accounting for Zakat funds, (2) clear statement about which programs receive Zakat, (3) commitment to 100% Zakat reaching eligible recipients. If we can\u2019t verify these elements, we classify the charity as Sadaqah to err on the side of caution."
    },
    {
      category: 'zakat',
      q: "Is your Zakat classification a religious ruling (fatwa)?",
      a: "Absolutely not. Our classifications are informational only, based on publicly available data about the organization\u2019s policies and programs. We report what charities claim about themselves and provide context for donors. For definitive guidance on your specific situation, please consult a qualified Islamic scholar who can consider your madhab and circumstances."
    },
    {
      category: 'zakat',
      q: "What scholarly frameworks inform your Zakat approach?",
      a: "We don\u2019t issue religious rulings\u2014we classify based on what charities publicly claim. Our understanding of the eight asnaf categories draws from classical sources (Quran 9:60, major tafsir works) and contemporary scholarship including guidelines from the Assembly of Muslim Jurists of America (AMJA), the European Council for Fatwa and Research, and individual scholars like Dr. Yusuf al-Qaradawi\u2019s \u2018Fiqh al-Zakah.\u2019 Where madhabs differ\u2014such as on giving to non-Muslim beneficiaries or the scope of \u2018fi sabilillah\u2019\u2014we note the existence of legitimate scholarly disagreement rather than adopting one position. Our role is to help you find charities that claim Zakat eligibility; your scholar\u2019s role is to confirm whether that claim aligns with your madhab."
    },
    {
      category: 'zakat',
      q: "What are the eight Zakat categories (asnaf)?",
      a: "Islamic jurisprudence identifies eight categories eligible for Zakat (Quran 9:60): Al-Fuqara (the poor), Al-Masakin (the destitute), Al-Amileen (Zakat administrators), Al-Muallafatul Quloob (those being brought closer to Islam), Ar-Riqab (freeing captives \u2014 modernly interpreted as refugees and trafficking victims), Al-Gharimeen (those in debt), Fi Sabilillah (in Allah\u2019s path \u2014 Islamic education, humanitarian work), and Ibnus-Sabil (stranded travelers, displaced persons). When a charity claims Zakat eligibility, we note which categories their work serves."
    },
    {
      category: 'zakat',
      q: "Why is a high-scoring charity classified as \u2018Sadaqah\u2019 instead of \u2018Zakat\u2019?",
      a: "The GMG Score measures overall strength across impact and alignment \u2014 while wallet classification is about religious compliance. A medical research organization or civil rights group might score very high but not fit traditional Zakat categories. This doesn\u2019t make them less worthy \u2014 it just means you should use your Sadaqah funds rather than Zakat. Both are important forms of giving."
    },
    {
      category: 'zakat',
      q: "Should I consult a scholar before giving Zakat?",
      a: "We recommend it, especially for: large Zakat payments where you want extra assurance, specific madhab requirements (Hanafi, Shafi\u2019i, etc. may differ on details), edge cases involving mixed-purpose organizations, and family situations like giving to relatives or calculating nisab. Our classifications help you narrow down which charities to consider, but a qualified scholar can address your specific situation."
    },
    {
      category: 'zakat',
      q: "What if a charity accepts Zakat but you classified them as Sadaqah?",
      a: "Our classification is based on the data we have. If an organization has a Zakat fund that we missed, please email us at hello@goodmeasuregiving.org and we\u2019ll update our records. However, some organizations accept Zakat without proper segregation or clear policies \u2014 in those cases, we err on the side of caution and classify as Sadaqah until we can verify compliance."
    },

    // Data
    {
      category: 'data',
      q: "Where does your data come from?",
      a: "We aggregate data from 7 sources: IRS Form 990 filings (via ProPublica\u2019s API \u2014 official legal filings), Charity Navigator (scores, accountability), Candid/GuideStar (transparency seals, outcomes), BBB Wise Giving Alliance (standards compliance), charity websites (programs, mission, Zakat policies), Form 990 grant data (who they fund), and \u2018discovered\u2019 information via Grounded Search (finding zakat claims, evaluations, and awards from across the web). When sources conflict, official IRS filings take precedence over rating agencies, which take precedence over self-reported website content."
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
      a: "We welcome feedback. If you believe we\u2019ve made an error or missed important information, please email us at hello@goodmeasuregiving.org with specifics. We\u2019ll review the data and update our evaluation if warranted. Our goal is accuracy, not defending our initial assessments."
    },
    {
      category: 'data',
      q: "Why is a charity I know listed as \u2018Insufficient Data\u2019?",
      a: "Some organizations, particularly newer or smaller ones, don\u2019t have enough publicly available information for us to make a confident assessment. This isn\u2019t a negative judgment \u2014 it just means we need more data. Often this improves as organizations file more 990s or achieve transparency seals from Candid."
    }
  ];

  const categories = [
    { id: 'general', label: 'General', description: 'About Good Measure Giving' },
    { id: 'methodology', label: 'Our Methodology', description: 'How we score charities' },
    { id: 'ai', label: 'AI & Technology', description: 'How we use AI responsibly' },
    { id: 'zakat', label: 'Zakat & Sadaqah', description: 'Religious classifications' },
    { id: 'data', label: 'Data & Accuracy', description: 'Sources and updates' }
  ];

  const scrollToCategory = (categoryId: string) => {
    const element = document.getElementById(`faq-${categoryId}`);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <div className={`min-h-screen transition-colors duration-300 ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
      {/* Hero */}
      <div className={`border-b ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <h1 className={`text-4xl font-bold font-merriweather mb-4 [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>
            Frequently Asked Questions
          </h1>
          <p className={`text-lg mb-8 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
            Everything you need to know about how we evaluate charities.
          </p>

          {/* Quick Jump Navigation */}
          <div className="flex flex-wrap gap-2">
            {categories.map(cat => (
              <button
                key={cat.id}
                onClick={() => scrollToCategory(cat.id)}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                  isDark
                    ? 'bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200 hover:text-slate-900'
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* FAQ Content */}
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">

        {/* Featured Questions - Key Differentiators */}
        <section className="mb-16">
          <div className={`rounded-2xl p-8 ${isDark ? 'bg-emerald-900/20 border border-emerald-800/30' : 'bg-emerald-50 border border-emerald-200'}`}>
            <h2 className={`text-xl font-bold font-merriweather mb-6 [text-wrap:balance] ${isDark ? 'text-emerald-400' : 'text-emerald-800'}`}>
              The Questions That Matter Most
            </h2>

            <div className="space-y-8">
              <article>
                <h3 className={`text-lg font-semibold mb-3 ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  Why don&#x2019;t you just use overhead ratios like other evaluators?
                </h3>
                <p className={`leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                  Because overhead ratios can be misleading. An organization can have a 95% program expense ratio while doing something completely ineffective. Conversely, a legal advocacy organization might have higher administrative costs because lawyers are expensive &#x2014; but win cases protecting millions of Muslims. A food bank with 92% program spending might distribute food recipients don&#x2019;t need, while a civil rights organization with 75% program spending might achieve far greater impact. <strong>We measure whether programs actually work</strong>, not just how money is allocated.
                </p>
              </article>

              <article>
                <h3 className={`text-lg font-semibold mb-3 ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  Why do you need a specific evaluator for Muslim charities?
                </h3>
                <p className={`leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                  General charity evaluators often miss nuances important to our community. They don&#x2019;t check for Zakat compliance, may unfairly penalize organizations working in conflict zones like Gaza or Syria, and often overlook smaller grassroots organizations that serve Muslim communities. We built this to fill that gap &#x2014; and to ask: <strong>would YOUR donation make more difference here than elsewhere?</strong>
                </p>
              </article>
            </div>
          </div>
        </section>

        {categories.map((category, catIndex) => {
          const categoryFaqs = faqs.filter(f => f.category === category.id);
          return (
            <section
              key={category.id}
              id={`faq-${category.id}`}
              className={catIndex > 0 ? 'mt-16 pt-16 border-t' : ''}
              style={catIndex > 0 ? { borderColor: isDark ? 'rgb(30 41 59)' : 'rgb(226 232 240)' } : {}}
            >
              {/* Category Header */}
              <div className="mb-8">
                <h2 className={`text-2xl font-bold font-merriweather mb-1 [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  {category.label}
                </h2>
                <p className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                  {category.description}
                </p>
              </div>

              {/* Q&A Items - All Open */}
              <div className="space-y-8">
                {categoryFaqs.map((faq, i) => (
                  <article key={i} className="group">
                    <h3 className={`text-lg font-semibold mb-3 ${isDark ? 'text-slate-200' : 'text-slate-800'}`}>
                      {faq.q}
                    </h3>
                    <p className={`leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                      {faq.a}
                    </p>
                  </article>
                ))}
              </div>
            </section>
          );
        })}

        {/* Contact CTA */}
        <div className={`mt-16 pt-16 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
          <div className={`rounded-2xl p-8 text-center ${isDark ? 'bg-slate-900' : 'bg-white border border-slate-200'}`}>
            <h3 className={`text-xl font-bold mb-2 ${isDark ? 'text-white' : 'text-slate-900'}`}>
              Still have questions?
            </h3>
            <p className={`mb-6 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              We&#x2019;re here to help. Reach out and we&#x2019;ll get back to you as soon as we can.
            </p>
            <a
              href="mailto:hello@goodmeasuregiving.org"
              className={`inline-block px-6 py-3 rounded-lg font-bold transition-colors ${
                isDark
                  ? 'bg-white text-slate-900 hover:bg-slate-100'
                  : 'bg-slate-900 text-white hover:bg-slate-800'
              }`}
            >
              Contact Us
            </a>
          </div>
        </div>
      </div>
    </div>
  );
};
