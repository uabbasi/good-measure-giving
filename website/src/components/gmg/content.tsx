// Good Measure Giving — "Modern" motif content-page kit.
// Shared building blocks for long-form / informational pages (about, faq, guides,
// causes, calculators, …) so each converted page is concise and consistent.
// Inline-styled, palette-driven, SSR-safe — same conventions as primitives.tsx.

import React from 'react';
import { Link } from 'react-router-dom';
import {
  GmgPalette,
  gmgPalette,
  FONT_DISPLAY,
  FONT_TEXT,
  FONT_MONO,
  FONT_THEMES,
  resolveFontVariant,
  type FontTheme,
  type FontVariant,
} from './tokens';
import { GmgNav } from './chrome';
import { GmgLogo } from './primitives';
import { useIsMobile } from './useIsMobile';

// Resolve the motif font CSS vars (mirrors ChangelogPage / GmgChromeFrame).
export function useMotifFontVars(): { ft: FontTheme; fontVars: React.CSSProperties } {
  const variant: FontVariant = resolveFontVariant(
    typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('type') : null,
  );
  const ft = FONT_THEMES[variant];
  const fontVars = {
    ['--gmg-display' as any]: ft.display,
    ['--gmg-text' as any]: ft.text,
    ['--gmg-mono' as any]: ft.mono,
    ['--gmg-arabic' as any]: ft.arabic,
  } as React.CSSProperties;
  return { ft, fontVars };
}

export interface ContentCtx {
  p: GmgPalette;
  isMobile: boolean;
  ft: FontTheme;
}

// Full motif chrome for a content page: bg + font vars + GmgNav (+ version strip,
// which GmgNav renders) + footer. Render-prop hands the page the resolved palette,
// mobile flag, and font theme so it doesn't re-derive them.
export const GmgContentFrame: React.FC<{
  isDark: boolean;
  active?: string;
  maxWidth?: number;
  children: (ctx: ContentCtx) => React.ReactNode;
}> = ({ isDark, active, maxWidth = 760, children }) => {
  const p = gmgPalette(isDark);
  const isMobile = useIsMobile();
  const { ft, fontVars } = useMotifFontVars();
  const padX = isMobile ? 20 : 24;
  return (
    <div
      style={{
        background: p.bg,
        color: p.fg,
        fontFamily: FONT_TEXT,
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        ...fontVars,
      }}
    >
      <GmgNav p={p} isMobile={isMobile} active={active} />
      <main
        style={{
          flex: 1,
          width: '100%',
          maxWidth,
          margin: '0 auto',
          padding: isMobile ? `40px ${padX}px 64px` : `56px ${padX}px 88px`,
          boxSizing: 'border-box',
        }}
      >
        {children({ p, isMobile, ft })}
      </main>
      <GmgFooter p={p} isMobile={isMobile} />
    </div>
  );
};

// Breadcrumb trail — uses Router Links so SEO breadcrumb URLs stay well-formed.
export const Breadcrumb: React.FC<{ p: GmgPalette; trail: { label: string; to?: string }[] }> = ({ p, trail }) => (
  <nav
    aria-label="Breadcrumb"
    style={{ fontFamily: FONT_MONO, fontSize: 11, letterSpacing: '0.04em', color: p.sub2, marginBottom: 18 }}
  >
    {trail.map((c, i) => (
      <span key={c.label}>
        {i > 0 && <span style={{ margin: '0 8px', color: p.rule2 }}>/</span>}
        {c.to ? (
          <Link to={c.to} style={{ color: p.sub, textDecoration: 'none' }}>
            {c.label}
          </Link>
        ) : (
          <span style={{ color: p.sub2 }}>{c.label}</span>
        )}
      </span>
    ))}
  </nav>
);

