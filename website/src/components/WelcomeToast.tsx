/**
 * WelcomeToast: Post-signup confirmation toast.
 * Listens for 'gmg:welcome' custom event, shows a brief message, auto-dismisses after 5s.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { X, CheckCircle } from 'lucide-react';

const SESSION_KEY = 'gmg-welcome-shown';

export const WelcomeToast: React.FC = () => {
  const [visible, setVisible] = useState(false);

  const dismiss = useCallback(() => setVisible(false), []);

  useEffect(() => {
    const handleWelcome = () => {
      if (sessionStorage.getItem(SESSION_KEY)) return;
      sessionStorage.setItem(SESSION_KEY, '1');
      setVisible(true);
    };

    window.addEventListener('gmg:welcome', handleWelcome);
    return () => window.removeEventListener('gmg:welcome', handleWelcome);
  }, []);

  // Auto-dismiss after 5s
  useEffect(() => {
    if (!visible) return;
    const timer = setTimeout(dismiss, 5000);
    return () => clearTimeout(timer);
  }, [visible, dismiss]);

  if (!visible) return null;

  return (
    <div
      className="fixed bottom-6 right-6 z-[200] max-w-sm animate-slide-in-right"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-start gap-3 px-5 py-4 rounded-xl shadow-2xl border bg-white border-slate-200 text-slate-800">
        <CheckCircle className="w-5 h-5 text-emerald-500 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="text-sm font-semibold">Welcome!</p>
          <p className="text-xs text-slate-500 mt-0.5">You now have full access to all evaluations.</p>
        </div>
        <button
          onClick={dismiss}
          aria-label="Close"
          className="p-1 text-slate-400 hover:text-slate-600 rounded-full transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
