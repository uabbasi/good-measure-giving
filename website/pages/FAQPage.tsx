import React from 'react';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import { FAQ_ITEMS, type FaqItem } from '../src/data/faq';

export const FAQPage: React.FC = () => {
  const { isDark } = useLandingTheme();

  React.useEffect(() => {
    document.title = 'FAQ | Good Measure Giving';
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, []);

  const faqs: FaqItem[] = FAQ_ITEMS;

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
                  General charity evaluators often miss nuances important to our community. They usually don&#x2019;t track whether a charity publicly says it accepts Zakat, may unfairly penalize organizations working in conflict zones like Gaza or Syria, and often overlook smaller grassroots organizations that serve Muslim communities. We built this to fill that gap &#x2014; and to ask: <strong>would YOUR donation make more difference here than elsewhere?</strong>
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
