import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Copy, Check, ArrowRight, ShieldCheck, Link2, Image as ImageIcon } from 'lucide-react';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import {
  SITE_URL,
  buildTrustBadgeSnippet,
  buildTextLinkSnippets,
  type BadgeCharity,
} from '../src/lib/trustBadge';

// A real, high-scoring charity used purely as the worked example so the badge
// preview links somewhere live. Partners swap the EIN + score for their own.
const EXAMPLE_CHARITY: BadgeCharity = {
  ein: '41-2046295',
  name: 'The Citizens Foundation USA',
  score: 87,
};

// Small copy-to-clipboard control, mirroring PromptDetailPage's pattern.
const CopyButton: React.FC<{ text: string; isDark: boolean }> = ({ text, isDark }) => {
  const [copied, setCopied] = useState(false);
  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };
  return (
    <button
      type="button"
      onClick={onCopy}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
        isDark ? 'bg-slate-700 text-slate-200 hover:bg-slate-600' : 'bg-slate-200 text-slate-700 hover:bg-slate-300'
      }`}
    >
      {copied ? <Check className="w-3.5 h-3.5" aria-hidden="true" /> : <Copy className="w-3.5 h-3.5" aria-hidden="true" />}
      {copied ? 'Copied' : 'Copy'}
    </button>
  );
};

// A labelled, copyable code block holding an HTML snippet.
const SnippetBlock: React.FC<{ title: string; snippet: string; isDark: boolean }> = ({ title, snippet, isDark }) => (
  <div className={`rounded-xl border overflow-hidden ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
    <div className={`flex items-center justify-between px-4 py-2.5 border-b ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
      <span className={`text-sm font-medium ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>{title}</span>
      <CopyButton text={snippet} isDark={isDark} />
    </div>
    <pre className={`px-4 py-3 text-xs overflow-x-auto whitespace-pre-wrap break-all ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
      <code>{snippet}</code>
    </pre>
  </div>
);

export const LinkToUsPage: React.FC = () => {
  const { isDark } = useLandingTheme();

  React.useEffect(() => {
    document.title = 'Link to Us | Good Measure Giving';
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, []);

  const badgeSnippet = buildTrustBadgeSnippet(EXAMPLE_CHARITY);
  const textLinks = buildTextLinkSnippets();

  return (
    <div className={`min-h-screen transition-colors duration-300 ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
      {/* Hero */}
      <div className={`border-b ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <div className="text-center">
            <h1 className={`text-4xl md:text-5xl font-bold font-merriweather mb-6 [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>
              Link to Us
            </h1>
            <p className={`text-xl max-w-2xl mx-auto leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              Rated by Good Measure Giving? Show it. Copy a badge or link below to point your
              supporters to your independent evaluation {'—'} and help donors find trustworthy charities.
            </p>
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16 space-y-20">

        {/* Pitch */}
        <section>
          <h2 className={`text-2xl font-bold font-merriweather mb-4 [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>
            Why link to your evaluation
          </h2>
          <div className={`rounded-2xl border p-8 space-y-4 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
            <p className={`leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              Good Measure Giving is an independent evaluator. We don{'’'}t take money from the charities we
              rate, which means a link to your evaluation is a third-party signal of transparency {'—'} the kind
              of trust marker donors look for before they give.
            </p>
            <ul className={`space-y-2 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              <li className="flex items-start gap-2">
                <ShieldCheck className={`w-5 h-5 shrink-0 mt-0.5 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />
                <span>Show supporters you{'’'}ve been independently reviewed on impact, alignment, and transparency.</span>
              </li>
              <li className="flex items-start gap-2">
                <Link2 className={`w-5 h-5 shrink-0 mt-0.5 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />
                <span>Give donors a one-click path to the evidence behind your work.</span>
              </li>
            </ul>
            <p className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
              These badges and links are free to use. We just ask that the link points to your live evaluation
              and isn{'’'}t altered to misrepresent your score.
            </p>
          </div>
        </section>

        {/* Trust badge */}
        <section>
          <h2 className={`text-2xl font-bold font-merriweather mb-4 [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>
            The trust badge
          </h2>
          <p className={`mb-6 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
            Paste this badge onto your site. It shows your GMG score and links back to your full evaluation.
            Here{'’'}s how it looks for{' '}
            <Link
              to={`/charity/${EXAMPLE_CHARITY.ein}`}
              className={isDark ? 'text-emerald-400 hover:text-emerald-300 underline' : 'text-emerald-600 hover:text-emerald-700 underline'}
            >
              {EXAMPLE_CHARITY.name}
            </Link>:
          </p>

          {/* Live preview — rendered from the exact same string that gets copied. */}
          <div className={`rounded-2xl border p-8 mb-6 flex justify-center ${isDark ? 'bg-slate-800/60 border-slate-800' : 'bg-slate-100 border-slate-200'}`}>
            <div dangerouslySetInnerHTML={{ __html: badgeSnippet }} />
          </div>

          <SnippetBlock title="Trust badge HTML" snippet={badgeSnippet} isDark={isDark} />

          <div className={`rounded-xl p-4 mt-4 text-sm ${isDark ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-700'}`}>
            <strong>Using it on your own page?</strong> Swap two things for your charity:
            the URL{'’'}s EIN (<code className="text-xs">{EXAMPLE_CHARITY.ein}</code>) and the score number
            (<code className="text-xs">{EXAMPLE_CHARITY.score}</code>). Both appear on your evaluation page.
            Not sure of your numbers?{' '}
            <a href="mailto:hello@goodmeasuregiving.org" className={isDark ? 'text-emerald-400 underline' : 'text-emerald-600 underline'}>
              Email us
            </a>{' '}
            and we{'’'}ll send a ready-made snippet.
          </div>
        </section>

        {/* Text links */}
        <section>
          <h2 className={`text-2xl font-bold font-merriweather mb-4 [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>
            Plain text links
          </h2>
          <p className={`mb-6 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
            Prefer a simple link? Drop any of these into a blog post, footer, or transparency page.
          </p>
          <div className="space-y-4">
            {textLinks.map((link) => (
              <SnippetBlock key={link.label} title={link.label} snippet={link.html} isDark={isDark} />
            ))}
          </div>
        </section>

        {/* Brand assets */}
        <section>
          <h2 className={`text-2xl font-bold font-merriweather mb-4 [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>
            Brand assets
          </h2>
          <p className={`mb-6 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
            Need our logo for a partners page or press mention? Use these. Please don{'’'}t alter the colors or
            stretch the mark.
          </p>
          <div className="grid sm:grid-cols-2 gap-4">
            <div className={`rounded-xl border p-6 flex items-center gap-4 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
              <img src="/favicon.svg" alt="Good Measure Giving logo mark" width={48} height={48} />
              <div>
                <p className={`font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>Logo mark (SVG)</p>
                <a
                  href="/favicon.svg"
                  download
                  className={`inline-flex items-center gap-1.5 text-sm mt-1 ${isDark ? 'text-emerald-400 hover:text-emerald-300' : 'text-emerald-600 hover:text-emerald-700'}`}
                >
                  <ImageIcon className="w-4 h-4" aria-hidden="true" /> Download SVG
                </a>
              </div>
            </div>
            <div className={`rounded-xl border p-6 flex items-center gap-4 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
              <img src="/apple-touch-icon.png" alt="Good Measure Giving icon" width={48} height={48} className="rounded-lg" />
              <div>
                <p className={`font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>App icon (PNG)</p>
                <a
                  href="/apple-touch-icon.png"
                  download
                  className={`inline-flex items-center gap-1.5 text-sm mt-1 ${isDark ? 'text-emerald-400 hover:text-emerald-300' : 'text-emerald-600 hover:text-emerald-700'}`}
                >
                  <ImageIcon className="w-4 h-4" aria-hidden="true" /> Download PNG
                </a>
              </div>
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="text-center">
          <div className="bg-slate-900 rounded-2xl p-10">
            <h2 className="text-2xl font-bold text-white font-merriweather mb-4 [text-wrap:balance]">
              Questions about your evaluation?
            </h2>
            <p className="text-slate-400 mb-8 max-w-lg mx-auto">
              Read how we score charities, or get in touch and we{'’'}ll help you set up the badge.
            </p>
            <Link
              to="/methodology"
              className="inline-flex items-center gap-2 px-6 py-3 bg-emerald-600 text-white rounded-lg font-bold hover:bg-emerald-700 transition-colors"
            >
              See our methodology
              <ArrowRight className="w-4 h-4" aria-hidden="true" />
            </Link>
          </div>
        </section>

      </div>
    </div>
  );
};
