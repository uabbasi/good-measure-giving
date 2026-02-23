import { useRef, useCallback, useEffect } from 'react';
import { driver, type DriveStep } from 'driver.js';
import 'driver.js/dist/driver.css';
import './tourTheme.css';
import { useNuxState, type NuxKey } from '../hooks/useNuxState';

/**
 * Find the first *visible* element matching a selector.
 * Components like RecommendationCue render in both mobile (lg:hidden)
 * and desktop (hidden lg:block) layouts. querySelector returns the first
 * DOM match regardless of visibility, so Driver.js would target a hidden
 * instance and render a detached popover. This helper picks the instance
 * the user can actually see.
 */
function findVisibleElement(selector: string): HTMLElement | null {
  const elements = document.querySelectorAll<HTMLElement>(selector);
  for (const el of elements) {
    // offsetParent is null for display:none elements (except body/fixed)
    // Also check dimensions as a fallback
    if (el.offsetParent !== null || el.offsetWidth > 0 || el.offsetHeight > 0) {
      return el;
    }
  }
  return null;
}

export function useTour(tourKey: NuxKey, steps: DriveStep[]) {
  const nux = useNuxState(tourKey);
  const driverRef = useRef<ReturnType<typeof driver> | null>(null);

  const startTour = useCallback(() => {
    if (!nux.shouldShow) return;

    // Resolve each step to a visible element, skip steps with no visible target
    const available = steps
      .map((s) => {
        if (!s.element) return s; // centered modal — keep as-is
        const visible = findVisibleElement(s.element as string);
        if (!visible) return null; // element hidden or missing — skip
        return { ...s, element: visible };
      })
      .filter((s): s is DriveStep => s !== null);

    if (available.length === 0) return;

    driverRef.current = driver({
      showProgress: true,
      smoothScroll: true,
      popoverClass: 'gmg-tour',
      allowClose: true,
      steps: available,
      onDestroyStarted: () => {
        nux.dismiss();
        if (typeof window.gtag === 'function') {
          window.gtag('event', 'tour_complete', { tour: tourKey });
        }
        driverRef.current?.destroy();
      },
    });
    driverRef.current.drive();
  }, [nux.shouldShow, steps, tourKey]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      driverRef.current?.destroy();
    };
  }, []);

  return { shouldShow: nux.shouldShow, startTour, dismiss: nux.dismiss };
}
