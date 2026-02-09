/**
 * Auth module - Supabase-based authentication
 *
 * Requires VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in environment.
 */

export { SupabaseProvider } from './SupabaseProvider';
export { useSupabase } from './SupabaseProvider';
export { useAuth, useCommunityMember } from './useAuth';
export { SignInButton } from './SignInButton';
export { CommunityGate, JoinCommunityPrompt } from './CommunityGate';
