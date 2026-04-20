import React, { useEffect, useState } from 'react';
import { useParams, Link, Navigate } from 'react-router-dom';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import { calculateZakat, NISAB_USD } from '../src/utils/zakatCalculator';
import { isValidAssetSlug, KNOWN_ASSET_SLUGS } from '../scripts/lib/calculator-seo';
import type { ZakatAssets } from '../types';

interface AssetSection {
  heading: string;
  paragraphs: string[];
}

interface AssetFaq {
  q: string;
  a: string;
}

interface AssetEntry {
  slug: string;
  displayName: string;
  metaTitle: string;
  metaDescription: string;
  heroAnswer: string;
  zakatAssetKey: keyof ZakatAssets;
  inputLabel: string;
  inputHelp: string;
  sections: AssetSection[];
  faq: AssetFaq[];
}

interface CalculatorData {
  hub: { metaTitle: string; metaDescription: string; heroText: string };
  assets: AssetEntry[];
}

export const ZakatCalculatorAssetPage: React.FC = () => {
  const { asset: assetSlug } = useParams<{ asset: string }>();
  const { isDark } = useLandingTheme();
  const [data, setData] = useState<CalculatorData | null>(null);
  const [loading, setLoading] = useState(true);
  const [assetAmount, setAssetAmount] = useState('');
  const [liabilities, setLiabilities] = useState('');

  useEffect(() => {
    fetch('/data/zakat-calculator/assets.json')
      .then((r) => r.json())
      .then((d: CalculatorData) => setData(d))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

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
      <div className={`min-h-screen flex items-center justify-center ${isDark ? 'bg-slate-950' : 'bg-slate-50'}`}>
        <div className={isDark ? 'text-slate-400' : 'text-slate-600'}>Loading calculator…</div>
      </div>
    );
  }

  if (!asset) {
    return (
      <div className={`min-h-screen ${isDark ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-900'}`}>
        <div className="max-w-2xl mx-auto px-4 py-16 text-center">
          <h1 className="text-3xl font-semibold mb-4">This calculator is coming soon</h1>
          <p className="text-slate-600 dark:text-slate-400 mb-6">
            The {assetSlug.replace(/-/g, ' ')} calculator is on our roadmap. In the meantime, the cash-savings calculator covers the simplest zakat case.
          </p>
          <Link to="/zakat-calculator" className="text-emerald-600 hover:underline">← Back to all calculators</Link>
        </div>
      </div>
    );
  }

  const amountNum = parseFloat(assetAmount) || 0;
  const liabilitiesNum = parseFloat(liabilities) || 0;
  const assets: ZakatAssets = { [asset.zakatAssetKey]: amountNum };
  const estimate = calculateZakat(assets, { other: liabilitiesNum });

  return (
    <div className={`min-h-screen ${isDark ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-900'}`}>
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <nav aria-label="Breadcrumb" className="mb-6 text-sm text-slate-500">
          <Link to="/" className="hover:underline">Home</Link>
          <span className="mx-2">/</span>
          <Link to="/zakat-calculator" className="hover:underline">Zakat Calculator</Link>
          <span className="mx-2">/</span>
          <span>{asset.displayName}</span>
        </nav>

        <h1 className="text-4xl font-semibold mb-3">Zakat on {asset.displayName}</h1>
        <p className="text-lg text-slate-700 dark:text-slate-300 mb-8">{asset.heroAnswer}</p>

        <section className="mb-10 p-6 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 shadow-sm">
          <h2 className="text-xl font-semibold mb-4">Calculate</h2>
          <div className="mb-4">
            <label className="block text-sm font-medium mb-1">{asset.inputLabel}</label>
            <input
              type="number"
              inputMode="decimal"
              value={assetAmount}
              onChange={(e) => setAssetAmount(e.target.value)}
              placeholder="0"
              className="w-full px-3 py-2 rounded border border-slate-300 dark:border-slate-600 dark:bg-slate-800"
            />
            <p className="text-xs text-slate-500 mt-1">{asset.inputHelp}</p>
          </div>
          <div className="mb-6">
            <label className="block text-sm font-medium mb-1">Short-term liabilities (USD, optional)</label>
            <input
              type="number"
              inputMode="decimal"
              value={liabilities}
              onChange={(e) => setLiabilities(e.target.value)}
              placeholder="0"
              className="w-full px-3 py-2 rounded border border-slate-300 dark:border-slate-600 dark:bg-slate-800"
            />
            <p className="text-xs text-slate-500 mt-1">Credit cards, personal loans, or other debts due within the lunar year.</p>
          </div>

          <div className="p-4 rounded bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
            <div className="text-sm text-slate-600 dark:text-slate-400 mb-1">Nisab threshold (2026)</div>
            <div className="text-lg font-semibold mb-3">${NISAB_USD.toLocaleString()}</div>

            <div className="text-sm text-slate-600 dark:text-slate-400 mb-1">Net zakatable wealth</div>
            <div className="text-lg font-semibold mb-3">${estimate.netZakatable.toLocaleString()}</div>

            <div className="text-sm text-slate-600 dark:text-slate-400 mb-1">Zakat owed (2.5%)</div>
            <div className="text-3xl font-bold text-emerald-600 dark:text-emerald-400">
              {estimate.isAboveNisab ? `$${estimate.zakatAmount.toLocaleString()}` : 'Below nisab — no zakat owed'}
            </div>
          </div>

          {estimate.isAboveNisab && estimate.zakatAmount > 0 && (
            <div className="mt-6 flex flex-wrap gap-3">
              <Link
                to="/browse?zakat=eligible"
                className="inline-flex items-center px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-semibold hover:bg-emerald-700"
              >
                See zakat-eligible charities →
              </Link>
              <Link
                to="/profile"
                className="inline-flex items-center px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm font-semibold hover:border-slate-500"
              >
                Save this plan
              </Link>
            </div>
          )}
        </section>

        {asset.sections.map((section, i) => (
          <section key={i} className="mb-10">
            <h2 className="text-2xl font-semibold mb-4">{section.heading}</h2>
            {section.paragraphs.map((p, j) => (
              <p key={j} className="mb-4 leading-relaxed text-slate-700 dark:text-slate-300">{p}</p>
            ))}
          </section>
        ))}

        <section className="mb-10">
          <h2 className="text-2xl font-semibold mb-4">Frequently Asked Questions</h2>
          <dl>
            {asset.faq.map((item, i) => (
              <div key={i} className="mb-6">
                <dt className="font-semibold text-slate-900 dark:text-slate-100">{item.q}</dt>
                <dd className="mt-1 text-slate-700 dark:text-slate-300">{item.a}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Other calculators</h2>
          <ul className="flex flex-wrap gap-2">
            {KNOWN_ASSET_SLUGS.filter((s) => s !== asset.slug).map((s) => (
              <li key={s}>
                <Link to={`/zakat-calculator/${s}`} className="inline-block px-3 py-1 text-sm rounded-full border border-slate-300 dark:border-slate-700 hover:border-slate-500">
                  {s.replace(/-/g, ' ')}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
};
