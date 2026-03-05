/**
 * Sign In Button Component - shows sign-in options for community membership
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import {
  GoogleAuthProvider,
  OAuthProvider,
  signInWithPopup,
  signInWithRedirect,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  updateProfile,
  signOut,
} from 'firebase/auth';
import { auth, isConfigured } from './firebase';
import { useAuth } from './useAuth';
import { trackSignIn, trackSignInError } from '../utils/analytics';

interface SignInButtonProps {
  variant?: 'default' | 'compact' | 'button' | 'custom';
  className?: string;
  children?: React.ReactNode;
  isDark?: boolean;
  context?: string;
}

type Screen = 'providers' | 'email';

export const SignInButton: React.FC<SignInButtonProps> = ({
  variant = 'default',
  className = '',
  children,
  isDark = false,
  context
}) => {
  const { isSignedIn, firstName } = useAuth();
  const [showMenu, setShowMenu] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  // Auth flow state
  const [screen, setScreen] = useState<Screen>('providers');
  const [signInError, setSignInError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Email state
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isNewAccount, setIsNewAccount] = useState(false);

  const resetAuthState = useCallback(() => {
    setScreen('providers');
    setSignInError(null);
    setIsSubmitting(false);
    setFullName('');
    setEmail('');
    setPassword('');
    setIsNewAccount(false);
  }, []);

  const closeModal = useCallback(() => {
    setShowMenu(false);
    resetAuthState();
  }, [resetAuthState]);

  // Close on Escape key (backdrop click handled inline)
  useEffect(() => {
    if (!showMenu) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeModal();
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
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

  const isMobileBrowser = () =>
    /Android|iPhone|iPad|iPod|Opera Mini|IEMobile|WPDesktop/i.test(navigator.userAgent);

  // Google sign-in
  const signInWithGoogle = async () => {
    if (!auth || !isConfigured) return;
    setSignInError(null);
    trackSignIn('google');
    const provider = new GoogleAuthProvider();
    try {
      if (isMobileBrowser()) {
        await signInWithRedirect(auth, provider);
      } else {
        await signInWithPopup(auth, provider);
      }
    } catch (err: unknown) {
      const code = (err as { code?: string })?.code ?? 'unknown';
      if (code === 'auth/popup-closed-by-user') return;
      console.error('Sign-in error:', err);
      trackSignInError('google', code);
      setSignInError('Something went wrong. Please try again or use a different method.');
    }
  };

  // Apple sign-in
  const signInWithApple = async () => {
    if (!auth || !isConfigured) return;
    setSignInError(null);
    trackSignIn('apple');
    const provider = new OAuthProvider('apple.com');
    provider.addScope('email');
    provider.addScope('name');
    try {
      if (isMobileBrowser()) {
        await signInWithRedirect(auth, provider);
      } else {
        const result = await signInWithPopup(auth, provider);
        if (result.user && !result.user.displayName) {
          window.dispatchEvent(new CustomEvent('gmg:needs-name'));
        }
      }
    } catch (err: unknown) {
      const code = (err as { code?: string })?.code ?? 'unknown';
      if (code === 'auth/popup-closed-by-user') return;
      console.error('Apple sign-in error:', err);
      trackSignInError('apple', code);
      setSignInError(
        code === 'auth/operation-not-allowed'
          ? 'Apple sign-in is not available. Please use Google or email.'
          : 'Something went wrong. Please try again or use a different method.'
      );
    }
  };

  // Email sign-in / sign-up
  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!auth || !email || !password) return;
    setSignInError(null);
    setIsSubmitting(true);
    trackSignIn('email');
    try {
      if (isNewAccount) {
        const { user } = await createUserWithEmailAndPassword(auth, email, password);
        if (fullName.trim()) {
          await updateProfile(user, { displayName: fullName.trim() });
        }
      } else {
        await signInWithEmailAndPassword(auth, email, password);
      }
    } catch (err: unknown) {
      const code = (err as { code?: string })?.code ?? 'unknown';
      console.error('Email sign-in error:', err);
      trackSignInError('email', code);
      if (code === 'auth/user-not-found' || code === 'auth/invalid-credential') {
        setSignInError('No account found. Create one instead?');
        setIsNewAccount(true);
      } else if (code === 'auth/wrong-password') {
        setSignInError('Incorrect password. Please try again.');
      } else if (code === 'auth/email-already-in-use') {
        setSignInError('An account with this email already exists. Try signing in.');
        setIsNewAccount(false);
      } else if (code === 'auth/weak-password') {
        setSignInError('Password must be at least 6 characters.');
      } else if (code === 'auth/invalid-email') {
        setSignInError('Please enter a valid email address.');
      } else {
        setSignInError('Something went wrong. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSignOut = async () => {
    if (!auth) return;
    await signOut(auth);
    setShowMenu(false);
  };

  // Back button for sub-screens
  const BackButton = () => (
    <button
      type="button"
      onClick={() => { setScreen('providers'); setSignInError(null); }}
      className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 mb-4"
    >
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
      </svg>
      Back
    </button>
  );

  const ErrorMessage = () => signInError ? (
    <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700 text-center">
      {signInError}
    </div>
  ) : null;

  const inputClasses = "w-full px-4 py-3 border border-slate-200 rounded-xl text-base focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent";
  const submitClasses = "w-full px-6 py-3 bg-emerald-600 text-white rounded-xl font-medium hover:bg-emerald-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed";

  // Signed in - show user menu (portaled to escape navbar stacking context)
  if (isSignedIn) {
    // Compute dropdown position from the button's bounding rect
    const getDropdownStyle = (): React.CSSProperties => {
      if (!containerRef.current) return { top: '4rem', right: '1rem' };
      const rect = containerRef.current.getBoundingClientRect();
      return {
        position: 'fixed',
        top: rect.bottom + 8,
        right: Math.max(8, window.innerWidth - rect.right),
      };
    };

    return (
      <div className="relative" ref={containerRef}>
        <button
          onClick={() => setShowMenu(!showMenu)}
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
        {showMenu && createPortal(
          <div className="fixed inset-0 z-[9998]" onClick={() => setShowMenu(false)}>
            <div
              className={`w-48 rounded-lg shadow-xl border py-1 ${
                isDark ? 'bg-slate-700 border-slate-600' : 'bg-white border-slate-200'
              }`}
              style={getDropdownStyle()}
              ref={modalRef}
              onClick={(e) => e.stopPropagation()}
            >
              <button
                onClick={handleSignOut}
                className={`w-full px-4 py-2 text-left text-sm ${
                  isDark ? 'text-slate-200 hover:bg-slate-600' : 'text-slate-700 hover:bg-slate-50'
                }`}
              >
                Sign out
              </button>
            </div>
          </div>,
          document.body
        )}
      </div>
    );
  }

  // Signed out - sign in modal as inline JSX (not a component — avoids remount on state change)
  const signInModal = showMenu && !isSignedIn ? createPortal(
    <div
      className="fixed inset-0 bg-black/50 z-[100] flex items-center justify-center"
      onClick={closeModal}
    >
      <div ref={modalRef} role="dialog" aria-modal="true" aria-labelledby="signin-modal-title" onClick={(e) => e.stopPropagation()} className="relative w-[calc(100%-2rem)] max-w-md max-h-[calc(100vh-2rem)] bg-white rounded-2xl shadow-2xl overflow-y-auto overscroll-contain">
        {/* Header with logo - only on providers screen */}
        {screen === 'providers' && (
          <div className="px-8 pt-8 pb-6 text-center border-b border-slate-100">
            <div className="flex justify-center mb-4">
              <img
                src="/favicon.svg"
                alt="Good Measure"
                className="w-16 h-16 rounded-2xl shadow-lg"
              />
            </div>
            <h2 id="signin-modal-title" className="text-2xl font-bold text-slate-900 mb-2">
              {context ? `Sign in to see ${context}` : 'See the Full Picture'}
            </h2>
            <p className="text-slate-500 max-w-xs mx-auto">
              Unlock detailed evaluations — impact evidence, financial analysis, leadership data, and donor fit for every charity. Free, always.
            </p>
          </div>
        )}

        {/* Sign in content */}
        <div className="px-8 py-6 space-y-3">
          {!isConfigured ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
              Sign-in is temporarily unavailable in this environment. Please try again after Firebase auth variables are configured.
            </div>
          ) : screen === 'providers' ? (
            <>
              <button
                onClick={signInWithGoogle}
                className="w-full flex items-center justify-center gap-3 px-6 py-4 border border-slate-200 rounded-xl hover:bg-slate-50 hover:border-slate-300 transition-colors select-none touch-manipulation"
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
                onClick={signInWithApple}
                className="w-full flex items-center justify-center gap-3 px-6 py-4 border border-slate-200 rounded-xl hover:bg-slate-50 hover:border-slate-300 transition-colors select-none touch-manipulation"
              >
                <svg className="w-6 h-6" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M17.05 20.28c-.98.95-2.05.8-3.08.35-1.09-.46-2.09-.48-3.24 0-1.44.62-2.2.44-3.06-.35C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.54 4.09l.01-.01zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z"/>
                </svg>
                <span className="text-base font-medium text-slate-700">Continue with Apple</span>
              </button>

              {/* Divider */}
              <div className="relative my-1">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-slate-200" />
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="bg-white px-4 text-slate-400">or</span>
                </div>
              </div>

              <button
                onClick={() => { setScreen('email'); setSignInError(null); }}
                className="w-full flex items-center justify-center gap-3 px-6 py-4 border border-slate-200 rounded-xl hover:bg-slate-50 hover:border-slate-300 transition-colors select-none touch-manipulation"
              >
                <svg className="w-6 h-6 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
                </svg>
                <span className="text-base font-medium text-slate-700">Continue with email</span>
              </button>

              <ErrorMessage />
            </>
          ) : screen === 'email' ? (
            <>
              <BackButton />
              <h3 className="text-lg font-semibold text-slate-900 mb-1">
                {isNewAccount ? 'Create an account' : 'Sign in with email'}
              </h3>
              <form onSubmit={handleEmailSubmit} className="space-y-3">
                {isNewAccount && (
                  <input
                    type="text"
                    placeholder="Your name"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className={inputClasses}
                    autoComplete="name"
                    autoFocus
                  />
                )}
                <input
                  type="email"
                  placeholder="Email address"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={inputClasses}
                  required
                  autoComplete="email"
                  autoFocus
                />
                <input
                  type="password"
                  placeholder={isNewAccount ? 'Create a password (6+ characters)' : 'Password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={inputClasses}
                  required
                  minLength={6}
                  autoComplete={isNewAccount ? 'new-password' : 'current-password'}
                />
                <button type="submit" disabled={isSubmitting} className={submitClasses}>
                  {isSubmitting ? 'Please wait...' : isNewAccount ? 'Create account' : 'Sign in'}
                </button>
                <ErrorMessage />
                <button
                  type="button"
                  onClick={() => { setIsNewAccount(!isNewAccount); setSignInError(null); }}
                  className="w-full text-sm text-emerald-600 hover:text-emerald-500"
                >
                  {isNewAccount ? 'Already have an account? Sign in' : "Don't have an account? Create one"}
                </button>
              </form>
            </>
          ) : null}
        </div>

        {/* Footer - only on providers screen */}
        {screen === 'providers' && (
          <div className="px-8 py-5 bg-slate-50 border-t border-slate-100">
            <p className="text-xs text-slate-400 text-center">
              We only use your name and email to personalize your experience. No spam, ever.
            </p>
          </div>
        )}

        {/* Close button */}
        <button
          onClick={closeModal}
          aria-label="Close"
          className="absolute top-4 right-4 p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>,
    document.body
  ) : null;

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
        {signInModal}
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
        {signInModal}
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
          See Full Evaluations — Free
        </button>
        {signInModal}
      </div>
    );
  }

  return (
    <div className="relative" ref={containerRef}>
      <button
        onClick={() => setShowMenu(!showMenu)}
        className={`px-6 py-3 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-500 transition-colors ${className}`}
      >
        See Full Evaluations — Free
      </button>
      {signInModal}
    </div>
  );
};
