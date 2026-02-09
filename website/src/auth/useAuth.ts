/**
 * Authentication hook - returns current auth state
 */

import { useSupabase } from './SupabaseProvider';

interface AuthState {
  isLoaded: boolean;
  isSignedIn: boolean;
  email: string | null;
  firstName: string | null;
}

export const useAuth = (): AuthState => {
  const { session, isLoading } = useSupabase();

  if (isLoading) {
    return { isLoaded: false, isSignedIn: false, email: null, firstName: null };
  }

  if (!session) {
    return { isLoaded: true, isSignedIn: false, email: null, firstName: null };
  }

  const user = session.user;
  // OAuth providers put name in user_metadata
  const metadata = user.user_metadata || {};
  const firstName = metadata.full_name?.split(' ')[0]
    || metadata.name?.split(' ')[0]
    || null;

  return {
    isLoaded: true,
    isSignedIn: true,
    email: user.email ?? null,
    firstName,
  };
};

/**
 * Check if user is a community member (signed in)
 */
export const useCommunityMember = (): boolean => {
  const { isLoaded, isSignedIn } = useAuth();
  return isLoaded && isSignedIn;
};
