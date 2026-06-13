/**
 * ZakatSection (CDP single-scroll): id="zakat".
 * Lifted verbatim from TabbedView's renderGivingTab "Zakat Claim Evidence" block:
 * corroborated zakat claim evidence text with an optional linked zakat policy URL,
 * emerald styling. NOT gated — visible to all users when zakat-eligible.
 */
import React from 'react';
import { Shield, ExternalLink } from 'lucide-react';
import { useLandingTheme } from '../../../../contexts/LandingThemeContext';
import type { CdpData } from '../useCdpData';
import { SectionCard, SectionHeader, extractZakatPolicyUrl } from './_primitives';

export const ZakatSection: React.FC<{ data: CdpData }> = ({ data }) => {
  const { isDark } = useLandingTheme();
  const { charity, isZakatEligible } = data;

  if (!(isZakatEligible && charity.zakatClaimEvidence && charity.zakatClaimEvidence.length > 0)) {
    return null;
  }

  return (
    <section id="zakat">
      <SectionCard isDark={isDark} className={`!border-2 ${isDark ? '!border-emerald-700/50 !bg-emerald-900/10' : '!border-emerald-300 !bg-emerald-50'}`}>
        <SectionHeader icon={Shield} title="Zakat Claim Evidence" isDark={isDark} />
        <div className="space-y-2">
          {charity.zakatClaimEvidence.map((evidence, i) => {
            const policyUrl = extractZakatPolicyUrl(evidence);
            const cleanEvidence = evidence.replace(/\(Source:\s*https?:\/\/[^\s)]+\)/, '').trim();
            return (
              <div key={i} className={`text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                {cleanEvidence}
                {policyUrl && (
                  <a
                    href={policyUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`ml-2 inline-flex items-center gap-1 text-xs ${
                      isDark ? 'text-emerald-400 hover:text-emerald-300' : 'text-emerald-600 hover:text-emerald-700'
                    }`}
                  >
                    View policy <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            );
          })}
        </div>
      </SectionCard>
    </section>
  );
};
