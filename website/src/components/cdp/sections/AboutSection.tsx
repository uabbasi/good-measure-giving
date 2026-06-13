/**
 * AboutSection (CDP single-scroll): id="about".
 * Combines four Overview-tab blocks lifted verbatim from TabbedView:
 * emerging-org notice, About headline+summary (anon-gated), Quick Facts, External Links.
 */
import React from 'react';
import { Rocket, BookOpen, FileText, Globe, ExternalLink, Lock } from 'lucide-react';
import { useLandingTheme } from '../../../../contexts/LandingThemeContext';
import { getCharityAddress } from '../../../utils/formatters';
import { trackExternalLinkClick, trackOutboundClick } from '../../../utils/analytics';
import { SignInButton } from '../../../auth/SignInButton';
import { SourceLinkedText } from '../../SourceLinkedText';
import type { CdpData } from '../useCdpData';
import {
  SectionCard,
  SectionHeader,
  DataRow,
  formatCurrency,
  categorizeTags,
  formatTag,
  formatProgramTag,
} from './_primitives';

export const AboutSection: React.FC<{ data: CdpData }> = ({ data }) => {
  const { isDark } = useLandingTheme();
  const { charity, canViewRich, rich, headline, aboutSummary, citations, revenue } = data;
  const beneficiariesCount = charity.beneficiariesServedAnnually;

  return (
    <section id="about" className="space-y-5">
      {/* Emerging Org notice */}
      {charity.evaluationTrack === 'NEW_ORG' && (
        <SectionCard isDark={isDark}>
          <div className="flex items-center gap-3 mb-3">
            <div className={`p-2 rounded-lg ${isDark ? 'bg-sky-800/50' : 'bg-sky-100'}`}>
              <Rocket className={`w-5 h-5 ${isDark ? 'text-sky-400' : 'text-sky-600'}`} />
            </div>
            <div>
              <div className={`text-sm font-bold ${isDark ? 'text-sky-300' : 'text-sky-700'}`}>
                Emerging Organization
              </div>
              {charity.foundedYear && (
                <div className={`text-xs ${isDark ? 'text-sky-400/70' : 'text-sky-600/80'}`}>
                  Est. {charity.foundedYear} -- Building Track Record
                </div>
              )}
            </div>
          </div>
          <p className={`text-sm leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
            This organization is too early to rate numerically.
            We show qualitative context and early indicators while it builds a longer public track record.
          </p>
        </SectionCard>
      )}

      {/* About */}
      {(headline || aboutSummary) && (
        <SectionCard isDark={isDark}>
          <SectionHeader icon={BookOpen} title="About" isDark={isDark} />
          {headline && (
            <p className={`text-base font-medium leading-relaxed mb-3 ${isDark ? 'text-slate-100' : 'text-slate-800'}`}>
              <SourceLinkedText text={headline} citations={citations} isDark={isDark} />
            </p>
          )}
          {aboutSummary && (
            <div className="relative">
              <p className={`text-sm leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-600'} ${!canViewRich ? 'line-clamp-3' : ''}`}>
                <SourceLinkedText text={aboutSummary} citations={citations} isDark={isDark} />
              </p>
              {!canViewRich && aboutSummary.length > 200 && (
                <div className={`absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t ${isDark ? 'from-slate-800' : 'from-white'}`} />
              )}
            </div>
          )}
          {!canViewRich && (
            <SignInButton
              variant="custom"
              className={`mt-3 pt-3 border-t text-sm flex items-center gap-2 w-full text-left cursor-pointer hover:opacity-80 transition-opacity ${
                isDark ? 'border-slate-700 text-emerald-400' : 'border-slate-200 text-emerald-600'
              }`}
            >
              <Lock className="w-3.5 h-3.5 flex-shrink-0" />
              <span>
                <span className="underline font-medium">Sign in</span>
                {' '}to read full analysis with evidence grades and source citations
              </span>
            </SignInButton>
          )}
        </SectionCard>
      )}

      {/* Quick Facts */}
      <SectionCard isDark={isDark}>
        <SectionHeader icon={FileText} title="Quick Facts" isDark={isDark} />
        <div className="space-y-0">
          {beneficiariesCount != null && beneficiariesCount > 0 && (
            <DataRow label="Beneficiaries Served" value={beneficiariesCount.toLocaleString()} isDark={isDark} highlight />
          )}
          {(() => {
            const tagCategories = categorizeTags(charity.causeTags);
            return (
              <>
                {tagCategories.populations.length > 0 && (
                  <DataRow label="Populations" value={tagCategories.populations.slice(0, 3).map(t => formatTag(t)).join(', ')} isDark={isDark} mono={false} />
                )}
                {tagCategories.geography.length > 0 && (
                  <DataRow label="Geography" value={tagCategories.geography.slice(0, 3).map(t => formatTag(t)).join(', ')} isDark={isDark} mono={false} />
                )}
                {tagCategories.interventions.length > 0 && (
                  <DataRow label="Services" value={tagCategories.interventions.slice(0, 3).map(t => formatTag(t)).join(', ')} isDark={isDark} mono={false} />
                )}
              </>
            );
          })()}
          {(charity.programs || []).length > 0 && (
            <DataRow label="Programs" value={(charity.programs || []).slice(0, 3).map(t => formatProgramTag(t)).join(', ')} isDark={isDark} mono={false} />
          )}
          {rich?.long_term_outlook?.founded_year && (
            <DataRow label="Founded" value={rich.long_term_outlook.founded_year} isDark={isDark} />
          )}
          {revenue != null && (
            <DataRow label="Annual Revenue" value={formatCurrency(revenue)} isDark={isDark} />
          )}
          <DataRow label="EIN" value={charity.ein || charity.id} isDark={isDark} />
          {getCharityAddress(charity) && (
            <DataRow label="Location" value={getCharityAddress(charity)} isDark={isDark} mono={false} />
          )}
        </div>
      </SectionCard>

      {/* External Links */}
      <SectionCard isDark={isDark}>
        <SectionHeader icon={Globe} title="External Links" isDark={isDark} />
        <div className="space-y-2">
          {charity.website && (
            <a
              href={charity.website}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => trackExternalLinkClick(charity.id ?? charity.ein ?? '', 'website', charity.website!)}
              className={`flex items-center gap-2 text-sm py-1 ${isDark ? 'text-emerald-400 hover:text-emerald-300' : 'text-emerald-600 hover:text-emerald-700'}`}
            >
              Website <ExternalLink className="w-3 h-3" />
            </a>
          )}
          <a
            href={`https://www.charitynavigator.org/ein/${(charity.ein ?? charity.id ?? '').replace(/-/g, '')}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => trackExternalLinkClick(charity.id ?? charity.ein ?? '', 'source', `https://www.charitynavigator.org/ein/${(charity.ein ?? charity.id ?? '').replace(/-/g, '')}`)}
            className={`flex items-center justify-between text-sm py-1 ${isDark ? 'text-slate-400 hover:text-slate-300' : 'text-slate-500 hover:text-slate-600'}`}
          >
            <span className="flex items-center gap-1">Charity Navigator <ExternalLink className="w-3 h-3" /></span>
            {charity.scores?.overall && (
              <span className={`font-mono ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{Math.round(charity.scores.overall)}</span>
            )}
          </a>
          <a
            href={`https://projects.propublica.org/nonprofits/organizations/${(charity.ein ?? charity.id ?? '').replace(/-/g, '')}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => trackExternalLinkClick(charity.id ?? charity.ein ?? '', 'source', `https://projects.propublica.org/nonprofits/organizations/${(charity.ein ?? charity.id ?? '').replace(/-/g, '')}`)}
            className={`flex items-center gap-2 text-sm py-1 ${isDark ? 'text-slate-400 hover:text-slate-300' : 'text-slate-500 hover:text-slate-600'}`}
          >
            ProPublica 990 <ExternalLink className="w-3 h-3" />
          </a>
          {rich?.bbb_assessment?.review_url && (
            <a
              href={rich.bbb_assessment.review_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => trackOutboundClick(charity.id ?? charity.ein ?? '', charity.name, 'give.org')}
              className={`flex items-center justify-between text-sm py-1 ${isDark ? 'text-slate-400 hover:text-slate-300' : 'text-slate-500 hover:text-slate-600'}`}
            >
              <span className="flex items-center gap-1">BBB Wise Giving <ExternalLink className="w-3 h-3" /></span>
              {rich.bbb_assessment.meets_all_standards && (
                <span className={`font-medium text-xs ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>Accredited</span>
              )}
            </a>
          )}
        </div>
      </SectionCard>
    </section>
  );
};
