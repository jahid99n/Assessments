import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";
export default defineConfig(({ command }) => {
  if (command !== "serve")
    throw new Error("Integration harness must never be built");
  return {
    cacheDir: "node_modules/.vite-integration",
    plugins: [
      react(),
      {
        name: "local-integration-entry",
        configureServer(server) {
          server.middlewares.use((req, res, next) => {
            if (req.headers.accept?.includes("text/html")) {
              server
                .transformIndexHtml(
                  req.url,
                  readFileSync("integration/index.html", "utf8"),
                )
                .then((html) => {
                  res.setHeader("Content-Type", "text/html");
                  res.end(html);
                })
                .catch(next);
            } else next();
          });
        },
      },
    ],
    server: { host: "127.0.0.1", port: 5180, strictPort: true },
  };
});
