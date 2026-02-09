import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ThemedLogo } from './logos';
import { Menu, X } from 'lucide-react';
import { SignInButton, useAuth } from '../src/auth';
import { useLandingTheme } from '../contexts/LandingThemeContext';

export interface NavbarProps {
  forceTheme?: 'light' | 'dark';
}

export const Navbar: React.FC<NavbarProps> = ({ forceTheme: propForceTheme }) => {
  const [isOpen, setIsOpen] = useState(false);
  const location = useLocation();
  const { isDark: landingIsDark } = useLandingTheme();
  const { isSignedIn } = useAuth();

  // Determine if we should use dark or light mode
  // Priority: 1. propForceTheme, 2. landingIsDark from context
  const themeMode = propForceTheme || (landingIsDark ? 'dark' : 'light');
  const isDark = themeMode === 'dark';

  // Dynamic Styles
  const navClasses = isDark
    ? "bg-slate-900/90 backdrop-blur-md border-b border-slate-800 sticky top-0 z-40"
    : "bg-slate-50/80 backdrop-blur-md border-b border-slate-200 sticky top-0 z-40";

  const linkBase = isDark
    ? "text-slate-300 hover:text-white hover:bg-white/10"
    : "text-slate-500 hover:text-slate-900 hover:bg-white";

  const linkActive = isDark
    ? "text-white font-medium bg-white/10"
    : "text-slate-900 font-medium bg-slate-100";

  const getLinkClasses = (path: string) =>
    `px-4 py-2 rounded-lg text-sm transition-colors ${location.pathname === path ? linkActive : linkBase}`;

  return (
    <>
      <nav className={navClasses}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <Link to="/" className="flex-shrink-0 flex items-center hover:opacity-80 transition-opacity">
                <ThemedLogo size="md" variant={isDark ? 'dark' : 'light'} />
              </Link>
            </div>

            {/* Desktop Menu */}
            <div className="hidden md:flex items-center space-x-2">
              <Link to="/browse" className={getLinkClasses('/browse')}>Browse Charities</Link>
              <Link to="/methodology" className={getLinkClasses('/methodology')}>Methodology</Link>
              <Link to="/faq" className={getLinkClasses('/faq')}>FAQ</Link>
              <Link to="/about" className={getLinkClasses('/about')}>About</Link>
              {isSignedIn && (
                <div className={`ml-2 pl-2 border-l ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                  <Link
                    to="/profile"
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      location.pathname === '/profile'
                        ? 'bg-emerald-500 text-white shadow-md'
                        : isDark
                          ? 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 border border-emerald-500/30'
                          : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200'
                    }`}
                  >
                    Giving Plan
                  </Link>
                </div>
              )}
              <div className={`ml-2 pl-2 border-l ${isDark ? 'border-slate-700' : 'border-slate-200'}`}>
                <SignInButton variant="compact" isDark={isDark} />
              </div>
            </div>

          {/* Mobile menu button */}
          <div className="flex items-center md:hidden">
            <button
              onClick={() => setIsOpen(!isOpen)}
              aria-label={isOpen ? 'Close menu' : 'Open menu'}
              aria-expanded={isOpen}
              className={`p-3 rounded-md min-w-[44px] min-h-[44px] flex items-center justify-center ${isDark ? 'text-slate-400 hover:text-white hover:bg-white/10' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-100'}`}
            >
              {isOpen ? <X className="block h-6 w-6" aria-hidden="true" /> : <Menu className="block h-6 w-6" aria-hidden="true" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu */}
      {isOpen && (
        <div className={`md:hidden border-b shadow-xl ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
          <div className="px-4 pt-4 pb-6 space-y-2">
            {[
              { path: '/browse', label: 'Browse Charities' },
              { path: '/methodology', label: 'Methodology' },
              { path: '/faq', label: 'FAQ' },
              { path: '/about', label: 'About' },
            ].map(({ path, label }) => (
              <Link
                key={path}
                onClick={() => setIsOpen(false)}
                to={path}
                className={`block px-3 py-3 rounded-lg text-base font-medium ${isDark ? 'text-slate-300 hover:bg-white/10 hover:text-white' : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'}`}
              >
                {label}
              </Link>
            ))}
            {isSignedIn && (
              <div className={`pt-4 mt-4 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                <Link
                  onClick={() => setIsOpen(false)}
                  to="/profile"
                  className={`block px-3 py-3 rounded-lg text-base font-medium ${
                    isDark
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                      : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  }`}
                >
                  Giving Plan
                </Link>
              </div>
            )}
            <div className={`pt-4 mt-4 border-t ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
              <SignInButton variant="compact" isDark={isDark} className="block px-3 py-3" />
            </div>
          </div>
        </div>
      )}
    </nav>
    </>
  );
};
