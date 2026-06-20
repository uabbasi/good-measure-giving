// Good Measure Giving — "Modern" motif sign-in modal.
// Self-contained and isolated (like every motif surface): it calls Firebase
// directly and carries the sage-on-bone palette, so the moment a donor signs in
// from a motif page they stay in the motif rather than dropping into the legacy
// emerald/slate auth card. Independence-framed copy — no "free" promises.

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
} from 'firebase/auth';
import { auth, isConfigured } from '../../auth/firebase';
import { trackSignIn, trackSignInError } from '../../utils/analytics';
import {
  GmgPalette,
  FONT_DISPLAY,
  FONT_TEXT,
  FONT_MONO,
  FONT_THEMES,
  resolveFontVariant,
} from './tokens';
import { GmgLogo } from './primitives';

type Screen = 'providers' | 'email';

const isMobileBrowser = () =>
  typeof navigator !== 'undefined' &&
  /Android|iPhone|iPad|iPod|Opera Mini|IEMobile|WPDesktop/i.test(navigator.userAgent);

export const GmgSignIn: React.FC<{
  p: GmgPalette;
  open: boolean;
  onClose: () => void;
  context?: string;
}> = ({ p, open, onClose, context }) => {
  const modalRef = useRef<HTMLDivElement>(null);

  const [screen, setScreen] = useState<Screen>('providers');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isNewAccount, setIsNewAccount] = useState(false);

  const variant = resolveFontVariant(
    typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('type') : null,
  );
  const ft = FONT_THEMES[variant];
  const fontVars = {
    ['--gmg-display' as any]: ft.display,
    ['--gmg-text' as any]: ft.text,
    ['--gmg-mono' as any]: ft.mono,
    ['--gmg-arabic' as any]: ft.arabic,
  };

  const close = useCallback(() => {
    onClose();
    setScreen('providers');
    setError(null);
    setIsSubmitting(false);
    setFullName('');
    setEmail('');
    setPassword('');
    setIsNewAccount(false);
  }, [onClose]);

  // Dialog behaviors: Escape to close, Tab focus-trap, body-scroll lock, and
  // restore focus to the trigger on close.
  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const focusables = (): HTMLElement[] =>
      Array.from(
        modalRef.current?.querySelectorAll<HTMLElement>(
          'button, [href], input, [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      ).filter((el) => !el.hasAttribute('disabled'));

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        close();
        return;
      }
      if (e.key === 'Tab') {
        const items = focusables();
        if (!items.length) return;
        const first = items[0];
        const last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    document.addEventListener('keydown', onKey);
    focusables()[0]?.focus();
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
      previouslyFocused?.focus?.();
    };
  }, [open, close]);

  const signInWithGoogle = async () => {
    if (!auth || !isConfigured) return;
    setError(null);
    trackSignIn('google');
    const provider = new GoogleAuthProvider();
    try {
      if (isMobileBrowser()) await signInWithRedirect(auth, provider);
      else await signInWithPopup(auth, provider);
    } catch (err: unknown) {
      const code = (err as { code?: string })?.code ?? 'unknown';
      if (code === 'auth/popup-closed-by-user') return;
      trackSignInError('google', code);
      setError('Something went wrong. Please try again or use a different method.');
    }
  };

  const signInWithApple = async () => {
    if (!auth || !isConfigured) return;
    setError(null);
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
      trackSignInError('apple', code);
      setError(
        code === 'auth/operation-not-allowed'
          ? 'Apple sign-in is not available. Please use Google or email.'
          : 'Something went wrong. Please try again or use a different method.',
      );
    }
  };

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!auth || !email || !password) return;
    setError(null);
    setIsSubmitting(true);
    trackSignIn('email');
    try {
      if (isNewAccount) {
        const { user } = await createUserWithEmailAndPassword(auth, email, password);
        if (fullName.trim()) await updateProfile(user, { displayName: fullName.trim() });
      } else {
        await signInWithEmailAndPassword(auth, email, password);
      }
      close();
    } catch (err: unknown) {
      const code = (err as { code?: string })?.code ?? 'unknown';
      trackSignInError('email', code);
      if (code === 'auth/user-not-found' || code === 'auth/invalid-credential') {
        setError('No account found. Create one instead?');
        setIsNewAccount(true);
      } else if (code === 'auth/wrong-password') {
        setError('Incorrect password. Please try again.');
      } else if (code === 'auth/email-already-in-use') {
        setError('An account with this email already exists. Try signing in.');
        setIsNewAccount(false);
      } else if (code === 'auth/weak-password') {
        setError('Password must be at least 6 characters.');
      } else if (code === 'auth/invalid-email') {
        setError('Please enter a valid email address.');
      } else {
        setError('Something went wrong. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!open) return null;

  const providerBtn: React.CSSProperties = {
    width: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    padding: '13px 20px',
    border: `1px solid ${p.rule2}`,
    borderRadius: 12,
    background: 'transparent',
    color: p.fg,
    fontSize: 15,
    fontFamily: FONT_TEXT,
    cursor: 'pointer',
  };
  const inputStyle: React.CSSProperties = {
    width: '100%',
    boxSizing: 'border-box',
    padding: '12px 14px',
    border: `1px solid ${p.rule2}`,
    borderRadius: 12,
    background: p.bg2,
    color: p.fg,
    fontSize: 15,
    fontFamily: FONT_TEXT,
    outline: 'none',
  };

  const errorBox = error ? (
    <div
      role="alert"
      style={{
        borderRadius: 12,
        border: `1px solid ${p.neg}`,
        background: p.negBg,
        padding: '10px 12px',
        fontSize: 13,
        color: p.neg,
        textAlign: 'center',
      }}
    >
      {error}
    </div>
  ) : null;

  return createPortal(
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.55)',
        zIndex: 100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
      onClick={close}
    >
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="gmg-signin-title"
        onClick={(e) => e.stopPropagation()}
        style={{
          position: 'relative',
          width: '100%',
          maxWidth: 420,
          maxHeight: 'calc(100vh - 2rem)',
          overflowY: 'auto',
          background: p.bg,
          color: p.fg,
          fontFamily: FONT_TEXT,
          border: `1px solid ${p.rule2}`,
          borderRadius: 18,
          boxShadow: '0 24px 60px rgba(0,0,0,0.35)',
          ...fontVars,
        }}
      >
        {screen === 'providers' && (
          <div style={{ padding: '30px 30px 22px', textAlign: 'center', borderBottom: `1px solid ${p.rule}` }}>
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16 }}>
              <GmgLogo p={p} size={30} />
            </div>
            <h2 id="gmg-signin-title" style={{ fontFamily: FONT_DISPLAY, fontWeight: 400, fontSize: 27, lineHeight: 1.1, letterSpacing: ft.displayTracking, margin: '0 0 8px' }}>
              {context ? `Sign in to ${context}` : 'See the full picture'}
            </h2>
            <p style={{ fontSize: 14, lineHeight: 1.55, color: p.sub, maxWidth: 300, margin: '0 auto' }}>
              Save charities, build your giving plan, and track your zakat — across every device.
            </p>
          </div>
        )}

        <div style={{ padding: '22px 30px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          {!isConfigured ? (
            <div style={{ borderRadius: 12, border: `1px solid ${p.warn}`, background: p.warnBg, padding: 14, fontSize: 13, color: p.warn }}>
              Sign-in is temporarily unavailable in this environment.
            </div>
          ) : screen === 'providers' ? (
            <>
              <button type="button" onClick={signInWithGoogle} style={providerBtn}>
                <svg width={20} height={20} viewBox="0 0 24 24" aria-hidden="true">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                </svg>
                Continue with Google
              </button>
              <button type="button" onClick={signInWithApple} style={providerBtn}>
                <svg width={20} height={20} viewBox="0 0 24 24" fill={p.fg} aria-hidden="true">
                  <path d="M17.05 20.28c-.98.95-2.05.8-3.08.35-1.09-.46-2.09-.48-3.24 0-1.44.62-2.2.44-3.06-.35C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.54 4.09l.01-.01zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z" />
                </svg>
                Continue with Apple
              </button>

              <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '2px 0', color: p.sub2, fontSize: 12 }}>
                <span style={{ flex: 1, height: 1, background: p.rule }} />
                or
                <span style={{ flex: 1, height: 1, background: p.rule }} />
              </div>

              <button type="button" onClick={() => { setScreen('email'); setError(null); }} style={providerBtn}>
                Continue with email
              </button>
              {errorBox}
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={() => { setScreen('providers'); setError(null); }}
                style={{ alignSelf: 'flex-start', background: 'none', border: 'none', color: p.sub, fontSize: 13, cursor: 'pointer', padding: 0 }}
              >
                ← Back
              </button>
              <h3 style={{ fontFamily: FONT_DISPLAY, fontWeight: 400, fontSize: 20, margin: 0, letterSpacing: ft.displayTracking }}>
                {isNewAccount ? 'Create an account' : 'Sign in with email'}
              </h3>
              <form onSubmit={handleEmailSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {isNewAccount && (
                  <input type="text" aria-label="Your name" placeholder="Your name" value={fullName} onChange={(e) => setFullName(e.target.value)} style={inputStyle} autoComplete="name" />
                )}
                <input type="email" aria-label="Email address" aria-invalid={!!error} placeholder="Email address" value={email} onChange={(e) => setEmail(e.target.value)} style={inputStyle} required autoComplete="email" autoFocus />
                <input type="password" aria-label="Password" aria-invalid={!!error} placeholder={isNewAccount ? 'Create a password (6+ characters)' : 'Password'} value={password} onChange={(e) => setPassword(e.target.value)} style={inputStyle} required minLength={6} autoComplete={isNewAccount ? 'new-password' : 'current-password'} />
                <button
                  type="submit"
                  disabled={isSubmitting}
                  style={{ width: '100%', padding: '13px 20px', borderRadius: 12, border: 'none', background: p.chip, color: p.chipFg, fontSize: 15, fontWeight: 500, cursor: isSubmitting ? 'default' : 'pointer', opacity: isSubmitting ? 0.6 : 1 }}
                >
                  {isSubmitting ? 'Please wait…' : isNewAccount ? 'Create account' : 'Sign in'}
                </button>
                {errorBox}
                <button
                  type="button"
                  onClick={() => { setIsNewAccount(!isNewAccount); setError(null); }}
                  style={{ width: '100%', background: 'none', border: 'none', color: p.accent, fontSize: 13, cursor: 'pointer' }}
                >
                  {isNewAccount ? 'Already have an account? Sign in' : "Don't have an account? Create one"}
                </button>
              </form>
            </>
          )}
        </div>

        {screen === 'providers' && (
          <div style={{ padding: '14px 30px 20px', background: p.bg2, borderTop: `1px solid ${p.rule}`, borderRadius: '0 0 18px 18px' }}>
            <p style={{ fontSize: 11.5, lineHeight: 1.5, color: p.sub2, textAlign: 'center', margin: 0, fontFamily: FONT_MONO, letterSpacing: '0.02em' }}>
              We only use your name and email to personalize your experience. No spam, ever.
            </p>
          </div>
        )}

        <button
          type="button"
          onClick={close}
          aria-label="Close"
          style={{ position: 'absolute', top: 12, right: 12, padding: 8, background: 'none', border: 'none', color: p.sub, cursor: 'pointer', lineHeight: 0 }}
        >
          <svg width={18} height={18} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>,
    document.body,
  );
};

export default GmgSignIn;
