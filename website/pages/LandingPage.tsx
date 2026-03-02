/**
 * Landing Page — Responsive Layout
 *
 * Desktop (>=1024px): Traditional vertical scroll — 3 sections
 * Mobile (<1024px): Horizontal scroll-snap — 3 viewport panels
 */

import React, { useMemo, useRef, useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Scale, ArrowRight, CheckCircle, Search, Heart, ChevronLeft, ChevronRight } from 'lucide-react';
import { SignInButton } from '../src/auth/SignInButton';
import { useAuth } from '../src/auth/useAuth';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import { THEMES } from '../src/themes';
import { trackHeroCTA } from '../src/utils/analytics';
import { TOP_CHARITY_FOR_LANDING } from '../src/data/topCharity';
import { useCharities } from '../src/hooks/useCharities';
import { isPubliclyVisible } from '../src/utils/tierUtils';

const featuredCharity = TOP_CHARITY_FOR_LANDING;
const LIGHT_THEME_INDEX = 4;
const DARK_THEME_INDEX = 2;
const PANEL_COUNT = 3;
const PANEL_LABELS = ['Welcome', 'Our Approach', 'Real Data'];
const LG = 1024;

function useIsMobile() {
  const [mobile, setMobile] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth < LG : false
  );
  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${LG - 1}px)`);
    const handler = (e: MediaQueryListEvent) => setMobile(e.matches);
    mq.addEventListener('change', handler);
    setMobile(mq.matches);
    return () => mq.removeEventListener('change', handler);
  }, []);
  return mobile;
}

export const LandingPage: React.FC = () => {
  const { isDark } = useLandingTheme();
  const theme = THEMES[isDark ? DARK_THEME_INDEX : LIGHT_THEME_INDEX];
  const { charities } = useCharities();
  const charityCount = useMemo(() => charities.filter(isPubliclyVisible).length, [charities]);
  const scoreDetails = featuredCharity?.amalEvaluation?.score_details;
  const confidenceBadge = scoreDetails?.data_confidence?.badge ?? '\u2014';
  const riskLevel = scoreDetails?.risks?.overall_risk_level ?? 'UNKNOWN';
  const zakatClaimed = scoreDetails?.zakat?.charity_claims_zakat;
  const walletLabel = zakatClaimed === true ? 'Zakat Claimed' : zakatClaimed === false ? 'Sadaqah Route' : 'Wallet Unclear';
  const scoreSummary = scoreDetails?.score_summary;
  const isMobile = useIsMobile();
  const { isSignedIn } = useAuth();

  const dk = theme.id.includes('dark') || theme.id === 'warm-atmosphere';

  // ── Mobile horizontal-scroll state ──
  const scrollRef = useRef<HTMLDivElement>(null);
  const [activePanel, setActivePanel] = useState(0);

  useEffect(() => {
    if (!isMobile) return;
    const el = scrollRef.current;
    if (!el) return;
    const handleScroll = () => setActivePanel(Math.round(el.scrollLeft / el.clientWidth));
    el.addEventListener('scroll', handleScroll, { passive: true });
    return () => el.removeEventListener('scroll', handleScroll);
  }, [isMobile]);

  const scrollToPanel = useCallback((index: number) => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ left: Math.max(0, Math.min(PANEL_COUNT - 1, index)) * el.clientWidth, behavior: 'smooth' });
  }, []);

  useEffect(() => {
    if (!isMobile) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      const el = scrollRef.current;
      if (!el) return;
      const cur = Math.round(el.scrollLeft / el.clientWidth);
      if (e.key === 'ArrowRight') { e.preventDefault(); scrollToPanel(cur + 1); }
      if (e.key === 'ArrowLeft') { e.preventDefault(); scrollToPanel(cur - 1); }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isMobile, scrollToPanel]);

  useEffect(() => {
    if (!isMobile) return;
    const el = scrollRef.current;
    if (!el) return;
    const handleWheel = (e: WheelEvent) => {
      if ((e.target as HTMLElement).closest('[data-scroll-internal]')) return;
      e.preventDefault();
      el.scrollLeft += e.deltaY;
    };
    el.addEventListener('wheel', handleWheel, { passive: false });
    return () => el.removeEventListener('wheel', handleWheel);
  }, [isMobile]);

  // ── Shared content pieces ──

  const heroContent = (
    <>
      <div className={`mb-4 md:mb-6 ${dk ? 'text-slate-500' : 'text-emerald-800/60'}`}>
        <span className="font-arabic text-base md:text-lg tracking-wider" dir="rtl" lang="ar">
          بِسْمِ ٱللَّٰهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ
        </span>
      </div>
      <h1 className={`text-[2rem] md:text-5xl lg:text-7xl font-bold font-merriweather tracking-tight mb-3 md:mb-5 leading-[1.1] [text-wrap:balance] ${theme.textMain}`}>
        Independent Research on the{' '}
        <br className="hidden md:block" />
        <span className={theme.textAccent}>Charities You Trust</span>
      </h1>
      <p className={`text-[15px] md:text-xl leading-relaxed mb-5 md:mb-8 max-w-2xl mx-auto ${theme.textSub}`}>
        Financials, impact evidence, and how your dollar travels — for the charities you already know.
      </p>
      <Link
        to="/browse"
        onClick={() => trackHeroCTA('browse_charities_primary', '/browse')}
        className={`inline-flex items-center justify-center gap-2 md:gap-3 px-8 py-3.5 md:px-10 md:py-5 rounded-full font-bold text-lg md:text-xl group transition-all duration-300 shadow-lg ${theme.btnPrimary}`}
      >
        <Search className="w-5 h-5 md:w-6 md:h-6" aria-hidden="true" />
        Browse Charities
        <ArrowRight className="w-4 h-4 md:w-5 md:h-5 group-hover:translate-x-1 transition-transform" aria-hidden="true" />
      </Link>
      <div className="mt-3 md:mt-4">
        <Link
          to="/methodology"
          onClick={() => trackHeroCTA('methodology', '/methodology')}
          className={`text-xs md:text-sm font-medium transition-colors ${dk ? 'text-slate-400 hover:text-white' : 'text-slate-500 hover:text-slate-900'}`}
        >
          How we evaluate charities →
        </Link>
      </div>
      <div className={`mt-5 md:mt-8 flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs md:text-sm ${theme.stats}`}>
        <span><strong className={theme.statsStrong}>{charityCount > 0 ? charityCount : '170+'}</strong> Evaluated</span>
        <span className={dk ? 'text-white/20' : 'text-slate-300'}>·</span>
        <span><strong className={theme.statsStrong}>Program</strong> Outcomes</span>
        <span className={dk ? 'text-white/20' : 'text-slate-300'}>·</span>
        <span><strong className={theme.statsStrong}>Independent</strong> Research</span>
      </div>
    </>
  );

  const bulletPoints = (
    <ul className="space-y-5">
      {[
        { title: 'Evidence of Impact', desc: 'Do their programs actually change lives? We check.' },
        { title: 'Cost-Effectiveness', desc: 'How far does each dollar go compared to peers?' },
        { title: 'Zakat & Sadaqah', desc: 'Is this charity Zakat-eligible? No guessing needed.' },
      ].map(({ title, desc }) => (
        <li key={title} className="flex items-start gap-3">
          <CheckCircle className={`w-5 h-5 flex-shrink-0 mt-0.5 ${dk ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />
          <div>
            <span className={`font-semibold ${dk ? 'text-slate-100' : 'text-slate-800'}`}>{title}</span>
            <span className={`block text-sm mt-0.5 ${dk ? 'text-slate-400' : 'text-slate-500'}`}>{desc}</span>
          </div>
        </li>
      ))}
    </ul>
  );

  const evaluationCard = (compact: boolean) => (
    <div className={`relative ${compact ? 'p-5' : 'p-8'} rounded-2xl shadow-2xl backdrop-blur-sm ${dk ? 'bg-slate-800/90 border border-slate-600/50 ring-1 ring-white/10' : 'bg-white border border-slate-200 ring-1 ring-slate-100'}`}>
      <div className={`mb-${compact ? '4' : '8'} pb-${compact ? '3' : '6'} border-b ${dk ? 'border-slate-700/50' : 'border-slate-100'}`}>
        <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 mb-2">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-[10px] font-bold text-emerald-500 uppercase tracking-wider">Featured Evaluation</span>
        </div>
        <div className={`${compact ? 'text-lg' : 'text-2xl'} font-bold ${dk ? 'text-white' : 'text-slate-900'}`}>{featuredCharity?.name || 'Loading...'}</div>
        <div className={`text-${compact ? 'xs' : 'sm'} line-clamp-2 mt-0.5 ${dk ? 'text-slate-400' : 'text-slate-500'}`}>{featuredCharity?.headline || ''}</div>
      </div>

      <div className={`grid grid-cols-3 gap-2 mb-${compact ? '4' : '8'}`}>
        <Badge dk={dk} value={confidenceBadge} label="Confidence" color="blue" compact={compact} />
        <Badge dk={dk} value={riskLevel} label="Risk" color="emerald" compact={compact} />
        <Badge dk={dk} value={walletLabel} label="Route" color="purple" compact={compact} />
      </div>

      {scoreSummary && (
        <div className={`p-${compact ? '3' : '5'} rounded-xl mb-${compact ? '4' : '6'} ${dk ? 'bg-slate-900/80 border border-slate-700/50' : 'bg-slate-50 border border-slate-200'}`}>
          <div className={`text-${compact ? '[10px]' : 'xs'} font-bold uppercase tracking-wider mb-1.5 ${dk ? 'text-slate-400' : 'text-slate-500'}`}>Evaluation Summary</div>
          <p className={`text-${compact ? 'xs' : 'sm'} leading-relaxed line-clamp-3 ${dk ? 'text-slate-300' : 'text-slate-700'}`}>{scoreSummary}</p>
        </div>
      )}

      {featuredCharity?.impactHighlight && !compact && (
        <div className={`p-5 rounded-xl mb-6 ${dk ? 'bg-gradient-to-br from-emerald-900/40 to-emerald-800/20 border border-emerald-700/30' : 'bg-gradient-to-br from-emerald-50 to-emerald-100/50 border border-emerald-200/50'}`}>
          <div className={`text-xs font-bold uppercase tracking-wider mb-2 ${dk ? 'text-emerald-400' : 'text-emerald-700'}`}>Why They Stand Out</div>
          <div className={`text-lg leading-relaxed ${dk ? 'text-slate-200' : 'text-slate-700'}`}>{featuredCharity.impactHighlight}</div>
        </div>
      )}

      <Link
        to={`/charity/${featuredCharity?.ein}`}
        onClick={() => trackHeroCTA('view_featured_evaluation', `/charity/${featuredCharity?.ein}`)}
        className={`w-full flex items-center justify-center gap-2 py-${compact ? '3' : '4'} bg-gradient-to-r from-emerald-600 to-emerald-500 text-white rounded-xl text-${compact ? 'sm' : 'base'} font-bold hover:from-emerald-500 hover:to-emerald-400 transition-all shadow-lg shadow-emerald-500/25`}
      >
        View Full Evaluation
        <ArrowRight className={compact ? 'w-4 h-4' : 'w-5 h-5'} aria-hidden="true" />
      </Link>
      <Link
        to="/browse"
        onClick={() => trackHeroCTA('browse_all_charities', '/browse')}
        className={`block text-center text-${compact ? 'xs' : 'sm'} mt-2 transition-colors ${dk ? 'text-slate-400 hover:text-emerald-400' : 'text-slate-500 hover:text-emerald-600'}`}
      >
        Or browse all {charityCount > 0 ? `${charityCount}+` : '170+'} charities &rarr;
      </Link>
    </div>
  );

  const joinContent = (
    <>
      <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full mb-5 md:mb-6 ${dk ? 'bg-emerald-500/10 border border-emerald-500/30' : 'bg-emerald-50 border border-emerald-200'}`}>
        <Heart className={`w-4 h-4 ${dk ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />
        <span className={`text-sm font-medium ${dk ? 'text-emerald-400' : 'text-emerald-700'}`}>Community Access</span>
      </div>
      <h2 className={`text-2xl md:text-3xl lg:text-4xl font-bold font-merriweather mb-3 md:mb-4 [text-wrap:balance] ${dk ? 'text-white' : 'text-slate-900'}`}>
        Go deeper on the charities you care about
      </h2>
      <p className={`text-sm md:text-lg leading-relaxed mb-6 md:mb-8 max-w-xl mx-auto ${dk ? 'text-slate-300' : 'text-slate-600'}`}>
        Unlock full evaluations — leadership, financial history, impact evidence, and donor fit. Free, always.
      </p>
      <SignInButton
        variant="button"
        className={`px-8 py-4 md:px-10 md:py-5 rounded-full font-bold text-lg md:text-xl transition-all duration-300 shadow-lg ${
          dk
            ? 'bg-emerald-500 text-white hover:bg-emerald-400 shadow-emerald-500/25'
            : 'bg-emerald-600 text-white hover:bg-emerald-500 shadow-emerald-500/25'
        }`}
      />
    </>
  );

  /* ════════════════════════════════════════════
     MOBILE: Horizontal 3-panel scroll-snap
     ════════════════════════════════════════════ */
  if (isMobile) {
    const panelBase = 'w-screen h-full flex-shrink-0 snap-start flex flex-col relative overflow-hidden pb-[12vh]';
    return (
      <div className={`h-full overflow-hidden relative ${theme.bgPage} font-sans transition-colors duration-500`}>
        <div ref={scrollRef} className="flex h-full overflow-x-auto snap-x snap-mandatory scrollbar-hide">

          {/* Panel 1: Hero */}
          <section className={`${panelBase} justify-center ${theme.bgHero}`}>
            {theme.backgroundElements}
            <div className="relative z-10 max-w-4xl mx-auto px-5 text-center">
              {heroContent}
            </div>
            <button onClick={() => scrollToPanel(1)} className={`absolute right-3 top-1/2 -translate-y-1/2 p-2 rounded-full animate-pulse z-10 ${dk ? 'text-white/30' : 'text-slate-300'}`} aria-label="Next">
              <ChevronRight className="w-5 h-5" />
            </button>
          </section>

          {/* Panel 2: What We Reveal */}
          <section className={`${panelBase} justify-center ${dk ? 'bg-slate-950' : 'bg-white'}`}>
            <div className="max-w-xl mx-auto px-6">
              <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full mb-5 ${dk ? 'bg-emerald-500/10 border border-emerald-500/30' : 'bg-emerald-50 border border-emerald-200'}`}>
                <Scale className={`w-3.5 h-3.5 ${dk ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />
                <span className={`text-xs font-medium ${dk ? 'text-emerald-400' : 'text-emerald-700'}`}>What We Show You</span>
              </div>
              <h2 className={`text-2xl font-bold font-merriweather mb-3 leading-tight [text-wrap:balance] ${dk ? 'text-white' : 'text-slate-900'}`}>
                What you{'\u2019'}ve never been able to see
              </h2>
              <p className={`text-sm leading-relaxed mb-6 ${dk ? 'text-slate-400' : 'text-slate-600'}`}>
                Charities share stories. We dig into the data behind them.
              </p>
              {bulletPoints}
            </div>
            <EdgeArrows dk={dk} onLeft={() => scrollToPanel(0)} onRight={() => scrollToPanel(2)} />
          </section>

          {/* Panel 3: Featured Evaluation */}
          <section className={`${panelBase} justify-center items-center ${dk ? 'bg-slate-900' : 'bg-slate-50'}`}>
            <div className="relative w-full max-w-lg mx-auto px-5">
              <div className="absolute -inset-6 bg-gradient-to-r from-emerald-500/25 via-blue-500/15 to-purple-500/25 blur-3xl rounded-3xl opacity-60" />
              {evaluationCard(true)}
              {!isSignedIn && (
                <div className={`relative mt-4 flex flex-col items-center gap-2 text-center`}>
                  <p className={`text-sm font-medium ${dk ? 'text-slate-300' : 'text-slate-700'}`}>
                    See the full story behind every charity
                  </p>
                  <SignInButton
                    variant="button"
                    className={`px-6 py-2.5 rounded-full text-sm font-bold transition-all shadow-md ${
                      dk
                        ? 'bg-emerald-500 text-white hover:bg-emerald-400 shadow-emerald-500/20'
                        : 'bg-emerald-600 text-white hover:bg-emerald-500 shadow-emerald-500/20'
                    }`}
                  />
                  <span className={`text-[11px] ${dk ? 'text-slate-500' : 'text-slate-400'}`}>Free, always</span>
                </div>
              )}
            </div>
            <button onClick={() => scrollToPanel(1)} className={`absolute left-3 top-1/2 -translate-y-1/2 p-2 rounded-full z-10 ${dk ? 'text-white/25 hover:text-white/60' : 'text-slate-300 hover:text-slate-500'}`} aria-label="Previous">
              <ChevronLeft className="w-5 h-5" />
            </button>
          </section>
        </div>

        {/* Nav dots */}
        <div className={`absolute bottom-0 left-0 right-0 z-20 flex items-center justify-center gap-3 py-3 ${dk ? 'bg-gradient-to-t from-black/60 via-black/30 to-transparent' : 'bg-gradient-to-t from-white/70 via-white/40 to-transparent'}`}>
          <button onClick={() => scrollToPanel(activePanel - 1)} disabled={activePanel === 0} className={`p-1.5 rounded-full ${dk ? 'text-white/50 disabled:text-white/15' : 'text-slate-400 disabled:text-slate-200'}`} aria-label="Previous"><ChevronLeft className="w-4 h-4" /></button>
          <div className="flex items-center gap-2">
            {Array.from({ length: PANEL_COUNT }).map((_, i) => (
              <button key={i} onClick={() => scrollToPanel(i)} className="flex flex-col items-center gap-0.5 group" aria-label={`${PANEL_LABELS[i]}`}>
                <div className={`rounded-full transition-all duration-300 ${i === activePanel ? 'w-6 h-2 bg-emerald-500' : `w-2 h-2 ${dk ? 'bg-white/25' : 'bg-slate-300'}`}`} />
                <span className={`text-[9px] font-medium ${i === activePanel ? `${dk ? 'text-white/80' : 'text-slate-600'}` : 'text-transparent'}`}>{PANEL_LABELS[i]}</span>
              </button>
            ))}
          </div>
          <button onClick={() => scrollToPanel(activePanel + 1)} disabled={activePanel === PANEL_COUNT - 1} className={`p-1.5 rounded-full ${dk ? 'text-white/50 disabled:text-white/15' : 'text-slate-400 disabled:text-slate-200'}`} aria-label="Next"><ChevronRight className="w-4 h-4" /></button>
        </div>
      </div>
    );
  }

  /* ════════════════════════════════════════════
     DESKTOP: Traditional vertical scroll
     ════════════════════════════════════════════ */
  return (
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
            Independent Research on the{' '}
            <br className="hidden md:block" />
            <span className={theme.textAccent}>Charities You Trust</span>
          </h1>
          <p className={`text-xl leading-relaxed mb-8 max-w-2xl mx-auto ${theme.textSub}`}>
            See what{'\u2019'}s behind the names you already know — financials, impact evidence, and how your dollar travels.
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
                What you{'\u2019'}ve never been able to see
              </h2>
              <p className={`text-lg leading-relaxed mb-8 ${dk ? 'text-slate-300' : 'text-slate-600'}`}>
                Charities share stories. We dig into the data behind them — program outcomes, financial health, and where your dollar actually ends up.
              </p>
              {bulletPoints}
            </div>
            <div className="w-1/2 relative">
              <div className="absolute -inset-4 bg-gradient-to-r from-emerald-500/30 via-blue-500/20 to-purple-500/30 blur-3xl rounded-3xl opacity-60" />
              <div className="absolute -inset-1 bg-gradient-to-r from-emerald-500/20 to-blue-500/20 blur-xl rounded-2xl" />
              {evaluationCard(false)}
            </div>
          </div>
        </div>
      </section>

      {/* Join Community */}
      <section className={`py-16 lg:py-20 transition-colors duration-500 ${dk ? 'bg-slate-900' : 'bg-slate-50'}`}>
        <div className="max-w-3xl mx-auto px-6 lg:px-8 text-center">
          {joinContent}
        </div>
      </section>
    </div>
  );
};

/* ── Helpers ── */

function EdgeArrows({ dk, onLeft, onRight }: { dk: boolean; onLeft: () => void; onRight: () => void }) {
  const cls = `absolute top-1/2 -translate-y-1/2 p-2 rounded-full z-10 ${dk ? 'text-white/25 hover:text-white/60' : 'text-slate-300 hover:text-slate-500'}`;
  return (
    <>
      <button onClick={onLeft} className={`${cls} left-3`} aria-label="Previous"><ChevronLeft className="w-5 h-5" /></button>
      <button onClick={onRight} className={`${cls} right-3`} aria-label="Next"><ChevronRight className="w-5 h-5" /></button>
    </>
  );
}

function Badge({ dk, value, label, color, compact = false }: { dk: boolean; value: string; label: string; color: 'blue' | 'emerald' | 'purple'; compact?: boolean }) {
  const styles = {
    blue: { box: dk ? 'bg-blue-500/10 border-blue-500/20' : 'bg-blue-50 border-blue-100', text: dk ? 'text-blue-400' : 'text-blue-600' },
    emerald: { box: dk ? 'bg-emerald-500/10 border-emerald-500/20' : 'bg-emerald-50 border-emerald-100', text: dk ? 'text-emerald-400' : 'text-emerald-600' },
    purple: { box: dk ? 'bg-purple-500/10 border-purple-500/20' : 'bg-purple-50 border-purple-100', text: dk ? 'text-purple-400' : 'text-purple-600' },
  };
  const s = styles[color];
  return (
    <div className={`${compact ? 'p-2.5' : 'p-4'} rounded-xl text-center border ${s.box}`}>
      <div className={`${compact ? 'text-sm' : 'text-xl'} font-bold ${s.text}`}>{value}</div>
      <div className={`${compact ? 'text-[10px]' : 'text-xs'} font-medium mt-0.5 ${dk ? 'text-slate-400' : 'text-slate-500'}`}>{label}</div>
    </div>
  );
}
