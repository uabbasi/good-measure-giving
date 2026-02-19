/**
 * useSectionTracking - Track which sections users view and how long they spend
 *
 * Uses IntersectionObserver to detect when sections enter/leave the viewport.
 * Fires trackSectionView on entry and trackSectionTime on exit.
 */

import { useEffect, useRef } from 'react';
import { trackSectionView, trackSectionTime } from '../utils/analytics';

export function useSectionTracking(charityId: string) {
  const containerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !charityId) return;

    const sections = container.querySelectorAll<HTMLElement>('[data-section]');
    if (sections.length === 0) return;

    const entryTimes = new Map<string, number>();
    const viewed = new Set<string>();

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const name = (entry.target as HTMLElement).dataset.section;
          if (!name) return;

          if (entry.isIntersecting) {
            if (!viewed.has(name)) {
              trackSectionView(charityId, name);
              viewed.add(name);
            }
            entryTimes.set(name, Date.now());
          } else {
            const startTime = entryTimes.get(name);
            if (startTime) {
              trackSectionTime(charityId, name, Date.now() - startTime);
              entryTimes.delete(name);
            }
          }
        });
      },
      { threshold: 0.3 }
    );

    sections.forEach((el) => observer.observe(el));

    return () => {
      // Fire time events for any sections still visible on unmount
      entryTimes.forEach((startTime, name) => {
        trackSectionTime(charityId, name, Date.now() - startTime);
      });
      observer.disconnect();
    };
  }, [charityId]);

  return containerRef;
}

export default useSectionTracking;
