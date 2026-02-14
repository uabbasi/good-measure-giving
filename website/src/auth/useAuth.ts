/**
 * Authentication hook - returns current auth state
 */

import { useFirebaseAuth } from './FirebaseProvider';

interface AuthState {
  isLoaded: boolean;
  isSignedIn: boolean;
  email: string | null;
  firstName: string | null;
  uid: string | null;
}

export const useAuth = (): AuthState => {
  const { user, isLoading } = useFirebaseAuth();

  if (isLoading) {
    return { isLoaded: false, isSignedIn: false, email: null, firstName: null, uid: null };
  }

  if (!user) {
    return { isLoaded: true, isSignedIn: false, email: null, firstName: null, uid: null };
  }

  const firstName = user.displayName?.split(' ')[0] || null;

  return {
    isLoaded: true,
    isSignedIn: true,
    email: user.email ?? null,
    firstName,
    uid: user.uid,
  };
};

/**
 * Check if user is a community member (signed in)
 */
export const useCommunityMember = (): boolean => {
  const { isLoaded, isSignedIn } = useAuth();
  return isLoaded && isSignedIn;
};
