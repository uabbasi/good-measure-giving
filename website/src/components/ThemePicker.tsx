import React from 'react';
import { Settings, Palette, Type } from 'lucide-react';
import { THEMES } from '../themes';

interface ThemePickerProps {
  themeIndex: number;
  setThemeIndex: (index: number) => void;
  // Optional headline controls (for LandingPage)
  headlineIndex?: number;
  setHeadlineIndex?: React.Dispatch<React.SetStateAction<number>>;
  headlinesLength?: number;
}

export const ThemePicker: React.FC<ThemePickerProps> = ({ 
  themeIndex, 
  setThemeIndex, 
  headlineIndex, 
  setHeadlineIndex,
  headlinesLength 
}) => {
  const theme = THEMES[themeIndex];

  return (
    <div className="fixed bottom-6 right-6 z-50 bg-white shadow-2xl rounded-2xl border border-slate-200 p-4 w-80 animate-fade-in text-slate-900">
      <div className="flex items-center gap-2 mb-4 pb-3 border-b border-slate-100">
        <Settings className="w-4 h-4 text-slate-400" />
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">Design Studio</h3>
      </div>

      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
            <Palette className="w-4 h-4 text-emerald-600" /> Theme
          </div>
          <span className="text-xs text-slate-400">{theme.name}</span>
        </div>
        <div className="flex gap-1 overflow-x-auto pb-2">
          {THEMES.map((t, i) => (
            <button
              key={t.id}
              onClick={() => setThemeIndex(i)}
              className={`w-8 h-8 rounded-full border-2 flex-shrink-0 transition-all ${themeIndex === i ? 'border-emerald-500 scale-110' : 'border-slate-200 opacity-50 hover:opacity-100'}`}
              style={{ background: t.id.includes('light') || t.id === 'original' || t.id === 'soft-noor' ? '#f8fafc' : '#0f172a' }}
              title={t.name}
            />
          ))}
        </div>
      </div>

      {setHeadlineIndex && headlinesLength && (
        <div>
           <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
              <Type className="w-4 h-4 text-blue-600" /> Headline
            </div>
            <span className="text-xs text-slate-400">{(headlineIndex || 0) + 1} / {headlinesLength}</span>
          </div>
          <div className="flex gap-2">
             <button 
               onClick={() => setHeadlineIndex(h => (h - 1 + headlinesLength) % headlinesLength)}
               className="px-3 py-1 bg-slate-100 hover:bg-slate-200 rounded text-xs font-medium"
             >
               Prev
             </button>
             <button 
               onClick={() => setHeadlineIndex(h => (h + 1) % headlinesLength)}
               className="flex-grow px-3 py-1 bg-slate-900 text-white hover:bg-slate-800 rounded text-xs font-medium"
             >
               Next Headline
             </button>
          </div>
        </div>
      )}
    </div>
  );
};
