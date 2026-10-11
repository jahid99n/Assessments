import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial" });
test.beforeEach(async ({ page }) => {
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (
      url.hostname.includes("amazonaws.com") &&
      route.request().method() === "POST"
    ) {
      // Preserve the real XMLHttpRequest multipart body; replace only AWS transport.
      const response = await route.fetch({ url: "http://127.0.0.1:5181/s3" });
      return route.fulfill({ response });
    }
    if (!["localhost", "127.0.0.1"].includes(url.hostname)) {
      await route.abort();
      throw new Error("External request prohibited: " + url.hostname);
    }
    await route.continue();
  });
  await page.goto("/");
  await expect(page.locator("main h1")).toBeVisible();
});

test("real JS adapter exercises nine Python routes, totals, paging and isolation", async ({
  page,
  request,
}) => {
  const result = await page.evaluate(async () => {
    const api = window.integrationApi();
    const { month } = await api.budget();
    const base = {
      merchant: "Integration manual",
      receiptDate: `${month}-04`,
      total: "0.10",
      category: "Dining",
      currency: "AUD",
    };
    const first = await api.create(base);
    const second = await api.create({ ...base, total: "0.20" });
    const before = await api.stats();
    const budget = await api.saveBudget({ month, monthlyLimit: "100.00" });
    const detail = await api.detail(first.expenseId);
    await api.update(first.expenseId, { ...base, total: "1.10" });
    const changed = await api.budget(month);
    const pages = [];
    let cursor;
    do {
      const p = await api.list({ limit: 1, cursor });
      pages.push(...p.items);
      cursor = p.nextCursor;
    } while (cursor);
    const filtered = await api.list({
      from: `${month}-01`,
      to: `${month}-31`.replace(/-31$/, "-28"),
      category: "Dining",
    });
    const bob = window.integrationApi("bob");
    let forbidden;
    try {
      await bob.detail(first.expenseId);
    } catch (e) {
      forbidden = e.status;
    }
    let forged;
    try {
      await api.list({ userId: "bob" });
    } catch (e) {
      forged = e.status;
    }
    const bobList = await bob.list({});
    const pending = await api.uploadPermission("image/jpeg");
    const status = await api.detail(pending.expenseId);
    await api.remove(first.expenseId);
    await api.remove(second.expenseId);
    const after = await api.stats();
    await api.remove(pending.expenseId);
    return {
      before,
      budget,
      detail,
      changed,
      pages,
      filtered,
      forbidden,
      forged,
      bobList,
      status,
      after,
    };
  });
  expect(result.before.thisMonth.total).toBe(0.3);
  expect(result.budget.spent).toBe(0.3);
  expect(result.changed.spent).toBe(1.3);
  expect(result.pages).toHaveLength(2);
  expect(result.filtered.items).toHaveLength(2);
  expect(result.detail.total).toBe(0.1);
  expect(result.forbidden).toBe(404);
  expect(result.forged).toBe(400);
  expect(result.bobList.items).toHaveLength(0);
  expect(result.status.status).toBe("PENDING");
  expect(result.after.thisMonth.total).toBe(0);
  expect((await request.get("http://127.0.0.1:5181/expenses")).status()).toBe(
    401,
  );
});

