/**
 * TrustAwardsSection (CDP single-scroll): id="trust-awards".
 * Combines two source blocks lifted verbatim from TabbedView:
 *  - "Recognition & Awards" (OVERVIEW tab): Charity Navigator beacons, Candid
 *    seal, BBB Wise Giving status/link. Rich-gated.
 *  - "BBB Wise Giving Assessment" (GIVING tab): meets-all-standards badge,
 *    standards met count (/20), category status (governance/effectiveness/
 *    finances), audit type, summary, standards-not-met list (top 3), give.org
 *    link. Rich-gated.
 * Each sub-block keeps its own rendering gate; both share one <section> anchor.
 */
import React from 'react';
import { Award, ExternalLink, Shield, CheckCircle2, AlertTriangle, AlertCircle } from 'lucide-react';
import { useLandingTheme } from '../../../../contexts/LandingThemeContext';
import { GLOSSARY } from '../../../data/glossary';
import { SourceLinkedText } from '../../SourceLinkedText';
import { ContentPreview } from '../../ContentPreview';
import { trackOutboundClick } from '../../../utils/analytics';
import type { CdpData } from '../useCdpData';
import { SectionCard, SectionHeader } from './_primitives';

export const TrustAwardsSection: React.FC<{ data: CdpData }> = ({ data }) => {
  const { isDark } = useLandingTheme();
  const { charity, canViewRich, rich, citations } = data;

  const hasAwards = !!(
    charity.awards?.cnBeacons?.length ||
    charity.awards?.candidSeal ||
    charity.awards?.bbbStatus ||
    charity.awards?.bbbReviewUrl
  );

  // Nothing to render at all (no awards data and no bbb_assessment) for a
  // signed-in user; for anon, the bbb block still shows a gate when bbb data
  // is absent (matches original GIVING-tab behavior).
  if (!hasAwards && !rich?.bbb_assessment && canViewRich) {
    return null;
  }

  return (
    <section id="trust-awards">
      {/* Recognition & Awards */}
      {hasAwards && (
        canViewRich ? (
          <SectionCard isDark={isDark}>
            <SectionHeader icon={Award} title="Recognition & Awards" isDark={isDark} />
            <div className="space-y-2">
              {charity.awards?.cnBeacons?.map((beacon, i) => (
                <div key={i} className={`flex items-center gap-2 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                  <Award className={`w-4 h-4 flex-shrink-0 ${isDark ? 'text-amber-400' : 'text-amber-500'}`} />
                  {charity.awards?.cnUrl ? (
                    <a href={charity.awards.cnUrl} target="_blank" rel="noopener noreferrer"
                      className={`text-sm hover:underline ${isDark ? 'text-blue-400' : 'text-blue-600'}`}>
                      {beacon}
                    </a>
                  ) : (
                    <span className="text-sm">{beacon}</span>
                  )}
                  <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>-- Charity Navigator</span>
                </div>
              ))}
              {charity.awards?.candidSeal && (
                <div className={`flex items-center gap-2 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                  <Award className={`w-4 h-4 flex-shrink-0 ${isDark ? 'text-amber-400' : 'text-amber-500'}`} />
                  {charity.awards.candidUrl ? (
                    <a href={charity.awards.candidUrl} target="_blank" rel="noopener noreferrer"
                      className={`text-sm hover:underline ${isDark ? 'text-blue-400' : 'text-blue-600'}`}>
                      {String(charity.awards.candidSeal).charAt(0).toUpperCase() + String(charity.awards.candidSeal).slice(1)} Seal
                    </a>
                  ) : (
                    <span className="text-sm">{String(charity.awards.candidSeal).charAt(0).toUpperCase() + String(charity.awards.candidSeal).slice(1)} Seal</span>
                  )}
                  <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>-- Candid</span>
                </div>
              )}
              {charity.awards?.bbbStatus && (
                <div className={`flex items-center gap-2 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                  <Award className={`w-4 h-4 flex-shrink-0 ${isDark ? 'text-amber-400' : 'text-amber-500'}`} />
                  {charity.awards.bbbReviewUrl ? (
                    <a href={charity.awards.bbbReviewUrl} target="_blank" rel="noopener noreferrer"
                      className={`text-sm hover:underline ${isDark ? 'text-blue-400' : 'text-blue-600'}`}>
                      {charity.awards.bbbStatus}
                    </a>
                  ) : (
                    <span className="text-sm">{charity.awards.bbbStatus}</span>
                  )}
                  <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>-- BBB Wise Giving</span>
                </div>
              )}
              {!charity.awards?.bbbStatus && charity.awards?.bbbReviewUrl && (
                <div className={`flex items-center gap-2 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                  <ExternalLink className={`w-4 h-4 flex-shrink-0 ${isDark ? 'text-slate-400' : 'text-slate-500'}`} />
                  <a href={charity.awards.bbbReviewUrl} target="_blank" rel="noopener noreferrer"
                    className={`text-sm hover:underline ${isDark ? 'text-blue-400' : 'text-blue-600'}`}>
                    View BBB Evaluation
                  </a>
                  <span className={`text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>-- BBB Wise Giving</span>
                </div>
              )}
            </div>
          </SectionCard>
        ) : (
          <ContentPreview title="Recognition & Awards" description="third-party awards and ratings" valueProps={['Charity Navigator beacons', 'Candid seal of transparency', 'BBB Wise Giving accreditation']} />
        )
      )}

      {/* BBB Wise Giving Assessment */}
      {rich?.bbb_assessment ? (
        canViewRich ? (
          (rich.bbb_assessment.meets_all_standards ||
           (rich.bbb_assessment.standards_met && rich.bbb_assessment.standards_met > 0) ||
           (rich.bbb_assessment.standards_not_met && rich.bbb_assessment.standards_not_met.length > 0) ||
           rich.bbb_assessment.review_url || rich.bbb_assessment.summary || rich.bbb_assessment.audit_type) ? (
            <SectionCard isDark={isDark} className={`!border-l-4 ${
              rich.bbb_assessment.meets_all_standards
                ? isDark ? '!border-emerald-500' : '!border-emerald-500'
                : isDark ? '!border-amber-500' : '!border-amber-500'
            }`}>
              <SectionHeader icon={Shield} title="BBB Wise Giving" isDark={isDark} infoTip={GLOSSARY['BBB Wise Giving']} />
              <div className="flex items-center gap-2 mb-3">
                {rich.bbb_assessment.meets_all_standards ? (
                  <CheckCircle2 className={`w-5 h-5 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                ) : (
                  <AlertTriangle className={`w-5 h-5 ${isDark ? 'text-amber-400' : 'text-amber-600'}`} />
                )}
                <span className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  {rich.bbb_assessment.meets_all_standards ? 'Meets All Standards' : 'Standards Review'}
                </span>
                {rich.bbb_assessment.standards_met != null && rich.bbb_assessment.standards_met > 0 && (
                  <span className={`text-xs font-mono ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    ({rich.bbb_assessment.standards_met}/20)
                  </span>
                )}
              </div>
              <div className="grid grid-cols-2 gap-1.5 mb-3">
                {['governance', 'effectiveness', 'finances'].map((category) => {
                  const statusKey = `${category}_status` as 'governance_status' | 'effectiveness_status' | 'finances_status';
                  const status = rich.bbb_assessment![statusKey];
                  const isPassing = status === 'pass' || status === 'Pass' || status === 'PASS';
                  return status && status !== 'NEUTRAL' ? (
                    <div key={category} className="flex items-center gap-1.5 text-sm">
                      {isPassing ? (
                        <CheckCircle2 className={`w-4 h-4 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                      ) : (
                        <AlertCircle className={`w-4 h-4 ${isDark ? 'text-amber-400' : 'text-amber-600'}`} />
                      )}
                      <span className={`capitalize ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>{category}</span>
                    </div>
                  ) : null;
                })}
                {rich.bbb_assessment.audit_type && (
                  <div className="flex items-center gap-1.5 text-sm">
                    <CheckCircle2 className={`w-4 h-4 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
                    <span className={isDark ? 'text-slate-300' : 'text-slate-700'}>{rich.bbb_assessment.audit_type}</span>
                  </div>
                )}
              </div>
              {rich.bbb_assessment.summary && (
                <p className={`text-xs mb-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  <SourceLinkedText text={rich.bbb_assessment.summary} citations={citations} isDark={isDark} subtle />
                </p>
              )}
              {rich.bbb_assessment.standards_not_met && rich.bbb_assessment.standards_not_met.length > 0 && (
                <div className={`pt-2 border-t ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                  <div className={`text-xs font-semibold mb-1 flex items-center gap-1 ${isDark ? 'text-amber-400' : 'text-amber-600'}`}>
                    <AlertTriangle className="w-3 h-3" />
                    Not Met
                  </div>
                  <ul className={`text-xs space-y-0.5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                    {rich.bbb_assessment.standards_not_met.slice(0, 3).map((std, i) => (
                      <li key={i}>- {std}</li>
                    ))}
                  </ul>
                </div>
              )}
              {rich.bbb_assessment.review_url && (
                <a
                  href={rich.bbb_assessment.review_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={() => trackOutboundClick(charity.id ?? charity.ein ?? '', charity.name, 'give.org')}
                  className={`mt-2 inline-flex items-center gap-1 text-xs font-medium ${isDark ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-700'}`}
                >
                  View on give.org <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </SectionCard>
          ) : null
        ) : (
          <ContentPreview title="BBB Assessment" description="BBB Wise Giving standards review" valueProps={['Meets all 20 BBB standards check', 'Governance, effectiveness & finance review', 'Audit type and standards not met']} />
        )
      ) : !canViewRich && (
        <ContentPreview title="BBB Assessment" description="BBB Wise Giving standards review" valueProps={['Meets all 20 BBB standards check', 'Governance, effectiveness & finance review', 'Audit type and standards not met']} />
      )}
    </section>
  );
};
