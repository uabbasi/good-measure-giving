/**
 * Supabase Authentication Provider
 */

import React, { createContext, useContext, useEffect, useState } from 'react';
import { createClient, SupabaseClient, Session, AuthChangeEvent } from '@supabase/supabase-js';
import { trackSignInSuccess } from '../utils/analytics';

interface SupabaseContextType {
  supabase: SupabaseClient | null;
  session: Session | null;
  isLoading: boolean;
}

const SupabaseContext = createContext<SupabaseContextType>({
  supabase: null,
  session: null,
  isLoading: true,
});

export const useSupabase = () => useContext(SupabaseContext);

interface Props {
  children: React.ReactNode;
}

// Check config at module level
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;
const isConfigured = !!(supabaseUrl && supabaseAnonKey);

// Create client once at module level (if configured)
const supabaseClient = isConfigured
  ? createClient(supabaseUrl, supabaseAnonKey)
  : null;

export const SupabaseProvider: React.FC<Props> = ({ children }) => {
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!supabaseClient) {
      // Only warn in development to avoid noisy console in production
      if (import.meta.env.DEV) {
        console.warn('Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY - auth disabled');
      }
      setIsLoading(false);
      return;
    }

    // Get initial session
    supabaseClient.auth.getSession()
      .then(({ data: { session } }) => {
        setSession(session);
        setIsLoading(false);
      })
      .catch((error) => {
        // Invalid refresh token - clear the stale session
        console.warn('Session refresh failed, signing out:', error.message);
        supabaseClient.auth.signOut();
        setSession(null);
        setIsLoading(false);
      });

    // Listen for auth changes
    const { data: { subscription } } = supabaseClient.auth.onAuthStateChange(
      (event: AuthChangeEvent, session) => {
        setSession(session);

        // Track successful sign-ins
        if (event === 'SIGNED_IN' && session?.user) {
          const provider = session.user.app_metadata?.provider || 'unknown';

          // Detect new signup vs returning login
          // If user was created within last 60 seconds, it's a new signup
          const createdAt = new Date(session.user.created_at).getTime();
          const isNewUser = Date.now() - createdAt < 60_000;

          trackSignInSuccess(provider, isNewUser ? 'signup' : 'login');
        }
      }
    );

    return () => subscription.unsubscribe();
  }, []);

  return (
    <SupabaseContext.Provider value={{ supabase: supabaseClient, session, isLoading }}>
      {children}
    </SupabaseContext.Provider>
  );
};
