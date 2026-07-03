// Good Measure Giving — "Modern" motif Zakat Calculator asset page
// (/zakat-calculator/:asset). Motif-only: renders its own GmgNav + footer via the
// content kit. Calculation logic + hooks are unchanged from the legacy version.

import React, { useEffect, useState } from 'react';
import { useParams, Navigate, Link } from 'react-router-dom';
import { zakatCalculatorPath, paths } from '../src/lib/paths';
import { calculateZakat } from '../src/utils/zakatCalculator';
import { useNisab, useSilverPricePerGram } from '../src/utils/nisabPrice';
import { buildChartRows, GOLD_WEIGHTS, SILVER_WEIGHTS } from '../src/utils/zakatChart';
import { ZakatMetalChart } from '../src/components/calculator/ZakatMetalChart';
import { isValidAssetSlug, KNOWN_ASSET_SLUGS } from '../scripts/lib/calculator-seo';
import { useCalculatorData } from '../src/hooks/useCalculatorData';
import {
  GmgContentFrame,
  Breadcrumb,
  ContentHero,
  Em,
  Section,
  P,
  NumberField,
  ResultCard,
  CtaLink,
  FaqList,
  type ContentCtx,
} from '../src/components/gmg/content';
import { FONT_MONO } from '../src/components/gmg/tokens';
import type { ZakatAssets } from '../types';

