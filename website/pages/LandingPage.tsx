/**
 * Landing Page — Responsive Layout
 *
 * Desktop (>=1024px): Traditional vertical scroll — hero + audit + community CTA
 * Mobile (<1024px): Vertical scroll — compact hero → stats → value props → evaluation preview → sign-in CTA
 */

import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Scale, ArrowRight, CheckCircle, Search, Heart, Shield, Eye, Sparkles, Lock, Target } from 'lucide-react';
import { SignInButton } from '../src/auth/SignInButton';
import { useAuth } from '../src/auth/useAuth';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import { THEMES } from '../src/themes';
import { trackHeroCTA } from '../src/utils/analytics';
import { TOP_CHARITY_FOR_LANDING } from '../src/data/topCharity';
import { useCharities } from '../src/hooks/useCharities';
import { cleanNarrativeText } from '../src/utils/cleanNarrativeText';
import { isPubliclyVisible } from '../src/utils/tierUtils';

const featuredCharity = TOP_CHARITY_FOR_LANDING;
const LIGHT_THEME_INDEX = 4;
const DARK_THEME_INDEX = 2;

export const LandingPage: React.FC = () => {
  const { isDark } = useLandingTheme();
  const theme = THEMES[isDark ? DARK_THEME_INDEX : LIGHT_THEME_INDEX];
  const { charities } = useCharities();
  const charityCount = useMemo(() => charities.filter(isPubliclyVisible).length, [charities]);
  const scoreDetails = featuredCharity?.amalEvaluation?.score_details;
  const confidenceBadge = scoreDetails?.data_confidence?.badge ?? '\u2014';
  const riskLevel = scoreDetails?.risks?.overall_risk_level ?? 'UNKNOWN';
  const zakatClaimed = scoreDetails?.zakat?.charity_claims_zakat;
  const walletLabel = zakatClaimed === true ? 'Accepts Zakat' : zakatClaimed === false ? 'Sadaqah Route' : 'Wallet Unclear';
  const scoreSummary = scoreDetails?.score_summary;
  const { isSignedIn } = useAuth();

  const dk = theme.id.includes('dark') || theme.id === 'warm-atmosphere';
  const count = charityCount > 0 ? charityCount : 170;

  /* ════════════════════════════════════════════
     MOBILE: Vertical scroll — fast, scannable
     ════════════════════════════════════════════ */
  const mobileLayout = (
    <div className={`min-h-screen ${theme.bgPage} font-sans transition-colors duration-500`}>

      {/* Hero */}
      <section className={`relative pt-12 pb-10 overflow-hidden ${theme.bgHero}`}>
        {theme.backgroundElements}
        <div className="relative z-10 max-w-lg mx-auto px-5 text-center">
          <div className={`mb-4 ${dk ? 'text-slate-500' : 'text-emerald-800/60'}`}>
            <span className="font-arabic text-base tracking-wider" dir="rtl" lang="ar">
              بِسْمِ ٱللَّٰهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ
            </span>
          </div>
          <h1 className={`text-[1.75rem] font-bold font-merriweather tracking-tight mb-3 leading-[1.15] [text-wrap:balance] ${theme.textMain}`}>
            Know where your{' '}
            <span className={theme.textAccent}>charity dollar</span> goes
          </h1>
          <p className={`text-[15px] leading-relaxed mb-6 ${theme.textSub}`}>
            Real research on {count}+ Muslim charities — financials, impact evidence, and zakat eligibility. Plan your giving with confidence.
          </p>
          <Link
            to="/browse"
            onClick={() => trackHeroCTA('browse_charities_primary', '/browse')}
            className={`inline-flex items-center justify-center gap-2 px-7 py-3 rounded-full font-bold text-base group transition-all duration-300 shadow-lg ${theme.btnPrimary}`}
          >
            <Search className="w-5 h-5" aria-hidden="true" />
            Browse Charities
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" aria-hidden="true" />
          </Link>
        </div>
      </section>

      {/* Stats strip */}
      <div className={`py-3 border-y ${dk ? 'bg-slate-950/50 border-slate-800' : 'bg-white border-slate-100'}`}>
        <div className={`flex justify-center items-center gap-4 text-xs font-medium ${dk ? 'text-slate-400' : 'text-slate-500'}`}>
          <span><strong className={dk ? 'text-white' : 'text-slate-800'}>{count}+</strong> Evaluated</span>
          <span className={dk ? 'text-white/15' : 'text-slate-200'}>|</span>
          <span><strong className={dk ? 'text-white' : 'text-slate-800'}>Independent</strong> Research</span>
          <span className={dk ? 'text-white/15' : 'text-slate-200'}>|</span>
          <span><strong className={dk ? 'text-emerald-400' : 'text-emerald-700'}>Free</strong>, always</span>
        </div>
      </div>

      {/* What we dig into */}
      <section className={`py-8 px-5 ${dk ? 'bg-slate-950' : 'bg-white'}`}>
        <h2 className={`text-xl font-bold font-merriweather mb-5 text-center [text-wrap:balance] ${dk ? 'text-white' : 'text-slate-900'}`}>
          What charities don{'\u2019'}t put on their homepage
        </h2>
        <div className="max-w-md mx-auto space-y-4">
          {[
            { icon: Eye, title: 'Program outcomes', desc: 'Do their programs change lives? We check the evidence, not just the claims.' },
            { icon: Shield, title: 'Financial accountability', desc: 'Where does each dollar go? We trace it through IRS filings and audits.' },
            { icon: Sparkles, title: 'Zakat verification', desc: 'Does this charity accept zakat? We show the source — no guessing.' },
            { icon: Target, title: 'Zakat & giving planning', desc: 'Set a zakat target, organize charities into giving buckets, and track your annual plan.' },
          ].map(({ icon: Icon, title, desc }) => (
            <div key={title} className="flex items-start gap-3">
              <div className={`flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center ${dk ? 'bg-emerald-500/10' : 'bg-emerald-50'}`}>
                <Icon className={`w-4.5 h-4.5 ${dk ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />
              </div>
              <div>
                <span className={`font-semibold text-[15px] ${dk ? 'text-slate-100' : 'text-slate-800'}`}>{title}</span>
                <span className={`block text-[13px] mt-0.5 leading-relaxed ${dk ? 'text-slate-400' : 'text-slate-500'}`}>{desc}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Featured evaluation preview */}
      <section className={`py-8 px-5 ${dk ? 'bg-slate-900' : 'bg-slate-50'}`}>
        <div className="max-w-md mx-auto">
          <div className={`text-xs font-bold uppercase tracking-wider text-center mb-4 ${dk ? 'text-slate-500' : 'text-slate-400'}`}>
            Sample evaluation
          </div>
          <div className="relative">
            <div className="absolute -inset-4 bg-gradient-to-r from-emerald-500/20 via-blue-500/10 to-purple-500/20 blur-2xl rounded-3xl opacity-50" />
            <div className={`relative p-5 rounded-2xl shadow-xl ${dk ? 'bg-slate-800/90 border border-slate-600/50 ring-1 ring-white/10' : 'bg-white border border-slate-200 ring-1 ring-slate-100'}`}>
              <div className={`mb-4 pb-3 border-b ${dk ? 'border-slate-700/50' : 'border-slate-100'}`}>
                <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 mb-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-[10px] font-bold text-emerald-500 uppercase tracking-wider">Featured Evaluation</span>
                </div>
                <div className={`text-lg font-bold ${dk ? 'text-white' : 'text-slate-900'}`}>{featuredCharity?.name || 'Loading...'}</div>
                <div className={`text-xs line-clamp-2 mt-0.5 ${dk ? 'text-slate-400' : 'text-slate-500'}`}>{featuredCharity?.headline ? cleanNarrativeText(featuredCharity.headline) : ''}</div>
              </div>

              <div className="grid grid-cols-3 gap-2 mb-4">
                <Badge dk={dk} value={confidenceBadge} label="Confidence" color="blue" />
                <Badge dk={dk} value={riskLevel} label="Risk" color="emerald" />
                <Badge dk={dk} value={walletLabel} label="Route" color="purple" />
              </div>

              {scoreSummary && (
                <div className={`p-3 rounded-xl mb-4 ${dk ? 'bg-slate-900/80 border border-slate-700/50' : 'bg-slate-50 border border-slate-200'}`}>
                  <div className={`text-[10px] font-bold uppercase tracking-wider mb-1.5 ${dk ? 'text-slate-400' : 'text-slate-500'}`}>Evaluation Summary</div>
                  <p className={`text-xs leading-relaxed line-clamp-3 ${dk ? 'text-slate-300' : 'text-slate-700'}`}>{cleanNarrativeText(scoreSummary)}</p>
                </div>
              )}

              <Link
                to={`/charity/${featuredCharity?.ein}`}
                onClick={() => trackHeroCTA('view_featured_evaluation', `/charity/${featuredCharity?.ein}`)}
                className="w-full flex items-center justify-center gap-2 py-3 bg-gradient-to-r from-emerald-600 to-emerald-500 text-white rounded-xl text-sm font-bold hover:from-emerald-500 hover:to-emerald-400 transition-all shadow-lg shadow-emerald-500/25"
              >
                View Full Evaluation
                <ArrowRight className="w-4 h-4" aria-hidden="true" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Sign-in CTA — what you unlock */}
      {!isSignedIn && (
        <section className={`py-10 px-5 ${dk ? 'bg-slate-950' : 'bg-white'}`}>
          <div className="max-w-md mx-auto text-center">
            <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full mb-4 ${dk ? 'bg-emerald-500/10 border border-emerald-500/30' : 'bg-emerald-50 border border-emerald-200'}`}>
              <Heart className={`w-4 h-4 ${dk ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />
              <span className={`text-sm font-medium ${dk ? 'text-emerald-400' : 'text-emerald-700'}`}>Free access</span>
            </div>
            <h2 className={`text-2xl font-bold font-merriweather mb-3 [text-wrap:balance] ${dk ? 'text-white' : 'text-slate-900'}`}>
              Go deeper on the charities you care about
            </h2>
            <p className={`text-sm leading-relaxed mb-5 ${dk ? 'text-slate-400' : 'text-slate-500'}`}>
              Sign in to unlock the full picture for every charity we evaluate.
            </p>

            {/* What you unlock */}
            <div className={`text-left rounded-xl p-4 mb-6 space-y-3 ${dk ? 'bg-slate-800/60 border border-slate-700/50' : 'bg-slate-50 border border-slate-200'}`}>
              {[
                'Full charity evaluations & leadership profiles',
                '3-year financial trends & audit results',
                'Zakat target & giving plan tools',
                'Organize charities into giving buckets',
              ].map((item) => (
                <div key={item} className="flex items-center gap-2.5">
                  <Lock className={`w-3.5 h-3.5 flex-shrink-0 ${dk ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />
                  <span className={`text-[13px] ${dk ? 'text-slate-300' : 'text-slate-700'}`}>{item}</span>
                </div>
              ))}
            </div>

            <SignInButton
              variant="button"
              context="landing_mobile_cta"
              className={`w-full px-8 py-4 rounded-full font-bold text-lg transition-all duration-300 shadow-lg ${
                dk
                  ? 'bg-emerald-500 text-white hover:bg-emerald-400 shadow-emerald-500/25'
                  : 'bg-emerald-600 text-white hover:bg-emerald-500 shadow-emerald-500/25'
              }`}
            />
            <span className={`block text-[11px] mt-2 ${dk ? 'text-slate-500' : 'text-slate-400'}`}>No credit card. No spam. Just better giving.</span>
          </div>
        </section>
      )}

      {/* Browse all footer CTA */}
      <section className={`py-6 px-5 text-center ${dk ? 'bg-slate-900 border-t border-slate-800' : 'bg-slate-50 border-t border-slate-100'}`}>
        <Link
          to="/browse"
          onClick={() => trackHeroCTA('browse_all_charities', '/browse')}
          className={`text-sm font-medium transition-colors ${dk ? 'text-slate-400 hover:text-emerald-400' : 'text-slate-500 hover:text-emerald-600'}`}
        >
          Browse all {count}+ evaluated charities &rarr;
        </Link>
      </section>
    </div>
  );

  /* ════════════════════════════════════════════
     DESKTOP: Traditional vertical scroll
     ════════════════════════════════════════════ */
  const desktopLayout = (
    <div className={`flex flex-col min-h-screen ${theme.bgPage} font-sans transition-colors duration-500`}>

      {/* Bismillah bar */}
      <div className={`w-full py-4 text-center border-b transition-colors duration-500 ${dk ? 'bg-slate-950 text-slate-400 border-slate-800' : 'bg-emerald-900 text-emerald-100 border-emerald-800'}`}>
        <span className="font-arabic text-2xl tracking-wider opacity-90" dir="rtl" lang="ar">
          بِسْمِ ٱللَّٰهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ
        </span>
      </div>

      {/* Hero */}
      <section className={`relative pt-12 pb-14 lg:pt-16 lg:pb-20 overflow-hidden transition-colors duration-500 ${theme.bgHero}`}>
        {theme.backgroundElements}
        <div className="relative max-w-4xl mx-auto px-6 lg:px-8 text-center z-10">
          <div className={`inline-flex items-center gap-3 px-5 py-2.5 rounded-full mb-5 ${theme.pill}`}>
            <Scale className={`w-4 h-4 ${theme.pillIcon}`} aria-hidden="true" />
            <span className="text-sm font-serif italic tracking-wide">
              {'\u201C'}He raised the sky and set up the balance.{'\u201D'} — Surah Ar-Rahman [55:7]
            </span>
          </div>
          <h1 className={`text-5xl lg:text-7xl font-bold font-merriweather tracking-tight mb-6 leading-[1.1] [text-wrap:balance] ${theme.textMain}`}>
            Know where your{' '}
            <br className="hidden md:block" />
            <span className={theme.textAccent}>charity dollar</span> goes
          </h1>
          <p className={`text-xl leading-relaxed mb-8 max-w-2xl mx-auto ${theme.textSub}`}>
            Real research on {count}+ Muslim charities — financials, impact evidence, and zakat eligibility. Plan your giving with confidence.
          </p>
          <div className="flex flex-col items-center gap-4 mb-8">
            <Link
              to="/browse"
              onClick={() => trackHeroCTA('browse_charities_primary', '/browse')}
              className={`px-10 py-5 min-h-[56px] rounded-full font-bold text-xl flex items-center justify-center gap-3 group transition-all duration-300 shadow-lg ${theme.btnPrimary}`}
            >
              <Search className="w-6 h-6" aria-hidden="true" />
              Browse Charities
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" aria-hidden="true" />
            </Link>
            <Link
              to="/methodology"
              onClick={() => trackHeroCTA('methodology', '/methodology')}
              className={`text-sm font-medium transition-colors ${dk ? 'text-slate-400 hover:text-white' : 'text-slate-500 hover:text-slate-900'}`}
            >
              How we evaluate charities →
            </Link>
          </div>
          <div className={`flex flex-wrap justify-center gap-x-6 gap-y-3 text-sm border-t pt-6 px-6 ${theme.stats} ${dk ? 'border-white/10' : 'border-slate-200'}`}>
            <div className="flex items-center gap-2">
              <CheckCircle className={`w-4 h-4 ${theme.pillIcon}`} aria-hidden="true" />
              <span>{charityCount > 0 ? <><strong className={theme.statsStrong}>{charityCount}</strong> Charities Evaluated</> : <><strong className={theme.statsStrong}>Multi-Source</strong> Verification</>}</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle className={`w-4 h-4 ${theme.pillIcon}`} aria-hidden="true" />
              <span><strong className={theme.statsStrong}>Program</strong> Outcomes</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle className={`w-4 h-4 ${theme.pillIcon}`} aria-hidden="true" />
              <span><strong className={theme.statsStrong}>Independent</strong> Research</span>
            </div>
          </div>
        </div>
      </section>

      {/* Sample Audit — text + card side-by-side */}
      <section className={`py-10 lg:py-16 relative z-10 overflow-hidden transition-colors duration-500 ${dk ? 'bg-slate-950' : 'bg-white border-y border-slate-100'}`}>
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="flex flex-row items-center gap-10">
            <div className="w-1/2">
              <h2 className={`text-4xl font-bold font-merriweather mb-4 [text-wrap:balance] ${dk ? 'text-white' : 'text-slate-900'}`}>
                What charities don{'\u2019'}t put on their homepage
              </h2>
              <p className={`text-lg leading-relaxed mb-8 ${dk ? 'text-slate-300' : 'text-slate-600'}`}>
                Charities share stories. We dig into the data — program outcomes, financial health, and where your dollar actually ends up.
              </p>
              <ul className="space-y-5">
                {[
                  { icon: Eye, title: 'Program outcomes', desc: 'Do their programs change lives? We check the evidence, not just the claims.' },
                  { icon: Shield, title: 'Financial accountability', desc: 'Where does each dollar go? We trace it through IRS filings and audits.' },
                  { icon: Sparkles, title: 'Zakat verification', desc: 'Does this charity accept zakat? We show the source — no guessing.' },
                  { icon: Target, title: 'Zakat & giving planning', desc: 'Set a zakat target, organize charities into giving buckets, and track your annual plan.' },
                ].map(({ icon: Icon, title, desc }) => (
                  <li key={title} className="flex items-start gap-3">
                    <Icon className={`w-5 h-5 flex-shrink-0 mt-0.5 ${dk ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />
                    <div>
                      <span className={`font-semibold ${dk ? 'text-slate-100' : 'text-slate-800'}`}>{title}</span>
                      <span className={`block text-sm mt-0.5 ${dk ? 'text-slate-400' : 'text-slate-500'}`}>{desc}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
            <div className="w-1/2 relative">
              <div className="absolute -inset-4 bg-gradient-to-r from-emerald-500/30 via-blue-500/20 to-purple-500/30 blur-3xl rounded-3xl opacity-60" />
              <div className="absolute -inset-1 bg-gradient-to-r from-emerald-500/20 to-blue-500/20 blur-xl rounded-2xl" />
              <div className={`relative p-8 rounded-2xl shadow-2xl backdrop-blur-sm ${dk ? 'bg-slate-800/90 border border-slate-600/50 ring-1 ring-white/10' : 'bg-white border border-slate-200 ring-1 ring-slate-100'}`}>
                <div className={`mb-8 pb-6 border-b ${dk ? 'border-slate-700/50' : 'border-slate-100'}`}>
                  <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 mb-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    <span className="text-[10px] font-bold text-emerald-500 uppercase tracking-wider">Featured Evaluation</span>
                  </div>
                  <div className={`text-2xl font-bold ${dk ? 'text-white' : 'text-slate-900'}`}>{featuredCharity?.name || 'Loading...'}</div>
                  <div className={`text-sm line-clamp-2 mt-0.5 ${dk ? 'text-slate-400' : 'text-slate-500'}`}>{featuredCharity?.headline ? cleanNarrativeText(featuredCharity.headline) : ''}</div>
                </div>

                <div className="grid grid-cols-3 gap-2 mb-8">
                  <Badge dk={dk} value={confidenceBadge} label="Confidence" color="blue" large />
                  <Badge dk={dk} value={riskLevel} label="Risk" color="emerald" large />
                  <Badge dk={dk} value={walletLabel} label="Route" color="purple" large />
                </div>

                {scoreSummary && (
                  <div className={`p-5 rounded-xl mb-6 ${dk ? 'bg-slate-900/80 border border-slate-700/50' : 'bg-slate-50 border border-slate-200'}`}>
                    <div className={`text-xs font-bold uppercase tracking-wider mb-1.5 ${dk ? 'text-slate-400' : 'text-slate-500'}`}>Evaluation Summary</div>
                    <p className={`text-sm leading-relaxed line-clamp-3 ${dk ? 'text-slate-300' : 'text-slate-700'}`}>{cleanNarrativeText(scoreSummary)}</p>
                  </div>
                )}

                {featuredCharity?.impactHighlight && (
                  <div className={`p-5 rounded-xl mb-6 ${dk ? 'bg-gradient-to-br from-emerald-900/40 to-emerald-800/20 border border-emerald-700/30' : 'bg-gradient-to-br from-emerald-50 to-emerald-100/50 border border-emerald-200/50'}`}>
                    <div className={`text-xs font-bold uppercase tracking-wider mb-2 ${dk ? 'text-emerald-400' : 'text-emerald-700'}`}>Why They Stand Out</div>
                    <div className={`text-lg leading-relaxed ${dk ? 'text-slate-200' : 'text-slate-700'}`}>{featuredCharity.impactHighlight}</div>
                  </div>
                )}

                <Link
                  to={`/charity/${featuredCharity?.ein}`}
                  onClick={() => trackHeroCTA('view_featured_evaluation', `/charity/${featuredCharity?.ein}`)}
                  className="w-full flex items-center justify-center gap-2 py-4 bg-gradient-to-r from-emerald-600 to-emerald-500 text-white rounded-xl text-base font-bold hover:from-emerald-500 hover:to-emerald-400 transition-all shadow-lg shadow-emerald-500/25"
                >
                  View Full Evaluation
                  <ArrowRight className="w-5 h-5" aria-hidden="true" />
                </Link>
                <Link
                  to="/browse"
                  onClick={() => trackHeroCTA('browse_all_charities', '/browse')}
                  className={`block text-center text-sm mt-2 transition-colors ${dk ? 'text-slate-400 hover:text-emerald-400' : 'text-slate-500 hover:text-emerald-600'}`}
                >
                  Or browse all {count}+ charities &rarr;
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Join Community */}
      <section className={`py-16 lg:py-20 transition-colors duration-500 ${dk ? 'bg-slate-900' : 'bg-slate-50'}`}>
        <div className="max-w-3xl mx-auto px-6 lg:px-8 text-center">
          <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full mb-5 md:mb-6 ${dk ? 'bg-emerald-500/10 border border-emerald-500/30' : 'bg-emerald-50 border border-emerald-200'}`}>
            <Heart className={`w-4 h-4 ${dk ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />
            <span className={`text-sm font-medium ${dk ? 'text-emerald-400' : 'text-emerald-700'}`}>Free access</span>
          </div>
          <h2 className={`text-2xl md:text-3xl lg:text-4xl font-bold font-merriweather mb-3 md:mb-4 [text-wrap:balance] ${dk ? 'text-white' : 'text-slate-900'}`}>
            Go deeper on the charities you care about
          </h2>
          <p className={`text-sm md:text-lg leading-relaxed mb-6 md:mb-8 max-w-xl mx-auto ${dk ? 'text-slate-300' : 'text-slate-600'}`}>
            Unlock full evaluations and giving plan tools — set a zakat target, organize charities into giving buckets, and track your annual plan. Free, always.
          </p>
          <SignInButton
            variant="button"
            context="landing_desktop_cta"
            className={`px-8 py-4 md:px-10 md:py-5 rounded-full font-bold text-lg md:text-xl transition-all duration-300 shadow-lg ${
              dk
                ? 'bg-emerald-500 text-white hover:bg-emerald-400 shadow-emerald-500/25'
                : 'bg-emerald-600 text-white hover:bg-emerald-500 shadow-emerald-500/25'
            }`}
          />
        </div>
      </section>
    </div>
  );

  return (
    <>
      <div className="lg:hidden">{mobileLayout}</div>
      <div className="hidden lg:block">{desktopLayout}</div>
    </>
  );
};

/* ── Helpers ── */

function Badge({ dk, value, label, color, large = false }: { dk: boolean; value: string; label: string; color: 'blue' | 'emerald' | 'purple'; large?: boolean }) {
  const styles = {
    blue: { box: dk ? 'bg-blue-500/10 border-blue-500/20' : 'bg-blue-50 border-blue-100', text: dk ? 'text-blue-400' : 'text-blue-600' },
    emerald: { box: dk ? 'bg-emerald-500/10 border-emerald-500/20' : 'bg-emerald-50 border-emerald-100', text: dk ? 'text-emerald-400' : 'text-emerald-600' },
    purple: { box: dk ? 'bg-purple-500/10 border-purple-500/20' : 'bg-purple-50 border-purple-100', text: dk ? 'text-purple-400' : 'text-purple-600' },
  };
  const s = styles[color];
  return (
    <div className={`${large ? 'p-4' : 'p-2.5'} rounded-xl text-center border ${s.box}`}>
      <div className={`${large ? 'text-xl' : 'text-sm'} font-bold ${s.text}`}>{value}</div>
      <div className={`${large ? 'text-xs' : 'text-[10px]'} font-medium mt-0.5 ${dk ? 'text-slate-400' : 'text-slate-500'}`}>{label}</div>
    </div>
  );
}
