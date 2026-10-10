import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { readConfig, configError } from "./config.js";
import { createApi } from "./lib/api.js";
import { postReceipt } from "./lib/upload.js";
import { RuntimeProvider } from "./runtime.jsx";
import App from "./App.jsx";
import "./styles.css";

async function start() {
  const config = readConfig(import.meta.env, import.meta.env.DEV);
  let runtime;
  if (import.meta.env.DEV && config.demo) {
    const { createDemoApi, createDemoAuth } = await import("./lib/demo.js");
    const api = createDemoApi();
    runtime = {
      api,
      auth: createDemoAuth(),
      demo: true,
      upload: api.simulateUpload,
    };
  } else {
    const issue = configError(config);
    if (issue) {
      runtime = {
        demo: false,
        configurationError: issue,
        auth: {
          async session() {
            return null;
          },
          subscribe() {
            return () => {};
          },
        },
      };
    } else {
      const { createCognitoAuth } = await import("./lib/cognito.js");
      const auth = createCognitoAuth(config);
      runtime = {
        auth,
        demo: false,
        upload: postReceipt,
        api: createApi({
          baseUrl: config.apiUrl,
          getToken: () => auth.token(),
          onUnauthorized: () => auth.invalidate(),
        }),
      };
    }
  }
  createRoot(document.getElementById("root")).render(
    <React.StrictMode>
      <RuntimeProvider runtime={runtime}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </RuntimeProvider>
    </React.StrictMode>,
  );
}
start().catch(() => {
  const root = document.getElementById("root");
  root.textContent =
    "The application could not start. Check configuration or clear incompatible local demo data, then reload.";
  root.setAttribute("role", "alert");
});
