/**
 * Computed hook for giving dashboard
 * Combines profile buckets, charity targets, and giving history for progress tracking
 */

import { useMemo } from 'react';
import { useProfileState } from '../contexts/UserFeaturesContext';
import { useGivingHistory } from './useGivingHistory';
import { useCharityTargets } from './useCharityTargets';
import type { GivingBucket, CharityBucketAssignment, CharitySummary } from '../../types';

export interface BucketProgress {
  bucket: GivingBucket;
  allocationPercent: number;
  targetAmount: number; // Calculated from zakat target * allocation %
  actualAmount: number; // Sum of donations in this bucket
  remainingAmount: number;
  progressPercent: number; // 0-100 (can exceed 100)
  charityCount: number;
  charities: string[]; // EINs of charities in this bucket
}

export interface CharityProgress {
  ein: string;
  charityName: string;
  bucketId?: string;
  bucketName?: string;
  targetAmount: number;
  actualAmount: number;
  remainingAmount: number;
  progressPercent: number;
}

export interface OverallProgress {
  targetAmount: number;
  actualAmount: number;
  remainingAmount: number;
  progressPercent: number;
  zakatProgress: {
    target: number;
    actual: number;
    percent: number;
  };
}

interface UseGivingDashboardResult {
  // Loading states
  isLoading: boolean;

  // Core data
  targetZakatAmount: number | null;
  zakatYear: number; // Current zakat year

  // Progress tracking
  overallProgress: OverallProgress;
  bucketProgress: BucketProgress[];
  charityProgress: CharityProgress[];

  // Legacy alias for backward compatibility
  categoryProgress: BucketProgress[];

  // Utilities
  getBucketProgress: (bucketId: string) => BucketProgress | undefined;
  getCharityProgress: (ein: string) => CharityProgress | undefined;
  getCharityBucket: (ein: string) => GivingBucket | undefined;
}

// Normalize tag for matching (lowercase, handle common variations)
function normalizeTag(tag: string): string {
  return tag.toLowerCase().replace(/[^a-z0-9]/g, '');
}

// Check if a charity matches a bucket's tags
function charityMatchesBucket(
  charity: CharitySummary,
  bucket: GivingBucket
): boolean {
  if (bucket.tags.length === 0) return false;

  const charityTags = new Set<string>();

  // Add normalized cause tags
  if (charity.causeTags) {
    for (const tag of charity.causeTags) {
      charityTags.add(normalizeTag(tag));
    }
  }

  // Add normalized geography tags (from countries/regions if available)
  // This is a simplification - real implementation would check charity's operating regions
  // For now, we rely on explicit assignments for geography

  // Check if any bucket tag matches any charity tag
  for (const bucketTag of bucket.tags) {
    const normalizedBucketTag = normalizeTag(bucketTag);
    if (charityTags.has(normalizedBucketTag)) {
      return true;
    }
    // Also check if bucket tag is contained in any charity tag
    for (const charityTag of charityTags) {
      if (charityTag.includes(normalizedBucketTag) || normalizedBucketTag.includes(charityTag)) {
        return true;
      }
    }
  }

  return false;
}