// Page hero — optional kicker, display-serif h1 (optional accent emphasis), lead.
export const ContentHero: React.FC<{
  ctx: ContentCtx;
  kicker?: string;
  title: React.ReactNode;
  lead?: React.ReactNode;
}> = ({ ctx, kicker, title, lead }) => {
  const { p, isMobile, ft } = ctx;
  return (
    <header style={{ marginBottom: isMobile ? 36 : 48 }}>
      {kicker && (
        <div
          style={{
            fontFamily: FONT_MONO,
            fontSize: 11,
            letterSpacing: '0.18em',
            textTransform: 'uppercase',
            color: p.accent2,
            marginBottom: 18,
          }}
        >
          {kicker}
        </div>
      )}
      <h1
        style={{
          fontFamily: FONT_DISPLAY,
          fontWeight: 400,
          fontSize: isMobile ? 36 : 50,
          lineHeight: 1.06,
          letterSpacing: ft.displayTracking,
          margin: 0,
        }}
      >
        {title}
      </h1>
      {lead && (
        <p style={{ fontSize: isMobile ? 16 : 19, lineHeight: 1.6, color: p.sub, margin: '20px 0 0', maxWidth: 640 }}>
          {lead}
        </p>
      )}
    </header>
  );
};

// Emphasis span for hero titles — `<Em>word.</Em>` renders in the sage accent.
export const Em: React.FC<{ p: GmgPalette; children: React.ReactNode }> = ({ p, children }) => (
  <em style={{ color: p.accent, fontStyle: 'italic' }}>{children}</em>
);

// Titled section with a hairline top rule (suppressed on the first section).
export const Section: React.FC<{
  ctx: ContentCtx;
  title?: React.ReactNode;
  first?: boolean;
  children: React.ReactNode;
}> = ({ ctx, title, first, children }) => {
  const { p, isMobile } = ctx;
  return (
    <section
      style={{
        marginTop: first ? 0 : isMobile ? 36 : 52,
        paddingTop: first ? 0 : isMobile ? 28 : 40,
        borderTop: first ? 'none' : `1px solid ${p.rule}`,
      }}
    >
      {title && (
        <h2
          style={{
            fontFamily: FONT_DISPLAY,
            fontWeight: 400,
            fontSize: isMobile ? 24 : 30,
            lineHeight: 1.15,
            letterSpacing: '-0.01em',
            margin: '0 0 18px',
          }}
        >
          {title}
        </h2>
      )}
      {children}
    </section>
  );
};

// Body paragraph.
export const P: React.FC<{ p: GmgPalette; children: React.ReactNode; muted?: boolean }> = ({ p, children, muted }) => (
  <p style={{ fontSize: 16, lineHeight: 1.7, color: muted ? p.sub : p.fg, margin: '0 0 14px' }}>{children}</p>
);

// Subsection heading.
export const H3: React.FC<{ p: GmgPalette; children: React.ReactNode }> = ({ p, children }) => (
  <h3 style={{ fontSize: 17, fontWeight: 600, color: p.fg, margin: '0 0 8px', fontFamily: FONT_TEXT }}>{children}</h3>
);

// Inline accent link (Router Link).
export const ALink: React.FC<{ p: GmgPalette; to: string; children: React.ReactNode }> = ({ p, to, children }) => (
  <Link to={to} style={{ color: p.accent, textDecoration: 'none', fontWeight: 500 }}>
    {children}
  </Link>
);

