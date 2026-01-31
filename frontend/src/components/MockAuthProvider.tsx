"use client";

import React, { createContext, useContext, ReactNode } from "react";

/**
 * Mock User Profile
 */
const mockUser = {
  id: "local-user",
  profile: {
    sub: "local-user",
    email: "local@scrollwise.app",
    email_verified: true,
    name: "Local User",
  },
  access_token: "mock-token",
  id_token: "mock-token",
  session_state: null,
  token_type: "Bearer",
  scope: "openid email profile",
  expires_at: Math.floor(Date.now() / 1000) + 3600,
};

/**
 * Mock Auth Context Interface
 */
interface AuthContextProps {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: typeof mockUser | null;
  error: Error | null;
  signinRedirect: () => Promise<void>;
  signoutRedirect: () => Promise<void>;
}

const AuthContext = createContext<AuthContextProps | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const value: AuthContextProps = {
    isAuthenticated: true,
    isLoading: false,
    user: mockUser,
    error: null,
    signinRedirect: async () => { },
    signoutRedirect: async () => { },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
