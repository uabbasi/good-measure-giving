import React, { useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useCharities } from '../src/hooks/useCharities';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import { filterMuslimCharities, type HubCharity } from '../scripts/lib/muslim-hub';
import hubData from '../data/best-muslim-charities.json';

interface HubCopy {
  intro: string;
  introSecondary: string;
  faq: Array<{ q: string; a: string }>;
}

const COPY = hubData as HubCopy;
const TOP_N = 20;

export const BestMuslimCharitiesPage: React.FC = () => {
  const { isDark } = useLandingTheme();
  const { summaries, loading } = useCharities();
  const year = new Date().getFullYear();

  useEffect(() => {
    document.title = `Best Muslim Charities in the USA (${year}) | Good Measure Giving`;
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, [year]);

  const { ranked, pending } = useMemo(() => {
    const pool: HubCharity[] = (summaries ?? []).map((c) => ({
      ein: c.ein,
      name: c.name,
      primaryCategory: c.primaryCategory ?? null,
      amalScore: c.amalScore ?? null,
      walletTag: c.walletTag ?? null,
      isMuslimCharity: c.isMuslimCharity,
      hideFromCurated: c.hideFromCurated,
    }));
    const all = filterMuslimCharities(pool);
    return {
      ranked: all.filter((c) => c.amalScore != null),
      pending: all.filter((c) => c.amalScore == null),
    };
  }, [summaries]);

  const topRanked = ranked.slice(0, TOP_N);
  const remainingRanked = ranked.slice(TOP_N);

  const isZakatEligible = (c: HubCharity) => c.walletTag === 'ZAKAT-ELIGIBLE';

  return (
    <div className={`min-h-screen ${isDark ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-900'}`}>
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <nav aria-label="Breadcrumb" className="mb-6 text-sm text-slate-500">
          <Link to="/" className="hover:underline">Home</Link>
          <span className="mx-2">/</span>
          <span>Best Muslim Charities</span>
        </nav>

        <h1 className="text-4xl font-semibold mb-4">
          Best Muslim Charities in the USA ({year}, Independently Rated)
        </h1>
        <p className="text-lg leading-relaxed text-slate-700 dark:text-slate-300 mb-4">{COPY.intro}</p>
        <p className="text-lg leading-relaxed text-slate-700 dark:text-slate-300 mb-10">{COPY.introSecondary}</p>

        {loading ? (
          <div className="text-slate-500 mb-12">Loading charities…</div>
        ) : (
          <>
            {/* Top ranked */}
            <section className="mb-12">
              <h2 className="text-2xl font-semibold mb-4">Top {Math.min(TOP_N, topRanked.length)} by GMG Score</h2>
              {topRanked.length === 0 ? (
                <div className="text-slate-500">No ranked charities yet.</div>
              ) : (
                <ol className="space-y-3">
                  {topRanked.map((c, i) => (
                    <li key={c.ein}>
                      <Link
                        to={`/charity/${c.ein}`}
                        className="flex items-center gap-4 p-4 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-slate-400 dark:hover:border-slate-500 transition-colors"
                      >
                        <span className="text-lg font-semibold text-slate-400 dark:text-slate-500 w-8 shrink-0 text-right tabular-nums">
                          {i + 1}
                        </span>
                        <span className="flex-grow min-w-0">
                          <span className="font-medium block truncate">{c.name}</span>
                          {isZakatEligible(c) && (
                            <span className="inline-block mt-1 text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
                              Zakat-eligible
                            </span>
                          )}
                        </span>
                        <span className="text-sm font-semibold text-slate-600 dark:text-slate-300 shrink-0 tabular-nums">
                          {c.amalScore}/100
                        </span>
                      </Link>
                    </li>
                  ))}
                </ol>
              )}
            </section>

            {/* Remaining ranked directory */}
            {remainingRanked.length > 0 && (
              <section className="mb-12">
                <h2 className="text-2xl font-semibold mb-4">More Rated Muslim Charities</h2>
                <ul className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {remainingRanked.map((c, i) => (
                    <li key={c.ein}>
                      <Link
                        to={`/charity/${c.ein}`}
                        className="flex items-center justify-between gap-3 px-3 py-2 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                      >
                        <span className="min-w-0 truncate">
                          <span className="text-slate-400 dark:text-slate-500 tabular-nums mr-2">{TOP_N + i + 1}.</span>
                          {c.name}
                          {isZakatEligible(c) && (
                            <span className="ml-2 text-xs text-emerald-700 dark:text-emerald-400">zakat-eligible</span>
                          )}
                        </span>
                        <span className="text-sm text-slate-500 dark:text-slate-400 shrink-0 tabular-nums">{c.amalScore}/100</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {/* Evaluated but not yet scored */}
            {pending.length > 0 && (
              <section className="mb-12">
                <h2 className="text-2xl font-semibold mb-2">Evaluated — Score Pending</h2>
                <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
                  These Muslim charities have been evaluated and published, but their GMG score is not yet finalized. They are not ranked.
                </p>
                <ul className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {pending.map((c) => (
                    <li key={c.ein}>
                      <Link
                        to={`/charity/${c.ein}`}
                        className="block px-3 py-2 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors truncate"
                      >
                        {c.name}
                        {isZakatEligible(c) && (
                          <span className="ml-2 text-xs text-emerald-700 dark:text-emerald-400">zakat-eligible</span>
                        )}
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section className="mb-12">
              <Link to="/browse" className="text-emerald-700 dark:text-emerald-400 font-medium hover:underline">
                Browse all evaluated charities →
              </Link>
            </section>
          </>
        )}

        <section>
          <h2 className="text-2xl font-semibold mb-4">Frequently Asked Questions</h2>
          <dl>
            {COPY.faq.map((item, i) => (
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
