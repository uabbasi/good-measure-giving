/**
 * Landing Page - Marketing Focus
 *
 * Structure:
 * 1. Top Bar (Bismillah) - Spiritual anchor
 * 2. Hero Section (Single dominant CTA: Browse Charities)
 * 3. Sample Audit (Dynamic top charity - auto-selected at build time)
 * 4. Mission + Request (Join Community CTA)
 *
 * Auth: "Join the Community" button in Navbar (not on landing page)
 * No charity listings on this page (those are on BrowsePage)
 */

import React from 'react';
import { Link } from 'react-router-dom';
import { Scale, ArrowRight, CheckCircle, Search, ShieldCheck, TrendingUp, Target, Heart } from 'lucide-react';
import { SignInButton } from '../src/auth/SignInButton';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import { THEMES } from '../src/themes';
import { trackHeroCTA } from '../src/utils/analytics';
import { TOP_CHARITY_FOR_LANDING } from '../src/data/topCharity';

// Featured charity data - dynamically selected at build time (highest-scoring charity)
const featuredCharity = TOP_CHARITY_FOR_LANDING;

// Theme indices: soft-noor (light) = 4, warm-atmosphere (dark) = 2
const LIGHT_THEME_INDEX = 4;
const DARK_THEME_INDEX = 2;



