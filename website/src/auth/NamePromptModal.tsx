/**
 * NamePromptModal - Prompts for display name after OAuth sign-in when missing.
 * Listens for 'gmg:needs-name' custom event (fired by Apple/redirect sign-in flows).
 */

import React, { useState, useEffect, useCallback } from 'react';
import { updateProfile } from 'firebase/auth';
import { auth } from './firebase';

const SESSION_KEY = 'gmg-name-prompted';

export const NamePromptModal: React.FC = () => {
  const [visible, setVisible] = useState(false);
  const [name, setName] = useState('');
  const [saving, setSaving] = useState(false);

  const dismiss = useCallback(() => {
    setVisible(false);
    setName('');
  }, []);

  useEffect(() => {
    const handle = () => {
      if (sessionStorage.getItem(SESSION_KEY)) return;
      sessionStorage.setItem(SESSION_KEY, '1');
      setVisible(true);
    };

    window.addEventListener('gmg:needs-name', handle);
    return () => window.removeEventListener('gmg:needs-name', handle);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !auth?.currentUser) return;
    setSaving(true);
    try {
      await updateProfile(auth.currentUser, { displayName: name.trim() });
      // Force auth state refresh so useAuth picks up the new name
      await auth.currentUser.reload();
      window.dispatchEvent(new Event('gmg:name-updated'));
      dismiss();
    } catch (err) {
      console.error('Failed to update name:', err);
    } finally {
      setSaving(false);
    }
  };

  if (!visible) return null;

  return (
    <div
      className="fixed inset-0 bg-black/50 z-[200] flex items-center justify-center"
      onClick={dismiss}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-[calc(100%-2rem)] max-w-sm bg-white rounded-2xl shadow-2xl overflow-hidden"
      >
        <div className="px-6 pt-6 pb-4 text-center">
          <h2 className="text-lg font-semibold text-slate-900 mb-1">
            What should we call you?
          </h2>
          <p className="text-sm text-slate-500">
            Just your first name is fine — it helps personalize your experience.
          </p>
        </div>
        <form onSubmit={handleSubmit} className="px-6 pb-6 space-y-3">
          <input
            type="text"
            placeholder="Your name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full px-4 py-3 border border-slate-200 rounded-xl text-base focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
            autoComplete="name"
            autoFocus
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={dismiss}
              className="flex-1 px-4 py-3 border border-slate-200 rounded-xl text-slate-600 hover:bg-slate-50 transition-colors"
            >
              Skip
            </button>
            <button
              type="submit"
              disabled={!name.trim() || saving}
              className="flex-1 px-4 py-3 bg-emerald-600 text-white rounded-xl font-medium hover:bg-emerald-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
