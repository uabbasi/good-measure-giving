/**
 * Hook for managing charity bookmarks
 * Uses TanStack Query for caching + useMutation for optimistic updates
 */

import { useCallback, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSupabase } from '../auth/SupabaseProvider';
import type { Bookmark } from '../../types';

interface UseBookmarksResult {
  bookmarks: Bookmark[];
  bookmarkedEins: Set<string>;
  isLoading: boolean;
  error: string | null;
  isBookmarked: (ein: string) => boolean;
  toggleBookmark: (ein: string) => Promise<void>;
  addBookmark: (ein: string, notes?: string) => Promise<void>;
  removeBookmark: (ein: string) => Promise<void>;
  updateNotes: (ein: string, notes: string | null) => Promise<void>;
  getBookmark: (ein: string) => Bookmark | undefined;
  refreshBookmarks: () => Promise<void>;
}

// Convert snake_case DB row to camelCase
function dbToBookmark(row: Record<string, unknown>): Bookmark {
  return {
    id: row.id as string,
    userId: row.user_id as string,
    charityEin: row.charity_ein as string,
    notes: row.notes as string | null,
    createdAt: row.created_at as string,
  };
}

export function useBookmarks(): UseBookmarksResult {
  const { supabase, session } = useSupabase();
  const queryClient = useQueryClient();
  const userId = session?.user?.id;

  const bookmarksQueryKey = ['bookmarks', userId];

  // Fetch bookmarks
  const { data: bookmarks = [], isLoading, error: queryError } = useQuery({
    queryKey: bookmarksQueryKey,
    queryFn: async () => {
      if (!supabase || !userId) return [];

      const { data, error: fetchError } = await supabase
        .from('bookmarks')
        .select('*')
        .eq('user_id', userId)
        .order('created_at', { ascending: false });

      if (fetchError) throw fetchError;
      return (data || []).map(dbToBookmark);
    },
    enabled: !!supabase && !!userId,
  });

  const error = queryError
    ? (queryError instanceof Error ? queryError.message : 'Failed to load bookmarks')
    : null;

  // Create a Set of bookmarked EINs for O(1) lookup
  const bookmarkedEins = useMemo(() => {
    return new Set(bookmarks.map(b => b.charityEin));
  }, [bookmarks]);

  // Add bookmark mutation
  const addMutation = useMutation({
    mutationFn: async ({ ein, notes }: { ein: string; notes?: string }) => {
      if (!supabase || !userId) throw new Error('Not authenticated');

      const { data, error: insertError } = await supabase
        .from('bookmarks')
        .insert({ user_id: userId, charity_ein: ein, notes: notes || null })
        .select()
        .single();

      if (insertError) throw insertError;
      return dbToBookmark(data);
    },
    onMutate: async ({ ein, notes }) => {
      await queryClient.cancelQueries({ queryKey: bookmarksQueryKey });
      const previous = queryClient.getQueryData<Bookmark[]>(bookmarksQueryKey);

      const optimistic: Bookmark = {
        id: `temp-${Date.now()}`,
        userId: userId!,
        charityEin: ein,
        notes: notes || null,
        createdAt: new Date().toISOString(),
      };
      queryClient.setQueryData<Bookmark[]>(bookmarksQueryKey, old => [optimistic, ...(old || [])]);
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(bookmarksQueryKey, context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: bookmarksQueryKey });
    },
  });

  // Remove bookmark mutation
  const removeMutation = useMutation({
    mutationFn: async (ein: string) => {
      if (!supabase || !userId) throw new Error('Not authenticated');

      const { error: deleteError } = await supabase
        .from('bookmarks')
        .delete()
        .eq('user_id', userId)
        .eq('charity_ein', ein);

      if (deleteError) throw deleteError;
    },
    onMutate: async (ein) => {
      await queryClient.cancelQueries({ queryKey: bookmarksQueryKey });
      const previous = queryClient.getQueryData<Bookmark[]>(bookmarksQueryKey);

      queryClient.setQueryData<Bookmark[]>(bookmarksQueryKey, old =>
        (old || []).filter(b => b.charityEin !== ein)
      );
      return { previous };
    },
    onError: (_err, _ein, context) => {
      if (context?.previous) {
        queryClient.setQueryData(bookmarksQueryKey, context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: bookmarksQueryKey });
    },
  });

  // Update notes mutation
  const updateNotesMutation = useMutation({
    mutationFn: async ({ ein, notes }: { ein: string; notes: string | null }) => {
      if (!supabase || !userId) throw new Error('Not authenticated');

      const { error: updateError } = await supabase
        .from('bookmarks')
        .update({ notes })
        .eq('user_id', userId)
        .eq('charity_ein', ein);

      if (updateError) throw updateError;
    },
    onMutate: async ({ ein, notes }) => {
      await queryClient.cancelQueries({ queryKey: bookmarksQueryKey });
      const previous = queryClient.getQueryData<Bookmark[]>(bookmarksQueryKey);

      queryClient.setQueryData<Bookmark[]>(bookmarksQueryKey, old =>
        (old || []).map(b => b.charityEin === ein ? { ...b, notes } : b)
      );
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(bookmarksQueryKey, context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: bookmarksQueryKey });
    },
  });

  // Public API (same interface as before)
  const isBookmarked = useCallback((ein: string): boolean => {
    return bookmarkedEins.has(ein);
  }, [bookmarkedEins]);

  const getBookmark = useCallback((ein: string): Bookmark | undefined => {
    return bookmarks.find(b => b.charityEin === ein);
  }, [bookmarks]);

  const addBookmark = useCallback(async (ein: string, notes?: string) => {
    await addMutation.mutateAsync({ ein, notes });
  }, [addMutation]);

  const removeBookmark = useCallback(async (ein: string) => {
    await removeMutation.mutateAsync(ein);
  }, [removeMutation]);

  const toggleBookmark = useCallback(async (ein: string) => {
    if (isBookmarked(ein)) {
      await removeBookmark(ein);
    } else {
      await addBookmark(ein);
    }
  }, [isBookmarked, removeBookmark, addBookmark]);

  const updateNotes = useCallback(async (ein: string, notes: string | null) => {
    await updateNotesMutation.mutateAsync({ ein, notes });
  }, [updateNotesMutation]);

  const refreshBookmarks = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: bookmarksQueryKey });
  }, [queryClient, bookmarksQueryKey]);

  return {
    bookmarks,
    bookmarkedEins,
    isLoading,
    error,
    isBookmarked,
    toggleBookmark,
    addBookmark,
    removeBookmark,
    updateNotes,
    getBookmark,
    refreshBookmarks,
  };
}
