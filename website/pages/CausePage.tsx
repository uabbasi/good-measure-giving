import React, { useEffect, useMemo } from 'react';
import { useParams, Link, Navigate } from 'react-router-dom';
import { useCharities } from '../src/hooks/useCharities';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import { slugToCategory, filterCharitiesByCategory, type HubCharity } from '../scripts/lib/cause-seo';
import causesData from '../data/causes/causes.json';

interface CauseData {
  slug: string;
  category: string;
  displayName: string;
  intro: string;
  faq: Array<{ q: string; a: string }>;
}

const CAUSES: CauseData[] = (causesData.causes as CauseData[]);

export const CausePage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const { isDark } = useLandingTheme();
  const { summaries, loading } = useCharities();

  const cause = useMemo(() => CAUSES.find((c) => c.slug === slug), [slug]);

  useEffect(() => {
    if (cause) {
      document.title = `Best Muslim ${cause.displayName} Charities | Good Measure Giving`;
    }
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, [cause]);

  if (!slug || !cause) {
    return <Navigate to="/causes" replace />;
  }

  const category = slugToCategory(slug);
  if (!category) return <Navigate to="/causes" replace />;

  const pool: HubCharity[] = (summaries ?? []).map((c) => ({
    ein: c.ein,
    name: c.name,
    primaryCategory: c.primaryCategory ?? null,
    amalScore: c.amalScore ?? null,
    walletTag: c.walletTag ?? null,
  }));

  const charities = filterCharitiesByCategory(pool, category);

  return (
    <div className={`min-h-screen ${isDark ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-900'}`}>
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <nav aria-label="Breadcrumb" className="mb-6 text-sm text-slate-500">
          <Link to="/" className="hover:underline">Home</Link>
          <span className="mx-2">/</span>
          <Link to="/causes" className="hover:underline">Causes</Link>
          <span className="mx-2">/</span>
          <span>{cause.displayName}</span>
        </nav>

        <h1 className="text-4xl font-semibold mb-4">Best Muslim {cause.displayName} Charities</h1>
        <p className="text-lg leading-relaxed text-slate-700 dark:text-slate-300 mb-10">{cause.intro}</p>

        <section className="mb-12">
          <h2 className="text-2xl font-semibold mb-4">Evaluated Charities</h2>
          {loading ? (
            <div className="text-slate-500">Loading charities…</div>
          ) : charities.length === 0 ? (
            <div className="text-slate-500">No charities evaluated in this category yet.</div>
          ) : (
            <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {charities.map((c) => (
                <li key={c.ein}>
                  <Link
                    to={`/charity/${c.ein}`}
                    className="block p-4 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-slate-400 dark:hover:border-slate-500 transition-colors"
                  >
                    <div className="font-medium">{c.name}</div>
                    {c.amalScore != null && (
                      <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                        {c.amalScore}/100
                      </div>
                    )}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Frequently Asked Questions</h2>
          <dl>
            {cause.faq.map((item, i) => (
              <div key={i} className="mb-6">
                <dt className="font-semibold text-slate-900 dark:text-slate-100">{item.q}</dt>
                <dd className="mt-1 text-slate-700 dark:text-slate-300">{item.a}</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>
    </div>
  );
};
