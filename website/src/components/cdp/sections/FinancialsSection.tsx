/**
 * FinancialsSection (CDP single-scroll): id="financials".
 * Lifted verbatim from TabbedView's renderFinancialsTab:
 *   - Financial Overview: annual revenue + NEW_ORG "Pre-990" + form990Exempt
 *     branch; rich-only rows (expenses, net assets, working capital, assets,
 *     liabilities) with a PARTIAL gate — anonymous users still see revenue but
 *     get a sign-in CTA for the rest.
 *   - Expense Breakdown: programs/admin/fundraising stacked bar + rows.
 *   - Financial History (3-year): yearly revenue, 3yr CAGR, reserves.
 *   - Grantmaking: total grants, domestic/international, recipients, regions.
 * Expense/history/grantmaking blocks are rich-gated with anonymous ContentPreview
 * fallbacks.
 */
import React from 'react';
import { BarChart3, Rocket, Lock, TrendingUp, Landmark } from 'lucide-react';
import { useLandingTheme } from '../../../../contexts/LandingThemeContext';
import { GLOSSARY } from '../../../data/glossary';
import { SignInButton } from '../../../auth/SignInButton';
import { ContentPreview } from '../../ContentPreview';
import type { CdpData } from '../useCdpData';
import { SectionCard, SectionHeader, DataRow, formatCurrency } from './_primitives';

