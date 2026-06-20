// Good Measure Giving — "Modern" motif primitives.
// Ported from the claude.ai design handoff. Inline-styled and self-contained so
// the motif stays isolated from the app's Tailwind theme while we evaluate it.

import React from 'react';
import { GmgPalette, FONT_DISPLAY, FONT_MONO, FONT_ARABIC } from './tokens';
import { Rating, RATING_SCALE, ratingColor } from './rating';

// Harvey ball — sector-filled rating dot (Strong=full … Weak=empty).
export const HarveyBall = React.memo(function HarveyBall({
  rating,
  size = 14,
  p,
}: {
  rating: Rating;
  size?: number;
  p: GmgPalette;
}) {
  const fill = RATING_SCALE[rating].fill;
  const color = ratingColor(rating, p);
  const r = size / 2;
  const sectorPath = (frac: number): string => {
    if (frac <= 0) return '';
    if (frac >= 1)
      return `M ${r} ${r} m -${r} 0 a ${r} ${r} 0 1 0 ${size} 0 a ${r} ${r} 0 1 0 -${size} 0 Z`;
    const angle = frac * 2 * Math.PI;
    const x2 = r + r * Math.sin(angle);
    const y2 = r - r * Math.cos(angle);
    const large = frac > 0.5 ? 1 : 0;
    return `M ${r} ${r} L ${r} 0 A ${r} ${r} 0 ${large} 1 ${x2} ${y2} Z`;
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      style={{ display: 'inline-block', verticalAlign: 'middle', flexShrink: 0 }}
      aria-hidden="true"
    >
      <circle cx={r} cy={r} r={r - 0.5} fill="none" stroke={color} strokeWidth="1" opacity="0.4" />
      {fill > 0 && <path d={sectorPath(fill)} fill={color} />}
    </svg>
  );
});

// Rating word + ball.
export const RatingLabel: React.FC<{ rating: Rating; p: GmgPalette; size?: number }> = ({
  rating,
  p,
  size = 13,
}) => (
  <span
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      color: ratingColor(rating, p),
      fontWeight: 500,
      fontSize: size,
    }}
  >
    <HarveyBall rating={rating} p={p} size={size + 1} />
    {rating}
  </span>
);

// Eight-pointed star (Rub el Hizb) — structural brand mark.
export const Star8: React.FC<{
  size?: number;
  color?: string;
  fill?: string;
  strokeWidth?: number;
}> = ({ size = 14, color = 'currentColor', fill = 'none', strokeWidth = 1.2 }) => (
  <svg
    width={size}
    height={size}
    viewBox="-12 -12 24 24"
    fill={fill}
    stroke={color}
    strokeWidth={strokeWidth}
    aria-hidden="true"
  >
    <polygon points="0,-10 2.4,-2.4 10,0 2.4,2.4 0,10 -2.4,2.4 -10,0 -2.4,-2.4" />
  </svg>
);

type TagTone =
  | 'default'
  | 'solid'
  | 'accent'
  | 'warn'
  | 'danger'
  | 'muted'
  | 'pos'
  | 'caution'
  | 'neg';

export const Tag = React.memo(function Tag({
  children,
  tone = 'default',
  p,
}: {
  children: React.ReactNode;
  tone?: TagTone;
  p: GmgPalette;
}) {
  const styles: Record<TagTone, { bg: string; fg: string; border: string }> = {
    default: { bg: 'transparent', fg: p.sub, border: p.rule },
    solid: { bg: p.chip, fg: p.chipFg, border: p.chip },
    accent: { bg: p.accent, fg: p.bg, border: p.accent },
    warn: { bg: p.warnBg, fg: p.warn, border: p.warnBg },
    danger: { bg: 'transparent', fg: p.danger, border: p.danger },
    muted: { bg: p.bg3, fg: p.sub, border: p.bg3 },
    pos: { bg: p.posBg, fg: p.pos, border: p.posBg },
    caution: { bg: p.cautionBg, fg: p.caution, border: p.cautionBg },
    neg: { bg: p.negBg, fg: p.neg, border: p.negBg },
  };
  const s = styles[tone];
  return (
    <span
      style={{
        padding: '3px 8px',
        borderRadius: 99,
        background: s.bg,
        color: s.fg,
        border: `1px solid ${s.border}`,
        fontFamily: FONT_MONO,
        fontSize: 9.5,
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        whiteSpace: 'nowrap',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
      }}
    >
      {children}
    </span>
  );
});

