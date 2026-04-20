import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import causesData from '../data/causes/causes.json';

interface CauseData {
  slug: string;
  category: string;
  displayName: string;
  intro: string;
}

const CAUSES: CauseData[] = (causesData.causes as CauseData[]);

export const CausesIndexPage: React.FC = () => {
  const { isDark } = useLandingTheme();

  useEffect(() => {
    document.title = 'Causes | Good Measure Giving';
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, []);

  return (
    <div className={`min-h-screen ${isDark ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-900'}`}>
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <nav aria-label="Breadcrumb" className="mb-6 text-sm text-slate-500">
          <Link to="/" className="hover:underline">Home</Link>
          <span className="mx-2">/</span>
          <span>Causes</span>
        </nav>

        <h1 className="text-4xl font-semibold mb-4">Browse Charities by Cause</h1>
        <p className="text-lg leading-relaxed text-slate-700 dark:text-slate-300 mb-10">
          Explore {CAUSES.length} cause areas in the Muslim charity ecosystem, each evaluated by Good Measure Giving on impact, alignment, and financial transparency.
        </p>

        <ul className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {CAUSES.map((c) => (
            <li key={c.slug}>
              <Link
                to={`/causes/${c.slug}`}
                className="block p-5 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-slate-400 dark:hover:border-slate-500 transition-colors"
              >
                <h2 className="text-xl font-semibold mb-2">{c.displayName}</h2>
                <p className="text-sm text-slate-600 dark:text-slate-400 line-clamp-3">{c.intro}</p>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};
