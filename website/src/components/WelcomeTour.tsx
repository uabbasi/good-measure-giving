/**
 * WelcomeTour — Lightweight modal shown once on first sign-in.
 *
 * Replaces WelcomeToast. Listens for 'gmg:welcome' custom event.
 * Shows 4 feature cards + two CTAs: "Start exploring" or "Set up giving plan →".
 * Uses localStorage (permanent) so it never shows again.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { BookOpen, Target, FolderOpen, Bookmark, X } from 'lucide-react';
import { useLandingTheme } from '../../contexts/LandingThemeContext';

const STORAGE_KEY = 'gmg_welcome_tour_shown';

const FEATURES = [
  {
    icon: BookOpen,
    title: 'Full evaluations unlocked',
    desc: 'Deep analysis on all 170+ charities',
  },
  {
    icon: Target,
    title: 'Set a zakat target',
    desc: 'Track your annual giving goal',
  },
  {
    icon: FolderOpen,
    title: 'Organize with giving buckets',
    desc: 'Group charities by cause area or priority',
  },
  {
    icon: Bookmark,
    title: 'Save & compare charities',
    desc: 'Bookmark and compare side by side',
  },
];

export const WelcomeTour: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const navigate = useNavigate();
  const { isDark } = useLandingTheme();

  const dismiss = useCallback(() => {
    setIsOpen(false);
    try {
      localStorage.setItem(STORAGE_KEY, 'true');
    } catch {
      // fail silently
    }
  }, []);

  useEffect(() => {
    const handleWelcome = () => {
      try {
        if (localStorage.getItem(STORAGE_KEY)) return;
      } catch {
        // If localStorage unavailable, show anyway
      }
      setIsOpen(true);
    };

    window.addEventListener('gmg:welcome', handleWelcome);
    return () => window.removeEventListener('gmg:welcome', handleWelcome);
  }, []);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === e.currentTarget) dismiss(); }}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

      {/* Modal */}
      <div className={`relative w-full max-w-md rounded-2xl shadow-2xl overflow-hidden ${
        isDark ? 'bg-slate-900 border border-slate-700' : 'bg-white border border-slate-200'
      }`}>
        {/* Close button */}
        <button
          onClick={dismiss}
          className={`absolute top-4 right-4 p-1 rounded-full transition-colors ${
            isDark ? 'text-slate-400 hover:text-white hover:bg-slate-700' : 'text-slate-400 hover:text-slate-600 hover:bg-slate-100'
          }`}
          aria-label="Close"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className={`px-6 pt-6 pb-4 text-center ${
          isDark ? 'bg-gradient-to-b from-slate-800 to-slate-900' : 'bg-gradient-to-b from-slate-50 to-white'
        }`}>
          <h2 className={`text-xl font-bold font-merriweather ${isDark ? 'text-white' : 'text-slate-900'}`}>
            Welcome to Good Measure
          </h2>
          <p className={`text-sm mt-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
            Here's what you can do now
          </p>
        </div>

        {/* Feature cards */}
        <div className="px-6 py-4 space-y-2.5">
          {FEATURES.map(({ icon: Icon, title, desc }) => (
            <div
              key={title}
              className={`flex items-start gap-3 p-3 rounded-xl ${
                isDark ? 'bg-slate-800/60 border border-slate-700/50' : 'bg-slate-50 border border-slate-100'
              }`}
            >
              <Icon className={`w-5 h-5 mt-0.5 flex-shrink-0 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} />
              <div>
                <div className={`text-sm font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
                  {title}
                </div>
                <div className={`text-xs mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  {desc}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* CTAs */}
        <div className="px-6 pb-6 flex gap-3">
          <button
            onClick={dismiss}
            className={`flex-1 px-4 py-3 rounded-xl text-sm font-semibold transition-colors ${
              isDark
                ? 'bg-slate-700 text-white hover:bg-slate-600'
                : 'bg-slate-900 text-white hover:bg-slate-800'
            }`}
          >
            Start exploring
          </button>
          <button
            onClick={() => { dismiss(); navigate('/profile'); }}
            className={`px-4 py-3 rounded-xl text-sm font-medium transition-colors ${
              isDark
                ? 'bg-transparent text-slate-300 border border-slate-600 hover:bg-slate-800'
                : 'bg-transparent text-slate-600 border border-slate-300 hover:bg-slate-50'
            }`}
          >
            Set up giving plan →
          </button>
        </div>
      </div>
    </div>
  );
};