export const Kicker = React.memo(function Kicker({
  children,
  p,
}: {
  children: React.ReactNode;
  p: GmgPalette;
}) {
  return (
    <span
      style={{
        fontFamily: FONT_MONO,
        fontSize: 10,
        letterSpacing: '0.18em',
        textTransform: 'uppercase',
        color: p.sub,
      }}
    >
      {children}
    </span>
  );
});

export const Bar: React.FC<{
  value: number;
  max?: number;
  color: string;
  bg: string;
  h?: number;
}> = ({ value, max = 100, color, bg, h = 4 }) => (
  <div style={{ height: h, width: '100%', background: bg, borderRadius: 99, overflow: 'hidden' }}>
    <div
      style={{
        height: '100%',
        width: `${Math.max(0, Math.min(100, (value / max) * 100))}%`,
        background: color,
        borderRadius: 99,
      }}
    />
  </div>
);

export const Stacked: React.FC<{ segs: { pct: number; color: string }[]; h?: number }> = ({
  segs,
  h = 6,
}) => (
  <div style={{ display: 'flex', height: h, borderRadius: 99, overflow: 'hidden', width: '100%' }}>
    {segs.map((s, i) => (
      <div key={i} style={{ width: `${s.pct}%`, background: s.color }} />
    ))}
  </div>
);

export const Bismillah: React.FC<{ p: GmgPalette }> = ({ p }) => (
  <div
    style={{
      background: p.bg2,
      borderBottom: `1px solid ${p.rule}`,
      padding: '8px 24px',
      textAlign: 'center',
    }}
  >
    <span dir="rtl" lang="ar" style={{ fontFamily: FONT_ARABIC, fontSize: 19, color: p.accent, lineHeight: 1.6 }}>
      بِسْمِ ٱللَّٰهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ
    </span>
  </div>
);

// Brand mark — the existing two-square octagram + center dot, recolored to the
// motif's sage accent, with the stacked wordmark in the motif type.
export const GmgLogo: React.FC<{ p: GmgPalette; size?: number }> = ({ p, size = 30 }) => (
  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}>
    <svg width={size} height={size} viewBox="0 0 40 40" style={{ flexShrink: 0 }} aria-hidden="true">
      <rect width="40" height="40" rx="10" fill={p.accent} />
      <g transform="translate(20, 20)">
        <rect x="-9" y="-9" width="18" height="18" rx="1" stroke={p.bg} strokeWidth="2" fill="none" />
        <rect x="-9" y="-9" width="18" height="18" rx="1" stroke={p.bg} strokeWidth="2" fill="none" transform="rotate(45)" />
        <circle cx="0" cy="0" r="3" fill={p.bg} />
      </g>
    </svg>
    <span style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.05 }}>
      <span style={{ fontFamily: FONT_DISPLAY, fontSize: size * 0.62, color: p.fg, letterSpacing: '-0.01em' }}>
        Good Measure
      </span>
      <span style={{ fontFamily: FONT_MONO, fontSize: size * 0.3, color: p.accent, textTransform: 'uppercase', letterSpacing: '0.28em', fontWeight: 500 }}>
        Giving
      </span>
    </span>
  </span>
);

// Display-serif numeral used for stat values / score figures.
export const Figure = React.memo(function Figure({
  children,
  size = 24,
  color,
  italic,
}: {
  children: React.ReactNode;
  size?: number;
  color: string;
  italic?: boolean;
}) {
  return (
    <span
      style={{
        fontFamily: FONT_DISPLAY,
        fontStyle: italic ? 'italic' : 'normal',
        fontSize: size,
        lineHeight: 1,
        color,
        letterSpacing: '-0.02em',
      }}
    >
      {children}
    </span>
  );
});