export const FinancialsSection: React.FC<{ data: CdpData }> = ({ data }) => {
  const { isDark } = useLandingTheme();
  const {
    charity, canViewRich, rich, financials, revenue,
    hasExpenseData, programRatio, adminRatio, fundRatio,
    hasSignificantNoncash, cashAdjProgramRatio,
  } = data;

  return (
    <section id="financials">
      <div className="space-y-5">
        {/* Financial Overview */}
        <SectionCard isDark={isDark}>
          <SectionHeader icon={BarChart3} title="Financial Overview" isDark={isDark} />
          {revenue != null ? (
            <div className={`mb-4 pb-3 border-b ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
              <div className={`text-3xl font-mono font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                {formatCurrency(revenue)}
              </div>
              <div className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Annual Revenue</div>
            </div>
          ) : charity.evaluationTrack === 'NEW_ORG' ? (
            <div className={`mb-4 pb-3 border-b ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
              <div className={`flex items-center gap-2 ${isDark ? 'text-sky-400' : 'text-sky-600'}`}>
                <Rocket className="w-5 h-5" />
                <span className="text-lg font-semibold">Pre-990</span>
              </div>
              <div className={`text-xs mt-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                New org -- First 990 filing pending
              </div>
            </div>
          ) : null}

          {!!charity.form990Exempt && !revenue && (
            <div className={`mb-4 p-3 rounded-lg text-sm ${isDark ? 'bg-slate-800 text-slate-300' : 'bg-amber-50 text-amber-800'}`}>
              <div className="font-medium mb-1">Form 990 Exempt</div>
              <div className={`text-xs ${isDark ? 'text-slate-400' : 'text-amber-700'}`}>
                {charity.form990ExemptReason || 'Religious organization'} -- not required to file public financial disclosures.
              </div>
            </div>
          )}

          <div className="space-y-0">
            {canViewRich ? (
              <>
                {financials?.totalExpenses != null && (
                  <DataRow label="Total Expenses" value={formatCurrency(financials.totalExpenses)} isDark={isDark} />
                )}
                {financials?.netAssets != null && (
                  <DataRow label="Net Assets" value={formatCurrency(financials.netAssets)} isDark={isDark} />
                )}
                {financials?.workingCapitalMonths != null && (
                  <DataRow label="Working Capital" value={`${Number(financials.workingCapitalMonths).toFixed(1)} months`} isDark={isDark} />
                )}
                {financials?.totalAssets != null && (
                  <DataRow label="Total Assets" value={formatCurrency(financials.totalAssets)} isDark={isDark} />
                )}
                {financials?.totalLiabilities != null && (
                  <DataRow label="Total Liabilities" value={formatCurrency(financials.totalLiabilities)} isDark={isDark} />
                )}
              </>
            ) : (
              <SignInButton
                variant="custom"
                className={`text-sm flex items-center gap-2 cursor-pointer hover:opacity-80 transition-opacity ${
                  isDark ? 'text-emerald-400' : 'text-emerald-600'
                }`}
              >
                <Lock className="w-3.5 h-3.5 flex-shrink-0" />
                <span>
                  <span className="underline font-medium">Sign in</span>
                  {' '}to see expenses, assets, and working capital
                </span>
              </SignInButton>
            )}
          </div>
        </SectionCard>

        {/* Expense Breakdown */}
        {hasExpenseData && (
          canViewRich ? (
          <SectionCard isDark={isDark}>
            <SectionHeader icon={BarChart3} title="Expense Breakdown" isDark={isDark} />
            <div className={`h-3 rounded-full overflow-hidden flex mb-4 ${isDark ? 'bg-slate-700' : 'bg-slate-200'}`}>
              <div className="bg-emerald-500 transition-all" style={{ width: `${programRatio}%` }} />
              <div className={`${isDark ? 'bg-slate-500' : 'bg-slate-400'} transition-all`} style={{ width: `${adminRatio}%` }} />
              <div className="bg-amber-500 transition-all" style={{ width: `${fundRatio}%` }} />
            </div>
            <div className={`space-y-2 text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-emerald-500" />
                  Programs
                </span>
                <span className="font-mono">
                  {formatCurrency(financials?.programExpenses)}
                  {hasSignificantNoncash && cashAdjProgramRatio != null ? (
                    <>
                      <span className={`ml-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>({cashAdjProgramRatio.toFixed(0)}% cash-adjusted)</span>
                      <span className={`ml-1 text-xs ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>({programRatio.toFixed(0)}% reported)</span>
                    </>
                  ) : (
                    <>
                      <span className={`ml-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>({programRatio.toFixed(0)}%)</span>
                      {financials?.cashAdjustedProgramRatio != null && (
                        <span className={`ml-1 text-xs ${isDark ? 'text-amber-400' : 'text-amber-600'}`}>
                          ({(financials.cashAdjustedProgramRatio * 100).toFixed(0)}% cash-adj)
                        </span>
                      )}
                    </>
                  )}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <span className={`w-3 h-3 rounded-full ${isDark ? 'bg-slate-500' : 'bg-slate-400'}`} />
                  Admin
                </span>
                <span className="font-mono">
                  {formatCurrency(financials?.adminExpenses)}
                  <span className={`ml-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>({adminRatio.toFixed(0)}%)</span>
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-amber-500" />
                  Fundraising
                </span>
                <span className="font-mono">
                  {formatCurrency(financials?.fundraisingExpenses)}
                  <span className={`ml-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>({fundRatio.toFixed(0)}%)</span>
                </span>
              </div>
            </div>
          </SectionCard>
          ) : (
            <ContentPreview title="Expense Breakdown" description="program, admin, and fundraising ratios" valueProps={['Program expense ratio', 'Admin and fundraising costs', 'Visual ratio comparison']} />
          )
        )}

        {/* Financial History (3-year) */}
        {rich?.financial_deep_dive?.yearly_financials && rich.financial_deep_dive.yearly_financials.length > 0 && (
          canViewRich ? (
            <SectionCard isDark={isDark}>
              <SectionHeader icon={TrendingUp} title="Financial History" isDark={isDark} />
              <div className="space-y-2 text-sm">
                {rich.financial_deep_dive.yearly_financials.map((year) => (
                  <div key={year.year} className="flex justify-between items-center">
                    <span className={`font-mono ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{year.year}</span>
                    <span className={`font-mono font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>
                      {formatCurrency(year.revenue)}
                    </span>
                  </div>
                ))}
              </div>
              {rich.financial_deep_dive.revenue_cagr_3yr && (
                <div className={`mt-3 pt-3 border-t flex justify-between items-center ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                  <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>3yr CAGR</span>
                  <span className={`text-sm font-mono font-semibold ${
                    rich.financial_deep_dive.revenue_cagr_3yr > 0
                      ? isDark ? 'text-emerald-400' : 'text-emerald-600'
                      : isDark ? 'text-red-400' : 'text-red-600'
                  }`}>
                    {rich.financial_deep_dive.revenue_cagr_3yr > 0 ? '↑' : '↓'} {Math.abs(rich.financial_deep_dive.revenue_cagr_3yr).toFixed(1)}%
                  </span>
                </div>
              )}
              {rich.financial_deep_dive.reserves_months && (
                <div className="flex justify-between items-center mt-1">
                  <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Reserves</span>
                  <span className={`text-sm font-mono ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                    {rich.financial_deep_dive.reserves_months.toFixed(1)} mo
                  </span>
                </div>
              )}
            </SectionCard>
          ) : (
            <ContentPreview title="3-Year Financials" description="three years of financial data" valueProps={['Year-over-year revenue trends', 'Expense breakdown over time', 'Revenue growth rate (CAGR)']} />
          )
        )}

        {/* Grantmaking */}
        {rich?.grantmaking_profile && rich.grantmaking_profile.is_significant_grantmaker && (
          canViewRich ? (
            <SectionCard isDark={isDark}>
              <SectionHeader icon={Landmark} title="Grantmaking" isDark={isDark} infoTip={GLOSSARY['Grantmaking']} />
              {rich.grantmaking_profile.total_grants && (
                <div className={`mb-3 pb-2 border-b ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                  <div className={`text-2xl font-mono font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    {formatCurrency(rich.grantmaking_profile.total_grants)}
                  </div>
                  <div className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                    Total Grants ({rich.grantmaking_profile.grant_count || 0} recipients)
                  </div>
                </div>
              )}
              <div className={`space-y-1 text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                {rich.grantmaking_profile.domestic_grants !== undefined && (
                  <div className="flex justify-between">
                    <span>Domestic</span>
                    <span className="font-mono">{formatCurrency(rich.grantmaking_profile.domestic_grants)}</span>
                  </div>
                )}
                {rich.grantmaking_profile.foreign_grants !== undefined && (
                  <div className="flex justify-between">
                    <span>International</span>
                    <span className="font-mono">{formatCurrency(rich.grantmaking_profile.foreign_grants)}</span>
                  </div>
                )}
              </div>
              {rich.grantmaking_profile.top_recipients && rich.grantmaking_profile.top_recipients.length > 0 && (
                <div className={`mt-3 pt-2 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                  <div className={`text-xs font-semibold mb-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Top Recipients</div>
                  <ul className={`text-xs space-y-0.5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                    {rich.grantmaking_profile.top_recipients.slice(0, 3).map((r, i) => (
                      <li key={i}>- {r}</li>
                    ))}
                  </ul>
                </div>
              )}
              {rich.grantmaking_profile.regions_served && rich.grantmaking_profile.regions_served.length > 0 && (
                <div className={`mt-2 pt-2 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                  <div className="flex flex-wrap gap-1">
                    {rich.grantmaking_profile.regions_served.slice(0, 4).map((region, i) => (
                      <span key={i} className={`px-1.5 py-0.5 rounded text-xs ${isDark ? 'bg-slate-700 text-slate-300' : 'bg-slate-200 text-slate-600'}`}>
                        {region}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </SectionCard>
          ) : (
            <ContentPreview title="Grantmaking" description="grantmaking profile and distribution data" valueProps={['Grant distribution and recipients', 'Grantmaking as % of expenses', 'Geographic and programmatic focus']} />
          )
        )}
      </div>
    </section>
  );
};
