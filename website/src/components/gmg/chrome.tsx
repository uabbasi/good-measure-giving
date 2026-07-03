// Shared GMG motif chrome — nav header + live typeface switcher — used by every
// motif surface (charity detail, index, …).

import React, { useState, useRef, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { signOut } from 'firebase/auth';
import { auth } from '../../auth/firebase';
import { useAuth } from '../../auth';
import {
  GmgPalette,
  gmgPalette,
  FONT_DISPLAY,
  FONT_TEXT,
  FONT_THEMES,
  resolveFontVariant,
  type FontVariant,
} from './tokens';
import { GmgLogo, Tag } from './primitives';
import { paths } from '../../lib/paths';
import { GmgSignIn } from './GmgSignIn';
import { GmgVersionStrip } from './GmgVersionStrip';
import { useIsMobile } from './useIsMobile';

// Concise desktop nav row. `active` (passed per surface) highlights the match.
const NAV_LINKS: [string, string][] = [
  ['Browse', paths.browse],
  ['Causes', paths.causes],
  ['Guides', paths.guides],
  ['Methodology', paths.methodology],
  ['About', paths.about],
];

// The mobile drawer carries the fuller set.
const MOBILE_LINKS: [string, string][] = [
  ['Browse charities', paths.browse],
  ['Causes', paths.causes],
  ['Guides', paths.guides],
  ['Zakat calculator', paths.zakatCalculator],
  ['Best Muslim charities', '/best-muslim-charities-in-usa/'],
  ['Methodology', paths.methodology],
  ['About', paths.about],
  ['FAQ', paths.faq],
];

export const GmgNav: React.FC<{ p: GmgPalette; isMobile: boolean; active?: string }> = ({
  p,
  isMobile,
  active,
}) => {
  const { isSignedIn, firstName } = useAuth();
  const [signInOpen, setSignInOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const location = useLocation();

  // Dismiss the account dropdown on outside-click, Escape, or route change.
  useEffect(() => {
    if (!menuOpen) return;
    const onDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMenuOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [menuOpen]);

  useEffect(() => {
    setMenuOpen(false);
    setMobileMenuOpen(false);
  }, [location.pathname]);

  const pill: React.CSSProperties = {
    padding: '7px 14px',
    borderRadius: 99,
    border: `1px solid ${p.rule}`,
    background: 'transparent',
    color: p.fg,
    fontSize: 12,
    fontFamily: 'inherit',
    textDecoration: 'none',
    cursor: 'pointer',
  };

  const account = isSignedIn ? (
    <div style={{ position: 'relative' }} ref={menuRef}>
      <button
        type="button"
        style={pill}
        onClick={() => setMenuOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={menuOpen}
      >
        {firstName || 'Account'} ▾
      </button>
      {menuOpen && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            right: 0,
            minWidth: 150,
            background: p.bg,
            border: `1px solid ${p.rule2}`,
            borderRadius: 10,
            boxShadow: '0 12px 30px rgba(0,0,0,0.25)',
            overflow: 'hidden',
            zIndex: 50,
          }}
        >
          <Link
            to="/profile"
            onClick={() => setMenuOpen(false)}
            style={{ display: 'block', padding: '10px 14px', fontSize: 13, color: p.fg, textDecoration: 'none' }}
          >
            Your giving
          </Link>
          <button
            type="button"
            onClick={() => { setMenuOpen(false); if (auth) signOut(auth).catch(() => {}); }}
            style={{ display: 'block', width: '100%', textAlign: 'left', padding: '10px 14px', fontSize: 13, color: p.sub, background: 'none', border: 'none', borderTop: `1px solid ${p.rule}`, cursor: 'pointer' }}
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  ) : (
    <button type="button" style={pill} onClick={() => setSignInOpen(true)}>
      Sign in
    </button>
  );

  return (
  <>
  {/* Site-wide editorial version strip — sits directly above the nav, non-sticky. */}
  <GmgVersionStrip p={p} isMobile={isMobile} />
  <header
    style={{
      display: 'flex',
      alignItems: 'center',
      gap: isMobile ? 12 : 20,
      flexWrap: 'wrap',
      padding: `12px ${isMobile ? 16 : 24}px`,
      background: p.bg,
      borderBottom: `1px solid ${p.rule}`,
    }}
  >
    <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none' }}>
      <GmgLogo p={p} size={isMobile ? 26 : 30} />
      <Tag tone="warn" p={p}>Beta</Tag>
    </Link>
    {!isMobile && (
      <nav style={{ display: 'flex', gap: 4, fontSize: 13, marginLeft: 8 }}>
        {NAV_LINKS.map(([label, to]) => (
          <Link
            key={label}
            to={to}
            style={{
              padding: '6px 12px',
              borderRadius: 6,
              color: label === active ? p.fg : p.sub,
              background: label === active ? p.bg2 : 'transparent',
              textDecoration: 'none',
            }}
          >
            {label}
          </Link>
        ))}
      </nav>
    )}
    <span style={{ flex: 1 }} />
    {isMobile && (
      <button
        type="button"
        aria-label="Menu"
        aria-expanded={mobileMenuOpen}
        onClick={() => setMobileMenuOpen((v) => !v)}
        style={{ ...pill, padding: '6px 11px', fontSize: 16, lineHeight: 1 }}
      >
        {mobileMenuOpen ? '✕' : '☰'}
      </button>
    )}
    {account}
    <GmgSignIn p={p} open={signInOpen} onClose={() => setSignInOpen(false)} />
  </header>
  {isMobile && mobileMenuOpen && (
    <nav style={{ display: 'flex', flexDirection: 'column', background: p.bg, borderBottom: `1px solid ${p.rule}` }}>
      {MOBILE_LINKS.map(([label, to]) => (
        <Link
          key={to}
          to={to}
          onClick={() => setMobileMenuOpen(false)}
          style={{ padding: '13px 16px', color: p.fg, textDecoration: 'none', fontSize: 15, borderTop: `1px solid ${p.rule}` }}
        >
          {label}
        </Link>
      ))}
    </nav>
  )}
  </>
  );
};

// Motif chrome wrapper for legacy authenticated surfaces (Profile, plan invites)
// that don't render their own motif header. Suppresses the app Navbar/Footer
// upstream and frames the page in the motif background + GmgNav so the handoff
// from a motif page into the signed-in app no longer switches design languages.
// The page body stays as-is — deep theming is a later phase.
export const GmgChromeFrame: React.FC<{
  isDark: boolean;
  requireAuth?: boolean;
  children: React.ReactNode;
}> = ({ isDark, requireAuth, children }) => {
  const p = gmgPalette(isDark);
  const isMobile = useIsMobile();
  const { isSignedIn, isLoaded } = useAuth();
  const [gateSignInOpen, setGateSignInOpen] = useState(false);
  const variant = resolveFontVariant(
    typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('type') : null,
  );
  const ft = FONT_THEMES[variant];
  const fontVars = {
    ['--gmg-display' as any]: ft.display,
    ['--gmg-text' as any]: ft.text,
    ['--gmg-mono' as any]: ft.mono,
    ['--gmg-arabic' as any]: ft.arabic,
  };

  // Auth-required surfaces (the giving plan) show a motif sign-in gate rather than
  // the legacy signed-out body — keeping the off-brand "free" CTA out of the motif.
  // Public surfaces (plan invites) pass no requireAuth and render straight through.
  const gated = requireAuth && isLoaded && !isSignedIn;

  return (
    <div style={{ background: p.bg, minHeight: '100vh', fontFamily: FONT_TEXT, ...fontVars }}>
      <GmgNav p={p} isMobile={isMobile} />
      {gated ? (
        <section style={{ maxWidth: 540, margin: '0 auto', padding: isMobile ? '64px 20px' : '104px 24px', textAlign: 'center' }}>
          <h1 style={{ fontFamily: FONT_DISPLAY, fontWeight: 400, fontSize: isMobile ? 34 : 46, lineHeight: 1.05, letterSpacing: ft.displayTracking, margin: 0 }}>
            Your <em style={{ color: p.accent }}>giving plan.</em>
          </h1>
          <p style={{ fontSize: 16, lineHeight: 1.6, color: p.sub, margin: '18px auto 28px', maxWidth: 420 }}>
            Sign in to set your giving goals, track your zakat, and follow your progress across every device.
          </p>
          <button
            type="button"
            onClick={() => setGateSignInOpen(true)}
            style={{ padding: '13px 26px', borderRadius: 99, border: 'none', background: p.accent, color: p.bg, fontSize: 15, fontWeight: 500, cursor: 'pointer' }}
          >
            Sign in
          </button>
          <GmgSignIn p={p} open={gateSignInOpen} onClose={() => setGateSignInOpen(false)} context="your giving plan" />
        </section>
      ) : (
        children
      )}
    </div>
  );
};

// Live typeface switcher — links preserve the current surface (basePath).
export const TypeSwitcher: React.FC<{ p: GmgPalette; variant: FontVariant; basePath: string }> = ({
  p,
  variant,
  basePath,
}) => (
  <>
    <span style={{ color: p.sub2 }}>TYPEFACE</span>
    {(Object.keys(FONT_THEMES) as FontVariant[]).map((v) => (
      <Link
        key={v}
        to={`${basePath}?type=${v}`}
        style={{
          padding: '2px 8px',
          borderRadius: 99,
          textDecoration: 'none',
          fontSize: 10,
          letterSpacing: '0.04em',
          border: `1px solid ${v === variant ? p.chip : p.rule}`,
          background: v === variant ? p.chip : 'transparent',
          color: v === variant ? p.chipFg : p.sub,
        }}
      >
        {FONT_THEMES[v].label}
      </Link>
    ))}
  </>
);
