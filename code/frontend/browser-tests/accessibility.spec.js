import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

for (const route of ["/", "/expenses", "/receipts", "/budget"]) {
  test(`accessibility: ${route}`, async ({ page }) => {
    await page.goto(route);
    await expect(page.locator("main h1")).toBeVisible();
    await expect(page.getByText("Loading…", { exact: true })).toHaveCount(0);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(results.violations).toEqual([]);
  });
}

test("accessibility: expense dialog", async ({ page }) => {
  await page.goto("/expenses");
  await page.getByRole("button", { name: "Add expense" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
});
