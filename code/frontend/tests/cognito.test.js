import { beforeEach, describe, expect, it, vi } from "vitest";

const sdk = vi.hoisted(() => ({
  configure: vi.fn(),
  fetchAuthSession: vi.fn(),
  signInWithRedirect: vi.fn(),
  signOut: vi.fn(),
  setKeyValueStorage: vi.fn(),
  listen: vi.fn(),
  sessionStorage: { name: "sdk-session-storage" },
}));
vi.mock("aws-amplify", () => ({ Amplify: { configure: sdk.configure } }));
vi.mock("aws-amplify/auth", () => ({
  fetchAuthSession: sdk.fetchAuthSession,
  signInWithRedirect: sdk.signInWithRedirect,
  signOut: sdk.signOut,
}));
vi.mock("aws-amplify/auth/cognito", () => ({
  cognitoUserPoolsTokenProvider: { setKeyValueStorage: sdk.setKeyValueStorage },
}));
vi.mock("aws-amplify/utils", () => ({
  Hub: { listen: sdk.listen },
  sessionStorage: sdk.sessionStorage,
}));
import { createCognitoAuth } from "../src/lib/cognito.js";

const config = {
  userPoolId: "ap-southeast-2_EXAMPLE",
  clientId: "public-client-id",
  domain: "example.auth.ap-southeast-2.amazoncognito.com",
  redirectIn: "http://localhost:5173/auth/callback",
  redirectOut: "http://localhost:5173/login",
};
beforeEach(() => {
  Object.values(sdk)
    .filter((v) => typeof v === "function")
    .forEach((fn) => fn.mockReset());
});
describe("Cognito SDK integration (mocked, no real authentication)", () => {
  it("uses the OAuth code flow and tab-scoped SDK token storage", () => {
    createCognitoAuth(config);
    expect(
      sdk.configure.mock.calls[0][0].Auth.Cognito.loginWith.oauth,
    ).toMatchObject({
      responseType: "code",
      scopes: ["openid", "email", "profile"],
      redirectSignIn: [config.redirectIn],
    });
    expect(sdk.setKeyValueStorage).toHaveBeenCalledWith(sdk.sessionStorage);
  });
  it("uses the ID token required by the existing API contract", async () => {
    sdk.fetchAuthSession.mockResolvedValue({
      tokens: {
        idToken: { toString: () => "MOCK_ID_TOKEN" },
        accessToken: { toString: () => "MOCK_ACCESS_TOKEN" },
      },
    });
    expect(await createCognitoAuth(config).token()).toBe("MOCK_ID_TOKEN");
  });
  it("restores verified email from SDK session claims", async () => {
    sdk.fetchAuthSession.mockResolvedValue({
      tokens: {
        idToken: {
          payload: { email: "test@example.com", email_verified: true },
        },
      },
    });
    expect(await createCognitoAuth(config).session()).toEqual({
      email: "test@example.com",
      emailVerified: true,
      name: "Your account",
    });
  });
  it("returns no user when there is no authenticated session", async () => {
    sdk.fetchAuthSession.mockResolvedValue({});
    expect(await createCognitoAuth(config).session()).toBeNull();
  });
  it("delegates login and logout to Amplify", async () => {
    const auth = createCognitoAuth(config);
    await auth.signIn();
    await auth.signOut();
    expect(sdk.signInWithRedirect).toHaveBeenCalledOnce();
    expect(sdk.signOut).toHaveBeenCalledOnce();
  });
  it("notifies the UI of session changes and allows cleanup", () => {
    const auth = createCognitoAuth(config),
      update = vi.fn(),
      unsubscribe = auth.subscribe(update);
    sdk.listen.mock.calls[0][1]({ payload: { event: "signedIn" } });
    expect(update).toHaveBeenCalledOnce();
    unsubscribe();
    sdk.listen.mock.calls[0][1]({ payload: { event: "signedOut" } });
    expect(update).toHaveBeenCalledOnce();
  });
  it("turns OAuth callback failure into a safe authentication error", async () => {
    const auth = createCognitoAuth(config);
    sdk.listen.mock.calls[0][1]({
      payload: {
        event: "signInWithRedirect_failure",
        data: "sensitive provider message",
      },
    });
    await expect(auth.session()).rejects.toThrow(
      "Sign-in could not be completed",
    );
  });
});
