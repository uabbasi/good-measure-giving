import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import type { GuidesIndex, GuideSummary } from '../scripts/lib/guide-seo';

export const GuidesIndexPage: React.FC = () => {
  const { isDark } = useLandingTheme();
  const [guides, setGuides] = useState<GuideSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    document.title = 'Guides | Good Measure Giving';
    fetch('/data/guides/guides.json')
      .then((r) => r.json())
      .then((data: GuidesIndex) => setGuides(data.guides || []))
      .catch(() => setGuides([]))
      .finally(() => setLoading(false));

    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, []);

  return (
    <div className={`min-h-screen ${isDark ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-900'}`}>
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <nav aria-label="Breadcrumb" className="mb-6 text-sm text-slate-500">
          <Link to="/" className="hover:underline">Home</Link>
          <span className="mx-2">/</span>
          <span>Guides</span>
        </nav>

        <h1 className="text-4xl font-semibold mb-4">Guides</h1>
        <p className="text-lg leading-relaxed text-slate-700 dark:text-slate-300 mb-10">
          Evergreen guides to evaluating Muslim charities, planning zakat, and thinking about impact.
        </p>

        {loading ? (
          <div className="text-slate-500">Loading guides…</div>
        ) : guides.length === 0 ? (
          <div className="text-slate-500">No guides published yet.</div>
        ) : (
          <ul className="space-y-4">
            {guides.map((g) => (
              <li key={g.slug}>
                <Link
                  to={`/guides/${g.slug}`}
                  className="block p-5 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-slate-400 dark:hover:border-slate-500 transition-colors"
                >
                  <h2 className="text-xl font-semibold mb-2">{g.title}</h2>
                  <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">{g.description}</p>
                  <div className="text-xs text-slate-500">
                    {g.readingTimeMinutes} min read
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};
