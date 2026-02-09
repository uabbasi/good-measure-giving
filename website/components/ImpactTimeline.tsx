import React, { useState } from 'react';
import { Clock, Calendar, ArrowRight, Coffee, BookOpen } from 'lucide-react';

export const ImpactTimeline: React.FC = () => {
  const [mode, setMode] = useState<'relief' | 'release'>('relief');

  return (
    <div className="w-full max-w-3xl mx-auto bg-white rounded-2xl border border-slate-200 shadow-xl overflow-hidden">
      {/* Header / Toggle */}
      <div className="bg-slate-50 border-b border-slate-200 p-1 flex justify-center">
        <div className="flex bg-white rounded-xl border border-slate-200 p-1 shadow-sm">
          <button
            onClick={() => setMode('relief')}
            className={`px-6 py-2 rounded-lg text-sm font-bold transition-all ${
              mode === 'relief'
                ? 'bg-slate-900 text-white shadow-md'
                : 'text-slate-500 hover:text-slate-900'
            }`}
          >
            Short-Term Relief
          </button>
          <button
            onClick={() => setMode('release')}
            className={`px-6 py-2 rounded-lg text-sm font-bold transition-all ${
              mode === 'release'
                ? 'bg-emerald-600 text-white shadow-md'
                : 'text-slate-500 hover:text-slate-900'
            }`}
          >
            Long-Term Release
          </button>
        </div>
      </div>

      {/* Content Area */}
      <div className="p-8 md:p-12">

        {/* Scenario Description */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-slate-50 mb-6 shadow-sm border border-slate-100">
            {mode === 'relief' ? (
              <Coffee className="w-8 h-8 text-amber-600" />
            ) : (
              <BookOpen className="w-8 h-8 text-emerald-600" />
            )}
          </div>
          <h3 className="text-2xl font-bold font-merriweather text-slate-900 mb-3">
            {mode === 'relief' ? 'The Standard Donation' : 'The Strategic Investment'}
          </h3>
          <p className="text-lg text-slate-600 max-w-lg mx-auto">
            {mode === 'relief'
              ? 'A $50 donation provides a food basket. The hunger is satisfied for today.'
              : 'A $50 donation funds vocational training materials. The hunger is prevented forever.'}
          </p>
        </div>

        {/* Timeline Visualization */}
        <div className="relative pt-8 pb-4">
          {/* Base Line */}
          <div className="absolute top-0 left-0 w-full h-0.5 bg-slate-100 top-[15px]"></div>

          {/* Ticks */}
          <div className="flex justify-between text-xs font-bold text-slate-400 uppercase tracking-wider relative z-10">
            <div className="text-center w-20">
              <div className="w-0.5 h-2 bg-slate-200 mx-auto mb-2"></div>
              Day 1
            </div>
            <div className="text-center w-20">
              <div className="w-0.5 h-2 bg-slate-200 mx-auto mb-2"></div>
              Month 1
            </div>
            <div className="text-center w-20">
              <div className="w-0.5 h-2 bg-slate-200 mx-auto mb-2"></div>
              Year 1
            </div>
            <div className="text-center w-20">
              <div className="w-0.5 h-2 bg-slate-200 mx-auto mb-2"></div>
              Year 10
            </div>
          </div>

          {/* Active Progress Bar */}
          <div className="absolute top-[15px] left-0 h-1 bg-gradient-to-r from-slate-900 to-transparent w-full opacity-10"></div>

          {/* Dynamic Bar */}
          <div
            className={`absolute top-[13px] left-0 h-1.5 rounded-full transition-all duration-1000 ease-out ${
              mode === 'relief' ? 'bg-amber-500 w-[15%]' : 'bg-emerald-500 w-full'
            }`}
          >
            {/* Pulse Effect at end of bar */}
            <div className={`absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 rounded-full shadow-lg transform scale-100 ${
               mode === 'relief' ? 'bg-amber-500' : 'bg-emerald-500'
            }`}>
              <div className="absolute inset-0 rounded-full bg-white opacity-50 animate-ping"></div>
            </div>
          </div>

          {/* Impact Text Overlay */}
          <div
            className={`absolute top-8 text-sm font-bold transition-all duration-700 ${
               mode === 'relief' ? 'left-[10%] text-amber-700' : 'left-[80%] text-emerald-700'
            }`}
          >
            {mode === 'relief' ? 'Impact Ends' : 'Sadaqah Jariyah Flows'}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="bg-slate-50 px-8 py-4 text-center border-t border-slate-200">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-widest">
          {mode === 'relief' ? 'Duration: 24 Hours' : 'Duration: A Lifetime'}
        </p>
      </div>
    </div>
  );
};