export const ZakatCalculatorAssetPage: React.FC<{ isDark: boolean }> = ({ isDark }) => {
  const { asset: assetSlug } = useParams<{ asset: string }>();
  const { data, loading } = useCalculatorData();
  const [assetAmount, setAssetAmount] = useState('');
  const [liabilities, setLiabilities] = useState('');
  const nisab = useNisab();
  const silverPerGram = useSilverPricePerGram();

  const asset = data?.assets.find((a) => a.slug === assetSlug);

  useEffect(() => {
    if (asset) document.title = asset.metaTitle;
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, [asset]);

  if (!assetSlug || !isValidAssetSlug(assetSlug)) {
    return <Navigate to="/zakat-calculator" replace />;
  }

  if (loading) {
    return (
      <GmgContentFrame isDark={isDark} active="Zakat calculator" maxWidth={760}>
        {({ p }: ContentCtx) => <P p={p} muted>Loading calculator…</P>}
      </GmgContentFrame>
    );
  }

  if (!asset) {
    return (
      <GmgContentFrame isDark={isDark} active="Zakat calculator" maxWidth={760}>
        {(ctx: ContentCtx) => {
          const { p } = ctx;
          return (
            <>
              <ContentHero ctx={ctx} kicker="Zakat Calculator" title="This calculator is coming soon" />
              <P p={p} muted>
                The {assetSlug.replace(/-/g, ' ')} calculator is on our roadmap. In the meantime, the cash-savings
                calculator covers the simplest zakat case.
              </P>
              <CtaLink p={p} to={paths.zakatCalculator}>← Back to all calculators</CtaLink>
            </>
          );
        }}
      </GmgContentFrame>
    );
  }

  const amountNum = parseFloat(assetAmount) || 0;
  const liabilitiesNum = parseFloat(liabilities) || 0;
  const assets: ZakatAssets = { [asset.zakatAssetKey]: amountNum };
  const estimate = calculateZakat(assets, { other: liabilitiesNum }, nisab);

  return (
    <GmgContentFrame isDark={isDark} active="Zakat calculator" maxWidth={760}>
      {(ctx: ContentCtx) => {
        const { p } = ctx;
        const displayName = asset.displayName;
        return (
          <>
            <Breadcrumb
              p={p}
              trail={[
                { label: 'Home', to: '/' },
                { label: 'Zakat Calculator', to: paths.zakatCalculator },
                { label: displayName },
              ]}
            />

            <ContentHero
              ctx={ctx}
              kicker="Zakat Calculator"
              title={<>Zakat on <Em p={p}>{displayName}</Em></>}
              lead={asset.heroAnswer}
            />

            <Section ctx={ctx} title="Calculate" first>
              <NumberField
                p={p}
                id="asset-amount-input"
                label={asset.inputLabel}
                value={assetAmount}
                onChange={setAssetAmount}
                help={asset.inputHelp}
              />
              <NumberField
                p={p}
                id="liabilities-input"
                label="Short-term liabilities (USD, optional)"
                value={liabilities}
                onChange={setLiabilities}
                help="Credit cards, personal loans, or other debts due within the lunar year."
              />

              <div style={{ marginTop: 8 }}>
                <ResultCard
                  p={p}
                  rows={[
                    { label: 'Nisab threshold (2026)', value: `$${nisab.toLocaleString()}` },
                    { label: 'Net zakatable wealth', value: `$${estimate.netZakatable.toLocaleString()}` },
                  ]}
                  resultLabel="Zakat owed (2.5%)"
                  result={estimate.isAboveNisab ? `$${estimate.zakatAmount.toLocaleString()}` : 'Below nisab — no zakat owed'}
                />
              </div>

              {estimate.isAboveNisab && estimate.zakatAmount > 0 && (
                <div style={{ marginTop: 20, display: 'flex', flexWrap: 'wrap', gap: 12 }}>
                  <CtaLink p={p} to="/browse/?zakat=eligible">See zakat-eligible charities →</CtaLink>
                  <Link
                    to="/profile"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      padding: '12px 22px',
                      borderRadius: 99,
                      border: `1px solid ${p.rule2}`,
                      background: 'transparent',
                      color: p.fg,
                      fontSize: 15,
                      fontWeight: 500,
                      textDecoration: 'none',
                    }}
                  >
                    Save this plan
                  </Link>
                </div>
              )}
            </Section>

            {asset.slug === 'gold-silver' && (
              <Section ctx={ctx} title="Gold & Silver Zakat Chart (2026)">
                <P p={p} muted>Prices update live based on current spot; refresh for the latest.</P>
                <ZakatMetalChart
                  p={p}
                  title="Gold"
                  rows={buildChartRows(nisab / 85, GOLD_WEIGHTS)}
                  nisabNote="85 g of gold is the nisab threshold for gold."
                />
                <ZakatMetalChart
                  p={p}
                  title="Silver"
                  rows={buildChartRows(silverPerGram, SILVER_WEIGHTS)}
                  nisabNote="595 g of silver is the nisab threshold (some scholars cite ~612 g)."
                />
                <p style={{ fontSize: 12, color: p.sub2, margin: '4px 0 0' }}>
                  Jewelry worn for personal use may be exempt under the majority Maliki, Shafi'i, and Hanbali view; the
                  Hanafi school holds all gold and silver zakatable. Follow the ruling of the school you adhere to.
                </p>
              </Section>
            )}

            {asset.sections.map((section, i) => (
              <Section key={i} ctx={ctx} title={section.heading}>
                {section.paragraphs.map((para, j) => (
                  <P key={j} p={p}>{para}</P>
                ))}
              </Section>
            ))}

            <Section ctx={ctx} title="Frequently Asked Questions">
              <FaqList p={p} items={asset.faq.map((f) => ({ q: f.q, a: f.a }))} />
            </Section>

            <Section ctx={ctx} title="Other calculators">
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {KNOWN_ASSET_SLUGS.filter((s) => s !== asset.slug).map((s) => (
                  <Link
                    key={s}
                    to={zakatCalculatorPath(s)}
                    style={{
                      display: 'inline-block',
                      padding: '6px 14px',
                      borderRadius: 99,
                      border: `1px solid ${p.rule2}`,
                      background: p.bg2,
                      color: p.sub,
                      fontSize: 13.5,
                      textDecoration: 'none',
                      textTransform: 'capitalize',
                      fontFamily: FONT_MONO,
                      letterSpacing: '0.02em',
                    }}
                  >
                    {s.replace(/-/g, ' ')}
                  </Link>
                ))}
              </div>
            </Section>
          </>
        );
      }}
    </GmgContentFrame>
  );
};
