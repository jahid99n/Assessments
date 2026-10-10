import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./browser-tests",
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  reporter: [
    ["list"],
    ["junit", { outputFile: "../../report/stage3-browser-results.xml" }],
  ],
  use: {
    baseURL: "http://127.0.0.1:5173",
    channel: "msedge",
    headless: true,
    viewport: { width: 1440, height: 1100 },
    trace: "retain-on-failure",
  },
  webServer: {
    command: `${process.platform === "win32" ? "npm.cmd" : "npm"} run demo -- --port 5173 --strictPort`,
    url: "http://127.0.0.1:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
  },
});
