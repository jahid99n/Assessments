import { Amplify } from "aws-amplify";
import {
  fetchAuthSession,
  signInWithRedirect,
  signOut,
} from "aws-amplify/auth";
import { cognitoUserPoolsTokenProvider } from "aws-amplify/auth/cognito";
import { Hub, sessionStorage } from "aws-amplify/utils";

export function createCognitoAuth(config) {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: config.userPoolId,
        userPoolClientId: config.clientId,
        loginWith: {
          oauth: {
            domain: config.domain,
            scopes: ["openid", "email", "profile"],
            redirectSignIn: [config.redirectIn],
            redirectSignOut: [config.redirectOut],
            responseType: "code",
          },
        },
      },
    },
  });
  cognitoUserPoolsTokenProvider.setKeyValueStorage(sessionStorage);
  const listeners = new Set();
  let authError = "";
  Hub.listen("auth", ({ payload }) => {
    if (
      ["signInWithRedirect_failure", "tokenRefresh_failure"].includes(
        payload.event,
      )
    )
      authError = "Sign-in could not be completed. Please try again.";
    if (
      [
        "signedIn",
        "signedOut",
        "signInWithRedirect",
        "signInWithRedirect_failure",
        "tokenRefresh_failure",
      ].includes(payload.event)
    )
      listeners.forEach((fn) => fn());
  });
  return {
    async session() {
      if (authError) {
        const error = authError;
        authError = "";
        throw new Error(error);
      }
      const { tokens } = await fetchAuthSession();
      const claims = tokens?.idToken?.payload;
      return claims
        ? {
            email: claims.email || "",
            emailVerified:
              claims.email_verified === true ||
              claims.email_verified === "true",
            name: claims.given_name || "Your account",
          }
        : null;
    },
    async token() {
      const { tokens } = await fetchAuthSession();
      return tokens?.idToken?.toString();
    },
    async signIn() {
      await signInWithRedirect();
    },
    async signOut() {
      await signOut();
    },
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    invalidate() {
      authError = "Your session expired. Please sign in again.";
      listeners.forEach((fn) => fn());
    },
  };
}
