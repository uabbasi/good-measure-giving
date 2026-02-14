/**
 * Auth module - Firebase-based authentication
 *
 * Requires VITE_FIREBASE_API_KEY and VITE_FIREBASE_PROJECT_ID in environment.
 */

export { FirebaseProvider } from './FirebaseProvider';
export { useFirebaseAuth, useFirebaseData } from './FirebaseProvider';
export { useAuth, useCommunityMember } from './useAuth';
export { SignInButton } from './SignInButton';
export { CommunityGate, JoinCommunityPrompt } from './CommunityGate';
