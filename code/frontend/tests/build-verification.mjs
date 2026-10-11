// Run after npm run build. Only localhost and local build processes are used.
import assert from "node:assert/strict";
import { execFileSync, spawn } from "node:child_process";
import { readFile, readdir, writeFile } from "node:fs/promises";
import { chromium } from "@playwright/test";

const results = [];
const record = (name) => {
  results.push({ name, result: "PASS" });
  console.log(`PASS ${name}`);
};
const vite = "node_modules/vite/bin/vite.js";
for (const [label, args, env] of [
  [
    "demo production build is rejected",
    ["build", "--mode", "demo"],
    { VITE_APP_MODE: "demo", NODE_ENV: "production" },
  ],
  [
    "development NODE_ENV build bypass is rejected",
    ["build"],
    { VITE_APP_MODE: "production", NODE_ENV: "development" },
  ],
]) {
  let rejected = false;
  try {
    execFileSync(process.execPath, [vite, ...args], {
      env: { ...process.env, ...env },
      windowsHide: true,
      stdio: "pipe",
    });
  } catch (error) {
    rejected =
      error.status !== 0 &&
      String(error.stderr).includes("cannot contain development/demo mode");
  }
  assert.ok(rejected, label);
  record(label);
}
const assetNames = await readdir("dist/assets");
const scripts = (
  await Promise.all(
    assetNames
      .filter((name) => name.endsWith(".js"))
      .map((name) => readFile(`dist/assets/${name}`, "utf8")),
  )
).join("\n");
for (const forbidden of [
  "smart-expense-demo-v1",
  "DEMO_NO_NETWORK",
  "integrationApi",
  "local-alice",
  "Previous month sample",
  "Demo receipt · simulated",
])
  assert.ok(
    !scripts.includes(forbidden),
    `Demo implementation marker found: ${forbidden}`,
  );
record("production bundles exclude the demo adapter, storage and seed data");
const server = spawn(
  process.execPath,
  [vite, "preview", "--host", "127.0.0.1", "--port", "5174", "--strictPort"],
  { windowsHide: true, stdio: "ignore" },
);
let browser;
try {
  for (let i = 0; i < 100; i++) {
    if (server.exitCode !== null)
      throw new Error("Preview server exited before starting.");
    try {
      const response = await fetch("http://127.0.0.1:5174");
      if (response.ok) break;
    } catch {
      /* localhost not ready */
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  browser = await chromium.launch({ channel: "msedge", headless: true });
  const page = await browser.newPage();
  const external = [],
    errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/*", async (route) => {
    if (new URL(route.request().url()).hostname !== "127.0.0.1") {
      external.push(route.request().url());
      await route.abort();
    } else await route.continue();
  });
  await page.goto("http://127.0.0.1:5174");
  await page
    .getByRole("alert")
    .filter({ hasText: "AWS connection is not configured" })
    .waitFor();
  assert.equal(
    await page
      .getByRole("button", { name: "Sign in with Cognito" })
      .isDisabled(),
    true,
  );
  assert.equal(
    await page.getByText("DEMO WORKSPACE", { exact: true }).count(),
    0,
  );
  assert.deepEqual(external, []);
  assert.deepEqual(errors, []);
  record(
    "unconfigured production build fails closed in a real browser without AWS calls",
  );
} finally {
  if (browser) await browser.close();
  server.kill();
}
await writeFile(
  "../../report/build-checks.json",
  JSON.stringify(
    { checks: results.length, passed: results.length, failed: 0, results },
    null,
    2,
  ) + "\n",
);