export function useGivingDashboard(
  charities?: CharitySummary[]
): UseGivingDashboardResult {
  const { profile, isLoading: profileLoading } = useProfileState();
  const { donations, isLoading: historyLoading, getYearSummary } = useGivingHistory();
  const { targetsList, isLoading: targetsLoading, getTarget } = useCharityTargets();

  const isLoading = profileLoading || historyLoading || targetsLoading;

  // Current zakat year (Islamic calendar approximation - can be refined)
  const zakatYear = useMemo(() => {
    // Use current calendar year as default zakat year
    // Users can override per-donation
    return new Date().getFullYear();
  }, []);

  const targetZakatAmount = profile?.targetZakatAmount ?? null;
  const buckets = profile?.givingBuckets ?? [];
  const assignments = profile?.charityBucketAssignments ?? [];

  // Build map of charity EIN -> assigned bucket ID
  const charityToBucket = useMemo(() => {
    const map = new Map<string, string>();
    for (const assignment of assignments) {
      map.set(assignment.charityEin, assignment.bucketId);
    }
    return map;
  }, [assignments]);

  // Build map of bucket ID -> bucket
  const bucketMap = useMemo(() => {
    return new Map(buckets.map(b => [b.id, b]));
  }, [buckets]);

  // Find which bucket a charity belongs to (explicit assignment or tag match)
  const getCharityBucketId = useMemo(() => {
    return (ein: string): string | undefined => {
      // Check explicit assignment first
      const explicitBucket = charityToBucket.get(ein);
      if (explicitBucket) return explicitBucket;

      // Try to match by tags
      if (!charities) return undefined;
      const charity = charities.find(c => c.ein === ein);
      if (!charity) return undefined;

      for (const bucket of buckets) {
        if (charityMatchesBucket(charity, bucket)) {
          return bucket.id;
        }
      }

      return undefined;
    };
  }, [charityToBucket, charities, buckets]);

  // Calculate overall progress
  const overallProgress = useMemo((): OverallProgress => {
    const target = targetZakatAmount ?? 0;
    const yearSummary = getYearSummary(zakatYear);
    const zakatActual = yearSummary.totalZakat;
    const totalActual = yearSummary.total;

    return {
      targetAmount: target,
      actualAmount: totalActual,
      remainingAmount: Math.max(0, target - totalActual),
      progressPercent: target > 0 ? Math.round((totalActual / target) * 100) : 0,
      zakatProgress: {
        target,
        actual: zakatActual,
        percent: target > 0 ? Math.round((zakatActual / target) * 100) : 0,
      },
    };
  }, [targetZakatAmount, zakatYear, getYearSummary]);

  // Calculate bucket progress
  const bucketProgress = useMemo((): BucketProgress[] => {
    const target = targetZakatAmount ?? 0;

    // Get zakat donations for the current year
    const zakatDonations = donations.filter(
      d => d.category === 'zakat' && d.zakatYear === zakatYear
    );

    return buckets.map(bucket => {
      const allocationPercent = bucket.percentage ?? 0;
      const targetAmount = Math.round((target * allocationPercent) / 100);

      // Find charities in this bucket
      const bucketCharities: string[] = [];

      // Add explicitly assigned charities
      for (const assignment of assignments) {
        if (assignment.bucketId === bucket.id) {
          bucketCharities.push(assignment.charityEin);
        }
      }

      // Add tag-matched charities (if not already assigned)
      if (charities) {
        for (const charity of charities) {
          if (!charityToBucket.has(charity.ein) && charityMatchesBucket(charity, bucket)) {
            bucketCharities.push(charity.ein);
          }
        }
      }

      const bucketCharitySet = new Set(bucketCharities);

      // Sum donations to charities in this bucket
      const bucketDonations = zakatDonations.filter(d =>
        d.charityEin && bucketCharitySet.has(d.charityEin)
      );

      const actualAmount = bucketDonations.reduce((sum, d) => sum + d.amount, 0);
      const uniqueCharities = new Set(bucketDonations.map(d => d.charityEin).filter(Boolean));

      return {
        bucket,
        allocationPercent,
        targetAmount,
        actualAmount,
        remainingAmount: Math.max(0, targetAmount - actualAmount),
        progressPercent: targetAmount > 0 ? Math.round((actualAmount / targetAmount) * 100) : 0,
        charityCount: uniqueCharities.size,
        charities: bucketCharities,
      };
    }).filter(bp => bp.allocationPercent > 0 || bp.actualAmount > 0);
  }, [targetZakatAmount, zakatYear, donations, charities, buckets, assignments, charityToBucket]);

  // Calculate per-charity progress
  const charityProgress = useMemo((): CharityProgress[] => {
    const charityToName = new Map<string, string>();

    if (charities) {
      for (const c of charities) {
        charityToName.set(c.ein, c.name);
      }
    }

    // Get all charity EINs that have targets or donations
    const relevantEins = new Set<string>();
    for (const t of targetsList) {
      relevantEins.add(t.charityEin);
    }
    for (const d of donations) {
      if (d.charityEin && d.category === 'zakat' && d.zakatYear === zakatYear) {
        relevantEins.add(d.charityEin);
      }
    }

    return Array.from(relevantEins).map(ein => {
      const targetAmount = getTarget(ein) ?? 0;
      const actualAmount = donations
        .filter(d => d.charityEin === ein && d.category === 'zakat' && d.zakatYear === zakatYear)
        .reduce((sum, d) => sum + d.amount, 0);

      // Try to get charity name from donations or charities list
      const donationName = donations.find(d => d.charityEin === ein)?.charityName;
      const charityName = charityToName.get(ein) || donationName || ein;

      // Get bucket info
      const bucketId = getCharityBucketId(ein);
      const bucket = bucketId ? bucketMap.get(bucketId) : undefined;

      return {
        ein,
        charityName,
        bucketId,
        bucketName: bucket?.name,
        targetAmount,
        actualAmount,
        remainingAmount: Math.max(0, targetAmount - actualAmount),
        progressPercent: targetAmount > 0 ? Math.round((actualAmount / targetAmount) * 100) : 0,
      };
    }).sort((a, b) => b.targetAmount - a.targetAmount || b.actualAmount - a.actualAmount);
  }, [targetsList, donations, zakatYear, charities, getTarget, getCharityBucketId, bucketMap]);

  // Utility: get progress for specific bucket
  const getBucketProgress = useMemo(() => {
    return (bucketId: string): BucketProgress | undefined => {
      return bucketProgress.find(bp => bp.bucket.id === bucketId);
    };
  }, [bucketProgress]);

  // Utility: get progress for specific charity
  const getCharityProgressUtil = useMemo(() => {
    return (ein: string): CharityProgress | undefined => {
      return charityProgress.find(cp => cp.ein === ein);
    };
  }, [charityProgress]);

  // Utility: get bucket for a charity
  const getCharityBucket = useMemo(() => {
    return (ein: string): GivingBucket | undefined => {
      const bucketId = getCharityBucketId(ein);
      return bucketId ? bucketMap.get(bucketId) : undefined;
    };
  }, [getCharityBucketId, bucketMap]);

  return {
    isLoading,
    targetZakatAmount,
    zakatYear,
    overallProgress,
    bucketProgress,
    charityProgress,
    // Legacy alias
    categoryProgress: bucketProgress,
    getBucketProgress,
    getCharityProgress: getCharityProgressUtil,
    getCharityBucket,
  };
}
