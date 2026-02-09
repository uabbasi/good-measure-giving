/**
 * T007: Analytics utility functions for GA4 event tracking
 *
 * Provides typed event tracking for:
 * - Page views
 * - Charity views (with view type)
 * - Outbound clicks
 * - User flow tracking (session-level journey)
 *
 * Fails silently when gtag is blocked (graceful degradation)
 */

import type { CharityTier } from '../../types';

// View type for charity detail pages (distinct from CharityTier which is data classification)
export type CharityViewType = 'report' | 'editorial' | 'terminal' | 'niche';

// Flow step names for journey tracking
type FlowStep = 'landing' | 'browse' | 'search' | 'card_click' | 'charity_view' | 'donate' | 'sign_in';

// Extend Window interface for gtag
declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
    dataLayer?: unknown[];
  }
}

const GA_MEASUREMENT_ID = (import.meta.env.VITE_GA_MEASUREMENT_ID || '').trim();

function canInitializeAnalytics(): boolean {
  if (typeof window === 'undefined') return false;
  if (!GA_MEASUREMENT_ID) return false;

  const hostname = window.location.hostname;
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return false;
  }

  return true;
}

/**
 * Initialize Google Analytics from environment configuration.
 */
export function initializeAnalytics(): void {
  if (!canInitializeAnalytics()) return;
  if (typeof window.gtag === 'function') return;

  const script = document.createElement('script');
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`;
  document.head.appendChild(script);

  window.dataLayer = window.dataLayer || [];
  window.gtag = (...args: unknown[]) => {
    window.dataLayer!.push(args);
  };

  window.gtag('js', new Date());
  window.gtag('config', GA_MEASUREMENT_ID, {
    anonymize_ip: true,
    allow_google_signals: false,
    allow_ad_personalization_signals: false,
  });
}

// ============================================================================
// Flow Tracking - Session-level user journey
// ============================================================================

const FLOW_ID_KEY = 'gmg_flow_id';
const FLOW_PATH_KEY = 'gmg_flow_path';
const FLOW_STEP_KEY = 'gmg_flow_step';

/**
 * Generate a unique flow ID for this session
 */
function generateFlowId(): string {
  return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Get or create flow ID for this session
 */
function getFlowId(): string {
  if (typeof window === 'undefined') return '';

  let flowId = sessionStorage.getItem(FLOW_ID_KEY);
  if (!flowId) {
    flowId = generateFlowId();
    sessionStorage.setItem(FLOW_ID_KEY, flowId);
    sessionStorage.setItem(FLOW_PATH_KEY, '');
    sessionStorage.setItem(FLOW_STEP_KEY, '0');
  }
  return flowId;
}

/**
 * Get current flow path (e.g., "landing>browse>card_click")
 */
function getFlowPath(): string {
  if (typeof window === 'undefined') return '';
  return sessionStorage.getItem(FLOW_PATH_KEY) || '';
}

/**
 * Get current flow step number
 */
function getFlowStep(): number {
  if (typeof window === 'undefined') return 0;
  return parseInt(sessionStorage.getItem(FLOW_STEP_KEY) || '0', 10);
}

/**
 * Add a step to the flow path and increment step counter
 */
function addFlowStep(step: FlowStep): { flowId: string; flowPath: string; flowStep: number } {
  if (typeof window === 'undefined') {
    return { flowId: '', flowPath: '', flowStep: 0 };
  }

  const flowId = getFlowId();
  const currentPath = getFlowPath();
  const currentStep = getFlowStep();

  // Append step to path (max 10 steps to avoid huge strings)
  const pathParts = currentPath ? currentPath.split('>') : [];
  if (pathParts.length < 10) {
    pathParts.push(step);
  }
  const newPath = pathParts.join('>');
  const newStep = currentStep + 1;

  sessionStorage.setItem(FLOW_PATH_KEY, newPath);
  sessionStorage.setItem(FLOW_STEP_KEY, newStep.toString());

  return { flowId, flowPath: newPath, flowStep: newStep };
}

/**
 * Get flow data without adding a step (for events that don't advance the flow)
 */
function getFlowData(): { flowId: string; flowPath: string; flowStep: number } {
  return {
    flowId: getFlowId(),
    flowPath: getFlowPath(),
    flowStep: getFlowStep(),
  };
}

/**
 * Check if gtag is available and we're in production
 * Returns false for localhost/dev to avoid polluting analytics
 */
function isGtagAvailable(): boolean {
  if (typeof window === 'undefined') return false;
  if (typeof window.gtag !== 'function') return false;

  // Disable analytics on localhost/dev environments
  const hostname = window.location.hostname;
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return false;
  }

  return true;
}

/**
 * Safe gtag call that fails silently when blocked
 */
function safeGtag(...args: unknown[]): void {
  if (isGtagAvailable()) {
    try {
      window.gtag!(...args);
    } catch (e) {
      // Silently ignore errors (e.g., if gtag is blocked)
      console.debug('Analytics event failed:', e);
    }
  }
}

/**
 * Track page view event
 * Called on route changes
 */
export function trackPageView(path: string, title?: string): void {
  // Determine flow step based on path
  let flowStep: FlowStep | null = null;
  if (path === '/' || path === '') flowStep = 'landing';
  else if (path === '/browse' || path.startsWith('/browse')) flowStep = 'browse';

  const flow = flowStep ? addFlowStep(flowStep) : getFlowData();

  safeGtag('event', 'page_view', {
    page_path: path,
    page_title: title || document.title,
    flow_id: flow.flowId,
    flow_path: flow.flowPath,
    flow_step: flow.flowStep,
  });
}

/**
 * Track charity view event with view type information
 */
export function trackCharityView(
  charityId: string,
  charityName: string,
  viewType: CharityViewType
): void {
  const flow = addFlowStep('charity_view');

  safeGtag('event', 'charity_view', {
    charity_id: charityId,
    charity_name: charityName,
    view_type: viewType,
    flow_id: flow.flowId,
    flow_path: flow.flowPath,
    flow_step: flow.flowStep,
  });
}

/**
 * Track outbound click to charity website
 */
export function trackOutboundClick(
  charityId: string,
  charityName: string,
  destinationUrl: string
): void {
  safeGtag('event', 'outbound_click', {
    charity_id: charityId,
    charity_name: charityName,
    destination_url: destinationUrl,
  });
}

/**
 * Track charity card click from browse page
 */
export function trackCharityCardClick(
  charityId: string,
  charityName: string,
  tier: CharityTier,
  position: number
): void {
  const flow = addFlowStep('card_click');

  safeGtag('event', 'charity_card_click', {
    charity_id: charityId,
    charity_name: charityName,
    charity_tier: tier,
    list_position: position,
    flow_id: flow.flowId,
    flow_path: flow.flowPath,
    flow_step: flow.flowStep,
  });
}

/**
 * Track search interaction
 */
export function trackSearch(query: string, resultCount: number): void {
  const flow = addFlowStep('search');

  safeGtag('event', 'search', {
    search_term: query,
    result_count: resultCount,
    flow_id: flow.flowId,
    flow_path: flow.flowPath,
    flow_step: flow.flowStep,
  });
}

/**
 * Track sign-in attempts (OAuth provider clicks)
 */
export function trackSignIn(provider: 'google' | 'apple'): void {
  const flow = addFlowStep('sign_in');

  safeGtag('event', 'sign_in_start', {
    method: provider,
    flow_id: flow.flowId,
    flow_path: flow.flowPath,
    flow_step: flow.flowStep,
  });
}

/**
 * Track successful sign-ins (fired from auth state change)
 * @param provider - OAuth provider (google, apple, etc.)
 * @param authType - 'signup' for new users, 'login' for returning users
 */
export function trackSignInSuccess(provider: string, authType: 'signup' | 'login'): void {
  const flow = getFlowData(); // Don't add step, sign_in_start already did

  safeGtag('event', 'sign_in_success', {
    method: provider,
    auth_type: authType,
    flow_id: flow.flowId,
    flow_path: flow.flowPath,
    flow_step: flow.flowStep,
  });
}

/**
 * Track hero CTA clicks on landing page
 */
export function trackHeroCTA(ctaName: string, destination: string): void {
  safeGtag('event', 'hero_cta_click', {
    cta_name: ctaName,
    destination_path: destination,
  });
}

/**
 * Track donate button clicks (distinct from general outbound)
 */
export function trackDonateClick(
  charityId: string,
  charityName: string,
  destinationUrl: string
): void {
  const flow = addFlowStep('donate');

  safeGtag('event', 'donate_click', {
    charity_id: charityId,
    charity_name: charityName,
    destination_url: destinationUrl,
    flow_id: flow.flowId,
    flow_path: flow.flowPath,
    flow_step: flow.flowStep,
  });
}

/**
 * Track Similar Organization click (cross-charity navigation)
 */
export function trackSimilarOrgClick(
  fromCharityId: string,
  toCharityId: string,
  toCharityName: string,
  position: number
): void {
  const flow = getFlowData(); // Don't add step, charity_view will handle it

  safeGtag('event', 'similar_org_click', {
    from_charity_id: fromCharityId,
    to_charity_id: toCharityId,
    to_charity_name: toCharityName,
    list_position: position,
    flow_id: flow.flowId,
    flow_path: flow.flowPath,
    flow_step: flow.flowStep,
  });
}

/**
 * Track share button clicks
 */
export type ShareMethod = 'copy' | 'twitter' | 'facebook' | 'linkedin' | 'email' | 'native';

export function trackShare(
  charityId: string,
  charityName: string,
  method: ShareMethod
): void {
  safeGtag('event', 'share', {
    method,
    content_type: 'charity',
    item_id: charityId,
    charity_name: charityName,
  });
}

// ============================================================================
// Enhanced Analytics - Scroll Depth & Section Visibility
// ============================================================================

// Track which scroll milestones have been fired this session
const scrollMilestonesFired = new Set<string>();

/**
 * Track scroll depth milestones (25%, 50%, 75%, 100%)
 * Call this from a scroll handler - it deduplicates internally
 */
export function trackScrollDepth(
  charityId: string,
  scrollPercentage: number
): void {
  const milestones = [25, 50, 75, 100];

  for (const milestone of milestones) {
    if (scrollPercentage >= milestone) {
      const key = `${charityId}-${milestone}`;
      if (!scrollMilestonesFired.has(key)) {
        scrollMilestonesFired.add(key);
        safeGtag('event', 'scroll_depth', {
          charity_id: charityId,
          scroll_percentage: milestone,
        });
      }
    }
  }
}

/**
 * Reset scroll milestones (call on page navigation)
 */
export function resetScrollMilestones(): void {
  scrollMilestonesFired.clear();
}

/**
 * Track section visibility (when a section enters the viewport)
 */
export function trackSectionView(
  charityId: string,
  sectionName: string
): void {
  safeGtag('event', 'section_view', {
    charity_id: charityId,
    section_name: sectionName,
  });
}

/**
 * Track time spent on a section (call when leaving section)
 */
export function trackSectionTime(
  charityId: string,
  sectionName: string,
  timeSpentMs: number
): void {
  // Only track if spent more than 1 second
  if (timeSpentMs < 1000) return;

  safeGtag('event', 'section_time', {
    charity_id: charityId,
    section_name: sectionName,
    time_spent_seconds: Math.round(timeSpentMs / 1000),
  });
}

/**
 * Track tab/accordion clicks
 */
export function trackTabClick(
  charityId: string,
  tabName: string
): void {
  safeGtag('event', 'tab_click', {
    charity_id: charityId,
    tab_name: tabName,
  });
}

/**
 * Track external link clicks (non-donate)
 */
export function trackExternalLinkClick(
  charityId: string,
  linkType: 'website' | 'source' | 'social' | 'other',
  url: string
): void {
  safeGtag('event', 'external_link_click', {
    charity_id: charityId,
    link_type: linkType,
    destination_url: url,
  });
}

/**
 * Track report issue submission
 */
export function trackReportIssue(
  charityId: string,
  issueType: string
): void {
  safeGtag('event', 'report_issue', {
    charity_id: charityId,
    issue_type: issueType,
  });
}

/**
 * Track bookmark add/remove
 */
export function trackBookmark(
  charityId: string,
  charityName: string,
  action: 'add' | 'remove'
): void {
  safeGtag('event', 'bookmark', {
    charity_id: charityId,
    charity_name: charityName,
    bookmark_action: action,
  });
}

/**
 * Track compare toggle
 */
export function trackCompareToggle(
  charityId: string,
  charityName: string,
  action: 'add' | 'remove'
): void {
  safeGtag('event', 'compare_toggle', {
    charity_id: charityId,
    charity_name: charityName,
    compare_action: action,
  });
}

/**
 * Track filter apply on browse page
 */
export function trackFilterApply(
  filterId: string,
  filterGroup: string,
  resultCount: number
): void {
  safeGtag('event', 'filter_apply', {
    filter_id: filterId,
    filter_group: filterGroup,
    result_count: resultCount,
  });
}

/**
 * Track view toggle on charity detail page
 */
export function trackViewToggle(
  charityId: string,
  fromView: string,
  toView: string
): void {
  safeGtag('event', 'view_toggle', {
    charity_id: charityId,
    from_view: fromView,
    to_view: toView,
  });
}
