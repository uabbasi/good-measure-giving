/**
 * NicheView: School-profile inspired layout for charity details.
 * Inspired by Niche.com with: top tabs, sticky sidebar nav, report card grade grid.
 * Comprehensive data display - no information loss from EditorialView.
 */

import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { getCharityAddress } from '../../utils/formatters';
import {
  ArrowLeft,
  ExternalLink,
  Heart,
  Globe,
  MapPin,
  CheckCircle2,
  TrendingUp,
  Lock,
  DollarSign,
  Users,
  Scale,
  Target,
  AlertCircle,
  AlertTriangle,
  Shield,
  Award,
  BookOpen,
  BarChart3,
  FileText,
  Building2,
  Landmark,
  ChevronRight,
  Briefcase,
  Info,
} from 'lucide-react';
import { CharityProfile } from '../../../types';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import { useAuth } from '../../auth/useAuth';
import { SignInButton } from '../../auth/SignInButton';
import { trackCharityView, trackOutboundClick, trackDonateClick, trackSimilarOrgClick } from '../../utils/analytics';
import { ShareButton } from '../ShareButton';
import { ReportIssueButton } from '../ReportIssueButton';
import { InlineViewToggle } from '../CharityViewPicker';
import { SourceLinkedText } from '../SourceLinkedText';
import { ActionsBar } from '../ActionsBar';
import { SCORE_THRESHOLD_UNDER_REVIEW } from '../../utils/scoreConstants';
import { AddDonationModal } from '../giving/AddDonationModal';
import { useCharities } from '../../hooks/useCharities';
import { useGivingHistory } from '../../hooks/useGivingHistory';


interface NicheViewProps {
  charity: CharityProfile;
  currentView?: import('../CharityViewPicker').ViewType;
  onViewChange?: (view: import('../CharityViewPicker').ViewType) => void;
}

// Convert numeric score to letter grade
const scoreToGrade = (score: number, max: number = 100): { grade: string; modifier: string } => {
  const pct = (score / max) * 100;
  if (pct >= 97) return { grade: 'A', modifier: '+' };
  if (pct >= 93) return { grade: 'A', modifier: '' };
  if (pct >= 90) return { grade: 'A', modifier: '-' };
  if (pct >= 87) return { grade: 'B', modifier: '+' };
  if (pct >= 83) return { grade: 'B', modifier: '' };
  if (pct >= 80) return { grade: 'B', modifier: '-' };
  if (pct >= 77) return { grade: 'C', modifier: '+' };
  if (pct >= 73) return { grade: 'C', modifier: '' };
  if (pct >= 70) return { grade: 'C', modifier: '-' };
  if (pct >= 67) return { grade: 'D', modifier: '+' };
  if (pct >= 63) return { grade: 'D', modifier: '' };
  if (pct >= 60) return { grade: 'D', modifier: '-' };
  return { grade: 'F', modifier: '' };
};

// Get grade color classes
const getGradeColors = (grade: string, isDark: boolean) => {
  switch (grade) {
    case 'A':
      return {
        bg: isDark ? 'bg-emerald-600' : 'bg-emerald-500',
        text: 'text-white',
        light: isDark ? 'bg-emerald-900/30' : 'bg-emerald-50',
        bar: isDark ? 'bg-emerald-500' : 'bg-emerald-500',
      };
    case 'B':
      return {
        bg: isDark ? 'bg-blue-600' : 'bg-blue-500',
        text: 'text-white',
        light: isDark ? 'bg-blue-900/30' : 'bg-blue-50',
        bar: isDark ? 'bg-blue-500' : 'bg-blue-500',
      };
    case 'C':
      return {
        bg: isDark ? 'bg-amber-600' : 'bg-amber-500',
        text: 'text-white',
        light: isDark ? 'bg-amber-900/30' : 'bg-amber-50',
        bar: isDark ? 'bg-amber-500' : 'bg-amber-500',
      };
    case 'D':
      return {
        bg: isDark ? 'bg-orange-600' : 'bg-orange-500',
        text: 'text-white',
        light: isDark ? 'bg-orange-900/30' : 'bg-orange-50',
        bar: isDark ? 'bg-orange-500' : 'bg-orange-500',
      };
    default:
      return {
        bg: isDark ? 'bg-red-600' : 'bg-red-500',
        text: 'text-white',
        light: isDark ? 'bg-red-900/30' : 'bg-red-50',
        bar: isDark ? 'bg-red-500' : 'bg-red-500',
      };
  }
};

// Format currency helper
const formatCurrency = (value: number | null | undefined): string => {
  if (!value) return 'N/A';
  if (value >= 1000000) return `$${(value / 1000000).toFixed(1)}M`;
  if (value >= 1000) return `$${(value / 1000).toFixed(0)}K`;
  return `$${value}`;
};

// Format wallet tag
const formatWalletTag = (tag: string): string => {
  const cleanTag = tag?.replace(/[\[\]]/g, '') || '';
  if (cleanTag.includes('ZAKAT')) return 'Zakat Eligible';
  return 'Sadaqah';
};

// Format primaryCategory for display
const formatPrimaryCategory = (category: string | null | undefined): string | null => {
  if (!category) return null;
  const mapping: Record<string, string> = {
    'HUMANITARIAN': 'Humanitarian',
    'RELIGIOUS_CONGREGATION': 'Religious',
    'CIVIL_RIGHTS_LEGAL': 'Civil Rights',
    'MEDICAL_HEALTH': 'Health',
    'EDUCATION_K12_RELIGIOUS': 'Education',
    'EDUCATION_HIGHER_RELIGIOUS': 'Education',
    'ENVIRONMENT_CLIMATE': 'Environment',
    'BASIC_NEEDS': 'Basic Needs',
    'PHILANTHROPY_GRANTMAKING': 'Grantmaking',
    'SOCIAL_SERVICES': 'Social Services',
    'EDUCATION_INTERNATIONAL': 'Education',
    'RELIGIOUS_OUTREACH': 'Religious',
    'RESEARCH_POLICY': 'Research',
    'WOMENS_SERVICES': "Women's Services",
    'ADVOCACY_CIVIC': 'Civic',
    'MEDIA_JOURNALISM': 'Media',
  };
  return mapping[category] || category.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
};

// Top-level tabs (consolidated to 3)
type TabId = 'overview' | 'impact' | 'organization';
const TABS: { id: TabId; label: string; icon: React.ElementType }[] = [
  { id: 'overview', label: 'Overview', icon: FileText },
  { id: 'impact', label: 'Impact & Giving', icon: Target },
  { id: 'organization', label: 'Organization', icon: Building2 },
];

// Dimension config (2-dimension framework)
const DIMENSION_CONFIG = {
  impact: { label: 'Impact', icon: TrendingUp, description: 'Effectiveness & efficiency', max: 50 },
  alignment: { label: 'Alignment', icon: Target, description: 'Mission & donor fit', max: 50 },
} as const;

