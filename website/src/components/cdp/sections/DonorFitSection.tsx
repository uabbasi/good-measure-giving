/**
 * DonorFitSection (CDP single-scroll): id="donor-fit".
 * Combines TabbedView's renderGivingTab "Best For" block (ideal donor profile:
 * summary, donor motivations, giving considerations, who it may not fit) and the
 * "Donor Fit" matrix (cause area, giving style, evidence rigor, geographic focus).
 * Both are rich-gated with their own anonymous ContentPreview fallbacks, lifted
 * verbatim.
 */
import React from 'react';
import { Target, Scale, Users } from 'lucide-react';
import { useLandingTheme } from '../../../../contexts/LandingThemeContext';
import { formatCauseArea } from '../../../utils/formatters';
import { GLOSSARY } from '../../../data/glossary';
import { ContentPreview } from '../../ContentPreview';
import type { CdpData } from '../useCdpData';
import { SectionCard, SectionHeader, DataRow } from './_primitives';

export const DonorFitSection: React.FC<{ data: CdpData }> = ({ data }) => {
  const { isDark } = useLandingTheme();
  const { canViewRich, rich } = data;
  const idealDonorProfile = rich?.ideal_donor_profile;

  return (
    <section id="donor-fit" className="space-y-5">
      {/* Best For */}
      {idealDonorProfile ? (
        canViewRich ? (
          <SectionCard isDark={isDark}>
            <SectionHeader icon={Target} title="Best For" isDark={isDark} />
            <p className={`text-sm font-medium mb-3 ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
              {idealDonorProfile.best_for_summary}
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {idealDonorProfile.donor_motivations?.length > 0 && (
                <div>
                  <div className={`text-xs font-semibold mb-1 flex items-center gap-1 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>
                    <Target className="w-3 h-3" />
                    Ideal for donors who:
                  </div>
                  <ul className={`text-xs space-y-0.5 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                    {idealDonorProfile.donor_motivations.slice(0, 4).map((m: string, i: number) => (
                      <li key={i} className="flex items-start gap-1">
                        <span className="text-emerald-500">+</span>
                        {m}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {idealDonorProfile.giving_considerations?.length > 0 && (
                <div>
                  <div className={`text-xs font-semibold mb-1 flex items-center gap-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    <Scale className="w-3 h-3" />
                    Consider:
                  </div>
                  <ul className={`text-xs space-y-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    {idealDonorProfile.giving_considerations.slice(0, 3).map((c: string, i: number) => (
                      <li key={i} className="flex items-start gap-1"><span>-</span>{c}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            {idealDonorProfile.not_ideal_for && (
              <div className={`mt-3 pt-2 border-t text-xs flex items-start gap-1 ${isDark ? 'border-slate-700 text-amber-400' : 'border-slate-200 text-amber-600'}`}>
                <Scale className="w-3 h-3 shrink-0 mt-0.5" />
                <span><strong>May not fit donors who:</strong> {idealDonorProfile.not_ideal_for}</span>
              </div>
            )}
          </SectionCard>
        ) : (
          <ContentPreview title="Best For" description="which donors this charity fits best" teaser={idealDonorProfile?.best_for_summary} valueProps={['Donor motivations and giving style fit', 'Considerations before giving', 'Who this charity may not be ideal for']} />
        )
      ) : !canViewRich && (
        <ContentPreview title="Best For" description="which donors this charity fits best" valueProps={['Which donor profiles align with this charity', 'Giving style and motivation fit', 'Considerations before giving']} />
      )}

      {/* Donor Fit Matrix */}
      {rich?.donor_fit_matrix ? (
        canViewRich ? (
          <SectionCard isDark={isDark}>
            <SectionHeader icon={Users} title="Donor Fit" isDark={isDark} infoTip={GLOSSARY['Donor Fit']} />
            <DataRow label="Cause Area" value={rich.donor_fit_matrix.cause_area ? formatCauseArea(rich.donor_fit_matrix.cause_area) : undefined} isDark={isDark} mono={false} />
            <DataRow label="Giving Style" value={rich.donor_fit_matrix.giving_style} isDark={isDark} mono={false} />
            <DataRow label="Evidence Rigor" value={rich.donor_fit_matrix.evidence_rigor?.split(' - ')[0]} isDark={isDark} />
            {(rich.donor_fit_matrix.geographic_focus?.length ?? 0) > 0 && (
              <div className={`py-2 border-b ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                <span className={`text-sm block mb-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>Geographic Focus</span>
                <span className={`text-xs ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  {rich.donor_fit_matrix.geographic_focus?.slice(0, 3).join(', ')}
                </span>
              </div>
            )}
          </SectionCard>
        ) : (
          <ContentPreview title="Donor Fit" description="donor fit and giving style analysis" valueProps={['Cause area and geographic focus', 'Giving style alignment', 'Evidence rigor assessment']} />
        )
      ) : !canViewRich && (
        <ContentPreview title="Donor Fit" description="donor fit and giving style analysis" valueProps={['Cause area and geographic focus', 'Giving style alignment', 'Evidence rigor assessment']} />
      )}
    </section>
  );
};
