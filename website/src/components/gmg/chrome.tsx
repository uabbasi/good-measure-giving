// Shared GMG motif chrome — nav header + live typeface switcher — used by every
// motif surface (charity detail, index, …).

import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { signOut } from 'firebase/auth';
import { auth } from '../../auth/firebase';
import { useAuth } from '../../auth';
import { GmgPalette } from './tokens';
import { FONT_THEMES, type FontVariant } from './tokens';
import { GmgLogo, Tag } from './primitives';
import { GmgSignIn } from './GmgSignIn';

export const GmgNav: React.FC<{ p: GmgPalette; isMobile: boolean; active?: string }> = ({
  p,
  isMobile,
  active,
}) => {
  const { isSignedIn, firstName } = useAuth();
  const [signInOpen, setSignInOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

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
    <div style={{ position: 'relative' }}>
      <button type="button" style={pill} onClick={() => setMenuOpen((v) => !v)}>
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
            onClick={() => { setMenuOpen(false); if (auth) signOut(auth); }}
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
        {[
          ['Browse', '/browse?design=gmg'],
          ['Compare', '/compare?design=gmg'],
          ['Methodology', '/methodology'],
          ['About', '/about'],
        ].map(([label, to]) => (
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
    {account}
    <GmgSignIn p={p} open={signInOpen} onClose={() => setSignInOpen(false)} />
  </header>
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
        to={`${basePath}?design=gmg&type=${v}`}
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
