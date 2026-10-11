import { defineConfig } from "@playwright/test";
import { fileURLToPath } from "node:url";
const cwd = fileURLToPath(new URL("..", import.meta.url));
export default defineConfig({
  testDir: ".",
  testMatch: "*.spec.js",
  workers: 1,
  timeout: 45000,
  use: { baseURL: "http://127.0.0.1:5180", channel: "msedge" },
  reporter: [
    ["list"],
    [
      "junit",
      {
        outputFile: fileURLToPath(
          new URL("../../../report/stage4-integration.xml", import.meta.url),
        ),
      },
    ],
  ],
  webServer: [
    {
      cwd,
      command: "uv run --frozen python ../integration/server.py",
      url: "http://127.0.0.1:5181/health",
      reuseExistingServer: false,
    },
    {
      cwd,
      command:
        "node node_modules/vite/bin/vite.js --config integration/vite.config.js",
      url: "http://127.0.0.1:5180",
      reuseExistingServer: false,
    },
  ],
});
