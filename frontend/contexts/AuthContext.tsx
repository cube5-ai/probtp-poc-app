/**
 * Authentication Context using Firebase
 */
import React, { createContext, useContext, useEffect, useState } from "react";
import { type User } from "firebase/auth";
import { authService } from "../lib/auth/firebase";
import { apiClient } from "../lib/api/client";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  getIdToken: () => Promise<string | null>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Only run on client side
    if (typeof window === "undefined") {
      setLoading(false);
      return;
    }

    let tokenRefreshInterval: NodeJS.Timeout | null = null;

    // Listen for auth state changes
    const unsubscribe = authService.onAuthStateChanged(async (user) => {
      setUser(user);
      setLoading(false);

      // Clear any existing interval
      if (tokenRefreshInterval) {
        clearInterval(tokenRefreshInterval);
        tokenRefreshInterval = null;
      }

      // Update API client with auth token
      if (user) {
        try {
          const token = await user.getIdToken();
          apiClient.setAuthToken(token);

          // Set up token refresh timer for this user
          tokenRefreshInterval = setInterval(async () => {
            try {
              const freshToken = await user.getIdToken(true); // Force refresh
              if (freshToken) {
                apiClient.setAuthToken(freshToken);
              }
            } catch {
              // Silent error handling
            }
          }, 45 * 60 * 1000); // 45 minutes
        } catch (error) {
          console.error("Error getting Firebase token:", error);
        }
      } else {
        apiClient.clearAuth();
      }
    });

    return () => {
      unsubscribe();
      if (tokenRefreshInterval) {
        clearInterval(tokenRefreshInterval);
      }
    };
  }, []); // Remove user dependency to avoid recreating effect

  const signIn = async (email: string, password: string) => {
    try {
      await authService.signIn(email, password);
    } catch (error) {
      throw error;
    }
  };

  const signUp = async (email: string, password: string) => {
    try {
      await authService.signUp(email, password);
    } catch (error) {
      throw error;
    }
  };

  const signOut = async () => {
    try {
      await authService.signOut();
    } catch (error) {
      throw error;
    }
  };

  const getIdToken = async () => {
    return await authService.getIdToken();
  };

  const changePassword = async (currentPassword: string, newPassword: string) => {
    return authService.changePassword(currentPassword, newPassword);
  };

  const value = {
    user,
    loading,
    signIn,
    signUp,
    signOut,
    getIdToken,
    changePassword,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
