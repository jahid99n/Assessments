export function assertBuildMode(command, mode = "production", nodeEnv) {
  if (!["production", "demo"].includes(mode))
    throw new Error("VITE_APP_MODE must be production or demo.");
  if (command === "build" && (mode === "demo" || nodeEnv === "development")) {
    throw new Error("Production builds cannot contain development/demo mode.");
  }
}

export function readConfig(env, dev) {
  const demo = dev && env.VITE_APP_MODE === "demo";
  if (env.VITE_APP_MODE === "demo" && !dev)
    throw new Error("Demo mode is development-only.");
  return {
    demo,
    apiUrl: (env.VITE_API_URL || "").replace(/\/$/, ""),
    userPoolId: env.VITE_COGNITO_USER_POOL_ID || "",
    clientId: env.VITE_COGNITO_CLIENT_ID || "",
    domain: env.VITE_COGNITO_DOMAIN || "",
    redirectIn: env.VITE_REDIRECT_SIGN_IN || "",
    redirectOut: env.VITE_REDIRECT_SIGN_OUT || "",
  };
}

export function configError(config) {
  if (config.demo) return "";
  if (
    !config.apiUrl ||
    !config.userPoolId ||
    !config.clientId ||
    !config.domain ||
    !config.redirectIn ||
    !config.redirectOut
  ) {
    return "AWS connection is not configured. Set the frontend environment variables before signing in.";
  }
  try {
    if (new URL(config.apiUrl).protocol !== "https:") throw new Error();
    if (!/^[a-zA-Z0-9.-]+$/.test(config.domain)) throw new Error();
    for (const redirect of [config.redirectIn, config.redirectOut]) {
      const url = new URL(redirect);
      if (
        url.protocol !== "https:" &&
        !(
          url.protocol === "http:" &&
          ["localhost", "127.0.0.1"].includes(url.hostname)
        )
      )
        throw new Error();
    }
  } catch {
    return "Check the configured HTTPS API, Cognito domain and redirect URLs.";
  }
  return "";
}