export const LandingPage: React.FC = () => {
  const { isDark } = useLandingTheme();
  const theme = THEMES[isDark ? DARK_THEME_INDEX : LIGHT_THEME_INDEX];

  return (

    <div className={`flex flex-col min-h-screen ${theme.bgPage} font-sans transition-colors duration-500`}>



      {/* TOP BAR: Spiritual Grounding */}

      <div className={`w-full py-4 text-center z-20 relative border-b transition-colors duration-500 ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' || theme.id === 'blueprint' ? 'bg-slate-950 text-slate-400 border-slate-800' : 'bg-emerald-900 text-emerald-100 border-emerald-800'}`}>

        <span className="font-arabic text-xl md:text-2xl tracking-wider opacity-90" dir="rtl" lang="ar">

          بِسْمِ ٱللَّٰهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ

        </span>

      </div>



      {/* Section 1: Hero */}

      <section className={`relative pt-12 pb-14 lg:pt-16 lg:pb-20 overflow-hidden transition-colors duration-500 ${theme.bgHero}`}>

        

        {/* Theme Background Elements */}

        {theme.backgroundElements}



        <div className="relative max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center z-10">



          {/* Quranic Verse Pill */}

          <div className={`inline-flex items-center gap-3 px-5 py-2.5 rounded-full mb-5 mx-auto transition-all duration-300 ${theme.pill}`}>

            <Scale className={`w-4 h-4 ${theme.pillIcon}`} aria-hidden="true" />

            <span className="text-sm font-serif italic tracking-wide">

              {'\u201C'}He raised the sky and set up the balance.{'\u201D'} — Surah Ar-Rahman [55:7]

            </span>

          </div>



          {/* Headline */}

          <h1 className={`text-5xl lg:text-7xl font-bold font-merriweather tracking-tight mb-6 leading-[1.1] [text-wrap:balance] transition-colors duration-300 ${theme.textMain}`}>
            From Guesswork to{' '}
            <br className="hidden md:block" />
            <span className={`${theme.textAccent}`}>Good Measure</span>
          </h1>



          {/* Subhead */}

          <div className="max-w-2xl mx-auto mb-8">

            <p className={`text-xl leading-relaxed mb-4 antialiased transition-colors duration-300 ${theme.textSub}`}>

              4-star ratings measure efficiency. We measure whether programs actually work.

            </p>

          </div>



          {/* Primary CTA - Single dominant action */}

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

              className={`text-sm font-medium transition-colors duration-300 ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-slate-400 hover:text-white' : 'text-slate-500 hover:text-slate-900'}`}

            >

              How we evaluate charities →

            </Link>

          </div>



          {/* Quick stats - Specific differentiators */}

          <div className={`flex flex-row flex-wrap sm:flex-nowrap justify-center gap-x-6 gap-y-3 text-sm border-t pt-6 px-6 transition-colors duration-300 ${theme.stats} ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'border-white/10' : 'border-slate-200'}`}>

            <div className="flex items-center gap-2">

              <CheckCircle className={`w-4 h-4 ${theme.pillIcon}`} aria-hidden="true" />

              <span><strong className={theme.statsStrong}>Multi-Source</strong> Verification</span>

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



      {/* Sample Audit Section - Real Evaluation Preview (Show, Don't Tell) */}

      <section className={`py-12 lg:py-16 relative z-10 overflow-hidden transition-colors duration-500 ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'bg-slate-950' : 'bg-white border-y border-slate-100'}`}>

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

          <div className="flex flex-col lg:flex-row items-center gap-8 lg:gap-10">

            <div className="lg:w-1/2">

              <h2 className={`text-3xl lg:text-4xl font-bold font-merriweather mb-5 [text-wrap:balance] ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-white' : 'text-slate-900'}`}>

                Don{'\u2019'}t guess. See the math.

              </h2>

              <p className={`text-lg leading-relaxed mb-8 ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-slate-300' : 'text-slate-600'}`}>

                Most charities show you sad photos. We show you which ones have proof their programs work{'\u2014'}and how far your donation actually goes.

              </p>

              <ul className="space-y-4">

                <li className="flex items-start gap-3">

                  <CheckCircle className={`w-5 h-5 flex-shrink-0 mt-0.5 ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />

                  <div>
                    <span className={`font-medium ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-slate-200' : 'text-slate-700'}`}>Evidence of Impact</span>
                    <span className={`block text-sm ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-slate-400' : 'text-slate-500'}`}>Does this charity track whether their programs actually change lives?</span>
                  </div>

                </li>

                <li className="flex items-start gap-3">

                  <CheckCircle className={`w-5 h-5 flex-shrink-0 mt-0.5 ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />

                  <div>
                    <span className={`font-medium ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-slate-200' : 'text-slate-700'}`}>Cost-Effectiveness</span>
                    <span className={`block text-sm ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-slate-400' : 'text-slate-500'}`}>How much impact per dollar, compared to similar charities?</span>
                  </div>

                </li>

                <li className="flex items-start gap-3">

                  <CheckCircle className={`w-5 h-5 flex-shrink-0 mt-0.5 ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />

                  <div>
                    <span className={`font-medium ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-slate-200' : 'text-slate-700'}`}>Zakat & Sadaqah Classification</span>
                    <span className={`block text-sm ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-slate-400' : 'text-slate-500'}`}>Is this charity Zakat-eligible? We check so you don{'\u2019'}t have to guess.</span>
                  </div>

                </li>

              </ul>

            </div>

            {/* The Sample Card Visual - Real TCF Evaluation */}

            <div className="lg:w-1/2 relative">

              {/* Glow effects */}
              <div className="absolute -inset-4 bg-gradient-to-r from-emerald-500/30 via-blue-500/20 to-purple-500/30 blur-3xl rounded-3xl opacity-60"></div>
              <div className="absolute -inset-1 bg-gradient-to-r from-emerald-500/20 to-blue-500/20 blur-xl rounded-2xl"></div>

              <div className={`relative p-8 rounded-2xl shadow-2xl backdrop-blur-sm ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'bg-slate-800/90 border border-slate-600/50 ring-1 ring-white/10' : 'bg-white border border-slate-200 ring-1 ring-slate-100'}`}>

                {/* Header with charity info and main score */}
                <div className={`flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between mb-8 pb-6 border-b ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'border-slate-700/50' : 'border-slate-100'}`}>

                  <div className="flex-1">
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 mb-3">
                      <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
                      <span className="text-xs font-bold text-emerald-500 uppercase tracking-wider">Top Rated</span>
                    </div>
                    <div className={`text-2xl font-bold mb-1 ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-white' : 'text-slate-900'}`}>{featuredCharity?.name || 'Loading...'}</div>
                    <div className={`text-sm line-clamp-2 ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-slate-400' : 'text-slate-500'}`}>{featuredCharity?.headline || ''}</div>
                  </div>

                  <div className="text-left sm:text-right sm:pl-4">
                    <div className="text-5xl font-bold text-emerald-500 leading-none">{featuredCharity?.amalEvaluation?.amal_score ?? '—'}</div>
                    <div className={`text-lg font-normal ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-slate-500' : 'text-slate-400'}`}>/ 100</div>
                    <div className={`text-xs font-semibold uppercase tracking-wider mt-1 ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-slate-400' : 'text-slate-500'}`}>GMG Score</div>
                  </div>

                </div>

                {/* Score Dimensions - Impact + Alignment + Data Confidence */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-8">
                  {(() => {
                    const isDark = theme.id.includes('dark') || theme.id === 'warm-atmosphere';
                    const dimensions = [
                      {
                        label: 'Impact',
                        subtitle: 'How far does $1 go?',
                        score: featuredCharity?.amalEvaluation?.score_details?.impact?.score ?? 0,
                        max: 50,
                        icon: TrendingUp,
                        text: isDark ? 'text-blue-400' : 'text-blue-600',
                        bg: isDark ? 'bg-blue-500/10 border-blue-500/20' : 'bg-blue-50 border-blue-100',
                        iconBg: isDark ? 'bg-blue-500/20' : 'bg-blue-100',
                      },
                      {
                        label: 'Alignment',
                        subtitle: 'Right for your giving?',
                        score: featuredCharity?.amalEvaluation?.score_details?.alignment?.score ?? 0,
                        max: 50,
                        icon: Target,
                        text: isDark ? 'text-emerald-400' : 'text-emerald-600',
                        bg: isDark ? 'bg-emerald-500/10 border-emerald-500/20' : 'bg-emerald-50 border-emerald-100',
                        iconBg: isDark ? 'bg-emerald-500/20' : 'bg-emerald-100',
                      },
                      {
                        label: 'Confidence',
                        subtitle: 'Can we verify claims?',
                        score: null,
                        badge: featuredCharity?.amalEvaluation?.score_details?.data_confidence?.badge ?? '—',
                        icon: ShieldCheck,
                        text: isDark ? 'text-purple-400' : 'text-purple-600',
                        bg: isDark ? 'bg-purple-500/10 border-purple-500/20' : 'bg-purple-50 border-purple-100',
                        iconBg: isDark ? 'bg-purple-500/20' : 'bg-purple-100',
                      },
                    ];
                    return dimensions.map((item) => {
                      const Icon = item.icon;
                      return (
                        <div key={item.label} className={`p-4 rounded-xl text-center border ${item.bg}`}>
                          <div className={`w-10 h-10 mx-auto mb-3 rounded-lg flex items-center justify-center ${item.iconBg}`}>
                            <Icon className={`w-5 h-5 ${item.text}`} aria-hidden="true" />
                          </div>
                          {'badge' in item && item.badge ? (
                            <div className={`text-xl font-bold ${item.text}`}>{item.badge}</div>
                          ) : (
                            <div className={`text-2xl font-bold ${item.text}`}>
                              {item.score}<span className="text-base opacity-40 font-normal"> / {item.max}</span>
                            </div>
                          )}
                          <div className={`text-xs font-medium mt-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{item.label}</div>
                          <div className={`text-[10px] mt-0.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>{item.subtitle}</div>
                        </div>
                      );
                    });
                  })()}
                </div>

                {/* Score Breakdown - Show the math */}
                {featuredCharity?.amalEvaluation?.score_details && (
                  <div className={`p-5 rounded-xl mb-6 ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'bg-slate-900/80 border border-slate-700/50' : 'bg-slate-50 border border-slate-200'}`}>
                    <div className={`text-xs font-bold uppercase tracking-wider mb-3 ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-slate-400' : 'text-slate-500'}`}>How This Score Was Calculated</div>
                    <div className="space-y-2 text-sm">
                      {/* Impact */}
                      {featuredCharity.amalEvaluation.score_details.impact && (
                      <div className={`flex justify-between ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-slate-300' : 'text-slate-600'}`}>
                        <span>Impact</span>
                        <span className="font-mono">{featuredCharity.amalEvaluation.score_details.impact.score}/50</span>
                      </div>
                      )}
                      {/* Alignment */}
                      {featuredCharity.amalEvaluation.score_details.alignment && (
                      <div className={`flex justify-between ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-slate-300' : 'text-slate-600'}`}>
                        <span>Alignment</span>
                        <span className="font-mono">{featuredCharity.amalEvaluation.score_details.alignment.score}/50</span>
                      </div>
                      )}
                      {/* Risk deduction if any */}
                      {(featuredCharity.amalEvaluation.score_details?.risks?.total_deduction ?? 0) > 0 && (
                        <div className={`flex justify-between pt-2 border-t ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'border-slate-700 text-amber-400' : 'border-slate-200 text-amber-600'}`}>
                          <span>Risk adjustment</span>
                          <span className="font-mono">-{featuredCharity.amalEvaluation.score_details?.risks?.total_deduction}</span>
                        </div>
                      )}
                      {/* Total */}
                      <div className={`flex justify-between pt-2 border-t font-bold ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'border-slate-700 text-white' : 'border-slate-300 text-slate-900'}`}>
                        <span>Total</span>
                        <span className="font-mono">{featuredCharity.amalEvaluation.amal_score}/100</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Impact highlight - dynamic from build */}
                {featuredCharity?.impactHighlight && (
                  <div className={`p-5 rounded-xl mb-6 ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'bg-gradient-to-br from-emerald-900/40 to-emerald-800/20 border border-emerald-700/30' : 'bg-gradient-to-br from-emerald-50 to-emerald-100/50 border border-emerald-200/50'}`}>
                    <div className={`text-xs font-bold uppercase tracking-wider mb-2 ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-emerald-400' : 'text-emerald-700'}`}>Why They Stand Out</div>
                    <div className={`text-lg leading-relaxed ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-slate-200' : 'text-slate-700'}`}>
                      {featuredCharity.impactHighlight}
                    </div>
                  </div>
                )}

                <Link
                  to={`/charity/${featuredCharity?.ein}`}
                  onClick={() => trackHeroCTA('view_featured_evaluation', `/charity/${featuredCharity?.ein}`)}
                  className="w-full flex items-center justify-center gap-2 py-4 bg-gradient-to-r from-emerald-600 to-emerald-500 text-white rounded-xl text-base font-bold hover:from-emerald-500 hover:to-emerald-400 transition-all shadow-lg shadow-emerald-500/25 hover:shadow-emerald-500/40"
                >
                  View Full Evaluation
                  <ArrowRight className="w-5 h-5" aria-hidden="true" />
                </Link>

              </div>

            </div>

          </div>

        </div>

      </section>

      {/* Section 3: Join the Community CTA */}
      <section className={`py-16 lg:py-20 transition-colors duration-500 ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'bg-slate-900' : 'bg-slate-50'}`}>
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full mb-6 ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'bg-emerald-500/10 border border-emerald-500/30' : 'bg-emerald-50 border border-emerald-200'}`}>
            <Heart className={`w-4 h-4 ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />
            <span className={`text-sm font-medium ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-emerald-400' : 'text-emerald-700'}`}>Free forever</span>
          </div>
          <h2 className={`text-3xl lg:text-4xl font-bold font-merriweather mb-4 [text-wrap:balance] ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-white' : 'text-slate-900'}`}>
            Build your giving plan
          </h2>
          <p className={`text-lg leading-relaxed mb-8 max-w-xl mx-auto ${theme.id.includes('dark') || theme.id === 'warm-atmosphere' ? 'text-slate-300' : 'text-slate-600'}`}>
            Save charities, compare evaluations, and get personalized research — all with a free community membership.
          </p>
          <SignInButton
            variant="button"
            className={`px-10 py-5 min-h-[56px] rounded-full font-bold text-xl transition-all duration-300 shadow-lg ${
              theme.id.includes('dark') || theme.id === 'warm-atmosphere'
                ? 'bg-emerald-500 text-white hover:bg-emerald-400 shadow-emerald-500/25'
                : 'bg-emerald-600 text-white hover:bg-emerald-500 shadow-emerald-500/25'
            }`}
          />
        </div>
      </section>





    </div>

  );

};
