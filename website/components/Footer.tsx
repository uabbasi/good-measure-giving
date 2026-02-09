import React from 'react';
import { Link } from 'react-router-dom';
import { Sun, Moon } from 'lucide-react';
import { useLandingTheme } from '../contexts/LandingThemeContext';
import { FeedbackButton } from '../src/components/FeedbackButton';

export const Footer: React.FC = () => {
  const { isDark, toggleTheme } = useLandingTheme();

  return (
    <footer className={`border-t py-8 ${isDark ? 'bg-slate-950 border-slate-800' : 'bg-slate-100 border-slate-200'}`}>
      <div className="max-w-7xl mx-auto px-4 flex flex-col items-center gap-4 text-sm">
        <div className="flex flex-col md:flex-row justify-between items-center gap-4 w-full text-xs">
          <div className={isDark ? 'text-slate-300' : 'text-slate-600'}>
            © 2026 Good Measure Giving.
          </div>
          <div className="flex flex-wrap items-center justify-center md:justify-end gap-x-4 gap-y-2 sm:gap-x-6">
            <Link to="/browse" className={`hover:text-emerald-600 transition-colors ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              Browse Charities
            </Link>
            <Link to="/methodology" className={`hover:text-emerald-600 transition-colors ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              Our Process
            </Link>
            <Link to="/faq" className={`hover:text-emerald-600 transition-colors ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              FAQ
            </Link>
            <Link to="/about" className={`hover:text-emerald-600 transition-colors ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              About
            </Link>
            <Link to="/prompts" className={`hover:text-emerald-600 transition-colors ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              AI Transparency
            </Link>
            <a href="mailto:hello@goodmeasuregiving.org" className={`hover:text-emerald-600 transition-colors ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              Contact
            </a>
            <FeedbackButton inline />
            {/* Theme Toggle - icon only */}
            <button
              onClick={toggleTheme}
              className={`p-1.5 rounded-md transition-colors ${isDark ? 'text-slate-500 hover:text-white hover:bg-slate-800' : 'text-slate-400 hover:text-slate-900 hover:bg-slate-200'}`}
              aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <p className={`text-center font-medium text-[11px] mt-2 uppercase tracking-widest ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          Rigorous charity research for Muslim donors.
        </p>
      </div>
    </footer>
  );
};
