/**
 * Theme Configuration
 *
 * Defines the interface for switchable landing page themes.
 * Used by: App.tsx, components/*, pages/LandingPage.tsx
 */

/**
 * Available theme variants
 */
export type ThemeVariant = 'amal' | 'third-bucket';

/**
 * Color palette for a theme
 */
export interface ThemeColors {
  /** Primary brand color (Tailwind class) */
  primary: string;
  /** Primary hover state */
  primaryHover: string;
  /** Accent color for highlights */
  accent: string;
  /** Background color */
  background: string;
  /** Text color */
  text: string;
  /** Muted text color */
  textMuted: string;
}

/**
 * Branding assets for a theme
 */
export interface ThemeBranding {
  /** Display name */
  name: string;
  /** Tagline/subtitle */
  tagline: string;
  /** Logo component path or URL */
  logoSrc: string;
  /** Favicon path */
  faviconSrc: string;
}

/**
 * Complete theme configuration
 */
export interface ThemeConfig {
  variant: ThemeVariant;
  colors: ThemeColors;
  branding: ThemeBranding;
}

/**
 * Theme definitions
 */
export const THEMES: Record<ThemeVariant, ThemeConfig> = {
  amal: {
    variant: 'amal',
    colors: {
      primary: 'emerald-700',
      primaryHover: 'emerald-600',
      accent: 'emerald-500',
      background: 'slate-50',
      text: 'slate-900',
      textMuted: 'slate-600',
    },
    branding: {
      name: 'Good Measure Giving',
      tagline: 'Rigorous charity research for Muslim donors',
      logoSrc: '/logo-amal.svg',
      faviconSrc: '/favicon.svg',
    },
  },
  'third-bucket': {
    variant: 'third-bucket',
    colors: {
      primary: 'blue-700',
      primaryHover: 'blue-600',
      accent: 'blue-500',
      background: 'gray-50',
      text: 'gray-900',
      textMuted: 'gray-600',
    },
    branding: {
      name: 'Third Bucket',
      tagline: 'Strategic giving for systemic change',
      logoSrc: '/logo-third-bucket.svg',
      faviconSrc: '/favicon-third-bucket.svg',
    },
  },
};

/**
 * Environment variable for theme selection
 */
export const THEME_ENV_VAR = 'VITE_LANDING_THEME';

/**
 * Default theme if env var is not set
 */
export const DEFAULT_THEME: ThemeVariant = 'amal';

/**
 * Get current theme from environment
 */
export function getThemeFromEnv(): ThemeVariant {
  const envValue = (import.meta as any).env?.VITE_LANDING_THEME;
  if (envValue === 'amal' || envValue === 'third-bucket') {
    return envValue;
  }
  return DEFAULT_THEME;
}

/**
 * React Context type for theme
 */
export interface ThemeContextValue {
  theme: ThemeConfig;
  variant: ThemeVariant;
}
