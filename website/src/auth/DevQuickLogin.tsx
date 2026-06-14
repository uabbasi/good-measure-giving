/**
 * DevQuickLogin — floating quick-login pill for local/emulator dogfooding.
 *
 * Renders ONLY when `devLoginEnabled()` (DEV + emulator + localhost). It lets a
 * developer sign in as a pre-defined test persona without typing credentials,
 * driving the same `window.__TEST_AUTH__` seam Playwright uses. NEVER ships to
 * production: the env gate is impossible in prod builds.
 */

import { useState } from 'react';
import { updateProfile } from 'firebase/auth';
import { devLoginEnabled } from './devLoginEnabled';
import { useAuth } from './useAuth';
import { auth } from './firebase';
import { seedTestUser, type SeededPersona } from './devSeed';
import { DEV_TEST_USERS, type DevTestUser } from './devTestUsers';

const COLLAPSED_KEY = 'gmg_devlogin_collapsed';

const TEST_AUTH = () =>
  (
    window as unknown as {
      __TEST_AUTH__?: {
        signUp(e: string, p: string): Promise<void>;
        signIn(e: string, p: string): Promise<void>;
        signOutTest(): Promise<void>;
      };
    }
  ).__TEST_AUTH__;

export function DevQuickLogin() {
  if (!devLoginEnabled()) return null;

  const { isSignedIn, email } = useAuth();
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(COLLAPSED_KEY) === '1';
    } catch {
      return false;
    }
  });
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function toggleCollapsed(next: boolean) {
    setCollapsed(next);
    try {
      localStorage.setItem(COLLAPSED_KEY, next ? '1' : '0');
    } catch {
      /* storage unavailable — non-fatal for a dev tool */
    }
  }

  async function login(u: DevTestUser) {
    const t = TEST_AUTH();
    if (!t) {
      setError('Emulator test-auth seam not available');
      return;
    }
    setBusy(u.id);
    setError(null);
    try {
      // Sign in first so repeat logins (the common case) make no failing network
      // call; only create the user the first time it doesn't exist yet.
      try {
        await t.signIn(u.email, u.password);
      } catch {
        await t.signUp(u.email, u.password);
      }
      if (auth?.currentUser && !auth.currentUser.displayName) {
        await updateProfile(auth.currentUser, { displayName: u.displayName });
      }
      if (u.seed && auth?.currentUser) await seedTestUser(auth.currentUser.uid, u.id as SeededPersona);
    } catch (e) {
      setError(String((e as Error)?.message ?? e));
    } finally {
      setBusy(null);
    }
  }

  async function signOut() {
    setError(null);
    try {
      await TEST_AUTH()?.signOutTest();
    } catch (e) {
      setError(String((e as Error)?.message ?? e));
    }
  }

  const panel: React.CSSProperties = {
    background: '#1f2937',
    color: '#f9fafb',
    borderRadius: 8,
    padding: 12,
    fontSize: 13,
    fontFamily: 'system-ui, sans-serif',
    boxShadow: '0 4px 16px rgba(0,0,0,0.35)',
    width: 220,
  };

  const btn: React.CSSProperties = {
    display: 'block',
    width: '100%',
    textAlign: 'left',
    background: '#374151',
    color: '#f9fafb',
    border: '1px solid #4b5563',
    borderRadius: 6,
    padding: '6px 10px',
    marginTop: 6,
    cursor: 'pointer',
    fontSize: 13,
  };

  return (
    <div className="fixed bottom-4 left-4 z-[60]">
      {collapsed ? (
        <button
          type="button"
          onClick={() => toggleCollapsed(false)}
          style={{
            background: '#1f2937',
            color: '#f9fafb',
            border: '1px solid #4b5563',
            borderRadius: 999,
            padding: '6px 12px',
            fontSize: 13,
            cursor: 'pointer',
            boxShadow: '0 4px 16px rgba(0,0,0,0.35)',
          }}
        >
          🔓 Dev login
        </button>
      ) : (
        <div style={panel}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 4,
            }}
          >
            <span style={{ fontWeight: 700, letterSpacing: 0.5, color: '#fbbf24' }}>
              🔓 DEV LOGIN
            </span>
            <button
              type="button"
              onClick={() => toggleCollapsed(true)}
              aria-label="Collapse dev login"
              style={{
                background: 'transparent',
                color: '#9ca3af',
                border: 'none',
                cursor: 'pointer',
                fontSize: 16,
                lineHeight: 1,
              }}
            >
              ×
            </button>
          </div>

          {isSignedIn ? (
            <>
              <div style={{ color: '#d1d5db', wordBreak: 'break-all' }}>{email}</div>
              <button type="button" style={btn} onClick={signOut}>
                Sign out
              </button>
            </>
          ) : (
            DEV_TEST_USERS.map((u) => (
              <button
                key={u.id}
                type="button"
                style={{ ...btn, opacity: busy ? 0.6 : 1 }}
                disabled={!!busy}
                onClick={() => login(u)}
              >
                {busy === u.id ? '… ' : ''}Login: {u.label}
              </button>
            ))
          )}

          {error && (
            <div style={{ color: '#fca5a5', marginTop: 8, fontSize: 12 }}>{error}</div>
          )}
        </div>
      )}
    </div>
  );
}
