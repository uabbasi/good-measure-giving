/**
 * MobileBottomNav - Sticky bottom tab bar for mobile viewports.
 * Three tabs: Browse, Giving Plan (or Sign In), More.
 * Hidden on md+ screens. Shifts up when CompareBar is active.
 */

import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Search, Heart, MoreHorizontal, X, BookOpen, HelpCircle, Info } from 'lucide-react';
import { useLandingTheme } from '../../contexts/LandingThemeContext';
import { useAuth } from '../auth/useAuth';
import { useCompareState } from '../contexts/UserFeaturesContext';

export function MobileBottomNav() {
  const { isDark } = useLandingTheme();
  const { isSignedIn } = useAuth();
  const { compareCount } = useCompareState();
  const location = useLocation();
  const [moreOpen, setMoreOpen] = useState(false);

  const isActive = (path: string) => location.pathname === path;

  const activeColor = 'text-emerald-500';
  const inactiveColor = isDark ? 'text-slate-400' : 'text-slate-500';

  const moreLinks = [
    { path: '/methodology', label: 'Methodology', icon: BookOpen },
    { path: '/faq', label: 'FAQ', icon: HelpCircle },
    { path: '/about', label: 'About', icon: Info },
  ];

  const isMoreActive = moreOpen || moreLinks.some(l => isActive(l.path));

  return (
    <>
      {/* "More" sheet overlay */}
      {moreOpen && (
        <div className="fixed inset-0 z-40 md:hidden" onClick={() => setMoreOpen(false)}>
          <div className="absolute inset-0 bg-black/40" />
          <div
            className={`absolute bottom-14 left-0 right-0 rounded-t-2xl border-t shadow-xl pb-[env(safe-area-inset-bottom)] ${
              isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
            }`}
            onClick={e => e.stopPropagation()}
          >
            <div className="px-4 pt-4 pb-2 flex items-center justify-between">
              <span className={`text-sm font-semibold ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>More</span>
              <button
                onClick={() => setMoreOpen(false)}
                className={`p-1.5 rounded-lg ${isDark ? 'hover:bg-white/10 text-slate-400' : 'hover:bg-slate-100 text-slate-500'}`}
                aria-label="Close menu"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="px-2 pb-4 space-y-1">
              {moreLinks.map(({ path, label, icon: Icon }) => (
                <Link
                  key={path}
                  to={path}
                  onClick={() => setMoreOpen(false)}
                  className={`flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-medium transition-colors ${
                    isActive(path)
                      ? isDark
                        ? 'bg-emerald-500/15 text-emerald-400'
                        : 'bg-emerald-50 text-emerald-700'
                      : isDark
                        ? 'text-slate-300 hover:bg-white/10'
                        : 'text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {label}
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Bottom tab bar */}
      <nav
        className={`
          fixed bottom-0 left-0 right-0 z-40 md:hidden
          border-t shadow-lg
          pb-[env(safe-area-inset-bottom)]
          transition-transform
          ${isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'}
          ${compareCount > 0 ? 'translate-y-0 bottom-[60px]' : ''}
        `}
        aria-label="Mobile navigation"
      >
        <div className="h-14 grid grid-cols-3">
          {/* Browse */}
          <Link
            to="/browse"
            className={`flex flex-col items-center justify-center gap-0.5 ${isActive('/browse') ? activeColor : inactiveColor}`}
          >
            <Search className="w-5 h-5" />
            <span className="text-[10px] font-medium">Browse</span>
          </Link>

          {/* Giving Plan / Sign In */}
          <Link
            to="/profile"
            className={`flex flex-col items-center justify-center gap-0.5 ${isActive('/profile') ? activeColor : inactiveColor}`}
          >
            <Heart className="w-5 h-5" />
            <span className="text-[10px] font-medium">{isSignedIn ? 'Giving Plan' : 'Sign In'}</span>
          </Link>

          {/* More */}
          <button
            onClick={() => setMoreOpen(v => !v)}
            className={`flex flex-col items-center justify-center gap-0.5 ${isMoreActive ? activeColor : inactiveColor}`}
            aria-label="More options"
          >
            <MoreHorizontal className="w-5 h-5" />
            <span className="text-[10px] font-medium">More</span>
          </button>
        </div>
      </nav>
    </>
  );
}
