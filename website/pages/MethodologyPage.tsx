import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  ShieldCheck,
  Database,
  Brain,
  Users,
  ArrowRight,
  CheckCircle2,
  FileText,
  Lock,
  TrendingUp,
  AlertTriangle,
  XCircle,
  Eye,
  Target
} from 'lucide-react';
import { useCharities } from '../src/hooks/useCharities';
import { useCalibrationReport } from '../src/hooks/useCalibrationReport';
import { getEvidenceStageLabel } from '../src/utils/scoreConstants';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import { MethodologyInsights } from '../components/MethodologyInsights';
import { CauseAreaMatrix } from '../components/CauseAreaMatrix';

// Get top performing charities for the showcase
const getTopCharities = (charities: any[]) => {
  return charities
    .filter(c => c.amalEvaluation?.amal_score && c.amalEvaluation.amal_score >= 70)
    .sort((a, b) => (b.amalEvaluation?.amal_score || 0) - (a.amalEvaluation?.amal_score || 0))
    .slice(0, 12);
};

const CUE_DISPLAY_LABELS: Record<string, string> = {
  'Strong Match': 'High Confidence',
  'Good Match': 'Good Signals',
  'Mixed Signals': 'Mixed Signals',
  'Limited Match': 'Limited Signals',
};

export const MethodologyPage: React.FC = () => {
  React.useEffect(() => {
    document.title = 'Our Methodology | Good Measure Giving';
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, []);
  const { isDark } = useLandingTheme();
  const { charities, summaries, loading } = useCharities();
  const { report: calibrationReport } = useCalibrationReport();

  // Get top-performing charities for showcase
  const topCharities = useMemo(() => getTopCharities(charities), [charities]);

  // Score distribution buckets for visualization (aligned with scoreConstants.ts thresholds)
  const scoreBuckets = useMemo(() => {
    const buckets = { exceptional: 0, good: 0, developing: 0, emerging: 0 };
    charities.forEach(c => {
      const score = c.amalEvaluation?.amal_score;
      if (!score) return;
      if (score >= 75) buckets.exceptional++;
      else if (score >= 60) buckets.good++;
      else if (score >= 30) buckets.developing++;
      else buckets.emerging++;
    });
    return buckets;
  }, [charities]);

  // Prepare data for insights visualization (needs pillar scores)
  const insightsData = useMemo(() => {
    return summaries
      .filter(s => s.pillarScores && s.amalScore)
      .map(s => ({
        id: s.id,
        name: s.name,
        amalScore: s.amalScore!,
        walletTag: s.walletTag || '',
        pillarScores: s.pillarScores!,
        category: s.primaryCategory || 'OTHER',
        totalRevenue: s.totalRevenue,
      }));
  }, [summaries]);

  return (
    <div className={`min-h-screen transition-colors duration-300 ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
      {/* Hero */}
      <div className={`border-b ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <div className="text-center">
            <h1 className={`text-4xl md:text-5xl font-bold font-merriweather mb-6 [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>
              How We Evaluate Charities
            </h1>
            <p className={`text-xl max-w-3xl mx-auto leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              A 100-point framework measuring what matters: how much good each dollar does,
              and whether it{'\u2019'}s the right fit for Muslim donors. No jargon, full transparency.
            </p>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-16">

        {/* TL;DR Summary */}
        <section className="mb-12">
          <div className={`rounded-2xl p-6 ${isDark ? 'bg-emerald-900/20 border border-emerald-800/30' : 'bg-emerald-50 border border-emerald-200'}`}>
            <h2 className={`text-lg font-bold mb-3 [text-wrap:balance] ${isDark ? 'text-emerald-400' : 'text-emerald-800'}`}>TL;DR</h2>
            <p className={`text-lg leading-relaxed ${isDark ? 'text-emerald-100' : 'text-emerald-900'}`}>
              We aggregate data from <strong>multiple sources</strong>: IRS Form 990 filings (via ProPublica API), Charity Navigator ratings, Candid transparency seals, BBB accreditation status, and charity websites. We score on two dimensions: <strong>Impact</strong> (how much good does each dollar do?) and <strong>Alignment</strong> (is this the right fit for Muslim donors?), with up to 10 points deducted for serious risks. A separate <strong>Data Confidence</strong> signal tells you how much data we had to work with. Most charities score 50-70. Above 75 is exceptional.
            </p>
          </div>
        </section>

        {/* The Big Picture */}
        <section className="mb-20">
          <h2 className={`text-2xl font-bold font-merriweather mb-8 [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>The Big Picture</h2>

          <div className={`rounded-2xl border p-8 mb-8 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
            <p className={`text-lg leading-relaxed mb-6 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              Most charity ratings focus on overhead ratios {'\u2014'} how much goes to {'\u201C'}programs{'\u201D'} vs {'\u201C'}admin.{'\u201D'}
              But an organization can be highly efficient at doing something that doesn{'\u2019'}t work.
            </p>
            <p className={`text-lg leading-relaxed mb-6 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              We ask two questions that matter more:
            </p>
            <ul className={`text-lg leading-relaxed space-y-2 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              <li><strong>Impact:</strong> How much good does each dollar do? (cost efficiency, proven outcomes, financial health, governance)</li>
              <li><strong>Alignment:</strong> Is this the right charity for Muslim donors? (cause urgency, donor fit, funding gap, track record)</li>
            </ul>
            <p className={`text-lg leading-relaxed mt-6 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              Each dimension is worth 50 points, with up to 10 points deducted for red flags.
              A separate Data Confidence signal shows how robust our data is.
              Then we help you route your donation to the right {'\u201C'}wallet{'\u201D'} {'\u2014'} Zakat or Sadaqah.
            </p>
          </div>

          {/* Process Overview */}
          <div className="grid md:grid-cols-4 gap-4">
            <div className={`rounded-xl border p-6 text-center ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-4 ${isDark ? 'bg-blue-900/30 text-blue-400' : 'bg-blue-100 text-blue-600'}`}>
                <Database className="w-6 h-6" aria-hidden="true" />
              </div>
              <h3 className={`font-bold mb-2 ${isDark ? 'text-white' : 'text-slate-900'}`}>1. Gather Data</h3>
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>We pull from IRS filings, rating agencies, and charity websites</p>
            </div>
            <div className={`rounded-xl border p-6 text-center ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-4 ${isDark ? 'bg-purple-900/30 text-purple-400' : 'bg-purple-100 text-purple-600'}`}>
                <Brain className="w-6 h-6" aria-hidden="true" />
              </div>
              <h3 className={`font-bold mb-2 ${isDark ? 'text-white' : 'text-slate-900'}`}>2. Extract & Score</h3>
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>AI extracts data; deterministic code calculates scores</p>
            </div>
            <div className={`rounded-xl border p-6 text-center ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-4 ${isDark ? 'bg-amber-900/30 text-amber-400' : 'bg-amber-100 text-amber-600'}`}>
                <Eye className="w-6 h-6" aria-hidden="true" />
              </div>
              <h3 className={`font-bold mb-2 ${isDark ? 'text-white' : 'text-slate-900'}`}>3. Validate</h3>
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Automated checks flag conflicts; citations enable verification</p>
            </div>
            <div className={`rounded-xl border p-6 text-center ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-4 ${isDark ? 'bg-emerald-900/30 text-emerald-400' : 'bg-emerald-100 text-emerald-600'}`}>
                <CheckCircle2 className="w-6 h-6" aria-hidden="true" />
              </div>
              <h3 className={`font-bold mb-2 ${isDark ? 'text-white' : 'text-slate-900'}`}>4. Publish</h3>
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>Clear scores and guidance you can act on</p>
            </div>
          </div>
        </section>

        {/* Our Perspective */}
        <section className="mb-20">
          <h2 className={`text-2xl font-bold font-merriweather mb-4 [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>Our Perspective</h2>
          <div className={`rounded-2xl border p-8 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
            <div className={`rounded-xl p-4 ${isDark ? 'bg-emerald-900/20 border border-emerald-800/30' : 'bg-emerald-50 border border-emerald-200'}`}>
              <p className={`text-sm ${isDark ? 'text-emerald-200/80' : 'text-emerald-800'}`}>
                <strong>Philosophy:</strong> We evaluate from the perspective of Muslim donors seeking to increase
                safety, dignity, representation, and resilience for Muslim communities worldwide. We focus on
                charities that either serve Muslim communities directly or demonstrate alignment with donor values.
              </p>
            </div>
          </div>
        </section>

        {/* The Two Dimensions */}
        <section className="mb-20">
          <h2 className={`text-2xl font-bold font-merriweather mb-4 [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>The Two Dimensions</h2>
          <p className={`mb-4 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
            Every charity receives a score from 0-100, built from two dimensions (50 points each)
            minus any risk deductions (up to -10 points).
          </p>
          <div className={`rounded-xl p-4 mb-8 ${isDark ? 'bg-slate-800 border border-slate-700' : 'bg-slate-100'}`}>
            <p className={`text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              <strong>How to read scores:</strong> Most charities score 50-70. Scores above 75 are exceptional.
              A score below 50 doesn{'\u2019'}t mean {'\u201C'}bad{'\u201D'} {'\u2014'} it usually means we don{'\u2019'}t have enough data yet, or the charity
              is newer and still building its track record.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-6 mb-8">
            {/* Impact */}
            <div className={`rounded-2xl border overflow-hidden ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
              <div className={`px-6 py-4 ${isDark ? 'bg-blue-900/40' : 'bg-blue-600'} text-white`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="w-5 h-5" aria-hidden="true" />
                    <h3 className="font-bold">Impact</h3>
                  </div>
                  <span className="text-blue-200 text-sm">50 points</span>
                </div>
                <p className="text-blue-200 text-sm mt-1">How much good does each dollar do?</p>
              </div>
              <div className="p-6">
                <p className={`text-sm mb-4 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  Impact combines cost efficiency, proven outcomes, financial health, and governance
                  into a single question: how much good does each dollar actually produce, and can
                  the organization prove it?
                </p>
                <h4 className={`text-xs font-bold uppercase tracking-wider mb-2 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>What We Measure (50 points total)</h4>
                <ul className={`text-sm space-y-1 mb-4 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  <li>{'\u2022'} <strong>Cost per beneficiary</strong> (20 pts): Cause-adjusted benchmarks with smooth interpolation</li>
                  <li>{'\u2022'} <strong>Directness</strong> (7 pts): Direct service vs indirect approaches</li>
                  <li>{'\u2022'} <strong>Financial health</strong> (7 pts): Working capital ratio (sweet spot: 1-2 months reserves)</li>
                  <li>{'\u2022'} <strong>Program ratio</strong> (6 pts): Percentage of spending on actual programs</li>
                  <li>{'\u2022'} <strong>Evidence & outcomes</strong> (5 pts): Verified {'\u2192'} Tracked {'\u2192'} Measured {'\u2192'} Reported {'\u2192'} Unverified</li>
                  <li>{'\u2022'} <strong>Theory of change</strong> (3 pts): Has a documented logic model?</li>
                  <li>{'\u2022'} <strong>Governance</strong> (2 pts): Board size and oversight</li>
                </ul>

                <h4 className={`text-xs font-bold uppercase tracking-wider mb-2 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>Cause-Adjusted Benchmarks</h4>
                <div className={`text-xs space-y-1 mb-4 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  <p><strong>Food:</strong> &lt;$0.25/meal excellent, $0.25-0.50 good</p>
                  <p><strong>Education:</strong> &lt;$100/student/yr excellent, $100-300 good</p>
                  <p><strong>Healthcare:</strong> &lt;$25/patient (primary), &lt;$500 (surgical)</p>
                  <p><strong>Humanitarian:</strong> &lt;$75/beneficiary excellent, $75-175 good</p>
                </div>

                <div className={`rounded-lg p-3 mb-4 ${isDark ? 'bg-amber-900/20 border border-amber-800/30' : 'bg-amber-50 border border-amber-200'}`}>
                  <p className={`text-xs ${isDark ? 'text-amber-200/80' : 'text-amber-800'}`}>
                    <strong>The overhead myth:</strong> Low overhead isn{'\u2019'}t always good. A legal advocacy
                    org might have higher admin costs because lawyers are expensive {'\u2014'} but win cases
                    protecting millions of Muslims. We consider context, not just ratios.
                  </p>
                </div>
                <div className={`rounded-lg p-3 ${isDark ? 'bg-blue-900/20 border border-blue-800/30' : 'bg-blue-50 border border-blue-200'}`}>
                  <p className={`text-xs ${isDark ? 'text-blue-200/80' : 'text-blue-800'}`}>
                    <strong>What{'\u2019'}s a {'\u201C'}Theory of Change{'\u201D'}?</strong> It{'\u2019'}s the charity{'\u2019'}s explanation of <em>why</em> their
                    approach should work {'\u2014'} the logical steps from {'\u201C'}what we do{'\u201D'} to {'\u201C'}lives improved.{'\u201D'}
                    Charities that have written this down tend to be more thoughtful about whether their programs actually work.
                  </p>
                </div>
              </div>
            </div>

            {/* Alignment */}
            <div className={`rounded-2xl border overflow-hidden ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
              <div className={`px-6 py-4 ${isDark ? 'bg-emerald-900/40' : 'bg-emerald-600'} text-white`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Target className="w-5 h-5" aria-hidden="true" />
                    <h3 className="font-bold">Alignment</h3>
                  </div>
                  <span className="text-emerald-200 text-sm">50 points</span>
                </div>
                <p className="text-emerald-200 text-sm mt-1">Is this the right charity for Muslim donors?</p>
              </div>
              <div className="p-6">
                <p className={`text-sm mb-4 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  Alignment measures whether your donation would make more difference here than elsewhere,
                  and whether the charity is a natural fit for Muslim donors. It rewards charities
                  working in urgent, underserved spaces.
                </p>
                <h4 className={`text-xs font-bold uppercase tracking-wider mb-2 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>What We Measure (50 points total)</h4>
                <ul className={`text-sm space-y-1 mb-4 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  <li>{'\u2022'} <strong>Muslim donor fit</strong> (19 pts): Zakat clarity, asnaf categories, Muslim-focused mission</li>
                  <li>{'\u2022'} <strong>Cause urgency</strong> (13 pts): Humanitarian crises and extreme poverty score highest</li>
                  <li>{'\u2022'} <strong>Underserved space</strong> (7 pts): Niche causes and underserved populations</li>
                  <li>{'\u2022'} <strong>Track record</strong> (6 pts): Years of operation and demonstrated reliability</li>
                  <li>{'\u2022'} <strong>Funding gap</strong> (5 pts): Smaller orgs where your dollar goes further</li>
                </ul>
                <div className={`rounded-lg p-3 mb-4 ${isDark ? 'bg-slate-800' : 'bg-slate-100'}`}>
                  <p className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                    <strong>Why Muslim-focused charities often score higher:</strong> Many serve
                    communities overlooked by mainstream philanthropy. Your Zakat dollar may go
                    further at a charity serving Muslim refugees than at a massive international
                    org with thousands of donors.
                  </p>
                </div>

                <h4 className={`text-xs font-bold uppercase tracking-wider mb-2 ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>Size-Adjusted Expectations</h4>
                <div className={`text-xs space-y-1 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  <p><strong>Emerging</strong> (&lt;$1M): We reward hustle, not formal rigor</p>
                  <p><strong>Growing</strong> ($1-10M): Standard expectations, building systems</p>
                  <p><strong>Established</strong> (&gt;$10M): Full accountability expected</p>
                </div>
              </div>
            </div>
          </div>

          {/* Data Confidence Signal */}
          <div className={`rounded-xl border p-6 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
            <div className="flex items-center gap-2 mb-3">
              <ShieldCheck className={`w-5 h-5 ${isDark ? 'text-blue-400' : 'text-blue-600'}`} aria-hidden="true" />
              <h3 className={`font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>Data Confidence Signal</h3>
              <span className={`text-xs px-2 py-0.5 rounded ${isDark ? 'bg-slate-700 text-slate-400' : 'bg-slate-200 text-slate-600'}`}>Outside the score</span>
            </div>
            <p className={`text-sm mb-3 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              Separate from the 100-point score, we compute a Data Confidence signal (0.0-1.0) that tells you
              how much data we had to work with. This considers third-party verification, transparency seals,
              and how many independent sources corroborate the same facts.
            </p>
            <div className="flex gap-2 text-xs flex-wrap">
              <span className={`px-2 py-1 rounded ${isDark ? 'bg-emerald-900/30 text-emerald-400' : 'bg-emerald-100 text-emerald-800'}`}>HIGH ({'\u2265'}0.7): 2+ strong ratings, verified data</span>
              <span className={`px-2 py-1 rounded ${isDark ? 'bg-amber-900/30 text-amber-400' : 'bg-amber-100 text-amber-800'}`}>MEDIUM (0.4-0.7): Some verification</span>
              <span className={`px-2 py-1 rounded ${isDark ? 'bg-rose-900/30 text-rose-400' : 'bg-rose-100 text-rose-800'}`}>LOW (&lt;0.4): Limited third-party data</span>
            </div>
          </div>
        </section>

        {/* Risk Assessment */}
        <section className="mb-20">
          <h2 className={`text-2xl font-bold font-merriweather mb-4 [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>Risk Assessment</h2>
          <p className={`mb-6 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
            Even strong charities can have red flags. We identify concerns and apply point deductions
            (up to -10 points total) when we find issues that could affect your donation{'\u2019'}s impact.
            Deductions are size-adjusted: emerging organizations (&lt;$1M) get lighter penalties for missing
            formal systems, while established organizations (&gt;$10M) are held to higher standards.
          </p>

          <div className={`rounded-2xl border p-8 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
            <div className="grid md:grid-cols-2 gap-8">
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <AlertTriangle className={`w-5 h-5 ${isDark ? 'text-rose-400' : 'text-rose-600'}`} aria-hidden="true" />
                  <h3 className={`font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>Red Flags We Check</h3>
                </div>
                <ul className={`text-sm space-y-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  <li className="flex items-start gap-2">
                    <span className={`px-1.5 py-0.5 rounded text-xs font-mono ${isDark ? 'bg-rose-900/30 text-rose-400' : 'bg-rose-100 text-rose-700'}`}>-5</span>
                    <span>Program ratio under 50% (most money not reaching programs)</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className={`px-1.5 py-0.5 rounded text-xs font-mono ${isDark ? 'bg-rose-900/30 text-rose-400' : 'bg-rose-100 text-rose-700'}`}>-5</span>
                    <span>Board under 3 members (governance concerns)</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className={`px-1.5 py-0.5 rounded text-xs font-mono ${isDark ? 'bg-amber-900/30 text-amber-400' : 'bg-amber-100 text-amber-700'}`}>-3</span>
                    <span>Charity Navigator advisory flag</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className={`px-1.5 py-0.5 rounded text-xs font-mono ${isDark ? 'bg-amber-900/30 text-amber-400' : 'bg-amber-100 text-amber-700'}`}>-2</span>
                    <span>Less than 1 month operating reserves</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className={`px-1.5 py-0.5 rounded text-xs font-mono ${isDark ? 'bg-amber-900/30 text-amber-400' : 'bg-amber-100 text-amber-700'}`}>-2</span>
                    <span>No outcome tracking (size-adjusted)</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className={`px-1.5 py-0.5 rounded text-xs font-mono ${isDark ? 'bg-slate-700 text-slate-400' : 'bg-slate-200 text-slate-600'}`}>-1</span>
                    <span>No theory of change documented (size-adjusted)</span>
                  </li>
                </ul>
              </div>

              <div>
                <div className="flex items-center gap-2 mb-4">
                  <CheckCircle2 className={`w-5 h-5 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />
                  <h3 className={`font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>What We DON{'\u2019'}T Penalize</h3>
                </div>
                <ul className={`text-sm space-y-3 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  <li className="flex items-start gap-2">
                    <XCircle className={`w-4 h-4 shrink-0 mt-0.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} aria-hidden="true" />
                    <span><strong>Conflict zone operations</strong> {'\u2014'} Higher costs in Gaza, Syria, Yemen are legitimate</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <XCircle className={`w-4 h-4 shrink-0 mt-0.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} aria-hidden="true" />
                    <span><strong>Newer organizations</strong> {'\u2014'} Less data doesn{'\u2019'}t mean worse; emerging orgs get lighter risk expectations</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <XCircle className={`w-4 h-4 shrink-0 mt-0.5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} aria-hidden="true" />
                    <span><strong>Non-Muslim-focused work</strong> {'\u2014'} We evaluate all charities fairly</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* How We Verify Our Work */}
        <section className="mb-20">
          <h2 className={`text-2xl font-bold font-merriweather mb-4 [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>How We Verify Our Work</h2>
          <p className={`mb-8 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
            We know trust must be earned. Here{'\u2019'}s what happens behind the scenes to make sure our evaluations are accurate and fair.
          </p>

          <div className="grid md:grid-cols-2 gap-6 mb-8">
            {/* Citations */}
            <div className={`rounded-xl border p-6 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center mb-4 ${isDark ? 'bg-blue-900/30 text-blue-400' : 'bg-blue-100 text-blue-600'}`}>
                <FileText className="w-5 h-5" aria-hidden="true" />
              </div>
              <h3 className={`font-bold mb-3 ${isDark ? 'text-white' : 'text-slate-900'}`}>Every Claim Has a Source</h3>
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                When we say a charity has a 92% program expense ratio, that number comes from their IRS Form 990.
                When we mention a Charity Navigator rating, that links to their actual profile. You can verify
                any factual claim we make by following the citation to the original source.
              </p>
            </div>

            {/* Conflict Resolution */}
            <div className={`rounded-xl border p-6 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center mb-4 ${isDark ? 'bg-amber-900/30 text-amber-400' : 'bg-amber-100 text-amber-600'}`}>
                <AlertTriangle className="w-5 h-5" aria-hidden="true" />
              </div>
              <h3 className={`font-bold mb-3 ${isDark ? 'text-white' : 'text-slate-900'}`}>When Sources Disagree</h3>
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                Sometimes Charity Navigator reports different revenue than the IRS filing. When this happens,
                we log the conflict and follow a clear priority: official IRS filings beat rating agency data,
                which beats self-reported information from charity websites. You see the winning value; we keep
                records of what was overridden.
              </p>
            </div>

            {/* Peer Comparison */}
            <div className={`rounded-xl border p-6 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center mb-4 ${isDark ? 'bg-emerald-900/30 text-emerald-400' : 'bg-emerald-100 text-emerald-600'}`}>
                <Users className="w-5 h-5" aria-hidden="true" />
              </div>
              <h3 className={`font-bold mb-3 ${isDark ? 'text-white' : 'text-slate-900'}`}>Apples to Apples</h3>
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                A legal advocacy organization has different cost structures than a food bank. We use cause-adjusted
                benchmarks {'\u2014'} different scales for food, education, healthcare, humanitarian, and other cause areas.
                This means a humanitarian relief org is compared against humanitarian benchmarks, not education benchmarks.
              </p>
            </div>

            {/* Case Against */}
            <div className={`rounded-xl border p-6 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center mb-4 ${isDark ? 'bg-rose-900/30 text-rose-400' : 'bg-rose-100 text-rose-600'}`}>
                <XCircle className="w-5 h-5" aria-hidden="true" />
              </div>
              <h3 className={`font-bold mb-3 ${isDark ? 'text-white' : 'text-slate-900'}`}>The {'\u201C'}Case Against{'\u201D'}</h3>
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                Every evaluation {'\u2014'} even for our highest-rated charities {'\u2014'} includes a section documenting limitations
                and concerns. This isn{'\u2019'}t about being negative; it{'\u2019'}s about being honest. If a charity lacks rigorous
                impact studies, we say so. If there{'\u2019'}s a governance concern, we flag it. You deserve the full picture.
              </p>
            </div>
          </div>

          {/* Conflict Zone Note */}
          <div className={`rounded-xl p-6 ${isDark ? 'bg-slate-800 border border-slate-700' : 'bg-slate-100 border border-slate-200'}`}>
            <div className="flex items-start gap-3">
              <ShieldCheck className={`w-5 h-5 shrink-0 mt-0.5 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />
              <div>
                <h4 className={`font-bold mb-1 ${isDark ? 'text-white' : 'text-slate-900'}`}>Special Consideration: Conflict Zones</h4>
                <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  Charities operating in active conflict zones (Gaza, Syria, Yemen, Sudan, Afghanistan, Somalia, Ukraine)
                  face legitimately higher costs {'\u2014'} security, logistics, and staff safety all cost more in war zones.
                  Our cause-adjusted benchmarks for humanitarian work account for this context rather than penalizing
                  organizations for circumstances beyond their control.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* See It In Action */}
        <section className="mb-20">
          <h2 className={`text-2xl font-bold font-merriweather mb-4 [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>See It In Action</h2>
          <p className={`mb-6 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
            We{'\u2019'}ve evaluated {summaries.filter(s => s.amalScore).length} charities using this framework.
            Here{'\u2019'}s what the data reveals.
          </p>

          {/* Score Summary — aligned with scoreConstants.ts thresholds */}
          <div className={`grid grid-cols-2 md:grid-cols-4 gap-4 mb-8 p-4 rounded-xl ${isDark ? 'bg-slate-800/50' : 'bg-slate-100'}`}>
            <div className="text-center">
              <div className={`text-2xl font-bold tabular-nums ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>{scoreBuckets.exceptional}</div>
              <div className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>75+ Exceptional</div>
            </div>
            <div className="text-center">
              <div className={`text-2xl font-bold tabular-nums ${isDark ? 'text-blue-400' : 'text-blue-600'}`}>{scoreBuckets.good}</div>
              <div className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>60-74 Good</div>
            </div>
            <div className="text-center">
              <div className={`text-2xl font-bold tabular-nums ${isDark ? 'text-amber-400' : 'text-amber-600'}`}>{scoreBuckets.developing}</div>
              <div className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>30-59 Developing</div>
            </div>
            <div className="text-center">
              <div className={`text-2xl font-bold tabular-nums ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{scoreBuckets.emerging}</div>
              <div className={`text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>&lt;30 Emerging</div>
            </div>
          </div>

          {/* Calibration Snapshot */}
          {calibrationReport && (
            <div className={`rounded-xl border p-4 mb-8 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
              <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                <h3 className={`font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>Calibration Snapshot</h3>
                <p className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                  {new Date(calibrationReport.metadata.generated_at).toLocaleDateString()} · config {calibrationReport.metadata.config_version}
                </p>
              </div>
              {calibrationReport.warnings.length > 0 && (
                <div className={`mb-3 rounded-lg border p-3 ${isDark ? 'bg-amber-900/20 border-amber-800/40 text-amber-300' : 'bg-amber-50 border-amber-200 text-amber-800'}`}>
                  <p className="text-xs font-semibold mb-1">Calibration warnings</p>
                  <ul className="text-xs space-y-1">
                    {calibrationReport.warnings.map((warning, idx) => (
                      <li key={idx}>• {warning}</li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div>
                  <p className={`text-[11px] uppercase tracking-wider ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>Fallback</p>
                  <p className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>{calibrationReport.fallback.rate_pct}%</p>
                </div>
                <div>
                  <p className={`text-[11px] uppercase tracking-wider ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>Near Threshold</p>
                  <p className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>{calibrationReport.near_threshold.rate_pct}%</p>
                </div>
                <div>
                  <p className={`text-[11px] uppercase tracking-wider ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>Top Cue</p>
                  <p className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    {CUE_DISPLAY_LABELS[Object.entries(calibrationReport.distributions.recommendation_cue).sort((a, b) => b[1] - a[1])[0]?.[0] || ''] || '—'}
                  </p>
                </div>
                <div>
                  <p className={`text-[11px] uppercase tracking-wider ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>Top Stage</p>
                  <p className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    {getEvidenceStageLabel(Object.entries(calibrationReport.distributions.evidence_stage).sort((a, b) => b[1] - a[1])[0]?.[0] || '') || '—'}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Insights Visualization */}
          {loading ? (
            <div className={`rounded-2xl border p-8 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
              <div className={`h-64 rounded-lg animate-pulse ${isDark ? 'bg-slate-800' : 'bg-slate-100'}`} />
            </div>
          ) : (
            <div className="space-y-8">
              {/* Cause Area Matrix - 2x2 with drill-down */}
              <CauseAreaMatrix charities={insightsData} />

              {/* Narrative Insights */}
              <MethodologyInsights charities={insightsData} />
            </div>
          )}
        </section>

        {/* Wallet Routing */}
        <section className="mb-20">
          <h2 className={`text-2xl font-bold font-merriweather mb-4 [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>Zakat Classification</h2>
          <p className={`mb-8 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
            Beyond the score, we help you decide if a charity accepts Zakat. This is a binary classification
            based on what the charity claims on its website, not a quality judgment {'\u2014'} a Sadaqah-only charity can still have an excellent score.
          </p>

          <div className="grid md:grid-cols-2 gap-6">
            <div className={`rounded-xl border-2 p-6 ${isDark ? 'bg-slate-900 border-emerald-800' : 'bg-white border-emerald-200'}`}>
              <div className="flex items-center gap-3 mb-4">
                <Lock className={`w-5 h-5 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />
                <h3 className={`font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>Zakat Eligible</h3>
              </div>
              <p className={`text-sm mb-4 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                The charity explicitly claims to accept Zakat donations on their website.
                They typically serve Zakat-eligible beneficiaries (poor, needy, refugees, debt relief)
                and may have fund segregation policies.
              </p>
              <div className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                <strong>How we detect:</strong> We scan the charity{'\u2019'}s website for explicit Zakat acceptance claims
              </div>
            </div>

            <div className={`rounded-xl border-2 p-6 ${isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'}`}>
              <div className="flex items-center gap-3 mb-4">
                <Users className={`w-5 h-5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`} aria-hidden="true" />
                <h3 className={`font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>Sadaqah</h3>
              </div>
              <p className={`text-sm mb-4 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                The charity does not explicitly claim to accept Zakat on their website.
                These charities are suitable for general Sadaqah donations but may or may not
                serve Zakat-eligible beneficiaries.
              </p>
              <div className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                <strong>Note:</strong> Some charities may accept Zakat but not advertise it
              </div>
            </div>
          </div>

          {/* Eight Asnaf Categories */}
          <div className={`rounded-xl border p-6 mt-6 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
            <h3 className={`font-bold mb-4 ${isDark ? 'text-white' : 'text-slate-900'}`}>The Eight Zakat Categories (Asnaf)</h3>
            <p className={`text-sm mb-4 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              When a charity claims zakat eligibility, we note which Quranic categories (9:60) their work serves:
            </p>
            <div className="grid md:grid-cols-2 gap-x-6 gap-y-2">
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}><strong>1. Al-Fuqara</strong> {'\u2014'} The poor (below nisab)</p>
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}><strong>2. Al-Masakin</strong> {'\u2014'} The destitute</p>
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}><strong>3. Al-Amileen</strong> {'\u2014'} Zakat administrators</p>
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}><strong>4. Al-Muallafatul Quloob</strong> {'\u2014'} New Muslims</p>
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}><strong>5. Ar-Riqab</strong> {'\u2014'} Freeing captives (refugees, trafficking victims)</p>
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}><strong>6. Al-Gharimeen</strong> {'\u2014'} Those in debt</p>
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}><strong>7. Fi Sabilillah</strong> {'\u2014'} In Allah{'\u2019'}s path (education, humanitarian, dawah)</p>
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}><strong>8. Ibnus-Sabil</strong> {'\u2014'} Stranded travelers (displaced persons)</p>
            </div>
          </div>

          <div className={`rounded-xl p-6 mt-6 ${isDark ? 'bg-amber-900/20 border border-amber-800/30' : 'bg-amber-50 border border-amber-200'}`}>
            <p className={`text-sm ${isDark ? 'text-amber-200/80' : 'text-amber-800'}`}>
              <strong>Important:</strong> Our Zakat classifications are informational only
              and do not constitute religious rulings. They are based on what charities claim
              on their own websites. Please consult a qualified scholar for definitive guidance
              on your specific situation.
            </p>
          </div>
        </section>

        {/* Data Sources */}
        <section className="mb-20">
          <h2 className={`text-2xl font-bold font-merriweather mb-4 [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>Our Data Sources</h2>
          <p className={`mb-8 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
            We aggregate data from multiple trusted sources and reconcile conflicts automatically.
            When sources disagree, we favor official filings and verified data.
          </p>

          <div className={`rounded-2xl border overflow-hidden ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
            <div className={`grid md:grid-cols-2 divide-y md:divide-y-0 md:divide-x ${isDark ? 'divide-slate-800' : 'divide-slate-200'}`}>
              <div className="p-6">
                <h3 className={`font-bold mb-4 ${isDark ? 'text-white' : 'text-slate-900'}`}>Data Sources</h3>
                <ul className={`space-y-3 text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className={`w-4 h-4 shrink-0 mt-0.5 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />
                    <span><strong>IRS Form 990</strong> {'\u2014'} Official financial filings (via ProPublica API)</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className={`w-4 h-4 shrink-0 mt-0.5 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />
                    <span><strong>Charity Navigator</strong> {'\u2014'} Ratings, financial health, accountability scores</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className={`w-4 h-4 shrink-0 mt-0.5 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />
                    <span><strong>Candid (GuideStar)</strong> {'\u2014'} Transparency seals, outcome tracking data</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className={`w-4 h-4 shrink-0 mt-0.5 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />
                    <span><strong>BBB Wise Giving Alliance</strong> {'\u2014'} Governance standards</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className={`w-4 h-4 shrink-0 mt-0.5 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />
                    <span><strong>Charity Websites</strong> {'\u2014'} Programs, mission, Zakat policies</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className={`w-4 h-4 shrink-0 mt-0.5 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />
                    <span><strong>Web Search</strong> {'\u2014'} Zakat claims, third-party evaluations, awards discovered across the web</span>
                  </li>
                </ul>

                <h4 className={`font-bold mt-6 mb-3 ${isDark ? 'text-white' : 'text-slate-900'}`}>Cost Benchmarks</h4>
                <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  We use cause-adjusted benchmarks informed by evidence-based giving research to compare
                  cost-effectiveness across different types of charities (food, healthcare, education, etc.)
                </p>
              </div>
              <div className="p-6">
                <h3 className={`font-bold mb-4 ${isDark ? 'text-white' : 'text-slate-900'}`}>What We Extract</h3>
                <ul className={`space-y-3 text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className={`w-4 h-4 shrink-0 mt-0.5 ${isDark ? 'text-blue-400' : 'text-blue-600'}`} aria-hidden="true" />
                    <span>Revenue, expenses, program expense ratios</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className={`w-4 h-4 shrink-0 mt-0.5 ${isDark ? 'text-blue-400' : 'text-blue-600'}`} aria-hidden="true" />
                    <span>Board size, working capital ratios</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className={`w-4 h-4 shrink-0 mt-0.5 ${isDark ? 'text-blue-400' : 'text-blue-600'}`} aria-hidden="true" />
                    <span>Outcome measurement and years of tracking</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className={`w-4 h-4 shrink-0 mt-0.5 ${isDark ? 'text-blue-400' : 'text-blue-600'}`} aria-hidden="true" />
                    <span>Zakat claims from charity websites</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className={`w-4 h-4 shrink-0 mt-0.5 ${isDark ? 'text-blue-400' : 'text-blue-600'}`} aria-hidden="true" />
                    <span>Third-party ratings and transparency seals</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className={`w-4 h-4 shrink-0 mt-0.5 ${isDark ? 'text-blue-400' : 'text-blue-600'}`} aria-hidden="true" />
                    <span>Theory of change and program descriptions</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* Human + AI */}
        <section className="mb-20">
          <h2 className={`text-2xl font-bold font-merriweather mb-4 [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>How We Use AI</h2>
          <p className={`mb-4 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
            We use AI to process large amounts of data consistently. The AI extracts
            and structures data from websites, PDFs, and filings. The scoring itself uses deterministic
            code {'\u2014'} the AI never decides point values or makes scoring judgments.
          </p>
          <p className={`mb-8 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
            We{'\u2019'}re transparent about this because we believe it produces more scalable and consistent analysis.
          </p>

          <div className="grid md:grid-cols-2 gap-6 mb-8">
            <div className={`rounded-xl border p-6 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center mb-4 ${isDark ? 'bg-purple-900/30 text-purple-400' : 'bg-purple-100 text-purple-600'}`}>
                <Brain className="w-5 h-5" aria-hidden="true" />
              </div>
              <h3 className={`font-bold mb-3 ${isDark ? 'text-white' : 'text-slate-900'}`}>What AI Does</h3>
              <ul className={`text-sm space-y-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                <li>{'\u2022'} Extracts structured data from Form 990s and charity websites</li>
                <li>{'\u2022'} Parses rating agency pages (CN, Candid, BBB)</li>
                <li>{'\u2022'} Detects Zakat claims on charity websites</li>
                <li>{'\u2022'} Generates narrative summaries citing specific sources</li>
                <li>{'\u2022'} Searches for theory of change documents</li>
              </ul>
            </div>

            <div className={`rounded-xl border p-6 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center mb-4 ${isDark ? 'bg-blue-900/30 text-blue-400' : 'bg-blue-100 text-blue-600'}`}>
                <Database className="w-5 h-5" aria-hidden="true" />
              </div>
              <h3 className={`font-bold mb-3 ${isDark ? 'text-white' : 'text-slate-900'}`}>What Code Does (Not AI)</h3>
              <ul className={`text-sm space-y-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                <li>{'\u2022'} <strong>All scoring math</strong> {'\u2014'} deterministic Python functions</li>
                <li>{'\u2022'} <strong>Wallet tag assignment</strong> {'\u2014'} rule-based on Zakat claims</li>
                <li>{'\u2022'} <strong>Risk deductions</strong> {'\u2014'} formula-based on red flags</li>
                <li>{'\u2022'} <strong>Tier classification</strong> {'\u2014'} threshold-based scoring</li>
              </ul>
            </div>
          </div>

          {/* Quality Controls */}
          <div className={`rounded-2xl border p-8 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
            <div className="flex items-center gap-2 mb-4">
              <Eye className={`w-5 h-5 ${isDark ? 'text-blue-400' : 'text-blue-600'}`} aria-hidden="true" />
              <h3 className={`font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>Quality Controls</h3>
            </div>
            <div className="grid md:grid-cols-2 gap-6">
              <ul className={`text-sm space-y-3 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className={`w-4 h-4 shrink-0 mt-0.5 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                  <span><strong>Cited sources</strong> {'\u2014'} every claim references specific data</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className={`w-4 h-4 shrink-0 mt-0.5 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                  <span><strong>Reproducible scores</strong> {'\u2014'} same data = same score every time</span>
                </li>
              </ul>
              <ul className={`text-sm space-y-3 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className={`w-4 h-4 shrink-0 mt-0.5 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                  <span><strong>Community feedback</strong> {'\u2014'} report errors and we{'\u2019'}ll investigate</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className={`w-4 h-4 shrink-0 mt-0.5 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                  <span><strong>Open methodology</strong> {'\u2014'} our scoring rubric is documented</span>
                </li>
              </ul>
            </div>

            <div className={`rounded-xl p-4 mt-6 ${isDark ? 'bg-amber-900/20 border border-amber-800/30' : 'bg-amber-50 border border-amber-200'}`}>
              <p className={`text-sm ${isDark ? 'text-amber-200/80' : 'text-amber-800'}`}>
                <strong>Limitation:</strong> This is an automated system. AI can misinterpret website content or miss
                information that requires human context. We do not manually review every evaluation before publishing.
                If you notice an error in a charity{'\u2019'}s evaluation, please let us know and we{'\u2019'}ll investigate.
              </p>
            </div>
          </div>

          {/* AI Prompts Link */}
          <div className={`rounded-xl p-6 mt-6 ${isDark ? 'bg-emerald-900/20 border border-emerald-800/30' : 'bg-emerald-50 border border-emerald-200'}`}>
            <div className="flex items-start gap-3">
              <Target className={`w-5 h-5 shrink-0 mt-0.5 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} aria-hidden="true" />
              <div>
                <h4 className={`font-bold mb-1 ${isDark ? 'text-white' : 'text-slate-900'}`}>Full Transparency: View Our AI Prompts</h4>
                <p className={`text-sm mb-3 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  We publish every prompt we use {'\u2014'} from data extraction to narrative generation to quality validation.
                  See exactly what instructions we give to AI models and how we prevent hallucinations.
                </p>
                <Link
                  to="/prompts"
                  className={`inline-flex items-center gap-2 text-sm font-medium ${isDark ? 'text-emerald-400 hover:text-emerald-300' : 'text-emerald-600 hover:text-emerald-700'}`}
                >
                  View all prompts
                  <ArrowRight className="w-4 h-4" aria-hidden="true" />
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* What We Don't Do */}
        <section className="mb-20">
          <h2 className={`text-2xl font-bold font-merriweather mb-4 [text-wrap:balance] ${isDark ? 'text-white' : 'text-slate-900'}`}>What We Don{'\u2019'}t Do</h2>

          <div className={`rounded-xl p-6 space-y-4 ${isDark ? 'bg-slate-800' : 'bg-slate-100'}`}>
            <div className="flex items-start gap-3">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${isDark ? 'bg-slate-700 text-slate-400' : 'bg-white text-slate-400'}`}>
                <span className="text-sm">{'\u2715'}</span>
              </div>
              <p className={isDark ? 'text-slate-300' : 'text-slate-700'}>
                <strong>We don{'\u2019'}t penalize conflict-zone charities unfairly.</strong> Operating in places
                like Gaza or Syria costs more due to security and logistics. We account for this.
              </p>
            </div>
            <div className="flex items-start gap-3">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${isDark ? 'bg-slate-700 text-slate-400' : 'bg-white text-slate-400'}`}>
                <span className="text-sm">{'\u2715'}</span>
              </div>
              <p className={isDark ? 'text-slate-300' : 'text-slate-700'}>
                <strong>We don{'\u2019'}t issue religious rulings.</strong> Our Zakat classifications are
                informational. Consult a scholar for your specific situation.
              </p>
            </div>
            <div className="flex items-start gap-3">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${isDark ? 'bg-slate-700 text-slate-400' : 'bg-white text-slate-400'}`}>
                <span className="text-sm">{'\u2715'}</span>
              </div>
              <p className={isDark ? 'text-slate-300' : 'text-slate-700'}>
                <strong>We don{'\u2019'}t take money from charities we rate.</strong> Our evaluations are
                independent. We{'\u2019'}re funded by donors who share our mission.
              </p>
            </div>
            <div className="flex items-start gap-3">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${isDark ? 'bg-slate-700 text-slate-400' : 'bg-white text-slate-400'}`}>
                <span className="text-sm">{'\u2715'}</span>
              </div>
              <p className={isDark ? 'text-slate-300' : 'text-slate-700'}>
                <strong>We don{'\u2019'}t manually review every evaluation.</strong> This is an automated system
                that prioritizes consistency and citation. We verify through sources, not human judgment {'\u2014'}
                which means we may miss nuance that a human expert would catch.
              </p>
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="text-center">
          <div className="bg-slate-900 rounded-2xl p-10">
            <h2 className="text-2xl font-bold text-white font-merriweather mb-4 [text-wrap:balance]">
              Ready to explore?
            </h2>
            <p className="text-slate-400 mb-8 max-w-lg mx-auto">
              Browse our directory of evaluated charities and find organizations
              that match your giving goals.
            </p>
            <Link
              to="/browse"
              className="inline-flex items-center gap-2 px-6 py-3 bg-emerald-600 text-white rounded-lg font-bold hover:bg-emerald-700 transition-colors"
            >
              Browse Charities
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </section>

      </div>
    </div>
  );
};
