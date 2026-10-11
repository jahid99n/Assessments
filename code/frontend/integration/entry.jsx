// Separate test entry, never imported by production main.jsx.
import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "../src/App.jsx";
import { RuntimeProvider } from "../src/runtime.jsx";
import { createApi } from "../src/lib/api.js";
import { postReceipt } from "../src/lib/upload.js";
import "../src/styles.css";
const apiFor = (user = "alice") =>
  createApi({
    baseUrl: "http://127.0.0.1:5181",
    getToken: async () => `local-${user}`,
  });
window.integrationApi = apiFor; // test harness only; actual API adapter over HTTP
const auth = {
  session: async () => ({
    name: "Local integration user",
    email: "alice@example.com",
    emailVerified: true,
  }),
  subscribe: () => () => {},
};
createRoot(document.getElementById("root")).render(
  <RuntimeProvider
    runtime={{ auth, api: apiFor(), upload: postReceipt, demo: false }}
  >
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </RuntimeProvider>,
);
