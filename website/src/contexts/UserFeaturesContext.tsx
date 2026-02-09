/**
 * UserFeaturesContext - combines bookmarks, comparison, and profile
 * Provides a single context for all user feature state
 */

import React, { createContext, useContext, ReactNode } from 'react';
import { useBookmarks } from '../hooks/useBookmarks';
import { useCompare } from '../hooks/useCompare';
import { useProfile } from '../hooks/useProfile';
import type {
  Bookmark,
  UserProfile,
  GivingPriorities,
  GeographicPreference,
  FiqhPreferences,
  GivingBucket,
  CharityBucketAssignment,
} from '../../types';

interface UserFeaturesContextType {
  // Bookmarks
  bookmarks: Bookmark[];
  bookmarkedEins: Set<string>;
  isBookmarksLoading: boolean;
  bookmarksError: string | null;
  isBookmarked: (ein: string) => boolean;
  toggleBookmark: (ein: string) => Promise<void>;
  addBookmark: (ein: string, notes?: string) => Promise<void>;
  removeBookmark: (ein: string) => Promise<void>;
  updateBookmarkNotes: (ein: string, notes: string | null) => Promise<void>;
  getBookmark: (ein: string) => Bookmark | undefined;

  // Compare
  compareList: string[];
  isComparing: (ein: string) => boolean;
  canAddMore: boolean;
  addToCompare: (ein: string) => void;
  removeFromCompare: (ein: string) => void;
  toggleCompare: (ein: string) => void;
  clearCompare: () => void;
  compareCount: number;

  // Profile
  profile: UserProfile | null;
  isProfileLoading: boolean;
  profileError: string | null;
  updateProfile: (updates: Partial<{
    givingPriorities: GivingPriorities;
    geographicPreferences: GeographicPreference[];
    fiqhPreferences: FiqhPreferences;
    zakatAnniversary: string | null;
    targetZakatAmount: number | null;
    givingBuckets: GivingBucket[];
    charityBucketAssignments: CharityBucketAssignment[];
  }>) => Promise<void>;
}

const UserFeaturesContext = createContext<UserFeaturesContextType | null>(null);

interface Props {
  children: ReactNode;
}

export function UserFeaturesProvider({ children }: Props) {
  const {
    bookmarks,
    bookmarkedEins,
    isLoading: isBookmarksLoading,
    error: bookmarksError,
    isBookmarked,
    toggleBookmark,
    addBookmark,
    removeBookmark,
    updateNotes: updateBookmarkNotes,
    getBookmark,
  } = useBookmarks();

  const {
    compareList,
    isComparing,
    canAddMore,
    addToCompare,
    removeFromCompare,
    toggleCompare,
    clearCompare,
    compareCount,
  } = useCompare();

  const {
    profile,
    isLoading: isProfileLoading,
    error: profileError,
    updateProfile,
  } = useProfile();

  const value: UserFeaturesContextType = {
    // Bookmarks
    bookmarks,
    bookmarkedEins,
    isBookmarksLoading,
    bookmarksError,
    isBookmarked,
    toggleBookmark,
    addBookmark,
    removeBookmark,
    updateBookmarkNotes,
    getBookmark,

    // Compare
    compareList,
    isComparing,
    canAddMore,
    addToCompare,
    removeFromCompare,
    toggleCompare,
    clearCompare,
    compareCount,

    // Profile
    profile,
    isProfileLoading,
    profileError,
    updateProfile,
  };

  return (
    <UserFeaturesContext.Provider value={value}>
      {children}
    </UserFeaturesContext.Provider>
  );
}

export function useUserFeatures(): UserFeaturesContextType {
  const context = useContext(UserFeaturesContext);
  if (!context) {
    throw new Error('useUserFeatures must be used within a UserFeaturesProvider');
  }
  return context;
}

// Convenience hooks for specific features
export function useBookmarkState() {
  const ctx = useUserFeatures();
  return {
    bookmarks: ctx.bookmarks,
    bookmarkedEins: ctx.bookmarkedEins,
    isLoading: ctx.isBookmarksLoading,
    error: ctx.bookmarksError,
    isBookmarked: ctx.isBookmarked,
    toggleBookmark: ctx.toggleBookmark,
    addBookmark: ctx.addBookmark,
    removeBookmark: ctx.removeBookmark,
    updateNotes: ctx.updateBookmarkNotes,
    getBookmark: ctx.getBookmark,
  };
}

export function useCompareState() {
  const ctx = useUserFeatures();
  return {
    compareList: ctx.compareList,
    isComparing: ctx.isComparing,
    canAddMore: ctx.canAddMore,
    addToCompare: ctx.addToCompare,
    removeFromCompare: ctx.removeFromCompare,
    toggleCompare: ctx.toggleCompare,
    clearCompare: ctx.clearCompare,
    compareCount: ctx.compareCount,
  };
}

export function useProfileState() {
  const ctx = useUserFeatures();
  return {
    profile: ctx.profile,
    isLoading: ctx.isProfileLoading,
    error: ctx.profileError,
    updateProfile: ctx.updateProfile,
  };
}
