import React, { useState } from 'react';
import { Info } from 'lucide-react';
import { SourceAttributionField } from '../../types';

interface SourceAttributionProps {
  fieldName: string;
  attribution: SourceAttributionField;
  className?: string;
}

/**
 * T059-T061: SourceAttribution Component
 *
 * Displays data source attribution with an info icon tooltip.
 * Shows which data source was used for a specific field (e.g., "ProPublica", "Charity Navigator")
 */
export const SourceAttribution: React.FC<SourceAttributionProps> = ({
  fieldName,
  attribution,
  className = ''
}) => {
  const [showTooltip, setShowTooltip] = useState(false);

  // Format source name for display
  const formatSourceName = (source: string): string => {
    const sourceNames: Record<string, string> = {
      'propublica': 'ProPublica (IRS 990)',
      'charity_navigator': 'Charity Navigator',
      'candid': 'Candid',
      'causeiq': 'CauseIQ',
      'website': 'Charity Website'
    };
    return sourceNames[source] || source;
  };

  // T061: Format tooltip text
  const getTooltipText = (): string => {
    if (attribution.method === 'merged' && attribution.sources) {
      const formattedSources = attribution.sources.map(formatSourceName).join(', ');
      return `Merged from: ${formattedSources}`;
    } else if (attribution.source) {
      return `Source: ${formatSourceName(attribution.source)}`;
    }
    return 'Source not available';
  };

  return (
    <div className={`relative inline-block ${className}`}>
      {/* T060: Info Icon */}
      <button
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        onClick={() => setShowTooltip(!showTooltip)}
        className="inline-flex items-center justify-center w-4 h-4 text-slate-400 hover:text-slate-600 transition-colors ml-1.5"
        aria-label={`View data source for ${fieldName}`}
      >
        <Info className="w-3.5 h-3.5" />
      </button>

      {/* Tooltip */}
      {showTooltip && (
        <div className="absolute z-50 bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-slate-900 text-white text-xs rounded-lg shadow-lg whitespace-nowrap">
          {getTooltipText()}
          {/* Arrow */}
          <div className="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-slate-900"></div>
        </div>
      )}
    </div>
  );
};
