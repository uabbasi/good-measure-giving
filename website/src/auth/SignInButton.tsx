/**
 * Sign In Button Component - shows sign-in options for community membership
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useSupabase } from './SupabaseProvider';
import { useAuth } from './useAuth';
import { trackSignIn } from '../utils/analytics';

interface SignInButtonProps {
  variant?: 'default' | 'compact' | 'button' | 'custom';
  className?: string;
  children?: React.ReactNode;
  isDark?: boolean;
}

export const SignInButton: React.FC<SignInButtonProps> = ({
  variant = 'default',
  className = '',
  children,
  isDark = false
}) => {
  const { supabase } = useSupabase();
  const { isSignedIn, firstName } = useAuth();
  const [showMenu, setShowMenu] = useState(false);
  const [menuPos, setMenuPos] = useState<{ top: number; right: number } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  const closeModal = useCallback(() => setShowMenu(false), []);

  // Close on outside click or Escape key
  useEffect(() => {
    if (!showMenu) return;

    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      const clickedInsideTrigger = containerRef.current?.contains(target);
      const clickedInsideModal = modalRef.current?.contains(target);
      if (!clickedInsideTrigger && !clickedInsideModal) closeModal();
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeModal();
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [showMenu, closeModal]);

  // Focus trap: on modal open, focus first button; cycle Tab within modal
  useEffect(() => {
    if (!showMenu || !modalRef.current) return;
    const modal = modalRef.current;
    const focusable = modal.querySelectorAll<HTMLElement>('button, [href], input, [tabindex]:not([tabindex="-1"])');
    if (focusable.length) (focusable[0] as HTMLElement).focus();

    const handleTab = (e: KeyboardEvent) => {
      if (e.key !== 'Tab' || !focusable.length) return;
      const first = focusable[0] as HTMLElement;
      const last = focusable[focusable.length - 1] as HTMLElement;
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };

    document.addEventListener('keydown', handleTab);
    return () => document.removeEventListener('keydown', handleTab);
  }, [showMenu]);

  // Don't render sign-in UI when Supabase isn't configured
  if (!supabase && !isSignedIn) return null;

  const signInWith = async (provider: 'google' | 'apple') => {
    if (!supabase) return;
    trackSignIn(provider);
    await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo: window.location.origin,
      },
    });
  };

  const signOut = async () => {
    if (!supabase) return;
    await supabase.auth.signOut();
    setShowMenu(false);
  };

  // Signed in - show user menu (portaled to escape navbar stacking context)
  if (isSignedIn) {
    const handleToggleMenu = () => {
      if (!showMenu && containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setMenuPos({ top: rect.bottom + 8, right: window.innerWidth - rect.right });
      }
      setShowMenu(!showMenu);
    };

    return (
      <div className="relative" ref={containerRef}>
        <button
          onClick={handleToggleMenu}
          className={`flex items-center gap-2 text-sm font-medium ${
            isDark
              ? 'text-slate-200 hover:text-white'
              : 'text-slate-800 hover:text-slate-900'
          }`}
        >
          <span>{firstName || 'Member'}</span>
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        {showMenu && menuPos && createPortal(
          <>
            <div className="fixed inset-0 z-[199]" onClick={() => setShowMenu(false)} />
            <div
              className={`fixed w-48 rounded-lg shadow-2xl border-2 py-1 z-[200] ${
                isDark ? 'bg-slate-600 border-slate-500' : 'bg-white border-slate-200'
              }`}
              style={{ top: menuPos.top, right: menuPos.right }}
              ref={modalRef}
            >
              <button
                onClick={signOut}
                className={`w-full px-4 py-2 text-left text-sm ${
                  isDark ? 'text-white hover:bg-slate-500' : 'text-slate-700 hover:bg-slate-50'
                }`}
              >
                Sign out
              </button>
            </div>
          </>,
          document.body
        )}
      </div>
    );
  }

  // Signed out - show sign in modal (centered overlay, rendered via portal)
  const SignInModal = () => createPortal(
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-[100]"
        onClick={() => setShowMenu(false)}
      />
      {/* Modal */}
      <div ref={modalRef} role="dialog" aria-modal="true" aria-labelledby="signin-modal-title" className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md mx-4 bg-white rounded-2xl shadow-2xl z-[101] overflow-hidden overscroll-contain">
        {/* Header with logo */}
        <div className="px-8 pt-8 pb-6 text-center border-b border-slate-100">
          <div className="flex justify-center mb-4">
            <img
              src="/favicon.svg"
              alt="Good Measure"
              className="w-16 h-16 rounded-2xl shadow-lg"
            />
          </div>
          <h2 id="signin-modal-title" className="text-2xl font-bold text-slate-900 mb-2">
            Join the Community
          </h2>
          <p className="text-slate-500 max-w-xs mx-auto">
            Free access to independent charity research, donor insights, and giving guides.
          </p>
        </div>

        {/* Sign in options */}
        <div className="px-8 py-6 space-y-3">
          <button
            onClick={() => signInWith('google')}
            className="w-full flex items-center justify-center gap-3 px-6 py-4 border border-slate-200 rounded-xl hover:bg-slate-50 hover:border-slate-300 transition-colors"
          >
            <svg className="w-6 h-6" viewBox="0 0 24 24" aria-hidden="true">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            <span className="text-base font-medium text-slate-700">Continue with Google</span>
          </button>
          <button
            onClick={() => signInWith('apple')}
            className="w-full flex items-center justify-center gap-3 px-6 py-4 border border-slate-200 rounded-xl hover:bg-slate-50 hover:border-slate-300 transition-colors"
          >
            <svg className="w-6 h-6" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M17.05 20.28c-.98.95-2.05.8-3.08.35-1.09-.46-2.09-.48-3.24 0-1.44.62-2.2.44-3.06-.35C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.54 4.09l.01-.01zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z"/>
            </svg>
            <span className="text-base font-medium text-slate-700">Continue with Apple</span>
          </button>
        </div>

        {/* Footer */}
        <div className="px-8 py-5 bg-slate-50 border-t border-slate-100">
          <p className="text-xs text-slate-400 text-center">
            We only use your name and email to personalize your experience. No spam, ever.
          </p>
        </div>

        {/* Close button */}
        <button
          onClick={() => setShowMenu(false)}
          aria-label="Close"
          className="absolute top-4 right-4 p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </>,
    document.body
  );

  // Custom variant - wraps children as the clickable area
  if (variant === 'custom' && children) {
    return (
      <div className="relative" ref={containerRef}>
        <button
          onClick={() => setShowMenu(!showMenu)}
          className={className}
        >
          {children}
        </button>
        {showMenu && <SignInModal />}
      </div>
    );
  }

  if (variant === 'compact') {
    return (
      <div className="relative" ref={containerRef}>
        <button
          onClick={() => setShowMenu(!showMenu)}
          className={`text-sm font-medium text-emerald-600 hover:text-emerald-500 ${className}`}
        >
          Sign in
        </button>
        {showMenu && <SignInModal />}
      </div>
    );
  }

  if (variant === 'button') {
    return (
      <div className="relative" ref={containerRef}>
        <button
          onClick={() => setShowMenu(!showMenu)}
          className={className}
        >
          Join the Community
        </button>
        {showMenu && <SignInModal />}
      </div>
    );
  }

  return (
    <div className="relative" ref={containerRef}>
      <button
        onClick={() => setShowMenu(!showMenu)}
        className={`px-6 py-3 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-500 transition-colors ${className}`}
      >
        Join the Community
      </button>
      {showMenu && <SignInModal />}
    </div>
  );
};
