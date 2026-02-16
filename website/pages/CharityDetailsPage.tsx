import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ShieldCheck,
  Target,
  ArrowLeft,
  Users,
  MapPin,
  Activity,
  Lock,
  BookOpen,
  Info,
  ExternalLink,
  Briefcase,
  TrendingUp,
  ChevronRight,
  ChevronDown,
  Globe,
  CheckCircle2,
  Database,
  AlertTriangle
} from 'lucide-react';
import { useCharity } from '../src/hooks/useCharities';
import { CharityProfile, AmalEvaluation, RatingColor } from '../types';
import { ScoreVisualizer, ScoreVariant } from '../components/ScoreVisualizer';
import { AssessmentCard, RatingIcon } from '../components/MetricCard';
import { SourceAttribution } from '../src/components/SourceAttribution';
import { TerminalView } from '../src/components/views';
import { isRichTier, isBaselineTier, isHiddenTier } from '../src/utils/tierUtils';
import { useCommunityMember, CommunityGate, JoinCommunityPrompt } from '../src/auth';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import { BookmarkButton } from '../src/components/BookmarkButton';

// Layout simplified - hidden tier charities use legacy layout only

// Helper function to format wallet tags with modifier first
const formatWalletTag = (tag: string): string => {
  // Remove brackets if present
  const cleanTag = tag?.replace(/[\[\]]/g, '') || '';

  // Map to display format with modifier first
  if (cleanTag.includes('ZAKAT-ELIGIBLE') || cleanTag.includes('ZAKAT-CONSENSUS') || cleanTag.includes('ZAKAT-TRADITIONAL')) {
    return 'Zakat Eligible';
  }
  if (cleanTag.includes('SADAQAH-STRATEGIC') || cleanTag.includes('STRATEGIC-SADAQAH') || cleanTag.includes('SADAQAH-CATALYTIC')) {
    return 'Strategic Sadaqah';
  }
  if (cleanTag.includes('SADAQAH-GENERAL')) {
    return 'General Sadaqah';
  }
  if (cleanTag.includes('INSUFFICIENT-DATA')) {
    return 'Insufficient Data';
  }

  // Fallback to formatted tag
  return cleanTag.replace('-', ' ');
};

