import React from 'react';
import { Link } from 'react-router-dom';
import {
  ShieldCheck,
  Database,
  Brain,
  Eye,
  ArrowRight,

  Heart,
  Scale,
} from 'lucide-react';
import { useLandingTheme } from '../contexts/LandingThemeContext';

export const AboutPage: React.FC = () => {
  const { isDark } = useLandingTheme();

  React.useEffect(() => {
    document.title = 'About | Good Measure Giving';
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, []);

  const cardClass = `rounded-xl p-6 ${isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-slate-200 shadow-sm'}`;
  const headingClass = `font-merriweather font-bold ${isDark ? 'text-white' : 'text-slate-900'}`;
  const bodyClass = isDark ? 'text-slate-300 leading-relaxed' : 'text-slate-600 leading-relaxed';
  const mutedClass = isDark ? 'text-slate-400' : 'text-slate-500';

  return (
    <div className={`min-h-screen transition-colors duration-300 ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
      {/* Hero */}
      <div className={`border-b ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <div className="text-center">
            <h1 className={`text-4xl md:text-5xl font-bold font-merriweather mb-6 ${isDark ? 'text-white' : 'text-slate-900'}`}>
              About Good Measure
            </h1>
            <p className={`text-xl max-w-3xl mx-auto leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              Rigorous, independent charity research for Muslim donors — so every dollar of Zakat and Sadaqah creates the deepest possible impact.
            </p>
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-12">

        {/* The Problem */}
        <section>
          <h2 className={`text-2xl mb-4 ${headingClass}`}>The Problem</h2>
          <p className={bodyClass}>
            Every year, billions of dollars flow through Zakat, Sadaqah, and charitable giving in Muslim communities. Yet most donors lack access to independent, rigorous evaluations of the charities they support. General-purpose evaluators like Charity Navigator focus heavily on financial ratios and often miss nuances critical to our community — Zakat compliance, work in conflict zones, grassroots organizations serving underserved populations. The result: well-intentioned giving that could do more.
          </p>
        </section>

        {/* Our Approach */}
        <section>
          <h2 className={`text-2xl mb-6 ${headingClass}`}>Our Approach</h2>
          <div className="grid sm:grid-cols-2 gap-4">
            {[
              {
                icon: Database,
                title: 'Impact',
                desc: 'How effectively does this charity turn donations into change? We evaluate cost per beneficiary, program efficiency, financial health, evidence of outcomes, and governance quality.',
              },
              {
                icon: Heart,
                title: 'Alignment',
                desc: 'Is this the right charity for Muslim donors? We assess Muslim donor fit, cause urgency, underserved space, track record, and funding gap.',
              },
            ].map(({ icon: Icon, title, desc }) => (
              <div key={title} className={cardClass}>
                <div className="flex items-start gap-3">
                  <div className={`mt-1 p-2 rounded-lg ${isDark ? 'bg-emerald-900/30 text-emerald-400' : 'bg-emerald-50 text-emerald-600'}`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className={`text-lg font-semibold mb-1 ${headingClass}`}>{title}</h3>
                    <p className={`text-sm ${mutedClass}`}>{desc}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
          <p className={`mt-4 text-sm ${mutedClass}`}>
            Each dimension contributes up to 50 points to the GMG Score (0–100).{' '}
            <Link to="/methodology" className="text-emerald-600 hover:text-emerald-500 underline underline-offset-2">
              See full methodology →
            </Link>
          </p>
        </section>

        {/* Data Sources */}
        <section>
          <h2 className={`text-2xl mb-4 ${headingClass}`}>Where Our Data Comes From</h2>
          <p className={`mb-4 ${bodyClass}`}>
            We don't rely only on charity self-reporting. Our pipeline aggregates data from multiple independent sources:
          </p>
          <div className={`${cardClass} space-y-3`}>
            {[
              ['IRS Form 990 filings', 'Financials, governance, compensation — the official public record.'],
              ['Charity Navigator', 'Financial health scores, accountability ratings, and 990 analysis.'],
              ['Candid (GuideStar)', 'Transparency seals and organizational profiles.'],
              ['BBB Wise Giving Alliance', 'Standards-based accreditation for governance and fundraising.'],
              ['ProPublica Nonprofit Explorer', 'Cross-referenced 990 data and historical filings.'],
              ['Charity websites & reports', 'Annual reports, impact data, and program descriptions.'],
            ].map(([source, detail]) => (
              <div key={source} className="flex items-start gap-2">
                <span className={`mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${isDark ? 'bg-emerald-500' : 'bg-emerald-400'}`} />
                <p className={`text-sm ${bodyClass}`}>
                  <span className={`font-medium ${isDark ? 'text-white' : 'text-slate-800'}`}>{source}</span>
                  {' — '}{detail}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* AI + Transparency */}
        <section>
          <h2 className={`text-2xl mb-4 ${headingClass}`}>AI-Assisted, Human-Guided</h2>
          <div className={`${cardClass} flex items-start gap-4`}>
            <div className={`mt-1 p-2 rounded-lg flex-shrink-0 ${isDark ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-600'}`}>
              <Brain className="w-5 h-5" />
            </div>
            <div>
              <p className={bodyClass}>
                We use AI to synthesize large volumes of public data into structured evaluations. Core prompts, scoring rubrics, and decision rules are published on our{' '}
                <Link to="/prompts" className="text-emerald-600 hover:text-emerald-500 underline underline-offset-2">
                  AI Transparency page
                </Link>
                . The pipeline is deterministic: same data in, same scores out. AI writes the narratives; the methodology, weights, and data sources are human-designed.
              </p>
            </div>
          </div>
        </section>

        {/* Independence */}
        <section>
          <h2 className={`text-2xl mb-4 ${headingClass}`}>Independence</h2>
          <div className="grid sm:grid-cols-3 gap-4">
            {[
              { icon: Scale, label: 'No charity pays to be listed or to influence scores.' },
              { icon: Eye, label: 'All scoring criteria and AI prompts are published openly.' },
              { icon: ShieldCheck, label: 'We serve donors, not organizations.' },
            ].map(({ icon: Icon, label }) => (
              <div key={label} className={`${cardClass} text-center`}>
                <Icon className={`w-6 h-6 mx-auto mb-3 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                <p className={`text-sm ${bodyClass}`}>{label}</p>
              </div>
            ))}
          </div>
        </section>

        {/* CTA */}
        <section className="text-center pt-4 pb-8">
          <Link
            to="/browse"
            className="inline-flex items-center gap-2 px-6 py-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-full font-medium transition-colors"
          >
            Browse Evaluated Charities
            <ArrowRight className="w-4 h-4" />
          </Link>
        </section>
      </div>
    </div>
  );
};
