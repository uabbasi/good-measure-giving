import React, { useSyncExternalStore } from 'react';
import { Link } from 'react-router-dom';
import { getAnalyticsConsent, setAnalyticsConsent, type AnalyticsConsent as Choice } from '../utils/analytics';
import { useLandingTheme } from '../../contexts/LandingThemeContext';
import { gmgPalette } from './gmg/tokens';

function subscribe(onChange: () => void) {
  const storageChanged = (event: StorageEvent) => {
    if (event.key !== 'gmg_analytics_consent' && event.key !== null) return;
    // Honor a withdrawal in another tab, including unloading its running scripts.
    if (getAnalyticsConsent() !== 'accepted' && document.querySelector('script[data-cf-beacon], script[src*="googletagmanager.com"]')) {
      setAnalyticsConsent('declined');
      window.location.reload();
    }
    onChange();
  };
  window.addEventListener('analytics-consent-change', onChange);
  window.addEventListener('storage', storageChanged);
  return () => {
    window.removeEventListener('analytics-consent-change', onChange);
    window.removeEventListener('storage', storageChanged);
  };
}

export function AnalyticsConsent({ preferences = false }: { preferences?: boolean }) {
  const choice = useSyncExternalStore(subscribe, getAnalyticsConsent, () => null);
  const { isDark } = useLandingTheme();
  const p = gmgPalette(isDark);
  if (!preferences && choice !== null) return null;
  const choose = (next: Exclude<Choice, null>) => {
    setAnalyticsConsent(next);
    // Reload to unload already-running third-party scripts when consent is withdrawn.
    if (choice === 'accepted' && next === 'declined') window.location.reload();
  };
  const button: React.CSSProperties = { padding: '10px 16px', border: `1px solid ${p.rule2}`, borderRadius: 8, background: p.bg, color: p.fg, cursor: 'pointer', font: 'inherit' };
  return <section aria-label="Analytics preferences" style={{
    ...(preferences ? {} : { position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 90, boxShadow: '0 -2px 12px #0002', maxHeight: '50dvh', overflowY: 'auto' }),
    padding: '16px 20px', paddingBottom: 'max(16px, env(safe-area-inset-bottom))', background: p.bg2, color: p.fg, borderTop: `1px solid ${p.rule}`, fontSize: 14,
  }}>
    <div style={{ maxWidth: 1080, margin: '0 auto' }}>
      <p style={{ margin: '0 0 12px', lineHeight: 1.5 }}>
        {preferences ? `Optional analytics: ${choice === 'accepted' ? 'on' : 'off'}. ` : ''}
        We use Google Analytics cookies and Cloudflare analytics to understand site use. Optional analytics stay off unless you accept. Your choice does not affect sign-in or site features.{' '}
        {!preferences && <Link to="/privacy/" style={{ color: p.accent }}>Privacy and preferences</Link>}
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
        <button style={button} onClick={() => choose('accepted')}>Accept analytics</button>
        <button style={button} onClick={() => choose('declined')}>Decline analytics</button>
      </div>
    </div>
  </section>;
}