export const CharityDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  // Load charity from exported JSON files
  const { charity, loading, error } = useCharity(id || '');
  const { isDark } = useLandingTheme();

  // Check community membership for content gating (must be called unconditionally)
  const isCommunityMember = useCommunityMember();

  // Set page title with charity name
  useEffect(() => {
    if (charity) {
      document.title = `${charity.name} | Good Measure Giving`;
    }
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, [charity]);

  // UX State - simplified to single layout for hidden tier charities
  const [visualVariant, setVisualVariant] = useState<ScoreVariant>('arch');

  // Loading state
  if (loading) {
    return (
      <div className={`min-h-screen flex items-center justify-center px-4 ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
        <div className={`rounded-2xl shadow-sm p-10 text-center max-w-md ${isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-slate-200'}`}>
          <div className="animate-pulse">
            <div className={`h-8 w-48 rounded mx-auto mb-4 ${isDark ? 'bg-slate-700' : 'bg-slate-200'}`} />
            <div className={`h-4 w-32 rounded mx-auto ${isDark ? 'bg-slate-700' : 'bg-slate-200'}`} />
          </div>
        </div>
      </div>
    );
  }

  if (!charity || error) {
    return (
      <div className={`min-h-screen flex items-center justify-center px-4 ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
        <div className={`rounded-2xl shadow-sm p-10 text-center max-w-md ${isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-slate-200'}`}>
          <h1 className={`text-2xl font-bold font-merriweather mb-3 ${isDark ? 'text-white' : 'text-slate-900'}`}>Charity not found</h1>
          <p className={`mb-6 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>The charity you're looking for isn't in our directory.</p>
          <Link to="/browse" className={`inline-flex items-center gap-2 px-4 py-3 rounded-lg text-sm font-bold transition-colors ${isDark ? 'bg-slate-700 text-white hover:bg-slate-600' : 'bg-slate-900 text-white hover:bg-slate-800'}`}>
            <ArrowLeft className="w-4 h-4" aria-hidden="true" />
            Back to Directory
          </Link>
        </div>
      </div>
    );
  }

  // Rich and baseline tiers use the terminal view
  if (isRichTier(charity) || isBaselineTier(charity)) {
    return <TerminalView charity={charity} />;
  }

  // Hidden tier indicator (accessible via direct URL)
  const isHidden = isHiddenTier(charity);

  // Determine if we have Amal data
  const hasAmalData = !!charity.amalEvaluation;
  const amal = charity.amalEvaluation;

  // Helper functions
  const toggleVariant = () => {
    const variants: ScoreVariant[] = ['arch', 'ring', 'seal', 'spider'];
    const currentIndex = variants.indexOf(visualVariant);
    setVisualVariant(variants[(currentIndex + 1) % variants.length]);
  };

  const getWalletTagStyles = (tag: string) => {
    if (tag?.includes('ZAKAT-ELIGIBLE') || tag?.includes('ZAKAT-CONSENSUS') || tag?.includes('ZAKAT-TRADITIONAL')) {
      return 'bg-emerald-100 text-emerald-800 border-emerald-200';
    }
    if (tag?.includes('SADAQAH-STRATEGIC') || tag?.includes('STRATEGIC-SADAQAH') || tag?.includes('SADAQAH-CATALYTIC')) {
      return 'bg-indigo-100 text-indigo-800 border-indigo-200';
    }
    if (tag?.includes('INSUFFICIENT-DATA')) return 'bg-slate-100 text-slate-600 border-slate-200';
    if (tag?.includes('SADAQAH-GENERAL')) return 'bg-slate-100 text-slate-800 border-slate-200';
    return 'bg-slate-100 text-slate-800 border-slate-200';
  };

  // Helper: Convert score to rating label
  const getRatingFromScore = (score: number): string => {
    if (score >= 80) return 'Exemplary';
    if (score >= 60) return 'Strong';
    if (score >= 40) return 'Developing';
    return 'Emerging';
  };

  // Helper: Get badge styles based on rating
  const getRatingBadgeStyles = (rating: string): string => {
    switch (rating) {
      case 'Exemplary': return 'bg-emerald-100 text-emerald-800 border-emerald-200';
      case 'Strong': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'Developing': return 'bg-amber-100 text-amber-800 border-amber-200';
      default: return 'bg-slate-100 text-slate-800 border-slate-200';
    }
  };

  // MobileHeroSummary: Compact summary for mobile, visible only on small screens
  const MobileHeroSummary: React.FC<{ amal: AmalEvaluation }> = ({ amal }) => {
    const rating = getRatingFromScore(amal.amal_score);
    const tier1 = amal.tier_1_strategic_fit;
    const tier2 = amal.tier_2_execution;
    const headline = amal.summary?.headline;

    return (
      <div className="lg:hidden mb-6">
        <div className={`rounded-xl shadow-sm p-5 ${isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-slate-200'}`}>
          {/* Score + Rating Row */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className={`text-4xl font-bold tabular-nums ${isDark ? 'text-emerald-400' : 'text-emerald-700'}`}>{amal.amal_score}</div>
              <div className="text-left">
                <div className="text-xs text-slate-400 uppercase tracking-wider">GMG Score</div>
                <span className={`inline-block mt-1 px-2 py-0.5 text-xs font-bold rounded border ${getRatingBadgeStyles(rating)}`}>
                  {rating}
                </span>
              </div>
            </div>
            {amal.wallet_routing && (
              <span className={`flex items-center gap-1 px-3 py-1.5 text-xs font-bold uppercase tracking-wider rounded-lg border ${getWalletTagStyles(amal.wallet_routing.tag)}`}>
                <Lock className="w-3 h-3" aria-hidden="true" />
                {formatWalletTag(amal.wallet_routing.tag)}
              </span>
            )}
          </div>

          {/* Tier Scores */}
          {tier1 && tier2 && (
            <div className={`flex gap-4 mb-4 pb-4 border-b ${isDark ? 'border-slate-800' : 'border-slate-100'}`}>
              <div className={`flex-1 text-center rounded-lg py-2 ${isDark ? 'bg-slate-800' : 'bg-slate-50'}`}>
                <div className={`text-lg font-bold tabular-nums ${isDark ? 'text-white' : 'text-slate-900'}`}>{tier1.subtotal}<span className="text-slate-400 text-sm">/50</span></div>
                <div className="text-[10px] text-slate-500 uppercase">Strategic</div>
              </div>
              <div className={`flex-1 text-center rounded-lg py-2 ${isDark ? 'bg-slate-800' : 'bg-slate-50'}`}>
                <div className={`text-lg font-bold tabular-nums ${isDark ? 'text-white' : 'text-slate-900'}`}>{tier2.subtotal}<span className="text-slate-400 text-sm">/50</span></div>
                <div className="text-[10px] text-slate-500 uppercase">Execution</div>
              </div>
            </div>
          )}

          {/* Headline */}
          {headline && (
            <p className={`text-sm font-medium leading-relaxed mb-4 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>{headline}</p>
          )}

          {/* Scroll to Details CTA */}
          <button
            onClick={() => document.getElementById('impact-memo')?.scrollIntoView({ behavior: 'smooth' })}
            className="w-full flex items-center justify-center gap-2 py-3 min-h-[44px] bg-slate-900 text-white rounded-lg text-sm font-bold hover:bg-slate-800 transition-colors"
          >
            View Full Impact Memo
            <ChevronDown className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>
      </div>
    );
  };

  const formatCurrency = (val?: number) => {
    if (!val) return 'N/A';
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val);
  };

  // Get financials from either nested object or flat rawData
  const getFinancials = () => {
    const f = charity.financials || charity.rawData.financials;
    return {
      totalRevenue: f?.totalRevenue || charity.rawData.total_revenue,
      programExpenses: f?.programExpenses,
      adminExpenses: f?.adminExpenses || charity.rawData.admin_expenses,
      fundraisingExpenses: f?.fundraisingExpenses || charity.rawData.fundraising_expenses,
      programExpenseRatio: f?.programExpenseRatio || charity.rawData.program_expense_ratio,
      fiscalYear: f?.fiscalYear || charity.rawData.fiscal_year
    };
  };

  const financials = getFinancials();

  // Get programs as string array
  const getPrograms = (): string[] => {
    const progs = charity.rawData.programs;
    if (!progs) return [];
    if (typeof progs[0] === 'string') return progs as string[];
    return (progs as any[]).map(p => p.name || p);
  };

  // Layout for hidden tier charities
  const renderLegacyLayout = () => {
    // Guard: legacy layout requires impactAssessment and confidenceAssessment
    if (!charity.impactAssessment || !charity.confidenceAssessment) {
      return (
        <div className={`p-8 rounded-2xl shadow-sm text-center ${isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-slate-200'}`}>
          <p className={isDark ? 'text-slate-400' : 'text-slate-600'}>Evaluation data not available for this charity.</p>
        </div>
      );
    }

    return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
      {/* LEFT COLUMN: IMPACT */}
      <div className="lg:col-span-7 space-y-8">

        {/* Impact Narrative */}
        <div className={`p-8 rounded-2xl shadow-sm ${isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-slate-200'}`}>
          <div className="flex items-center gap-3 mb-6">
            <div className={`p-2 rounded-lg ${isDark ? 'bg-blue-900/30 text-blue-400' : 'bg-blue-50 text-blue-600'}`}>
              <Target className="w-5 h-5" aria-hidden="true" />
            </div>
            <h2 className={`text-xl font-bold font-merriweather [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>Impact Analysis</h2>
          </div>

          <div className="prose prose-slate max-w-none">
            <p className={`leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              {charity.impactAssessment.narrative}
            </p>
          </div>

          <div className={`grid grid-cols-1 md:grid-cols-2 gap-6 mt-8 pt-8 border-t ${isDark ? 'border-slate-800' : 'border-slate-100'}`}>
            <div>
              <h4 className="text-xs font-bold text-emerald-700 uppercase tracking-wider mb-3 flex items-center gap-2">
                <CheckCircle2 className="w-3 h-3" aria-hidden="true" /> Strengths
              </h4>
              <ul className="space-y-2">
                {charity.impactAssessment.key_strengths.map((s, i) => (
                  <li key={i} className={`text-sm pl-3 border-l-2 border-emerald-100 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>{s}</li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="text-xs font-bold text-amber-700 uppercase tracking-wider mb-3 flex items-center gap-2">
                <Target className="w-3 h-3" aria-hidden="true" /> Opportunities
              </h4>
              <ul className="space-y-2">
                {charity.impactAssessment.growth_opportunities.map((s, i) => (
                  <li key={i} className={`text-sm pl-3 border-l-2 border-amber-100 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>{s}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Programs & Reach */}
        {(getPrograms().length > 0 || charity.programs?.length || charity.populationsServed?.length || charity.geographicCoverage?.length) && (
          <div className={`p-8 rounded-2xl shadow-sm ${isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-slate-200'}`}>
            <h2 className={`text-xl font-bold font-merriweather mb-6 [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>Programs & Reach</h2>

            <div className="space-y-6">
              {(getPrograms().length > 0 || (charity.programs && charity.programs.length > 0)) && (
                <div>
                  <h3 className={`text-sm font-bold mb-3 flex items-center gap-2 ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    <Target className="w-4 h-4 text-emerald-600" aria-hidden="true" />
                    Programs & Services ({(charity.programs?.length || getPrograms().length)})
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {(charity.programs && charity.programs.length > 0 ? charity.programs : getPrograms()).slice(0, 12).map((program, i) => (
                      <span key={i} className="px-3 py-1.5 bg-emerald-50 text-emerald-700 text-sm rounded-lg border border-emerald-100">
                        {typeof program === 'string' ? program : (program as any).name}
                      </span>
                    ))}
                    {(charity.programs?.length || getPrograms().length) > 12 && (
                      <span className="px-3 py-1.5 bg-slate-50 text-slate-500 text-sm rounded-lg border border-slate-100">
                        +{(charity.programs?.length || getPrograms().length) - 12} more
                      </span>
                    )}
                  </div>
                </div>
              )}

              {charity.populationsServed && charity.populationsServed.length > 0 && (
                <div>
                  <h3 className={`text-sm font-bold mb-3 flex items-center gap-2 ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    <Users className="w-4 h-4 text-blue-600" aria-hidden="true" />
                    Populations Served
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {charity.populationsServed.slice(0, 10).map((pop, i) => (
                      <span key={i} className="px-3 py-1.5 bg-blue-50 text-blue-700 text-sm rounded-lg border border-blue-100">
                        {pop}
                      </span>
                    ))}
                    {charity.populationsServed.length > 10 && (
                      <span className="px-3 py-1.5 bg-slate-50 text-slate-500 text-sm rounded-lg border border-slate-100">
                        +{charity.populationsServed.length - 10} more
                      </span>
                    )}
                  </div>
                </div>
              )}

              {charity.geographicCoverage && charity.geographicCoverage.length > 0 && (
                <div>
                  <h3 className={`text-sm font-bold mb-3 flex items-center gap-2 ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    <Globe className="w-4 h-4 text-indigo-600" aria-hidden="true" />
                    Geographic Coverage ({charity.geographicCoverage.length} locations)
                  </h3>
                  <p className="text-sm text-slate-600 leading-relaxed">
                    {charity.geographicCoverage.slice(0, 15).join(" · ")}
                    {charity.geographicCoverage.length > 15 && ` and ${charity.geographicCoverage.length - 15} more locations`}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Legacy Dimensions Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="md:col-span-2">
            <AssessmentCard
              title="Problem Importance"
              evaluation={charity.impactAssessment.dimension_ratings.problem_importance}
            />
          </div>

          <AssessmentCard
            title="Intervention Strength"
            evaluation={charity.impactAssessment.dimension_ratings.intervention_strength}
          />
          <AssessmentCard
            title="Scale of Reach"
            evaluation={charity.impactAssessment.dimension_ratings.scale_of_reach}
          />

          <AssessmentCard
            title="Cost Effectiveness"
            evaluation={charity.impactAssessment.dimension_ratings.cost_effectiveness}
            rawMetric={financials.programExpenseRatio ? `${financials.programExpenseRatio > 1 ? financials.programExpenseRatio.toFixed(0) : (financials.programExpenseRatio * 100).toFixed(0)}%` : undefined}
          />
          <AssessmentCard
            title="Long-Term Benefit"
            evaluation={charity.impactAssessment.dimension_ratings.long_term_benefit}
          />
        </div>
      </div>

      {/* RIGHT COLUMN: CONFIDENCE */}
      <div className="lg:col-span-5 space-y-6">

        {/* Confidence Narrative Card */}
        <div className={`p-8 rounded-2xl shadow-sm relative overflow-hidden ${isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-slate-200'}`}>
          <div className={`absolute top-0 right-0 w-32 h-32 rounded-bl-[100px] -mr-8 -mt-8 -z-0 ${isDark ? 'bg-slate-800' : 'bg-slate-50'}`}></div>

          <div className="relative z-10">
            <div className="flex items-center gap-3 mb-6">
              <div className={`p-2 rounded-lg ${isDark ? 'bg-indigo-900/30 text-indigo-400' : 'bg-indigo-50 text-indigo-600'}`}>
                <ShieldCheck className="w-5 h-5" aria-hidden="true" />
              </div>
              <h2 className={`text-xl font-bold font-merriweather [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>Organizational Health</h2>
            </div>

            <p className={`leading-relaxed mb-6 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              {charity.confidenceAssessment.narrative}
            </p>

            {charity.rawData.red_flags.length > 0 && (
              <div className="p-4 bg-rose-50 border border-rose-100 rounded-xl">
                <h4 className="text-xs font-bold text-rose-800 uppercase tracking-wider mb-2">Attention Needed</h4>
                <ul className="space-y-1">
                  {charity.rawData.red_flags.map((flag, i) => (
                    <li key={i} className="text-sm text-rose-700 flex items-start gap-2">
                      <span className="mt-1.5 w-1 h-1 bg-rose-500 rounded-full"></span>
                      {flag}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>

        {/* Financial Overview Card */}
        <div className={`rounded-2xl shadow-sm overflow-hidden ${isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-slate-200'}`}>
          <div className={`p-6 border-b ${isDark ? 'border-slate-800' : 'border-slate-100'}`}>
            <h3 className={`font-merriweather font-bold inline-flex items-center ${isDark ? 'text-white' : 'text-slate-900'}`}>
              Financial Overview
              {charity.sourceAttribution?.total_revenue && (
                <SourceAttribution
                  fieldName="total_revenue"
                  attribution={charity.sourceAttribution.total_revenue}
                />
              )}
            </h3>
            {financials.fiscalYear && (
              <p className="text-xs text-slate-500 mt-1">FY {financials.fiscalYear}</p>
            )}
          </div>

          <div className={`divide-y ${isDark ? 'divide-slate-800' : 'divide-slate-50'}`}>
            <div className={`p-5 transition-colors flex items-center justify-between ${isDark ? 'hover:bg-slate-800' : 'hover:bg-slate-50'}`}>
              <div>
                <div className={`text-sm font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>Total Revenue</div>
                <div className="text-xs text-slate-500">Annual revenue</div>
              </div>
              <div className="text-right">
                <div className={`text-lg font-bold tabular-nums ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  {financials.totalRevenue ? `$${(financials.totalRevenue / 1_000_000).toFixed(1)}M` : <span className="text-slate-400 text-sm font-normal">N/A</span>}
                </div>
              </div>
            </div>

            <div className={`p-5 transition-colors flex items-center justify-between ${isDark ? 'hover:bg-slate-800' : 'hover:bg-slate-50'}`}>
              <div>
                <div className={`text-sm font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>Program Expense Ratio</div>
                <div className="text-xs text-slate-500">% of expenses on programs</div>
              </div>
              <div className="text-right">
                <div className={`text-lg font-bold tabular-nums ${isDark ? 'text-emerald-400' : 'text-emerald-700'}`}>
                  {financials.programExpenseRatio ? `${financials.programExpenseRatio > 1 ? financials.programExpenseRatio.toFixed(0) : (financials.programExpenseRatio * 100).toFixed(0)}%` : <span className="text-slate-400 text-sm font-normal">N/A</span>}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Third-Party Ratings */}
        {charity.scores && (charity.scores.overall || charity.scores.financial || charity.scores.accountability) && (
          <div className={`rounded-2xl shadow-sm overflow-hidden ${isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-slate-200'}`}>
            <div className={`p-6 border-b ${isDark ? 'border-slate-800' : 'border-slate-100'}`}>
              <h3 className={`font-merriweather font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>Third-Party Ratings</h3>
              <p className="text-xs text-slate-500 mt-1">Charity Navigator Scores</p>
            </div>

            <div className={`divide-y ${isDark ? 'divide-slate-800' : 'divide-slate-50'}`}>
              {charity.scores?.overall && (
                <div className={`p-5 transition-colors flex items-center justify-between ${isDark ? 'hover:bg-slate-800' : 'hover:bg-slate-50'}`}>
                  <div>
                    <div className={`text-sm font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>Overall Score</div>
                    <div className="text-xs text-slate-500">Out of 100</div>
                  </div>
                  <div className={`text-2xl font-bold tabular-nums ${isDark ? 'text-emerald-400' : 'text-emerald-700'}`}>{charity.scores.overall}</div>
                </div>
              )}
              {charity.scores?.financial && (
                <div className={`p-5 transition-colors flex items-center justify-between ${isDark ? 'hover:bg-slate-800' : 'hover:bg-slate-50'}`}>
                  <div>
                    <div className={`text-sm font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>Financial Health</div>
                    <div className="text-xs text-slate-500">Out of 100</div>
                  </div>
                  <div className={`text-2xl font-bold tabular-nums ${isDark ? 'text-blue-400' : 'text-blue-700'}`}>{charity.scores.financial}</div>
                </div>
              )}
              {charity.scores?.accountability && (
                <div className={`p-5 transition-colors flex items-center justify-between ${isDark ? 'hover:bg-slate-800' : 'hover:bg-slate-50'}`}>
                  <div>
                    <div className={`text-sm font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>Accountability</div>
                    <div className="text-xs text-slate-500">Out of 100</div>
                  </div>
                  <div className={`text-2xl font-bold tabular-nums ${isDark ? 'text-indigo-400' : 'text-indigo-700'}`}>{charity.scores.accountability}</div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Governance Checklist */}
        <div className={`rounded-2xl shadow-sm overflow-hidden ${isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-slate-200'}`}>
          <div className={`p-6 border-b ${isDark ? 'border-slate-800' : 'border-slate-100'}`}>
            <h3 className={`font-merriweather font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>Governance Checklist</h3>
          </div>

          <div className={`divide-y ${isDark ? 'divide-slate-800' : 'divide-slate-50'}`}>
            <div className={`p-5 transition-colors flex items-center gap-4 ${isDark ? 'hover:bg-slate-800' : 'hover:bg-slate-50'}`}>
              <RatingIcon color={charity.confidenceAssessment.dimension_ratings.transparency} />
              <div className="flex-grow">
                <div className={`text-sm font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>Transparency</div>
                <div className="text-xs text-slate-500">Level: {charity.rawData.transparency_level}</div>
              </div>
            </div>

            <div className={`p-5 transition-colors flex items-center gap-4 ${isDark ? 'hover:bg-slate-800' : 'hover:bg-slate-50'}`}>
              <RatingIcon color={charity.confidenceAssessment.dimension_ratings.governance} />
              <div className="flex-grow">
                <div className={`text-sm font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>Board Independence</div>
                <div className="text-xs text-slate-500">
                  {charity.rawData.independent_board_members} of {charity.rawData.board_members_count} members independent
                </div>
              </div>
            </div>

            <div className={`p-5 transition-colors flex items-center gap-4 ${isDark ? 'hover:bg-slate-800' : 'hover:bg-slate-50'}`}>
              <RatingIcon color={charity.confidenceAssessment.dimension_ratings.financial_controls} />
              <div className="flex-grow">
                <div className={`text-sm font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>Financial Controls</div>
                <div className="text-xs text-slate-500">
                  Independent Audit: {charity.rawData.audit_performed ? "Yes" : "No"}
                </div>
              </div>
            </div>
          </div>

          <div className={`p-5 border-t ${isDark ? 'bg-slate-800/50 border-slate-800' : 'bg-slate-50 border-slate-100'}`}>
            <div className="flex items-start gap-3">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 shrink-0 ${isDark ? 'bg-slate-800 border border-slate-700' : 'bg-white border border-slate-200'}`}>
                <Globe className="w-4 h-4" aria-hidden="true" />
              </div>
              <div>
                <div className={`text-sm font-bold mb-1 ${isDark ? 'text-white' : 'text-slate-900'}`}>Zakat Policy</div>
                <p className="text-xs text-slate-500 leading-relaxed">
                  {charity.rawData.zakat_policy}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Data Confidence (if Amal data available) */}
        {charity.amalEvaluation?.data_confidence && (
          <DataConfidenceCard
            dataConfidence={charity.amalEvaluation.data_confidence}
            evaluationDate={charity.amalEvaluation.evaluation_date}
            methodologyVersion={charity.amalEvaluation.methodology_version}
          />
        )}
      </div>
    </div>
    );
  };

  // Hidden tier charities use legacy layout only


  return (
    <div className={`min-h-screen pb-24 font-sans ${isDark ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-900'}`}>
      {/* HEADER */}
      <div className={`border-b pt-8 pb-12 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <Link to="/browse" className={`inline-flex items-center text-sm text-slate-500 transition-colors mb-6 font-medium ${isDark ? 'hover:text-white' : 'hover:text-slate-900'}`}>
            <ArrowLeft className="w-4 h-4 mr-2" aria-hidden="true" />
            Back to Directory
          </Link>

          <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-8">
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-4">
                {/* T047: Hidden tier indicator */}
                {isHidden && (
                  <span className="flex items-center text-[10px] font-bold uppercase tracking-wider px-3 py-1.5 rounded-full border bg-slate-700 text-white border-slate-600">
                    <AlertTriangle className="w-3 h-3 mr-1.5" aria-hidden="true" />
                    Not Publicly Listed
                  </span>
                )}
                <span className="px-3 py-1.5 bg-slate-100 text-slate-600 text-[10px] font-bold uppercase tracking-wider rounded-full border border-slate-200">
                  {charity.category}
                </span>
                {amal?.wallet_routing && (
                  <span className={`flex items-center text-[10px] font-bold uppercase tracking-wider px-3 py-1.5 rounded-full border ${getWalletTagStyles(amal.wallet_routing.tag)}`}>
                    <Lock className="w-3 h-3 mr-1.5" aria-hidden="true" />
                    {formatWalletTag(amal.wallet_routing.tag)}
                  </span>
                )}
                <span className="flex items-center text-xs font-medium text-emerald-700 bg-emerald-50 px-3 py-1.5 rounded-full border border-emerald-100">
                  <CheckCircle2 className="w-3 h-3 mr-1.5" aria-hidden="true" />
                  Verified 501(c)(3)
                </span>
              </div>
              <h1 className={`text-3xl md:text-5xl font-bold font-merriweather mb-4 leading-tight [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>
                {charity.name}
              </h1>
              <div className="flex flex-wrap items-center gap-4 text-sm text-slate-500 font-medium">
                {(charity.rawData.geographicCoverage || charity.rawData.geographic_reach)?.length > 0 && (
                  <div className="flex items-center gap-1.5">
                    <MapPin className="w-4 h-4" aria-hidden="true" />
                    {(charity.rawData.geographicCoverage || charity.rawData.geographic_reach)?.slice(0, 3).join(", ")}
                  </div>
                )}
              </div>
            </div>

            <div className="flex items-center gap-3">
              <BookmarkButton
                charityEin={charity.ein || charity.id || ''}
                charityName={charity.name}
                size="lg"
                showLabel
                className={`px-3 py-2 rounded-lg transition-colors shadow-sm ${isDark ? 'bg-slate-800 border border-slate-700 hover:bg-slate-700' : 'bg-white border border-slate-200 hover:bg-slate-50'}`}
              />
              {charity.website && (
                <a
                  href={charity.website}
                  target="_blank"
                  rel="noreferrer"
                  className={`px-6 py-3 min-h-[44px] rounded-lg text-sm font-bold transition-colors shadow-sm flex items-center justify-center gap-2 ${isDark ? 'bg-slate-800 border border-slate-700 text-slate-300 hover:bg-slate-700' : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-50'}`}
                >
                  Visit Website
                  <ExternalLink className="w-4 h-4" aria-hidden="true" />
                </a>
              )}
              <button
                className="px-6 py-3 min-h-[44px] bg-emerald-700 text-white rounded-lg text-sm font-bold hover:bg-emerald-800 transition-colors shadow-md shadow-emerald-100 flex items-center justify-center"
              >
                Donate Now
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* CONTENT AREA */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 -mt-8 relative z-10">
        {renderLegacyLayout()}

        {/* Join Community CTA - show to non-members */}
        {!isCommunityMember && (
          <div className="mt-12">
            <JoinCommunityPrompt />
          </div>
        )}
      </div>
    </div>
  );
};

// --- SUB-COMPONENTS ---

const AnalysisBlock: React.FC<{
  label: string;
  score: number;
  maxScore?: number;
  desc?: string;
  lowLabel?: string;
  highLabel?: string;
  analysis?: string;
  ratingLabel?: string;
}> = ({ label, score, maxScore = 25, lowLabel = '', highLabel = '', analysis }) => {
  const percentage = (score / maxScore) * 100;
  const isHigh = score >= (maxScore * 0.8);
  const isMedium = score >= (maxScore * 0.5) && !isHigh;

  const barColor = isHigh ? 'bg-emerald-500' : isMedium ? 'bg-amber-400' : 'bg-rose-400';

  return (
    <div className="group">
      <div className="flex justify-between items-center mb-3">
        <div className="text-sm font-bold text-slate-900">{label}</div>
        <div className="font-mono font-bold text-slate-900 tabular-nums">{score}/{maxScore}</div>
      </div>

      {/* Scale visualization */}
      <div className="relative mb-2">
        <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full ${barColor}`}
            style={{ width: `${percentage}%` }}
          ></div>
        </div>
      </div>

      {(lowLabel || highLabel) && (
        <div className="flex justify-between text-[10px] text-slate-400 uppercase tracking-wider mb-3">
          <span>{lowLabel}</span>
          <span>{highLabel}</span>
        </div>
      )}

      {analysis && (
        <div className="text-sm text-slate-600 leading-relaxed pl-3 border-l-2 border-slate-200 mt-3">
          {analysis}
        </div>
      )}
    </div>
  );
};

interface DimensionScores {
  credibility: number;
  impact: number;
  alignment: number;
}

const ScoreCard: React.FC<{ score: number, variant: ScoreVariant, toggle: () => void, dimensions?: DimensionScores }> = ({ score, variant, toggle, dimensions }) => (
  <button
    onClick={toggle}
    className="text-left w-full bg-slate-900 rounded-2xl p-8 text-center text-white shadow-xl relative overflow-hidden cursor-pointer group transition-transform hover:scale-[1.02]"
  >
    <div className="absolute top-0 left-0 w-full h-full opacity-10 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')]"></div>
    <h3 className="text-emerald-400 text-xs font-bold uppercase tracking-[0.2em] mb-6 relative z-10">GMG Score</h3>
    <ScoreVisualizer score={score} variant={variant} dimensions={dimensions} />
    <div className="mt-4 text-slate-400 text-[10px] font-medium uppercase tracking-widest opacity-0 group-hover:opacity-100 transition-opacity">
      Click to change style
    </div>
  </button>
);

// Score Card with integrated Path to Exemplary
const ScoreCardWithPath: React.FC<{
  score: number;
  variant: ScoreVariant;
  toggle: () => void;
  dimensions?: DimensionScores;
  improvementAreas?: string[];
}> = ({ score, variant, toggle, dimensions, improvementAreas }) => (
  <div className="bg-slate-900 rounded-2xl shadow-xl relative overflow-hidden">
    <div className="absolute top-0 left-0 w-full h-full opacity-10 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')]"></div>

    {/* Score Section */}
    <button
      onClick={toggle}
      className="text-left w-full p-8 text-center text-white cursor-pointer group relative z-10"
    >
      <h3 className="text-emerald-400 text-xs font-bold uppercase tracking-[0.2em] mb-6">GMG Score</h3>
      <ScoreVisualizer score={score} variant={variant} dimensions={dimensions} />
      <div className="mt-4 text-slate-400 text-[10px] font-medium uppercase tracking-widest opacity-0 group-hover:opacity-100 transition-opacity">
        Click to change style
      </div>
    </button>

    {/* Path to Exemplary - Integrated */}
    {improvementAreas && improvementAreas.length > 0 && (
      <div className="border-t border-slate-700 p-5 relative z-10">
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp className="w-3.5 h-3.5 text-emerald-400" aria-hidden="true" />
          <h4 className="text-emerald-400 text-[10px] font-bold uppercase tracking-wider">Path to Exemplary</h4>
        </div>
        <ul className="space-y-2">
          {improvementAreas.slice(0, 3).map((step, i) => (
            <li key={i} className="flex items-start gap-2 text-xs text-slate-300">
              <ChevronRight className="w-3 h-3 text-slate-500 shrink-0 mt-0.5" aria-hidden="true" />
              <span className="leading-relaxed">{step}</span>
            </li>
          ))}
        </ul>
      </div>
    )}
  </div>
);

interface ImpactMatrixProps {
  tier1: { subtotal: number; systemic_leverage: { score: number }; ummah_gap: { score: number } };
  tier2: { subtotal: number; absorptive_capacity: { score: number }; evidence_of_impact: { score: number } };
}

const ImpactMatrix: React.FC<ImpactMatrixProps> = ({ tier1, tier2 }) => (
  <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
    <h3 className="font-bold text-slate-900 font-merriweather mb-6 text-center [text-wrap:balance]">Impact Matrix</h3>
    <div className="aspect-square relative bg-slate-50 border border-slate-200 rounded-lg p-4">
      <div className="absolute top-2 left-2 text-[8px] font-bold text-slate-400 uppercase leading-tight">High Risk<br/>(R&D)</div>
      <div className="absolute top-2 right-2 text-[8px] font-bold text-emerald-600 uppercase leading-tight text-right">Amal<br/>Catalyst</div>
      <div className="absolute bottom-2 left-2 text-[8px] font-bold text-rose-400 uppercase leading-tight">Avoid</div>
      <div className="absolute bottom-2 right-2 text-[8px] font-bold text-blue-400 uppercase leading-tight text-right">Standard<br/>Relief</div>
      <div className="absolute top-1/2 left-0 w-full h-px bg-slate-300 border-t border-dashed"></div>
      <div className="absolute left-1/2 top-0 h-full w-px bg-slate-300 border-l border-dashed"></div>
      <div
        className="absolute w-4 h-4 bg-slate-900 border-2 border-white rounded-full shadow-lg transform -translate-x-1/2 -translate-y-1/2 transition-all duration-1000 z-10"
        style={{
          left: `${(tier2.subtotal / 50) * 100}%`,
          bottom: `${(tier1.subtotal / 50) * 100}%`
        }}
      ></div>
      <div className="absolute -bottom-6 w-full text-center text-[10px] font-bold text-slate-500 uppercase tracking-wider">Execution</div>
      <div className="absolute -left-6 bottom-0 h-full flex items-center">
        <div className="transform -rotate-90 text-[10px] font-bold text-slate-500 uppercase tracking-wider whitespace-nowrap">Strategic Fit</div>
      </div>
    </div>
  </div>
);

interface WalletRoutingProps {
  wallet: {
    tag: string;
    rationale: string;
    advisory: string;
    disclaimer: string;
    matching_categories?: string[];
  };
  getStyles: (tag: string) => string;
}

const WalletRoutingCard: React.FC<WalletRoutingProps> = ({ wallet, getStyles }) => (
  <div className={`p-6 rounded-2xl border ${wallet.tag.includes('ZAKAT') ? 'bg-gradient-to-br from-emerald-50 to-white border-emerald-200' : 'bg-gradient-to-br from-indigo-50 to-white border-indigo-200'} shadow-sm relative overflow-hidden`}>
    <div className="absolute -right-4 -bottom-4 opacity-5 transform -rotate-12 pointer-events-none"><ShieldCheck className="w-32 h-32" aria-hidden="true" /></div>
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-white text-slate-600 rounded-lg border border-slate-200 shadow-sm"><Lock className="w-4 h-4" aria-hidden="true" /></div>
        <h3 className="font-bold text-slate-900 text-sm">Zakat Eligibility</h3>
      </div>
      <div className={`px-3 py-1.5 rounded-lg font-bold text-xs uppercase tracking-wider border ${getStyles(wallet.tag)}`}>{formatWalletTag(wallet.tag)}</div>
    </div>
    <p className="text-sm text-slate-700 leading-relaxed">{wallet.rationale}</p>
    {wallet.advisory && (
      <div className="mt-4 pt-4 border-t border-slate-200">
        <p className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Donor Advisory</p>
        <p className="text-sm text-slate-600 leading-relaxed">{wallet.advisory}</p>
      </div>
    )}
    {wallet.disclaimer && (
      <p className="mt-4 text-xs text-slate-400 italic">{wallet.disclaimer}</p>
    )}
  </div>
);

interface ProfileContentProps {
  charity: CharityProfile;
  formatCurrency: (n?: number) => string;
  financials: {
    totalRevenue?: number;
    programExpenses?: number;
    adminExpenses?: number;
    fundraisingExpenses?: number;
    programExpenseRatio?: number;
    fiscalYear?: number;
  };
  programs: string[];
}

const ProfileContent: React.FC<ProfileContentProps> = ({ charity, formatCurrency, financials, programs }) => (
  <>
    <div className="flex items-center gap-3 mb-6">
      <Briefcase className="w-5 h-5 text-slate-400" aria-hidden="true" />
      <h2 className="text-xl font-bold font-merriweather text-slate-900 [text-wrap:balance]">Organization Profile</h2>
    </div>

    {/* Mission Statement */}
    <div className="mb-8">
      <h4 className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-2">Mission Statement</h4>
      <p className="text-slate-800 leading-relaxed font-serif">{charity.rawData.mission}</p>
    </div>

    {/* Programs */}
    {programs.length > 0 && (
      <div className="mb-8">
        <h4 className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-4 flex items-center gap-2">
          <Target className="w-3 h-3" aria-hidden="true" />
          Programs & Services ({programs.length})
        </h4>
        <div className="flex flex-wrap gap-2">
          {programs.slice(0, 12).map((prog, i) => (
            <span key={i} className="px-3 py-1.5 bg-emerald-50 text-emerald-700 text-sm rounded-lg border border-emerald-100">
              {prog}
            </span>
          ))}
          {programs.length > 12 && (
            <span className="px-3 py-1.5 bg-slate-50 text-slate-500 text-sm rounded-lg border border-slate-100">
              +{programs.length - 12} more
            </span>
          )}
        </div>
      </div>
    )}

    {/* Populations Served */}
    {charity.populationsServed && charity.populationsServed.length > 0 && (
      <div className="mb-8">
        <h4 className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-4 flex items-center gap-2">
          <Users className="w-3 h-3" aria-hidden="true" />
          Populations Served
        </h4>
        <div className="flex flex-wrap gap-2">
          {charity.populationsServed.slice(0, 10).map((pop, i) => (
            <span key={i} className="px-3 py-1.5 bg-blue-50 text-blue-700 text-sm rounded-lg border border-blue-100">
              {pop}
            </span>
          ))}
          {charity.populationsServed.length > 10 && (
            <span className="px-3 py-1.5 bg-slate-50 text-slate-500 text-sm rounded-lg border border-slate-100">
              +{charity.populationsServed.length - 10} more
            </span>
          )}
        </div>
      </div>
    )}

    {/* Geographic Coverage */}
    {charity.geographicCoverage && charity.geographicCoverage.length > 0 && (
      <div className="mb-8">
        <h4 className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-4 flex items-center gap-2">
          <Globe className="w-3 h-3" aria-hidden="true" />
          Geographic Coverage ({charity.geographicCoverage.length} locations)
        </h4>
        <p className="text-sm text-slate-600 leading-relaxed">
          {charity.geographicCoverage.slice(0, 15).join(" · ")}
          {charity.geographicCoverage.length > 15 && ` and ${charity.geographicCoverage.length - 15} more locations`}
        </p>
      </div>
    )}

    {/* Financial Overview */}
    <div className="mb-8">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-xs font-bold uppercase tracking-widest text-slate-500">Financial Overview {financials.fiscalYear && `(${financials.fiscalYear})`}</h4>
        {financials.programExpenseRatio && (
          <span className={`text-xs font-bold px-2 py-0.5 rounded ${(financials.programExpenseRatio > 1 ? financials.programExpenseRatio : financials.programExpenseRatio * 100) >= 75 ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
            {financials.programExpenseRatio > 1 ? financials.programExpenseRatio.toFixed(0) : (financials.programExpenseRatio * 100).toFixed(0)}% Program Ratio
          </span>
        )}
      </div>
      <div className="bg-slate-50 rounded-xl p-6 border border-slate-100">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-center md:text-left">
          <div>
            <div className="text-[10px] text-slate-400 uppercase font-bold mb-1">Total Revenue</div>
            <div className="text-lg font-bold text-slate-900">{formatCurrency(financials.totalRevenue)}</div>
          </div>
          <div className="md:border-l border-slate-200 md:pl-6">
            <div className="text-[10px] text-emerald-600 uppercase font-bold mb-1">Program Expenses</div>
            <div className="text-lg font-bold text-slate-900">{formatCurrency(financials.programExpenses)}</div>
          </div>
          <div className="md:border-l border-slate-200 md:pl-6">
            <div className="text-[10px] text-slate-400 uppercase font-bold mb-1">Admin</div>
            <div className="text-lg font-bold text-slate-900">{formatCurrency(financials.adminExpenses)}</div>
          </div>
          <div className="md:border-l border-slate-200 md:pl-6">
            <div className="text-[10px] text-slate-400 uppercase font-bold mb-1">Fundraising</div>
            <div className="text-lg font-bold text-slate-900">{formatCurrency(financials.fundraisingExpenses)}</div>
          </div>
        </div>
      </div>
    </div>

    {/* Organization Details Footer */}
    <div className="flex flex-wrap items-center gap-6 text-xs text-slate-400 font-mono border-t border-slate-100 pt-6">
      <div>EIN: {charity.ein || charity.id}</div>
      <div>IRS Status: 501(c)(3) Recognized</div>
      <div>Audit: {charity.rawData.audit_performed ? 'Independent (Clean)' : 'Not Performed'}</div>
    </div>
  </>
);

// Data Confidence Component
interface DataConfidenceProps {
  dataConfidence?: {
    level: string;
    gaps?: string[];
    data_gaps?: string[];
    sources_used?: string[];
  };
  evaluationDate?: string;
  methodologyVersion?: string;
}

const DataConfidenceCard: React.FC<DataConfidenceProps> = ({ dataConfidence, evaluationDate, methodologyVersion }) => {
  if (!dataConfidence) return null;

  const getLevelStyles = (level: string) => {
    switch (level.toUpperCase()) {
      case 'HIGH': return 'bg-emerald-100 text-emerald-800 border-emerald-200';
      case 'MEDIUM': return 'bg-amber-100 text-amber-800 border-amber-200';
      case 'LOW': return 'bg-rose-100 text-rose-800 border-rose-200';
      default: return 'bg-slate-100 text-slate-800 border-slate-200';
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Database className="w-4 h-4 text-slate-400" aria-hidden="true" />
          <h3 className="font-bold text-slate-900">Data Confidence</h3>
        </div>
        <span className={`px-3 py-1 text-xs font-bold uppercase tracking-wider rounded-full border ${getLevelStyles(dataConfidence.level)}`}>
          {dataConfidence.level}
        </span>
      </div>

      <div className="p-6 space-y-6">
        {/* Sources Used */}
        {dataConfidence.sources_used && dataConfidence.sources_used.length > 0 && (
          <div>
            <h4 className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-3 flex items-center gap-2">
              <CheckCircle2 className="w-3 h-3 text-emerald-600" aria-hidden="true" />
              Sources Used
            </h4>
            <div className="flex flex-wrap gap-2">
              {dataConfidence.sources_used.map((source, i) => (
                <span key={i} className="px-2.5 py-1 bg-slate-50 text-slate-600 text-xs rounded border border-slate-100">
                  {source}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Data Gaps */}
        {((dataConfidence.gaps && dataConfidence.gaps.length > 0) || (dataConfidence.data_gaps && dataConfidence.data_gaps.length > 0)) && (
          <div>
            <h4 className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-3 flex items-center gap-2">
              <Info className="w-3 h-3 text-amber-600" aria-hidden="true" />
              Known Data Gaps
            </h4>
            <ul className="space-y-2">
              {(dataConfidence.data_gaps || dataConfidence.gaps || []).map((gap, i) => (
                <li key={i} className="text-sm text-slate-600 pl-3 border-l-2 border-amber-200">
                  {gap}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Metadata */}
        <div className="pt-4 border-t border-slate-100 flex flex-wrap gap-4 text-xs text-slate-400">
          {evaluationDate && (
            <div>Last evaluated: {new Date(evaluationDate).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}</div>
          )}
          {methodologyVersion && (
            <div>Methodology: {methodologyVersion}</div>
          )}
        </div>
      </div>
    </div>
  );
};
