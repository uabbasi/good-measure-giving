import React from 'react';
import { Link } from 'react-router-dom';
import { Search, ArrowLeft } from 'lucide-react';
import { useLandingTheme } from '../contexts/LandingThemeContext';

export const NotFoundPage: React.FC = () => {
  const { isDark } = useLandingTheme();

  React.useEffect(() => {
    document.title = 'Page Not Found | Good Measure Giving';
    return () => { document.title = 'Good Measure Giving | Muslim Charity Evaluator'; };
  }, []);

  return (
    <div className={`min-h-[70vh] flex items-center justify-center py-16 transition-colors duration-300 ${isDark ? 'bg-slate-950' : 'bg-white'}`}>
      <div className="max-w-md mx-auto px-4 text-center">
        <div className={`text-8xl font-bold font-merriweather mb-4 ${isDark ? 'text-slate-700' : 'text-slate-200'}`}>
          404
        </div>
        <h1 className={`text-2xl font-bold font-merriweather mb-3 ${isDark ? 'text-white' : 'text-slate-900'}`}>
          Page not found
        </h1>
        <p className={`mb-8 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
          The page you're looking for doesn't exist or may have moved.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Link
            to="/browse"
            className="inline-flex items-center justify-center gap-2 px-5 py-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-full font-medium transition-colors"
          >
            <Search className="w-4 h-4" />
            Browse Charities
          </Link>
          <Link
            to="/"
            className={`inline-flex items-center justify-center gap-2 px-5 py-3 rounded-full font-medium transition-colors border ${
              isDark
                ? 'border-slate-700 text-slate-300 hover:bg-slate-800'
                : 'border-slate-300 text-slate-700 hover:bg-slate-50'
            }`}
          >
            <ArrowLeft className="w-4 h-4" />
            Go Home
          </Link>
        </div>
      </div>
    </div>
  );
};