// Bulleted list with sage markers.
export const UL: React.FC<{ p: GmgPalette; items: React.ReactNode[] }> = ({ p, items }) => (
  <ul style={{ listStyle: 'none', margin: '0 0 14px', padding: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
    {items.map((it, i) => (
      <li key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
        <span
          style={{ marginTop: 9, width: 5, height: 5, borderRadius: 99, background: p.accent2, flexShrink: 0 }}
          aria-hidden="true"
        />
        <span style={{ fontSize: 15, lineHeight: 1.65, color: p.fg }}>{it}</span>
      </li>
    ))}
  </ul>
);

type CalloutTone = 'info' | 'pos' | 'caution' | 'neutral';

// Highlighted callout box (TL;DR, disclaimers, context). Tones map to the motif's
// semantic palette so they're never the off-brand emerald/blue/amber Tailwind set.
export const Callout: React.FC<{
  p: GmgPalette;
  tone?: CalloutTone;
  title?: React.ReactNode;
  children: React.ReactNode;
}> = ({ p, tone = 'info', title, children }) => {
  const tones: Record<CalloutTone, { bg: string; border: string; label: string }> = {
    info: { bg: p.bg2, border: p.rule2, label: p.accent2 },
    pos: { bg: p.posBg, border: p.pos, label: p.pos },
    caution: { bg: p.cautionBg, border: p.caution, label: p.caution },
    neutral: { bg: p.bg3, border: p.rule, label: p.sub },
  };
  const t = tones[tone];
  return (
    <div
      style={{
        background: t.bg,
        border: `1px solid ${t.border}`,
        borderRadius: 12,
        padding: '16px 18px',
        margin: '0 0 14px',
      }}
    >
      {title && (
        <div
          style={{
            fontFamily: FONT_MONO,
            fontSize: 10,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            color: t.label,
            marginBottom: 8,
          }}
        >
          {title}
        </div>
      )}
      <div style={{ fontSize: 15, lineHeight: 1.65, color: p.fg }}>{children}</div>
    </div>
  );
};

// Responsive auto-fill grid for cards.
export const CardGrid: React.FC<{ children: React.ReactNode; min?: number }> = ({ children, min = 240 }) => (
  <div style={{ display: 'grid', gridTemplateColumns: `repeat(auto-fill, minmax(${min}px, 1fr))`, gap: 14 }}>
    {children}
  </div>
);

// Link card — title + description (+ optional meta line), the whole block clickable.
export const LinkCard: React.FC<{
  p: GmgPalette;
  to: string;
  title: React.ReactNode;
  desc?: React.ReactNode;
  meta?: React.ReactNode;
}> = ({ p, to, title, desc, meta }) => (
  <Link
    to={to}
    style={{
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      padding: '16px 18px',
      borderRadius: 12,
      border: `1px solid ${p.rule}`,
      background: p.card,
      textDecoration: 'none',
      color: p.fg,
      height: '100%',
      boxSizing: 'border-box',
    }}
  >
    <span style={{ fontFamily: FONT_DISPLAY, fontSize: 18, lineHeight: 1.2, color: p.fg }}>{title}</span>
    {desc && <span style={{ fontSize: 13.5, lineHeight: 1.55, color: p.sub }}>{desc}</span>}
    {meta && (
      <span style={{ fontFamily: FONT_MONO, fontSize: 10.5, letterSpacing: '0.06em', textTransform: 'uppercase', color: p.sub2, marginTop: 'auto', paddingTop: 6 }}>
        {meta}
      </span>
    )}
  </Link>
);

// FAQ list — questions stay visible (open) so the page text matches the FAQPage
// JSON-LD schema emitted by the prerenderer.
export const FaqList: React.FC<{ p: GmgPalette; items: { q: string; a: React.ReactNode }[] }> = ({ p, items }) => (
  <dl style={{ margin: 0 }}>
    {items.map((it, i) => (
      <div key={i} style={{ padding: '18px 0', borderTop: i === 0 ? 'none' : `1px solid ${p.rule}` }}>
        <dt style={{ fontSize: 16, fontWeight: 600, color: p.fg, marginBottom: 8 }}>{it.q}</dt>
        <dd style={{ margin: 0, fontSize: 15, lineHeight: 1.65, color: p.sub }}>{it.a}</dd>
      </div>
    ))}
  </dl>
);

// Labeled numeric input — motif-styled form field for the calculators.
// Renders in the initial HTML (no loading gate) so crawlers see the form.
export const NumberField: React.FC<{
  p: GmgPalette;
  id: string;
  label: React.ReactNode;
  value: string;
  onChange: (v: string) => void;
  help?: React.ReactNode;
  placeholder?: string;
}> = ({ p, id, label, value, onChange, help, placeholder = '0' }) => (
  <div style={{ marginBottom: 16 }}>
    <label htmlFor={id} style={{ display: 'block', fontSize: 13.5, fontWeight: 600, color: p.fg, marginBottom: 6 }}>
      {label}
    </label>
    <input
      id={id}
      type="number"
      inputMode="decimal"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      style={{
        width: '100%',
        padding: '10px 12px',
        background: p.bg,
        border: `1px solid ${p.rule}`,
        color: p.fg,
        borderRadius: 10,
        fontSize: 15,
        fontFamily: FONT_TEXT,
        boxSizing: 'border-box',
      }}
    />
    {help && <p style={{ fontSize: 12, color: p.sub2, margin: '6px 0 0' }}>{help}</p>}
  </div>
);

// Highlighted result box — labeled rows + a prominent computed figure (positive tone).
export const ResultCard: React.FC<{
  p: GmgPalette;
  rows?: { label: React.ReactNode; value: React.ReactNode }[];
  resultLabel: React.ReactNode;
  result: React.ReactNode;
}> = ({ p, rows, resultLabel, result }) => (
  <div style={{ background: p.posBg, border: `1px solid ${p.pos}`, borderRadius: 12, padding: '16px 18px' }}>
    {rows?.map((r, i) => (
      <React.Fragment key={i}>
        <div style={{ fontSize: 13, color: p.sub, marginBottom: 2 }}>{r.label}</div>
        <div style={{ fontSize: 17, fontWeight: 600, color: p.fg, marginBottom: 12 }}>{r.value}</div>
      </React.Fragment>
    ))}
    <div style={{ fontSize: 13, color: p.sub, marginBottom: 2 }}>{resultLabel}</div>
    <div style={{ fontFamily: FONT_DISPLAY, fontSize: 30, lineHeight: 1.1, color: p.accent }}>{result}</div>
  </div>
);

// Primary pill CTA (Router Link).
export const CtaLink: React.FC<{ p: GmgPalette; to: string; children: React.ReactNode }> = ({ p, to, children }) => (
  <Link
    to={to}
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 8,
      padding: '12px 24px',
      borderRadius: 99,
      background: p.accent,
      color: p.bg,
      fontSize: 15,
      fontWeight: 500,
      textDecoration: 'none',
    }}
  >
    {children}
  </Link>
);