// Name aliases for charity matching
const NAME_ALIASES: Record<string, string> = {
  'islamic relief': 'islamic relief usa',
  'islamic relief worldwide': 'islamic relief usa',
  'mercy-usa': 'mercy-usa for aid and development',
  'helping hand': 'helping hand for relief and development',
  'hhrd': 'helping hand for relief and development',
};

export const NicheView: React.FC<NicheViewProps> = ({ charity, currentView, onViewChange }) => {
  const { isDark } = useLandingTheme();
  const { isSignedIn } = useAuth();
  const { charities: allCharities } = useCharities();
  const { addDonation, getPaymentSources } = useGivingHistory();
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [showDonationModal, setShowDonationModal] = useState(false);

  const amal = charity.amalEvaluation;
  const baseline = amal?.baseline_narrative;
  const rich = amal?.rich_narrative;
  const hasRich = !!rich;
  const scores = amal?.confidence_scores;
  const scoreDetails = amal?.score_details;
  const financials = charity.financials || charity.rawData?.financials;
  const revenue = financials?.totalRevenue || charity.rawData?.total_revenue;
  const citations = rich?.all_citations || baseline?.all_citations || [];

  // Build charity lookup for similar orgs
  const charityNameToCharity = useMemo(() => {
    const map = new Map<string, CharityProfile>();
    allCharities.forEach(c => map.set(c.name.toLowerCase().trim(), c));
    return map;
  }, [allCharities]);

  const findCharity = (name: string): CharityProfile | null => {
    const lowerName = name.toLowerCase().trim();
    if (charityNameToCharity.has(lowerName)) return charityNameToCharity.get(lowerName) || null;
    const aliasedName = NAME_ALIASES[lowerName];
    if (aliasedName && charityNameToCharity.has(aliasedName)) return charityNameToCharity.get(aliasedName) || null;
    for (const [charityName, c] of charityNameToCharity.entries()) {
      if (charityName.includes(lowerName) || lowerName.includes(charityName)) return c;
    }
    return null;
  };

  useEffect(() => {
    trackCharityView(charity.id ?? charity.ein ?? '', charity.name, 'niche');
  }, [charity.id, charity.ein, charity.name]);

  // Get dimension scores
  const getDimensionScore = (dim: keyof typeof DIMENSION_CONFIG): number => {
    if (scores) {
      const score = scores[dim as keyof typeof scores];
      if (typeof score === 'number') return score;
    }
    if (scoreDetails) {
      const details = scoreDetails[dim as keyof typeof scoreDetails];
      if (details && typeof details === 'object' && 'score' in details) {
        return (details as { score: number }).score;
      }
    }
    if (amal) {
      const amalDim = amal[dim as keyof typeof amal];
      if (amalDim && typeof amalDim === 'object' && 'score' in amalDim) {
        return (amalDim as { score: number }).score;
      }
    }
    return 0;
  };

  // Calculate expense ratios
  const totalExpenses = financials?.totalExpenses ?? 0;
  const hasExpenseData = totalExpenses > 0;
  const programRatio = hasExpenseData && financials?.programExpenses ? ((financials.programExpenses / totalExpenses) * 100) : 0;
  const adminRatio = hasExpenseData && financials?.adminExpenses ? ((financials.adminExpenses / totalExpenses) * 100) : 0;
  const fundRatio = hasExpenseData && financials?.fundraisingExpenses ? ((financials.fundraisingExpenses / totalExpenses) * 100) : 0;

  // Overall grade
  const overallScore = amal?.amal_score ?? 0;
  const overallGrade = scoreToGrade(overallScore);
  const overallColors = getGradeColors(overallGrade.grade, isDark);


  // Card wrapper component
  const Card: React.FC<{ children: React.ReactNode; className?: string; id?: string }> = ({ children, className = '', id }) => (
    <div id={id} className={`rounded-xl p-5 ${isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-gray-200'} ${className}`}>
      {children}
    </div>
  );

  // Section header component
  const SectionHeader: React.FC<{ title: string; icon?: React.ElementType }> = ({ title, icon: Icon }) => (
    <div className="flex items-center gap-3 mb-4">
      {Icon && <Icon className={`w-5 h-5 ${isDark ? 'text-slate-400' : 'text-gray-400'}`} aria-hidden="true" />}
      <h2 className={`text-lg font-bold [text-wrap:balance] ${isDark ? 'text-white' : 'text-gray-900'}`}>{title}</h2>
      <div className={`flex-1 h-px ${isDark ? 'bg-slate-700' : 'bg-gray-200'}`} />
    </div>
  );

  // Grade badge component — hides grades below B (shows "NR" = Not Rated)
  const GradeBadge: React.FC<{ score: number; max?: number; size?: 'sm' | 'md' | 'lg' }> = ({ score, max = 100, size = 'md' }) => {
    const grade = scoreToGrade(score, max);
    const isBelowB = grade.grade === 'C' || grade.grade === 'D' || grade.grade === 'F';
    const colors = isBelowB
      ? { bg: isDark ? 'bg-slate-700' : 'bg-slate-200', text: isDark ? 'text-slate-400' : 'text-slate-500', light: '', bar: '' }
      : getGradeColors(grade.grade, isDark);
    const sizeClasses = size === 'lg' ? 'w-20 h-20 text-3xl' : size === 'md' ? 'w-14 h-14 text-xl' : 'w-10 h-10 text-sm';
    return (
      <div className={`${sizeClasses} rounded-xl ${colors.bg} flex items-center justify-center font-bold ${colors.text}`}>
        {isBelowB ? (
          <span className={size === 'lg' ? 'text-base' : 'text-xs'}>NR</span>
        ) : (
          <>{grade.grade}<span className="text-xs">{grade.modifier}</span></>
        )}
      </div>
    );
  };

  return (
    <div className={`min-h-screen ${isDark ? 'bg-slate-950' : 'bg-gray-50'}`}>
      {/* Hero Section */}
      <div className={`${isDark ? 'bg-slate-900 border-b border-slate-800' : 'bg-white border-b border-gray-200'}`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          {/* Back Link */}
          <Link to="/browse" className={`inline-flex items-center gap-2 mb-3 text-sm ${isDark ? 'text-slate-400 hover:text-white' : 'text-gray-600 hover:text-gray-900'}`}>
            <ArrowLeft className="w-4 h-4" aria-hidden="true" /> Back to Directory
          </Link>

          <div className="flex flex-col lg:flex-row lg:items-center gap-4">
            {/* Overall Grade */}
            <GradeBadge score={overallScore} size="lg" />

            {/* Name and Meta */}
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <span className={`px-2 py-0.5 rounded-full text-xs ${isDark ? 'bg-slate-800 text-slate-300' : 'bg-gray-100 text-gray-600'}`}>
                  {formatPrimaryCategory((charity as any).primaryCategory) || charity.category}
                </span>
                {!!(charity as any).trustSignals?.isConflictZone && (
                  <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${isDark ? 'bg-orange-900/50 text-orange-400' : 'bg-orange-100 text-orange-700'}`}>
                    Conflict Zone
                  </span>
                )}
                {charity.categoryMetadata?.neglectedness === 'HIGH' && (
                  <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${isDark ? 'bg-violet-900/50 text-violet-400' : 'bg-violet-100 text-violet-700'}`}>
                    Neglected Cause
                  </span>
                )}
                {charity.archetype && (
                  <span className={`px-2 py-0.5 rounded-full text-xs ${isDark ? 'bg-slate-800 text-slate-400' : 'bg-gray-100 text-gray-500'}`}>
                    {({
                      'RESILIENCE': 'Community Resilience',
                      'LEVERAGE': 'Strategic Leverage',
                      'SOVEREIGNTY': 'Sovereignty Builder',
                      'ASSET_CREATION': 'Asset Creator',
                      'DIRECT_SERVICE': 'Direct Service',
                    } as Record<string, string>)[charity.archetype] || charity.archetype}
                  </span>
                )}
              </div>
              <h1 className={`text-xl lg:text-2xl font-bold [text-wrap:balance] ${isDark ? 'text-white' : 'text-gray-900'}`}>{charity.name}</h1>
              {getCharityAddress(charity) && (
                <p className={`flex items-center gap-1 text-sm mt-1 ${isDark ? 'text-slate-400' : 'text-gray-500'}`}>
                  <MapPin className="w-3 h-3" aria-hidden="true" />
                  {getCharityAddress(charity)}
                </p>
              )}
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-2">
              {(charity.donationUrl || charity.website) && (
                <a
                  href={charity.donationUrl ?? charity.website ?? undefined}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={() => trackDonateClick(charity.id ?? charity.ein ?? '', charity.name, charity.donationUrl || charity.website || '')}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-emerald-600 text-white hover:bg-emerald-700"
                >
                  <Heart className="w-4 h-4" aria-hidden="true" /> Donate
                </a>
              )}
            </div>
          </div>

          {/* Top Tabs */}
          <div className="flex gap-1 mt-4 overflow-x-auto pb-1">
            {TABS.map(tab => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-t-lg text-sm font-medium whitespace-nowrap transition-colors ${
                    isActive
                      ? isDark ? 'bg-slate-950 text-white border-t border-x border-slate-700' : 'bg-gray-50 text-gray-900 border-t border-x border-gray-200'
                      : isDark ? 'text-slate-400 hover:text-white hover:bg-slate-800' : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100'
                  }`}
                >
                  <Icon className="w-4 h-4" aria-hidden="true" /> {tab.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Actions Bar */}
      <ActionsBar
        charityEin={charity.ein!}
        charityName={charity.name}
        onLogDonation={() => setShowDonationModal(true)}
        walletTag={amal?.wallet_tag}
        causeArea={rich?.donor_fit_matrix?.cause_area}
      />

      {/* Main Content */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="space-y-6">
            {/* OVERVIEW TAB */}
            {activeTab === 'overview' && (
              <>
                {/* Report Card - Grade Grid */}
                    <Card id="report-card">
                      <SectionHeader title="Report Card" icon={Award} />
                      <div className="flex flex-col lg:flex-row lg:items-center gap-6">
                        {/* Overall Grade */}
                        <div className="text-center">
                          <GradeBadge score={overallScore} size="lg" />
                          <p className={`text-sm mt-2 font-medium ${isDark ? 'text-slate-300' : 'text-gray-700'}`}>Overall Grade</p>
                          {overallScore >= SCORE_THRESHOLD_UNDER_REVIEW ? (
                            <>
                              <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>{overallScore}/100</p>
                              {charity.scoreSummary && (
                                <p className={`mt-2 text-xs leading-relaxed max-w-[200px] ${isDark ? 'text-slate-400' : 'text-gray-500'}`}>
                                  {charity.scoreSummary}
                                </p>
                              )}
                            </>
                          ) : (
                            <>
                              <div className={`mt-1 inline-flex px-2 py-0.5 rounded text-xs font-semibold ${isDark ? 'bg-amber-900/30 text-amber-400' : 'bg-amber-50 text-amber-700'}`}>
                                Preliminary
                              </div>
                              <p className={`mt-2 text-xs leading-relaxed max-w-[200px] ${isDark ? 'text-slate-400' : 'text-gray-500'}`}>
                                {charity.evaluationTrack === 'NEW_ORG'
                                  ? 'Preliminary evaluation under emerging-org rubric.'
                                  : 'Preliminary score — methodology being calibrated for this profile.'}
                              </p>
                            </>
                          )}
                        </div>
                        {/* Dimension Grades Grid */}
                        <div className="flex-1 grid grid-cols-2 gap-4">
                          {(Object.keys(DIMENSION_CONFIG) as Array<keyof typeof DIMENSION_CONFIG>).map(dim => {
                            const config = DIMENSION_CONFIG[dim];
                            const score = getDimensionScore(dim);
                            const grade = scoreToGrade(score, config.max);
                            const isBelowB = grade.grade === 'C' || grade.grade === 'D' || grade.grade === 'F';
                            const colors = isBelowB
                              ? { bg: isDark ? 'bg-slate-700' : 'bg-slate-200', text: isDark ? 'text-slate-400' : 'text-slate-500' }
                              : getGradeColors(grade.grade, isDark);
                            return (
                              <div key={dim} className="flex items-center gap-3">
                                <div className={`w-12 h-12 rounded-lg ${colors.bg} flex items-center justify-center font-bold ${colors.text}`}>
                                  {isBelowB ? <span className="text-xs">NR</span> : <>{grade.grade}{grade.modifier}</>}
                                </div>
                                <div>
                                  <p className={`text-sm font-medium ${isDark ? 'text-white' : 'text-gray-900'}`}>{config.label}</p>
                                  <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>
                                    {isBelowB ? 'Developing' : config.description}
                                  </p>
                                  {dim === 'impact' && amal?.score_details?.data_confidence?.badge === 'LOW' && (
                                    <div className={`mt-0.5 flex items-center gap-1 text-xs ${isDark ? 'text-amber-400' : 'text-amber-600'}`}>
                                      <AlertTriangle className="w-3 h-3" />
                                      <span>Limited data confidence</span>
                                    </div>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    </Card>

                    {/* About Section */}
                    <Card id="about">
                      <SectionHeader title="About" icon={Info} />
                      {(baseline?.headline || rich?.headline) && (
                        <p className={`text-lg font-medium mb-4 ${isDark ? 'text-white' : 'text-gray-800'}`}>
                          {baseline?.headline || rich?.headline}
                        </p>
                      )}
                      {(rich?.summary || baseline?.summary) && (
                        <div className={`prose max-w-none ${isDark ? 'prose-invert' : ''}`}>
                          <SourceLinkedText text={rich?.summary || baseline?.summary || ''} citations={citations} isDark={isDark} />
                        </div>
                      )}
                    </Card>

                    {/* Quick Facts */}
                    <Card id="quick-facts">
                      <SectionHeader title="Quick Facts" icon={FileText} />
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {charity.beneficiariesServedAnnually != null && charity.beneficiariesServedAnnually > 0 && (
                          <div className="flex items-start gap-3">
                            <Heart className={`w-5 h-5 mt-0.5 ${isDark ? 'text-slate-500' : 'text-gray-400'}`} aria-hidden="true" />
                            <div>
                              <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Beneficiaries Served Annually <span className="italic">(self-reported)</span></p>
                              <p className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>{charity.beneficiariesServedAnnually.toLocaleString()}</p>
                            </div>
                          </div>
                        )}
                        {charity.populationsServed && charity.populationsServed.length > 0 && (
                          <div className="flex items-start gap-3">
                            <Users className={`w-5 h-5 mt-0.5 ${isDark ? 'text-slate-500' : 'text-gray-400'}`} aria-hidden="true" />
                            <div>
                              <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Populations Served</p>
                              <p className={`text-sm ${isDark ? 'text-white' : 'text-gray-900'}`}>{charity.populationsServed.slice(0, 5).join(', ')}</p>
                            </div>
                          </div>
                        )}
                        {charity.programs && charity.programs.length > 0 && (
                          <div className="flex items-start gap-3">
                            <Briefcase className={`w-5 h-5 mt-0.5 ${isDark ? 'text-slate-500' : 'text-gray-400'}`} aria-hidden="true" />
                            <div>
                              <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Programs</p>
                              <p className={`text-sm ${isDark ? 'text-white' : 'text-gray-900'}`}>{charity.programs.slice(0, 4).join(', ')}</p>
                            </div>
                          </div>
                        )}
                        {(charity.geographicCoverage?.length || rich?.donor_fit_matrix?.geographic_focus?.length) && (
                          <div className="flex items-start gap-3">
                            <Globe className={`w-5 h-5 mt-0.5 ${isDark ? 'text-slate-500' : 'text-gray-400'}`} aria-hidden="true" />
                            <div>
                              <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Geographic Coverage</p>
                              <p className={`text-sm ${isDark ? 'text-white' : 'text-gray-900'}`}>
                                {(charity.geographicCoverage || rich?.donor_fit_matrix?.geographic_focus || []).slice(0, 5).join(', ')}
                              </p>
                            </div>
                          </div>
                        )}
                        {charity.foundedYear && (
                          <div className="flex items-start gap-3">
                            <Building2 className={`w-5 h-5 mt-0.5 ${isDark ? 'text-slate-500' : 'text-gray-400'}`} aria-hidden="true" />
                            <div>
                              <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Founded</p>
                              <p className={`text-sm ${isDark ? 'text-white' : 'text-gray-900'}`}>{charity.foundedYear}</p>
                            </div>
                          </div>
                        )}
                        {revenue && (
                          <div className="flex items-start gap-3">
                            <DollarSign className={`w-5 h-5 mt-0.5 ${isDark ? 'text-slate-500' : 'text-gray-400'}`} aria-hidden="true" />
                            <div>
                              <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Annual Revenue</p>
                              <p className={`text-sm ${isDark ? 'text-white' : 'text-gray-900'}`}>{formatCurrency(revenue)}</p>
                            </div>
                          </div>
                        )}
                        {charity.ein && (
                          <div className="flex items-start gap-3">
                            <FileText className={`w-5 h-5 mt-0.5 ${isDark ? 'text-slate-500' : 'text-gray-400'}`} aria-hidden="true" />
                            <div>
                              <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>EIN</p>
                              <p className={`text-sm font-mono ${isDark ? 'text-white' : 'text-gray-900'}`}>{charity.ein}</p>
                            </div>
                          </div>
                        )}
                      </div>
                    </Card>

                    {/* Similar Organizations */}
                    {rich?.similar_organizations && rich.similar_organizations.length > 0 && (
                      <Card id="similar-orgs">
                        <SectionHeader title="Similar Organizations" icon={Building2} />
                        {rich?.peer_comparison && (
                          <p className={`text-sm mb-4 ${isDark ? 'text-slate-400' : 'text-gray-600'}`}>
                            <SourceLinkedText text={rich.peer_comparison.differentiator} citations={citations} isDark={isDark} />
                          </p>
                        )}
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                          {rich.similar_organizations.map((org, i) => {
                            const orgName = typeof org === 'string' ? org : org.name;
                            const linkedCharity = findCharity(orgName);
                            const linkedId = linkedCharity?.id ?? linkedCharity?.ein ?? null;
                            const gmScore = linkedCharity?.amalEvaluation?.amal_score;
                            return (
                              <div key={i} className={`p-3 rounded-lg ${isDark ? 'bg-slate-800' : 'bg-gray-50'}`}>
                                {linkedId ? (
                                  <Link
                                    to={`/charity/${linkedId}`}
                                    onClick={() => trackSimilarOrgClick(charity.ein || '', linkedId, orgName, i)}
                                    className="flex items-center justify-between group"
                                  >
                                    <span className={`text-sm font-medium group-hover:text-emerald-500 ${isDark ? 'text-white' : 'text-gray-900'}`}>{orgName}</span>
                                    {gmScore && <GradeBadge score={gmScore} size="sm" />}
                                  </Link>
                                ) : (
                                  <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-gray-600'}`}>{orgName}</span>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </Card>
                    )}
              </>
            )}

            {/* IMPACT TAB */}
            {activeTab === 'impact' && (
              <>
                {/* Strengths */}
                <Card id="strengths">
                  <SectionHeader title="Strengths & Growth Areas" icon={TrendingUp} />
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {(baseline?.strengths || rich?.strengths)?.slice(0, 6).map((s, i) => {
                      const text = typeof s === 'string' ? s : s.point;
                      return (
                        <div key={i} className={`p-3 rounded-lg flex items-start gap-2 ${isDark ? 'bg-emerald-900/20' : 'bg-emerald-50'}`}>
                          <CheckCircle2 className="w-5 h-5 text-emerald-500 flex-shrink-0 mt-0.5" aria-hidden="true" />
                          <span className={`text-sm ${isDark ? 'text-slate-300' : 'text-gray-700'}`}>{text}</span>
                        </div>
                      );
                    })}
                    {(baseline?.areas_for_improvement || rich?.areas_for_improvement)?.slice(0, 4).map((a, i) => {
                      const text = typeof a === 'string' ? a : a.area;
                      return (
                        <div key={i} className={`p-3 rounded-lg flex items-start gap-2 ${isDark ? 'bg-amber-900/20' : 'bg-amber-50'}`}>
                          <TrendingUp className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" aria-hidden="true" />
                          <span className={`text-sm ${isDark ? 'text-slate-300' : 'text-gray-700'}`}>{text}</span>
                        </div>
                      );
                    })}
                  </div>
                </Card>

                {/* Best For Donors */}
                {rich?.ideal_donor_profile && (
                  <Card id="best-for">
                    <SectionHeader title="Best For" icon={Target} />
                    <p className={`text-lg font-medium mb-4 ${isDark ? 'text-white' : 'text-gray-800'}`}>
                      {rich.ideal_donor_profile.best_for_summary}
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      {rich.ideal_donor_profile.donor_motivations?.length > 0 && (
                        <div>
                          <h4 className={`text-sm font-semibold mb-2 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>Ideal for donors who:</h4>
                          <ul className="space-y-1">
                            {rich.ideal_donor_profile.donor_motivations.map((m, i) => (
                              <li key={i} className={`text-sm flex items-start gap-2 ${isDark ? 'text-slate-300' : 'text-gray-600'}`}>
                                <span className="text-emerald-500">•</span> {m}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {rich.ideal_donor_profile.giving_considerations?.length > 0 && (
                        <div>
                          <h4 className={`text-sm font-semibold mb-2 ${isDark ? 'text-slate-400' : 'text-gray-500'}`}>Things to consider:</h4>
                          <ul className="space-y-1">
                            {rich.ideal_donor_profile.giving_considerations.map((c, i) => (
                              <li key={i} className={`text-sm flex items-start gap-2 ${isDark ? 'text-slate-400' : 'text-gray-500'}`}>
                                <span>•</span> {c}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                    {rich.ideal_donor_profile.not_ideal_for && (
                      <p className={`mt-4 text-sm flex items-start gap-2 ${isDark ? 'text-amber-400' : 'text-amber-600'}`}>
                        <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" aria-hidden="true" />
                        <span><strong>Not ideal for:</strong> {rich.ideal_donor_profile.not_ideal_for}</span>
                      </p>
                    )}
                  </Card>
                )}

                {/* Impact Evidence */}
                {rich?.impact_evidence && (
                  <Card id="evidence">
                    <SectionHeader title="Impact Evidence" icon={BarChart3} />
                    <div className="flex items-center gap-4 mb-4">
                      {(() => {
                        const evGrade = rich.impact_evidence.evidence_grade;
                        const isBelowB = evGrade && !['A', 'B'].includes(evGrade);
                        return (
                          <>
                            <div className={`w-16 h-16 rounded-xl flex items-center justify-center text-2xl font-bold ${
                              isBelowB
                                ? isDark ? 'bg-slate-700 text-slate-400' : 'bg-slate-200 text-slate-500'
                                : isDark ? 'bg-emerald-900/50 text-emerald-400' : 'bg-emerald-100 text-emerald-700'
                            }`}>
                              {isBelowB ? 'NR' : evGrade}
                            </div>
                            <div>
                              <p className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>
                                {isBelowB ? 'Evidence: Developing' : 'Evidence Grade'}
                              </p>
                              {rich.impact_evidence.evidence_grade_explanation && (
                                <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-gray-600'}`}>{rich.impact_evidence.evidence_grade_explanation}</p>
                              )}
                            </div>
                          </>
                        );
                      })()}
                    </div>
                    {rich.impact_evidence.theory_of_change_summary && (
                      <div className={`p-3 rounded-lg mb-4 ${isDark ? 'bg-slate-800' : 'bg-gray-50'}`}>
                        <h4 className={`text-sm font-semibold mb-1 ${isDark ? 'text-white' : 'text-gray-900'}`}>Theory of Change</h4>
                        <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-gray-600'}`}>{rich.impact_evidence.theory_of_change_summary}</p>
                      </div>
                    )}
                    <div className="grid grid-cols-2 gap-3">
                      <div className={`p-3 rounded-lg ${isDark ? 'bg-slate-800' : 'bg-gray-50'}`}>
                        <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>RCT Available</p>
                        <p className={`text-sm font-semibold ${rich.impact_evidence.rct_available ? 'text-emerald-500' : isDark ? 'text-slate-400' : 'text-gray-600'}`}>
                          {rich.impact_evidence.rct_available ? 'Yes' : 'No'}
                        </p>
                      </div>
                      <div className={`p-3 rounded-lg ${isDark ? 'bg-slate-800' : 'bg-gray-50'}`}>
                        <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Theory of Change</p>
                        <p className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>{rich.impact_evidence.theory_of_change || 'Not documented'}</p>
                      </div>
                    </div>
                  </Card>
                )}

                {/* Theory of Change (baseline fallback when no rich impact_evidence) */}
                {!rich?.impact_evidence && (charity as any).theoryOfChange && (
                  <Card id="theory-of-change">
                    <SectionHeader title="Theory of Change" icon={Target} />
                    <p className={`text-sm leading-relaxed ${isDark ? 'text-slate-300' : 'text-gray-700'}`}>
                      {(charity as any).theoryOfChange}
                    </p>
                  </Card>
                )}

                {/* Evidence Quality Checklist */}
                {charity.evidenceQuality && (
                  <Card id="evidence-quality">
                    <SectionHeader title="Evidence Quality" icon={Shield} />
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {[
                        { key: 'hasOutcomeMethodology', label: 'Outcome methodology documented' },
                        { key: 'hasMultiYearMetrics', label: 'Multi-year metrics tracked' },
                        { key: 'thirdPartyEvaluated', label: 'Third-party evaluated' },
                        { key: 'receivesFoundationGrants', label: 'Receives foundation grants' },
                      ].map(({ key, label }) => {
                        const val = (charity.evidenceQuality as Record<string, unknown>)?.[key];
                        if (val === null || val === undefined) return null;
                        return (
                          <div key={key} className={`p-3 rounded-lg flex items-center gap-3 ${isDark ? 'bg-slate-800' : 'bg-gray-50'}`}>
                            {val ? (
                              <CheckCircle2 className="w-5 h-5 text-emerald-500 flex-shrink-0" />
                            ) : (
                              <AlertCircle className={`w-5 h-5 flex-shrink-0 ${isDark ? 'text-slate-600' : 'text-gray-400'}`} />
                            )}
                            <span className={`text-sm ${val ? (isDark ? 'text-white' : 'text-gray-900') : (isDark ? 'text-slate-500' : 'text-gray-400')}`}>
                              {label}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                    {charity.evidenceQuality.evaluationSources && charity.evidenceQuality.evaluationSources.length > 0 && (
                      <p className={`mt-3 text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>
                        Sources: {charity.evidenceQuality.evaluationSources.join(', ')}
                      </p>
                    )}
                  </Card>
                )}

                {/* Case Against / Balanced View */}
                {rich?.case_against && (
                  <Card id="case-against" className={isDark ? 'border-violet-700/50' : 'border-violet-200'}>
                    <SectionHeader title="Balanced View" icon={Scale} />
                    <p className={`text-sm mb-4 ${isDark ? 'text-slate-300' : 'text-gray-700'}`}>
                      <SourceLinkedText text={rich.case_against.summary} citations={citations} isDark={isDark} />
                    </p>
                    {rich.case_against.risk_factors?.length > 0 && (
                      <div className={`p-3 rounded-lg ${isDark ? 'bg-violet-900/20' : 'bg-violet-50'}`}>
                        <h4 className={`text-xs font-semibold mb-2 flex items-center gap-1 ${isDark ? 'text-violet-400' : 'text-violet-700'}`}>
                          <AlertTriangle className="w-3 h-3" aria-hidden="true" /> Risk Factors
                        </h4>
                        <ul className="space-y-1">
                          {rich.case_against.risk_factors.map((risk, i) => (
                            <li key={i} className={`text-sm flex items-start gap-2 ${isDark ? 'text-slate-300' : 'text-gray-700'}`}>
                              <span className="text-violet-500">•</span>
                              <SourceLinkedText text={risk} citations={citations} isDark={isDark} />
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </Card>
                )}

                {/* Zakat claim evidence (zakat-eligible charities only) */}
                {amal?.wallet_tag?.includes('ZAKAT') && charity.zakatClaimEvidence && charity.zakatClaimEvidence.length > 0 && (
                  <Card id="zakat-evidence">
                    <SectionHeader title="Zakat Claim Evidence" icon={Heart} />
                    {charity.zakatClaimEvidence.map((evidence, i) => (
                      <p key={i} className={`text-sm leading-relaxed ${isDark ? 'text-slate-400' : 'text-gray-600'}`}>{evidence}</p>
                    ))}
                  </Card>
                )}

                {/* Donor Fit */}
                {rich?.donor_fit_matrix && (
                  <Card id="donor-fit">
                    <SectionHeader title="Donor Fit" icon={Target} />
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {rich.donor_fit_matrix.cause_area && (
                        <div>
                          <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Cause Area</p>
                          <p className={`text-sm font-medium ${isDark ? 'text-white' : 'text-gray-900'}`}>{rich.donor_fit_matrix.cause_area.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase()).replace(/\bAnd\b/g, '&')}</p>
                        </div>
                      )}
                      {rich.donor_fit_matrix.giving_style && (
                        <div>
                          <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Giving Style</p>
                          <p className={`text-sm font-medium ${isDark ? 'text-white' : 'text-gray-900'}`}>{rich.donor_fit_matrix.giving_style}</p>
                        </div>
                      )}
                      {rich.donor_fit_matrix.geographic_focus && rich.donor_fit_matrix.geographic_focus.length > 0 && (
                        <div>
                          <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Geographic Focus</p>
                          <p className={`text-sm font-medium ${isDark ? 'text-white' : 'text-gray-900'}`}>
                            {rich.donor_fit_matrix.geographic_focus.slice(0, 5).join(', ')}
                          </p>
                        </div>
                      )}
                      {rich.donor_fit_matrix.zakat_asnaf_served && rich.donor_fit_matrix.zakat_asnaf_served.length > 0 && (
                        <div className="md:col-span-2 lg:col-span-3">
                          <p className={`text-xs mb-1 ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Zakat Categories Served</p>
                          <div className="flex flex-wrap gap-1">
                            {rich.donor_fit_matrix.zakat_asnaf_served.map((asnaf, i) => (
                              <span key={i} className={`px-2 py-0.5 rounded text-xs ${isDark ? 'bg-emerald-900/50 text-emerald-400' : 'bg-emerald-50 text-emerald-700'}`}>
                                {asnaf}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                    {/* Giving Tiers */}
                    {rich.donor_fit_matrix.giving_tiers && rich.donor_fit_matrix.giving_tiers.length > 0 && (
                      <div className={`mt-4 pt-4 border-t ${isDark ? 'border-slate-700' : 'border-gray-200'}`}>
                        <p className={`text-xs mb-3 ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Suggested Giving Tiers</p>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                          {rich.donor_fit_matrix.giving_tiers.map((tier: any, i: number) => (
                            <div key={i} className={`p-3 rounded-lg text-center ${isDark ? 'bg-slate-800' : 'bg-gray-50'}`}>
                              <p className={`text-lg font-bold ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>
                                {tier.amount || tier.range}
                              </p>
                              <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>
                                {tier.label || tier.impact}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </Card>
                )}
              </>
            )}

            {/* ORGANIZATION TAB - Financials + Governance combined */}
            {activeTab === 'organization' && (
              <>
                {/* Financial Overview */}
                <Card id="financial-overview">
                  <SectionHeader title="Financial Overview" icon={DollarSign} />
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className={`p-4 rounded-lg text-center ${isDark ? 'bg-slate-800' : 'bg-gray-50'}`}>
                      <p className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>{formatCurrency(revenue)}</p>
                      <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Annual Revenue</p>
                    </div>
                    <div className={`p-4 rounded-lg text-center ${isDark ? 'bg-slate-800' : 'bg-gray-50'}`}>
                      <p className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>{formatCurrency(totalExpenses)}</p>
                      <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Total Expenses</p>
                    </div>
                    {financials?.netAssets && (
                      <div className={`p-4 rounded-lg text-center ${isDark ? 'bg-slate-800' : 'bg-gray-50'}`}>
                        <p className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>{formatCurrency(financials.netAssets)}</p>
                        <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Net Assets</p>
                      </div>
                    )}
                    {financials?.workingCapitalMonths != null && (
                      <div className={`p-4 rounded-lg text-center ${isDark ? 'bg-slate-800' : 'bg-gray-50'}`}>
                        <p className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>{financials.workingCapitalMonths.toFixed(1)}</p>
                        <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Months Working Capital</p>
                      </div>
                    )}
                    {hasExpenseData && (
                      <div className={`p-4 rounded-lg text-center ${isDark ? 'bg-emerald-900/30' : 'bg-emerald-50'}`}>
                        <p className={`text-2xl font-bold ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>{programRatio.toFixed(0)}%</p>
                        <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Program Spending</p>
                      </div>
                    )}
                  </div>
                  {/* Form 990 Exempt Notice */}
                  {!!charity.form990Exempt && !revenue && (
                    <div className={`mt-4 p-3 rounded-lg text-sm ${isDark ? 'bg-slate-800 text-slate-300' : 'bg-amber-50 text-amber-800'}`}>
                      <div className="font-medium mb-1">Form 990 Exempt</div>
                      <div className={`text-xs ${isDark ? 'text-slate-400' : 'text-amber-700'}`}>
                        {charity.form990ExemptReason || 'Religious organization'} — not required to file public financial disclosures.
                      </div>
                    </div>
                  )}
                </Card>

                {/* Expense Breakdown */}
                {hasExpenseData && (
                  <Card id="expense-breakdown">
                    <SectionHeader title="Expense Breakdown" icon={BarChart3} />
                    <div className={`h-4 rounded-full overflow-hidden flex mb-4 ${isDark ? 'bg-slate-700' : 'bg-gray-200'}`}>
                      <div className="bg-emerald-500" style={{ width: `${programRatio}%` }} />
                      <div className={isDark ? 'bg-slate-500' : 'bg-slate-400'} style={{ width: `${adminRatio}%` }} />
                      <div className="bg-amber-500" style={{ width: `${fundRatio}%` }} />
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="w-3 h-3 rounded-full bg-emerald-500" />
                          <span className={`text-sm font-medium ${isDark ? 'text-white' : 'text-gray-900'}`}>Programs</span>
                        </div>
                        <p className={`text-lg font-bold ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>{programRatio.toFixed(0)}%</p>
                        <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>{formatCurrency(financials?.programExpenses)}</p>
                      </div>
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`w-3 h-3 rounded-full ${isDark ? 'bg-slate-500' : 'bg-slate-400'}`} />
                          <span className={`text-sm font-medium ${isDark ? 'text-white' : 'text-gray-900'}`}>Admin</span>
                        </div>
                        <p className={`text-lg font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>{adminRatio.toFixed(0)}%</p>
                        <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>{formatCurrency(financials?.adminExpenses)}</p>
                      </div>
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="w-3 h-3 rounded-full bg-amber-500" />
                          <span className={`text-sm font-medium ${isDark ? 'text-white' : 'text-gray-900'}`}>Fundraising</span>
                        </div>
                        <p className={`text-lg font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>{fundRatio.toFixed(0)}%</p>
                        <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>{formatCurrency(financials?.fundraisingExpenses)}</p>
                      </div>
                    </div>
                  </Card>
                )}

                {/* Financial History */}
                {rich?.financial_deep_dive?.yearly_financials && rich.financial_deep_dive.yearly_financials.length > 0 && (
                  <Card id="financial-history">
                    <SectionHeader title="Financial History" icon={TrendingUp} />
                    <div className="space-y-2 mb-4">
                      {rich.financial_deep_dive.yearly_financials.map(year => {
                        const maxRevenue = Math.max(...rich.financial_deep_dive!.yearly_financials!.map(y => y.revenue || 0));
                        const widthPct = maxRevenue > 0 ? ((year.revenue || 0) / maxRevenue) * 100 : 0;
                        return (
                          <div key={year.year} className="flex items-center gap-3">
                            <span className={`text-xs font-mono w-12 ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>{year.year}</span>
                            <div className={`flex-1 h-6 rounded ${isDark ? 'bg-slate-800' : 'bg-gray-100'}`}>
                              <div className="h-full rounded bg-emerald-500" style={{ width: `${widthPct}%` }} />
                            </div>
                            <span className={`text-sm font-mono w-20 text-right ${isDark ? 'text-white' : 'text-gray-900'}`}>{formatCurrency(year.revenue)}</span>
                          </div>
                        );
                      })}
                    </div>
                    {rich.financial_deep_dive.revenue_cagr_3yr !== undefined && (
                      <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-gray-600'}`}>
                        3-Year CAGR: <span className={`font-semibold ${rich.financial_deep_dive.revenue_cagr_3yr > 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                          {rich.financial_deep_dive.revenue_cagr_3yr > 0 ? '+' : ''}{rich.financial_deep_dive.revenue_cagr_3yr.toFixed(1)}%
                        </span>
                      </p>
                    )}
                  </Card>
                )}

                {/* Grantmaking */}
                {rich?.grantmaking_profile?.is_significant_grantmaker && (
                  <Card id="grantmaking">
                    <SectionHeader title="Grantmaking" icon={Landmark} />
                    <div className="grid grid-cols-2 gap-4 mb-4">
                      <div className={`p-4 rounded-lg ${isDark ? 'bg-slate-800' : 'bg-gray-50'}`}>
                        <p className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>{formatCurrency(rich.grantmaking_profile.total_grants)}</p>
                        <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Total Grants</p>
                      </div>
                      <div className={`p-4 rounded-lg ${isDark ? 'bg-slate-800' : 'bg-gray-50'}`}>
                        <p className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>{rich.grantmaking_profile.grant_count || 0}</p>
                        <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Recipients</p>
                      </div>
                    </div>
                    {rich.grantmaking_profile.top_recipients && rich.grantmaking_profile.top_recipients.length > 0 && (
                      <div>
                        <h4 className={`text-sm font-semibold mb-2 ${isDark ? 'text-slate-400' : 'text-gray-500'}`}>Top Recipients</h4>
                        <ul className="space-y-1">
                          {rich.grantmaking_profile.top_recipients.slice(0, 5).map((r, i) => (
                            <li key={i} className={`text-sm ${isDark ? 'text-slate-300' : 'text-gray-700'}`}>• {r}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </Card>
                )}
                {/* Grants Data (baseline fallback when no rich grantmaking_profile) */}
                {!rich?.grantmaking_profile && (charity as any).grantsData && (charity as any).grantsData.length > 0 && (
                  <Card id="grants-data">
                    <SectionHeader title="Grants Made" icon={Landmark} />
                    <div className={`overflow-x-auto`}>
                      <table className={`w-full text-sm ${isDark ? 'text-slate-300' : 'text-gray-700'}`}>
                        <thead>
                          <tr className={`border-b ${isDark ? 'border-slate-700' : 'border-gray-200'}`}>
                            <th className={`text-left py-2 text-xs font-medium ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Recipient</th>
                            <th className={`text-right py-2 text-xs font-medium ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Amount</th>
                          </tr>
                        </thead>
                        <tbody>
                          {((charity as any).grantsData as Array<{ name?: string; recipient?: string; amount?: number }>).slice(0, 10).map((grant, i) => (
                            <tr key={i} className={`border-b ${isDark ? 'border-slate-800' : 'border-gray-100'}`}>
                              <td className="py-2">{grant.name || grant.recipient || 'Unknown'}</td>
                              <td className="py-2 text-right font-mono">{grant.amount ? formatCurrency(grant.amount) : '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Card>
                )}

                {/* Leadership & Governance */}
                <Card id="leadership">
                  <SectionHeader title="Leadership & Governance" icon={Users} />
                  {rich?.organizational_capacity ? (
                    <div className="space-y-4">
                      {rich.organizational_capacity.ceo_name && (
                        <div className={`p-4 rounded-lg ${isDark ? 'bg-slate-800' : 'bg-gray-50'}`}>
                          <p className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>{rich.organizational_capacity.ceo_name}</p>
                          <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-gray-500'}`}>CEO/Executive Director</p>
                          {!!rich.organizational_capacity.ceo_compensation && (
                            <p className={`text-sm mt-1 ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>
                              Compensation: {formatCurrency(rich.organizational_capacity.ceo_compensation)}
                            </p>
                          )}
                        </div>
                      )}
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                        {!!rich.organizational_capacity.board_size && (
                          <div>
                            <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Board Size</p>
                            <p className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>{rich.organizational_capacity.board_size}</p>
                          </div>
                        )}
                        {!!rich.organizational_capacity.employees_count && (
                          <div>
                            <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Employees</p>
                            <p className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>{rich.organizational_capacity.employees_count}</p>
                          </div>
                        )}
                        {rich.organizational_capacity.independent_board_pct !== undefined && (
                          <div>
                            <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Board Independence</p>
                            <p className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>{(rich.organizational_capacity.independent_board_pct * 100).toFixed(0)}%</p>
                          </div>
                        )}
                      </div>
                      <div className="flex gap-4 mt-2">
                        <span className={`flex items-center gap-1.5 text-sm ${isDark ? 'text-slate-400' : 'text-gray-600'}`}>
                          {rich.organizational_capacity.has_conflict_policy ? <CheckCircle2 className="w-4 h-4 text-emerald-500" aria-hidden="true" /> : <AlertCircle className="w-4 h-4 text-slate-400" aria-hidden="true" />}
                          COI Policy
                        </span>
                        <span className={`flex items-center gap-1.5 text-sm ${isDark ? 'text-slate-400' : 'text-gray-600'}`}>
                          {rich.organizational_capacity.has_financial_audit ? <CheckCircle2 className="w-4 h-4 text-emerald-500" aria-hidden="true" /> : <AlertCircle className="w-4 h-4 text-slate-400" aria-hidden="true" />}
                          Audited
                        </span>
                      </div>
                    </div>
                  ) : charity.baselineGovernance ? (
                    <div className="space-y-2">
                      {!!charity.baselineGovernance.boardSize && <p className={`text-sm ${isDark ? 'text-slate-300' : 'text-gray-700'}`}>Board Size: {charity.baselineGovernance.boardSize}</p>}
                      {!!charity.baselineGovernance.ceoCompensation && <p className={`text-sm ${isDark ? 'text-slate-300' : 'text-gray-700'}`}>CEO Compensation: {formatCurrency(charity.baselineGovernance.ceoCompensation)}</p>}
                    </div>
                  ) : (
                    <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-gray-500'}`}>Governance data not available.</p>
                  )}
                </Card>

                {/* BBB Rating */}
                {rich?.bbb_assessment && (
                  <Card id="bbb">
                    <SectionHeader title="BBB Wise Giving" icon={Shield} />
                    <div className="flex items-center gap-4 mb-4">
                      <div className={`w-14 h-14 rounded-lg flex items-center justify-center ${
                        rich.bbb_assessment.meets_all_standards
                          ? isDark ? 'bg-emerald-900/50' : 'bg-emerald-100'
                          : isDark ? 'bg-amber-900/50' : 'bg-amber-100'
                      }`}>
                        {rich.bbb_assessment.meets_all_standards
                          ? <CheckCircle2 className={`w-8 h-8 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />
                          : <AlertTriangle className={`w-8 h-8 ${isDark ? 'text-amber-400' : 'text-amber-600'}`} aria-hidden="true" />}
                      </div>
                      <div>
                        <p className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>
                          {rich.bbb_assessment.meets_all_standards ? 'Meets Standards' : 'Standards Review'}
                        </p>
                        {rich.bbb_assessment.standards_met !== undefined && (
                          <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-gray-500'}`}>{rich.bbb_assessment.standards_met}/20 standards met</p>
                        )}
                      </div>
                    </div>
                  </Card>
                )}

                {/* Data Quality */}
                <Card id="data-confidence">
                  <SectionHeader title="Data Quality" icon={BarChart3} />
                  <div className="grid grid-cols-2 gap-4">
                    {rich?.data_confidence?.confidence_score && (
                      <div className={`p-4 rounded-lg ${isDark ? 'bg-slate-800' : 'bg-gray-50'}`}>
                        <p className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>{rich.data_confidence.confidence_score}/100</p>
                        <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Confidence Score</p>
                      </div>
                    )}
                    {rich?.data_confidence?.total_citations && (
                      <div className={`p-4 rounded-lg ${isDark ? 'bg-slate-800' : 'bg-gray-50'}`}>
                        <p className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>{rich.data_confidence.total_citations}</p>
                        <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-gray-400'}`}>Citations</p>
                      </div>
                    )}
                  </div>
                  {amal?.evaluation_date && (
                    <p className={`text-sm mt-4 ${isDark ? 'text-slate-400' : 'text-gray-500'}`}>
                      Last evaluated: {new Date(amal.evaluation_date).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
                    </p>
                  )}
                </Card>

                {/* External Links */}
                <Card id="external-links">
                  <SectionHeader title="Verify Sources" icon={ExternalLink} />
                  <div className="space-y-3">
                    {charity.website && (
                      <a href={charity.website} target="_blank" rel="noopener noreferrer" onClick={() => trackOutboundClick(charity.id ?? charity.ein ?? '', charity.name, charity.website || '')}
                        className={`flex items-center gap-2 text-sm ${isDark ? 'text-emerald-400 hover:text-emerald-300' : 'text-emerald-600 hover:text-emerald-700'}`}>
                        <Globe className="w-4 h-4" aria-hidden="true" /> Official Website <ExternalLink className="w-3 h-3" aria-hidden="true" />
                      </a>
                    )}
                    <a href={`https://www.charitynavigator.org/ein/${(charity.ein ?? '').replace(/-/g, '')}`} target="_blank" rel="noopener noreferrer"
                      className={`flex items-center gap-2 text-sm ${isDark ? 'text-slate-400 hover:text-slate-300' : 'text-gray-500 hover:text-gray-600'}`}>
                      Charity Navigator <ExternalLink className="w-3 h-3" aria-hidden="true" />
                    </a>
                    <a href={`https://projects.propublica.org/nonprofits/organizations/${(charity.ein ?? '').replace(/-/g, '')}`} target="_blank" rel="noopener noreferrer"
                      className={`flex items-center gap-2 text-sm ${isDark ? 'text-slate-400 hover:text-slate-300' : 'text-gray-500 hover:text-gray-600'}`}>
                      ProPublica Form 990 <ExternalLink className="w-3 h-3" aria-hidden="true" />
                    </a>
                  </div>
                </Card>
              </>
            )}

        </div>
      </div>

      {/* Footer metadata bar */}
      <div className={`hidden lg:block border-t mt-8 pt-6 pb-8 ${
        isDark ? 'border-slate-800' : 'border-gray-200'
      }`}>
        <div className={`max-w-6xl mx-auto px-6 flex items-center justify-center gap-2 text-xs ${
          isDark ? 'text-slate-500' : 'text-gray-400'
        }`}>
          <span>EIN: {charity.ein}</span>
          {amal?.evaluation_date && (
            <>
              <span>·</span>
              <span>Last evaluated {new Date(amal.evaluation_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
            </>
          )}
          {currentView && onViewChange && (
            <>
              <span>·</span>
              <InlineViewToggle currentView={currentView} onViewChange={onViewChange} />
            </>
          )}
          <span>·</span>
          <ShareButton
            charityId={charity.ein!}
            charityName={charity.name}
            isDark={isDark}
            variant="text"
            className={`font-medium ${isDark ? 'text-emerald-400/80 hover:text-emerald-400' : 'text-emerald-600/80 hover:text-emerald-600'}`}
          />
          <span>·</span>
          <ReportIssueButton
            charityId={charity.ein!}
            charityName={charity.name}
            variant="text"
            isDark={isDark}
            className={`font-medium ${isDark ? 'text-slate-500 hover:text-slate-300' : 'text-gray-400 hover:text-gray-600'}`}
          />
        </div>
      </div>

      {/* Donation Modal */}
      <AddDonationModal
        isOpen={showDonationModal}
        onClose={() => setShowDonationModal(false)}
        onSave={addDonation as any}
        paymentSources={getPaymentSources()}
        prefillCharity={{ ein: charity.ein!, name: charity.name }}
      />
    </div>
  );
};

export default NicheView;
