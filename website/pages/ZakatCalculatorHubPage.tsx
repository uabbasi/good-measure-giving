import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import { KNOWN_ASSET_SLUGS } from '../scripts/lib/calculator-seo';

interface AssetSummary {
  slug: string;
  displayName: string;
  heroAnswer: string;
}

interface CalculatorData {
  hub: { metaTitle: string; metaDescription: string; heroText: string };
  assets: AssetSummary[];
}

const SLUG_TO_LABEL: Record<string, string> = {
  'cash-savings': 'Cash & Savings',
  'gold-silver': 'Gold & Silver',
  'stocks': 'Stocks & Investments',
  '401k-retirement': '401(k) & Retirement',
  'crypto': 'Cryptocurrency',
  'business-assets': 'Business Assets',
  'real-estate': 'Real Estate',
};

export const ZakatCalculatorHubPage: React.FC = () => {
  const { isDark } = useLandingTheme();
  const [data, setData] = useState<CalculatorData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    document.title = 'Zakat Calculator 2026 | Good Measure Giving';
    fetch('/data/zakat-calculator/assets.json')
      .then((r) => r.json())
      .then((d: CalculatorData) => setData(d))
      .catch(() => setData(null))
      .finally(() => setLoading(false));

    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, []);

  const availableSlugs = new Set((data?.assets || []).map((a) => a.slug));

  return (
    <div className={`min-h-screen ${isDark ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-900'}`}>
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <nav aria-label="Breadcrumb" className="mb-6 text-sm text-slate-500">
          <Link to="/" className="hover:underline">Home</Link>
          <span className="mx-2">/</span>
          <span>Zakat Calculator</span>
        </nav>

        <h1 className="text-4xl font-semibold mb-4">Zakat Calculator 2026</h1>
        <p className="text-lg leading-relaxed text-slate-700 dark:text-slate-300 mb-10">
          {data?.hub.heroText ?? 'Calculate the zakat owed on your assets. Start with the asset type most relevant to you.'}
        </p>

        {loading ? (
          <div className="text-slate-500">Loading…</div>
        ) : (
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {KNOWN_ASSET_SLUGS.map((slug) => {
              const available = availableSlugs.has(slug);
              const label = SLUG_TO_LABEL[slug] ?? slug.replace(/-/g, ' ');
              return (
                <li key={slug}>
                  <Link
                    to={`/zakat-calculator/${slug}`}
                    className={`block p-5 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-slate-400 dark:hover:border-slate-500 transition-colors ${available ? '' : 'opacity-60'}`}
                  >
                    <div className="flex items-center justify-between">
                      <h2 className="text-xl font-semibold">Zakat on {label}</h2>
                      {!available && (
                        <span className="text-xs uppercase tracking-wide text-slate-500">Coming soon</span>
                      )}
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
};
