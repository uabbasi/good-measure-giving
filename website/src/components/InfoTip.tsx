import React, { useState, useRef, useEffect } from 'react';
import { Info } from 'lucide-react';

interface InfoTipProps {
  text: string;
  isDark: boolean;
}

export const InfoTip: React.FC<InfoTipProps> = ({ text, isDark }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  // Close on outside click (mobile tap-to-dismiss)
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  return (
    <span
      ref={ref}
      className="relative inline-flex items-center group/infotip"
      onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
    >
      <Info
        className={`w-3 h-3 cursor-help ${
          isDark ? 'text-slate-600 hover:text-slate-400' : 'text-slate-400 hover:text-slate-600'
        } transition-colors`}
      />
      <span
        className={`absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 text-xs rounded-lg shadow-lg w-56 text-center transition-opacity pointer-events-none
          ${isDark ? 'bg-slate-800 text-slate-200 border border-slate-700' : 'bg-slate-900 text-white'}
          ${open ? 'opacity-100' : 'opacity-0 group-hover/infotip:opacity-100'}`}
      >
        {text}
        <span className={`absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent ${
          isDark ? 'border-t-slate-800' : 'border-t-slate-900'
        }`} />
      </span>
    </span>
  );
};
