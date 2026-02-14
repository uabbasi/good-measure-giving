/**
 * ProfilePage - User profile with giving dashboard
 * Tabs: Overview | History
 */

import React, { useState, useMemo } from 'react';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import { useBookmarkState, useProfileState } from '../src/contexts/UserFeaturesContext';
import { useAuth } from '../src/auth';
import { useCharities } from '../src/hooks/useCharities';
import { useGivingHistory } from '../src/hooks/useGivingHistory';
import { useCharityTargets } from '../src/hooks/useCharityTargets';
import { useGivingDashboard } from '../src/hooks/useGivingDashboard';
import { SignInButton } from '../src/auth/SignInButton';
import {
  AddDonationModal,
  GivingHistoryTable,
  UnifiedAllocationView,
} from '../src/components/giving';
import type { GivingHistoryEntry, CharitySummary } from '../types';

type TabId = 'overview' | 'history';

// Tab button component
function TabButton({
  id,
  label,
  icon,
  isActive,
  onClick,
  isDark,
}: {
  id: TabId;
  label: string;
  icon: React.ReactNode;
  isActive: boolean;
  onClick: () => void;
  isDark: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`
        flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors
        ${isActive
          ? 'bg-emerald-600 text-white'
          : isDark
          ? 'text-slate-400 hover:text-white hover:bg-slate-800'
          : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
        }
      `}
    >
      {icon}
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}

