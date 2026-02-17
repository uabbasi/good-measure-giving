/**
 * Firebase Authentication Provider
 */

import React, { createContext, useContext, useEffect, useState } from 'react';
import { onAuthStateChanged, User } from 'firebase/auth';
import { Firestore } from 'firebase/firestore';
import { auth, db, isConfigured } from './firebase';
import { trackSignInSuccess } from '../utils/analytics';

interface FirebaseAuthContextType {
  user: User | null;
  isLoading: boolean;
}

interface FirebaseDataContextType {
  db: Firestore | null;
  userId: string | null;
}

const AuthContext = createContext<FirebaseAuthContextType>({
  user: null,
  isLoading: true,
});

const DataContext = createContext<FirebaseDataContextType>({
  db: null,
  userId: null,
});

export const useFirebaseAuth = () => useContext(AuthContext);
export const useFirebaseData = () => useContext(DataContext);

interface Props {
  children: React.ReactNode;
}

export const FirebaseProvider: React.FC<Props> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!auth) {
      if (import.meta.env.DEV) {
        console.warn('Firebase not configured - auth disabled');
      }
      setIsLoading(false);
      return;
    }

    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      const previousUser = user;
      setUser(firebaseUser);
      setIsLoading(false);

      // Track sign-in
      if (firebaseUser && !previousUser) {
        const provider = firebaseUser.providerData[0]?.providerId || 'unknown';
        const createdAt = new Date(firebaseUser.metadata.creationTime || 0).getTime();
        const isNewUser = Date.now() - createdAt < 60_000;
        trackSignInSuccess(provider, isNewUser ? 'signup' : 'login');
      }
    });

    return () => unsubscribe();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const dataValue: FirebaseDataContextType = {
    db: db,
    userId: user?.uid || null,
  };

  return (
    <AuthContext.Provider value={{ user, isLoading }}>
      <DataContext.Provider value={dataValue}>
        {children}
      </DataContext.Provider>
    </AuthContext.Provider>
  );
};
