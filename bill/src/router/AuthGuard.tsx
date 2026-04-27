import type { ReactNode } from "react";
import { useAuth0 } from "@auth0/auth0-react";

interface AuthGuardProps {
  children: ReactNode;
}

const centerStyle = {
  display: "flex",
  flexDirection: "column" as const,
  alignItems: "center",
  justifyContent: "center",
  height: "100vh",
  width: "100vw",
  gap: 16,
  textAlign: "center" as const,
  padding: 24,
};

const messageStyle = {
  fontSize: 16,
  color: "#fff",
};

const linkStyle = {
  fontSize: 14,
  color: "#9ca3af",
  textDecoration: "underline",
};

const buttonStyle = {
  padding: "10px 20px",
  fontSize: 14,
  fontWeight: 500,
  color: "#000",
  background: "#fff",
  border: "none",
  borderRadius: 6,
  cursor: "pointer",
};

export function AuthGuard({ children }: AuthGuardProps) {
  const { isAuthenticated, isLoading, error, loginWithRedirect } = useAuth0();

  if (isLoading) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "100vh",
          width: "100vw",
        }}
      >
        <div
          style={{
            width: 40,
            height: 40,
            border: "3px solid rgba(255,255,255,0.15)",
            borderTopColor: "#fff",
            borderRadius: "50%",
            animation: "authguard-spin 0.8s linear infinite",
          }}
        />
        <style>{`@keyframes authguard-spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (error) {
    return (
      <div style={centerStyle}>
        <p style={messageStyle}>Access denied. This account is not authorized.</p>
        <a href="/" style={linkStyle}>Return to homepage</a>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div style={centerStyle}>
        <p style={messageStyle}>You must be logged in to view this page.</p>
        <button
          type="button"
          style={buttonStyle}
          onClick={() => loginWithRedirect({ appState: { returnTo: "/dashboard" } })}
        >
          Log in
        </button>
        <a href="/" style={linkStyle}>Return to homepage</a>
      </div>
    );
  }

  return <>{children}</>;
}
