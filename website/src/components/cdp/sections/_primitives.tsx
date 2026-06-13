/**
 * Shared section primitives + pure formatters lifted verbatim from TabbedView.
 * Used by the standalone CDP section components.
 */
import React from 'react';
import { InfoTip } from '../../InfoTip';

// --- Utility functions (verbatim from TabbedView) ---

export const formatCurrency = (value: number | null | undefined): string => {
  if (value == null) return 'N/A';
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${Math.round(value / 1_000)}K`;
  return `$${value}`;
};

const POPULATION_TAGS = new Set([
  'women', 'youth', 'children', 'disabled', 'refugees', 'low-income',
  'orphans', 'elderly', 'families', 'students', 'veterans', 'homeless',
  'fuqara', 'masakin', 'muallaf', 'fisabilillah', 'ibn-al-sabil', 'amil'
]);

const GEOGRAPHIC_TAGS = new Set([
  'usa', 'india', 'pakistan', 'bangladesh', 'afghanistan', 'palestine',
  'syria', 'sudan', 'yemen', 'somalia', 'turkey', 'jordan', 'lebanon',
  'iraq', 'gaza', 'global', 'south-africa', 'kenya', 'indonesia', 'malaysia',
  'ukraine', 'egypt', 'morocco', 'tunisia', 'nigeria', 'ethiopia'
]);

const INTERVENTION_TAGS = new Set([
  'educational', 'medical', 'food', 'water-sanitation', 'shelter', 'clothing',
  'legal-aid', 'vocational', 'microfinance', 'mental-health'
]);

const CHANGE_TYPE_TAGS = new Set([
  'emergency-response', 'direct-relief', 'direct-service', 'long-term-development',
  'advocacy', 'capacity-building', 'grantmaking', 'research', 'policy',
  'scalable-model', 'systemic-change'
]);

export const formatTag = (tag: string): string => {
  const specialCases: Record<string, string> = {
    'fuqara': 'Fuqara',
    'masakin': 'Masakin',
    'muallaf': 'Muallaf',
    'fisabilillah': 'Fi Sabilillah',
    'ibn-al-sabil': 'Ibn al-Sabil',
    'amil': 'Amil',
    'usa': 'USA',
  };
  if (specialCases[tag.toLowerCase()]) {
    return specialCases[tag.toLowerCase()];
  }
  return tag.split('-').map(word =>
    word.charAt(0).toUpperCase() + word.slice(1)
  ).join(' ');
};

export const categorizeTags = (tags: string[] | null | undefined) => {
  if (!tags || tags.length === 0) {
    return { populations: [] as string[], geography: [] as string[], interventions: [] as string[], changeTypes: [] as string[] };
  }
  const populations: string[] = [];
  const geography: string[] = [];
  const interventions: string[] = [];
  const changeTypes: string[] = [];
  tags.forEach(tag => {
    const lowerTag = tag.toLowerCase();
    if (POPULATION_TAGS.has(lowerTag)) populations.push(tag);
    else if (GEOGRAPHIC_TAGS.has(lowerTag)) geography.push(tag);
    else if (INTERVENTION_TAGS.has(lowerTag)) interventions.push(tag);
    else if (CHANGE_TYPE_TAGS.has(lowerTag)) changeTypes.push(tag);
  });
  return { populations, geography, interventions, changeTypes };
};

export function formatProgramTag(raw: string): string {
  let cleaned = raw.replace(/\s+measures?\s*$/i, '');
  cleaned = cleaned.replace(/^Assist\s+/i, '');
  cleaned = cleaned.replace(/\band\b/gi, '&').replace(/\b\w/g, c => c.toUpperCase());
  return cleaned;
}

// --- Reusable sub-components (verbatim from TabbedView) ---

export const SectionCard: React.FC<{
  children: React.ReactNode;
  isDark: boolean;
  className?: string;
}> = ({ children, isDark, className = '' }) => (
  <div className={`rounded-xl p-5 ${isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-slate-200'} ${className}`}>
    {children}
  </div>
);

export const SectionHeader: React.FC<{
  icon: React.ElementType;
  title: string;
  isDark: boolean;
  infoTip?: string;
}> = ({ icon: Icon, title, isDark, infoTip }) => (
  <div className={`flex items-center gap-2 mb-4 pb-2 border-b ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
    <Icon className={`w-4 h-4 ${isDark ? 'text-slate-400' : 'text-slate-500'}`} />
    <h3 className={`text-sm font-semibold uppercase tracking-wide ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
      {title}
    </h3>
    {infoTip && <InfoTip text={infoTip} isDark={isDark} />}
  </div>
);

export const DataRow: React.FC<{
  label: string;
  value: string | number | null | undefined;
  isDark: boolean;
  highlight?: boolean;
  mono?: boolean;
}> = ({ label, value, isDark, highlight = false, mono = true }) => (
  <div className={`flex justify-between py-2 border-b ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
    <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{label}</span>
    <span className={`text-sm font-medium ${
      highlight
        ? isDark ? 'text-emerald-400' : 'text-emerald-600'
        : isDark ? 'text-white' : 'text-slate-900'
    } ${mono ? 'font-mono' : ''}`}>
      {value ?? '—'}
    </span>
  </div>
);
