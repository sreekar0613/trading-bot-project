import { useEffect } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { registerTokenGetter } from "@/services/api";

export function AuthSetup() {
  const { getAccessTokenSilently, isAuthenticated } = useAuth0();

  useEffect(() => {
    if (isAuthenticated) {
      registerTokenGetter(() =>
        getAccessTokenSilently({
          authorizationParams: {
            audience: import.meta.env.VITE_AUTH0_AUDIENCE,
          },
        })
      );
    }
  }, [isAuthenticated, getAccessTokenSilently]);

  return null;
}