// Motif footer — the tail chrome the full-bleed pages never had. Compact link
// columns + tagline, palette-driven.
export const GmgFooter: React.FC<{ p: GmgPalette; isMobile: boolean }> = ({ p, isMobile }) => {
  const cols: { heading: string; links: { label: string; to: string }[] }[] = [
    {
      heading: 'Evaluate',
      links: [
        { label: 'Browse charities', to: '/browse' },
        { label: 'Best Muslim charities', to: '/best-muslim-charities-in-usa' },
        { label: 'Causes', to: '/causes' },
        { label: 'Compare', to: '/compare' },
      ],
    },
    {
      heading: 'Learn',
      links: [
        { label: 'Methodology', to: '/methodology' },
        { label: 'Guides', to: '/guides' },
        { label: 'Zakat calculator', to: '/zakat-calculator' },
        { label: 'FAQ', to: '/faq' },
      ],
    },
    {
      heading: 'About',
      links: [
        { label: 'About', to: '/about' },
        { label: 'AI transparency', to: '/prompts' },
        { label: 'Link to us', to: '/link-to-us' },
        { label: 'Changelog', to: '/changelog' },
      ],
    },
  ];
  return (
    <footer style={{ borderTop: `1px solid ${p.rule}`, background: p.bg2, marginTop: 'auto' }}>
      <div
        style={{
          maxWidth: 1080,
          margin: '0 auto',
          padding: isMobile ? '36px 20px' : '48px 24px',
          display: 'grid',
          gridTemplateColumns: isMobile ? '1fr 1fr' : '1.4fr repeat(3, 1fr)',
          gap: isMobile ? 28 : 32,
        }}
      >
        <div style={{ gridColumn: isMobile ? '1 / -1' : 'auto' }}>
          <GmgLogo p={p} size={26} />
          <p style={{ fontSize: 13, lineHeight: 1.6, color: p.sub, margin: '14px 0 0', maxWidth: 260 }}>
            Rigorous, independent charity research for Muslim donors.
          </p>
        </div>
        {cols.map((col) => (
          <div key={col.heading}>
            <div
              style={{
                fontFamily: FONT_MONO,
                fontSize: 10,
                letterSpacing: '0.14em',
                textTransform: 'uppercase',
                color: p.sub2,
                marginBottom: 12,
              }}
            >
              {col.heading}
            </div>
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 9 }}>
              {col.links.map((l) => (
                <li key={l.to}>
                  <Link to={l.to} style={{ fontSize: 13.5, color: p.sub, textDecoration: 'none' }}>
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div
        style={{
          borderTop: `1px solid ${p.rule}`,
          padding: isMobile ? '16px 20px' : '18px 24px',
          maxWidth: 1080,
          margin: '0 auto',
          display: 'flex',
          flexWrap: 'wrap',
          gap: 12,
          justifyContent: 'space-between',
          fontSize: 12,
          color: p.sub2,
        }}
      >
        <span>© {new Date().getUTCFullYear()} Good Measure Giving</span>
        <span style={{ display: 'flex', gap: 16 }}>
          <Link to="/privacy" style={{ color: p.sub2, textDecoration: 'none' }}>
            Privacy
          </Link>
        </span>
      </div>
    </footer>
  );
};
