import React, { createContext, useContext, useMemo, useState, ReactNode } from 'react';
import {
  ThemeConfig,
  ThemeContextValue,
  ThemeVariant,
  THEMES,
  getThemeFromEnv,
} from '../types/theme';

interface ExtendedThemeContextValue extends ThemeContextValue {
  setVariant: (variant: ThemeVariant) => void;
}

const ThemeContext = createContext<ExtendedThemeContextValue | undefined>(undefined);

interface ThemeProviderProps {
  children: ReactNode;
  variant?: ThemeVariant;
}

export function ThemeProvider({ children, variant: initialVariant }: ThemeProviderProps) {
  const [variant, setVariant] = useState<ThemeVariant>(initialVariant || getThemeFromEnv());

  const value = useMemo<ExtendedThemeContextValue>(() => {
    return {
      variant,
      theme: THEMES[variant],
      setVariant,
    };
  }, [variant]);

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

export function useTheme(): ExtendedThemeContextValue {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}

export function useThemeColors(): ThemeConfig['colors'] {
  return useTheme().theme.colors;
}

export function useThemeBranding(): ThemeConfig['branding'] {
  return useTheme().theme.branding;
}
