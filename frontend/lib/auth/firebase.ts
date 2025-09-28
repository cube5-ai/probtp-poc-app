/**
 * Firebase configuration and authentication
 */
import { type FirebaseApp, initializeApp } from 'firebase/app';
import {
    getAuth,
    signInWithEmailAndPassword,
    createUserWithEmailAndPassword,
    signOut as firebaseSignOut,
    onAuthStateChanged,
    type User as FirebaseUser,
    type Auth as FirebaseAuth
} from 'firebase/auth';

// Firebase config from environment variables
const firebaseConfig = {
    apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY || '',
    authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN || '',
    projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || '',
    storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET || '',
    messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID || '',
    appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID || '',
};

// Initialize Firebase only on client side
let app: FirebaseApp | null = null;
let auth: FirebaseAuth | null = null;

if (typeof window !== 'undefined') {
    app = initializeApp(firebaseConfig);
    auth = getAuth(app);
}

export { auth };

// Auth methods
export const authService = {
    signIn: (email: string, password: string) => {
        if (!auth) throw new Error('Firebase not initialized');
        return signInWithEmailAndPassword(auth, email, password);
    },

    signUp: (email: string, password: string) => {
        if (!auth) throw new Error('Firebase not initialized');
        return createUserWithEmailAndPassword(auth, email, password);
    },

    signOut: () => {
        if (!auth) throw new Error('Firebase not initialized');
        return firebaseSignOut(auth);
    },

    getCurrentUser: () => {
        if (!auth) return null;
        return auth.currentUser;
    },

    onAuthStateChanged: (callback: (user: FirebaseUser | null) => void) => {
        if (!auth) {
            callback(null);
            return () => { };
        }
        return onAuthStateChanged(auth, callback);
    },

    getIdToken: async (forceRefresh = false) => {
        if (!auth) return null;
        const user = auth.currentUser;
        if (user) {
            try {
                const token = await user.getIdToken(forceRefresh);

                // If force refreshing, add a small delay to prevent timing issues
                if (forceRefresh && token) {
                    await new Promise(resolve => setTimeout(resolve, 1100));
                }

                return token;
            } catch (error) {
                console.error('Error getting ID token:', error);
                // If token refresh fails, try once more after a delay
                if (forceRefresh) {
                    await new Promise(resolve => setTimeout(resolve, 2000));
                    return await user.getIdToken(true);
                }
                throw error;
            }
        }
        return null;
    },
};