/**
 * useScrollTracking - Track scroll depth on a page
 *
 * Fires analytics events at 25%, 50%, 75%, 100% scroll milestones.
 * Resets when charityId changes (navigating to new charity).
 */

import { useEffect, useCallback, useRef } from 'react';
import { trackScrollDepth, resetScrollMilestones } from '../utils/analytics';

export function useScrollTracking(charityId: string) {
  const lastScrollRef = useRef(0);
  const debounceRef = useRef<number | null>(null);

  const handleScroll = useCallback(() => {
    // Debounce scroll events
    if (debounceRef.current) {
      cancelAnimationFrame(debounceRef.current);
    }

    debounceRef.current = requestAnimationFrame(() => {
      const scrollTop = window.scrollY;
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;

      if (docHeight <= 0) return;

      const scrollPercentage = Math.min(100, Math.round((scrollTop / docHeight) * 100));

      // Only track if we've scrolled further (prevent duplicate tracking on bounce)
      if (scrollPercentage > lastScrollRef.current) {
        lastScrollRef.current = scrollPercentage;
        trackScrollDepth(charityId, scrollPercentage);
      }
    });
  }, [charityId]);

  useEffect(() => {
    // Reset when charity changes
    resetScrollMilestones();
    lastScrollRef.current = 0;

    // Track initial position (in case page is already scrolled)
    handleScroll();

    window.addEventListener('scroll', handleScroll, { passive: true });

    return () => {
      window.removeEventListener('scroll', handleScroll);
      if (debounceRef.current) {
        cancelAnimationFrame(debounceRef.current);
      }
    };
  }, [charityId, handleScroll]);
}

export default useScrollTracking;
