import type { ReactNode } from "react";
import { Navigate } from "@tanstack/react-router";

// Placeholder until Auth0 is wired in.
const isAuthenticated = true;

interface AuthGuardProps {
  children: ReactNode;
}

export function AuthGuard({ children }: AuthGuardProps) {
  if (!isAuthenticated) {
    return <Navigate to="/" />;
  }
  return <>{children}</>;
}