export function ProfilePage() {
  const { isDark } = useLandingTheme();
  const { isSignedIn, isLoaded, firstName, email } = useAuth();
  const { bookmarks, isLoading: bookmarksLoading, addBookmark, removeBookmark } = useBookmarkState();
  const { profile, isLoading: profileLoading, updateProfile } = useProfileState();
  const { summaries, loading: charitiesLoading } = useCharities();

  // Giving hooks
  const {
    donations,
    isLoading: historyLoading,
    addDonation,
    updateDonation,
    deleteDonation,
    getPaymentSources,
    exportCSV,
  } = useGivingHistory();

  // Charity targets hook
  const {
    targets: charityTargets,
    setTarget: setCharityTarget,
    removeTarget: removeCharityTarget,
  } = useCharityTargets();

  // Convert summaries to CharitySummary array for dashboard
  const charitySummaries = useMemo((): CharitySummary[] => {
    if (!summaries) return [];
    return summaries.map(s => ({
      id: s.ein,
      ein: s.ein,
      name: s.name,
      tier: s.tier || 'baseline',
      amalScore: s.amalScore || 0,
      walletTag: s.walletTag || 'INSUFFICIENT-DATA',
      impactTier: s.impactTier || null,
      causeTags: s.causeTags || null,
      headline: s.headline || null,
    }));
  }, [summaries]);

  const {
    isLoading: dashboardLoading,
    targetZakatAmount,
    zakatYear,
    overallProgress,
    bucketProgress,
  } = useGivingDashboard(charitySummaries);

  // UI state
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [showDonationModal, setShowDonationModal] = useState(false);
  const [editingDonation, setEditingDonation] = useState<GivingHistoryEntry | null>(null);
  const [prefillCharity, setPrefillCharity] = useState<{ ein: string; name: string } | null>(null);

  // Match bookmarks with charity data for the unified view
  const bookmarkedCharitiesForView = useMemo(() => {
    if (!summaries || bookmarks.length === 0) return [];

    const charityMap = new Map(summaries.map(c => [c.ein, c]));

    return bookmarks
      .map(bookmark => {
        const charity = charityMap.get(bookmark.charityEin);
        if (!charity) return null;
        return {
          ein: charity.ein,
          name: charity.name,
          amalScore: charity.amalScore || null,
          walletTag: charity.walletTag || null,
          causeTags: charity.causeTags || null,
          notes: bookmark.notes,
        };
      })
      .filter((item): item is NonNullable<typeof item> => item !== null);
  }, [bookmarks, summaries]);

  // Handle donation save
  const handleSaveDonation = async (input: Parameters<typeof addDonation>[0]) => {
    if (editingDonation) {
      await updateDonation(editingDonation.id, input);
    } else {
      await addDonation(input);
    }
  };

  // Handle donation delete (confirmation handled inline in table)
  const handleDeleteDonation = async (id: string) => {
    await deleteDonation(id);
  };

  // Handle CSV export
  const handleExport = (year?: number) => {
    const csv = exportCSV(year);
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `giving-history${year ? `-${year}` : ''}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Not signed in
  if (isLoaded && !isSignedIn) {
    return (
      <div className={`min-h-screen ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
        <div className="max-w-4xl mx-auto px-4 py-16 text-center">
          <svg
            className={`w-16 h-16 mx-auto mb-6 ${isDark ? 'text-slate-600' : 'text-slate-400'}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M17.982 18.725A7.488 7.488 0 0012 15.75a7.488 7.488 0 00-5.982 2.975m11.963 0a9 9 0 10-11.963 0m11.963 0A8.966 8.966 0 0112 21a8.966 8.966 0 01-5.982-2.275M15 9.75a3 3 0 11-6 0 3 3 0 016 0z"
            />
          </svg>
          <h1 className={`text-2xl font-semibold mb-4 ${isDark ? 'text-white' : 'text-slate-900'}`}>
            Your Giving Dashboard
          </h1>
          <p className={`text-lg mb-8 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
            Sign in to track your zakat, set giving goals, and see your progress.
          </p>
          <SignInButton />
        </div>
      </div>
    );
  }

  return (
    <div className={`min-h-screen ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
      <div className="max-w-5xl mx-auto px-4 py-8">
        {/* Profile Header */}
        <div className={`rounded-xl border p-6 mb-6 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
          <div className="flex items-center gap-4">
            <div className={`w-16 h-16 rounded-full flex items-center justify-center text-2xl font-semibold ${isDark ? 'bg-slate-800 text-white' : 'bg-slate-100 text-slate-700'}`}>
              {firstName ? firstName[0].toUpperCase() : email?.[0]?.toUpperCase() || '?'}
            </div>
            <div className="flex-grow">
              <h1 className={`text-xl font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                {firstName || 'Welcome'}
              </h1>
              <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                {email}
              </p>
            </div>
            <button
              onClick={() => {
                setEditingDonation(null);
                setShowDonationModal(true);
              }}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
              <span className="hidden sm:inline">Log Donation</span>
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className={`flex gap-1 p-1 rounded-xl mb-6 ${isDark ? 'bg-slate-900' : 'bg-slate-100'}`}>
          <TabButton
            id="overview"
            label="Overview"
            icon={<svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>}
            isActive={activeTab === 'overview'}
            onClick={() => setActiveTab('overview')}
            isDark={isDark}
          />
          <TabButton
            id="history"
            label="History"
            icon={<svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>}
            isActive={activeTab === 'history'}
            onClick={() => setActiveTab('history')}
            isDark={isDark}
          />
        </div>

        {/* Tab Content */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Unified Allocation View - card-based allocation with charity assignments */}
            <UnifiedAllocationView
              initialBuckets={profile?.givingBuckets || []}
              initialAssignments={profile?.charityBucketAssignments?.map(a => ({
                ein: a.charityEin,
                bucketId: a.bucketId,
              })) || []}
              targetAmount={profile?.targetZakatAmount ?? null}
              bookmarkedCharities={bookmarkedCharitiesForView}
              donations={donations}
              charityTargets={charityTargets}
              onSetCharityTarget={async (ein, amount) => {
                if (amount > 0) {
                  await setCharityTarget(ein, amount);
                } else {
                  await removeCharityTarget(ein);
                }
              }}
              onSave={async (buckets, amount, assignments) => {
                await updateProfile({
                  givingBuckets: buckets,
                  targetZakatAmount: amount,
                  charityBucketAssignments: assignments.map(a => ({
                    charityEin: a.ein,
                    bucketId: a.bucketId,
                  })),
                });
              }}
              onLogDonation={(ein, name) => {
                setEditingDonation(null);
                setPrefillCharity(ein && name ? { ein, name } : null);
                setShowDonationModal(true);
              }}
              onAddCharity={async (ein, _name, bucketId) => {
                // Bookmark the charity
                await addBookmark(ein);
                // Add the assignment to profile
                const currentAssignments = profile?.charityBucketAssignments || [];
                const nextAssignments = bucketId
                  ? [
                      ...currentAssignments.filter(a => a.charityEin !== ein),
                      { charityEin: ein, bucketId },
                    ]
                  : currentAssignments.filter(a => a.charityEin !== ein);
                await updateProfile({
                  charityBucketAssignments: nextAssignments,
                });
              }}
              onRemoveCharity={async (ein) => {
                await removeBookmark(ein);
                // Also remove from assignments
                const currentAssignments = profile?.charityBucketAssignments || [];
                await updateProfile({
                  charityBucketAssignments: currentAssignments.filter(a => a.charityEin !== ein),
                });
              }}
            />

            {/* Quick stats - compact summary */}
            {(donations.length > 0 || bookmarks.length > 0) && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className={`p-4 rounded-xl border ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
                  <p className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>Donations</p>
                  <p className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    {donations.filter(d => d.zakatYear === zakatYear || new Date(d.date).getFullYear() === zakatYear).length}
                  </p>
                </div>
                <div className={`p-4 rounded-xl border ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
                  <p className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>Saved</p>
                  <p className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    {bookmarks.length}
                  </p>
                </div>
                <div className={`p-4 rounded-xl border ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
                  <p className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>Categories</p>
                  <p className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    {bucketProgress.filter(bp => bp.allocationPercent > 0).length}
                  </p>
                </div>
                <div className={`p-4 rounded-xl border ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
                  <p className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>Progress</p>
                  <p className={`text-2xl font-bold text-emerald-500`}>
                    {overallProgress.progressPercent}%
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'history' && (
          <div className={`rounded-xl border p-6 ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
            <div className="flex items-center justify-between mb-6">
              <h2 className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                Giving History
              </h2>
              <button
                onClick={() => {
                  setEditingDonation(null);
                  setShowDonationModal(true);
                }}
                className="flex items-center gap-2 px-3 py-1.5 bg-emerald-600 text-white text-sm rounded-lg hover:bg-emerald-700 transition-colors"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
                Add
              </button>
            </div>

            <GivingHistoryTable
              donations={donations}
              onEdit={(donation) => {
                setEditingDonation(donation);
                setShowDonationModal(true);
              }}
              onDelete={handleDeleteDonation}
              onExport={handleExport}
            />
          </div>
        )}

      </div>

      {/* Add/Edit Donation Modal */}
      <AddDonationModal
        isOpen={showDonationModal}
        onClose={() => {
          setShowDonationModal(false);
          setEditingDonation(null);
          setPrefillCharity(null);
        }}
        onSave={handleSaveDonation}
        existingDonation={editingDonation || undefined}
        paymentSources={getPaymentSources()}
        prefillCharity={prefillCharity || undefined}
      />
    </div>
  );
}
