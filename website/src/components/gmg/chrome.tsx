// Shared GMG motif chrome — nav header + live typeface switcher — used by every
// motif surface (charity detail, index, …).

import React from 'react';
import { Link } from 'react-router-dom';
import { GmgPalette } from './tokens';
import { FONT_THEMES, type FontVariant } from './tokens';
import { GmgLogo, Tag } from './primitives';

export const GmgNav: React.FC<{ p: GmgPalette; isMobile: boolean; active?: string }> = ({
  p,
  isMobile,
  active,
}) => (
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
    <Link
      to="/profile"
      style={{
        padding: '7px 14px',
        borderRadius: 99,
        border: `1px solid ${p.rule}`,
        background: 'transparent',
        color: p.fg,
        fontSize: 12,
        textDecoration: 'none',
      }}
    >
      Sign in
    </Link>
  </header>
);

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
