/**
 * LeadershipSection (CDP single-scroll): id="leadership".
 * Lifted verbatim from TabbedView Overview tab:
 * Leadership & Governance (rich, with baselineGovernance fallback) + Long-Term Outlook.
 * Preserves rich/anon gating.
 */
import React from 'react';
import { Users, TrendingUp, CheckCircle2, AlertCircle } from 'lucide-react';
import { useLandingTheme } from '../../../../contexts/LandingThemeContext';
import { ContentPreview } from '../../ContentPreview';
import { GLOSSARY } from '../../../data/glossary';
import type { CdpData } from '../useCdpData';
import { SectionCard, SectionHeader, DataRow, formatCurrency } from './_primitives';

export const LeadershipSection: React.FC<{ data: CdpData }> = ({ data }) => {
  const { isDark } = useLandingTheme();
  const { charity, canViewRich, rich } = data;

  return (
    <section id="leadership" className="space-y-5">
      {/* Leadership & Governance */}
      {rich?.organizational_capacity && (
        canViewRich ? (
          <SectionCard isDark={isDark}>
            <SectionHeader icon={Users} title="Leadership & Governance" isDark={isDark} />
            {rich.organizational_capacity.ceo_name && (
              <div className={`mb-3 pb-3 border-b ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                <div className={`text-sm font-medium ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  {rich.organizational_capacity.ceo_name}
                </div>
                <div className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                  CEO/Executive Director
                  {!!rich.organizational_capacity.ceo_compensation && (
                    <span className="ml-2 font-mono">({formatCurrency(rich.organizational_capacity.ceo_compensation)})</span>
                  )}
                </div>
              </div>
            )}
            <div className={`space-y-1.5 text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              {!!rich.organizational_capacity.board_size && (
                <div className="flex justify-between">
                  <span>Board Size</span>
                  <span className="font-mono">{rich.organizational_capacity.board_size}</span>
                </div>
              )}
              {rich.organizational_capacity.independent_board_pct != null && (
                <div className="flex justify-between">
                  <span>Independent</span>
                  <span className="font-mono">{(rich.organizational_capacity.independent_board_pct * 100).toFixed(0)}%</span>
                </div>
              )}
              {!!rich.organizational_capacity.employees_count && (
                <div className="flex justify-between">
                  <span>Employees</span>
                  <span className="font-mono">{rich.organizational_capacity.employees_count}</span>
                </div>
              )}
              {rich.organizational_capacity.volunteers_count != null && rich.organizational_capacity.volunteers_count > 0 && (
                <div className="flex justify-between">
                  <span>Volunteers</span>
                  <span className="font-mono">{rich.organizational_capacity.volunteers_count}</span>
                </div>
              )}
            </div>
            <div className={`mt-3 pt-3 border-t grid grid-cols-2 gap-2 text-sm ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
              <div className="flex items-center gap-1.5">
                {rich.organizational_capacity.has_conflict_policy ? (
                  <CheckCircle2 className={`w-4 h-4 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                ) : (
                  <AlertCircle className={`w-4 h-4 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} />
                )}
                <span className={isDark ? 'text-slate-400' : 'text-slate-600'}>COI Policy</span>
              </div>
              <div className="flex items-center gap-1.5">
                {rich.organizational_capacity.has_financial_audit ? (
                  <CheckCircle2 className={`w-4 h-4 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                ) : (
                  <AlertCircle className={`w-4 h-4 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} />
                )}
                <span className={isDark ? 'text-slate-400' : 'text-slate-600'}>Audited</span>
              </div>
            </div>
          </SectionCard>
        ) : (
          <ContentPreview title="Leadership & Governance" description="leadership and governance details" valueProps={['CEO name and compensation', 'Board size and independence', 'Financial audit and conflict policy']} />
        )
      )}

      {/* Baseline Governance fallback */}
      {!rich?.organizational_capacity && charity.baselineGovernance && (
        canViewRich ? (
          <SectionCard isDark={isDark}>
            <SectionHeader icon={Users} title="Governance" isDark={isDark} />
            <div className={`space-y-1.5 text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              {!!charity.baselineGovernance.boardSize && (
                <div className="flex justify-between">
                  <span className={isDark ? 'text-slate-400' : 'text-slate-500'}>Board Size</span>
                  <span className="font-mono">{charity.baselineGovernance.boardSize}</span>
                </div>
              )}
              {!!charity.baselineGovernance.independentBoardMembers && (
                <div className="flex justify-between">
                  <span className={isDark ? 'text-slate-400' : 'text-slate-500'}>Independent Members</span>
                  <span className="font-mono">{charity.baselineGovernance.independentBoardMembers}</span>
                </div>
              )}
              {!!charity.baselineGovernance.ceoCompensation && (
                <div className="flex justify-between">
                  <span className={isDark ? 'text-slate-400' : 'text-slate-500'}>CEO Compensation</span>
                  <span className="font-mono">{formatCurrency(charity.baselineGovernance.ceoCompensation)}</span>
                </div>
              )}
            </div>
          </SectionCard>
        ) : (
          <ContentPreview title="Governance" description="governance and leadership details" valueProps={['Board size and independence', 'CEO compensation', 'Organizational oversight']} />
        )
      )}

      {/* Long-Term Outlook */}
      {rich?.long_term_outlook && (
        canViewRich ? (
          <SectionCard isDark={isDark}>
            <SectionHeader icon={TrendingUp} title="Long-Term Outlook" isDark={isDark} infoTip={GLOSSARY['Long-Term Outlook']} />
            <DataRow label="Years Operating" value={rich.long_term_outlook.years_operating} isDark={isDark} />
            <DataRow label="Maturity" value={rich.long_term_outlook.maturity_stage} isDark={isDark} mono={false} />
            <DataRow label="Room for Funding" value={rich.long_term_outlook.room_for_funding} isDark={isDark} />
            {(rich.long_term_outlook.strategic_priorities?.length ?? 0) > 0 && (
              <div className={`mt-3 pt-3 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                <div className={`text-xs font-semibold mb-1.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  Strategic Priorities
                </div>
                <ul className={`text-sm space-y-0.5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  {rich.long_term_outlook.strategic_priorities?.slice(0, 3).map((priority, i) => (
                    <li key={i} className="flex items-start gap-1">
                      <span className="text-emerald-500">-</span>
                      {priority}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </SectionCard>
        ) : (
          <ContentPreview title="Long-Term Outlook" description="sustainability and future direction" valueProps={['Organizational maturity stage', 'Room for additional funding', 'Strategic priorities and sustainability']} />
        )
      )}
    </section>
  );
};
