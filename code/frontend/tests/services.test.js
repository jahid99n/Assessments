import { describe, expect, it, vi } from "vitest";
import { assertBuildMode, configError, readConfig } from "../src/config.js";
import { createApi, allExpenses } from "../src/lib/api.js";
import {
  amount,
  cents,
  validateFile,
  validateExpense,
  sydneyDay,
} from "../src/lib/format.js";
import { pollReceipt, postReceipt } from "../src/lib/upload.js";
import { createDemoApi, DEMO_KEY } from "../src/lib/demo.js";

const expense = {
  merchant: "Coles",
  receiptDate: "2026-10-10",
  total: "40.00",
  category: "Groceries",
};
function client(response = { items: [] }, status = 200) {
  const fetcher = vi.fn(async () => ({
    ok: status < 400,
    status,
    json: async () => response,
  }));
  const onUnauthorized = vi.fn();
  return {
    api: createApi({
      baseUrl: "https://api.example.test",
      getToken: async () => "TEST_TOKEN",
      fetcher,
      onUnauthorized,
    }),
    fetcher,
    onUnauthorized,
  };
}

describe("API contract", () => {
  it("uses the nine existing routes and ID token header", async () => {
    const { api, fetcher } = client();
    await api.list({ month: "2026-10", cursor: "a+b=" });
    await api.detail("id");
    await api.create(expense);
    await api.update("id", expense);
    await api.remove("id");
    await api.stats();
    await api.budget("2026-10");
    await api.saveBudget({ month: "2026-10", monthlyLimit: "100.00" });
    await api.uploadPermission("image/png");
    expect(
      fetcher.mock.calls.map(
        ([url, options]) => `${options.method} ${new URL(url).pathname}`,
      ),
    ).toEqual([
      "GET /expenses",
      "GET /expenses/id",
      "POST /expenses",
      "PUT /expenses/id",
      "DELETE /expenses/id",
      "GET /stats",
      "GET /budget",
      "PUT /budget",
      "POST /upload-url",
    ]);
    expect(new URL(fetcher.mock.calls[0][0]).searchParams.get("cursor")).toBe(
      "a+b=",
    );
    for (const [, options] of fetcher.mock.calls) {
      expect(options.headers.Authorization).toBe("Bearer TEST_TOKEN");
      expect(options.credentials).toBe("omit");
    }
    expect(JSON.parse(fetcher.mock.calls[2][1].body).total).toBe("40.00");
  });
  it("never calls the API without a token", async () => {
    const fetcher = vi.fn();
    const expired = vi.fn();
    const api = createApi({
      baseUrl: "https://api.example.test",
      getToken: async () => null,
      fetcher,
      onUnauthorized: expired,
    });
    await expect(api.stats()).rejects.toThrow("session has expired");
    expect(fetcher).not.toHaveBeenCalled();
    expect(expired).toHaveBeenCalled();
  });
  it("handles token refresh failure without exposing its details", async () => {
    const api = createApi({
      baseUrl: "https://api.example.test",
      getToken: async () => {
        throw new Error("internal auth details");
      },
    });
    await expect(api.stats()).rejects.toThrow("could not be refreshed");
  });
  it("invalidates a rejected session", async () => {
    const { api, onUnauthorized } = client({ error: "bad JWT" }, 401);
    await expect(api.stats()).rejects.toThrow("sign in again");
    expect(onUnauthorized).toHaveBeenCalled();
  });
  it("sanitises server failures", async () => {
    const { api } = client({ error: "private configuration" }, 500);
    await expect(api.stats()).rejects.toThrow("temporarily unavailable");
  });
  it("preserves useful validation errors", async () => {
    const { api } = client(
      { error: "Only completed expenses can be edited" },
      409,
    );
    await expect(api.update("id", expense)).rejects.toThrow("Only completed");
  });
  it("continues through empty filtered pages", async () => {
    const list = vi
      .fn()
      .mockResolvedValueOnce({ items: [], nextCursor: "two" })
      .mockResolvedValueOnce({ items: [expense] });
    expect(await allExpenses({ list }, {})).toEqual([expense]);
    expect(list).toHaveBeenCalledTimes(2);
  });
  it("rejects repeating cursors rather than hanging", async () => {
    await expect(
      allExpenses(
        { list: async () => ({ items: [], nextCursor: "same" }) },
        {},
      ),
    ).rejects.toThrow("stopped progressing");
  });
  it("cancels obsolete requests", async () => {
    const { api, fetcher } = client();
    const controller = new AbortController();
    controller.abort();
    await expect(api.stats(controller.signal)).rejects.toMatchObject({
      name: "AbortError",
    });
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("reports unreachable API without automatically repeating mutations", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("network"));
    const api = createApi({
      baseUrl: "https://api.example.test",
      getToken: async () => "test",
      fetcher,
    });
    await expect(api.create(expense)).rejects.toThrow(
      "may already have been saved",
    );
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});

describe("receipt workflow", () => {
  it.each(["image/jpeg", "image/png"])("accepts %s", (type) =>
    expect(validateFile(new File(["bytes"], "receipt", { type })).size).toBe(5),
  );
  it.each([
    { type: "application/pdf", size: 10 },
    { type: "image/gif", size: 10 },
    { type: "image/png", size: 0 },
    { type: "image/png", size: 5242881 },
  ])("rejects invalid file %j", (file) =>
    expect(() => validateFile(file)).toThrow(),
  );
  it("accepts the exact size boundary", () =>
    expect(validateFile({ type: "image/jpeg", size: 5242880 }).size).toBe(
      5242880,
    ));
  it("sends signed fields unchanged with file last and no JWT", async () => {
    const xhr = {
      open: vi.fn(),
      upload: {},
      status: 204,
      send: vi.fn(() => queueMicrotask(() => xhr.onload())),
      abort: vi.fn(),
    };
    const progress = vi.fn();
    await postReceipt(
      {
        upload: {
          url: "https://bucket.s3.amazonaws.com/",
          fields: {
            key: "receipts/user/id.jpg",
            policy: "signed",
            "x-amz-meta-userid": "user",
          },
        },
      },
      new File(["jpeg"], "r.jpg", { type: "image/jpeg" }),
      { xhrFactory: () => xhr, onProgress: progress },
    );
    const fields = [...xhr.send.mock.calls[0][0].entries()];
    expect(fields.map(([key]) => key)).toEqual([
      "key",
      "policy",
      "x-amz-meta-userid",
      "file",
    ]);
    expect(fields[1][1]).toBe("signed");
    expect(xhr.open).toHaveBeenCalledWith(
      "POST",
      "https://bucket.s3.amazonaws.com/",
    );
    xhr.upload.onprogress({ lengthComputable: true, loaded: 4, total: 8 });
    expect(progress).toHaveBeenCalledWith(50);
  });
  it("rejects S3 upload failure", async () => {
    const xhr = {
      open: vi.fn(),
      upload: {},
      status: 403,
      send: () => queueMicrotask(() => xhr.onload()),
      abort: vi.fn(),
    };
    await expect(
      postReceipt(
        { upload: { url: "https://bucket.test/", fields: {} } },
        new File(["x"], "r.png", { type: "image/png" }),
        { xhrFactory: () => xhr },
      ),
    ).rejects.toThrow("rejected");
  });
  it("does not treat pending/processing as successful extraction", async () => {
    const detail = vi
      .fn()
      .mockResolvedValueOnce({ status: "PENDING" })
      .mockResolvedValueOnce({ status: "PROCESSING" })
      .mockResolvedValueOnce({ status: "PROCESSED", total: 40 });
    const statuses = vi.fn();
    expect(
      (
        await pollReceipt({ detail }, "id", {
          onStatus: statuses,
          sleep: async () => {},
        })
      ).total,
    ).toBe(40);
    expect(detail).toHaveBeenCalledTimes(3);
  });
  it("returns terminal extraction failure", async () =>
    expect(
      await pollReceipt(
        {
          detail: async () => ({
            status: "FAILED",
            errorMessage: "Missing total",
          }),
        },
        "id",
      ),
    ).toEqual({ status: "FAILED", errorMessage: "Missing total" }));
  it("bounds polling and leaves an unknown final state", async () => {
    const detail = vi.fn(async () => ({ status: "PROCESSING" }));
    expect(
      await pollReceipt({ detail }, "id", {
        attempts: 3,
        sleep: async () => {},
      }),
    ).toBeNull();
    expect(detail).toHaveBeenCalledTimes(3);
  });
  it("cancels polling", async () => {
    const controller = new AbortController();
    controller.abort();
    await expect(
      pollReceipt({ detail: vi.fn() }, "id", { signal: controller.signal }),
    ).rejects.toMatchObject({ name: "AbortError" });
  });
});

describe("financial validation and demo isolation", () => {
  it.each(["-1", "1.001", "NaN", "Infinity", "100000001"])(
    "rejects invalid money %s",
    (value) => expect(() => amount(value)).toThrow(),
  );
  it("adds cents exactly", () =>
    expect(cents("0.10") + cents("0.20")).toBe(30));
  it("uses Sydney date at the UTC boundary", () =>
    expect(sydneyDay(new Date("2026-10-11T22:00:00Z"))).toBe("2026-10-12"));
  it.each(["2026-02-30", "2026-13-01", "04/11/2024"])(
    "rejects invalid API date %s",
    (receiptDate) =>
      expect(() => validateExpense({ ...expense, receiptDate })).toThrow(
        "valid transaction date",
      ),
  );
  it("persists demo interactions without network calls", async () => {
    const api = createDemoApi();
    const item = await api.create(expense);
    await api.update(item.expenseId, { ...expense, total: "50.10" });
    const reloaded = createDemoApi();
    expect((await reloaded.detail(item.expenseId)).total).toBe("50.10");
    await reloaded.remove(item.expenseId);
    expect(fetch).not.toHaveBeenCalled();
    expect(localStorage.getItem(DEMO_KEY)).toBeTruthy();
  });
  it("keeps budgets separate by month", async () => {
    const api = createDemoApi();
    await api.saveBudget({ month: "2026-08", monthlyLimit: "100" });
    await api.saveBudget({ month: "2026-09", monthlyLimit: "200" });
    expect((await api.budget("2026-08")).monthlyLimit).toBe(100);
    expect((await api.budget("2026-09")).monthlyLimit).toBe(200);
  });
});

describe("production separation", () => {
  it("defaults to real mode", () =>
    expect(readConfig({}, true).demo).toBe(false));
  it("requires an explicit dev flag", () =>
    expect(readConfig({ VITE_APP_MODE: "demo" }, true).demo).toBe(true));
  it("rejects demo at production runtime", () =>
    expect(() => readConfig({ VITE_APP_MODE: "demo" }, false)).toThrow(
      "development-only",
    ));
  it("blocks demo build regardless of Vite mode name", () =>
    expect(() => assertBuildMode("build", "demo")).toThrow("cannot contain"));
  it("blocks development NODE_ENV build bypass", () =>
    expect(() => assertBuildMode("build", "production", "development")).toThrow(
      "cannot contain",
    ));
  it("permits production build and flags missing AWS config", () => {
    expect(() => assertBuildMode("build", "production")).not.toThrow();
    expect(configError(readConfig({}, false))).toContain("not configured");
  });
});
