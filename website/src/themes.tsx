import React from 'react';

export interface Theme {
  id: string;
  name: string;
  isDark: boolean;
  bgPage: string;
  bgHero: string;
  textMain: string;
  textSub: string;
  textAccent: string;
  pill: string;
  pillIcon: string;
  btnPrimary: string;
  btnSecondary: string;
  stats: string;
  statsStrong: string;
  filterSectionBg: string;
  filterText: string;
  backgroundElements: React.ReactNode | null;
}

export const THEMES: Theme[] = [
  {
    id: 'original',
    name: 'Original (Clean)',
    isDark: false,
    bgPage: 'bg-slate-50',
    bgHero: 'bg-slate-50',
    textMain: 'text-slate-900',
    textSub: 'text-slate-600',
    textAccent: 'text-transparent bg-clip-text bg-gradient-to-r from-emerald-800 to-emerald-600',
    pill: 'bg-emerald-50/80 border-emerald-200 text-emerald-800',
    pillIcon: 'text-emerald-700',
    btnPrimary: 'bg-emerald-700 text-white hover:bg-emerald-600 shadow-emerald-200',
    btnSecondary: 'bg-white text-slate-700 border-2 border-slate-200 hover:bg-slate-50',
    stats: 'text-slate-500',
    statsStrong: 'text-slate-700',
    filterSectionBg: 'bg-white',
    filterText: 'text-slate-900',
    backgroundElements: null
  },
  {
    id: 'dark-minimal',
    name: 'Dark Minimal',
    isDark: true,
    bgPage: 'bg-slate-900',
    bgHero: 'bg-slate-900',
    textMain: 'text-white',
    textSub: 'text-slate-300',
    textAccent: 'text-white', // No gradient, just stark white
    pill: 'bg-slate-800 border-slate-700 text-slate-300',
    pillIcon: 'text-white',
    btnPrimary: 'bg-white text-slate-900 hover:bg-slate-100',
    btnSecondary: 'bg-transparent text-white border border-slate-600 hover:bg-slate-800',
    stats: 'text-slate-400',
    statsStrong: 'text-white',
    filterSectionBg: 'bg-slate-900',
    filterText: 'text-white',
    backgroundElements: null
  },
  {
    id: 'warm-atmosphere',
    name: 'Warm Atmosphere',
    isDark: true,
    bgPage: 'bg-slate-900',
    bgHero: 'bg-slate-900',
    textMain: 'text-white',
    textSub: 'text-slate-300',
    textAccent: 'text-transparent bg-clip-text bg-gradient-to-r from-amber-200 to-amber-500',
    pill: 'bg-slate-800/50 border-amber-500/30 text-amber-100/90 ring-1 ring-white/10 backdrop-blur-sm',
    pillIcon: 'text-amber-400',
    btnPrimary: 'bg-emerald-600 text-white hover:bg-emerald-500 shadow-[0_0_20px_-5px_rgba(16,185,129,0.5)] border border-emerald-500/50',
    btnSecondary: 'bg-white/5 text-slate-200 border border-white/20 hover:bg-white/10',
    stats: 'text-slate-400',
    statsStrong: 'text-slate-200',
    filterSectionBg: 'bg-slate-900',
    filterText: 'text-white',
    backgroundElements: (
      <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden">
        <div className="absolute top-[-10%] left-1/2 -translate-x-1/2 w-[80%] h-[60%] bg-amber-500/10 blur-[100px] rounded-full mix-blend-screen"></div>
        <div className="absolute top-[20%] left-[20%] w-[40%] h-[40%] bg-emerald-900/20 blur-[80px] rounded-full"></div>
        <div className="absolute inset-0 opacity-[0.03]" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='1'/%3E%3C/svg%3E")` }}></div>
      </div>
    )
  },
  {
    id: 'blueprint',
    name: 'The Blueprint',
    isDark: true,
    bgPage: 'bg-slate-950',
    bgHero: 'bg-slate-950',
    textMain: 'text-white',
    textSub: 'text-slate-400 font-mono text-sm tracking-wide',
    textAccent: 'text-emerald-400',
    pill: 'bg-slate-900 border-slate-700 text-emerald-400 font-mono text-xs uppercase tracking-widest',
    pillIcon: 'text-emerald-500',
    btnPrimary: 'bg-emerald-600 text-white rounded-none border border-emerald-400 hover:bg-emerald-700 font-mono text-sm uppercase tracking-widest',
    btnSecondary: 'bg-transparent text-slate-300 rounded-none border border-slate-700 hover:border-slate-500 font-mono text-sm uppercase tracking-widest',
    stats: 'text-slate-500 font-mono text-xs',
    statsStrong: 'text-emerald-400',
    filterSectionBg: 'bg-slate-950',
    filterText: 'text-white',
    backgroundElements: (
      <div className="absolute inset-0 z-0 pointer-events-none opacity-20" style={{ backgroundImage: 'linear-gradient(#334155 1px, transparent 1px), linear-gradient(90deg, #334155 1px, transparent 1px)', backgroundSize: '40px 40px' }}></div>
    )
  },
  {
    id: 'soft-noor',
    name: 'Soft Noor (Light)',
    isDark: false,
    bgPage: 'bg-white',
    bgHero: 'bg-gradient-to-b from-emerald-50 to-white',
    textMain: 'text-slate-900',
    textSub: 'text-slate-600',
    textAccent: 'text-emerald-700',
    pill: 'bg-white border-emerald-200 text-emerald-900 shadow-sm',
    pillIcon: 'text-emerald-600',
    btnPrimary: 'bg-emerald-600 text-white hover:bg-emerald-700 shadow-lg shadow-emerald-200/50',
    btnSecondary: 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50',
    stats: 'text-slate-500',
    statsStrong: 'text-emerald-800',
    filterSectionBg: 'bg-white',
    filterText: 'text-slate-900',
    backgroundElements: (
      <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden">
         <div className="absolute -top-[20%] left-1/2 -translate-x-1/2 w-[80%] h-[80%] bg-emerald-100/50 blur-[120px] rounded-full"></div>
      </div>
    )
  }
];
