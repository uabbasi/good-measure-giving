import React from 'react';

export type LogoVariant = 'star' | 'lantern' | 'scale';
export type LogoSize = 'sm' | 'md' | 'lg';

interface LogoProps {
  className?: string;
  showText?: boolean;
  variant?: LogoVariant;
  size?: LogoSize;
}

export const Logo: React.FC<LogoProps> = ({
  className = "",
  showText = true,
  variant = 'star',
  size = 'md'
}) => {

  // Size Configuration
  const config = {
    sm: { px: 24, textSize: 'text-sm', subTextSize: 'text-[8px]', space: 'space-y-0' },
    md: { px: 40, textSize: 'text-xl', subTextSize: 'text-[10px]', space: '-space-y-0.5' },
    lg: { px: 72, textSize: 'text-4xl', subTextSize: 'text-sm', space: '-space-y-1' }
  };

  const { px, textSize, subTextSize, space } = config[size];

  const renderIcon = () => {
    switch (variant) {
      case 'lantern':
        return (
          <g>
             {/* Hanging Ring */}
             <circle cx="20" cy="6" r="2" stroke="white" strokeWidth="1.5" fill="none" />
             {/* Dome */}
             <path d="M14 13C14 10 17 8.5 20 8.5C23 8.5 26 10 26 13" stroke="white" strokeWidth="1.5" fill="none"/>
             {/* Top Cap */}
             <rect x="13" y="13" width="14" height="2" rx="1" fill="white" />
             {/* Main Body with Lattice suggestion */}
             <path d="M14 15L12 26H28L26 15H14Z" stroke="white" strokeWidth="1.5" fill="white" fillOpacity="0.15"/>
             <path d="M20 15V26" stroke="white" strokeWidth="1" strokeOpacity="0.5"/>
             <path d="M13 20H27" stroke="white" strokeWidth="1" strokeOpacity="0.5"/>
             {/* Inner Light */}
             <circle cx="20" cy="21" r="2.5" fill="white" fillOpacity="0.9"/>
             {/* Base */}
             <path d="M12 26H28L26 30C26 31.1046 25.1046 32 24 32H16C14.8954 32 14 31.1046 14 30L12 26Z" fill="white"/>
          </g>
        );
      case 'scale':
        return (
           <g>
             {/* Center Pillar Base */}
             <path d="M16 34H24" stroke="white" strokeWidth="2" strokeLinecap="round"/>
             <path d="M20 34V10" stroke="white" strokeWidth="2" strokeLinecap="round"/>

             {/* Top Pivot */}
             <circle cx="20" cy="10" r="1.5" fill="white"/>

             {/* Balance Beam */}
             <path d="M8 12L32 12" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>

             {/* Left Pan Assembly */}
             <path d="M8 12L5 20" stroke="white" strokeWidth="1" strokeOpacity="0.6"/>
             <path d="M8 12L11 20" stroke="white" strokeWidth="1" strokeOpacity="0.6"/>
             <path d="M4 20Q8 25 12 20" stroke="white" strokeWidth="1.5" fill="white" fillOpacity="0.2"/>

             {/* Right Pan Assembly */}
             <path d="M32 12L29 20" stroke="white" strokeWidth="1" strokeOpacity="0.6"/>
             <path d="M32 12L35 20" stroke="white" strokeWidth="1" strokeOpacity="0.6"/>
             <path d="M28 20Q32 25 36 20" stroke="white" strokeWidth="1.5" fill="white" fillOpacity="0.2"/>
           </g>
        );
      case 'star':
      default:
        return (
          <g transform="translate(20, 20)">
             {/* Rub el Hizb (Islamic Star) Geometry */}
             {/* Square 1 */}
             <rect x="-9" y="-9" width="18" height="18" rx="1" stroke="white" strokeWidth="2" fill="none" />
             {/* Square 2 (Rotated) */}
             <rect x="-9" y="-9" width="18" height="18" rx="1" stroke="white" strokeWidth="2" fill="none" transform="rotate(45)" />
             {/* Center Dot (Focus/Precision) */}
             <circle cx="0" cy="0" r="3" fill="white" />
          </g>
        );
    }
  };

  return (
    <div className={`flex items-center gap-3 ${className}`}>
      {/* Logomark Container */}
      <svg
        width={px}
        height={px}
        viewBox="0 0 40 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="shrink-0 shadow-sm rounded-xl"
      >
        <defs>
          <linearGradient id="logo_gradient" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#10b981" /> {/* emerald-500 */}
            <stop offset="100%" stopColor="#047857" /> {/* emerald-700 */}
          </linearGradient>
        </defs>

        {/* Background */}
        <rect width="40" height="40" rx="10" fill="url(#logo_gradient)" />

        {/* Render Icon Variant */}
        {renderIcon()}
      </svg>

      {/* Wordmark */}
      {showText && (
        <div className={`flex flex-col ${space} select-none`}>
          <span className={`${textSize} font-bold tracking-tight font-merriweather text-slate-900 leading-none`}>
            Good Measure
          </span>
          <span className={`${subTextSize} text-emerald-700 uppercase tracking-[0.25em] font-bold font-sans`}>
            Giving
          </span>
        </div>
      )}
    </div>
  );
};
