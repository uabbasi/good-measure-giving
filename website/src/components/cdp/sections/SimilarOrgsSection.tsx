/**
 * SimilarOrgsSection (CDP single-scroll): id="similar-orgs".
 * Lifted verbatim from TabbedView's renderGivingTab "Similar Organizations" block:
 * peer group label and a list of similar orgs (max 5 when signed in, first 3 names
 * when anonymous), each linked to the charity's detail page when found in the
 * directory (signed-in only, with click analytics), plus a sign-in CTA for
 * anonymous users. Uses useCharities() directly to resolve org names to ids.
 */
import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Users, ExternalLink, Lock } from 'lucide-react';
import { useLandingTheme } from '../../../../contexts/LandingThemeContext';
import { useCharities } from '../../../hooks/useCharities';
import { trackSimilarOrgClick } from '../../../utils/analytics';
import { SignInButton } from '../../../auth/SignInButton';
import type { CdpData } from '../useCdpData';
import { SectionCard, SectionHeader } from './_primitives';

export const SimilarOrgsSection: React.FC<{ data: CdpData }> = ({ data }) => {
  const { isDark } = useLandingTheme();
  const { charities: allCharities } = useCharities();
  const { charity, canViewRich, rich } = data;

  const charityNameToId = useMemo(() => {
    const map = new Map<string, string>();
    allCharities.forEach(c => {
      map.set(c.name.toLowerCase(), c.id ?? c.ein ?? '');
    });
    return map;
  }, [allCharities]);

  const findCharityId = (name: string): string | null => {
    const lowerName = name.toLowerCase();
    if (charityNameToId.has(lowerName)) return charityNameToId.get(lowerName) || null;
    for (const [charityName, id] of charityNameToId.entries()) {
      if (charityName.includes(lowerName) || lowerName.includes(charityName)) return id;
    }
    return null;
  };

  if (!(rich?.similar_organizations || rich?.peer_comparison)) return null;

  return (
    <section id="similar-orgs">
      <SectionCard isDark={isDark}>
        <SectionHeader icon={Users} title="Similar Organizations" isDark={isDark} />
        {rich?.peer_comparison && (
          <div className={`mb-3 pb-2 border-b text-sm font-medium ${isDark ? 'border-slate-800 text-slate-200' : 'border-slate-200 text-slate-700'}`}>
            {rich.peer_comparison.peer_group}
          </div>
        )}
        {rich?.similar_organizations && rich.similar_organizations.length > 0 && (
          <div className="space-y-2">
            {rich.similar_organizations.slice(0, canViewRich ? 5 : 3).map((org, i) => {
              const orgName = typeof org === 'string' ? org : org.name;
              const linkedId = findCharityId(orgName);
              return (
                <div key={i} className="text-sm">
                  {canViewRich && linkedId ? (
                    <Link
                      to={`/charity/${linkedId}`}
                      onClick={() => trackSimilarOrgClick(charity.id ?? charity.ein ?? '', linkedId!, orgName, i)}
                      className={`flex items-center gap-1.5 ${
                        isDark ? 'text-emerald-400 hover:text-emerald-300' : 'text-emerald-600 hover:text-emerald-700'
                      }`}
                    >
                      {orgName}
                      <ExternalLink className="w-3 h-3" />
                    </Link>
                  ) : (
                    <span className={isDark ? 'text-slate-300' : 'text-slate-700'}>{orgName}</span>
                  )}
                </div>
              );
            })}
          </div>
        )}
        {!canViewRich && (
          <SignInButton
            variant="custom"
            className={`mt-3 pt-2 border-t text-xs flex items-center gap-1.5 w-full text-left cursor-pointer hover:opacity-80 transition-opacity ${
              isDark ? 'border-slate-700 text-emerald-400' : 'border-slate-200 text-emerald-600'
            }`}
          >
            <Lock className="w-3 h-3 flex-shrink-0" />
            <span><span className="underline font-medium">Sign in</span> to compare</span>
          </SignInButton>
        )}
      </SectionCard>
    </section>
  );
};
