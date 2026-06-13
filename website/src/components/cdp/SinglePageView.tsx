/**
 * SinglePageView: single continuous scrolling charity detail page (no tabs).
 *
 * Composes the extracted CDP pieces:
 *   - a slim sticky header (back link, name, address/cause, action buttons + modal)
 *   - MobileScoreBar (mobile sticky jump-bar)
 *   - VerdictHero (at-a-glance verdict + score)
 *   - SectionRail (desktop sticky nav) alongside the section body
 *   - the visible sections rendered in order via a registry
 *   - a slim footer (EIN, evaluation date, share, report issue)
 *
 * The verdict/score/signal badges live in VerdictHero, so the header is kept to
 * name + address + actions only (no duplicated signal pills).
 */

import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ExternalLink, Plus, LogIn } from 'lucide-react';

import type { CharityProfile } from '../../../types';
import { useLandingTheme } from '../../../contexts/LandingThemeContext';
import { getCharityAddress, formatCauseArea } from '../../utils/formatters';
import { trackDonateClick } from '../../utils/analytics';
import { useGivingHistory } from '../../hooks/useGivingHistory';
import { SignInButton } from '../../auth/SignInButton';
import { BookmarkButton } from '../BookmarkButton';
import { CompareButton } from '../CompareButton';
import { ShareButton } from '../ShareButton';
import { ReportIssueButton } from '../ReportIssueButton';
import { OrganizationEngagement } from '../OrganizationEngagement';
import { AddDonationModal } from '../giving/AddDonationModal';

import { useCdpData, type CdpData } from './useCdpData';
import { visibleSections } from './sections.config';
import { useScrollSpy } from './useScrollSpy';
import { VerdictHero } from './VerdictHero';
import { SectionRail } from './SectionRail';
import { MobileScoreBar } from './MobileScoreBar';
import * as Sections from './sections';

const REGISTRY: Record<string, React.FC<{ data: CdpData }>> = {
  'about': Sections.AboutSection,
  'why-this-score': Sections.WhyThisScoreSection,
  'strengths-concerns': Sections.StrengthsConcernsSection,
  'evidence': Sections.EvidenceSection,
  'donor-fit': Sections.DonorFitSection,
  'financials': Sections.FinancialsSection,
  'leadership': Sections.LeadershipSection,
  'trust-awards': Sections.TrustAwardsSection,
  'zakat': Sections.ZakatSection,
  'similar-orgs': Sections.SimilarOrgsSection,
};

interface SinglePageViewProps {
  charity: CharityProfile;
  canViewRich: boolean;
}