test("React manual expense form saves and edits real backend records", async ({
  page,
}) => {
  await page.getByRole("link", { name: "Expenses", exact: true }).click();
  await page.getByRole("button", { name: "Add expense" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Merchant", { exact: true }).fill("UI to Python");
  await dialog.getByLabel("Total (AUD)", { exact: true }).fill("12.30");
  await dialog.getByRole("button", { name: "Save expense" }).click();
  await expect(
    page.getByRole("button", { name: "Edit UI to Python" }),
  ).toBeVisible();
  const saved = await page.evaluate(async () =>
    (await window.integrationApi().list({})).items.find(
      (x) => x.merchant === "UI to Python",
    ),
  );
  expect(saved.total).toBe(12.3);
  await page.getByRole("button", { name: "Edit UI to Python" }).click();
  await dialog.getByLabel("Total (AUD)", { exact: true }).fill("15.30");
  await dialog.getByRole("button", { name: "Save expense" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  expect(
    await page.evaluate(
      async (id) => (await window.integrationApi().detail(id)).total,
      saved.expenseId,
    ),
  ).toBe(15.3);
  await page.evaluate(
    (id) => window.integrationApi().remove(id),
    saved.expenseId,
  );
});

async function upload(page, content, mime = "image/jpeg") {
  await page.goto("/receipts");
  await page
    .getByLabel("Receipt image")
    .setInputFiles({
      name: mime === "image/png" ? "test.png" : "test.jpg",
      mimeType: mime,
      buffer: content,
    });
  await page
    .getByRole("button", { name: "Upload receipt", exact: true })
    .click();
}
const jpeg = Buffer.from([
  255,
  216,
  255,
  ...Buffer.from("synthetic OCR fixture"),
]);
const png = Buffer.concat([
  Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
  Buffer.from("synthetic PNG fixture"),
]);

test("React → signed POST → processor → DynamoDB → dashboard; replay and duplicate protection", async ({
  page,
}) => {
  await upload(page, jpeg);
  await expect(
    page.getByRole("heading", { name: "Expense ready to review" }),
  ).toBeVisible();
  const item = await page.evaluate(async () =>
    (await window.integrationApi().list({})).items.find(
      (x) => x.merchant === "Coles Integration",
    ),
  );
  expect(item.total).toBe(40);
  expect(item.gst).toBe(0.38);
  expect(item.category).toBe("Groceries");
  await page.request.post("http://127.0.0.1:5181/__test/replay", {
    data: { expenseId: item.expenseId },
  });
  expect(
    await page.evaluate(
      async () => (await window.integrationApi().stats()).thisMonth.total,
    ),
  ).toBe(40);
  await page.goto("/");
  await expect(page.locator(".summary-card").first()).toContainText("$40.00");
  await upload(page, jpeg);
  await expect(
    page.getByText("Duplicate receipt: this exact image was already submitted"),
  ).toBeVisible();
  expect(
    await page.evaluate(
      async () => (await window.integrationApi().stats()).thisMonth.total,
    ),
  ).toBe(40);
});

test("PNG and Australian day-first dates traverse real processor and UI", async ({
  page,
  request,
}) => {
  await request.post("http://127.0.0.1:5181/__test/scenario", {
    data: { mode: "success", date: "04/11/2024" },
  });
  await upload(page, png, "image/png");
  await expect(
    page.getByRole("heading", { name: "Expense ready to review" }),
  ).toBeVisible();
  const historical = await page.evaluate(() =>
    window.integrationApi().list({ month: "2024-11" }),
  );
  expect(historical.items).toHaveLength(1);
  expect(historical.items[0].receiptDate).toBe("2024-11-04");
  expect(
    await page.evaluate(
      async () => (await window.integrationApi().budget("2024-11")).spent,
    ),
  ).toBe(40);
});

test("missing fields fail visibly; transient failure safely recovers on original event replay", async ({
  page,
  request,
}) => {
  await request.post("http://127.0.0.1:5181/__test/scenario", {
    data: { mode: "missing_total" },
  });
  await upload(page, Buffer.concat([jpeg, Buffer.from("missing")]));
  await expect(
    page.getByRole("heading", { name: "Receipt could not be processed" }),
  ).toBeVisible();
  await expect(
    page.getByText("Receipt amount is missing or invalid"),
  ).toBeVisible();
  await request.post("http://127.0.0.1:5181/__test/scenario", {
    data: { mode: "transient" },
  });
  await upload(page, Buffer.concat([jpeg, Buffer.from("retry")]));
  await expect(
    page.getByText("Processing service unavailable; retry pending"),
  ).toBeVisible();
  const failed = await page.evaluate(async () =>
    (await window.integrationApi().list({})).items.find((x) => x.retryable),
  );
  await request.post("http://127.0.0.1:5181/__test/replay", {
    data: { expenseId: failed.expenseId },
  });
  await page.getByRole("button", { name: "Check receipt status" }).click();
  await expect(
    page.getByRole("heading", { name: "Expense ready to review" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      async () => (await window.integrationApi().stats()).thisMonth.total,
    ),
  ).toBe(80);
});

test("signed policy rejects modified ownership, size and MIME; invalid image fails processor", async ({
  page,
}) => {
  const results = await page.evaluate(async () => {
    const permission = await window
      .integrationApi()
      .uploadPermission("image/jpeg");
    const submit = async (change, size) => {
      const form = new FormData();
      for (const [k, v] of Object.entries({
        ...permission.upload.fields,
        ...change,
      }))
        form.append(k, v);
      form.append(
        "file",
        new Blob([new Uint8Array(size)], { type: "image/jpeg" }),
        "test.jpg",
      );
      return (
        await fetch("http://127.0.0.1:5181/s3", { method: "POST", body: form })
      ).status;
    };
    return [
      await submit({ "x-amz-meta-userid": "bob" }, 5),
      await submit({ "Content-Type": "application/pdf" }, 5),
      await submit({}, 5242881),
      await submit({}, 5242880),
    ];
  });
  expect(results).toEqual([403, 403, 403, 204]);
  await upload(page, Buffer.from("not an image"));
  await expect(
    page.getByText("Receipt file does not match its image type"),
  ).toBeVisible();
});
