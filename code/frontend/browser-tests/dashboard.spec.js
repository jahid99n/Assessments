import { test, expect } from "@playwright/test";
import { mkdir } from "node:fs/promises";

const screenshots = "../../report/stage3-screenshots";
let networkRequests;
let errors;
test.beforeEach(async ({ page }) => {
  networkRequests = [];
  errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (!["127.0.0.1", "localhost"].includes(url.hostname)) {
      networkRequests.push(url.origin);
      await route.abort();
    } else await route.continue();
  });
});
test.afterEach(() => {
  expect(networkRequests, "Demo must not call external services").toEqual([]);
  expect(errors, "No browser runtime errors").toEqual([]);
});

test("desktop dashboard renders real charts and screenshot", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Spending over time" }),
  ).toBeVisible();
  await expect(page.locator(".recharts-area path").first()).toBeVisible();
  await expect(page.getByText("DEMO WORKSPACE", { exact: true })).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await mkdir(screenshots, { recursive: true });
  await page.screenshot({
    path: `${screenshots}/dashboard-desktop.png`,
    fullPage: true,
  });
});

test("manual create, edit, details, filter, pagination and delete", async ({
  page,
}) => {
  await page.goto("/expenses");
  await page.getByRole("button", { name: "Add expense" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByLabel("Merchant", { exact: true })).toBeFocused();
  await dialog
    .getByLabel("Merchant", { exact: true })
    .fill("Browser test café");
  await dialog.getByLabel("Total (AUD)", { exact: true }).fill("18.90");
  await dialog.getByLabel("Category", { exact: true }).selectOption("Dining");
  await dialog.getByRole("button", { name: "Save expense" }).click();
  await expect(
    page.getByRole("button", { name: "Edit Browser test café" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Edit Browser test café" }).click();
  await dialog.getByLabel("Total (AUD)", { exact: true }).fill("21.50");
  await dialog.getByRole("button", { name: "Save expense" }).click();
  await page.getByRole("button", { name: "View Browser test café" }).click();
  await expect(dialog.locator(".detail-total")).toHaveText("$21.50");
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(
    page.getByRole("button", { name: "View Browser test café" }),
  ).toBeFocused();
  await page.getByLabel("Category", { exact: true }).selectOption("Dining");
  await expect(
    page.getByRole("button", { name: "Edit Browser test café" }),
  ).toBeVisible();
  await page
    .getByLabel("Search loaded expenses", { exact: true })
    .fill("Browser test");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page.getByRole("button", { name: "Reset", exact: true }).click();
  await page.getByRole("button", { name: "Load more expenses" }).click();
  await expect(
    page.getByRole("button", { name: "Edit Morning coffee" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Delete Browser test café" }).click();
  await dialog
    .getByRole("button", { name: "Delete expense", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Edit Browser test café" }),
  ).toHaveCount(0);
});

test("budget changes persist and notifications stay labelled simulated", async ({
  page,
}) => {
  await page.goto("/budget");
  await page
    .getByLabel("Monthly spending limit (AUD)", { exact: true })
    .fill("1750");
  await page.getByRole("button", { name: "Save budget", exact: true }).click();
  await expect(page.getByText("Budget and preferences saved.")).toBeVisible();
  await page.reload();
  await expect(
    page.getByLabel("Monthly spending limit (AUD)", { exact: true }),
  ).toHaveValue("1750");
  await expect(page.getByText("Demo only · no emails are sent")).toBeVisible();
});

test("receipt simulation reports processing then successful or failed outcome", async ({
  page,
}) => {
  await page.goto("/receipts");
  const png = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=",
    "base64",
  );
  await page
    .getByLabel("Receipt image", { exact: true })
    .setInputFiles({ name: "sample.png", mimeType: "image/png", buffer: png });
  await page.getByRole("button", { name: "Simulate receipt upload" }).click();
  await expect(
    page.getByRole("heading", { name: "Reading your receipt" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Demo receipt completed" }),
  ).toBeVisible({ timeout: 10000 });
  await page.screenshot({
    path: `${screenshots}/receipt-demo-completed.png`,
    fullPage: true,
  });
  await page
    .getByLabel("Receipt image", { exact: true })
    .setInputFiles({ name: "another.png", mimeType: "image/png", buffer: png });
  await page.getByLabel("Demonstration outcome").selectOption("failure");
  await page.getByRole("button", { name: "Simulate receipt upload" }).click();
  await expect(
    page.getByRole("heading", { name: "Receipt could not be processed" }),
  ).toBeVisible({ timeout: 10000 });
});

test("mobile layout stays within viewport and supports navigation and sign-out", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Spending over time" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: `${screenshots}/dashboard-mobile.png`,
    fullPage: true,
  });
  await page.getByRole("link", { name: "Expenses", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Your expenses" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Enter local demo" }),
  ).toBeVisible();
});

test("tablet navigation is accessible and receipt page fits", async ({
  page,
}) => {
  await page.setViewportSize({ width: 820, height: 1180 });
  await page.goto("/receipts");
  await expect(
    page.getByRole("heading", { name: "Upload a receipt", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Budget & alerts" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});
