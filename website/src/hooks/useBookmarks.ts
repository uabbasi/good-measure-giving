/**
 * Hook for managing charity bookmarks
 * Uses TanStack Query for caching + useMutation for optimistic updates
 */

import { useCallback, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { collection, doc, getDocs, setDoc, deleteDoc, updateDoc, orderBy, query, Timestamp } from 'firebase/firestore';
import { useFirebaseData } from '../auth/FirebaseProvider';
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

function docToBookmark(docData: Record<string, unknown>, docId: string, userId: string): Bookmark {
  return {
    id: docId,
    userId,
    charityEin: docData.charityEin as string,
    notes: (docData.notes as string) || null,
    createdAt: docData.createdAt instanceof Timestamp
      ? docData.createdAt.toDate().toISOString()
      : (docData.createdAt as string) || new Date().toISOString(),
  };
}

export function useBookmarks(): UseBookmarksResult {
  const { db, userId } = useFirebaseData();
  const queryClient = useQueryClient();

  const bookmarksQueryKey = ['bookmarks', userId];

  // Fetch bookmarks
  const { data: bookmarks = [], isLoading, error: queryError } = useQuery({
    queryKey: bookmarksQueryKey,
    queryFn: async () => {
      if (!db || !userId) return [];

      const colRef = collection(db, 'users', userId, 'bookmarks');
      const q = query(colRef, orderBy('createdAt', 'desc'));
      const snapshot = await getDocs(q);
      return snapshot.docs.map(d => docToBookmark(d.data(), d.id, userId));
    },
    enabled: !!db && !!userId,
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
      if (!db || !userId) throw new Error('Not authenticated');

      const docRef = doc(db, 'users', userId, 'bookmarks', ein);
      const data = {
        charityEin: ein,
        notes: notes || null,
        createdAt: Timestamp.now(),
      };
      await setDoc(docRef, data);
      return docToBookmark({ ...data, createdAt: data.createdAt }, ein, userId);
    },
    onMutate: async ({ ein, notes }) => {
      await queryClient.cancelQueries({ queryKey: bookmarksQueryKey });
      const previous = queryClient.getQueryData<Bookmark[]>(bookmarksQueryKey);

      const optimistic: Bookmark = {
        id: ein,
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
      if (!db || !userId) throw new Error('Not authenticated');

      const docRef = doc(db, 'users', userId, 'bookmarks', ein);
      await deleteDoc(docRef);
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
      if (!db || !userId) throw new Error('Not authenticated');

      const docRef = doc(db, 'users', userId, 'bookmarks', ein);
      await updateDoc(docRef, { notes });
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
