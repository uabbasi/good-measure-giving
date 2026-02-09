import React from 'react';
import { AmalLogo, LogoSize } from './AmalLogo';

export { AmalLogo } from './AmalLogo';
export type { LogoSize } from './AmalLogo';

// T009-T011: Removed ThirdBucket logo - single Amal theme only
// ThemedLogo now just returns AmalLogo for backwards compatibility

interface ThemedLogoProps {
  className?: string;
  showText?: boolean;
  size?: LogoSize;
  variant?: 'light' | 'dark';
}

/**
 * Logo component - renders Amal branding
 * (Previously theme-aware, now always Amal)
 */
export const ThemedLogo: React.FC<ThemedLogoProps> = (props) => {
  return <AmalLogo {...props} />;
};
