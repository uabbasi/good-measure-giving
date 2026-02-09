import React from 'react';

export type LogoSize = 'sm' | 'md' | 'lg';

interface AmalLogoProps {
  className?: string;
  showText?: boolean;
  size?: LogoSize;
  variant?: 'light' | 'dark';
}

/**
 * Amal/Good Measure Giving Logo
 * Emerald color palette with Islamic star (Rub el Hizb) motif
 */
export const AmalLogo: React.FC<AmalLogoProps> = ({
  className = "",
  showText = true,
  size = 'md',
  variant = 'light'
}) => {
  const config = {
    sm: { px: 24, textSize: 'text-sm', subTextSize: 'text-[8px]', space: 'space-y-0' },
    md: { px: 40, textSize: 'text-xl', subTextSize: 'text-[10px]', space: '-space-y-0.5' },
    lg: { px: 72, textSize: 'text-4xl', subTextSize: 'text-sm', space: '-space-y-1' }
  };

  const { px, textSize, subTextSize, space } = config[size];

  // Text Colors based on variant
  const titleColor = variant === 'dark' ? 'text-white' : 'text-slate-900';
  const subtitleColor = variant === 'dark' ? 'text-emerald-400' : 'text-emerald-700';

  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <svg
        width={px}
        height={px}
        viewBox="0 0 40 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="shrink-0 shadow-sm rounded-xl"
      >
        <defs>
          <linearGradient id="amal_gradient" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#10b981" />
            <stop offset="100%" stopColor="#047857" />
          </linearGradient>
        </defs>
        <rect width="40" height="40" rx="10" fill="url(#amal_gradient)" />
        <g transform="translate(20, 20)">
          <rect x="-9" y="-9" width="18" height="18" rx="1" stroke="white" strokeWidth="2" fill="none" />
          <rect x="-9" y="-9" width="18" height="18" rx="1" stroke="white" strokeWidth="2" fill="none" transform="rotate(45)" />
          <circle cx="0" cy="0" r="3" fill="white" />
        </g>
      </svg>

      {showText && (
        <div className={`flex flex-col ${space} select-none`}>
          <span className={`${textSize} font-bold tracking-tight font-merriweather ${titleColor} leading-none`}>
            Good Measure
          </span>
          <span className={`${subTextSize} ${subtitleColor} uppercase tracking-[0.25em] font-bold font-sans`}>
            Giving
          </span>
        </div>
      )}
    </div>
  );
};