export const SinglePageView: React.FC<SinglePageViewProps> = ({ charity, canViewRich }) => {
  const { isDark } = useLandingTheme();
  const { addDonation, getPaymentSources } = useGivingHistory();
  const [showDonationModal, setShowDonationModal] = useState(false);

  const data = useCdpData(charity, canViewRich);
  const sections = visibleSections(data);
  const activeId = useScrollSpy(sections.map((s) => s.id));

  const { amal } = data;
  const donateUrl = charity.donationUrl ?? charity.website ?? undefined;
  const handleDonateClick = () => {
    trackDonateClick(charity.id ?? charity.ein ?? '', charity.name, charity.donationUrl || charity.website || '');
  };

  return (
    <div className={`min-h-screen ${isDark ? 'bg-slate-950' : 'bg-slate-100'}`}>
      {/* ─────────────────────────────────────────────────────────────────────
          SLIM STICKY HEADER (name + address + actions)
          ───────────────────────────────────────────────────────────────────── */}
      <div
        className={`sticky top-0 z-40 border-b backdrop-blur ${
          isDark ? 'bg-slate-900/95 border-slate-800' : 'bg-white/95 border-slate-200'
        }`}
      >
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-3">
          {/* Back link */}
          <Link
            to="/browse"
            aria-label="Back to browse"
            className={`inline-flex items-center gap-1 text-xs mb-1.5 ${
              isDark ? 'text-slate-500 hover:text-white' : 'text-slate-400 hover:text-slate-900'
            }`}
          >
            <ArrowLeft className="w-3 h-3" />
            Browse
          </Link>

          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:gap-4">
            {/* Left: name + subtitle */}
            <div className="min-w-0">
              <h1 className={`text-xl sm:text-2xl font-bold leading-tight truncate ${isDark ? 'text-white' : 'text-slate-900'}`}>
                {charity.name}
              </h1>
              <div className={`flex flex-wrap items-center gap-1.5 mt-0.5 text-sm ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                {getCharityAddress(charity) && <span>{getCharityAddress(charity)}</span>}
                {getCharityAddress(charity) && charity.causeArea && (
                  <span className={isDark ? 'text-slate-700' : 'text-slate-300'}>·</span>
                )}
                {charity.causeArea && (
                  <span className={isDark ? 'text-slate-400' : 'text-slate-600'}>{formatCauseArea(charity.causeArea)}</span>
                )}
              </div>
            </div>

            {/* Right: inline actions */}
            <div className="flex items-center gap-1 flex-shrink-0">
              {canViewRich ? (
                <>
                  <button
                    data-tour="action-log-donation"
                    onClick={() => setShowDonationModal(true)}
                    className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors ${
                      isDark ? 'text-slate-400 hover:text-white hover:bg-slate-800' : 'text-slate-500 hover:text-slate-900 hover:bg-slate-100'
                    }`}
                  >
                    <Plus className="w-3 h-3" />
                    Log
                  </button>
                  <CompareButton charityEin={charity.ein!} charityName={charity.name} size="sm" />
                  <span data-tour="action-save">
                    <BookmarkButton charityEin={charity.ein || charity.id || ''} charityName={charity.name} causeTags={charity.causeTags || undefined} showLabel size="sm" />
                  </span>
                  <ShareButton charityId={charity.ein!} charityName={charity.name} isDark={isDark} />
                </>
              ) : (
                <>
                  <SignInButton variant="custom" isDark={isDark}>
                    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium cursor-pointer transition-colors ${
                      isDark ? 'text-emerald-400 hover:text-emerald-300 hover:bg-slate-800' : 'text-emerald-600 hover:text-emerald-700 hover:bg-slate-100'
                    }`}>
                      <LogIn className="w-3 h-3" />
                      Sign in
                    </span>
                  </SignInButton>
                  <ShareButton charityId={charity.ein!} charityName={charity.name} isDark={isDark} />
                </>
              )}
              {donateUrl && (
                <a
                  data-tour="action-donate"
                  href={donateUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={handleDonateClick}
                  className={`inline-flex items-center gap-1 px-3 py-1 rounded text-xs font-semibold transition-colors ${
                    isDark ? 'bg-emerald-600 hover:bg-emerald-500 text-white' : 'bg-emerald-600 hover:bg-emerald-700 text-white'
                  }`}
                >
                  Donate <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Mobile sticky score/jump bar */}
      <MobileScoreBar data={data} sections={sections} />

      {/* ─────────────────────────────────────────────────────────────────────
          BODY: verdict hero + (rail | sections)
          ───────────────────────────────────────────────────────────────────── */}
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6">
        <VerdictHero data={data} />

        <div className="mt-8 md:grid md:grid-cols-[170px_1fr] md:gap-8">
          <SectionRail sections={sections} activeId={activeId} />
          <div className="min-w-0 space-y-8">
            {sections.map((s) => {
              const C = REGISTRY[s.id];
              return C ? <C key={s.id} data={data} /> : null;
            })}
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────────────
          FOOTER (EIN, evaluation date, share, report issue)
          ───────────────────────────────────────────────────────────────────── */}
      <div className={`border-t mt-4 pt-6 pb-8 ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
        <div className={`max-w-5xl mx-auto px-4 sm:px-6 flex items-center justify-center gap-2 text-xs flex-wrap ${
          isDark ? 'text-slate-500' : 'text-slate-400'
        }`}>
          <span>EIN: {charity.ein}</span>
          {amal?.evaluation_date && (
            <>
              <span>--</span>
              <span>Last evaluated {new Date(amal.evaluation_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
            </>
          )}
          <span>--</span>
          <ShareButton charityId={charity.ein || charity.id || ''} charityName={charity.name} variant="text" isDark={isDark} />
          <span>--</span>
          <ReportIssueButton
            charityId={charity.ein!}
            charityName={charity.name}
            variant="text"
            isDark={isDark}
            className={`font-medium ${isDark ? 'text-slate-500 hover:text-slate-300' : 'text-slate-400 hover:text-slate-600'}`}
          />
        </div>
      </div>

      {/* Organization Engagement */}
      <div className="max-w-5xl mx-auto px-4 sm:px-6 pb-4">
        <OrganizationEngagement
          charityName={charity.name}
          charityEin={charity.ein!}
          isDark={isDark}
        />
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

export default SinglePageView;
