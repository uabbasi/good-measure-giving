/**
 * OrganizationEngagement: Shows collaboration posture on charity detail pages.
 *
 * Default empty state invites organizations to share feedback.
 * Future: renders organization responses when available.
 */

import React, { useState } from 'react';
import { Building2 } from 'lucide-react';
import { ReportIssueButton } from './ReportIssueButton';

interface OrganizationEngagementProps {
  charityName: string;
  charityEin: string;
  isDark: boolean;
  /** Future: organization response data (always undefined for now) */
  organizationResponse?: {
    content: string;
    respondentRole: string;
    respondedAt: string;
  };
}

export const OrganizationEngagement: React.FC<OrganizationEngagementProps> = ({
  charityName,
  charityEin,
  isDark,
  organizationResponse,
}) => {
  const [showReportModal, setShowReportModal] = useState(false);

  return (
    <div className={`rounded-xl border p-5 ${
      isDark ? 'bg-slate-900/50 border-slate-800' : 'bg-slate-50 border-slate-200'
    }`}>
      <div className="flex items-center gap-2 mb-3">
        <Building2 className={`w-4 h-4 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} />
        <h3 className={`text-sm font-semibold ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
          Organization Engagement
        </h3>
      </div>

      {organizationResponse ? (
        /* Future: render organization response */
        <div>
          <p className={`text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
            {organizationResponse.content}
          </p>
          <p className={`text-xs mt-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            {organizationResponse.respondentRole} &middot; {organizationResponse.respondedAt}
          </p>
        </div>
      ) : (
        /* Empty state */
        <div>
          <p className={`text-sm mb-3 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
            This evaluation is based on public data. We haven{'\u2019'}t heard from {charityName} yet.
          </p>
          <div className="flex items-center gap-3">
            <span className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
              Represent this organization?
            </span>
            <button
              onClick={() => setShowReportModal(true)}
              className={`text-sm font-medium transition-colors ${
                isDark ? 'text-emerald-400 hover:text-emerald-300' : 'text-emerald-600 hover:text-emerald-700'
              }`}
            >
              Tell us more &rarr;
            </button>
          </div>
          <p className={`text-xs mt-3 italic ${isDark ? 'text-slate-600' : 'text-slate-400'}`}>
            Organization submissions may be reviewed before publication.
          </p>
        </div>
      )}

      {/* ReportIssueButton modal with org feedback pre-selected */}
      {showReportModal && (
        <ReportIssueButton
          charityId={charityEin}
          charityName={charityName}
          isDark={isDark}
          initialIssueType="organization_feedback"
          defaultOpen
          onClose={() => setShowReportModal(false)}
        />
      )}
    </div>
  );
};
