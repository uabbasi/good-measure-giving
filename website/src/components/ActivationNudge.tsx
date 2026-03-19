/**
 * ActivationNudge — Inline card that surfaces feature prompts at natural moments.
 *
 * Renders as a small inline card (not modal/toast) with icon, message,
 * action link, and dismiss button. Appears within page content.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { X } from 'lucide-react';
import { useLandingTheme } from '../../contexts/LandingThemeContext';
import type { NudgeConfig } from '../hooks/useActivationNudge';

interface ActivationNudgeProps {
  nudge: NudgeConfig;
  onDismiss: (nudgeId: string) => void;
}

export const ActivationNudge: React.FC<ActivationNudgeProps> = ({ nudge, onDismiss }) => {
  const [dismissed, setDismissed] = useState(false);
  const navigate = useNavigate();
  const { isDark } = useLandingTheme();

  if (dismissed) return null;

  const handleDismiss = () => {
    setDismissed(true);
    onDismiss(nudge.id);
  };

  const handleAction = () => {
    handleDismiss();
    navigate(nudge.actionPath);
  };

  return (
    <div
      className={`flex items-start gap-3 p-4 rounded-xl mt-4 animate-in fade-in slide-in-from-bottom-2 duration-300 ${
        isDark
          ? 'bg-blue-950/30 border border-blue-800/30'
          : 'bg-blue-50 border border-blue-200'
      }`}
    >
      <span className="text-xl flex-shrink-0">{nudge.icon}</span>
      <div className="flex-1 min-w-0">
        <div className={`text-sm font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
          {nudge.title}
        </div>
        <div className={`text-xs mt-1 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          {nudge.description}
        </div>
        <div className="flex items-center gap-3 mt-2">
          <button
            onClick={handleAction}
            className={`text-xs font-semibold transition-colors ${
              isDark ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-800'
            }`}
          >
            {nudge.actionLabel}
          </button>
          <button
            onClick={handleDismiss}
            className={`text-xs transition-colors ${
              isDark ? 'text-slate-500 hover:text-slate-400' : 'text-slate-400 hover:text-slate-600'
            }`}
          >
            Maybe later
          </button>
        </div>
      </div>
      <button
        onClick={handleDismiss}
        className={`flex-shrink-0 p-1 rounded-full transition-colors ${
          isDark ? 'text-slate-500 hover:text-slate-300 hover:bg-slate-700' : 'text-slate-400 hover:text-slate-600 hover:bg-slate-100'
        }`}
        aria-label="Dismiss"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
};
