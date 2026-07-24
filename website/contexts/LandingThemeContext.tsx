import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface ThemeContextValue {
  isDark: boolean;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

const STORAGE_KEY = 'gmg-theme';

export const LandingThemeProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [isDark, setIsDark] = useState(() => {
    // Check localStorage first
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === 'dark') return true;
      if (stored === 'light') return false;
      // Fall back to system preference
      return window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    // SSR/prerender has no window, so this is what every static page ships with
    // by default. Must match the client's own fallback for most visitors (no
    // stored preference, light-mode OS) or the page flashes dark->light right
    // after hydration. The site's actual default motif is light ("sage-on-bone").
    return false;
  });

  // Persist to localStorage and sync browser-level color scheme
  useEffect(() => {
    if (typeof window === 'undefined') return;
    localStorage.setItem(STORAGE_KEY, isDark ? 'dark' : 'light');
    document.documentElement.style.colorScheme = isDark ? 'dark' : 'light';
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', isDark ? '#0f172a' : '#f8fafc');
  }, [isDark]);

  const toggleTheme = () => setIsDark(prev => !prev);

  return (
    <ThemeContext.Provider value={{ isDark, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useLandingTheme = () => {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useLandingTheme must be used within a LandingThemeProvider');
  }
  return context;
};
